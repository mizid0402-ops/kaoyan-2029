"""M0 workspace registry loader (``contracts/workspace.md`` §2.6 and §4).

Public interfaces are :func:`load_workspace`, :func:`find_workspace`,
:class:`Workspace`, :class:`SubjectProfile`, :meth:`Workspace.require`, and
:meth:`Workspace.write_target`. Registered inputs are checked for existence
and containment lazily by :meth:`Workspace.require`; writers use
:meth:`Workspace.write_target` for registered write destinations.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Mapping

import yaml

from ky.models import (
    ContractError,
    _reject_unknown_keys,
    _require_mapping,
    _StrictSafeLoader,
)

WORKSPACE_FILENAME = "kaoyan.workspace.yaml"
WORKSPACE_ENV = "KY_WORKSPACE"

_ROOT_KEYS = frozenset(
    {
        "schema_version", "subjects", "reference", "supplementary", "materials",
        "products", "settings", "state", "staging", "projection",
    }
)
_REFERENCE_KEYS = frozenset(
    {"knowledge_trees", "syllabus_versions", "exam_indexes", "paper_shapes",
     "timetable_schools", "topic_weights", "weight_batches", "vocabulary_db", "ledger"}
)
_SUPPLEMENTARY_KEYS = frozenset({"kind", "subject", "description", "files"})
_MATERIALS_KEYS = frozenset({"raw_root"})
_SETTINGS_KEYS = frozenset({"exam_config", "pacing"})
_STATE_KEYS = frozenset(
    {"review_queue", "plans", "availability", "routes", "timetable", "question_bank"}
)
_VIEW_ROLES = {"cross_year_tree": frozenset({"tree", "agreement"})}
_TREE_GRAMMARS = frozenset({"numbered_chapters", "named_chapters", "flat"})
_SUBJECT_FEATURES = frozenset({"vocabulary", "weighted_mastery"})
_SYLLABUS_VERSION_RE = re.compile(r"^[0-9]{4}$")
_SUBJECT_RE = re.compile(r"^[a-z][a-z0-9]*$")
_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True)
class SupplementaryView:
    name: str
    kind: str
    subject: str
    description: str
    files: Mapping[str, Path]


@dataclass(frozen=True)
class SubjectProfile:
    name: str
    tree_grammar: str | None
    domain_segment: bool
    features: tuple[str, ...]


@dataclass(frozen=True)
class SyllabusVersions:
    versions: Mapping[str, Path]
    mappings: tuple[Path, ...]


@dataclass(frozen=True)
class Workspace:
    source: Path
    root: Path
    sha256: str
    subjects: tuple[str, ...]
    subject_profiles: Mapping[str, SubjectProfile]
    knowledge_trees: Mapping[str, Path]
    syllabus_versions: Mapping[str, SyllabusVersions]
    exam_indexes: Mapping[str, tuple[Path, ...]]
    paper_shapes: Mapping[str, Path]
    timetable_schools: Mapping[str, Path]
    topic_weights: Path
    weight_batches: Path | None
    vocabulary_db: Path
    ledger: Path
    supplementary: Mapping[str, SupplementaryView]
    raw_root: Path
    products: Mapping[str, Path]
    exam_config: Path | None
    pacing: Path | None
    review_queue: Path
    plans: Path
    availability: Path | None
    routes: Path | None
    timetable: Path | None
    question_bank: Path | None
    staging: Path
    projection: Path
    local_sha256: str | None

    def effective_version(self, subject: str) -> str | None:
        """Return the registered version matching the subject's effective tree."""
        registered = self.syllabus_versions.get(subject)
        effective = self.knowledge_trees.get(subject)
        if registered is None or effective is None:
            return None
        return next(
            (version for version, path in registered.versions.items() if path == effective),
            None,
        )

    def _single_paths(self) -> dict[str, Path]:
        result = {
            "reference.topic_weights": self.topic_weights,
            "reference.vocabulary_db": self.vocabulary_db,
            "reference.ledger": self.ledger,
            "materials.raw_root": self.raw_root,
        }
        if self.weight_batches is not None:
            result["reference.weight_batches"] = self.weight_batches
        if self.exam_config is not None:
            result["settings.exam_config"] = self.exam_config
        if self.pacing is not None:
            result["settings.pacing"] = self.pacing
        # state.*, staging and projection are write targets (spec section 4): their writers
        # create them, so they are deliberately not require()-able.
        result.update(
            {
                f"reference.knowledge_trees.{key}": value
                for key, value in self.knowledge_trees.items()
            }
        )
        result.update(
            {
                f"reference.syllabus_versions.{subject}.versions.{version}": path
                for subject, record in self.syllabus_versions.items()
                for version, path in record.versions.items()
            }
        )
        result.update(
            {
                f"reference.paper_shapes.{key}": value
                for key, value in self.paper_shapes.items()
            }
        )
        result.update(
            {
                f"reference.timetable_schools.{key}": value
                for key, value in self.timetable_schools.items()
            }
        )
        result.update({f"products.{key}": value for key, value in self.products.items()})
        result.update(
            {
                f"supplementary.{name}.files.{role}": value
                for name, view in self.supplementary.items()
                for role, value in view.files.items()
            }
        )
        return result

    def _check_required_path(self, key: str, path: Path, *, is_dir: bool) -> Path:
        expected = "directory" if is_dir else "file"
        if not path.exists():
            raise ContractError(f"registered {expected} does not exist: {path}", key)
        if is_dir and not path.is_dir():
            raise ContractError("expected a directory", key)
        if not is_dir and not path.is_file():
            raise ContractError("expected a file", key)
        try:
            real_path = path.resolve(strict=True)
            real_root = self.root.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise ContractError(f"cannot resolve registered path: {exc}", key) from exc
        try:
            real_path.relative_to(real_root)
        except ValueError as exc:
            raise ContractError("resolves outside the workspace", key) from exc
        return path

    def require(self, key: str) -> Path:
        """Return one registered path after checking type and workspace bounds."""
        path = self._single_paths().get(key)
        if path is None:
            if self._registered_path_list(key) is not None:
                raise ContractError("field is a path list; use require_all", key)
            raise ContractError("not registered", key)
        is_dir = key == "materials.raw_root"
        is_dir = is_dir or key.startswith("products.")
        return self._check_required_path(key, path, is_dir=is_dir)

    def write_target(self, key: str) -> Path:
        """Return a registered write destination after checking workspace bounds.

        Unlike :meth:`require`, the destination need not exist and is not created.
        Resolving with ``strict=False`` still follows existing links and junctions.
        """
        paths = {
            "state.review_queue": self.review_queue,
            "state.plans": self.plans,
            "state.availability": self.availability,
            "state.routes": self.routes,
            "state.timetable": self.timetable,
            "state.question_bank": self.question_bank,
            "staging": self.staging,
            "projection": self.projection,
        }
        path = paths.get(key)
        if path is None:
            raise ContractError("not registered", key)
        directory_keys = {
            "state.review_queue", "state.plans", "state.routes", "state.question_bank",
            "staging",
        }
        file_keys = {"state.availability", "state.timetable", "projection"}
        try:
            real_path = path.resolve(strict=False)
            real_root = self.root.resolve(strict=True)
            real_path.relative_to(real_root)
        except ValueError as exc:
            raise ContractError("resolves outside the workspace", key) from exc
        except (OSError, RuntimeError) as exc:
            raise ContractError(f"cannot resolve registered path: {exc}", key) from exc
        if path.exists():
            if key in directory_keys and not path.is_dir():
                raise ContractError("expected a directory", key)
            if key in file_keys and not path.is_file():
                raise ContractError("expected a file", key)
        return path

    def require_all(self, key: str) -> tuple[Path, ...]:
        """Return a registered path list only after every entry passes checks."""
        paths = self._registered_path_list(key)
        if paths is None:
            if key in self._single_paths():
                raise ContractError("field is not a path list", key)
            raise ContractError("not registered", key)
        # Build a tuple only after checking each file; no partial result escapes.
        return tuple(
            self._check_required_path(key, path, is_dir=False)
            for path in paths
        )

    def _registered_path_list(self, key: str) -> tuple[Path, ...] | None:
        exam_prefix = "reference.exam_indexes."
        if key.startswith(exam_prefix):
            return self.exam_indexes.get(key[len(exam_prefix) :])
        version_prefix = "reference.syllabus_versions."
        if key.startswith(version_prefix) and key.endswith(".mappings"):
            subject = key[len(version_prefix) : -len(".mappings")]
            registered = self.syllabus_versions.get(subject)
            return None if registered is None else registered.mappings
        return None


