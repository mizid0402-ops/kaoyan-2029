"""Monthly close: observe what a month actually did, and carry the residue forward honestly.

Design stance
-------------
Consistent with the rest of stage 2, this module **reports, it does not prescribe**. It does not
decide how many minutes next month should have, how many words to introduce, or what to drop.
Those remain the caller's decisions. What it does is make the month's outcome legible and stop
residue from disappearing: unused time, overshoot, and unfinished backlog are all carried as
explicit numbers rather than being quietly absorbed into the next month.

The one thing it refuses to do is invent compensating numbers. If a month under-ran, the next
month's capacity is whatever the caller says it is -- this module will not "make up" the deficit
by silently inflating a budget, exactly as the review scheduler will not borrow future time.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Sequence

from ky.schedule.completion import CompletionEvent
from ky.schedule.longitudinal import Channel, DayPlan, check_invariants

__all__ = ["MonthClose", "close_month", "month_bounds"]


def month_bounds(year: int, month: int) -> tuple[date, date]:
    """First and last day of a calendar month, without importing a calendar library."""
    if not 1 <= month <= 12:
        raise ValueError(f"month must be 1..12, got {month}")
    first = date(year, month, 1)
    last = date(year + (month == 12), (month % 12) + 1, 1)
    return first, last.fromordinal(last.toordinal() - 1)


@dataclass
class MonthClose:
    """A month's observed outcome plus the residue carried into the next one."""

    year: int
    month: int
    first_day: date
    last_day: date

    days_in_month: int = 0
    days_planned: int = 0
    days_unplanned: int = 0

    available_minutes: int = 0
    allocated_minutes: int = 0
    by_channel: dict[str, int] = field(default_factory=dict)

    vocab_items_introduced: int = 0
    overshoot_days: int = 0
    overshoot_minutes: int = 0

    # residue: explicit, never silently absorbed
    unused_minutes: int = 0
    backlog_minutes: int = 0
    backlog_days: int = 0

    # -- actual outcomes, from CompletionEvent -----------------------------------------------
    # ``actual_data_available`` is False whenever the caller did not pass ``completions`` to
    # close_month() at all (every pre-existing call site). This is deliberately distinct from
    # "we looked and zero happened": a month with zero completion events but
    # ``actual_data_available=True`` really did have zero reviews/vocab activity recorded; a
    # month with ``actual_data_available=False`` was simply never asked about. Collapsing those
    # two into a bare ``0`` would misreport "no data" as "confirmed zero completed".
    actual_data_available: bool = False
    days_with_completion_events: int = 0
    actual_reviews_completed: int | None = None
    # Delivered vs. practiced are kept as two separate counts on purpose (round-37 §6): a
    # delivered word is one the learner was shown, a practiced word is one they engaged with --
    # summing them would silently claim practice for words that were only ever displayed.
    actual_vocab_delivered_words: int | None = None
    actual_vocab_practiced_words: int | None = None
    # actual_vocab_delivered_words minus vocab_items_introduced (the plan's count of *new*
    # words). Not a strict apples-to-apples count -- delivered_words can include previously
    # introduced words shown again for review, while vocab_items_introduced only counts new
    # introductions -- so treat this as a rough plan-vs-actual signal, not an exact reconciliation.
    vocab_delivered_vs_planned: int | None = None

    violations: tuple[str, ...] = ()
    notes: list[str] = field(default_factory=list)

    @property
    def utilisation(self) -> float:
        (
            "Allocated as a fraction of available. "
            "Zero available reports 0.0, not a division error."
        )
        if self.available_minutes <= 0:
            return 0.0
        return self.allocated_minutes / self.available_minutes

    @property
    def ok(self) -> bool:
        return not self.violations


def _deduplicate_month_plans(
    in_month: list[DayPlan],
) -> tuple[list[DayPlan], list[str]]:
    """Count one historical plan per date so duplicate records cannot inflate totals."""
    first_by_day: dict[date, DayPlan] = {}
    duplicate_counts: defaultdict[date, int] = defaultdict(int)
    for plan in in_month:
        if plan.day in first_by_day:
            duplicate_counts[plan.day] += 1
        else:
            first_by_day[plan.day] = plan
    violations = []
    for day, extra_count in sorted(duplicate_counts.items()):
        violations.append(
            f"{day}: {extra_count + 1} day-plan entries supplied for this date; only the "
            "first was counted, the rest were dropped instead of being summed"
        )
    return [first_by_day[day] for day in sorted(first_by_day)], violations


