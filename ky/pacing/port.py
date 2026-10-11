"""M28 pacing settings, periods, reports, and route conversion; see ``contracts/pacing_review.md``.

Public interfaces: ``load_settings``, ``settings_for_workspace``, ``cycle_for_date``,
``missing_report_cycles``, ``load_pacing_report_state``, ``build_report``,
``report_to_mapping``, and ``apply_pacing``.
Report inputs are caller supplied.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Any, Mapping, Sequence

import yaml

from ky.freeze.port import FreezeEvent, latch_active
from ky.availability import Availability, DerivedDailyMinutes
from ky.models import ContractError, KaoyanConfig, ReviewItem, load_yaml_text
from ky.planner.port import canonical_json_bytes
from ky.schedule.budget import daily_base_minutes, resolve_day_budget
from ky.schedule.completion import CompletionEvent
from ky.schedule.longitudinal import DayPlan
from ky.schedule.planning import Phase, RoutePlan, validate_route_plan
from ky.storage.day_plan_store import DayPlanRecord
from ky.workspace import Workspace
from ky.pacing.storage import read_report, report_path


@dataclass(frozen=True)
class Cadence:
    kind: str
    until: date | None


@dataclass(frozen=True)
class PacingSettings:
    start: date
    exam_date: date
    minimum: int
    maximum: int
    initial: int
    max_step_minutes: int
    cadence: tuple[Cadence, ...]


@dataclass(frozen=True)
class PacingCycle:
    start: date
    end_exclusive: date

    @property
    def end(self) -> date:
        return self.end_exclusive - timedelta(days=1)


def _date(value: object, path: str) -> date:
    if isinstance(value, datetime):
        raise ContractError("datetime is not a date", path)
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise ContractError("expected YYYY-MM-DD date", path) from exc
        if parsed.isoformat() == value:
            return parsed
    raise ContractError("expected YAML date or strict YYYY-MM-DD", path)


def _require_date(value: object, path: str) -> date:
    if type(value) is not date:
        raise ContractError("expected a date", path)
    return value


def _integer(value: object, path: str) -> int:
    if type(value) is not int or value < 0:
        raise ContractError("expected a non-negative integer", path)
    return value


def _mapping(value: object, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or any(not isinstance(k, str) for k in value):
        raise ContractError("expected a mapping", path)
    return value


def _keys(value: Mapping[str, Any], expected: set[str], path: str) -> None:
    unknown = set(value) - expected
    missing = expected - set(value)
    if unknown:
        key = sorted(unknown)[0]
        raise ContractError("unknown field", f"{path}.{key}".strip("."))
    if missing:
        key = sorted(missing)[0]
        raise ContractError("required field is missing", f"{path}.{key}".strip("."))


def load_settings(raw: object, *, source: str = "settings.pacing") -> PacingSettings:
    """Validate one already parsed settings mapping."""
    node = _mapping(raw, source)
    _keys(node, {"schema_version", "start", "exam_date", "base_daily_minutes",
                 "max_step_minutes", "cadence"}, source)
    if type(node["schema_version"]) is not int or node["schema_version"] != 1:
        raise ContractError("expected integer 1", f"{source}.schema_version")
    start = _date(node["start"], f"{source}.start")
    exam_date = _date(node["exam_date"], f"{source}.exam_date")
    if exam_date <= start:
        raise ContractError("must be later than start", f"{source}.exam_date")
    budget = _mapping(node["base_daily_minutes"], f"{source}.base_daily_minutes")
    _keys(budget, {"min", "max", "initial"}, f"{source}.base_daily_minutes")
    minimum = _integer(budget["min"], f"{source}.base_daily_minutes.min")
    maximum = _integer(budget["max"], f"{source}.base_daily_minutes.max")
    initial = _integer(budget["initial"], f"{source}.base_daily_minutes.initial")
    if not minimum <= initial <= maximum:
        raise ContractError("require min <= initial <= max",
                            f"{source}.base_daily_minutes")
    max_step = _integer(node["max_step_minutes"], f"{source}.max_step_minutes")
    raw_cadence = node["cadence"]
    if not isinstance(raw_cadence, list) or not raw_cadence:
        raise ContractError("expected a non-empty list", f"{source}.cadence")
    cadence: list[Cadence] = []
    for index, item in enumerate(raw_cadence):
        path = f"{source}.cadence[{index}]"
        record = _mapping(item, path)
        final = index == len(raw_cadence) - 1
        _keys(record, {"kind"} if final else {"kind", "until"}, path)
        kind = record["kind"]
        if not isinstance(kind, str) or kind not in {"half_month", "month"}:
            raise ContractError("kind must be half_month or month", f"{path}.kind")
        until = None if final else _date(record["until"], f"{path}.until")
        if until is not None:
            if until.day != 1:
                raise ContractError("until must be the first day of a month",
                                    f"{path}.until")
            if cadence and cadence[-1].until is not None and until <= cadence[-1].until:
                raise ContractError("until values must increase", f"{path}.until")
            if not cadence and until <= start:
                raise ContractError("first until must be later than start", f"{path}.until")
        cadence.append(Cadence(kind, until))
    return PacingSettings(start, exam_date, minimum, maximum, initial, max_step,
                          tuple(cadence))


def load_settings_file(path: str) -> PacingSettings:
    """Read and strictly parse the registered settings file."""
    return load_settings_source(path)[0]


def settings_for_workspace(workspace: Workspace) -> PacingSettings | None:
    """Load optional registered pacing settings once for an M8 consumer."""
    pacing_path = getattr(workspace, "pacing", None)
    if pacing_path is None:
        return None
    return load_settings_file(pacing_path)


def load_settings_source(path: str) -> tuple[PacingSettings, str]:
    """Read and validate settings once, returning the digest of the parsed bytes."""
    try:
        data = Path(path).read_bytes()
        value = load_yaml_text(data.decode("utf-8"), source=path)
    except OSError as exc:
        raise ContractError(f"cannot read pacing settings: {exc}", path) from exc
    except UnicodeError as exc:
        raise ContractError(f"settings are not UTF-8: {exc}", path) from exc
    return load_settings(value, source=path), hashlib.sha256(data).hexdigest()


def _month_after(day: date) -> date:
    if day.month == 12:
        return date(day.year + 1, 1, 1)
    return date(day.year, day.month + 1, 1)


def _next_boundary(day: date, kind: str) -> date:
    if kind == "month":
        return _month_after(day)
    if day.day < 16:
        return date(day.year, day.month, 16)
    return _month_after(day)


def _previous_boundary(day: date, kind: str) -> date:
    if kind == "half_month" and day.day >= 16:
        return date(day.year, day.month, 16)
    return date(day.year, day.month, 1)


def _boundary_after(settings: PacingSettings, cursor: date, index: int) -> tuple[date, int]:
    """Return the next cycle boundary and the cadence index in force from it."""
    spec = settings.cadence[index]
    boundary = _next_boundary(cursor, spec.kind)
    if spec.until is not None and boundary >= spec.until:
        return spec.until, index + 1
    return boundary, index


def _first_cycle_end(settings: PacingSettings) -> tuple[date, int]:
    # User 2026-10-02: a start off the 1st / 16th snaps to the nearer boundary. Nearer the
    # previous one (or a tie) keeps a short first cycle; nearer the next one joins the
    # following cycle, so no cycle is only a few days long.
    start = settings.start
    end, index = _boundary_after(settings, start, 0)
    previous = _previous_boundary(start, settings.cadence[0].kind)
    if previous < start and end - start < start - previous:
        end, index = _boundary_after(settings, end, index)
    return end, index


def cycle_for_date(settings: PacingSettings, day: date) -> PacingCycle | None:
    """Return the half-open cycle containing day, or None before configured start."""
    if not isinstance(settings, PacingSettings):
        raise ContractError("expected PacingSettings", "settings")
    day = _require_date(day, "day")
    if day < settings.start:
        return None
    cursor = settings.start
    end, index = _first_cycle_end(settings)
    while end <= day:
        cursor = end
        end, index = _boundary_after(settings, cursor, index)
    return PacingCycle(cursor, end)


def missing_report_cycles(settings: PacingSettings, today: date,
                          plans_root: Path) -> tuple[PacingCycle, ...]:
    """Return ended cycles before today's cycle that do not have saved reports."""
    missing, _reports = load_pacing_report_state(settings, today, plans_root)
    return missing


