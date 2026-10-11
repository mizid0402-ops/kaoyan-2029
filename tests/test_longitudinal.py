"""Regression locks for the longitudinal (24-month) planner.

The point of these tests is to freeze the decision that made stage 2 unblockable: the daily
budget is an INPUT, not a constant. If a future change reintroduces a fixed daily total, or lets
an overshoot be absorbed silently, one of these must go red.

The ``TestGuardrailHoles*`` classes below lock the seven holes found in round-37's guard-rail
audit (review/rounds/round-37-stage2-impl-task.md §2): each one reproduces the exact pre-fix
symptom in its docstring and then asserts the fixed behaviour.
"""

from __future__ import annotations

import unittest
from datetime import date

from ky.schedule.longitudinal import (
    Channel,
    DayPlan,
    PlanHorizon,
    add_calendar_months,
    check_invariants,
    enumerate_days,
    summarise,
)

WEIGHTS = {"math1": 0.40, "eng1": 0.20, "cs408": 0.40}


class TestNoFixedDailyBudget(unittest.TestCase):
    """The removal of a hardcoded daily total must stay removed."""

    def test_any_budget_size_is_accepted(self) -> None:
        # 120 is one value among many; nothing about it is special.
        for minutes in (0, 1, 40, 90, 120, 180, 300, 720, 1440):
            with self.subTest(minutes=minutes):
                day = DayPlan(day=date(2026, 9, 15), available_minutes=minutes)
                self.assertTrue(check_invariants(day, subject_weights=WEIGHTS).ok)

    def test_budget_is_not_required_to_be_any_particular_number(self) -> None:
        # A day far from 120 must not be rejected for its size alone.
        day = DayPlan(day=date(2026, 9, 15), available_minutes=37,
                      knowledge_minutes=20, vocab_minutes=17,
                      subject_minutes={"math1": 8, "eng1": 4, "cs408": 8})
        result = check_invariants(day, subject_weights=WEIGHTS)
        self.assertTrue(result.ok, result.violations)

    def test_negative_available_minutes_is_rejected(self) -> None:
        day = DayPlan(day=date(2026, 9, 15), available_minutes=-1)
        self.assertFalse(check_invariants(day, subject_weights=WEIGHTS).ok)


class TestInvariants(unittest.TestCase):
    def test_weights_must_sum_to_one(self) -> None:
        bad = {"math1": 0.40, "eng1": 0.20, "cs408": 0.30}
        result = check_invariants(DayPlan(day=date(2026, 9, 15), available_minutes=120),
                                  subject_weights=bad)
        self.assertFalse(result.ok)
        self.assertTrue(any("sum to" in v for v in result.violations))

    def test_weight_tolerance_is_honoured(self) -> None:
        nearly = {"math1": 0.40, "eng1": 0.20, "cs408": 0.40 + 1e-9}
        result = check_invariants(DayPlan(day=date(2026, 9, 15), available_minutes=120),
                                  subject_weights=nearly)
        self.assertTrue(result.ok, result.violations)

    def test_inverted_allocation_is_rejected(self) -> None:
        day = DayPlan(day=date(2026, 9, 15), available_minutes=120, knowledge_minutes=120,
                      subject_minutes={"math1": 10, "eng1": 50, "cs408": 60})
        result = check_invariants(day, subject_weights=WEIGHTS)
        self.assertFalse(result.ok)
        self.assertTrue(any("inverted" in v for v in result.violations))

    def test_proportional_allocation_is_accepted(self) -> None:
        day = DayPlan(day=date(2026, 9, 15), available_minutes=120, knowledge_minutes=120,
                      subject_minutes={"math1": 48, "eng1": 24, "cs408": 48})
        result = check_invariants(day, subject_weights=WEIGHTS)
        self.assertTrue(result.ok, result.violations)

    def test_unknown_subject_is_rejected(self) -> None:
        day = DayPlan(day=date(2026, 9, 15), available_minutes=120, knowledge_minutes=10,
                      subject_minutes={"politics": 10})
        result = check_invariants(day, subject_weights=WEIGHTS)
        self.assertFalse(result.ok)

    def test_negative_allocation_is_rejected(self) -> None:
        day = DayPlan(day=date(2026, 9, 15), available_minutes=120, vocab_minutes=-1)
        self.assertFalse(check_invariants(day, subject_weights=WEIGHTS).ok)

    def test_single_item_bound(self) -> None:
        day = DayPlan(day=date(2026, 9, 15), available_minutes=120, knowledge_minutes=45,
                      subject_minutes={"math1": 45})
        self.assertFalse(
            check_invariants(day, subject_weights=WEIGHTS, max_single_item_minutes=30).ok)
        day_ok = DayPlan(day=date(2026, 9, 15), available_minutes=120, knowledge_minutes=25,
                          subject_minutes={"math1": 25})
        self.assertTrue(
            check_invariants(day_ok, subject_weights=WEIGHTS, max_single_item_minutes=30).ok)