def _absolute(path: str | Path, *, cwd: Path | None = None) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = (cwd or Path.cwd()) / candidate
    # Normalize ``.`` and ``..`` lexically without following symlinks.
    return Path(os.path.normpath(str(candidate.absolute())))


def _select_workspace(
    start: Path | None, explicit: str | Path | None
) -> tuple[Path, str]:
    if explicit is not None:
        source = _absolute(explicit)
        label = "--workspace"
        if not source.is_file():
            raise ContractError(f"{label} workspace file does not exist: {source}", label)
        return source, label

    env_value = os.environ.get(WORKSPACE_ENV)
    if env_value:
        source = _absolute(env_value)
        label = WORKSPACE_ENV
        if not source.is_file():
            raise ContractError(f"{label} workspace file does not exist: {source}", label)
        return source, label

    origin = _absolute(start if start is not None else Path.cwd())
    current = origin.parent if origin.is_file() else origin
    for directory in (current, *current.parents):
        candidate = directory / WORKSPACE_FILENAME
        if candidate.is_file():
            return candidate.absolute(), "upward search"
    raise ContractError(
        f"{WORKSPACE_FILENAME} not found (searched upward from {origin}; "
        f"set --workspace or {WORKSPACE_ENV})"
    )


def find_workspace(start: Path | None = None, *, explicit: str | Path | None = None) -> Path:
    """Find the workspace registry using explicit, environment, then upward search."""
    return _select_workspace(start, explicit)[0]


