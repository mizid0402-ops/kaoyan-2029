"""Regression locks for the vocabulary channel adapter and the monthly close.

Two properties matter most here and are the reason these tests exist:

  1. The adapter does not choose how many words a day contains, and the per-word cost is the
     caller's input -- not a constant buried in code. If someone hardcodes either, these go red.
  2. The monthly close carries residue (unused time, overshoot, backlog) as explicit numbers and
     never invents compensating capacity for the next month.
"""

from __future__ import annotations

import hashlib
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

from ky.schedule.completion import CompletionEvent, ReviewCompletion, VocabProgress
from ky.storage.day_plan_store import DayPlanStore

from ky.schedule.longitudinal import DayPlan
from ky.schedule.monthly_close import close_month, month_bounds
from ky.schedule.vocab_channel import (
    VocabChannelError,
    import_delivery_baseline_with_dates,
    preview_batch,
    remaining_pool,
)

WEIGHTS = {"math1": 0.40, "eng1": 0.20, "cs408": 0.40}
REPO_ROOT = Path(__file__).resolve().parents[1]
from ky.workspace import load_workspace

VOCAB_DB = load_workspace(REPO_ROOT / "kaoyan.workspace.yaml").require("reference.vocabulary_db")
HAVE_DB = VOCAB_DB.is_file()


