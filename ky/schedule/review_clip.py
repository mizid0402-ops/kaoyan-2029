"""M9 deterministic review selection and capacity clipping.

See ``contracts/review_clip.md`` and ``contracts/route_plan.md``.
Public interfaces: :class:`ClipResult`,
:func:`select_daily_reviews`, and :func:`preflight_to_mapping`.

This is the module that decides, out of every review item that is due today,
which ones actually fit inside one day's 120-minute budget.

Design rules (see docs/评审结论与实施契约.md §4.1 and §6.2):

* The selector is pure and deterministic: no clock, no randomness, no IO.
  Replaying the same day with the same inputs yields byte-identical output.
* A deferred item keeps its original ``due_date``. Only ``defer_count``
  advances, so the growing overdue age itself raises the item's priority on a
  later day. Nothing is silently rescheduled and no audit entry is needed.
* Reviews may borrow up to a hard cap only for *urgent* items; the soft quota
  is the normal target. The gap between the two is what keeps one bad week
  from consuming the next week's new content.
* Self-report never changes ``due_date``, interval, or quality. At most it
  breaks a tie between two otherwise identical items.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from fractions import Fraction
from typing import Mapping, Sequence

from ky.models import (
    ContractError,
    KaoyanConfig,
    ReviewItem,
    scale_minutes,
    validate_items_against_config,
)
from ky.schedule.budget import SubjectAllocation, hard_review_cap_minutes

__all__ = [
    "ReviewPolicy",
    "ClipResult",
    "select_daily_reviews",
    "preflight_to_mapping",
]

# Lower rank means selected earlier when overdue age, defer count, lapses and
# subject deficit are all identical -- this is the fifth of eight tie-break
# levels, so it rarely decides the outcome on its own. Core academic units
# (concept/procedure, then question_pattern) outrank error-pattern drills and
# batched vocabulary, which are narrower, single-purpose passes.
ITEM_TYPE_PRIORITY: dict[str, int] = {
    "concept": 0,
    "procedure": 0,
    "question_pattern": 1,
    "error_pattern": 2,
    "vocabulary_batch": 3,
}

# Self-report tie-break: an item the learner already feels fluent in yields to
# one they do not, but only when everything ranked above is identical.
SELF_RATING_TIEBREAK: dict[str, int] = {
    "unknown": 0,
    "vague": 1,
    "basic": 2,
    "fluent": 3,
}
_DEFAULT_SELF_TIEBREAK = 4


@dataclass(frozen=True)
class ReviewPolicy:
    """Thresholds that decide when a deferred item becomes urgent."""

    urgent_overdue_days: int = 3
    urgent_defer_count: int = 2

    def __post_init__(self) -> None:
        if self.urgent_overdue_days < 1:
            raise ValueError("urgent_overdue_days must be >= 1")
        if self.urgent_defer_count < 1:
            raise ValueError("urgent_defer_count must be >= 1")


@dataclass(frozen=True)
class ClipResult:
    """Outcome of one day's review clipping.

    Every non-retired item handed to the selector must appear in exactly one
    of ``selected`` / ``deferred`` / ``unschedulable`` / ``scheduled_ahead`` /
    ``unreachable``. ``visible_ids`` exposes that union so the invariant can be
    asserted instead of trusted; a declared-valid state that silently fell out
    of every bucket is exactly the class of defect this guards against.
    """

    today: date
    selected: tuple[ReviewItem, ...]
    deferred: tuple[ReviewItem, ...]
    review_minutes: int
    new_learning_minutes: int
    soft_target_minutes: int
    hard_cap_minutes: int
    backlog_minutes: int
    over_capacity: bool
    unschedulable: tuple[ReviewItem, ...]
    scheduled_ahead: tuple[ReviewItem, ...] = ()
    unreachable: tuple[ReviewItem, ...] = ()
    subject_review_quotas: Mapping[str, int] | None = None
    subject_review_minutes: Mapping[str, int] | None = None

    @property
    def selected_ids(self) -> tuple[str, ...]:
        return tuple(item.review_id for item in self.selected)

    @property
    def deferred_ids(self) -> tuple[str, ...]:
        return tuple(item.review_id for item in self.deferred)

    @property
    def scheduled_ahead_ids(self) -> tuple[str, ...]:
        return tuple(item.review_id for item in self.scheduled_ahead)

    @property
    def unreachable_ids(self) -> tuple[str, ...]:
        return tuple(item.review_id for item in self.unreachable)

    @property
    def visible_ids(self) -> tuple[str, ...]:
        """Every item this result accounts for, in a stable order."""
        return (
            self.selected_ids
            + self.deferred_ids
            + tuple(item.review_id for item in self.unschedulable)
            + self.scheduled_ahead_ids
            + self.unreachable_ids
        )

    def summary(self) -> dict[str, object]:
        """Stable, JSON-serialisable summary used by the preflight command."""

        def describe(item: ReviewItem) -> dict[str, object]:
            return {
                "review_id": item.review_id,
                "subject_id": item.subject_id,
                "estimated_minutes": item.estimated_minutes,
                "overdue_days": item.overdue_days(self.today),
                "defer_count": item.defer_count,
                "state": item.state,
            }

        payload = {
            "date": self.today.isoformat(),
            "selected": [describe(item) for item in self.selected],
            "deferred": [describe(item) for item in self.deferred],
            "unschedulable": [item.review_id for item in self.unschedulable],
            "scheduled_ahead": [describe(item) for item in self.scheduled_ahead],
            "unreachable": [describe(item) for item in self.unreachable],
            "review_minutes": self.review_minutes,
            "new_learning_minutes": self.new_learning_minutes,
            "soft_target_minutes": self.soft_target_minutes,
            "hard_cap_minutes": self.hard_cap_minutes,
            "backlog_minutes": self.backlog_minutes,
            "over_capacity": self.over_capacity,
        }
        if self.subject_review_quotas is not None:
            payload["subject_review_quotas"] = dict(self.subject_review_quotas)
            payload["subject_review_minutes"] = dict(self.subject_review_minutes or {})
        return payload


def preflight_to_mapping(
    config: KaoyanConfig,
    result: ClipResult,
    allocations: Sequence[SubjectAllocation],
) -> dict[str, object]:
    """Return the shared JSON payload used by ``ky preflight --json`` and M19."""
    payload = result.summary()
    payload["subject_allocation"] = [
        {
            "subject_id": allocation.subject_id,
            "display_name": allocation.display_name,
            "weight": allocation.weight,
            "new_content_minutes": allocation.minutes,
        }
        for allocation in allocations
    ]
    payload["config"] = {
        "project_id": config.project_id,
        "default_daily_minutes": config.default_daily_minutes,
        "review_reserve_ratio": config.review_reserve_ratio,
        "hard_max_ratio": config.hard_max_ratio,
    }
    return payload


def _deficit_ratio(
    subject_id: str, seven_day_usage: dict[str, int], config: KaoyanConfig
) -> Fraction:
    """How far behind this subject is over the recent window.

    Returns ``(target - actual) / target`` over a seven-day window, where
    positive means under target. A zero target yields 0 so the sort key
    stays total and deterministic.

    The result is an exact ``Fraction`` and is deliberately **never** narrowed
    to ``float``. The sort key only needs this value to be orderable, and a
    ``float`` cannot represent the whole domain the contract accepts:

    * the float form ``weight * default_daily_minutes * 7`` overflows for
      ``total`` beyond ~1e308, and an ``inf`` target would quietly corrupt the
      priority order rather than fail;
    * converting the *ratio* back to float does not escape that either. The
      contract puts no upper bound on ``seven_day_usage`` any more than it does
      on ``default_daily_minutes``, and ``float(Fraction)`` raises
      ``OverflowError`` once ``actual / target`` passes ~1e308 -- which used to
      escape ``py -m ky preflight --usage ...`` as an uncaught traceback rather
      than one of the documented exit codes.

    Staying in ``Fraction`` also keeps the tie-break exact: no two subjects can
    be collapsed into one rank by float rounding.

    ``subject_id`` is guaranteed to exist by the
    ``validate_items_against_config`` call at the top of
    ``select_daily_reviews``, so an unknown subject here would be a real
    programming error and must raise, not be swallowed into "no opinion".
    """
    weight = config.subject(subject_id).weight
    target = Fraction(str(weight)) * config.default_daily_minutes * 7
    if target <= 0:
        return Fraction(0)
    actual = seven_day_usage.get(subject_id, 0)
    return (target - actual) / target


def _is_urgent(item: ReviewItem, today: date, policy: ReviewPolicy) -> bool:
    if item.overdue_days(today) >= policy.urgent_overdue_days:
        return True
    return item.defer_count >= policy.urgent_defer_count


def _sort_key(
    item: ReviewItem,
    today: date,
    config: KaoyanConfig,
    seven_day_usage: dict[str, int],
) -> tuple[object, ...]:
    """Total order over due items. Ascending sort = highest priority first."""
    return (
        -item.overdue_days(today),
        -item.defer_count,
        -item.schedule.lapses,
        -_deficit_ratio(item.subject_id, seven_day_usage, config),
        item.due_date,
        ITEM_TYPE_PRIORITY.get(item.granularity, 99),
        SELF_RATING_TIEBREAK.get(item.last_self_rating or "", _DEFAULT_SELF_TIEBREAK),
        item.review_id,
    )


def _select_subject_quota_pass(
    ordered: Sequence[ReviewItem],
    urgent_ids: set[str],
    quotas: Mapping[str, int],
    hard_cap: int,
    selected: list[ReviewItem],
    deferred: list[ReviewItem],
    subject_used: dict[str, int],
) -> tuple[list[ReviewItem], int]:
    waiting_urgent: list[ReviewItem] = []
    used = 0
    for item in ordered:
        cost = item.estimated_minutes
        in_quota = subject_used.get(item.subject_id, 0) + cost <= quotas.get(item.subject_id, 0)
        if in_quota and used + cost <= hard_cap:
            selected.append(item)
            used += cost
            subject_used[item.subject_id] = subject_used.get(item.subject_id, 0) + cost
        elif item.review_id in urgent_ids:
            waiting_urgent.append(item)
        else:
            deferred.append(item)
    return waiting_urgent, used


def _select_urgent_quota_overflow(
    waiting_urgent: list[ReviewItem],
    hard_cap: int,
    selected: list[ReviewItem],
    deferred: list[ReviewItem],
    subject_used: dict[str, int],
    used: int,
) -> int:
    for item in waiting_urgent:
        cost = item.estimated_minutes
        if used + cost <= hard_cap:
            selected.append(item)
            used += cost
            subject_used[item.subject_id] = subject_used.get(item.subject_id, 0) + cost
        else:
            deferred.append(item)
    return used


def _select_with_subject_quotas(
    ranked: list[ReviewItem],
    quotas: Mapping[str, int],
    *,
    hard_cap: int,
    unschedulable_cap: int,
    today: date,
    policy: ReviewPolicy,
) -> tuple[list[ReviewItem], list[ReviewItem], list[ReviewItem], dict[str, int]]:
    """Select urgent in-quota work first, then borrow unused capacity for urgent work."""
    rank = {item.review_id: index for index, item in enumerate(ranked)}
    subject_used = {subject_id: 0 for subject_id in quotas}
    selected: list[ReviewItem] = []
    unschedulable: list[ReviewItem] = []
    deferred: list[ReviewItem] = []
    schedulable = []
    for item in ranked:
        if item.estimated_minutes > unschedulable_cap:
            unschedulable.append(item)
        else:
            schedulable.append(item)
    urgent_ids = {item.review_id for item in schedulable if _is_urgent(item, today, policy)}
    urgent = [item for item in schedulable if item.review_id in urgent_ids]
    regular = [item for item in schedulable if item.review_id not in urgent_ids]
    waiting_urgent, used = _select_subject_quota_pass(
        (*urgent, *regular), urgent_ids, quotas, hard_cap,
        selected, deferred, subject_used,
    )
    used = _select_urgent_quota_overflow(
        waiting_urgent, hard_cap, selected, deferred, subject_used, used
    )
    selected.sort(key=lambda item: rank[item.review_id])
    deferred.sort(key=lambda item: rank[item.review_id])
    return selected, deferred, unschedulable, subject_used


def _validate_subject_review_quotas(
    config: KaoyanConfig, quotas: Mapping[str, int] | None
) -> None:
    # Validate before capacity arithmetic so bad values keep their contract path (sol 114).
    if quotas is None:
        return
    active_subject_ids = {subject.subject_id for subject in config.active_subjects()}
    for subject_id, minutes in quotas.items():
        path = f"subject_review_quotas.{subject_id}"
        if subject_id not in active_subject_ids:
            raise ContractError("unknown or inactive subject ID", path)
        if type(minutes) is not int or minutes < 0:
            raise ContractError("minutes must be a non-negative integer", path)


def _daily_review_capacity(
    config: KaoyanConfig, total: int, quotas: Mapping[str, int] | None
) -> tuple[int, int, int]:
    soft_target = scale_minutes(total, config.review_reserve_ratio)
    hard_cap = hard_review_cap_minutes(total, config.hard_max_ratio)
    if quotas is not None:
        soft_target = sum(quotas.values())
        if soft_target > hard_cap:
            raise ContractError(
                f"subject review quotas sum to {soft_target}, above the day's hard cap "
                f"{hard_cap}; pass quotas resolved by resolve_day_budget",
                "subject_review_quotas",
            )
    return soft_target, hard_cap, max(config.review_hard_cap_minutes(), hard_cap)


def _select_without_subject_quotas(
    ranked: list[ReviewItem],
    *,
    soft_target: int,
    hard_cap: int,
    unschedulable_cap: int,
    today: date,
    policy: ReviewPolicy,
) -> tuple[list[ReviewItem], list[ReviewItem], list[ReviewItem], int]:
    selected: list[ReviewItem] = []
    deferred: list[ReviewItem] = []
    unschedulable: list[ReviewItem] = []
    used = 0
    for item in ranked:
        cost = item.estimated_minutes
        if cost > unschedulable_cap:
            unschedulable.append(item)
            continue
        if used + cost > hard_cap:
            deferred.append(item)
            continue
        if used + cost > soft_target and not _is_urgent(item, today, policy):
            deferred.append(item)
            continue
        selected.append(item)
        used += cost
    return selected, deferred, unschedulable, used


def _classify_scheduled_reviews(
    items: Sequence[ReviewItem], today: date
) -> tuple[list[ReviewItem], list[ReviewItem]]:
    scheduled_ahead: list[ReviewItem] = []
    unreachable: list[ReviewItem] = []
    for item in items:
        if item.state == "scheduled":
            if item.due_date > today:
                scheduled_ahead.append(item)
            else:
                unreachable.append(item)
    return scheduled_ahead, unreachable


def _build_clip_result(
    today: date,
    selected: list[ReviewItem],
    deferred: list[ReviewItem],
    unschedulable: list[ReviewItem],
    scheduled_ahead: list[ReviewItem],
    unreachable: list[ReviewItem],
    used: int,
    total: int,
    soft_target: int,
    hard_cap: int,
    backlog_minutes: int,
    quotas: Mapping[str, int] | None,
    subject_used: dict[str, int],
) -> ClipResult:
    return ClipResult(
        today=today,
        selected=tuple(selected),
        deferred=tuple(item.with_deferral() for item in deferred),
        review_minutes=used,
        new_learning_minutes=total - used,
        soft_target_minutes=soft_target,
        hard_cap_minutes=hard_cap,
        backlog_minutes=backlog_minutes,
        over_capacity=bool(deferred or unschedulable or unreachable),
        unschedulable=tuple(unschedulable),
        scheduled_ahead=tuple(scheduled_ahead),
        unreachable=tuple(unreachable),
        subject_review_quotas=(dict(quotas) if quotas is not None else None),
        subject_review_minutes=(subject_used if quotas is not None else None),
    )


def _assert_review_accounting(items: Sequence[ReviewItem], today: date, result: ClipResult) -> None:
    # Queued future work is absent by design; every due or scheduled item must be accounted for.
    expected = {item.review_id for item in items if item.state in ("scheduled",)} | {
        item.review_id for item in items if item.is_due(today)
    }
    accounted = set(result.visible_ids)
    missing = expected - accounted
    if missing:  # pragma: no cover - guards a future state added to the enum
        raise AssertionError(
            "review items silently dropped from every output bucket: "
            f"{sorted(missing)}; add the state to the selector's classification"
        )


def select_daily_reviews(
    config: KaoyanConfig,
    items: tuple[ReviewItem, ...] | list[ReviewItem],
    today: date,
    *,
    seven_day_usage: dict[str, int] | None = None,
    policy: ReviewPolicy | None = None,
    daily_minutes_override: int | None = None,
    subject_review_quotas: Mapping[str, int] | None = None,
) -> ClipResult:
    """Choose due reviews under capacity and account for all visible items."""
    validate_items_against_config(config, items)
    usage = dict(seven_day_usage or {})
    active_policy = policy or ReviewPolicy()
    if daily_minutes_override is not None and daily_minutes_override < 0:
        raise ValueError(
            f"daily_minutes_override must be >= 0, got {daily_minutes_override}"
        )
    total = (
        config.default_daily_minutes
        if daily_minutes_override is None else daily_minutes_override
    )
    _validate_subject_review_quotas(config, subject_review_quotas)
    soft_target, hard_cap, unschedulable_cap = _daily_review_capacity(
        config, total, subject_review_quotas
    )
    due = [item for item in items if item.is_due(today)]
    ranked = sorted(due, key=lambda item: _sort_key(item, today, config, usage))
    subject_used: dict[str, int] = {}
    if subject_review_quotas is not None:
        selected, deferred, unschedulable, subject_used = _select_with_subject_quotas(
            ranked, subject_review_quotas, hard_cap=hard_cap,
            unschedulable_cap=unschedulable_cap, today=today, policy=active_policy,
        )
        used = sum(item.estimated_minutes for item in selected)
    else:
        selected, deferred, unschedulable, used = _select_without_subject_quotas(
            ranked, soft_target=soft_target, hard_cap=hard_cap,
            unschedulable_cap=unschedulable_cap, today=today, policy=active_policy,
        )
    scheduled_ahead, unreachable = _classify_scheduled_reviews(items, today)
    backlog_minutes = sum(item.estimated_minutes for item in deferred)
    if used > hard_cap:  # pragma: no cover - defensive, the loop already caps
        raise AssertionError("review selection exceeded the hard cap")
    result = _build_clip_result(
        today, selected, deferred, unschedulable, scheduled_ahead, unreachable,
        used, total, soft_target, hard_cap, backlog_minutes, subject_review_quotas,
        subject_used,
    )
    _assert_review_accounting(items, today, result)
    return result
