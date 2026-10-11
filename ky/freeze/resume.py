"""M27 pure backlog replanning; see ``contracts/freeze.md``.

Public interfaces: :class:`ResumePlan`, :func:`plan_resume`, and
:func:`resume_plan_to_mapping` (D11).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Mapping, Sequence

from ky.availability import Availability, DerivedDailyMinutes
from ky.freeze.port import overdue_review_items
from ky.models import KaoyanConfig, ReviewItem, scale_minutes
from ky.schedule.budget import PacingInitial, resolve_day_budget
from ky.schedule.completion import reset_for_relearning
from ky.schedule.planning import RoutePlan

_SEARCH_DAYS = 366


@dataclass(frozen=True)
class ResumeEntry:
    """Auditable before/after summary for one overdue item."""

    review_id: str
    tier: str
    old_due_date: date
    new_due_date: date
    reset_for_relearning: bool


@dataclass(frozen=True)
class ResumePlan:
    """Replanned queue and its stable audit summary."""

    day: date
    entries: tuple[ResumeEntry, ...]
    updated_items: tuple[ReviewItem, ...]
    possible_forgetting_count: int
    recent_overdue_count: int
    last_assigned_day: date | None
    unschedulable_review_ids: tuple[str, ...]
    scheduled_to_queued_count: int


def plan_resume(
    day: date,
    config: KaoyanConfig,
    items: Sequence[ReviewItem],
    *,
    availability: Availability | None,
    route: RoutePlan | None,
    timetable: DerivedDailyMinutes | None = None,
    pacing_initial: PacingInitial | None = None,
) -> ResumePlan:
    """Replan queued overdue work against each future day's ordinary capacity."""
    overdue = overdue_review_items(day, items)
    ordered = sorted(
        overdue,
        key=lambda item: (
            0 if _possibly_forgotten(day, item) else 1,
            item.due_date,
            item.review_id,
        ),
    )
    occupied = _existing_occupancy(day, items)
    updated_by_id, entries, unschedulable = _assign_overdue_items(
        day, config, items, ordered, availability, route, timetable,
        pacing_initial, occupied,
    )
    entries.sort(key=lambda entry: (
        0 if entry.tier == "possible_forgetting" else 1,
        entry.old_due_date,
        entry.review_id,
    ))
    possible_count = sum(entry.tier == "possible_forgetting" for entry in entries)
    assigned_days = [entry.new_due_date for entry in entries]
    return ResumePlan(
        day=day,
        entries=tuple(entries),
        updated_items=tuple(updated_by_id[item.review_id] for item in items),
        possible_forgetting_count=possible_count,
        recent_overdue_count=len(entries) - possible_count,
        last_assigned_day=max(assigned_days) if assigned_days else None,
        unschedulable_review_ids=tuple(unschedulable),
        scheduled_to_queued_count=sum(item.state == "scheduled" for item in overdue),
    )


def _assign_overdue_items(
    day: date,
    config: KaoyanConfig,
    items: Sequence[ReviewItem],
    ordered: Sequence[ReviewItem],
    availability: Availability | None,
    route: RoutePlan | None,
    timetable: DerivedDailyMinutes | None,
    pacing_initial: PacingInitial | None,
    occupied: dict[date, dict[str, int] | int],
) -> tuple[dict[str, ReviewItem], list[ResumeEntry], list[str]]:
    remaining: dict[date, dict[str, int] | int] = {}
    updated_by_id = {item.review_id: item for item in items}
    entries: list[ResumeEntry] = []
    unschedulable: list[str] = []
    for item in ordered:
        forgotten = _possibly_forgotten(day, item)
        schedule = reset_for_relearning(item.schedule) if forgotten else item.schedule
        assigned = _first_fit_day(
            day, item, config, availability, route, timetable, pacing_initial,
            occupied, remaining,
        )
        if assigned is None:
            assigned = day
            unschedulable.append(item.review_id)
        current = replace(
            item, state="queued", due_date=assigned, defer_count=0, schedule=schedule,
        )
        assert current.schedule.interval_days <= item.schedule.interval_days
        updated_by_id[item.review_id] = current
        entries.append(ResumeEntry(
            review_id=item.review_id,
            tier="possible_forgetting" if forgotten else "recent_overdue",
            old_due_date=item.due_date,
            new_due_date=assigned,
            reset_for_relearning=forgotten,
        ))
    return updated_by_id, entries, unschedulable


