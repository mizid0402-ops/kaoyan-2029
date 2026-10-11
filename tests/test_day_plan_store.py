"""Regression locks for ky.storage.day_plan_store (round-37 §5.1).

Two hard requirements from the task book:

  1. A violating ``write_day_plan`` call must leave the store directory byte-for-byte unchanged
     (checked with a whole-tree hash before/after) -- a rejected write must have zero side effects.
  2. A legal write must read back exactly as written.
"""

from __future__ import annotations

import hashlib
import tempfile
import unittest
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

from ky.schedule.completion import CompletionEvent, ReviewCompletion, VocabProgress
from ky.schedule.longitudinal import DayPlan
from ky.schedule.monthly_close import close_month
from ky.storage.day_plan_store import DayPlanStore, StorageError, parse_day_plan

WEIGHTS = {"math1": 0.40, "eng1": 0.20, "cs408": 0.40}


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.is_dir():
        return digest.hexdigest()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode("utf-8"))
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _valid_day_plan(day: date, **overrides) -> DayPlan:
    fields = dict(
        day=day, available_minutes=120, knowledge_minutes=60, vocab_minutes=60,
        vocab_new_items=15, subject_minutes={"math1": 24, "eng1": 12, "cs408": 24},
    )
    fields.update(overrides)
    return DayPlan(**fields)


class DayPlanRoundTripTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.store = DayPlanStore(self._tmp.name, subject_weights=WEIGHTS)

    def test_valid_plan_writes_and_reads_back_identically(self) -> None:
        plan = _valid_day_plan(date(2026, 9, 15))
        report = self.store.write_day_plan(plan)
        self.assertEqual(report.version, 1)
        reread = self.store.load_day_plan(date(2026, 9, 15))
        self.assertEqual(reread, plan)

    def test_missing_day_loads_as_none(self) -> None:
        self.assertIsNone(self.store.load_day_plan(date(2026, 9, 15)))

    def test_resubmitting_a_day_adds_a_new_version_without_touching_the_old_file(self) -> None:
        first = _valid_day_plan(date(2026, 9, 15))
        self.store.write_day_plan(first)
        first_files = sorted((Path(self._tmp.name) / "2026-09" / "day_plans").glob("*.yaml"))
        first_bytes = {p: p.read_bytes() for p in first_files}

        second = _valid_day_plan(date(2026, 9, 15), knowledge_minutes=48, vocab_minutes=48,
                                  subject_minutes={"math1": 19, "eng1": 10, "cs408": 19})
        report = self.store.write_day_plan(second)
        self.assertEqual(report.version, 2)

        for path, data in first_bytes.items():
            self.assertEqual(path.read_bytes(), data, f"{path} was overwritten")
        self.assertEqual(self.store.load_day_plan(date(2026, 9, 15)), second)

    def test_load_month_returns_every_day_sorted(self) -> None:
        self.store.write_day_plan(_valid_day_plan(date(2026, 9, 16)))
        self.store.write_day_plan(_valid_day_plan(date(2026, 9, 15)))
        plans = self.store.load_month(2026, 9)
        self.assertEqual([p.day for p in plans], [date(2026, 9, 15), date(2026, 9, 16)])


class RejectedWriteHasZeroSideEffectsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.store = DayPlanStore(self.root, subject_weights=WEIGHTS)

    def test_invariant_violation_leaves_the_directory_byte_identical(self) -> None:
        before = _tree_hash(self.root)
        bad = _valid_day_plan(date(2026, 9, 15), backlog_minutes=-1)  # hole #2: negative backlog
        with self.assertRaises(StorageError):
            self.store.write_day_plan(bad)
        after = _tree_hash(self.root)
        self.assertEqual(before, after)
        self.assertIsNone(self.store.load_day_plan(date(2026, 9, 15)))

    def test_violation_message_names_the_exact_guardrail(self) -> None:
        bad = _valid_day_plan(date(2026, 9, 15), knowledge_minutes=999)  # no longer reconciles
        with self.assertRaises(StorageError) as ctx:
            self.store.write_day_plan(bad)
        self.assertIn("knowledge_minutes", str(ctx.exception))

    def test_existing_good_plan_is_untouched_by_a_later_bad_one(self) -> None:
        good = _valid_day_plan(date(2026, 9, 15))
        self.store.write_day_plan(good)
        before = _tree_hash(self.root)
        bad = _valid_day_plan(date(2026, 9, 16), vocab_new_items=-1)
        with self.assertRaises(StorageError):
            self.store.write_day_plan(bad)
        after = _tree_hash(self.root)
        self.assertEqual(before, after)
        self.assertEqual(self.store.load_day_plan(date(2026, 9, 15)), good)


class MonthCloseWriteOnceTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.store = DayPlanStore(self._tmp.name, subject_weights=WEIGHTS)

    def _close(self) -> "close_month":
        plans = [_valid_day_plan(date(2026, 9, 15))]
        return close_month(2026, 9, plans, subject_weights=WEIGHTS)

    def test_write_then_read_back(self) -> None:
        mc = self._close()
        self.store.write_month_close(mc)
        reread = self.store.load_month_close(2026, 9)
        self.assertEqual(reread.available_minutes, mc.available_minutes)
        self.assertEqual(reread.violations, mc.violations)

    def test_second_write_is_rejected_not_overwritten(self) -> None:
        mc = self._close()
        self.store.write_month_close(mc)
        path = Path(self._tmp.name) / "2026-09" / "month_close.yaml"
        before = path.read_bytes()
        with self.assertRaises(StorageError):
            self.store.write_month_close(mc)
        self.assertEqual(path.read_bytes(), before)

    def test_missing_month_close_loads_as_none(self) -> None:
        self.assertIsNone(self.store.load_month_close(2099, 1))

    def test_actual_vs_planned_fields_round_trip(self) -> None:
        # round-38 residual B: the new actual_* / vocab_delivered_vs_planned fields must not be
        # silently dropped by the storage layer's own mapping <-> MonthClose conversion.
        completions = [CompletionEvent(
            day=date(2026, 9, 15),
            reviews=(ReviewCompletion(review_id="rv1", completed_on=date(2026, 9, 15),
                                      check="past_question", outcome="correct"),),
            vocab=VocabProgress(delivered_words=("abate", "abdicate"), practiced_words=("abate",)),
        )]
        mc = close_month(2026, 9, [_valid_day_plan(date(2026, 9, 15))], subject_weights=WEIGHTS,
                          completions=completions)
        self.store.write_month_close(mc)
        reread = self.store.load_month_close(2026, 9)
        self.assertEqual(reread.actual_data_available, True)
        self.assertEqual(reread.days_with_completion_events, 1)
        self.assertEqual(reread.actual_reviews_completed, 1)
        self.assertEqual(reread.actual_vocab_delivered_words, 2)
        self.assertEqual(reread.actual_vocab_practiced_words, 1)
        self.assertEqual(reread.vocab_delivered_vs_planned, mc.vocab_delivered_vs_planned)

    def test_month_close_without_completions_round_trips_actuals_as_unavailable(self) -> None:
        mc = self._close()
        self.store.write_month_close(mc)
        reread = self.store.load_month_close(2026, 9)
        self.assertFalse(reread.actual_data_available)
        self.assertIsNone(reread.actual_reviews_completed)
        self.assertIsNone(reread.actual_vocab_delivered_words)
        self.assertIsNone(reread.actual_vocab_practiced_words)
        self.assertIsNone(reread.vocab_delivered_vs_planned)


class CompletionEventWriteOnceTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.store = DayPlanStore(self._tmp.name, subject_weights=WEIGHTS)

    def _event(self) -> CompletionEvent:
        return CompletionEvent(
            day=date(2026, 9, 15),
            reviews=(ReviewCompletion(review_id="rv1", completed_on=date(2026, 9, 15),
                                      check="past_question", outcome="correct"),),
            vocab=VocabProgress(delivered_words=("abate", "abdicate"), practiced_words=("abate",)),
        )

    def test_write_then_read_back(self) -> None:
        event = self._event()
        self.store.write_completion_event(event)
        reread = self.store.load_completion_event(date(2026, 9, 15))
        self.assertEqual(reread, replace(
            event,
            reviews=(replace(event.reviews[0], completion_id="2026-09-15#0"),),
        ))
        # delivered != practiced must survive the round trip, not just be present.
        self.assertEqual(len(reread.vocab.delivered_words), 2)
        self.assertEqual(len(reread.vocab.practiced_words), 1)

    def test_second_write_for_the_same_day_is_rejected(self) -> None:
        event = self._event()
        self.store.write_completion_event(event)
        path = Path(self._tmp.name) / "2026-09" / "completion--2026-09-15.yaml"
        before = path.read_bytes()
        with self.assertRaises(StorageError):
            self.store.write_completion_event(event)
        self.assertEqual(path.read_bytes(), before)

    def test_missing_completion_event_loads_as_none(self) -> None:
        self.assertIsNone(self.store.load_completion_event(date(2099, 1, 1)))

    def test_delivered_words_unions_all_completion_events(self) -> None:
        first = self._event()
        second = replace(
            first,
            day=date(2026, 10, 2),
            vocab=VocabProgress(delivered_words=("abdicate", "abjure")),
        )
        self.store.write_completion_event(first)
        self.store.write_completion_event(second)
        self.assertEqual(self.store.delivered_words(), frozenset({"abate", "abdicate", "abjure"}))

    def test_delivered_words_is_empty_for_an_empty_store(self) -> None:
        self.assertEqual(self.store.delivered_words(), frozenset())

    def test_delivered_words_refuses_events_outside_the_store_layout(self) -> None:
        # sol round 86, M1: a valid event in a stray directory, or under another day's name,
        # used to be counted and silently shrank the daily-word pool.
        self.store.write_completion_event(self._event())
        written = Path(self._tmp.name) / "2026-09" / "completion--2026-09-15.yaml"
        root = Path(self._tmp.name)
        for stray in (root / "misc" / "completion--junk.yaml",
                      root / "2026-09" / "completion--2026-09-16.yaml",
                      root / "completion--2026-09-15.yaml",
                      root / "2026-09" / "day_plans" / "completion--2026-09-15.yaml"):
            with self.subTest(stray=stray.name):
                stray.parent.mkdir(parents=True, exist_ok=True)
                stray.write_bytes(written.read_bytes())
                with self.assertRaises(StorageError) as caught:
                    self.store.delivered_words()
                self.assertIn("not at its store path", str(caught.exception))
                stray.unlink()


