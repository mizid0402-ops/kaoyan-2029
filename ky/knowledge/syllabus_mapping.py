"""M4 syllabus-version mapping port (``contracts/syllabus_mapping.md``).

Public interfaces are :func:`load_syllabus_mapping`, :class:`SyllabusMapping`,
and :meth:`SyllabusMapping.targets`. Trees are read through the knowledge-tree port.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from ky.knowledge.knowledge_point import load_knowledge_points
from ky.models import ContractError, load_yaml_text
from ky.workspace import Workspace

_ROOT_KEYS = frozenset(
    {"schema_version", "kind", "subject_id", "from_version", "to_version", "basis",
     "changes", "added"}
)
_CHANGE_KEYS = frozenset({"from", "to"})
_VERSION_RE = re.compile(r"^[0-9]{4}$")


@dataclass(frozen=True)
class SyllabusMapping:
    subject_id: str
    from_version: str
    to_version: str
    changes: Mapping[str, tuple[str, ...]]
    old_ids: frozenset[str]

    def targets(self, old_id: str) -> tuple[str, ...]:
        """Return declared targets, preserving unchanged source IDs."""
        if old_id not in self.old_ids:
            raise ContractError("old ID is not in source tree", "old_id")
        return self.changes.get(old_id, (old_id,))


@dataclass(frozen=True)
class _MappingHeader:
    subject_id: str
    from_version: str
    to_version: str


@dataclass(frozen=True)
class _MappingDocument:
    header: _MappingHeader
    changes: object
    added: object


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ContractError("expected a mapping", field)
    return value


def _string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError("expected a non-empty string", field)
    return value


def _id_list(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ContractError("expected a list", field)
    result: list[str] = []
    for index, item in enumerate(value):
        result.append(_string(item, f"{field}[{index}]"))
    return tuple(result)


def _tree_ids(path: Path, field: str) -> frozenset[str]:
    try:
        return frozenset(point.knowledge_point_id for point in load_knowledge_points(path))
    except (OSError, ValueError) as exc:
        raise ContractError(f"invalid registered knowledge tree: {exc}", field) from exc


def _read_mapping_document(path: str | Path) -> _MappingDocument:
    source = Path(path)
    try:
        raw = load_yaml_text(source.read_text(encoding="utf-8"), source=source.as_posix())
    except (OSError, UnicodeError, ContractError) as exc:
        if isinstance(exc, ContractError):
            raise
        raise ContractError(f"cannot read mapping: {exc}", "") from exc
    document = _mapping(raw, "")
    unknown = set(document) - _ROOT_KEYS
    if unknown:
        key = sorted(unknown, key=str)[0]
        raise ContractError(f"unknown field {key!r}", str(key))
    version = document.get("schema_version")
    if isinstance(version, bool) or version != 1:
        raise ContractError("expected schema_version 1", "schema_version")
    if document.get("kind") != "syllabus_mapping":
        raise ContractError("expected syllabus_mapping", "kind")
    header = _parse_mapping_header(document)
    return _MappingDocument(header, document.get("changes"), document.get("added"))


def _parse_mapping_header(document: Mapping[str, object]) -> _MappingHeader:
    subject = _string(document.get("subject_id"), "subject_id")
    from_version = _string(document.get("from_version"), "from_version")
    to_version = _string(document.get("to_version"), "to_version")
    for label, field in ((from_version, "from_version"), (to_version, "to_version")):
        if not _VERSION_RE.fullmatch(label):
            raise ContractError("expected a four-digit string", field)
    if from_version == to_version:
        raise ContractError("from_version must differ from to_version", "to_version")
    _string(document.get("basis"), "basis")
    return _MappingHeader(subject, from_version, to_version)


def _check_registered_subject(header: _MappingHeader, subject_id: str) -> None:
    if header.subject_id != subject_id:
        raise ContractError(
            f"mapping subject {header.subject_id!r} does not match registered subject "
            f"{subject_id!r}",
            "subject_id",
        )


def _load_version_tree_ids(
    header: _MappingHeader, workspace: Workspace
) -> tuple[frozenset[str], frozenset[str]]:
    registered = workspace.syllabus_versions.get(header.subject_id)
    if registered is None:
        raise ContractError(
            "subject has no registered syllabus versions", "subject_id"
        )
    versions = registered.versions
    if header.from_version not in versions:
        raise ContractError("version is not registered", "from_version")
    if header.to_version not in versions:
        raise ContractError("version is not registered", "to_version")
    from_key = (
        f"reference.syllabus_versions.{header.subject_id}.versions."
        f"{header.from_version}"
    )
    to_key = (
        f"reference.syllabus_versions.{header.subject_id}.versions."
        f"{header.to_version}"
    )
    old_ids = _tree_ids(
        workspace.require(from_key), f"from_version.{header.from_version}"
    )
    new_ids = _tree_ids(
        workspace.require(to_key), f"to_version.{header.to_version}"
    )
    return old_ids, new_ids


def _require_registered_mapping(
    path: str | Path, workspace: Workspace, subject_id: str
) -> Path:
    """Return the registered path that ``path`` names.

    The caller reads the returned registered path, not its own alias, so the file checked here
    is the file read (sol round 71: an alias could be re-pointed between check and read).
    """
    key = f"reference.syllabus_versions.{subject_id}.mappings"
    registered_paths = workspace.require_all(key)
    try:
        requested_path = Path(path).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ContractError(f"cannot resolve mapping path: {exc}", "path") from exc
    for registered in registered_paths:
        if registered.resolve(strict=True) == requested_path:
            return registered
    raise ContractError("mapping file is not registered", "path")


def _parse_changes(
    raw_changes: object, old_ids: frozenset[str], new_ids: frozenset[str]
) -> tuple[dict[str, tuple[str, ...]], set[str]]:
    if not isinstance(raw_changes, list):
        raise ContractError("expected a list", "changes")
    changes: dict[str, tuple[str, ...]] = {}
    declared_targets: set[str] = set()
    for index, raw_change in enumerate(raw_changes):
        field = f"changes[{index}]"
        change = _mapping(raw_change, field)
        unknown_change = set(change) - _CHANGE_KEYS
        if unknown_change:
            key = sorted(unknown_change, key=str)[0]
            raise ContractError(f"unknown field {key!r}", f"{field}.{key}")
        old_id = _string(change.get("from"), f"{field}.from")
        targets = _id_list(change.get("to"), f"{field}.to")
        if old_id in changes:
            raise ContractError("from ID appears more than once", f"{field}.from")
        if old_id not in old_ids:
            raise ContractError("from ID is not in old tree", f"{field}.from")
        seen_targets: set[str] = set()
        for target_index, target in enumerate(targets):
            if target in seen_targets:
                raise ContractError("duplicate target ID", f"{field}.to[{target_index}]")
            if target not in new_ids:
                raise ContractError("to ID is not in new tree", f"{field}.to[{target_index}]")
            seen_targets.add(target)
            declared_targets.add(target)
        changes[old_id] = targets
    return changes, declared_targets


def _parse_added(
    raw_added: object,
    old_ids: frozenset[str],
    new_ids: frozenset[str],
    declared_targets: set[str],
) -> set[str]:
    added = _id_list(raw_added, "added")
    if len(set(added)) != len(added):
        raise ContractError("added ID appears more than once", "added")
    added_set = set(added)
    for index, point_id in enumerate(added):
        field = f"added[{index}]"
        if point_id not in new_ids:
            raise ContractError("added ID is not in new tree", field)
        if point_id in old_ids:
            raise ContractError("added ID already exists in old tree", field)
        if point_id in declared_targets:
            raise ContractError("added ID also appears in changes.to", field)
    return added_set


def _validate_tree_coverage(
    old_ids: frozenset[str],
    new_ids: frozenset[str],
    changes: Mapping[str, tuple[str, ...]],
    declared_targets: set[str],
    added: set[str],
) -> None:
    for old_id in old_ids - new_ids:
        if old_id not in changes:
            raise ContractError(f"undeclared deletion or rename: {old_id}", "changes")
    for new_id in new_ids:
        implicit_self = new_id in old_ids and new_id not in changes
        explicit_target = new_id in declared_targets
        coverage_count = sum((explicit_target, implicit_self, new_id in added))
        if coverage_count == 0:
            raise ContractError(f"new ID has no source and is not added: {new_id}", "added")
        if coverage_count > 1:
            raise ContractError(f"new ID has multiple sources: {new_id}", "changes")


def load_syllabus_mapping(
    path: str | Path, workspace: Workspace, *, subject_id: str
) -> SyllabusMapping:
    """Load a mapping for its registered subject and validate both version trees."""
    registered_path = _require_registered_mapping(path, workspace, subject_id)
    document = _read_mapping_document(registered_path)
    _check_registered_subject(document.header, subject_id)
    old_ids, new_ids = _load_version_tree_ids(document.header, workspace)
    changes, declared_targets = _parse_changes(document.changes, old_ids, new_ids)
    added = _parse_added(document.added, old_ids, new_ids, declared_targets)
    _validate_tree_coverage(old_ids, new_ids, changes, declared_targets, added)
    return SyllabusMapping(
        document.header.subject_id,
        document.header.from_version,
        document.header.to_version,
        MappingProxyType(changes),
        old_ids,
    )