def load_pacing_report_state(
    settings: PacingSettings, today: date, plans_root: Path,
) -> tuple[tuple[PacingCycle, ...], Mapping[str, Mapping[str, Any]]]:
    """Load and validate prior M28 reports once for an assembled view (M33 §3)."""
    current = cycle_for_date(settings, today)
    if current is None:
        return (), {}
    cursor = settings.start
    missing = []
    reports: dict[str, Mapping[str, Any]] = {}
    while cursor < current.start:
        cycle = cycle_for_date(settings, cursor)
        if cycle is None:
            break
        if cycle.end < today:
            path = report_path(plans_root, cycle.end.isoformat())
            if path.exists():
                reports[cycle.end.isoformat()] = read_report(path)
            else:
                missing.append(cycle)
        cursor = cycle.end_exclusive
    return tuple(missing), reports


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    value = (Decimal(numerator) / Decimal(denominator)).quantize(
        Decimal("0.001"), rounding=ROUND_HALF_EVEN
    )
    return float(value)


def _as_day_plan(record: DayPlanRecord | DayPlan) -> DayPlan:
    return record.plan if isinstance(record, DayPlanRecord) else record


def build_report(
    settings: PacingSettings,
    config: KaoyanConfig,
    cycle: PacingCycle,
    today: date,
    *,
    plans: Sequence[DayPlanRecord | DayPlan] = (),
    completions: Sequence[CompletionEvent] = (),
    items: Sequence[ReviewItem] = (),
    freeze_events: Sequence[FreezeEvent] = (),
    sources: Mapping[str, str] | None = None,
    previous: Mapping[str, Any] | None = None,
    availability: Availability | None = None,
    timetable: DerivedDailyMinutes | None = None,
    route: RoutePlan | None = None,
) -> dict[str, Any]:
    """Calculate the frozen report mapping. Caller supplies one snapshot of all sources."""
    _validate_report_inputs(settings, config, cycle, today)
    days = _cycle_days(cycle)
    bases = [daily_base_minutes(day, config, route, pacing_initial=settings)[0]
             for day in days]
    reference_minutes = _reference_minutes(
        days, config, availability, route, timetable, settings
    )
    day_plans = [_as_day_plan(plan) for plan in plans]
    included = _period_completions(completions, cycle)
    reviews, unattributed, duplicates = _review_statistics(completions, items, cycle)
    backlog, due_next = _queue_statistics(settings, cycle, today, items)
    frozen = _freeze_statistics(cycle, freeze_events)
    report = _report_mapping(
        cycle, today, bases, reference_minutes, day_plans, included, reviews,
        unattributed, duplicates, backlog, due_next, frozen, sources, previous,
    )
    report["report_hash"] = hashlib.sha256(
        canonical_json_bytes(report_to_mapping(report))
    ).hexdigest()
    return report