class HandWrittenPlanInputTest(unittest.TestCase):
    """WP-R3 (round 153 D2 / D3): hand-written plan values give contract errors, not tracebacks.

    ``parse_day_plan`` is the single entry for M19 proposals and ``day-plan submit --plan``,
    so it sees the scalars YAML produces from a hand-typed file.
    """

    DAY = date(2026, 9, 15)

    def _raw(self, **overrides) -> dict:
        raw = {"day": self.DAY.isoformat(), "available_minutes": 60}
        raw.update(overrides)
        return raw

    def test_an_unquoted_yaml_date_is_accepted_as_that_day(self) -> None:
        plan = parse_day_plan(self._raw(day=self.DAY), "plan")
        self.assertEqual(plan, parse_day_plan(self._raw(), "plan"))
        self.assertEqual(plan.day, self.DAY)

    def test_a_datetime_day_is_still_rejected(self) -> None:
        moment = datetime(self.DAY.year, self.DAY.month, self.DAY.day, 8, 0)
        with self.assertRaises(StorageError) as caught:
            parse_day_plan(self._raw(day=moment), "plan")
        self.assertEqual(caught.exception.path, "plan.day")

    def test_an_impossible_date_string_is_a_contract_error(self) -> None:
        impossible = f"{self.DAY.year}-13-01"
        with self.assertRaises(StorageError) as caught:
            parse_day_plan(self._raw(day=impossible), "plan")
        self.assertEqual(caught.exception.path, "plan.day")
        self.assertIn(repr(impossible), str(caught.exception))

    def test_minutes_given_as_strings_are_contract_errors(self) -> None:
        for field in ("available_minutes", "knowledge_minutes", "vocab_new_items"):
            with self.subTest(field=field):
                with self.assertRaises(StorageError) as caught:
                    parse_day_plan(self._raw(**{field: "60"}), "plan")
                self.assertEqual(caught.exception.path, f"plan.{field}")

    def test_empty_list_is_not_silently_accepted_as_subject_minutes(self) -> None:
        with self.assertRaises(StorageError) as caught:
            parse_day_plan(self._raw(subject_minutes=[]), "plan")
        self.assertEqual(caught.exception.path, "plan.subject_minutes")

    def test_booleans_and_floats_are_not_stored_as_minutes(self) -> None:
        subject = next(iter(WEIGHTS))
        for value in (True, 30.0, 30.5):
            for raw, field_path in (
                (self._raw(backlog_minutes=value), "plan.backlog_minutes"),
                (self._raw(subject_minutes={subject: value}), f"plan.subject_minutes.{subject}"),
            ):
                with self.subTest(value=value, field_path=field_path):
                    with self.assertRaises(StorageError) as caught:
                        parse_day_plan(raw, "plan")
                    self.assertEqual(caught.exception.path, field_path)


class DoesNotPrescribeTest(unittest.TestCase):
    """Mirrors monthly_close's test_close_does_not_prescribe_next_month, replicated per round-37
    §1: a store only persists already-validated records -- no public name here may look like a
    recommendation/suggestion/default/optimum, or a next-month prescription."""

    def test_no_prescriptive_public_names(self) -> None:
        import ky.storage.day_plan_store as module

        banned_prefixes = ("recommend", "suggest", "default", "optimal", "next_month_")
        names = list(dir(module))
        names.extend(module.WriteReport.__dataclass_fields__)
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