class TestVocabChannelAgainstRealDb(unittest.TestCase):
    """Only runs when the vocabulary database is present."""

    @unittest.skipUnless(HAVE_DB, "vocabulary database not built")
    def test_pool_is_positive(self) -> None:
        self.assertGreater(remaining_pool(db=VOCAB_DB), 0)

    @unittest.skipUnless(HAVE_DB, "vocabulary database not built")
    def test_requested_count_is_honoured(self) -> None:
        for n in (1, 5, 15, 40):
            with self.subTest(n=n):
                self.assertEqual(preview_batch(n, db=VOCAB_DB).count, n)

    @unittest.skipUnless(HAVE_DB, "vocabulary database not built")
    def test_zero_is_allowed_and_costs_nothing(self) -> None:
        b = preview_batch(0, db=VOCAB_DB)
        self.assertEqual(b.count, 0)
        self.assertEqual(b.minutes, 0)

    @unittest.skipUnless(HAVE_DB, "vocabulary database not built")
    def test_minutes_follow_the_caller_supplied_cost(self) -> None:
        # No default per-word cost may be baked in: four different inputs, four answers.
        got = {c: preview_batch(20, minutes_per_word=c, db=VOCAB_DB).minutes for c in (0.25, 0.5, 1.0, 2.0)}
        self.assertEqual(got[0.25], 5)
        self.assertEqual(got[0.5], 10)
        self.assertEqual(got[1.0], 20)
        self.assertEqual(got[2.0], 40)

    @unittest.skipUnless(HAVE_DB, "vocabulary database not built")
    def test_batch_is_ordered_by_frequency_descending(self) -> None:
        # The database's own ordering must be preserved; the adapter must not re-sort.
        b = preview_batch(10, db=VOCAB_DB)
        con = sqlite3.connect(f"file:{VOCAB_DB}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        counts = []
        for w in b.words:
            r = con.execute(
                "SELECT family_total_count c FROM words WHERE word_form = ?", (w,)).fetchone()
            if r is not None:
                counts.append(r["c"])
        con.close()
        self.assertEqual(counts, sorted(counts, reverse=True), counts)

    @unittest.skipUnless(HAVE_DB, "vocabulary database not built")
    def test_pool_exhaustion_is_reported_not_padded(self) -> None:
        b = preview_batch(10 ** 6, db=VOCAB_DB)
        self.assertLess(b.count, 10 ** 6)
        self.assertIn("pool exhausted", b.note)
        self.assertEqual(len(b.words), len(set(b.words)), "must not pad with repeats")

    def test_negative_count_is_rejected(self) -> None:
        with self.assertRaises(VocabChannelError):
            preview_batch(-1, db=VOCAB_DB)

    def test_negative_per_word_cost_is_rejected(self) -> None:
        with self.assertRaises(VocabChannelError):
            preview_batch(5, minutes_per_word=-0.1, db=VOCAB_DB)

    def test_missing_database_raises(self) -> None:
        with self.assertRaises(VocabChannelError):
            preview_batch(5, db=Path(tempfile.gettempdir()) / "definitely-absent.sqlite")

    @unittest.skipUnless(HAVE_DB, "vocabulary database not built")
    def test_preview_does_not_write_the_delivery_log(self) -> None:
        con = sqlite3.connect(f"file:{VOCAB_DB}?mode=ro", uri=True)
        before = con.execute("SELECT COUNT(*) FROM delivery_log").fetchone()[0]
        con.close()
        preview_batch(5, db=VOCAB_DB)
        con = sqlite3.connect(f"file:{VOCAB_DB}?mode=ro", uri=True)
        after = con.execute("SELECT COUNT(*) FROM delivery_log").fetchone()[0]
        con.close()
        self.assertEqual(before, after, "preview must not deliver")


class TestVocabDatabaseStaysFrozen(unittest.TestCase):
    """round-37 §6/§8: the vocabulary database is permanently read-only. Delivery/practice
    tracking going forward lives in external completion events (ky.storage.day_plan_store), not
    in the database's own delivery_log, which remains available as a read-only migration input."""

    @unittest.skipUnless(HAVE_DB, "vocabulary database not built")
    def test_import_delivery_baseline_includes_dates_without_repetition(self) -> None:
        baseline = import_delivery_baseline_with_dates(db=VOCAB_DB)
        self.assertEqual(len(baseline), len(set(baseline)), "baseline rows must not repeat")
        self.assertTrue(all(day and word for day, word in baseline))

    @unittest.skipUnless(HAVE_DB, "vocabulary database not built")
    def test_import_delivery_baseline_does_not_write(self) -> None:
        before = hashlib.sha256(VOCAB_DB.read_bytes()).hexdigest()
        import_delivery_baseline_with_dates(db=VOCAB_DB)
        after = hashlib.sha256(VOCAB_DB.read_bytes()).hexdigest()
        self.assertEqual(before, after)

    @unittest.skipUnless(HAVE_DB, "vocabulary database not built")
    def test_a_full_delivery_cycle_through_the_new_path_leaves_the_database_byte_identical(self) -> None:
        # Preview a batch (read-only) and record it as delivered through the external
        # completion-event log -- the new authoritative path -- instead of tools/daily_words.py.
        before = hashlib.sha256(VOCAB_DB.read_bytes()).hexdigest()

        batch = preview_batch(10, db=VOCAB_DB)
        with tempfile.TemporaryDirectory() as tmp:
            store = DayPlanStore(tmp)
            event = CompletionEvent(
                day=date(2026, 9, 20),
                vocab=VocabProgress(delivered_words=batch.words, practiced_words=()),
            )
            store.write_completion_event(event)
            reread = store.load_completion_event(date(2026, 9, 20))
            self.assertEqual(reread.vocab.delivered_words, batch.words)

        after = hashlib.sha256(VOCAB_DB.read_bytes()).hexdigest()
        self.assertEqual(before, after, "the frozen vocabulary database must be byte-identical")
        self.assertEqual(after, "839d48be37d7716b1a12da04e3e2293868ee379b6e09a13dd198dae5498d0e2c")


class TestMonthBounds(unittest.TestCase):
    def test_ordinary_month(self) -> None:
        a, b = month_bounds(2026, 1)
        self.assertEqual((a, b), (date(2026, 1, 1), date(2026, 1, 31)))

    def test_february_non_leap(self) -> None:
        a, b = month_bounds(2026, 2)
        self.assertEqual((b - a).days + 1, 28)

    def test_february_leap(self) -> None:
        a, b = month_bounds(2028, 2)
        self.assertEqual((b - a).days + 1, 29)

    def test_december_does_not_roll_into_itself(self) -> None:
        a, b = month_bounds(2026, 12)
        self.assertEqual((a, b), (date(2026, 12, 1), date(2026, 12, 31)))

    def test_invalid_month_rejected(self) -> None:
        for m in (0, 13, -1):
            with self.subTest(month=m), self.assertRaises(ValueError):
                month_bounds(2026, m)


class TestMonthlyClose(unittest.TestCase):
    def _march_plans(self):
        return [
            DayPlan(day=date(2026, 9, 15), available_minutes=120,
                    knowledge_minutes=60, vocab_minutes=60, vocab_new_items=20,
                    subject_minutes={"math1": 24, "eng1": 12, "cs408": 24}),
            DayPlan(day=date(2026, 9, 16), available_minutes=90,
                    knowledge_minutes=40, vocab_minutes=30, vocab_new_items=15,
                    backlog_minutes=10,
                    subject_minutes={"math1": 16, "eng1": 8, "cs408": 16}),
            DayPlan(day=date(2026, 9, 20), available_minutes=150,
                    knowledge_minutes=60, vocab_minutes=40, phrase_minutes=50,
                    subject_minutes={"math1": 24, "eng1": 12, "cs408": 24}),
        ]

    def test_totals(self) -> None:
        mc = close_month(2026, 9, self._march_plans(), subject_weights=WEIGHTS)
        self.assertEqual(mc.days_in_month, 30)
        self.assertEqual(mc.days_planned, 3)
        self.assertEqual(mc.days_unplanned, 27)
        self.assertEqual(mc.available_minutes, 360)
        self.assertEqual(mc.allocated_minutes, 340)
        self.assertEqual(mc.vocab_items_introduced, 35)
        self.assertEqual(mc.by_channel["phrase"], 50)
        # With every day's knowledge minutes now honestly attributed to a subject, the
        # guard-rail-compliant fixture must close clean.
        self.assertTrue(mc.ok, mc.violations)

    def test_unplanned_days_are_counted_not_assumed(self) -> None:
        # No capacity may be invented for a day that has no plan.
        mc = close_month(2026, 9, self._march_plans(), subject_weights=WEIGHTS)
        self.assertEqual(mc.available_minutes, 360)  # only the three planned days
        self.assertEqual(mc.days_unplanned, 27)

    def test_residue_is_explicit(self) -> None:
        mc = close_month(2026, 9, self._march_plans(), subject_weights=WEIGHTS)
        self.assertEqual(mc.unused_minutes, 20)
        self.assertEqual(mc.backlog_minutes, 10)
        self.assertEqual(mc.backlog_days, 1)
        self.assertTrue(any("carried forward" in n for n in mc.notes))

    def test_utilisation(self) -> None:
        mc = close_month(2026, 9, self._march_plans(), subject_weights=WEIGHTS)
        self.assertAlmostEqual(mc.utilisation, 340 / 360, places=6)

    def test_utilisation_with_no_available_time_is_zero_not_error(self) -> None:
        mc = close_month(2026, 9, [], subject_weights=WEIGHTS)
        self.assertEqual(mc.utilisation, 0.0)

    def test_violating_day_is_surfaced(self) -> None:
        bad = [DayPlan(day=date(2026, 9, 21), available_minutes=60,
                      knowledge_minutes=60, vocab_minutes=40)]
        mc = close_month(2026, 9, bad, subject_weights=WEIGHTS)
        self.assertFalse(mc.ok)
        self.assertTrue(any("backlog" in v for v in mc.violations))

    def test_overshoot_is_reported(self) -> None:
        plans = [DayPlan(day=date(2026, 9, 22), available_minutes=60,
                         knowledge_minutes=60, vocab_minutes=40, backlog_minutes=40)]
        mc = close_month(2026, 9, plans, subject_weights=WEIGHTS)
        self.assertEqual(mc.overshoot_days, 1)
        self.assertEqual(mc.overshoot_minutes, 40)

    def test_days_outside_the_month_are_ignored(self) -> None:
        plans = self._march_plans() + [
            DayPlan(day=date(2026, 10, 1), available_minutes=600, knowledge_minutes=600)]
        mc = close_month(2026, 9, plans, subject_weights=WEIGHTS)
        self.assertEqual(mc.available_minutes, 360)
        self.assertEqual(mc.days_planned, 3)

    def test_duplicate_same_day_entries_are_not_double_counted(self) -> None:
        # Hole #6 (round-37 audit): passing the same calendar day twice used to double the
        # month's totals -- days_planned=2 and available_minutes=120 for what is really one
        # 60-minute day. The duplicate must now be dropped from the totals (not summed) and
        # surfaced as an explicit violation instead of silently doubling the count.
        same_day_twice = [
            DayPlan(day=date(2026, 9, 15), available_minutes=60, knowledge_minutes=60,
                    subject_minutes={"math1": 24, "eng1": 12, "cs408": 24}),
            DayPlan(day=date(2026, 9, 15), available_minutes=60, knowledge_minutes=60,
                    subject_minutes={"math1": 24, "eng1": 12, "cs408": 24}),
        ]
        mc = close_month(2026, 9, same_day_twice, subject_weights=WEIGHTS)
        self.assertEqual(mc.days_planned, 1)
        self.assertEqual(mc.available_minutes, 60)
        self.assertEqual(mc.allocated_minutes, 60)
        self.assertFalse(mc.ok)
        self.assertTrue(
            any("2026-09-15" in v and "only the first was counted" in v for v in mc.violations),
            mc.violations,
        )

    def test_close_does_not_prescribe_next_month(self) -> None:
        # There is deliberately no field telling the next month what capacity to use.
        mc = close_month(2026, 9, self._march_plans(), subject_weights=WEIGHTS)
        for forbidden in ("next_month_minutes", "recommended_budget", "suggested_minutes"):
            self.assertFalse(hasattr(mc, forbidden),
                             f"{forbidden} would be a prescription, not a report")


class TestMonthlyCloseActualVsPlanned(unittest.TestCase):
    """round-38 residual B: close_month must be able to consume CompletionEvent and report
    plan vs. actual separately -- never merged into one number, never prescriptive."""

    def _plans(self):
        return [DayPlan(day=date(2026, 9, 15), available_minutes=120,
                         knowledge_minutes=60, vocab_minutes=60, vocab_new_items=15,
                         subject_minutes={"math1": 24, "eng1": 12, "cs408": 24})]

    def test_standard_1_no_completions_argument_behaves_exactly_as_before(self) -> None:
        # This is the existing call shape used by every round-37 call site: completions omitted.
        mc = close_month(2026, 9, self._plans(), subject_weights=WEIGHTS)
        self.assertFalse(mc.actual_data_available)
        self.assertEqual(mc.days_with_completion_events, 0)
        self.assertIsNone(mc.actual_reviews_completed)
        self.assertIsNone(mc.actual_vocab_delivered_words)
        self.assertIsNone(mc.actual_vocab_practiced_words)
        self.assertIsNone(mc.vocab_delivered_vs_planned)
        # Existing totals are completely unaffected by the new, unused parameter.
        self.assertEqual(mc.vocab_items_introduced, 15)
        self.assertEqual(mc.available_minutes, 120)

    def test_standard_2_plan_and_actual_are_both_present_and_the_difference_reconciles(self) -> None:
        completions = [
            CompletionEvent(
                day=date(2026, 9, 15),
                reviews=(ReviewCompletion(review_id="rv1", completed_on=date(2026, 9, 15),
                                          check="past_question", outcome="correct"),),
                vocab=VocabProgress(
                    delivered_words=("abate", "abdicate"),
                    practiced_words=("abate",),
                ),
            ),
        ]
        mc = close_month(2026, 9, self._plans(), subject_weights=WEIGHTS, completions=completions)
        self.assertTrue(mc.actual_data_available)
        self.assertEqual(mc.days_with_completion_events, 1)
        self.assertEqual(mc.actual_reviews_completed, 1)
        # Planned (from DayPlan) and actual (from CompletionEvent) are both visible ...
        self.assertEqual(mc.vocab_items_introduced, 15)
        self.assertEqual(mc.actual_vocab_delivered_words, 2)
        # ... and the difference between them is directly computable from the two numbers above.
        self.assertEqual(mc.vocab_delivered_vs_planned, mc.actual_vocab_delivered_words - mc.vocab_items_introduced)
        self.assertEqual(mc.vocab_delivered_vs_planned, -13)

    def test_standard_3_delivered_and_practiced_are_never_summed(self) -> None:
        completions = [
            CompletionEvent(
                day=date(2026, 9, 15),
                vocab=VocabProgress(
                    delivered_words=("abate", "abdicate", "abstain", "accede"),
                    practiced_words=("abate",),
                ),
            ),
        ]
        mc = close_month(2026, 9, self._plans(), subject_weights=WEIGHTS, completions=completions)
        self.assertEqual(mc.actual_vocab_delivered_words, 4)
        self.assertEqual(mc.actual_vocab_practiced_words, 1)
        # If these had been summed instead of kept separate, this would be 5, not 4-and-1.
        self.assertNotEqual(mc.actual_vocab_delivered_words + mc.actual_vocab_practiced_words, 4)
        self.assertNotEqual(mc.actual_vocab_delivered_words + mc.actual_vocab_practiced_words, 1)

    def test_standard_4_zero_completion_events_is_a_measured_zero_not_missing_data(self) -> None:
        mc = close_month(2026, 9, self._plans(), subject_weights=WEIGHTS, completions=[])
        self.assertTrue(mc.actual_data_available)  # "we looked" ...
        self.assertEqual(mc.actual_reviews_completed, 0)  # ... "and found zero"
        self.assertEqual(mc.actual_vocab_delivered_words, 0)
        self.assertEqual(mc.actual_vocab_practiced_words, 0)
        self.assertTrue(any("measured zero" in n for n in mc.notes))
        # Contrast with "not measured at all":
        mc_unmeasured = close_month(2026, 9, self._plans(), subject_weights=WEIGHTS)
        self.assertFalse(mc_unmeasured.actual_data_available)
        self.assertIsNone(mc_unmeasured.actual_reviews_completed)
        self.assertNotEqual(mc.actual_data_available, mc_unmeasured.actual_data_available)

    def test_completions_outside_the_month_are_excluded(self) -> None:
        completions = [
            CompletionEvent(day=date(2026, 8, 31), vocab=VocabProgress(delivered_words=("abate",))),
            CompletionEvent(day=date(2026, 10, 1), vocab=VocabProgress(delivered_words=("abate", "abdicate"))),
            CompletionEvent(day=date(2026, 9, 15), vocab=VocabProgress(delivered_words=("abstain",))),
        ]
        mc = close_month(2026, 9, self._plans(), subject_weights=WEIGHTS, completions=completions)
        self.assertEqual(mc.days_with_completion_events, 1)
        self.assertEqual(mc.actual_vocab_delivered_words, 1)

    def test_no_prescriptive_or_next_month_fields_leak_in_with_actuals(self) -> None:
        completions = [CompletionEvent(day=date(2026, 9, 15))]
        mc = close_month(2026, 9, self._plans(), subject_weights=WEIGHTS, completions=completions)
        for forbidden in ("next_month_minutes", "recommended_budget", "suggested_minutes",
                          "next_month_vocab", "recommended_delivery"):
            self.assertFalse(hasattr(mc, forbidden),
                             f"{forbidden} would be a prescription, not a report")

    def test_no_prescriptive_public_names_in_the_module(self) -> None:
        import ky.schedule.monthly_close as module

        banned_prefixes = ("recommend", "suggest", "default", "optimal", "next_month_")
        # module.__all__ (not dir(module)) -- dir() would also catch incidental imports like
        # collections.defaultdict, which is not part of this module's own public surface.
        names = list(module.__all__)
        names.extend(module.MonthClose.__dataclass_fields__)
        for name in names:
            if name.startswith("_"):
                continue
            lowered = name.lower()
            for prefix in banned_prefixes:
                self.assertFalse(
                    lowered.startswith(prefix), f"{name} looks prescriptive (matches {prefix!r})"
                )


if __name__ == "__main__":
    unittest.main()
