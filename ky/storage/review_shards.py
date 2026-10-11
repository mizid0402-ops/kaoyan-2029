"""M13 deterministic bounded shards; see ``contracts/state_sources.md``.

Public read interfaces include ``ReviewShardStore.load()`` and
``ReviewShardStore.read_state_sources()``.

The manifest is the only visible commit point.  New shard files are written
under versioned names before the manifest is replaced.  Consequently a failed
write can leave an unreferenced orphan (which is safe to garbage-collect), but
it cannot make the previous manifest observe a partially written shard.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Iterable, Mapping, Sequence

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

from ky.models import (
    ContractError,
    REVIEWS_SCHEMA_VERSION,
    ReviewItem,
    load_review_items,
    validate_review_item,
    validate_review_items,
)

__all__ = [
    "DEFAULT_BUCKET_COUNT",
    "DEFAULT_SHARD_SIZE",
    "Manifest",
    "ReviewQueueStateSources",
    "ReviewShardStore",
    "ShardDescriptor",
    "StorageDiagnostic",
    "StorageError",
    "WriteReport",
    "diagnose_shards",
    "load_review_queue",
    "load_sharded_reviews",
    "partition_review_items",
    "upgrade_legacy_queue",
    "write_review_queue",
]

MANIFEST_SCHEMA_VERSION = 2
SHARD_SCHEMA_VERSION = REVIEWS_SCHEMA_VERSION
DEFAULT_SHARD_SIZE = 250
DEFAULT_BUCKET_COUNT = 16
MANIFEST_NAME = "manifest.yaml"
_SHARD_NAME = re.compile(r"^[A-Za-z0-9_-]+--b[0-9]{2}--[0-9]{4}--v[0-9]+\.yaml$")


class StorageError(ContractError):
    """A storage/manifest error with a precise file-oriented path."""


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise StorageError(f"expected a mapping, got {type(value).__name__}", path)
    return value


def _integer(value: Any, path: str, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise StorageError(f"expected an integer, got {type(value).__name__}", path)
    if minimum is not None and value < minimum:
        raise StorageError(f"must be >= {minimum}, got {value}", path)
    return value


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StorageError("expected a non-empty string", path)
    return value


def _unknown(node: Mapping[str, Any], allowed: set[str], path: str) -> None:
    extra = sorted(set(node) - allowed)
    if extra:
        key = extra[0]
        raise StorageError(f"unknown field {key!r}", f"{path}.{key}" if path else key)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_manifest_payload(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _yaml_bytes(value: Any) -> bytes:
    if yaml is None:  # pragma: no cover
        raise StorageError("PyYAML is required for review shard storage")
    return yaml.safe_dump(
        value,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    ).encode("utf-8")


def _read_yaml(path: Path) -> Any:
    if not path.is_file():
        raise StorageError(f"file does not exist: {path}", path.as_posix())
    if yaml is None:  # pragma: no cover
        raise StorageError("PyYAML is required for review shard storage", path.as_posix())
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise StorageError(f"invalid YAML: {exc}", path.as_posix()) from exc


def _item_mapping(item: ReviewItem) -> dict[str, Any]:
    schedule = item.schedule
    schedule_mapping = {
        "mode": schedule.mode,
        "phase": schedule.phase,
        "interval_days": schedule.interval_days,
        "ease_factor": schedule.ease_factor,
        "repetitions": schedule.repetitions,
        "lapses": schedule.lapses,
    }
    if schedule.mode == "fsrs" or any((
        schedule.stability is not None,
        schedule.difficulty is not None,
        schedule.fsrs_reviewed_on is not None,
    )):
        schedule_mapping.update({
            "stability": schedule.stability,
            "difficulty": schedule.difficulty,
            "fsrs_reviewed_on": (
                schedule.fsrs_reviewed_on.isoformat()
                if schedule.fsrs_reviewed_on is not None else None
            ),
        })
    return {
        "review_id": item.review_id,
        "revision": item.revision,
        "subject_id": item.subject_id,
        "knowledge_point_id": item.knowledge_point_id,
        "title": item.title,
        "granularity": item.granularity,
        "state": item.state,
        "estimated_minutes": item.estimated_minutes,
        "introduced_on": item.introduced_on.isoformat(),
        "due_date": item.due_date.isoformat(),
        "last_reviewed_on": (
            item.last_reviewed_on.isoformat() if item.last_reviewed_on is not None else None
        ),
        "schedule": schedule_mapping,
        "defer_count": item.defer_count,
        "last_quality": item.last_quality,
        "self_rating": item.last_self_rating,
    }


def _normalise_items(items: Iterable[ReviewItem | Mapping[str, Any]]) -> tuple[ReviewItem, ...]:
    raw: list[Any] = []
    for item in items:
        raw.append(_item_mapping(item) if isinstance(item, ReviewItem) else item)
    return validate_review_items(raw, source="<review-queue>")


def _bucket(review_id: str, bucket_count: int) -> int:
    return int.from_bytes(
        hashlib.sha256(review_id.encode("utf-8")).digest()[:2], "big"
    ) % bucket_count


def _shard_key(subject_id: str, bucket: int, chunk: int) -> str:
    safe_subject = re.sub(r"[^A-Za-z0-9_-]", "_", subject_id)
    return f"{safe_subject}--b{bucket:02d}--{chunk:04d}"


def partition_review_items(
    items: Iterable[ReviewItem | Mapping[str, Any]],
    *,
    shard_size: int = DEFAULT_SHARD_SIZE,
    bucket_count: int = DEFAULT_BUCKET_COUNT,
) -> dict[str, tuple[ReviewItem, ...]]:
    """Return deterministic shard contents independent of input order."""
    if shard_size < 1:
        raise ValueError("shard_size must be >= 1")
    if bucket_count < 1 or bucket_count > 256:
        raise ValueError("bucket_count must be between 1 and 256")
    validated = _normalise_items(items)
    groups: dict[tuple[str, int], list[ReviewItem]] = {}
    for item in validated:
        groups.setdefault((item.subject_id, _bucket(item.review_id, bucket_count)), []).append(item)

    result: dict[str, tuple[ReviewItem, ...]] = {}
    for (subject_id, bucket), group in sorted(groups.items()):
        group.sort(key=lambda item: item.review_id)
        for chunk_start in range(0, len(group), shard_size):
            chunk = tuple(group[chunk_start : chunk_start + shard_size])
            result[_shard_key(subject_id, bucket, chunk_start // shard_size)] = chunk
    return result


@dataclass(frozen=True)
class ShardDescriptor:
    path: str
    sha256: str
    item_count: int
    subject_id: str
    bucket: int
    min_review_id: str
    max_review_id: str

    def as_mapping(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "item_count": self.item_count,
            "subject_id": self.subject_id,
            "bucket": self.bucket,
            "review_id_range": {"min": self.min_review_id, "max": self.max_review_id},
        }


@dataclass(frozen=True)
class Manifest:
    schema_version: int
    manifest_version: int
    shard_size: int
    bucket_count: int
    shards: tuple[ShardDescriptor, ...]
    calculated_completion_ids: tuple[str, ...]
    manifest_sha256: str

    def payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "manifest_version": self.manifest_version,
            "shard_size": self.shard_size,
            "bucket_count": self.bucket_count,
            "shards": [descriptor.as_mapping() for descriptor in self.shards],
            "calculated_completion_ids": list(self.calculated_completion_ids),
        }

    def as_mapping(self) -> dict[str, Any]:
        result = self.payload()
        result["manifest_sha256"] = self.manifest_sha256
        return result


@dataclass(frozen=True)
class WriteReport:
    manifest: Manifest
    changed_shards: tuple[str, ...]
    bytes_written: int
    previous_hashes: dict[str, str]
    new_hashes: dict[str, str | None]

    @property
    def affected_shard_hashes(self) -> dict[str, tuple[str | None, str | None]]:
        names = set(self.previous_hashes) | set(self.new_hashes)
        return {
            name: (self.previous_hashes.get(name), self.new_hashes.get(name))
            for name in sorted(names)
        }


@dataclass(frozen=True)
class _CommitPlan:
    manifest: Manifest
    manifest_data: bytes
    pending: tuple[tuple[Path, Path, bytes], ...]
    descriptors: tuple[ShardDescriptor, ...]
    changed: tuple[str, ...]
    previous_for_report: dict[str, str]
    new_for_report: dict[str, str | None]


@dataclass(frozen=True)
class StorageDiagnostic:
    path: str
    ok: bool
    error: str | None = None
    error_path: str | None = None

    def as_mapping(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "ok": self.ok,
            "error": self.error,
            "error_path": self.error_path,
        }


@dataclass(frozen=True)
class ReviewQueueStateSources:
    """Validated queue sources retained for M13 reads and sol 289 M1 writes."""

    items: tuple[ReviewItem, ...]
    sources: Mapping[str, str]
    schema_version: int | None = None
    calculated_completion_ids: frozenset[str] = frozenset()
    _manifest: Manifest | None = field(default=None, repr=False, compare=False)
    _groups: Mapping[str, tuple[ReviewItem, ...]] = field(
        default_factory=lambda: MappingProxyType({}), repr=False, compare=False,
    )


def _descriptor_from_mapping(raw: Any, index: int, manifest_path: Path) -> ShardDescriptor:
    path = f"{manifest_path.as_posix()}.shards[{index}]"
    node = _mapping(raw, path)
    _unknown(
        node,
        {"path", "sha256", "item_count", "subject_id", "bucket", "review_id_range"},
        path,
    )
    rel = _string(node.get("path"), f"{path}.path")
    if Path(rel).is_absolute() or ".." in Path(rel).parts:
        raise StorageError("shard path must stay below the manifest directory", f"{path}.path")
    sha = _string(node.get("sha256"), f"{path}.sha256")
    if len(sha) != 64 or any(char not in "0123456789abcdef" for char in sha.lower()):
        raise StorageError("expected a SHA-256 hex digest", f"{path}.sha256")
    count = _integer(node.get("item_count"), f"{path}.item_count", minimum=1)
    subject = _string(node.get("subject_id"), f"{path}.subject_id")
    bucket = _integer(node.get("bucket"), f"{path}.bucket", minimum=0)
    range_node = _mapping(node.get("review_id_range"), f"{path}.review_id_range")
    _unknown(range_node, {"min", "max"}, f"{path}.review_id_range")
    return ShardDescriptor(
        path=rel,
        sha256=sha,
        item_count=count,
        subject_id=subject,
        bucket=bucket,
        min_review_id=_string(range_node.get("min"), f"{path}.review_id_range.min"),
        max_review_id=_string(range_node.get("max"), f"{path}.review_id_range.max"),
    )


def _manifest_from_path(path: Path) -> Manifest:
    raw = _mapping(_read_yaml(path), path.as_posix())
    return _manifest_from_mapping(raw, path)


def _manifest_from_bytes(data: bytes, path: Path) -> Manifest:
    if yaml is None:  # pragma: no cover
        raise StorageError("PyYAML is required for review shard storage", path.as_posix())
    try:
        raw = yaml.safe_load(data.decode("utf-8"))
    except (UnicodeError, yaml.YAMLError) as exc:
        raise StorageError(f"invalid YAML: {exc}", path.as_posix()) from exc
    return _manifest_from_mapping(_mapping(raw, path.as_posix()), path)


def _manifest_from_mapping(raw: Mapping[str, Any], path: Path) -> Manifest:
    base = path.as_posix()
    _unknown(
        raw,
        {"schema_version", "manifest_version", "shard_size", "bucket_count", "shards",
         "calculated_completion_ids", "manifest_sha256"},
        base,
    )
    schema = _integer(raw.get("schema_version"), f"{base}.schema_version", minimum=1)
    if schema not in {1, MANIFEST_SCHEMA_VERSION}:
        raise StorageError(f"unsupported schema_version {schema}", f"{base}.schema_version")
    version = _integer(raw.get("manifest_version"), f"{base}.manifest_version", minimum=1)
    shard_size = _integer(raw.get("shard_size"), f"{base}.shard_size", minimum=1)
    bucket_count = _integer(raw.get("bucket_count"), f"{base}.bucket_count", minimum=1)
    raw_shards = raw.get("shards")
    if not isinstance(raw_shards, Sequence) or isinstance(raw_shards, (str, bytes)):
        raise StorageError("expected a list of shards", f"{base}.shards")
    descriptors = tuple(
        _descriptor_from_mapping(item, i, path) for i, item in enumerate(raw_shards)
    )
    if list(descriptor.path for descriptor in descriptors) != sorted(
        descriptor.path for descriptor in descriptors
    ):
        raise StorageError("shards must be sorted by path", f"{base}.shards")
    manifest_sha = _string(raw.get("manifest_sha256"), f"{base}.manifest_sha256")
    raw_completion_ids = raw.get("calculated_completion_ids", [])
    if not isinstance(raw_completion_ids, Sequence) or isinstance(raw_completion_ids, (str, bytes)):
        raise StorageError("expected a list of completion IDs",
                           f"{base}.calculated_completion_ids")
    completion_ids = tuple(_string(value, f"{base}.calculated_completion_ids[{index}]")
                           for index, value in enumerate(raw_completion_ids))
    if len(set(completion_ids)) != len(completion_ids):
        raise StorageError("completion IDs must be unique", f"{base}.calculated_completion_ids")
    payload = {
        "schema_version": schema,
        "manifest_version": version,
        "shard_size": shard_size,
        "bucket_count": bucket_count,
        "shards": [descriptor.as_mapping() for descriptor in descriptors],
    }
    if schema >= 2:
        payload["calculated_completion_ids"] = list(completion_ids)
    expected = _sha256(_canonical_manifest_payload(payload))
    if manifest_sha != expected:
        raise StorageError(
            "manifest SHA-256 does not match its contents", f"{base}.manifest_sha256"
        )
    return Manifest(schema, version, shard_size, bucket_count, descriptors, completion_ids,
                    manifest_sha)


def _shard_bytes(items: Sequence[ReviewItem]) -> bytes:
    return _yaml_bytes(
        {
            "schema_version": SHARD_SCHEMA_VERSION,
            "items": [_item_mapping(item) for item in items],
        }
    )


def _load_shard(
    path: Path, descriptor: ShardDescriptor, *, bucket_count: int | None = None
) -> tuple[ReviewItem, ...]:
    actual_path = path.as_posix()
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise StorageError(str(exc), actual_path) from exc
    raw = _mapping(_read_yaml(path), actual_path)
    return _validate_shard_mapping(raw, data, path, descriptor, bucket_count=bucket_count)


def _load_shard_bytes(
    data: bytes,
    path: Path,
    descriptor: ShardDescriptor,
    *,
    bucket_count: int | None = None,
) -> tuple[ReviewItem, ...]:
    actual_path = path.as_posix()
    if yaml is None:  # pragma: no cover
        raise StorageError("PyYAML is required for review shard storage", actual_path)
    try:
        raw_value = yaml.safe_load(data.decode("utf-8"))
    except (UnicodeError, yaml.YAMLError) as exc:
        raise StorageError(f"invalid YAML: {exc}", actual_path) from exc
    raw = _mapping(raw_value, actual_path)
    return _validate_shard_mapping(raw, data, path, descriptor, bucket_count=bucket_count)


def _validate_shard_mapping(
    raw: Mapping[str, Any],
    data: bytes,
    path: Path,
    descriptor: ShardDescriptor,
    *,
    bucket_count: int | None = None,
) -> tuple[ReviewItem, ...]:
    actual_path = path.as_posix()
    _unknown(raw, {"schema_version", "items"}, actual_path)
    schema = _integer(raw.get("schema_version"), f"{actual_path}.schema_version", minimum=1)
    if schema != SHARD_SCHEMA_VERSION:
        raise StorageError(f"unsupported schema_version {schema}", f"{actual_path}.schema_version")
    raw_items = raw.get("items")
    if not isinstance(raw_items, Sequence) or isinstance(raw_items, (str, bytes)):
        raise StorageError("expected a list of review items", f"{actual_path}.items")
    parsed: list[ReviewItem] = []
    for index, item in enumerate(raw_items):
        try:
            parsed.append(validate_review_item(item, index=index, source=actual_path))
        except ContractError as exc:
            detail = exc.path or f"items[{index}]"
            raise StorageError(str(exc), f"{actual_path}.{detail}") from exc
    if len(parsed) != descriptor.item_count:
        raise StorageError(
            f"item count mismatch (manifest {descriptor.item_count}, actual {len(parsed)})",
            f"{actual_path}.items",
        )
    if not parsed:
        raise StorageError("shard must not be empty", f"{actual_path}.items")
    for index, item in enumerate(parsed):
        if item.subject_id != descriptor.subject_id:
            raise StorageError(
                f"subject_id {item.subject_id!r} does not match descriptor "
                f"{descriptor.subject_id!r}",
                f"{actual_path}.items[{index}].subject_id",
            )
        if bucket_count is not None and _bucket(item.review_id, bucket_count) != descriptor.bucket:
            raise StorageError(
                f"review_id hashes to bucket {_bucket(item.review_id, bucket_count)}, "
                f"not descriptor bucket {descriptor.bucket}",
                f"{actual_path}.items[{index}].review_id",
            )
    ids = [item.review_id for item in parsed]
    if ids != sorted(ids):
        raise StorageError("items must be sorted by review_id", f"{actual_path}.items")
    if ids[0] != descriptor.min_review_id:
        raise StorageError(
            "minimum review_id does not match descriptor",
            f"{actual_path}.review_id_range.min",
        )
    if ids[-1] != descriptor.max_review_id:
        raise StorageError(
            "maximum review_id does not match descriptor",
            f"{actual_path}.review_id_range.max",
        )
    actual_hash = _sha256(data)
    if actual_hash != descriptor.sha256:
        raise StorageError(
            f"SHA-256 mismatch (manifest {descriptor.sha256}, actual {actual_hash})",
            f"{actual_path}.sha256",
        )
    return tuple(parsed)


class ReviewShardStore:
    """Read and atomically update a sharded review queue directory."""

    def __init__(
        self,
        root: str | Path,
        *,
        shard_size: int = DEFAULT_SHARD_SIZE,
        bucket_count: int = DEFAULT_BUCKET_COUNT,
    ):
        self.root = Path(root)
        self.manifest_path = self.root / MANIFEST_NAME
        self.shard_size = shard_size
        self.bucket_count = bucket_count

    def _manifest(self) -> Manifest:
        return _manifest_from_path(self.manifest_path)

    def load(self) -> tuple[ReviewItem, ...]:
        manifest = self._manifest()
        return self._load_items(
            manifest,
            lambda path, descriptor: _load_shard(
                path, descriptor, bucket_count=manifest.bucket_count
            ),
        )

    def _load_items(
        self,
        manifest: Manifest,
        load_shard: Callable[[Path, ShardDescriptor], tuple[ReviewItem, ...]],
    ) -> tuple[ReviewItem, ...]:
        """Load and order shard items while enforcing queue-wide unique IDs."""
        all_items: list[ReviewItem] = []
        seen: dict[str, str] = {}
        for descriptor in manifest.shards:
            shard_path = self.root / descriptor.path
            items = load_shard(shard_path, descriptor)
            for index, item in enumerate(items):
                if item.review_id in seen:
                    raise StorageError(
                        f"duplicate review_id {item.review_id!r}; first seen in "
                        f"{seen[item.review_id]}",
                        f"{shard_path.as_posix()}.items[{index}].review_id",
                    )
                seen[item.review_id] = shard_path.as_posix()
                all_items.append(item)
        return tuple(sorted(all_items, key=lambda item: item.review_id))

    def read_state_sources(self) -> ReviewQueueStateSources:
        """Read the current queue once, returning each parsed file's relative hash."""
        if self.root.exists() and not self.root.is_dir():
            # An existing non-directory is an invalid registered path, not an empty store
            # (sol round 136, M2).
            raise StorageError("store root is not a directory", self.root.as_posix())
        if not self.manifest_path.exists():
            return ReviewQueueStateSources((), MappingProxyType({}))
        try:
            manifest_bytes = self.manifest_path.read_bytes()
        except OSError as exc:
            raise StorageError(str(exc), self.manifest_path.as_posix()) from exc
        manifest = _manifest_from_bytes(manifest_bytes, self.manifest_path)
        all_items: list[ReviewItem] = []
        seen: dict[str, str] = {}
        groups: dict[str, tuple[ReviewItem, ...]] = {}
        sources: dict[str, str] = {
            self.manifest_path.relative_to(self.root).as_posix(): _sha256(manifest_bytes)
        }

        def load_source_shard(
            shard_path: Path, descriptor: ShardDescriptor
        ) -> tuple[ReviewItem, ...]:
            try:
                shard_bytes = shard_path.read_bytes()
            except OSError as exc:
                raise StorageError(str(exc), shard_path.as_posix()) from exc
            items = _load_shard_bytes(
                shard_bytes, shard_path, descriptor, bucket_count=manifest.bucket_count
            )
            sources[descriptor.path] = _sha256(shard_bytes)
            groups[descriptor.path] = items
            return items

        return ReviewQueueStateSources(
            self._load_items(manifest, load_source_shard), MappingProxyType(sources),
            manifest.schema_version, frozenset(manifest.calculated_completion_ids),
            manifest, MappingProxyType(groups),
        )

    def calculated_completion_ids(self) -> frozenset[str]:
        """Return completion IDs committed atomically with the current queue."""
        if not self.manifest_path.exists():
            return frozenset()
        return frozenset(self._manifest().calculated_completion_ids)

    def manifest_schema_version(self) -> int:
        """Return the validated schema version for the current queue manifest."""
        return self._manifest().schema_version

    def has_unproven_legacy_history(self) -> bool:
        """True when a schema-1 queue already holds a reviewed item.

        Schema 1 kept no calculated completion IDs, so once any item has been reviewed a replay
        cannot be told from a new record (D8′). Such a queue accepts no write until
        ``upgrade_legacy_queue`` acknowledges the unknown history (sol round 60, C2).
        """
        if not self.manifest_path.exists() or self.manifest_schema_version() != 1:
            return False
        return any(item.last_reviewed_on is not None for item in self.load())

    def write(
        self,
        items: Iterable[ReviewItem | Mapping[str, Any]],
        *,
        calculated_completion_ids: Iterable[str] | None = None,
        source_state: ReviewQueueStateSources | None = None,
    ) -> WriteReport:
        if source_state is None and self.has_unproven_legacy_history():
            raise StorageError(
                "schema-1 queue has reviewed items; call upgrade_legacy_queue first",
                "calculated_completion_ids",
            )
        if source_state is not None and (
            source_state.schema_version == 1
            and any(item.last_reviewed_on is not None for item in source_state.items)
        ):
            raise StorageError(
                "schema-1 queue has reviewed items; call upgrade_legacy_queue first",
                "calculated_completion_ids",
            )
        return self._commit(items, calculated_completion_ids, source_state=source_state)

    def _commit(
        self,
        items: Iterable[ReviewItem | Mapping[str, Any]],
        calculated_completion_ids: Iterable[str] | None,
        *,
        source_state: ReviewQueueStateSources | None = None,
    ) -> WriteReport:
        validated = _normalise_items(items)
        new_groups = partition_review_items(
            validated, shard_size=self.shard_size, bucket_count=self.bucket_count,
        )
        old_manifest, old_groups = self._read_previous_groups(source_state)

        if calculated_completion_ids is None:
            if source_state is not None:
                completion_ids = source_state.calculated_completion_ids
            else:
                completion_ids = old_manifest.calculated_completion_ids if old_manifest else ()
        else:
            completion_ids = tuple(sorted(set(calculated_completion_ids)))
        for index, completion_id in enumerate(completion_ids):
            _string(completion_id, f"calculated_completion_ids[{index}]")

        version = (old_manifest.manifest_version + 1) if old_manifest else 1
        plan = self._prepare_commit_plan(
            new_groups, old_groups, completion_ids, version,
        )
        return self._publish_commit(plan)

    def _read_previous_groups(
        self,
        source_state: ReviewQueueStateSources | None = None,
    ) -> tuple[Manifest | None, dict[str, tuple[ReviewItem, ...]]]:
        if source_state is not None:
            # sol 289 M1: compare against the exact parsed files already loaded by M33.
            return source_state._manifest, dict(source_state._groups)
        old_manifest: Manifest | None = None
        old_groups: dict[str, tuple[ReviewItem, ...]] = {}
        old_hashes: dict[str, str] = {}
        if self.manifest_path.exists():
            old_manifest = self._manifest()
            old_hashes = {descriptor.path: descriptor.sha256 for descriptor in old_manifest.shards}
            for descriptor in old_manifest.shards:
                old_groups[descriptor.path] = _load_shard(
                    self.root / descriptor.path, descriptor, bucket_count=old_manifest.bucket_count
                )
        return old_manifest, old_groups

    def _prepare_commit_plan(
        self,
        new_groups: Mapping[str, tuple[ReviewItem, ...]],
        old_groups: Mapping[str, tuple[ReviewItem, ...]],
        completion_ids: tuple[str, ...],
        version: int,
    ) -> _CommitPlan:
        previous_by_key = {
            Path(path).name.rsplit("--v", 1)[0]: (path, group)
            for path, group in old_groups.items()
        }
        descriptors: list[ShardDescriptor] = []
        pending: list[tuple[Path, Path, bytes]] = []
        changed: list[str] = []
        previous_for_report: dict[str, str] = {}
        new_for_report: dict[str, str] = {}

        for key, group in sorted(new_groups.items()):
            data = _shard_bytes(group)
            digest = _sha256(data)
            previous = previous_by_key.get(key)
            if previous is not None and previous[1] == group:
                rel_path = previous[0]
            else:
                rel_path = f"shards/{key}--v{version}.yaml"
                pending.append((self.root / rel_path, self.root / rel_path, data))
                changed.append(key)
                if previous is not None:
                    previous_for_report[key] = _sha256(_shard_bytes(previous[1]))
                new_for_report[key] = digest
            bucket = _bucket(group[0].review_id, self.bucket_count)
            descriptors.append(ShardDescriptor(
                rel_path, digest, len(group), group[0].subject_id, bucket,
                group[0].review_id, group[-1].review_id,
            ))

        self._record_removed_shards(
            previous_by_key, set(new_groups), changed, previous_for_report, new_for_report,
        )

        descriptors.sort(key=lambda descriptor: descriptor.path)
        manifest, manifest_data = self._build_commit_manifest(
            descriptors, completion_ids, version,
        )
        return _CommitPlan(
            manifest=manifest,
            manifest_data=manifest_data,
            pending=tuple(pending),
            descriptors=tuple(descriptors),
            changed=tuple(changed),
            previous_for_report=previous_for_report,
            new_for_report=new_for_report,
        )

    def _build_commit_manifest(
        self,
        descriptors: Sequence[ShardDescriptor],
        completion_ids: tuple[str, ...],
        version: int,
    ) -> tuple[Manifest, bytes]:
        payload = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "manifest_version": version,
            "shard_size": self.shard_size,
            "bucket_count": self.bucket_count,
            "shards": [descriptor.as_mapping() for descriptor in descriptors],
            "calculated_completion_ids": list(completion_ids),
        }
        manifest_hash = _sha256(_canonical_manifest_payload(payload))
        manifest = Manifest(
            MANIFEST_SCHEMA_VERSION, version, self.shard_size, self.bucket_count,
            tuple(descriptors), tuple(completion_ids), manifest_hash
        )
        manifest_data = _yaml_bytes(manifest.as_mapping())
        return manifest, manifest_data

    @staticmethod
    def _record_removed_shards(
        previous_by_key: Mapping[str, tuple[str, tuple[ReviewItem, ...]]],
        new_keys: set[str],
        changed: list[str],
        previous_for_report: dict[str, str],
        new_for_report: dict[str, str | None],
    ) -> None:
        for key, (old_path, old_group) in previous_by_key.items():
            if key not in new_keys:
                changed.append(key)
                previous_for_report[key] = _sha256(_shard_bytes(old_group))
                new_for_report[key] = None

    def _publish_commit(self, plan: _CommitPlan) -> WriteReport:
        self.root.mkdir(parents=True, exist_ok=True)
        temp_paths: list[Path] = []
        final_paths: list[Path] = []
        committed = False
        bytes_written = 0
        try:
            prepared: list[tuple[Path, Path]] = []
            for final_path, _, data in plan.pending:
                final_path.parent.mkdir(parents=True, exist_ok=True)
                temp_path = final_path.with_name(f".{final_path.name}.{uuid.uuid4().hex}.tmp")
                temp_paths.append(temp_path)
                final_paths.append(final_path)
                prepared.append((temp_path, final_path))
                temp_path.write_bytes(data)
                # Validate the complete temporary shard before it becomes visible.
                expected_descriptor = next(
                    descriptor for descriptor in plan.descriptors
                    if descriptor.path == final_path.relative_to(self.root).as_posix()
                )
                _load_shard(temp_path, expected_descriptor)
                bytes_written += len(data)
            manifest_tmp = self.manifest_path.with_name(f".{MANIFEST_NAME}.{uuid.uuid4().hex}.tmp")
            temp_paths.append(manifest_tmp)
            manifest_tmp.write_bytes(plan.manifest_data)
            _manifest_from_path(manifest_tmp)
            # Old files are never overwritten.  A manifest replacement is the commit.
            for temp_path, final_path in prepared:
                os.replace(temp_path, final_path)
                temp_paths.remove(temp_path)
            os.replace(manifest_tmp, self.manifest_path)
            temp_paths.remove(manifest_tmp)
            committed = True
        finally:
            for temp_path in temp_paths:
                try:
                    temp_path.unlink()
                except FileNotFoundError:
                    pass
            if not committed:
                for final_path in final_paths:
                    try:
                        final_path.unlink()
                    except FileNotFoundError:
                        pass
        return WriteReport(
            plan.manifest,
            plan.changed,
            bytes_written + len(plan.manifest_data),
            plan.previous_for_report,
            plan.new_for_report,
        )

    def upsert(self, item: ReviewItem | Mapping[str, Any]) -> WriteReport:
        candidate = _normalise_items([item])[0]
        current = list(self.load()) if self.manifest_path.exists() else []
        replaced = False
        for index, existing in enumerate(current):
            if existing.review_id == candidate.review_id:
                current[index] = candidate
                replaced = True
                break
        if not replaced:
            current.append(candidate)
        return self.write(current)

    def delete(self, review_id: str) -> WriteReport:
        current = list(self.load())
        remaining = [item for item in current if item.review_id != review_id]
        if len(remaining) == len(current):
            raise StorageError(f"review_id {review_id!r} not found", "review_id")
        return self.write(remaining)

    update = upsert