def _validate_report_inputs(
    settings: PacingSettings, config: KaoyanConfig, cycle: PacingCycle, today: date,
) -> None:
    if not isinstance(settings, PacingSettings):
        raise ContractError("expected PacingSettings", "settings")
    if not isinstance(config, KaoyanConfig):
        raise ContractError("expected KaoyanConfig", "config")
    if not isinstance(cycle, PacingCycle):
        raise ContractError("expected PacingCycle", "cycle")
    today = _require_date(today, "today")
    start = _require_date(cycle.start, "cycle.start")
    end_exclusive = _require_date(cycle.end_exclusive, "cycle.end_exclusive")
    if end_exclusive <= start:
        raise ContractError("cycle must be a non-empty interval", "cycle")


def _cycle_days(cycle: PacingCycle) -> tuple[date, ...]:
    return tuple(cycle.start + timedelta(days=index)
                 for index in range((cycle.end_exclusive - cycle.start).days))


def _reference_minutes(
    days: Sequence[date], config: KaoyanConfig, availability: Availability | None,
    route: RoutePlan | None, timetable: DerivedDailyMinutes | None,
    pacing_initial: PacingSettings,
) -> int:
    return sum(
        resolve_day_budget(day, config, availability, route, timetable,
                           pacing_initial=pacing_initial).total_minutes
        for day in days
    )