def _mapping(value: object, path: str) -> Mapping[str, object]:
    result = _require_mapping(value, path)
    if any(not isinstance(key, str) for key in result):
        raise ContractError("mapping keys must be strings", path)
    return result


def _required(node: Mapping[str, object], key: str, path: str) -> object:
    if key not in node:
        field = f"{path}.{key}" if path else key
        raise ContractError("required field is missing", field)
    return node[key]


def _string(value: object, path: str, *, nonempty: bool = True) -> str:
    if not isinstance(value, str) or (nonempty and not value):
        raise ContractError(
            "expected a non-empty string" if nonempty else "expected a string", path
        )
    return value


def _registered_path(value: object, field: str, root: Path) -> Path:
    raw = _string(value, field)
    segments = raw.split("/")
    if (
        "\\" in raw
        or raw.startswith("/")
        or ":" in raw
        or any(segment in {"", ".", ".."} for segment in segments)
    ):
        raise ContractError("invalid registered path", field)
    return root.joinpath(*PurePosixPath(raw).parts)


def _path_mapping(
    value: object,
    field: str,
    root: Path,
    allowed_keys: frozenset[str] | None = None,
) -> Mapping[str, Path]:
    raw = _mapping(value, field)
    if allowed_keys is not None:
        _reject_unknown_keys(raw, allowed_keys, field)
    return MappingProxyType(
        {key: _registered_path(path, f"{field}.{key}", root) for key, path in raw.items()}
    )


def _name(value: object, field: str) -> str:
    name = _string(value, field)
    if not _NAME_RE.fullmatch(name):
        raise ContractError("invalid identifier", field)
    return name


def _reject_duplicate_keys(node: yaml.Node, path: str, _visited: set[int] | None = None) -> None:
    """Walk the composed node tree and report a repeated mapping key at its real dotted path.

    Working on nodes (which keep every key, unlike the constructed dict) gives the exact field
    path for quoted keys, flow mappings and nested levels alike -- no text re-parsing.

    An alias makes the node graph share (or cycle back to) a node; each node is checked once,
    so a self-referencing alias cannot recurse forever. The structural checks that run
    afterwards reject such a document as an unknown or mistyped field.
    """
    visited = set() if _visited is None else _visited
    if id(node) in visited:
        return
    visited.add(id(node))
    if isinstance(node, yaml.MappingNode):
        seen: set[str] = set()
        for key_node, value_node in node.value:
            key = key_node.value if isinstance(key_node, yaml.ScalarNode) else None
            child = (f"{path}.{key}" if path else str(key)) if key is not None else path
            if key is not None:
                if key in seen:
                    raise ContractError(
                        f"duplicate YAML field (line {key_node.start_mark.line + 1})", child
                    )
                seen.add(key)
            _reject_duplicate_keys(value_node, child, visited)
    elif isinstance(node, yaml.SequenceNode):
        for index, item in enumerate(node.value):
            _reject_duplicate_keys(item, f"{path}[{index}]", visited)