class TestOvershootMustBeVisible(unittest.TestCase):
    """Overshoot is visible via ``backlog_minutes`` / ``over_capacity`` (see
    ``TestGuardrailHole5NoBacklogBypass`` for what "visible" now means: allocated_minutes must
    still fit inside available_minutes, exactly like ``review_clip.select_daily_reviews`` never
    lets ``used`` exceed the hard cap)."""

    def test_overshoot_without_backlog_is_rejected(self) -> None:
        day = DayPlan(day=date(2026, 9, 15), available_minutes=60,
                      knowledge_minutes=60, vocab_minutes=40)
        result = check_invariants(day, subject_weights=WEIGHTS)
        self.assertFalse(result.ok)
        self.assertTrue(any("backlog" in v for v in result.violations))

    def test_partial_backlog_declaration_is_rejected(self) -> None:
        day = DayPlan(day=date(2026, 9, 15), available_minutes=60,
                      knowledge_minutes=60, vocab_minutes=40, backlog_minutes=10)
        self.assertFalse(check_invariants(day, subject_weights=WEIGHTS).ok)

    def test_fitting_day_needs_no_backlog(self) -> None:
        day = DayPlan(day=date(2026, 9, 15), available_minutes=120,
                      knowledge_minutes=60, vocab_minutes=60,
                      subject_minutes={"math1": 24, "eng1": 12, "cs408": 24})
        self.assertEqual(day.over_capacity, 0)
        self.assertTrue(check_invariants(day, subject_weights=WEIGHTS).ok)


class TestChannels(unittest.TestCase):
    def test_channels_are_distinct(self) -> None:
        self.assertEqual({c.value for c in Channel}, {"knowledge", "vocab", "phrase"})

    def test_phrase_slot_may_be_zero(self) -> None:
        # No phrase material exists yet; a zero phrase allocation is normal.
        day = DayPlan(day=date(2026, 9, 15), available_minutes=120,
                      knowledge_minutes=60, vocab_minutes=60, phrase_minutes=0,
                      subject_minutes={"math1": 24, "eng1": 12, "cs408": 24})
        self.assertTrue(check_invariants(day, subject_weights=WEIGHTS).ok)

    def test_phrase_minutes_are_counted_separately(self) -> None:
        day = DayPlan(day=date(2026, 9, 15), available_minutes=120,
                      knowledge_minutes=60, vocab_minutes=30, phrase_minutes=30)
        self.assertEqual(day.allocated_minutes, 120)


class TestHorizon(unittest.TestCase):
    def test_24_months_is_731_days(self) -> None:
        # 2026-09-15 + 24 calendar months = 2028-09-15 (exclusive); 2028 is a leap year, so
        # the span is 731 days, not the 30-day-month figure of 720/721.
        h = PlanHorizon(start=date(2026, 9, 15), months=24)
        self.assertEqual(h.end_exclusive, date(2028, 9, 15))
        self.assertEqual(h.end, date(2028, 9, 14))
        days = enumerate_days(h)
        self.assertEqual(len(days), 731)
        self.assertEqual(days[0], date(2026, 9, 15))
        self.assertEqual(days[-1], date(2028, 9, 14))

    def test_days_are_consecutive_and_unique(self) -> None:
        days = enumerate_days(PlanHorizon(start=date(2026, 9, 15), months=1))
        self.assertEqual(len(days), len(set(days)))
        for a, b in zip(days, days[1:]):
            self.assertEqual((b - a).days, 1)


