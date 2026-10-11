"""M4 knowledge-tree port from ``contracts/knowledge_tree.md``.

Public interfaces validate nodes and trees, apply deterministic frequency, and
perform actor-checked status transitions. Hierarchy helpers are public through
``ky.knowledge``. Extraction and frequency inference are outside this module.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from ky.models import ContractError, load_yaml_text

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

KNOWLEDGE_SCHEMA_VERSION = 1
ACTOR_AI = "ai"
ACTOR_HUMAN = "human"
ACTOR_DETERMINISTIC_SCRIPT = "deterministic_script"
STATISTICAL_VALIDATIONS = frozenset(
    {"frequency", "coverage", "baseline", "prediction", "final_acceptance"}
)
VALID_STATUSES = ("raw", "extracted", "reviewed", "approved", "superseded")
VALID_SOURCE_KINDS = frozenset(
    {"official_outline", "textbook", "real_question", "manual", "ai_generated"}
)
VALID_VALIDATIONS = frozenset({"guided", "independent", *STATISTICAL_VALIDATIONS})

# How broad a node is. This is what makes the syllabus's own 考查目标 usable
# without letting them masquerade as something a learner can achieve in a day.
#
# The 408 syllabus states 12 考查目标, all at **subject** scope, e.g. "掌握数据
# 结构的基本概念、基本原理和基本方法". That is a two-year aspiration, not a
# next-day acceptance criterion. Scope makes the difference machine-checkable:
# a planner may only attach `day`-granular criteria to a day, and must report an
# objective-scope goal as a standing tracker instead.
VALID_SCOPES = frozenset({"subject", "chapter", "section", "item"})

# Scopes a single study day could plausibly be assessed against.
DAY_ASSESSABLE_SCOPES = frozenset({"section", "item"})

# Scopes a *block* review is assessed against. A block is one chapter's worth of
# study; `subject` earns its place here because the syllabus's 考查目标 are
# subject-wide statements -- unusable as a next-day check, exactly right as the
# question a learner answers after finishing a chapter of that subject.
BLOCK_ASSESSABLE_SCOPES = frozenset({"chapter", "subject"})

# Scopes that must never enter frequency statistics or capability levels: they
# describe the exam's intent, not examinable content.
NON_EXAMINABLE_SCOPES = frozenset({"subject"})

TRANSITION_RULES: dict[tuple[str, str], dict[str, frozenset[str]]] = {
    ("raw", "extracted"): {
        "actors": frozenset({ACTOR_AI, ACTOR_HUMAN}),
        "requires": frozenset({"source"}),
    },
    ("extracted", "reviewed"): {
        "actors": frozenset({ACTOR_HUMAN}),
        "requires": frozenset({"source", "evidence"}),
    },
    ("reviewed", "approved"): {
        "actors": frozenset({ACTOR_HUMAN}),
        "requires": frozenset({"source", "evidence"}),
    },
    ("approved", "superseded"): {
        "actors": frozenset({ACTOR_HUMAN}),
        "requires": frozenset({"source", "replacement"}),
    },
}

_POINT_KEYS = {
    "schema_version", "knowledge_point_id", "title", "status", "source_kind", "sources",
    "frequency", "evidence", "transition_history", "supersedes", "revision", "scope",
}
_SOURCE_KEYS = {"path", "sha256", "locator"}
_FREQUENCY_KEYS = {"value", "basis", "computed_by", "as_of"}
_EVIDENCE_KEYS = {"validation", "result", "source", "note"}
_TRANSITION_KEYS = {"from", "to", "actor", "at", "source", "evidence", "replacement", "reason"}
_LOCATOR_KEYS = {"page", "line", "line_start", "line_end", "section", "offset", "quote_ref"}


class KnowledgePointError(ValueError):
    def __init__(self, message: str, path: str = "") -> None:
        self.path = path
        super().__init__(f"{path}: {message}" if path else message)


def _map(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise KnowledgePointError(f"expected a mapping, got {type(value).__name__}", path)
    return value


def _unknown(node: Mapping[str, Any], allowed: set[str], path: str) -> None:
    extra = sorted(set(node) - allowed)
    if extra:
        key = extra[0]
        raise KnowledgePointError(f"unknown field {key!r}", f"{path}.{key}" if path else key)


def _str(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise KnowledgePointError("expected a non-empty string", path)
    return value


def _int(value: Any, path: str, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise KnowledgePointError(f"expected an integer, got {type(value).__name__}", path)
    if minimum is not None and value < minimum:
        raise KnowledgePointError(f"must be >= {minimum}, got {value}", path)
    return value


def _source(value: Any, path: str) -> dict[str, Any]:
    node = _map(value, path)
    _unknown(node, _SOURCE_KEYS, path)
    source_path = _str(node.get("path"), f"{path}.path")
    digest = _str(node.get("sha256"), f"{path}.sha256")
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest.lower()):
        raise KnowledgePointError("expected a SHA-256 hex digest", f"{path}.sha256")
    locator = _map(node.get("locator"), f"{path}.locator")
    _unknown(locator, _LOCATOR_KEYS, f"{path}.locator")
    if not locator:
        raise KnowledgePointError(
            "locator must identify a page, line, section, offset or quote",
            f"{path}.locator",
        )
    return {"path": source_path, "sha256": digest, "locator": dict(locator)}


def _sources(value: Any, path: str) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or not value:
        raise KnowledgePointError("expected a non-empty list", path)
    return [_source(entry, f"{path}[{index}]") for index, entry in enumerate(value)]


def _validate_frequency(value: Any, path: str, *, source_kind: str) -> dict[str, Any] | None:
    if value is None:
        return None
    node = _map(value, path)
    _unknown(node, _FREQUENCY_KEYS, path)
    if "value" not in node:
        raise KnowledgePointError("frequency requires value when present", f"{path}.value")
    frequency_value = node["value"]
    if isinstance(frequency_value, bool) or not isinstance(frequency_value, (int, float)):
        raise KnowledgePointError("expected a numeric frequency value", f"{path}.value")
    if isinstance(frequency_value, float) and not math.isfinite(frequency_value):
        raise KnowledgePointError("expected a finite frequency value", f"{path}.value")
    if frequency_value < 0:
        raise KnowledgePointError("must be >= 0", f"{path}.value")
    if source_kind == "ai_generated":
        raise KnowledgePointError(
            "AI-generated points cannot carry frequency.value", f"{path}.value"
        )
    if node.get("computed_by") != ACTOR_DETERMINISTIC_SCRIPT:
        raise KnowledgePointError(
            "frequency.computed_by must be deterministic_script", f"{path}.computed_by"
        )
    return dict(node)


def _validate_evidence(value: Any, path: str, *, source_kind: str) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise KnowledgePointError("expected a list", path)
    result: list[dict[str, Any]] = []
    for index, entry in enumerate(value):
        item_path = f"{path}[{index}]"
        node = _map(entry, item_path)
        _unknown(node, _EVIDENCE_KEYS, item_path)
        validation = _str(node.get("validation"), f"{item_path}.validation")
        if validation not in VALID_VALIDATIONS:
            raise KnowledgePointError(
                f"unsupported validation {validation!r}", f"{item_path}.validation"
            )
        if source_kind == "ai_generated" and validation != "guided":
            raise KnowledgePointError(
                "AI-generated points may produce only validation=guided evidence",
                f"{item_path}.validation",
            )
        _source(node.get("source"), f"{item_path}.source")
        result.append(dict(node))
    return result


def _validate_history(value: Any, path: str, *, source_kind: str) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise KnowledgePointError("expected a list", path)
    result: list[dict[str, Any]] = []
    previous = "raw"
    for index, entry in enumerate(value):
        item_path = f"{path}[{index}]"
        node = _map(entry, item_path)
        _unknown(node, _TRANSITION_KEYS, item_path)
        from_status = _str(node.get("from"), f"{item_path}.from")
        to_status = _str(node.get("to"), f"{item_path}.to")
        actor = _str(node.get("actor"), f"{item_path}.actor")
        if from_status != previous:
            raise KnowledgePointError(
                "transition history is not a contiguous chain", f"{item_path}.from"
            )
        validate_transition(from_status, to_status, actor, node, path=item_path)
        if source_kind == "ai_generated" and to_status == "approved":
            raise KnowledgePointError(
                "AI-generated points cannot transition to approved", f"{item_path}.to"
            )
        _source(node.get("source"), f"{item_path}.source")
        history_evidence = node.get("evidence")
        if history_evidence is not None:
            evidence_node = _map(history_evidence, f"{item_path}.evidence")
            validation = _str(evidence_node.get("validation"), f"{item_path}.evidence.validation")
            _source(evidence_node.get("source"), f"{item_path}.evidence.source")
            if source_kind == "ai_generated" and validation != "guided":
                raise KnowledgePointError(
                    "AI-generated points may produce only validation=guided evidence",
                    f"{item_path}.evidence.validation",
                )
        previous = to_status
        result.append(dict(node))
    return result


def validate_transition(
    from_status: str,
    to_status: str,
    actor: str,
    details: Mapping[str, Any] | None = None,
    *,
    path: str = "transition",
) -> None:
    rule = TRANSITION_RULES.get((from_status, to_status))
    if rule is None:
        raise KnowledgePointError(
            f"transition {from_status!r} -> {to_status!r} is not allowed",
            f"{path}.to",
        )
    if actor not in rule["actors"]:
        raise KnowledgePointError(
            f"actor {actor!r} cannot initiate this transition", f"{path}.actor"
        )
    node = details or {}
    for key in rule["requires"]:
        if not node.get(key):
            raise KnowledgePointError(f"transition requires {key}", f"{path}.{key}")


@dataclass(frozen=True)
class KnowledgePoint:
    knowledge_point_id: str
    title: str
    status: str
    source_kind: str
    sources: tuple[dict[str, Any], ...]
    frequency: dict[str, Any] | None
    evidence: tuple[dict[str, Any], ...]
    transition_history: tuple[dict[str, Any], ...]
    supersedes: str | None
    revision: int
    scope: str = "item"

    def is_day_assessable(self) -> bool:
        """Whether a single study day could be assessed against this node.

        ``subject``-scope goals (the syllabus's 考查目标) cannot: they are
        standing trackers, not next-day checks.
        """
        return self.scope in DAY_ASSESSABLE_SCOPES

    def is_examinable(self) -> bool:
        """Whether this node is examinable content at all."""
        return self.scope not in NON_EXAMINABLE_SCOPES


def validate_knowledge_point(raw: Any, *, source: str = "<knowledge_point>") -> KnowledgePoint:
    path = source
    node = _map(raw, path)
    _unknown(node, _POINT_KEYS, path)
    schema = _int(
        node.get("schema_version", KNOWLEDGE_SCHEMA_VERSION),
        f"{path}.schema_version",
        minimum=1,
    )
    if schema != KNOWLEDGE_SCHEMA_VERSION:
        raise KnowledgePointError(f"unsupported schema_version {schema}", f"{path}.schema_version")
    point_id = _str(node.get("knowledge_point_id"), f"{path}.knowledge_point_id")
    title = _str(node.get("title"), f"{path}.title")
    status = _str(node.get("status"), f"{path}.status")
    if status not in VALID_STATUSES:
        raise KnowledgePointError(f"unsupported status {status!r}", f"{path}.status")
    source_kind = _str(node.get("source_kind"), f"{path}.source_kind")
    if source_kind not in VALID_SOURCE_KINDS:
        raise KnowledgePointError(f"unsupported source_kind {source_kind!r}", f"{path}.source_kind")
    sources = tuple(_sources(node.get("sources"), f"{path}.sources"))
    frequency = _validate_frequency(
        node.get("frequency"), f"{path}.frequency", source_kind=source_kind
    )
    evidence = tuple(
        _validate_evidence(node.get("evidence"), f"{path}.evidence", source_kind=source_kind)
    )
    history = tuple(
        _validate_history(
            node.get("transition_history"),
            f"{path}.transition_history",
            source_kind=source_kind,
        )
    )
    if history and history[-1]["to"] != status:
        raise KnowledgePointError("last transition must lead to current status", f"{path}.status")
    if not history and status != "raw":
        raise KnowledgePointError(
            "non-raw points require transition_history", f"{path}.transition_history"
        )
    supersedes = node.get("supersedes")
    if supersedes is not None:
        supersedes = _str(supersedes, f"{path}.supersedes")
    revision = _int(node.get("revision", 1), f"{path}.revision", minimum=1)
    # Default to ``item``: the narrowest, most checkable granularity. A node
    # only becomes broader by saying so explicitly.
    scope = _str(node.get("scope", "item"), f"{path}.scope")
    if scope not in VALID_SCOPES:
        raise KnowledgePointError(
            f"scope must be one of {', '.join(sorted(VALID_SCOPES))}, got {scope!r}",
            f"{path}.scope",
        )
    return KnowledgePoint(
        point_id, title, status, source_kind, sources, frequency, evidence,
        history, supersedes, revision, scope,
    )


def transition_knowledge_point(
    raw: Mapping[str, Any],
    target_status: str,
    actor: str,
    *,
    source: Mapping[str, Any] | None = None,
    evidence: Mapping[str, Any] | None = None,
    replacement: str | None = None,
    reason: str | None = None,
    at: str | None = None,
) -> dict[str, Any]:
    """Return a new mapping after one validated workflow transition."""
    current = copy.deepcopy(dict(raw))
    point = validate_knowledge_point(current)
    details: dict[str, Any] = {
        "from": point.status,
        "to": target_status,
        "actor": actor,
        "at": at or datetime.now(timezone.utc).isoformat(),
    }
    if source is not None:
        details["source"] = dict(source)
    if evidence is not None:
        details["evidence"] = dict(evidence)
    if replacement is not None:
        details["replacement"] = replacement
    if reason is not None:
        details["reason"] = reason
    validate_transition(point.status, target_status, actor, details)
    if source is not None:
        _source(source, "transition.source")
    if evidence is not None:
        _map(evidence, "transition.evidence")
    current["status"] = target_status
    current.setdefault("transition_history", []).append(details)
    if target_status == "superseded":
        current["supersedes"] = replacement
    validate_knowledge_point(current)
    return current


def apply_deterministic_frequency(
    raw: Mapping[str, Any],
    value: int | float,
    *,
    basis: str,
    as_of: str,
    writer: str,
) -> dict[str, Any]:
    if writer != ACTOR_DETERMINISTIC_SCRIPT:
        raise KnowledgePointError(
            "frequency.value may only be written by deterministic_script",
            "frequency.value",
        )
    current = copy.deepcopy(dict(raw))
    current["frequency"] = {"value": value, "basis": basis, "computed_by": writer, "as_of": as_of}
    validate_knowledge_point(current)
    return current


def _scope_of(point: KnowledgePoint | Mapping[str, Any]) -> str:
    if isinstance(point, KnowledgePoint):
        return point.scope
    # A raw mapping being validated downstream may not carry scope yet; treat
    # it as the narrowest granularity, matching ``validate_knowledge_point``.
    return str(point.get("scope", "item"))


def eligible_for_frequency(point: KnowledgePoint | Mapping[str, Any]) -> bool:
    """Whether this node may be counted in frequency statistics.

    Requires examinable content *and* a non-generated source. A subject-scope
    objective is excluded even though it comes from the official syllabus: it
    states the exam's intent, so counting it would inflate every denominator.
    """
    source_kind = (
        point.source_kind if isinstance(point, KnowledgePoint) else point.get("source_kind")
    )
    return source_kind != "ai_generated" and _scope_of(point) not in NON_EXAMINABLE_SCOPES


def eligible_for_exam_metrics(point: KnowledgePoint | Mapping[str, Any]) -> bool:
    """Whether this node may feed coverage or prediction metrics."""
    source_kind = (
        point.source_kind if isinstance(point, KnowledgePoint) else point.get("source_kind")
    )
    return source_kind != "ai_generated" and _scope_of(point) not in NON_EXAMINABLE_SCOPES


def block_verification_targets(
    points: Iterable[KnowledgePoint | Mapping[str, Any]],
) -> tuple[KnowledgePoint | Mapping[str, Any], ...]:
    """The nodes that a *block* review is assessed against.

    A block is one chapter's worth of study. Its verification target is the
    subject-level 考查目标 (the syllabus's own statement of what the subject
    demands) together with the chapter node itself.

    The cadence matters and is the whole point of this function: a 考查目标 such
    as "掌握数据结构的基本概念、基本原理和基本方法" can never be a *daily*
    acceptance criterion -- no single study day makes it true -- but it is
    exactly the right thing to check after a chapter is finished. Keeping the
    granularity explicit is what stops a planner from either misusing it as a
    next-day check or dropping it entirely.
    """
    out: list[KnowledgePoint | Mapping[str, Any]] = []
    for point in points:
        if _scope_of(point) in BLOCK_ASSESSABLE_SCOPES:
            out.append(point)
    return tuple(out)


def load_knowledge_points_from_text(
    text: str,
    *,
    source: str,
) -> tuple[KnowledgePoint, ...]:
    """Validate knowledge points parsed from YAML text.

    The strict YAML loader currently locates duplicate keys at the source-file level.
    """
    if yaml is None:  # pragma: no cover
        raise KnowledgePointError("PyYAML is required", source)
    try:
        raw = load_yaml_text(text, source=source)
    except ContractError as exc:
        raise KnowledgePointError(exc.message, exc.path or source) from exc
    if isinstance(raw, Mapping) and "items" in raw:
        _unknown(raw, {"schema_version", "items"}, source)
        schema_version = raw.get("schema_version", KNOWLEDGE_SCHEMA_VERSION)
        if (isinstance(schema_version, bool) or not isinstance(schema_version, int)
                or schema_version != KNOWLEDGE_SCHEMA_VERSION):
            raise KnowledgePointError(
                f"unsupported schema_version {schema_version}", f"{source}.schema_version"
            )
        entries = raw["items"]
    else:
        entries = raw
    if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
        raise KnowledgePointError("expected a list of knowledge points", f"{source}.items")
    return tuple(
        validate_knowledge_point(
            item,
            source=f"{source}.items[{index}]",
        )
        for index, item in enumerate(entries)
    )


def load_knowledge_points(
    path: str | Path,
) -> tuple[KnowledgePoint, ...]:
    resolved = Path(path)
    try:
        text = resolved.read_bytes().decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise KnowledgePointError(str(exc), resolved.as_posix()) from exc
    return load_knowledge_points_from_text(
        text,
        source=resolved.as_posix(),
    )