def _period_completions(
    completions: Sequence[CompletionEvent], cycle: PacingCycle,
) -> tuple[CompletionEvent, ...]:
    return tuple(event for event in completions
                 if cycle.start <= event.day < cycle.end_exclusive)


def _review_statistics(
    completions: Sequence[CompletionEvent], items: Sequence[ReviewItem],
    cycle: PacingCycle,
) -> tuple[dict[str, dict[str, Any]], int, int]:
    by_review = {item.review_id: item.subject_id for item in items}
    selected: dict[str, tuple[date, Any]] = {}
    duplicates = 0
    for event in completions:
        for index, review in enumerate(event.reviews):
            identifier = review.completion_id or f"{event.day}#{index}"
            old = selected.get(identifier)
            if old is None:
                selected[identifier] = (event.day, review)
                continue
            duplicates += 1
            if event.day < old[0]:
                selected[identifier] = (event.day, review)
    reviews: dict[str, dict[str, Any]] = {}
    unattributed = 0
    for event_day, review in selected.values():
        if not cycle.start <= review.completed_on < cycle.end_exclusive:
            continue
        subject = by_review.get(review.review_id)
        if subject is None:
            unattributed += 1
            continue
        counts = reviews.setdefault(subject, {"completed": 0, "correct": 0,
            "partial": 0, "incorrect": 0, "none": 0})
        counts["completed"] += 1
        outcome = review.outcome if review.check != "none" else "none"
        counts[outcome] += 1
    for counts in reviews.values():
        counts["miss_ratio"] = _ratio(counts["incorrect"] + counts["partial"],
            counts["correct"] + counts["partial"] + counts["incorrect"])

    return dict(sorted(reviews.items())), unattributed, duplicates


def _queue_statistics(
    settings: PacingSettings, cycle: PacingCycle, today: date,
    items: Sequence[ReviewItem],
) -> tuple[dict[str, int], dict[str, int]]:
    backlog: dict[str, int] = {}
    due_next: dict[str, int] = {}
    following = cycle_for_date(settings, cycle.end_exclusive)
    for item in items:
        if item.state not in {"queued", "scheduled"}:
            continue
        if item.due_date < today:
            backlog[item.subject_id] = backlog.get(item.subject_id, 0) + item.estimated_minutes
        if following is not None and following.start <= item.due_date < following.end_exclusive:
            due_next[item.subject_id] = due_next.get(item.subject_id, 0) + item.estimated_minutes

    return dict(sorted(backlog.items())), dict(sorted(due_next.items()))


def _freeze_statistics(
    cycle: PacingCycle, freeze_events: Sequence[FreezeEvent],
) -> dict[str, Any]:
    end_events = [event for event in freeze_events if event.day <= cycle.end]
    period_events = [event for event in freeze_events
                     if cycle.start <= event.day <= cycle.end]
    return {"events": len(period_events), "latched_at_end": latch_active(end_events)}


def _report_mapping(
    cycle: PacingCycle, today: date, bases: Sequence[int], reference_minutes: int,
    plans: Sequence[DayPlan], completions: Sequence[CompletionEvent],
    reviews: Mapping[str, Mapping[str, Any]], unattributed: int, duplicates: int,
    backlog: Mapping[str, int], due_next: Mapping[str, int], frozen: Mapping[str, Any],
    sources: Mapping[str, str] | None, previous: Mapping[str, Any] | None,
) -> dict[str, Any]:
    study_events = [event for event in completions if event.study_minutes is not None]
    return {
        "schema_version": 1,
        "cycle": {"start": cycle.start.isoformat(), "end": cycle.end.isoformat(),
                  "days": len(bases)},
        "generated_on": today.isoformat(),
        "base": {"min": min(bases), "max": max(bases),
                 "mean": sum(bases) // len(bases),
                 "source_note": (
                     "路线阶段 > 复盘设置 initial > 考试配置"
                 )},
        "reference_minutes": reference_minutes,
        "reference_source_note": "按生成时来源重算",
        "declared_minutes": {"days": len({plan.day for plan in plans
            if cycle.start <= plan.day < cycle.end_exclusive}),
            "sum": sum(plan.available_minutes for plan in plans
                if cycle.start <= plan.day < cycle.end_exclusive)},
        "recorded_event_days": len({event.day for event in completions}),
        "study_minutes": {"days": len({event.day for event in study_events}),
                          "sum": sum(event.study_minutes for event in study_events)},
        "reviews": dict(reviews),
        "reviews_unattributed": unattributed,
        "duplicate_completion_ids": duplicates,
        "backlog_observed": {"observed_on": today.isoformat(),
            "total": sum(backlog.values()), "by_subject": dict(backlog)},
        "freeze": dict(frozen),
        "due_next": dict(due_next),
        "previous": (None if previous is None else {key: previous[key] for key in
            ("reviews", "backlog_observed", "study_minutes", "cycle", "report_hash")}),
        "sources": dict(sorted((sources or {}).items())),
    }