def _parse_registry(raw_bytes: bytes) -> object:
    """Parse exactly the bytes that were hashed (spec section 5): one read, one version."""
    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ContractError(f"registry is not valid UTF-8: {exc}", "") from exc
    try:
        node = yaml.compose(text, Loader=yaml.SafeLoader)
    except yaml.YAMLError as exc:
        raise ContractError(f"invalid YAML: {exc}", "") from exc
    if node is not None:
        _reject_duplicate_keys(node, "")
    return yaml.load(text, Loader=_StrictSafeLoader)


def _parse_syllabus_versions(
    reference: Mapping[str, object],
    subject_set: set[str],
    knowledge_trees: Mapping[str, Path],
    root: Path,
) -> Mapping[str, SyllabusVersions]:
    raw_syllabus = _mapping(
        reference.get("syllabus_versions", {}), "reference.syllabus_versions"
    )
    records: dict[str, SyllabusVersions] = {}
    for subject, raw_record in raw_syllabus.items():
        field = f"reference.syllabus_versions.{subject}"
        if subject not in subject_set:
            raise ContractError("subject is not declared", field)
        record = _mapping(raw_record, field)
        _reject_unknown_keys(record, frozenset({"versions", "mappings"}), field)
        versions_value = _required(record, "versions", field)
        if not isinstance(versions_value, Mapping):
            raise ContractError("expected a mapping", f"{field}.versions")
        if not versions_value:
            raise ContractError("at least one version is required", f"{field}.versions")
        versions = _parse_version_paths(versions_value, field, root)
        effective = knowledge_trees.get(subject)
        if effective is None or effective not in versions.values():
            raise ContractError(
                "effective tree path must match one registered version",
                f"reference.knowledge_trees.{subject}",
            )
        mappings = _parse_mapping_paths(record.get("mappings", []), field, root)
        records[subject] = SyllabusVersions(MappingProxyType(versions), mappings)
    return MappingProxyType(records)


def _parse_version_paths(
    values: Mapping[object, object], field: str, root: Path
) -> dict[str, Path]:
    versions: dict[str, Path] = {}
    for label, value in values.items():
        version_field = f"{field}.versions.{label}"
        if not isinstance(label, str) or not _SYLLABUS_VERSION_RE.fullmatch(label):
            raise ContractError("version label must be a four-digit string", version_field)
        path = _registered_path(value, version_field, root)
        if path in versions.values():
            raise ContractError("version tree path is already registered", version_field)
        versions[label] = path
    return versions


def _parse_mapping_paths(value: object, field: str, root: Path) -> tuple[Path, ...]:
    mappings_field = f"{field}.mappings"
    if not isinstance(value, list):
        raise ContractError("expected a list", mappings_field)
    return tuple(
        _registered_path(item, f"{mappings_field}[{index}]", root)
        for index, item in enumerate(value)
    )