class TestSummarise(unittest.TestCase):
    def test_totals_and_first_phrase_day(self) -> None:
        plans = [
            DayPlan(day=date(2026, 9, 15), available_minutes=120,
                    knowledge_minutes=60, vocab_minutes=60, vocab_new_items=20),
            DayPlan(day=date(2026, 9, 16), available_minutes=90,
                    knowledge_minutes=40, vocab_minutes=30, vocab_new_items=15,
                    backlog_minutes=10),
            DayPlan(day=date(2026, 9, 17), available_minutes=150,
                    knowledge_minutes=60, vocab_minutes=40, phrase_minutes=50),
        ]
        s = summarise(plans)
        self.assertEqual(s.days, 3)
        self.assertEqual(s.total_available_minutes, 360)
        self.assertEqual(s.vocab_items, 35)
        self.assertEqual(s.by_channel["phrase"], 50)
        self.assertEqual(s.first_phrase_day, date(2026, 9, 17))
        self.assertEqual(s.overshoot_days, 0)

    def test_empty_summary(self) -> None:
        s = summarise([])
        self.assertEqual(s.days, 0)
        self.assertIsNone(s.first_phrase_day)


# --------------------------------------------------------------------------------------------
# Round-37 guardrail holes: one class per hole in the audit table. Each test reproduces the
# exact pre-fix symptom quoted from review/rounds/round-37-stage2-impl-task.md §2, and mutation
# testing (see the report) proves each is load-bearing by reverting the fix and watching it fail.
# --------------------------------------------------------------------------------------------


class TestGuardrailHole1NegativeVocabNewItems(unittest.TestCase):
    """Hole #1: ``vocab_new_items=-5`` used to return ``ok=True`` because nothing checked it."""

    def test_negative_vocab_new_items_is_rejected(self) -> None:
        day = DayPlan(day=date(2026, 9, 15), available_minutes=120, vocab_new_items=-5)
        result = check_invariants(day, subject_weights=WEIGHTS)
        self.assertFalse(result.ok)
        self.assertTrue(any("vocab_new_items" in v for v in result.violations), result.violations)


class TestGuardrailHole2NegativeBacklogMinutes(unittest.TestCase):
    """Hole #2: ``backlog_minutes=-1`` used to return ``ok=True`` because nothing checked it."""

    def test_negative_backlog_minutes_is_rejected(self) -> None:
        day = DayPlan(day=date(2026, 9, 15), available_minutes=120, backlog_minutes=-1)
        result = check_invariants(day, subject_weights=WEIGHTS)
        self.assertFalse(result.ok)
        self.assertTrue(any("backlog_minutes" in v for v in result.violations), result.violations)


class TestGuardrailHole3SubjectMinutesIsMandatory(unittest.TestCase):
    """Hole #3: with ``subject_weights={"a": 0.90, "b": 0.05, "c": 0.05}`` and no per-subject
    breakdown, the inversion check used to never run at all -- ``ok=True`` regardless of how the
    knowledge channel was actually split. ``subject_minutes`` is no longer an optional override:
    it is read straight off ``DayPlan`` and must reconcile to ``knowledge_minutes``, so a caller
    cannot omit it and skip the check."""

    def test_missing_subject_minutes_is_rejected_when_knowledge_minutes_is_positive(self) -> None:
        skewed = {"a": 0.90, "b": 0.05, "c": 0.05}
        day = DayPlan(day=date(2026, 9, 15), available_minutes=120, knowledge_minutes=60)
        result = check_invariants(day, subject_weights=skewed)
        self.assertFalse(result.ok)
        self.assertTrue(any("knowledge_minutes" in v for v in result.violations), result.violations)

    def test_inversion_is_caught_once_subject_minutes_is_supplied(self) -> None:
        skewed = {"a": 0.90, "b": 0.05, "c": 0.05}
        day = DayPlan(day=date(2026, 9, 15), available_minutes=120, knowledge_minutes=60,
                      subject_minutes={"a": 10, "b": 25, "c": 25})
        result = check_invariants(day, subject_weights=skewed)
        self.assertFalse(result.ok)
        self.assertTrue(any("inverted" in v for v in result.violations), result.violations)