def write_review_queue(
    root: str | Path,
    items: Iterable[ReviewItem | Mapping[str, Any]],
    **kwargs: Any,
) -> WriteReport:
    return ReviewShardStore(root, **kwargs).write(items)


def upgrade_legacy_queue(
    store: ReviewShardStore,
    *,
    acknowledge_unknown_history: bool,
) -> WriteReport:
    """Upgrade schema 1 with an explicit reset of unknown replay history.

    Acknowledgement means prior calculations cannot be reconstructed, so schema 2
    starts with an empty calculated-ID set.
    """
    if acknowledge_unknown_history is not True:
        raise StorageError("explicit acknowledgement is required", "acknowledge_unknown_history")
    if not store.manifest_path.exists():
        raise StorageError("legacy queue manifest does not exist", store.manifest_path.as_posix())
    if store.manifest_schema_version() != 1:
        raise StorageError("queue manifest is not schema 1", "schema_version")
    return store._commit(store.load(), ())


def load_sharded_reviews(path: str | Path) -> tuple[ReviewItem, ...]:
    candidate = Path(path)
    root = candidate.parent if candidate.is_file() else candidate
    return ReviewShardStore(root).load()


def load_review_queue(path: str | Path) -> tuple[ReviewItem, ...]:
    candidate = Path(path)
    if candidate.is_dir() or candidate.name == MANIFEST_NAME:
        return load_sharded_reviews(candidate)
    return load_review_items(candidate)


