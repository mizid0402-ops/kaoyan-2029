"""M29 staging files for ``contracts/timetable_import.md`` §3.

Public interfaces: :class:`StagedSemester`, :func:`parse_staging_bytes`,
:func:`read_staging`, :func:`staged_to_bytes`, :func:`staging_hash12`, and
:func:`publish_staging`.
"""

from __future__ import annotations

import hashlib
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

import yaml

from ky.models import ContractError
from ky.planner.port import canonical_json_bytes
from ky.timetable import Semester, semester_from_mapping, semester_to_mapping
from ky.timetable_io.isolation import Isolation, check_isolated_path
from ky.workspace import Workspace

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_ROOT_KEYS = frozenset({"schema_version", "kind", "source", "semester", "notes"})


# contracts/timetable_import.md section 3: one adapter per import route (4b-1 ics, 4b-2 zfsoft PDF).
ADAPTERS = frozenset({"ics", "zfsoft_pdf"})

@dataclass(frozen=True)
class StagedSemester:
    adapter: str
    source_sha256: str
    semester: Semester
    notes: tuple[str, ...]


def _walk_duplicates(node: yaml.Node, path: str) -> None:
    if isinstance(node, yaml.MappingNode):
        seen: set[str] = set()
        for key_node, value_node in node.value:
            key = key_node.value if isinstance(key_node, yaml.ScalarNode) else None
            field = f"{path}.{key}" if path else str(key)
            if key is not None and key in seen:
                raise ContractError("duplicate field", field)
            if key is not None:
                seen.add(key)
            _walk_duplicates(value_node, field)
    elif isinstance(node, yaml.SequenceNode):
        for index, item in enumerate(node.value):
            _walk_duplicates(item, f"{path}[{index}]")


def _parse_yaml(data: bytes, source: Path) -> object:
    try:
        text = data.decode("utf-8")
        node = yaml.compose(text, Loader=yaml.SafeLoader)
        if node is not None:
            _walk_duplicates(node, "")
        return yaml.load(text, Loader=yaml.SafeLoader)
    except UnicodeError as exc:
        raise ContractError(f"invalid UTF-8: {exc}", source.as_posix()) from exc
    except yaml.YAMLError as exc:
        raise ContractError(f"invalid YAML: {exc}", source.as_posix()) from exc


