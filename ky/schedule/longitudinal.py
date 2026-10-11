"""Longitudinal (24-month) planning over multiple independent learning channels.

Design rule this module exists to enforce
-----------------------------------------
The system supplies **inputs and guard-rails, never the numbers**. Every quantity that varies
day to day -- how many minutes are available, how many vocabulary items to introduce, when to
switch from vocabulary to phrase work -- is supplied by the caller (in practice, the agent
handling that study day). Nothing here defaults those to a fixed value or rejects a day for
being larger or smaller than 120 minutes.

What it *does* enforce is a small set of invariants that must hold no matter how the day is
budgeted (see ``GuardResult``). Those five invariants used to be tangled up with a fixed
"120 minutes" constant; the constant is gone, the invariants are not.

Channels
--------
A day is partitioned into independent channels. Vocabulary and knowledge-point review have
different cost models (vocabulary suits batch recall; a knowledge point is an individual task
with its own duration), so they are never merged into one queue. The phrase channel is a
declared extension slot with no material behind it yet -- see ``CHANNEL_PHRASE``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from typing import Mapping

__all__ = [
    "Channel",
    "DayPlan",
    "GuardResult",
    "PlanHorizon",
    "add_calendar_months",
    "check_invariants",
    "enumerate_days",
    "summarise",
]


def add_calendar_months(start: date, months: int) -> date:
    """``start`` shifted forward by ``months`` calendar months, day-of-month clamped.

    This is calendar-aware, not a ``30 * months`` day count: adding 24 calendar months to
    2026-09-15 lands on 2028-09-15 (731 days later, because 2028 is a leap year), not on
    ``start + 720 days``. A day that does not exist in the target month (31 Jan + 1 month)
    clamps to the target month's last day, the same rule ``dateutil.relativedelta`` uses.
    """
    if months < 0:
        raise ValueError(f"months must be >= 0, got {months}")
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start.day, _days_in_month(year, month))
    return date(year, month, day)


def _days_in_month(year: int, month: int) -> int:
    next_month = month % 12 + 1
    next_year = year + (month == 12)
    return (date(next_year, next_month, 1) - date(year, month, 1)).days


class Channel(str, Enum):
    """Independent capacity channels.

    ``VOCAB`` and ``PHRASE`` are grouped as the language track; ``KNOWLEDGE`` carries the
    subject knowledge-point review. They are separate because their per-item cost and their
    acceptable batch size differ by an order of magnitude.
    """

    KNOWLEDGE = "knowledge"
    VOCAB = "vocab"
    PHRASE = "phrase"


CHANNEL_PHRASE = Channel.PHRASE
"""Extension slot for long-sentence / collocation work.

