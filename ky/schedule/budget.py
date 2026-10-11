"""M8 pure daily allocation and D10 budget resolution.

See ``contracts/route_plan.md``, ``contracts/availability.md`` and ``contracts/timetable.md`` §6.
Public interfaces: :class:`DayBudget`, :class:`PacingInitial`, :func:`daily_base_minutes`,
:func:`resolve_day_budget`, :func:`hard_review_cap_minutes`, :func:`allocate_new_content`,
and :func:`idle_minutes`.

Everything here is pure: no file access, no clock, no randomness. The same
inputs always produce the same outputs, which is what makes the daily plan
replayable and auditable.

Allocation policy
-----------------
1. ``min_daily_minutes`` floors are guaranteed first.
2. The **remainder** is split by weight (largest-remainder rounding, so the
   parts always sum back to the whole).

This ordering is deliberate: a declared floor is a promise, while a weight is
a preference. The floor is granted in full and only the *remainder* is split
by weight, so a subject's final minutes are ``floor + weight * (budget -
floor_total)``, never ``weight * budget``. A floor therefore always lifts a
subject above its nominal share, at any budget size -- English's 15-minute
floor is 22.7% of a 66-minute remainder (not 20%), and it is still 35 of 115
minutes (~30.4%, not 20%) once the remainder grows to 100. The floor never
"stops binding"; it just becomes a smaller fraction of an ever-larger total.
``tests/test_contracts.py`` asserts both regimes with their real numbers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from fractions import Fraction
from typing import Literal, Mapping, Protocol

from ky.availability import (
    Availability,
    DailyMinutes,
    DerivedDailyMinutes,
    resolve_daily_minutes,
)
from ky.models import ContractError, KaoyanConfig, scale_minutes
from ky.schedule.planning import RoutePlan

__all__ = [
    "DayBudget",
    "SubjectAllocation",
    "PacingInitial",
    "allocate_new_content",
    "daily_base_minutes",
    "hard_review_cap_minutes",
    "idle_minutes",
    "resolve_day_budget",
]


@dataclass(frozen=True)
class DayBudget:
    """Resolved daily study and phase review budgets (M8, D10)."""

    total_minutes: int
    total_source: Literal["availability", "timetable", "base", "config"]
    subject_review_quotas: Mapping[str, int] | None
    phase_index: int | None
    route_revision: int | None
    # The day's base before timetable deductions; M18 explanations need it, not the total.
    base_minutes: int
    base_source: Literal["route", "pacing_initial", "config"]


class PacingInitial(Protocol):
    """Read-only subset of registered pacing settings needed by M8."""

    @property
    def start(self) -> date: ...

    @property
    def initial(self) -> int: ...


def hard_review_cap_minutes(total_minutes: int, hard_max_ratio: float) -> int:
    """Return M9's daily hard review cap for a resolved total budget."""
    return min(scale_minutes(total_minutes, hard_max_ratio), total_minutes)


def _split_integer_quotas(total: int, quotas: Mapping[str, int]) -> dict[str, int]:
    """Scale integer quotas by exact largest remainders, breaking ties by ID."""
    quota_total = sum(quotas.values())
    if quota_total <= 0:
        return {subject_id: 0 for subject_id in quotas}
    exact = {
        subject_id: Fraction(total * quota, quota_total)
        for subject_id, quota in quotas.items()
    }
    scaled = {
        subject_id: value.numerator // value.denominator
        for subject_id, value in exact.items()
    }
    remainder = total - sum(scaled.values())
    order = sorted(
        quotas,
        key=lambda subject_id: (-(exact[subject_id] - scaled[subject_id]), subject_id),
    )
    for subject_id in order[:remainder]:
        scaled[subject_id] += 1
    return scaled