def _parse_subjects(
    doc: Mapping[str, object],
) -> tuple[tuple[str, ...], dict[str, SubjectProfile], set[str]]:
    raw_subjects = _mapping(_required(doc, "subjects", ""), "subjects")
    if not raw_subjects:
        raise ContractError("at least one subject is required", "subjects")
    subjects: list[str] = []
    profiles: dict[str, SubjectProfile] = {}
    for subject, raw_profile in raw_subjects.items():
        field = f"subjects.{subject}"
        if not _SUBJECT_RE.fullmatch(subject):
            raise ContractError("invalid subject identifier", field)
        profile = _mapping(raw_profile, field)
        _reject_unknown_keys(
            profile,
            frozenset({"name", "tree_grammar", "domain_segment", "features"}),
            field,
        )
        name = _string(_required(profile, "name", field), f"{field}.name")
        grammar = None
        if "tree_grammar" in profile:
            grammar = _string(profile["tree_grammar"], f"{field}.tree_grammar")
            if grammar not in _TREE_GRAMMARS:
                raise ContractError("unknown tree grammar", f"{field}.tree_grammar")
        domain_segment = profile.get("domain_segment", False)
        if not isinstance(domain_segment, bool):
            raise ContractError("expected a boolean", f"{field}.domain_segment")
        raw_features = profile.get("features", [])
        if not isinstance(raw_features, list):
            raise ContractError("expected a list", f"{field}.features")
        features: list[str] = []
        for index, raw_feature in enumerate(raw_features):
            feature = _string(raw_feature, f"{field}.features[{index}]")
            if feature not in _SUBJECT_FEATURES:
                raise ContractError("unknown subject feature", f"{field}.features[{index}]")
            if feature in features:
                raise ContractError("duplicate subject feature", f"{field}.features[{index}]")
            features.append(feature)
        subjects.append(subject)
        profiles[subject] = SubjectProfile(name, grammar, domain_segment, tuple(features))
    subject_tuple = tuple(subjects)
    return subject_tuple, profiles, set(subject_tuple)


def _parse_knowledge_trees(
    reference: Mapping[str, object],
    subject_set: set[str],
    profiles: Mapping[str, SubjectProfile],
    root: Path,
) -> Mapping[str, Path]:
    knowledge_raw = _mapping(
        _required(reference, "knowledge_trees", "reference"),
        "reference.knowledge_trees",
    )
    knowledge_trees = _path_mapping(knowledge_raw, "reference.knowledge_trees", root)
    for subject in knowledge_trees:
        if subject not in subject_set:
            raise ContractError("subject is not declared", f"reference.knowledge_trees.{subject}")
        if profiles[subject].tree_grammar is None:
            raise ContractError(
                "tree grammar is required for a registered tree",
                f"subjects.{subject}.tree_grammar",
            )
    return knowledge_trees


def _parse_exam_indexes(
    reference: Mapping[str, object], subject_set: set[str], root: Path
) -> Mapping[str, tuple[Path, ...]]:
    exam_raw = _mapping(
        _required(reference, "exam_indexes", "reference"), "reference.exam_indexes"
    )
    exam_indexes: dict[str, tuple[Path, ...]] = {}
    seen_paths: set[str] = set()
    for subject, values in exam_raw.items():
        field = f"reference.exam_indexes.{subject}"
        if subject not in subject_set:
            raise ContractError("subject is not declared", field)
        if not isinstance(values, list):
            raise ContractError("expected a list", field)
        if not values:
            raise ContractError("path list must not be empty", field)
        parsed: list[Path] = []
        for index, value in enumerate(values):
            item_field = f"{field}[{index}]"
            resolved = _registered_path(value, item_field, root)
            # Preserve case-insensitive duplicate detection on Windows.
            normalized = os.path.normcase(str(value))
            if normalized in seen_paths:
                raise ContractError("path is registered more than once", item_field)
            seen_paths.add(normalized)
            parsed.append(resolved)
        exam_indexes[subject] = tuple(parsed)
    return MappingProxyType(exam_indexes)


def _parse_paper_shapes(
    reference: Mapping[str, object], subject_set: set[str], root: Path
) -> Mapping[str, Path]:
    paper_shapes = _path_mapping(
        reference.get("paper_shapes", {}), "reference.paper_shapes", root
    )
    for subject in paper_shapes:
        if subject not in subject_set:
            raise ContractError("subject is not declared", f"reference.paper_shapes.{subject}")
    return paper_shapes