def report_to_mapping(report: Mapping[str, Any]) -> dict[str, Any]:
    """Return a shallow plain-dict copy; nested objects remain shared."""
    return dict(report)


def apply_pacing(
    route: RoutePlan | None,
    proposal: Mapping[str, Any],
    settings: PacingSettings,
    cycle_end: date,
) -> RoutePlan:
    """Create the next route revision by replacing or splitting one active phase."""
    if route is not None and not isinstance(route, RoutePlan):
        raise ContractError("expected RoutePlan or None", "route")
    if not isinstance(proposal, Mapping):
        raise ContractError("expected a proposal mapping", "proposal")
    if not isinstance(settings, PacingSettings):
        raise ContractError("expected PacingSettings", "settings")
    cycle_end = _require_date(cycle_end, "cycle_end")
    effective = _date(proposal.get("effective_from"), "proposal.effective_from")
    base = _integer(proposal.get("base_daily_minutes"), "proposal.base_daily_minutes")
    review_raw = _mapping(proposal.get("review_minutes"), "proposal.review_minutes")
    review_minutes = dict(review_raw)
    input_hash = proposal.get("input_hash")
    if not isinstance(input_hash, str) or len(input_hash) != 64:
        raise ContractError("expected a SHA-256 digest", "proposal.input_hash")
    if route is None:
        result = _new_pacing_route(effective, settings.exam_date, cycle_end,
                                   review_minutes, base, input_hash)
    else:
        phases = _phases_with_adjustment(route, effective, cycle_end, review_minutes, base)
        result = RoutePlan(
            route.route_id, route.revision + 1, route.start_date,
            route.target_exam_date, route.policy_version, input_hash, phases,
        )
    try:
        return validate_route_plan(result)
    except ValueError as exc:
        raise ContractError(f"invalid pacing route: {exc}", "route") from exc


def _new_pacing_route(effective: date, exam_date: date, cycle_end: date,
                      review_minutes: dict[str, Any], base: int, input_hash: str) -> RoutePlan:
    """Build revision 1 when no route exists (§7 "无路线")."""
    phases = (Phase(0, effective, exam_date, f"复盘 {cycle_end}", review_minutes, base),)
    return RoutePlan("pacing", 1, effective, exam_date, "pacing-v1", input_hash, phases)


def _phases_with_adjustment(route: RoutePlan, effective: date, cycle_end: date,
                            review_minutes: dict[str, Any], base: int) -> tuple[Phase, ...]:
    """Replace the phase holding ``effective`` in place, or split it there (§7 "有路线")."""
    if not any(phase.start <= effective < phase.end_exclusive for phase in route.phases):
        raise ContractError("effective_from is outside the existing route", "effective_from")
    phases: list[Phase] = []
    for phase in route.phases:
        if not phase.start <= effective < phase.end_exclusive:
            phases.append(phase)
        elif effective == phase.start:
            phases.append(Phase(phase.index, phase.start, phase.end_exclusive, phase.label,
                                review_minutes, base, phase.targets))
        else:
            phases.append(Phase(phase.index, phase.start, effective, phase.label,
                                phase.review_minutes, phase.base_daily_minutes, None))
            phases.append(Phase(phase.index + 1, effective, phase.end_exclusive,
                                f"{phase.label} · 复盘 {cycle_end}", review_minutes, base,
                                phase.targets))
    # A split shifts every later phase by one, so §7 renumbers all indexes from 0.
    return tuple(Phase(index, phase.start, phase.end_exclusive, phase.label,
                       phase.review_minutes, phase.base_daily_minutes, phase.targets)
                 for index, phase in enumerate(phases))