No material is wired behind it yet: the project holds a vocabulary database but no sentence
corpus. The slot exists so that the day plan can already carry it, and so that turning it on
later is a data change rather than a schema change. A day whose phrase allocation is zero is
normal, not an error.
"""


@dataclass(frozen=True)
class PlanHorizon:
    """The planning window: ``months`` real calendar months starting at ``start``.

    ``end`` is the *inclusive* last day of the horizon. It is derived from calendar-month
    arithmetic (:func:`add_calendar_months`), not from ``30 * months`` days -- 24 calendar
    months from 2026-09-15 is 2028-09-15 (exclusive), i.e. 731 days and a last day of
    2028-09-14, not the 721-day/2028-09-04 figure a fixed 30-day month produces.
    """

    start: date
    months: int = 24

    def __post_init__(self) -> None:
        if self.months <= 0:
            raise ValueError(f"months must be >= 1, got {self.months}")

    @property
    def end_exclusive(self) -> date:
        """The first day *after* the horizon (a real calendar-month boundary)."""
        return add_calendar_months(self.start, self.months)

    @property
    def end(self) -> date:
        """The last day *inside* the horizon (inclusive)."""
        return self.end_exclusive - timedelta(days=1)


@dataclass(frozen=True)
class DayPlan:
    """One day's allocation, as decided by the agent handling that day.

    Every field is an input. Nothing is derived from a global constant, so a 40-minute day and
    a 300-minute day are equally valid.
    """

    day: date
    available_minutes: int
    knowledge_minutes: int = 0
    vocab_minutes: int = 0
    vocab_new_items: int = 0
    phrase_minutes: int = 0
    backlog_minutes: int = 0
    subject_minutes: Mapping[str, int] = field(default_factory=dict)
    notes: str = ""

    @property
    def allocated_minutes(self) -> int:
        return self.knowledge_minutes + self.vocab_minutes + self.phrase_minutes

    @property
    def over_capacity(self) -> int:
        """Minutes by which the plan exceeds the day. Zero or negative means it fits."""
        return self.allocated_minutes - self.available_minutes


@dataclass(frozen=True)
class GuardResult:
    """Outcome of the invariant check. ``violations`` empty means the plan is acceptable."""

    violations: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.violations


def enumerate_days(horizon: PlanHorizon) -> tuple[date, ...]:
    """Every date in the horizon, inclusive of start and end."""
    span = (horizon.end - horizon.start).days
    return tuple(horizon.start + timedelta(days=i) for i in range(span + 1))


def _check_weight_closure(
    subject_weights: Mapping[str, float], weight_tolerance: float, violations: list[str]
) -> None:
    if not subject_weights:
        violations.append("no active subjects: subject_weights is empty")
    else:
        total = sum(subject_weights.values())
        if abs(total - 1.0) > weight_tolerance:
            violations.append(
                f"active subject weights sum to {total!r}, expected 1.0 +/- {weight_tolerance}"
            )


def _check_nonnegative_quantities(day: DayPlan, violations: list[str]) -> None:
    for name, value in (
        ("available_minutes", day.available_minutes),
        ("knowledge_minutes", day.knowledge_minutes),
        ("vocab_minutes", day.vocab_minutes),
        ("phrase_minutes", day.phrase_minutes),
        ("vocab_new_items", day.vocab_new_items),
        ("backlog_minutes", day.backlog_minutes),
    ):
        if value < 0:
            violations.append(f"{name} must be non-negative, got {value}")


def _check_subject_attribution(
    day: DayPlan, subject_weights: Mapping[str, float], violations: list[str]
) -> None:
    for subject_id, minutes in day.subject_minutes.items():
        if subject_id not in subject_weights:
            violations.append(
                f"subject_minutes names {subject_id!r}, which is not an active subject"
            )
        elif minutes < 0:
            violations.append(f"subject {subject_id!r} has negative minutes")
    subject_total = sum(day.subject_minutes.values())
    if subject_total != day.knowledge_minutes:
        violations.append(
            f"subject_minutes sums to {subject_total}, which does not match knowledge_minutes "
            f"({day.knowledge_minutes}); every knowledge minute must be attributed to a subject"
        )


def _check_weight_inversions(
    day: DayPlan, subject_weights: Mapping[str, float], violations: list[str]
) -> None:
    if not subject_weights:
        return
    items = [
        (subject, subject_weights[subject], day.subject_minutes.get(subject, 0))
        for subject in subject_weights
    ]
    for index, (left_id, left_weight, left_minutes) in enumerate(items):
        for right_id, right_weight, right_minutes in items[index + 1:]:
            if left_weight > right_weight and left_minutes < right_minutes:
                violations.append(
                    f"inverted allocation: {left_id!r} (weight {left_weight}) got "
                    f"{left_minutes} minutes while {right_id!r} (weight {right_weight}) "
                    f"got {right_minutes}"
                )


def _check_single_item_bounds(
    day: DayPlan, max_single_item_minutes: int | None, violations: list[str]
) -> None:
    if max_single_item_minutes is None:
        return
    for subject_id, minutes in day.subject_minutes.items():
        if minutes > max_single_item_minutes:
            violations.append(
                f"subject {subject_id!r} knowledge allocation {minutes} exceeds the "
                f"single-item bound {max_single_item_minutes}"
            )
    for name, minutes in (("vocab", day.vocab_minutes), ("phrase", day.phrase_minutes)):
        if minutes > max_single_item_minutes:
            violations.append(
                f"{name} allocation {minutes} exceeds the single-item bound "
                f"{max_single_item_minutes}"
            )


def _check_day_capacity(day: DayPlan, violations: list[str]) -> None:
    if day.allocated_minutes > day.available_minutes:
        violations.append(
            f"allocated_minutes ({day.allocated_minutes}) exceeds available_minutes "
            f"({day.available_minutes}); minutes that do not fit belong in backlog_minutes, "
            "not in an allocation excused by a matching backlog figure"
        )


def check_invariants(
    day: DayPlan,
    *,
    subject_weights: dict[str, float],
    weight_tolerance: float = 1e-6,
    max_single_item_minutes: int | None = None,
) -> GuardResult:
    """The invariants that survive the removal of a fixed daily budget.

    1. Every quantity field closes individually: ``available_minutes``, ``knowledge_minutes``,
       ``vocab_minutes``, ``phrase_minutes``, ``vocab_new_items`` and ``backlog_minutes`` must
       each be non-negative on their own -- a negative ``vocab_new_items`` or
       ``backlog_minutes`` used to pass silently because nothing looked at those two fields.
    2. ``day.subject_minutes`` must sum to exactly ``day.knowledge_minutes``. This is the only
       way the guard can see a per-subject breakdown at all, so it is mandatory rather than an
       optional override: a caller that never mentions ``subject_minutes`` cannot smuggle a
       whole day's knowledge allocation past the inversion check by simply omitting it.
    3. No subject's declared share is inverted (a heavier weight never gets fewer minutes than a
       lighter one), checked over every active subject, including ones ``day.subject_minutes``
       silently omits (an omitted subject is 0 minutes, not "not checked").
    4. No single *pass* exceeds ``max_single_item_minutes`` when that bound is supplied. This is
       evaluated per subject inside the knowledge channel (and per vocab/phrase channel total,
       the finest grain available there) -- never against the whole knowledge channel's sum, so
       two 30-minute subject passes sharing a 60-minute knowledge channel are not flagged as one
       60-minute item.
    5. ``allocated_minutes`` (knowledge + vocab + phrase) may never exceed ``available_minutes``.
       A day cannot physically spend more minutes than it has; work that does not fit belongs in
       ``backlog_minutes`` -- as a separate, honestly-reported number -- not inside an
       allocation that is then excused by a matching backlog figure. This mirrors
       ``review_clip.select_daily_reviews``, which never lets ``used`` exceed the hard cap and
       reports what did not fit as ``backlog_minutes`` on the *excluded* items, rather than
       admitting them and declaring the overage as backlog.

    Deliberately NOT checked: whether ``available_minutes`` equals any particular number.
    That check is what this module removed.
    """
    violations: list[str] = []
    _check_weight_closure(subject_weights, weight_tolerance, violations)
    _check_nonnegative_quantities(day, violations)
    _check_subject_attribution(day, subject_weights, violations)
    _check_weight_inversions(day, subject_weights, violations)
    _check_single_item_bounds(day, max_single_item_minutes, violations)
    _check_day_capacity(day, violations)
    return GuardResult(tuple(violations))


@dataclass
class HorizonSummary:
    """Aggregate over a set of day plans. Used for the monthly close."""

    days: int = 0
    days_planned: int = 0
    total_available_minutes: int = 0
    total_allocated_minutes: int = 0
    by_channel: dict[str, int] = field(default_factory=dict)
    vocab_items: int = 0
    overshoot_days: int = 0
    first_phrase_day: date | None = None


def summarise(plans: list[DayPlan]) -> HorizonSummary:
    """Roll a list of day plans up. Days with no plan still count toward ``days`` only if
    passed in; this function does not invent plans for unplanned days."""
    s = HorizonSummary()
    for p in plans:
        s.days += 1
        s.days_planned += 1
        s.total_available_minutes += p.available_minutes
        s.total_allocated_minutes += p.allocated_minutes
        s.by_channel[Channel.KNOWLEDGE.value] = (
            s.by_channel.get(Channel.KNOWLEDGE.value, 0) + p.knowledge_minutes)
        s.by_channel[Channel.VOCAB.value] = (
            s.by_channel.get(Channel.VOCAB.value, 0) + p.vocab_minutes)
        s.by_channel[Channel.PHRASE.value] = (
            s.by_channel.get(Channel.PHRASE.value, 0) + p.phrase_minutes)
        s.vocab_items += p.vocab_new_items
        if p.over_capacity > 0:
            s.overshoot_days += 1
        if p.phrase_minutes > 0 and s.first_phrase_day is None:
            s.first_phrase_day = p.day
    return s