def _parse_reference_paths(
    reference: Mapping[str, object], root: Path
) -> dict[str, Path | None]:
    paths: dict[str, Path | None] = {
        "topic_weights": _registered_path(
            _required(reference, "topic_weights", "reference"),
            "reference.topic_weights",
            root,
        ),
        "weight_batches": (
            _registered_path(reference["weight_batches"], "reference.weight_batches", root)
            if "weight_batches" in reference
            else None
        ),
        "vocabulary_db": _registered_path(
            _required(reference, "vocabulary_db", "reference"),
            "reference.vocabulary_db",
            root,
        ),
        "ledger": _registered_path(
            _required(reference, "ledger", "reference"), "reference.ledger", root
        ),
    }
    return paths


def _parse_timetable_schools(
    reference: Mapping[str, object], root: Path
) -> Mapping[str, Path]:
    raw = _mapping(reference.get("timetable_schools", {}), "reference.timetable_schools")
    schools: dict[str, Path] = {}
    for school_id, value in raw.items():
        field = f"reference.timetable_schools.{school_id}"
        _name(school_id, field)
        schools[school_id] = _registered_path(value, field, root)
    return MappingProxyType(schools)


def _parse_reference(
    doc: Mapping[str, object],
    subject_set: set[str],
    profiles: Mapping[str, SubjectProfile],
    root: Path,
) -> dict[str, object]:
    reference = _mapping(_required(doc, "reference", ""), "reference")
    _reject_unknown_keys(reference, _REFERENCE_KEYS, "reference")
    knowledge_trees = _parse_knowledge_trees(reference, subject_set, profiles, root)
    syllabus_versions = _parse_syllabus_versions(
        reference, subject_set, knowledge_trees, root
    )
    exam_indexes = _parse_exam_indexes(reference, subject_set, root)
    paper_shapes = _parse_paper_shapes(reference, subject_set, root)
    paths = _parse_reference_paths(reference, root)
    return {
        "knowledge_trees": knowledge_trees,
        "syllabus_versions": syllabus_versions,
        "exam_indexes": exam_indexes,
        "paper_shapes": paper_shapes,
        "timetable_schools": _parse_timetable_schools(reference, root),
        **paths,
    }


def _parse_supplementary(
    doc: Mapping[str, object], subject_set: set[str], root: Path
) -> Mapping[str, SupplementaryView]:
    supplementary_node = _mapping(doc.get("supplementary", {}), "supplementary")
    supplementary: dict[str, SupplementaryView] = {}
    for raw_name, raw_view in supplementary_node.items():
        name = _name(raw_name, f"supplementary.{raw_name}")
        field = f"supplementary.{name}"
        view = _mapping(raw_view, field)
        _reject_unknown_keys(view, _SUPPLEMENTARY_KEYS, field)
        kind = _string(_required(view, "kind", field), f"{field}.kind")
        if kind not in _VIEW_ROLES:
            raise ContractError("unknown supplementary kind", f"{field}.kind")
        subject = _string(_required(view, "subject", field), f"{field}.subject")
        if subject not in subject_set:
            raise ContractError("subject is not declared", f"{field}.subject")
        description = _string(_required(view, "description", field), f"{field}.description")
        files_field = f"{field}.files"
        files_raw = _mapping(_required(view, "files", field), files_field)
        _reject_unknown_keys(files_raw, _VIEW_ROLES[kind], files_field)
        missing_role = _VIEW_ROLES[kind] - set(files_raw)
        if missing_role:
            role = sorted(missing_role)[0]
            raise ContractError("required role is missing", f"{files_field}.{role}")
        files = _path_mapping(files_raw, files_field, root)
        supplementary[name] = SupplementaryView(name, kind, subject, description, files)
    return MappingProxyType(supplementary)


def _parse_materials(doc: Mapping[str, object], root: Path) -> Path:
    materials = _mapping(_required(doc, "materials", ""), "materials")
    _reject_unknown_keys(materials, _MATERIALS_KEYS, "materials")
    return _registered_path(
        _required(materials, "raw_root", "materials"), "materials.raw_root", root
    )


def _parse_products(doc: Mapping[str, object], root: Path) -> Mapping[str, Path]:
    products_raw = _mapping(doc.get("products", {}), "products")
    products: dict[str, Path] = {}
    for raw_name, value in products_raw.items():
        name = _name(raw_name, f"products.{raw_name}")
        products[name] = _registered_path(value, f"products.{name}", root)
    return MappingProxyType(products)