def _accumulate_month_plans(
    mc: MonthClose,
    plans: list[DayPlan],
    subject_weights: dict[str, float],
    max_single_item_minutes: int | None,
    violations: list[str],
) -> None:
    per_channel: defaultdict[str, int] = defaultdict(int)
    for plan in plans:
        mc.available_minutes += plan.available_minutes
        mc.allocated_minutes += plan.allocated_minutes
        per_channel[Channel.KNOWLEDGE.value] += plan.knowledge_minutes
        per_channel[Channel.VOCAB.value] += plan.vocab_minutes
        per_channel[Channel.PHRASE.value] += plan.phrase_minutes
        mc.vocab_items_introduced += plan.vocab_new_items
        over = plan.over_capacity
        if over > 0:
            mc.overshoot_days += 1
            mc.overshoot_minutes += over
        if plan.backlog_minutes > 0:
            mc.backlog_days += 1
            mc.backlog_minutes += plan.backlog_minutes
        result = check_invariants(
            plan, subject_weights=subject_weights,
            max_single_item_minutes=max_single_item_minutes,
        )
        if not result.ok:
            violations.extend(f"{plan.day}: {value}" for value in result.violations)
    mc.by_channel = dict(per_channel)


def _record_month_residue(mc: MonthClose) -> None:
    mc.unused_minutes = max(0, mc.available_minutes - mc.allocated_minutes)
    if mc.overshoot_minutes:
        mc.notes.append(
            f"{mc.overshoot_days} day(s) exceeded their own capacity by "
            f"{mc.overshoot_minutes} minutes in total"
        )
    if mc.backlog_minutes:
        mc.notes.append(
            f"{mc.backlog_minutes} minutes declared as backlog across {mc.backlog_days} day(s); "
            "carried forward, not absorbed"
        )
    if mc.days_unplanned:
        mc.notes.append(f"{mc.days_unplanned} day(s) had no plan and were left as-is")


def _record_month_completions(
    mc: MonthClose,
    first: date,
    last: date,
    completions: Sequence[CompletionEvent],
) -> None:
    in_month = [event for event in completions if first <= event.day <= last]
    mc.actual_data_available = True
    mc.days_with_completion_events = len(in_month)
    reviews_completed = 0
    delivered_words = 0
    practiced_words = 0
    for event in in_month:
        reviews_completed += len(event.reviews)
        delivered_words += len(event.vocab.delivered_words)
        practiced_words += len(event.vocab.practiced_words)
    mc.actual_reviews_completed = reviews_completed
    mc.actual_vocab_delivered_words = delivered_words
    mc.actual_vocab_practiced_words = practiced_words
    mc.vocab_delivered_vs_planned = delivered_words - mc.vocab_items_introduced
    if not in_month:
        mc.notes.append(
            "0 completion events recorded for this month -- a measured zero, not missing data"
        )


def close_month(
    year: int,
    month: int,
    plans: list[DayPlan],
    *,
    subject_weights: dict[str, float],
    max_single_item_minutes: int | None = None,
    completions: Sequence[CompletionEvent] | None = None,
) -> MonthClose:
    """Summarise one month's plans, and -- optionally -- what actually happened.

    ``plans`` are the days actually planned for that month; days with no plan are counted as
    ``days_unplanned`` rather than being filled in with an assumed capacity. An unplanned day is
    information, not an error -- the agent may simply not have run that day.

    ``completions`` is a new, optional, keyword-only parameter (round-37 §6 flagged that closing
    only ever consumed ``DayPlan`` -- "the plan" -- and never the ``CompletionEvent`` record of
    what actually happened; this is that fix). It defaults to ``None`` so every existing call
    site is untouched: passing nothing produces exactly the plan-only report this function has
    always produced, with the new ``actual_*`` fields left at their "not supplied" defaults
    (``actual_data_available=False``, counts ``None``). Passing a (possibly empty) sequence of
    ``CompletionEvent`` opts into the actual-vs-planned report; an empty sequence is a real,
    measured "zero happened", reported as such rather than as "unknown".

    This function still reports; it does not prescribe. No field here (plan-side or actual-side)
    says what next month's capacity or delivery should be.
    """
    first, last = month_bounds(year, month)
    n_days = (last - first).days + 1
    mc = MonthClose(year=year, month=month, first_day=first, last_day=last, days_in_month=n_days)
    in_month = [plan for plan in plans if first <= plan.day <= last]
    deduplicated, violations = _deduplicate_month_plans(in_month)
    mc.days_planned = len(deduplicated)
    mc.days_unplanned = n_days - len(deduplicated)
    _accumulate_month_plans(
        mc, deduplicated, subject_weights, max_single_item_minutes, violations
    )
    _record_month_residue(mc)
    if completions is not None:
        _record_month_completions(mc, first, last, completions)
    mc.violations = tuple(violations)
    return mc