def daily_base_minutes(
    day: date, config: KaoyanConfig, route: RoutePlan | None,
    pacing_initial: PacingInitial | None = None,
) -> tuple[int, Literal["route", "pacing_initial", "config"]]:
    """Resolve the daily base using route, pacing initial, then exam config."""
    if isinstance(day, datetime) or not isinstance(day, date):
        raise ContractError("expected a date", "day")
    if pacing_initial is not None:
        if isinstance(pacing_initial.start, datetime) or not isinstance(
            pacing_initial.start, date
        ):
            raise ContractError("expected a date", "settings.pacing.start")
        if (
            isinstance(pacing_initial.initial, bool)
            or not isinstance(pacing_initial.initial, int)
            or pacing_initial.initial < 0
        ):
            raise ContractError(
                "expected a non-negative integer", "settings.pacing.initial",
            )
    phase = next(
        (item for item in route.phases if item.start <= day < item.end_exclusive), None,
    ) if route is not None else None
    if phase is not None and phase.base_daily_minutes is not None:
        return phase.base_daily_minutes, "route"
    if pacing_initial is not None and day >= pacing_initial.start:
        return pacing_initial.initial, "pacing_initial"
    return config.default_daily_minutes, "config"


def resolve_day_budget(
    day: date,
    config: KaoyanConfig,
    availability: Availability | None,
    route: RoutePlan | None,
    timetable: DerivedDailyMinutes | None = None,
    *, pacing_initial: PacingInitial | None = None,
) -> DayBudget:
    """Resolve M26 total minutes and the matching D10 phase review quotas."""
    base_minutes, base_source = daily_base_minutes(day, config, route, pacing_initial)
    daily: DailyMinutes = resolve_daily_minutes(
        day, base_minutes, availability, timetable
    )
    total_source = daily.source
    if total_source == "config" and base_source != "config":
        total_source = "base"
    phase = next(
        (phase for phase in route.phases if phase.start <= day < phase.end_exclusive),
        None,
    ) if route is not None else None
    if phase is None:
        return DayBudget(
            daily.minutes, total_source, None, None, None, base_minutes, base_source,
        )

    active = {subject.subject_id for subject in config.active_subjects()}
    configured = {subject.subject_id for subject in config.subjects}
    for subject_id in phase.review_minutes:
        path = f"route.phases[{phase.index}].review_minutes.{subject_id}"
        if subject_id not in configured:
            raise ContractError("未知的配置科目 ID", path)
        if subject_id not in active and phase.review_minutes[subject_id] > 0:
            raise ContractError(
                "请先在配置中启用该科目，再设置复习分钟", path,
            )
    for subject_id in sorted(active):
        if subject_id not in phase.review_minutes:
            raise ContractError(
                f"时间线阶段 {phase.index} 缺少在考科目 {subject_id} 的复习分钟",
                f"route.phases[{phase.index}].review_minutes.{subject_id}",
            )

    quotas = {
        subject_id: phase.review_minutes[subject_id]
        for subject_id in sorted(active)
    }
    hard_cap = hard_review_cap_minutes(daily.minutes, config.hard_max_ratio)
    if sum(quotas.values()) > hard_cap:
        quotas = _split_integer_quotas(hard_cap, quotas)
    return DayBudget(
        daily.minutes, total_source, quotas, phase.index, route.revision, base_minutes,
        base_source,
    )


@dataclass(frozen=True)
class SubjectAllocation:
    """One subject's share of the day's *new content* minutes."""

    subject_id: str
    display_name: str
    minutes: int
    weight: float
    floor_minutes: int = 0

    @property
    def floor_binding(self) -> bool:
        return self.floor_minutes > 0 and self.minutes == self.floor_minutes