def _parse_settings(doc: Mapping[str, object], root: Path) -> dict[str, Path | None]:
    settings = _mapping(doc.get("settings", {}), "settings")
    _reject_unknown_keys(settings, _SETTINGS_KEYS, "settings")
    return {
        key: (_registered_path(settings[key], f"settings.{key}", root)
              if key in settings else None)
        for key in ("exam_config", "pacing")
    }


def _parse_state(doc: Mapping[str, object], root: Path) -> dict[str, Path | None]:
    state = _mapping(_required(doc, "state", ""), "state")
    _reject_unknown_keys(state, _STATE_KEYS, "state")
    return {
        "review_queue": _registered_path(
            _required(state, "review_queue", "state"), "state.review_queue", root
        ),
        "plans": _registered_path(_required(state, "plans", "state"), "state.plans", root),
        "availability": (
            _registered_path(state["availability"], "state.availability", root)
            if "availability" in state
            else None
        ),
        "routes": (
            _registered_path(state["routes"], "state.routes", root)
            if "routes" in state
            else None
        ),
        "timetable": (
            _registered_path(state["timetable"], "state.timetable", root)
            if "timetable" in state
            else None
        ),
        "question_bank": (
            _registered_path(state["question_bank"], "state.question_bank", root)
            if "question_bank" in state
            else None
        ),
    }


def _parse_output_targets(doc: Mapping[str, object], root: Path) -> tuple[Path, Path]:
    staging = _registered_path(_required(doc, "staging", ""), "staging", root)
    projection = _registered_path(_required(doc, "projection", ""), "projection", root)
    return staging, projection


def _parse_document(raw: object, root: Path) -> dict[str, object]:
    doc = _mapping(raw, "")
    _reject_unknown_keys(doc, _ROOT_KEYS, "")
    version = _required(doc, "schema_version", "")
    if isinstance(version, bool) or not isinstance(version, int):
        raise ContractError("expected an integer", "schema_version")
    if version != 2:
        raise ContractError(f"unsupported schema_version {version}", "schema_version")
    subjects, profiles, subject_set = _parse_subjects(doc)
    reference = _parse_reference(doc, subject_set, profiles, root)
    supplementary = _parse_supplementary(doc, subject_set, root)
    raw_root = _parse_materials(doc, root)
    products = _parse_products(doc, root)
    settings = _parse_settings(doc, root)
    state = _parse_state(doc, root)
    staging, projection = _parse_output_targets(doc, root)
    return {
        "subjects": subjects,
        "profiles": profiles,
        **reference,
        "supplementary": supplementary,
        "raw_root": raw_root,
        "products": products,
        **settings,
        **state,
        "staging": staging,
        "projection": projection,
    }


def _local_field(path: str) -> str:
    return f"local.{path}" if path else "local"


def _parse_local_path(value: object, field: str, root: Path) -> Path:
    try:
        return _registered_path(value, field, root)
    except ContractError as exc:
        raise ContractError(str(exc).split(": ", 1)[-1], _local_field(exc.path)) from exc


def _parse_local_mapping(value: object, field: str, root: Path) -> Mapping[str, Path]:
    try:
        raw = _mapping(value, field)
    except ContractError as exc:
        raise ContractError(str(exc).split(": ", 1)[-1], _local_field(exc.path)) from exc
    result: dict[str, Path] = {}
    for raw_key, path in raw.items():
        key_field = f"{field}.{raw_key}"
        try:
            key = _name(raw_key, key_field)
            result[key] = _registered_path(path, key_field, root)
        except ContractError as exc:
            raise ContractError(
                str(exc).split(": ", 1)[-1], _local_field(exc.path)
            ) from exc
    return MappingProxyType(result)