def _mapping(value: object, path: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ContractError("expected a mapping", path)
    if any(not isinstance(key, str) for key in value):
        raise ContractError("mapping keys must be strings", path)
    return value


def _closed_mapping(
    value: object, path: str, required: frozenset[str], allowed: frozenset[str]
) -> Mapping[str, object]:
    raw = _mapping(value, path)
    unknown = sorted(set(raw) - allowed)
    if unknown:
        field = f"{path}.{unknown[0]}" if path else unknown[0]
        raise ContractError("unknown field", field)
    missing = sorted(required - set(raw))
    if missing:
        field = f"{path}.{missing[0]}" if path else missing[0]
        raise ContractError("required field is missing", field)
    return raw


def _check_source(value: object) -> tuple[str, str]:
    source = _closed_mapping(value, "source", frozenset({"adapter", "sha256"}),
                             frozenset({"adapter", "sha256"}))
    adapter = source["adapter"]
    if not isinstance(adapter, str) or adapter not in ADAPTERS:
        raise ContractError("adapter must be ics or zfsoft_pdf", "source.adapter")
    digest = source["sha256"]
    if not isinstance(digest, str) or not _HASH_RE.fullmatch(digest):
        raise ContractError("expected lowercase SHA-256", "source.sha256")
    return adapter, digest


def _check_notes(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ContractError("notes must be a list", "notes")
    for index, note in enumerate(value):
        if not isinstance(note, str):
            raise ContractError("note must be a string", f"notes[{index}]")
    return tuple(value)


def parse_staging_bytes(data: bytes, source: Path) -> StagedSemester:
    raw = _closed_mapping(_parse_yaml(data, source), "", _ROOT_KEYS, _ROOT_KEYS)
    version = raw["schema_version"]
    if type(version) is not int or version != 1:
        raise ContractError("schema_version must be integer 1", "schema_version")
    if raw["kind"] != "timetable_import":
        raise ContractError("kind must be timetable_import", "kind")
    adapter, digest = _check_source(raw["source"])
    semester = semester_from_mapping(raw["semester"], "semester")
    notes = _check_notes(raw["notes"])
    return StagedSemester(adapter, digest, semester, notes)


def read_staging(path: str | Path) -> tuple[StagedSemester, bytes]:
    source = Path(path)
    try:
        data = source.read_bytes()
    except OSError as exc:
        raise ContractError(f"cannot read staging file: {exc}", source.as_posix()) from exc
    return parse_staging_bytes(data, source), data


def _hash_mapping(staged: StagedSemester) -> dict[str, object]:
    return {
        "schema_version": 1,
        "kind": "timetable_import",
        "source": {"adapter": staged.adapter, "sha256": staged.source_sha256},
        "semester": semester_to_mapping(staged.semester),
    }


def staging_hash12(staged: StagedSemester) -> str:
    return hashlib.sha256(canonical_json_bytes(_hash_mapping(staged))).hexdigest()[:12]


def staged_to_mapping(staged: StagedSemester) -> dict[str, object]:
    return {
        **_hash_mapping(staged),
        "notes": list(staged.notes),
    }


def staged_to_bytes(staged: StagedSemester) -> bytes:
    return yaml.safe_dump(
        staged_to_mapping(staged),
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    ).encode("utf-8")


def _stage_directory(workspace: Workspace, isolation: Isolation) -> Path:
    staging_root = workspace.write_target("staging")
    resolved_root = staging_root.resolve(strict=False)
    directory = staging_root / "timetables"
    # Git tracks files, not directories: only files written here face the isolation check.
    resolved_directory = directory.resolve(strict=False)
    try:
        resolved_directory.relative_to(resolved_root)
    except ValueError as exc:
        raise ContractError("staging directory escapes staging root", "staging") from exc
    return directory


def _publish_once(target: Path, data: bytes, isolation: Isolation) -> None:
    check_isolated_path(isolation, target)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    check_isolated_path(isolation, temporary)
    try:
        with temporary.open("xb") as stream:
            stream.write(data)
        read_back = temporary.read_bytes()
        parse_staging_bytes(read_back, temporary)
        if read_back != data:
            raise ContractError("temporary staging bytes changed", temporary.as_posix())
        check_isolated_path(isolation, temporary)
        try:
            os.link(temporary, target)
        except FileExistsError:
            raise
        except OSError as exc:
            raise ContractError(f"cannot publish staging file: {exc}", target.as_posix()) from exc
    finally:
        temporary.unlink(missing_ok=True)


def publish_staging(
    workspace: Workspace, staged: StagedSemester, isolation: Isolation
) -> tuple[Path, bool]:
    directory = _stage_directory(workspace, isolation)
    digest = staging_hash12(staged)
    target = directory / f"import--{digest}.yaml"
    data = staged_to_bytes(staged)
    try:
        target.resolve(strict=False).relative_to(directory.resolve(strict=False))
    except ValueError as exc:
        raise ContractError("staging file escapes timetables staging", "staging") from exc
    target = check_isolated_path(isolation, target)
    if target.exists():
        existing, existing_bytes = read_staging(target)
        if existing_bytes == data and existing == staged:
            return target, False
        raise ContractError(
            "staging target already exists with different content",
            target.as_posix(),
        )
    try:
        _publish_once(target, data, isolation)
    except FileExistsError as exc:
        existing, existing_bytes = read_staging(target)
        if existing_bytes == data and existing == staged:
            return target, False
        raise ContractError(
            "staging target already exists with different content", target.as_posix()
        ) from exc
    return target, True
