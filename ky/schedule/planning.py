"""M11 variable route timeline contract: ``contracts/route_plan.md`` (D10, schema v2–v4).

Public interfaces are :class:`RoutePlan`, :class:`Phase`, :func:`route_plan_to_mapping`,
:func:`parse_route_plan`, and :func:`validate_route_plan`.

The route is a caller-authored timeline of adjacent, non-overlapping phases. Each phase
records daily review minutes and may supply a daily base or M30 stage targets; this module
validates the shape without choosing dates, labels, or minute allocations.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Mapping

__all__ = [
    "Phase",
    "RoutePlan",
    "RoutePlanError",
    "parse_route_plan",
    "route_plan_to_mapping",
    "validate_route_plan",
]

_ROUTE_KEYS = frozenset({
    "schema_version", "route_id", "revision", "start_date", "target_exam_date",
    "policy_version", "stage1_input_hash", "phases",
})
_PHASE_KEYS = frozenset({"index", "start", "end_exclusive", "label", "review_minutes"})


class RoutePlanError(ValueError):
    """A route-plan contract error with the path of the invalid field."""

    def __init__(self, message: str, path: str = "") -> None:
        self.path = path
        super().__init__(f"{path}: {message}" if path else message)


@dataclass(frozen=True)
class Phase:
    """One half-open timeline interval with daily review minutes by subject."""

    index: int
    start: date
    end_exclusive: date
    label: str
    review_minutes: Mapping[str, int]
    base_daily_minutes: int | None = None
    targets: Mapping[str, int] | None = None


@dataclass(frozen=True)
class RoutePlan:
    """A versioned route whose phases cover ``[start_date, target_exam_date)``."""

    route_id: str
    revision: int
    start_date: date
    target_exam_date: date
    policy_version: str
    stage1_input_hash: str
    phases: tuple[Phase, ...]

    @property
    def end_exclusive(self) -> date:
        return self.target_exam_date


def _is_sha256_hex(value: str) -> bool:
    return len(value) == 64 and all(c in "0123456789abcdef" for c in value.lower())


def validate_route_plan(plan: RoutePlan) -> RoutePlan:
    """Verify timeline closure and field values, then return ``plan`` unchanged."""
    if not plan.route_id.strip():
        raise RoutePlanError("route_id must be a non-empty string", "route_id")
    if isinstance(plan.revision, bool) or not isinstance(plan.revision, int) or plan.revision < 1:
        raise RoutePlanError(f"revision must be an integer >= 1, got {plan.revision}", "revision")
    if not plan.policy_version.strip():
        raise RoutePlanError("policy_version must be a non-empty string", "policy_version")
    if not _is_sha256_hex(plan.stage1_input_hash):
        raise RoutePlanError(
            "stage1_input_hash must be a 64-character lowercase hex SHA-256 digest",
            "stage1_input_hash",
        )
    if plan.target_exam_date <= plan.start_date:
        raise RoutePlanError(
            "target_exam_date must be after start_date", "target_exam_date"
        )
    if not plan.phases:
        raise RoutePlanError("phases must not be empty", "phases")

    cursor = plan.start_date
    previous_targets: Mapping[str, int] | None = None
    for i, phase in enumerate(plan.phases):
        path = f"phases[{i}]"
        if isinstance(phase.index, bool) or not isinstance(phase.index, int) or phase.index != i:
            raise RoutePlanError(f"phase index must be {i}, got {phase.index}", f"{path}.index")
        if phase.start != cursor:
            requirement = "start_date" if i == 0 else "the previous phase end_exclusive"
            raise RoutePlanError(
                f"phase must start at {requirement} ({cursor}), got {phase.start}",
                f"{path}.start",
            )
        if phase.end_exclusive <= phase.start:
            raise RoutePlanError(
                "end_exclusive must be after start", f"{path}.end_exclusive"
            )
        if not phase.label.strip():
            raise RoutePlanError("label must be a non-empty string", f"{path}.label")
        if not phase.review_minutes:
            raise RoutePlanError("review_minutes must not be empty", f"{path}.review_minutes")
        for subject_id, minutes in phase.review_minutes.items():
            field = f"{path}.review_minutes.{subject_id}"
            if not isinstance(subject_id, str) or not subject_id.strip():
                raise RoutePlanError(
                    "subject ID must be a non-empty string", f"{path}.review_minutes"
                )
            if isinstance(minutes, bool) or not isinstance(minutes, int) or minutes < 0:
                raise RoutePlanError("expected a non-negative integer", field)
        _check_phase_base(phase, path)
        if phase.targets is not None:
            _check_phase_targets(phase.targets, f"{path}.targets")
            if previous_targets is not None:
                for key in ("covered", "consolidated"):
                    if phase.targets[key] < previous_targets[key]:
                        raise RoutePlanError(
                            "target must not decrease from the previous target phase",
                            f"{path}.targets.{key}",
                        )
            previous_targets = phase.targets
        cursor = phase.end_exclusive

    if cursor != plan.target_exam_date:
        raise RoutePlanError(
            f"last phase must end at target_exam_date ({plan.target_exam_date}), got {cursor}",
            f"phases[{len(plan.phases) - 1}].end_exclusive",
        )
    return plan


def _check_phase_base(phase: Phase, path: str) -> None:
    value = phase.base_daily_minutes
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RoutePlanError("expected a non-negative integer", f"{path}.base_daily_minutes")


def _check_phase_targets(targets: Mapping[str, int], path: str) -> None:
    if not isinstance(targets, Mapping) or any(not isinstance(key, str) for key in targets):
        raise RoutePlanError("expected a mapping", path)
    unknown = sorted(set(targets) - {"covered", "consolidated"})
    if unknown:
        raise RoutePlanError("unknown field", f"{path}.{unknown[0]}")
    missing = {"covered", "consolidated"} - set(targets)
    if missing:
        raise RoutePlanError("required field is missing", f"{path}.{sorted(missing)[0]}")
    for key in ("covered", "consolidated"):
        value = targets[key]
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100:
            raise RoutePlanError("expected an integer from 0 to 100", f"{path}.{key}")
    if targets["consolidated"] > targets["covered"]:
        raise RoutePlanError("consolidated must not exceed covered", f"{path}.consolidated")


def route_plan_to_mapping(plan: RoutePlan) -> dict[str, Any]:
    """Return the sole YAML/JSON mapping shape for a route plan (M11, D10)."""
    has_base = any(phase.base_daily_minutes is not None for phase in plan.phases)
    has_targets = any(phase.targets is not None for phase in plan.phases)
    phases = []
    for phase in plan.phases:
        item = {
            "index": phase.index,
            "start": phase.start.isoformat(),
            "end_exclusive": phase.end_exclusive.isoformat(),
            "label": phase.label,
            "review_minutes": dict(phase.review_minutes),
        }
        if phase.base_daily_minutes is not None:
            item["base_daily_minutes"] = phase.base_daily_minutes
        if phase.targets is not None:
            item["targets"] = {
                "covered": phase.targets["covered"],
                "consolidated": phase.targets["consolidated"],
            }
        phases.append(item)
    return {
        "schema_version": 4 if has_targets else 3 if has_base else 2,
        "route_id": plan.route_id,
        "revision": plan.revision,
        "start_date": plan.start_date.isoformat(),
        "target_exam_date": plan.target_exam_date.isoformat(),
        "policy_version": plan.policy_version,
        "stage1_input_hash": plan.stage1_input_hash,
        "phases": phases,
    }


def parse_route_plan(raw: object, path: str = "route_plan") -> RoutePlan:
    """Parse the strict timeline mapping and validate its closure."""
    node = _route_mapping(raw, path)
    # Version first: an old 24-month file carries `months`, and the key check below would
    # otherwise report "unknown field" instead of telling the user what changed.
    if "schema_version" in node:
        schema = _route_integer(node["schema_version"], f"{path}.schema_version")
        if schema == 1:
            raise RoutePlanError(
                "旧 24 月格式已作废（D10），请按时间线格式重写", f"{path}.schema_version"
            )
        if schema not in (2, 3, 4):
            raise RoutePlanError("schema_version must be 2, 3, or 4", f"{path}.schema_version")
    schema = node.get("schema_version", 2)
    phases_node = node.get("phases")
    if schema == 2 and isinstance(phases_node, list) and any(
        isinstance(item, Mapping) and "base_daily_minutes" in item
        for item in phases_node
    ):
        raise RoutePlanError("schema_version 2 does not allow base_daily_minutes", path)
    has_targets = isinstance(phases_node, list) and any(
        isinstance(item, Mapping) and "targets" in item for item in phases_node
    )
    if schema in (2, 3) and has_targets:
        for index, item in enumerate(phases_node):
            if isinstance(item, Mapping) and "targets" in item:
                raise RoutePlanError("targets require schema_version 4",
                                     f"{path}.phases[{index}].targets")
    _route_exact_keys(node, _ROUTE_KEYS, path)
    phases_raw = node["phases"]
    if not isinstance(phases_raw, list):
        raise RoutePlanError("expected a list", f"{path}.phases")
    phases = tuple(
        _parse_phase(item, f"{path}.phases[{index}]")
        for index, item in enumerate(phases_raw)
    )
    plan = RoutePlan(
        route_id=_route_string(node["route_id"], f"{path}.route_id"),
        revision=_route_integer(node["revision"], f"{path}.revision"),
        start_date=_route_date(node["start_date"], f"{path}.start_date"),
        target_exam_date=_route_date(node["target_exam_date"], f"{path}.target_exam_date"),
        policy_version=_route_string(node["policy_version"], f"{path}.policy_version"),
        stage1_input_hash=_route_string(node["stage1_input_hash"], f"{path}.stage1_input_hash"),
        phases=phases,
    )
    return validate_route_plan(plan)


def _parse_phase(raw: object, path: str) -> Phase:
    node = _route_mapping(raw, path)
    unknown = sorted(set(node) - _PHASE_KEYS - {"base_daily_minutes", "targets"})
    if unknown:
        raise RoutePlanError(f"unknown field {unknown[0]!r}", f"{path}.{unknown[0]}")
    required = {key: value for key, value in node.items()
                if key not in {"base_daily_minutes", "targets"}}
    _route_exact_keys(required, _PHASE_KEYS, path)
    minutes_raw = _route_mapping(node["review_minutes"], f"{path}.review_minutes")
    minutes: dict[str, int] = {}
    for subject_id, value in minutes_raw.items():
        if not isinstance(subject_id, str):
            raise RoutePlanError("mapping keys must be strings", f"{path}.review_minutes")
        minutes[subject_id] = _route_integer(
            value, f"{path}.review_minutes.{subject_id}"
        )
    return Phase(
        index=_route_integer(node["index"], f"{path}.index"),
        start=_route_date(node["start"], f"{path}.start"),
        end_exclusive=_route_date(node["end_exclusive"], f"{path}.end_exclusive"),
        label=_route_string(node["label"], f"{path}.label"),
        review_minutes=minutes,
        base_daily_minutes=(
            _route_integer(node["base_daily_minutes"], f"{path}.base_daily_minutes")
            if "base_daily_minutes" in node else None
        ),
        targets=(
            _parse_targets(node["targets"], f"{path}.targets")
            if "targets" in node else None
        ),
    )


def _parse_targets(raw: object, path: str) -> dict[str, int]:
    if not isinstance(raw, Mapping):
        raise RoutePlanError("expected a mapping", path)
    if any(not isinstance(key, str) for key in raw):
        raise RoutePlanError("mapping keys must be strings", path)
    unknown = sorted(set(raw) - {"covered", "consolidated"})
    if unknown:
        raise RoutePlanError("unknown field", f"{path}.{unknown[0]}")
    missing = {"covered", "consolidated"} - set(raw)
    if missing:
        raise RoutePlanError("required field is missing", f"{path}.{sorted(missing)[0]}")
    return {
        key: _route_integer(raw[key], f"{path}.{key}")
        for key in ("covered", "consolidated")
    }


def _route_mapping(raw: object, path: str) -> Mapping[str, object]:
    if not isinstance(raw, Mapping):
        raise RoutePlanError("expected a mapping", path)
    if any(not isinstance(key, str) for key in raw):
        raise RoutePlanError("mapping keys must be strings", path)
    return raw


def _route_exact_keys(node: Mapping[str, object], expected: frozenset[str], path: str) -> None:
    unknown = sorted(set(node) - expected)
    if unknown:
        raise RoutePlanError(f"unknown field {unknown[0]!r}", f"{path}.{unknown[0]}")
    missing = sorted(expected - set(node))
    if missing:
        raise RoutePlanError("required field is missing", f"{path}.{missing[0]}")


def _route_integer(value: object, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise RoutePlanError("expected an integer", path)
    return value


def _route_string(value: object, path: str) -> str:
    if not isinstance(value, str):
        raise RoutePlanError("expected a string", path)
    return value


def _route_date(value: object, path: str) -> date:
    if isinstance(value, datetime):
        raise RoutePlanError("datetime is not accepted; expected a date", path)
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise RoutePlanError("expected a date or YYYY-MM-DD string", path)
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise RoutePlanError("expected a YYYY-MM-DD date", path) from exc
    if parsed.isoformat() != value:
        raise RoutePlanError("expected a YYYY-MM-DD date", path)
    return parsed