def _possibly_forgotten(day: date, item: ReviewItem) -> bool:
    """D11 tier: overdue for longer than the item's own spacing interval."""
    return (day - item.due_date).days > item.schedule.interval_days


def _existing_occupancy(
    day: date, items: Sequence[ReviewItem],
) -> dict[date, dict[str, int] | int]:
    occupied: dict[date, dict[str, int] | int] = {}
    for item in items:
        if item.state != "queued" or item.due_date < day:
            continue
        by_subject = occupied.setdefault(item.due_date, {})
        assert isinstance(by_subject, dict)
        by_subject[item.subject_id] = by_subject.get(item.subject_id, 0) + item.estimated_minutes
    return occupied


def _capacity_for_day(
    day: date,
    config: KaoyanConfig,
    availability: Availability | None,
    route: RoutePlan | None,
    timetable: DerivedDailyMinutes | None,
    pacing_initial: PacingInitial | None,
    occupied: Mapping[date, dict[str, int] | int],
) -> dict[str, int] | int:
    budget = resolve_day_budget(
        day, config, availability, route, timetable, pacing_initial=pacing_initial,
    )
    used = occupied.get(day, {})
    if budget.subject_review_quotas is not None:
        assert isinstance(used, dict)
        return {
            subject_id: max(0, quota - used.get(subject_id, 0))
            for subject_id, quota in budget.subject_review_quotas.items()
        }
    soft_capacity = scale_minutes(budget.total_minutes, config.review_reserve_ratio)
    assert isinstance(used, dict)
    return max(0, soft_capacity - sum(used.values()))


def _first_fit_day(
    start: date,
    item: ReviewItem,
    config: KaoyanConfig,
    availability: Availability | None,
    route: RoutePlan | None,
    timetable: DerivedDailyMinutes | None,
    pacing_initial: PacingInitial | None,
    occupied: Mapping[date, dict[str, int] | int],
    remaining: dict[date, dict[str, int] | int],
) -> date | None:
    for offset in range(_SEARCH_DAYS):
        candidate = start + timedelta(days=offset)
        if candidate not in remaining:
            remaining[candidate] = _capacity_for_day(
                candidate, config, availability, route, timetable, pacing_initial, occupied,
            )
        available = remaining[candidate]
        if isinstance(available, dict):
            if available.get(item.subject_id, 0) < item.estimated_minutes:
                continue
            available[item.subject_id] -= item.estimated_minutes
        else:
            if available < item.estimated_minutes:
                continue
            remaining[candidate] = available - item.estimated_minutes
        return candidate
    return None


def resume_plan_to_mapping(plan: ResumePlan) -> dict[str, object]:
    """Return the sole JSON/YAML shape for a resume plan."""
    result = {
        "day": plan.day.isoformat(),
        "items": [
            {
                "review_id": entry.review_id,
                "tier": entry.tier,
                "old_due_date": entry.old_due_date.isoformat(),
                "new_due_date": entry.new_due_date.isoformat(),
                "reset_for_relearning": entry.reset_for_relearning,
            }
            for entry in plan.entries
        ],
        "possible_forgetting_count": plan.possible_forgetting_count,
        "recent_overdue_count": plan.recent_overdue_count,
        "last_assigned_day": (
            plan.last_assigned_day.isoformat() if plan.last_assigned_day else None
        ),
        "unschedulable_review_ids": list(plan.unschedulable_review_ids),
    }
    if plan.scheduled_to_queued_count:
        result["scheduled_to_queued_count"] = plan.scheduled_to_queued_count
    return result
