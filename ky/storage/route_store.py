"""M13 versioned RoutePlan storage; see ``contracts/route_plan.md`` and
``contracts/state_sources.md``.

Public interface: :class:`RoutePlanStore`, ``current()``, ``read_state_sources()``,
``read_revision_context()``, ``load_revision()``,
``provenance()``, and ``write_route_plan()``. Every immutable route revision keeps
its own provenance entry in the manifest (B4).
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

import yaml

from ky.models import ContractError, load_yaml_text
from ky.schedule.planning import (
    RoutePlan,
    parse_route_plan,
    route_plan_to_mapping,
    validate_route_plan,
)
from ky.storage.atomic import replace_bytes
from ky.storage.day_plan_store import StorageError, WriteReport

__all__ = ["RoutePlanReadResult", "RouteRevisionContext", "RoutePlanStore"]


@dataclass(frozen=True)
class RoutePlanReadResult:
    """Current route and hashes of the manifest and revision bytes parsed for it."""

    route: RoutePlan | None
    sources: Mapping[str, str]


@dataclass(frozen=True)
class RouteRevisionContext:
    """One target revision validated from a manifest snapshot and its provenance."""

    current_revision: int
    actor: str | None
    input_hash: str | None
    route: RoutePlan | None


def _yaml_bytes(value: Any) -> bytes:
    return yaml.safe_dump(
        value, allow_unicode=True, sort_keys=False, default_flow_style=False
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _manifest_mapping(
    raw: object, expected: set[str], path: str, label: str
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise StorageError(f"{label} must be a mapping", path)
    if any(not isinstance(key, str) for key in raw):
        raise StorageError(f"{label} keys must be strings", path)
    if set(raw) != expected:
        unknown = sorted(set(raw) - expected)
        field = unknown[0] if unknown else sorted(expected - set(raw))[0]
        reason = "unknown field" if unknown else "required field is missing"
        raise StorageError(f"{reason}: {field}", f"{path}.{field}")
    return raw


def _parse_manifest_entry(raw: object, index: int, prefix: str) -> dict[str, Any]:
    entry_prefix = f"{prefix}.revisions[{index}]"
    entry = _manifest_mapping(
        raw,
        {"revision", "path", "sha256", "actor", "input_hash"},
        entry_prefix,
        "revision entry",
    )
    revision = entry["revision"]
    if type(revision) is not int:
        raise StorageError("revision must be an integer", f"{entry_prefix}.revision")
    expected_revision = index + 1
    if revision != expected_revision:
        raise StorageError(
            f"revision must be {expected_revision}, got {revision}",
            f"{entry_prefix}.revision",
        )
    expected_path = f"route--r{revision}.yaml"
    if entry["path"] != expected_path:
        raise StorageError(f"path must be {expected_path!r}", f"{entry_prefix}.path")
    if not _is_sha256(entry["sha256"]):
        raise StorageError(
            "sha256 must be lowercase 64-character hex", f"{entry_prefix}.sha256"
        )
    _validate_provenance(entry["actor"], entry["input_hash"], entry_prefix)
    return entry


def _validate_provenance(actor: object, input_hash: object, prefix: str) -> None:
    actor_path = f"{prefix}.actor" if prefix else "actor"
    hash_path = f"{prefix}.input_hash" if prefix else "input_hash"
    if not isinstance(actor, str):
        raise StorageError("actor must be a string", actor_path)
    if input_hash is not None and not _is_sha256(input_hash):
        raise StorageError(
            "input_hash must be null or lowercase 64-character hex",
            hash_path,
        )


def _parse_manifest(raw: object, path: Path) -> dict[str, Any]:
    """Validate the closed manifest shape before it can select route files."""
    prefix = path.as_posix()
    manifest = _manifest_mapping(
        raw, {"schema_version", "route_id", "revisions"}, prefix, "manifest"
    )

    schema = manifest["schema_version"]
    if type(schema) is not int or schema != 1:
        raise StorageError("schema_version must be integer 1", f"{prefix}.schema_version")
    route_id = manifest["route_id"]
    if not isinstance(route_id, str) or not route_id.strip():
        raise StorageError("route_id must be a non-empty string", f"{prefix}.route_id")
    revisions = manifest["revisions"]
    if not isinstance(revisions, list):
        raise StorageError("revisions must be a list", f"{prefix}.revisions")
    manifest["revisions"] = [
        _parse_manifest_entry(entry, index, prefix)
        for index, entry in enumerate(revisions)
    ]
    return manifest


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


class RoutePlanStore:
    """Append immutable route revisions below one workspace-owned directory."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.manifest_path = self.root / "routes_manifest.yaml"

    def _read_manifest(self) -> dict[str, Any]:
        if not self.manifest_path.exists():
            return {"schema_version": 1, "route_id": None, "revisions": []}
        if not self.manifest_path.is_file():
            raise StorageError("manifest path is not a file", self.manifest_path.as_posix())
        try:
            data = self.manifest_path.read_bytes()
        except OSError as exc:
            raise StorageError(
                f"cannot read routes manifest: {exc}", self.manifest_path.as_posix()
            ) from exc
        return self._parse_manifest_bytes(data)

    def _parse_manifest_bytes(self, data: bytes) -> dict[str, Any]:
        """Parse the manifest from the byte sequence already read by the caller."""
        try:
            raw = load_yaml_text(data.decode("utf-8"), source=self.manifest_path.as_posix())
        except (UnicodeError, ContractError) as exc:
            raise StorageError(
                f"cannot read routes manifest: {exc}", self.manifest_path.as_posix()
            ) from exc
        return _parse_manifest(raw, self.manifest_path)

    def read_state_sources(self) -> RoutePlanReadResult:
        """Read the manifest and current route once, hashing each parsed byte sequence."""
        if self.root.exists() and not self.root.is_dir():
            # An existing non-directory is an invalid registered path, not an empty store
            # (sol round 136, M2).
            raise StorageError("store root is not a directory", self.root.as_posix())
        if not self.manifest_path.exists():
            return RoutePlanReadResult(None, MappingProxyType({}))
        try:
            manifest_bytes = self.manifest_path.read_bytes()
        except OSError as exc:
            raise StorageError(
                f"cannot read routes manifest: {exc}", self.manifest_path.as_posix()
            ) from exc
        manifest = self._parse_manifest_bytes(manifest_bytes)
        sources = {
            self.manifest_path.relative_to(self.root).as_posix(): _sha256(manifest_bytes)
        }
        revisions = manifest["revisions"]
        if not revisions:
            return RoutePlanReadResult(None, MappingProxyType(sources))

        entry = revisions[-1]
        path, data = self._read_entry_bytes(entry)
        route = self._load_entry_from_bytes(entry, manifest["route_id"], path, data)
        actual = _sha256(data)
        sources[path.relative_to(self.root).as_posix()] = actual
        return RoutePlanReadResult(route, MappingProxyType(sources))

    def read_revision_context(self, revision: int) -> RouteRevisionContext:
        """Read the manifest once and verify the requested historical route revision."""
        if type(revision) is not int or revision < 1:
            raise StorageError("revision must be an integer >= 1", "revision")
        if self.root.exists() and not self.root.is_dir():
            raise StorageError("store root is not a directory", self.root.as_posix())
        if not self.manifest_path.exists():
            return RouteRevisionContext(0, None, None, None)
        if not self.manifest_path.is_file():
            raise StorageError("manifest path is not a file", self.manifest_path.as_posix())
        try:
            manifest_bytes = self.manifest_path.read_bytes()
        except OSError as exc:
            raise StorageError(
                f"cannot read routes manifest: {exc}", self.manifest_path.as_posix()
            ) from exc
        manifest = self._parse_manifest_bytes(manifest_bytes)
        entries = manifest["revisions"]
        current = entries[-1]["revision"] if entries else 0
        for entry in entries:
            if entry["revision"] == revision:
                path, data = self._read_entry_bytes(entry)
                route = self._load_entry_from_bytes(entry, manifest["route_id"], path, data)
                return RouteRevisionContext(
                    current, entry["actor"], entry["input_hash"], route,
                )
        return RouteRevisionContext(current, None, None, None)

    def _read_entry_bytes(self, entry: dict[str, Any]) -> tuple[Path, bytes]:
        relative = entry.get("path")
        if not isinstance(relative, str):
            raise StorageError("manifest path must be a string", "path")
        path = self.root / relative
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise StorageError(f"cannot read route revision: {exc}", path.as_posix()) from exc
        return path, data

    def _load_entry_from_bytes(
        self, entry: dict[str, Any], route_id: str, path: Path, data: bytes
    ) -> RoutePlan:
        """Verify and parse a revision from the exact bytes read by the caller."""
        actual = _sha256(data)
        expected = entry.get("sha256")
        if actual != expected:
            raise StorageError(
                f"SHA-256 mismatch (manifest {expected}, actual {actual})", path.as_posix()
            )
        try:
            raw = load_yaml_text(data.decode("utf-8"), source=path.as_posix())
            plan = parse_route_plan(raw, path.as_posix())
        except (UnicodeError, ContractError, ValueError) as exc:
            raise StorageError(f"invalid route revision: {exc}", path.as_posix()) from exc
        if plan.revision != entry["revision"]:
            raise StorageError(
                "route revision does not match manifest entry", f"{path.as_posix()}.revision"
            )
        if plan.route_id != route_id:
            raise StorageError(
                "route route_id does not match manifest", f"{path.as_posix()}.route_id"
            )
        return plan

    def _load_entry(self, entry: dict[str, Any], route_id: str) -> RoutePlan:
        path, data = self._read_entry_bytes(entry)
        return self._load_entry_from_bytes(entry, route_id, path, data)

    def current(self) -> RoutePlan | None:
        manifest = self._read_manifest()
        revisions = manifest["revisions"]
        return None if not revisions else self._load_entry(revisions[-1], manifest["route_id"])

    def load_revision(self, revision: int) -> RoutePlan:
        manifest = self._read_manifest()
        for entry in manifest["revisions"]:
            if entry.get("revision") == revision:
                return self._load_entry(entry, manifest["route_id"])
        raise StorageError(f"revision {revision} is not present", "revision")

    def provenance(self, revision: int) -> tuple[str, str | None]:
        manifest = self._read_manifest()
        for entry in manifest["revisions"]:
            if entry.get("revision") == revision:
                return entry.get("actor", "unknown"), entry.get("input_hash")
        raise StorageError(f"revision {revision} is not present", "revision")

    def write_route_plan(
        self,
        plan: RoutePlan,
        *,
        actor: str = "unknown",
        input_hash: str | None = None,
    ) -> WriteReport:
        """Append exactly the next revision, leaving every prior version byte-for-byte intact."""
        _validate_provenance(actor, input_hash, "")
        validate_route_plan(plan)
        if not self.root.exists() and plan.revision != 1:
            raise StorageError("first revision must be 1", "revision")
        self.root.mkdir(parents=True, exist_ok=True)
        # The lock makes the revision compare-and-swap atomic across processes. A crash can
        # leave it behind; recovery is manual (contracts/route_plan.md), never automatic.
        lock_path = self.root / ".routes.lock"
        try:
            descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise StorageError(
                "another route write is in progress, or a crashed write left the lock; "
                "delete it only after confirming no write is running",
                lock_path.as_posix(),
            ) from exc
        try:
            os.close(descriptor)
            return self._write_locked(plan, actor=actor, input_hash=input_hash)
        finally:
            lock_path.unlink(missing_ok=True)

    def _write_locked(
        self, plan: RoutePlan, *, actor: str, input_hash: str | None
    ) -> WriteReport:
        manifest = self._read_manifest()
        revisions = manifest["revisions"]
        latest = revisions[-1] if revisions else None
        expected_revision = 1 if latest is None else latest.get("revision", 0) + 1
        if plan.revision != expected_revision:
            raise StorageError(
                f"expected revision {expected_revision}, got {plan.revision}", "revision"
            )
        if latest is not None and plan.route_id != manifest["route_id"]:
            raise StorageError(
                f"route_id must remain {manifest['route_id']!r}", "route_id"
            )
        if latest is None and plan.revision != 1:
            raise StorageError("first revision must be 1", "revision")

        filename = f"route--r{plan.revision}.yaml"
        final_path = self.root / filename
        if final_path.exists():
            raise self._unregistered_revision_error(final_path)
        data = _yaml_bytes(route_plan_to_mapping(plan))
        digest = _sha256(data)
        published_identity = self._write_version(final_path, data)

        updated = {
            "schema_version": 1,
            "route_id": plan.route_id,
            "revisions": [
                *revisions,
                {
                    "revision": plan.revision,
                    "path": filename,
                    "sha256": digest,
                    "actor": actor,
                    "input_hash": input_hash,
                },
            ],
        }
        try:
            replace_bytes(self.manifest_path, _yaml_bytes(updated))
        except Exception:
            try:
                current = os.stat(final_path)
            except OSError:
                pass
            else:
                if (current.st_dev, current.st_ino) == published_identity:
                    try:
                        final_path.unlink(missing_ok=True)
                    except OSError:
                        pass
            raise
        return WriteReport(path=final_path.as_posix(), sha256=digest, version=plan.revision)

    @staticmethod
    def _unregistered_revision_error(path: Path) -> StorageError:
        return StorageError(
            "未登记的版本文件，确认后手动删除",
            path.as_posix(),
        )

    @staticmethod
    def _write_version(final_path: Path, data: bytes) -> tuple[int, int]:
        descriptor, temp_name = tempfile.mkstemp(
            prefix=f".{final_path.name}.", suffix=".tmp", dir=final_path.parent
        )
        temporary = Path(temp_name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
            parsed = load_yaml_text(
                temporary.read_text(encoding="utf-8"), source=temporary.as_posix()
            )
            parse_route_plan(parsed, temporary.as_posix())
            # Take the identity from our own temporary, before publishing: the hard link shares
            # its inode, and stat-ing final_path afterwards could record a file swapped in
            # between link and stat (sol round 105, A1).
            published = os.stat(temporary)
            try:
                os.link(temporary, final_path)
            except FileExistsError as exc:
                raise RoutePlanStore._unregistered_revision_error(final_path) from exc
            except OSError as exc:
                raise StorageError(
                    f"cannot publish version with a hard link: {exc}", final_path.as_posix()
                ) from exc
            return published.st_dev, published.st_ino
        finally:
            temporary.unlink(missing_ok=True)