class TestGuardrailHole4PerPassBound(unittest.TestCase):
    """Hole #4: a 60-minute knowledge channel made of two 30-minute subject passes used to be
    compared as one 60-minute item against ``max_single_item_minutes=30`` and rejected, even
    though neither individual pass exceeds the bound."""

    def test_two_bound_sized_passes_sharing_a_channel_are_accepted(self) -> None:
        day = DayPlan(day=date(2026, 9, 15), available_minutes=120, knowledge_minutes=60,
                      subject_minutes={"math1": 30, "cs408": 30})
        result = check_invariants(
            day, subject_weights=WEIGHTS, max_single_item_minutes=30)
        self.assertTrue(result.ok, result.violations)

    def test_a_single_oversized_pass_is_still_rejected(self) -> None:
        day = DayPlan(day=date(2026, 9, 15), available_minutes=120, knowledge_minutes=60,
                      subject_minutes={"math1": 31, "cs408": 29})
        result = check_invariants(
            day, subject_weights=WEIGHTS, max_single_item_minutes=30)
        self.assertFalse(result.ok)
        self.assertTrue(any("math1" in v and "exceeds" in v for v in result.violations),
                         result.violations)


class TestGuardrailHole5NoBacklogBypass(unittest.TestCase):
    """Hole #5: capacity 60, allocation 100, ``backlog_minutes=40`` used to return ``ok=True`` --
    declaring "enough" backlog legalised any amount of overload. ``allocated_minutes`` must now
    fit inside ``available_minutes`` unconditionally; unmet demand is reported through
    ``backlog_minutes`` as a separate figure, not as an excuse for the allocation itself,
    mirroring how ``review_clip.select_daily_reviews`` never lets ``used`` exceed the hard cap."""

    def test_declaring_backlog_does_not_legalise_overallocation(self) -> None:
        day = DayPlan(day=date(2026, 9, 15), available_minutes=60,
                      knowledge_minutes=100, backlog_minutes=40,
                      subject_minutes={"math1": 40, "eng1": 20, "cs408": 40})
        result = check_invariants(day, subject_weights=WEIGHTS)
        self.assertFalse(result.ok)
        self.assertTrue(any("exceeds available_minutes" in v for v in result.violations),
                         result.violations)


class TestGuardrailHole6DuplicateDayVersion(unittest.TestCase):
    """Hole #6 (duplicate same-day entries silently double-counted) is fixed in
    ``monthly_close.close_month`` -- see ``tests/test_monthly_close.py``, since
    ``check_invariants`` only ever sees one ``DayPlan`` at a time and has no list to dedupe."""


class TestGuardrailHole7CalendarAwareHorizon(unittest.TestCase):
    """Hole #7: ``PlanHorizon`` used to express "24 months" as 720/730 days
    (``timedelta(days=30 * months)``), giving 2026-09-15 -> 2028-09-04 (721 days) instead of the
    calendar-correct 2028-09-14 (731 days)."""

    def test_horizon_matches_real_calendar_months_not_a_30_day_approximation(self) -> None:
        h = PlanHorizon(start=date(2026, 9, 15), months=24)
        self.assertNotEqual(h.end, date(2028, 9, 4))  # the old, buggy value
        self.assertEqual(h.end, date(2028, 9, 14))

    def test_add_calendar_months_clamps_short_months(self) -> None:
        # 31 Jan + 1 month has no 31st in February; clamp to February's last day.
        self.assertEqual(add_calendar_months(date(2026, 1, 31), 1), date(2026, 2, 28))
        self.assertEqual(add_calendar_months(date(2028, 1, 31), 1), date(2028, 2, 29))


if __name__ == "__main__":
    unittest.main()