def _proportional_split(minutes: int, weights: dict[str, float]) -> dict[str, int]:
    """Largest-remainder split of ``minutes`` across ``weights``.

    The result sums to ``minutes`` exactly, for any ``minutes`` and any
    combination of legal weights -- ties break on subject_id so the result
    never depends on dictionary insertion order.

    This uses exact rational arithmetic (``fractions.Fraction``) instead of
    binary floats. A binary float has 53 bits of mantissa, so
    ``minutes * weight`` silently loses precision once ``minutes`` is large
    (budgets around ``10**17`` and up); the resulting per-subject rounding
    error can exceed a single minute, which the old "claw back one minute
    per subject" leftover recovery could not fully undo. Rebuilding each
    weight as ``Fraction(str(weight))`` reconstructs the exact decimal the
    config author typed (not its binary approximation), and every following
    operation (normalising, multiplying by ``minutes``, flooring) stays
    exact, so the floor/remainder decomposition below is exact for
    arbitrarily large ``minutes``.

    ``validate_config`` accepts active weights that sum to ``1.0 +/-
    WEIGHT_TOLERANCE``, not exactly 1.0. Weights are normalised here (as
    exact fractions) so that residual drift (for example a declared sum of
    1.0000009) cannot leave the total off by more than the largest-remainder
    rounding already accounts for.

    With exact arithmetic, ``sum(raw.values()) == minutes`` exactly (because
    the normalised weights sum to exactly 1), so
    ``leftover = minutes - sum(floor(raw))`` is always in
    ``[0, len(weights))`` -- it can never go negative, so there is no
    separate "claw back" branch to get wrong.
    """
    if minutes <= 0 or not weights:
        return {key: 0 for key in weights}

    exact_weights = {key: Fraction(str(weight)) for key, weight in weights.items()}
    total_weight = sum(exact_weights.values())
    normalized = {key: weight / total_weight for key, weight in exact_weights.items()}

    raw = {key: minutes * weight for key, weight in normalized.items()}
    granted = {key: value.numerator // value.denominator for key, value in raw.items()}
    fractional = {key: value - granted[key] for key, value in raw.items()}
    leftover = minutes - sum(granted.values())

    # Internal invariant, not a business-input error: for validated positive
    # weights summing to 1 the leftover is provably in [0, len(weights)).
    # Raised explicitly rather than via ``assert`` so it survives ``python -O``
    # and stays diagnosable if the allocator is ever refactored.
    if not 0 <= leftover < len(weights):
        raise RuntimeError(
            f"internal exact-rational invariant violated: leftover={leftover}, "
            f"subjects={len(weights)}"
        )

    order = sorted(weights, key=lambda key: (-fractional[key], key))
    for key in order[:leftover]:
        granted[key] += 1

    return granted


def allocate_new_content(
    config: KaoyanConfig,
    new_content_minutes: int,
    *,
    floor_policy: Literal["strict", "drop_when_short"] = "strict",
) -> tuple[SubjectAllocation, ...]:
    """Split ``new_content_minutes`` across active subjects.

    With ``floor_policy="strict"`` (the default), raises ``ValueError`` when
    the configured floors cannot all be satisfied, because silently dropping
    a floor would hide a mis-specified config.
    """
    if floor_policy not in ("strict", "drop_when_short"):
        raise ValueError(f"unsupported floor_policy: {floor_policy!r}")
    if new_content_minutes < 0:
        raise ValueError(f"new_content_minutes must be >= 0, got {new_content_minutes}")

    active = config.active_subjects()
    if not active:
        raise ValueError("config has no active subjects")

    floors = {subject.subject_id: subject.min_daily_minutes for subject in active}
    weights = {subject.subject_id: subject.weight for subject in active}

    floor_total = sum(floors.values())
    if floor_total > new_content_minutes:
        if floor_policy == "strict":
            raise ValueError(
                f"min_daily_minutes sum ({floor_total}) exceeds the new-content budget "
                f"({new_content_minutes}); lower the floors or raise the budget"
            )
        floors = {subject.subject_id: 0 for subject in active}
        floor_total = 0

    remainder = new_content_minutes - floor_total
    extra = _proportional_split(remainder, weights) if remainder > 0 else {k: 0 for k in floors}

    return tuple(
        SubjectAllocation(
            subject_id=subject.subject_id,
            display_name=subject.display_name,
            minutes=floors[subject.subject_id] + extra[subject.subject_id],
            weight=subject.weight,
            floor_minutes=floors[subject.subject_id],
        )
        for subject in active
    )


def idle_minutes(config: KaoyanConfig, new_content_minutes: int) -> int:
    """Minutes left over after allocating new content to every active subject.

    Should always be zero; a non-zero value would mean the allocator leaked
    budget and callers must surface it rather than pocket it.
    """
    allocated = sum(
        allocation.minutes for allocation in allocate_new_content(config, new_content_minutes)
    )
    return new_content_minutes - allocated