def diagnose_shards(path: str | Path) -> tuple[StorageDiagnostic, ...]:
    """Read-only diagnostics: report every manifest-declared shard."""
    candidate = Path(path)
    root = candidate.parent if candidate.is_file() else candidate
    manifest_path = candidate if candidate.is_file() else root / MANIFEST_NAME
    try:
        manifest = _manifest_from_path(manifest_path)
    except ContractError as exc:
        return (StorageDiagnostic(manifest_path.as_posix(), False, str(exc), exc.path),)
    diagnostics: list[StorageDiagnostic] = []
    seen: set[str] = set()
    for descriptor in manifest.shards:
        shard_path = root / descriptor.path
        try:
            items = _load_shard(shard_path, descriptor, bucket_count=manifest.bucket_count)
            for index, item in enumerate(items):
                if item.review_id in seen:
                    raise StorageError(
                        f"duplicate review_id {item.review_id!r} across shards",
                        f"{shard_path.as_posix()}.items[{index}].review_id",
                    )
                seen.add(item.review_id)
            diagnostics.append(StorageDiagnostic(shard_path.as_posix(), True))
        except ContractError as exc:
            diagnostics.append(StorageDiagnostic(shard_path.as_posix(), False, str(exc), exc.path))
    return tuple(diagnostics)


def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only review shard diagnostics")
    subparsers = parser.add_subparsers(dest="command", required=True)
    diagnose_parser = subparsers.add_parser("diagnose")
    diagnose_parser.add_argument("path")
    args = parser.parse_args(argv)
    if args.command == "diagnose":
        diagnostics = diagnose_shards(args.path)
        for diagnostic in diagnostics:
            if diagnostic.ok:
                print(f"OK {diagnostic.path}")
            else:
                print(f"ERROR {diagnostic.path}: {diagnostic.error}")
        return 0
    return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(_main())