def _parse_local_document(
    raw: object, root: Path, main: Mapping[str, object]
) -> dict[str, object]:
    doc = _mapping(raw, "local")
    allowed_roots = frozenset({"schema_version", "reference", "settings", "state"})
    _reject_unknown_keys(doc, allowed_roots, "local")
    version = _required(doc, "schema_version", "local")
    if isinstance(version, bool) or not isinstance(version, int) or version != 1:
        raise ContractError("expected schema_version 1", "local.schema_version")

    result: dict[str, object] = {}
    for section, allowed in (
        ("reference", frozenset({"timetable_schools"})),
        ("settings", frozenset({"exam_config", "pacing"})),
        ("state", frozenset({"availability", "timetable", "question_bank"})),
    ):
        if section not in doc:
            continue
        values = _mapping(doc[section], f"local.{section}")
        _reject_unknown_keys(values, allowed, f"local.{section}")
        main_values = _mapping(main.get(section, {}), section)
        for key, value in values.items():
            field = f"{section}.{key}"
            if key in main_values:
                raise ContractError(
                    "local field is already registered", _local_field(field)
                )
            if section == "reference":
                result["timetable_schools"] = _parse_local_mapping(
                    value, field, root
                )
            else:
                result[key] = _parse_local_path(value, field, root)
    return result


def _read_local_overlay(
    source: Path, main: Mapping[str, object]
) -> tuple[bytes | None, dict[str, object]]:
    path = source.with_name("kaoyan.workspace.local.yaml")
    try:
        raw_bytes = path.read_bytes()
    except FileNotFoundError:
        return None, {}
    except OSError as exc:
        raise ContractError(f"cannot read local workspace file: {exc}", "local") from exc
    try:
        raw = _parse_registry(raw_bytes)
    except ContractError as exc:
        raise ContractError(str(exc).split(": ", 1)[-1], _local_field(exc.path)) from exc
    except yaml.YAMLError as exc:
        raise ContractError(f"invalid YAML: {exc}", "local") from exc
    return raw_bytes, _parse_local_document(raw, source.parent, main)


def _workspace_from_parts(
    source: Path,
    raw_bytes: bytes,
    parts: Mapping[str, object],
    local_sha256: str | None = None,
) -> Workspace:
    return Workspace(
        source=source,
        root=source.parent,
        sha256=hashlib.sha256(raw_bytes).hexdigest(),
        subjects=parts["subjects"],
        subject_profiles=MappingProxyType(parts["profiles"]),
        knowledge_trees=parts["knowledge_trees"],
        syllabus_versions=parts["syllabus_versions"],
        exam_indexes=parts["exam_indexes"],
        paper_shapes=parts["paper_shapes"],
        timetable_schools=parts["timetable_schools"],
        topic_weights=parts["topic_weights"],
        weight_batches=parts["weight_batches"],
        vocabulary_db=parts["vocabulary_db"],
        ledger=parts["ledger"],
        supplementary=parts["supplementary"],
        raw_root=parts["raw_root"],
        products=parts["products"],
        exam_config=parts["exam_config"],
        pacing=parts["pacing"],
        review_queue=parts["review_queue"],
        plans=parts["plans"],
        availability=parts["availability"],
        routes=parts["routes"],
        timetable=parts["timetable"],
        question_bank=parts["question_bank"],
        staging=parts["staging"],
        projection=parts["projection"],
        local_sha256=local_sha256,
    )


def _add_selection_context(exc: ContractError, source_label: str) -> ContractError:
    if source_label not in {"--workspace", WORKSPACE_ENV}:
        return exc
    message = str(exc)
    if exc.path and message.startswith(f"{exc.path}: "):
        message = message[len(exc.path) + 2 :]
    return ContractError(f"{message} (selected via {source_label})", exc.path)


def load_workspace(path: str | Path | None = None) -> Workspace:
    """Load and validate a registry without touching any registered paths."""
    source, source_label = _select_workspace(None, path)
    try:
        try:
            raw_bytes = source.read_bytes()
        except OSError as exc:
            raise ContractError(f"cannot read workspace file: {exc}", source_label) from exc
        raw = _parse_registry(raw_bytes)
        parts = _parse_document(raw, source.parent)
        local_bytes, local_parts = _read_local_overlay(source, _mapping(raw, ""))
        parts.update(local_parts)
        local_hash = (
            hashlib.sha256(local_bytes).hexdigest() if local_bytes is not None else None
        )
        return _workspace_from_parts(source, raw_bytes, parts, local_hash)
    except ContractError as exc:
        contextual = _add_selection_context(exc, source_label)
        if contextual is exc:
            raise
        raise contextual from exc
