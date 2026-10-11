"""Contract tests for M10's deterministic FSRS implementation."""

from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from fsrs import Card, Rating, Scheduler, State

from ky.models import ContractError, validate_review_item
from ky.schedule.completion import (
    CompletionEvent,
    ReviewCompletion,
    create_review_algorithm,
    reset_for_relearning,
)
from ky.schedule.fsrs_algorithm import FsrsAlgorithm
from ky.storage.day_plan_store import advance_review_queue
from ky.storage.review_shards import ReviewShardStore


def _item(*, mode: str = "fixed_bootstrap", phase: int = 0, interval: int = 1):
    schedule = {
        "mode": mode,
        "phase": phase,
        "interval_days": interval,
        "ease_factor": 2.5,
        "repetitions": 0,
        "lapses": 0,
    }
    if mode == "fsrs":
        schedule.update({
            "stability": 8.0,
            "difficulty": 5.0,
            "fsrs_reviewed_on": "2026-10-01",
        })
    return validate_review_item({
        "review_id": "rv1",
        "revision": 1,
        "subject_id": "math1",
        "knowledge_point_id": "math1.demo.rv1",
        "title": "demo",
        "granularity": "concept",
        "state": "queued",
        "estimated_minutes": 10,
        "introduced_on": "2026-09-01",
        "due_date": "2026-09-12",
        "last_reviewed_on": None,
        "schedule": schedule,
        "defer_count": 0,
        "last_quality": None,
    })


def _completion(day: date, outcome: str, *, completion_id: str | None = None):
    return ReviewCompletion(
        "rv1", day, "past_question", outcome, completion_id=completion_id
    )


def _scheduler() -> Scheduler:
    return Scheduler(
        desired_retention=0.9,
        learning_steps=(),
        relearning_steps=(),
        maximum_interval=180,
        enable_fuzzing=False,
    )


class FsrsAlgorithmPortTests(unittest.TestCase):
    def test_checked_ratings_match_py_fsrs_scheduler(self) -> None:
        for outcome, rating in (
            ("correct", Rating.Good), ("partial", Rating.Hard),
            ("incorrect", Rating.Again),
        ):
            with self.subTest(outcome=outcome):
                item = _item()
                day = date(2026, 10, 1)
                review_time = datetime.combine(day, time.min, timezone.utc)
                expected_card, _ = _scheduler().review_card(
                    Card(card_id=1), rating, review_datetime=review_time
                )
                advanced = FsrsAlgorithm().advance(item, _completion(day, outcome))
                schedule = advanced.schedule
                interval = max(1, (expected_card.due.date() - day).days)
                self.assertEqual(schedule.mode, "fsrs")
                self.assertEqual(schedule.stability, expected_card.stability)
                self.assertEqual(schedule.difficulty, expected_card.difficulty)
                self.assertEqual(schedule.interval_days, interval)
                self.assertEqual(advanced.due_date, day + timedelta(days=interval))
                self.assertEqual(schedule.repetitions, 1)
                self.assertEqual(schedule.lapses, int(outcome == "incorrect"))

    def test_unchecked_d9_keeps_memory_state_and_caps_unrated_interval(self) -> None:
        memory_fields = ("stability", "difficulty", "fsrs_reviewed_on")
        rules = {
            ("strict", "unknown"): 20,
            ("strict", "vague"): 20,
            ("strict", "basic"): 20,
            ("strict", "fluent"): 20,
            ("lenient", "unknown"): 1,
            ("lenient", "vague"): 10,
            ("lenient", "basic"): 20,
            ("lenient", "fluent"): 20,
        }
        for (mode, rating), expected_interval in rules.items():
            with self.subTest(mode=mode, rating=rating):
                item = _item(mode="fsrs", phase=5, interval=20)
                algorithm = FsrsAlgorithm(mode)
                completion = ReviewCompletion(
                    "rv1", date(2026, 10, 10), "none", self_rating=rating
                )
                advanced = algorithm.advance(item, completion)
                self.assertEqual(
                    tuple(getattr(advanced.schedule, name) for name in memory_fields),
                    tuple(getattr(item.schedule, name) for name in memory_fields),
                )
                self.assertEqual(advanced.schedule.interval_days, expected_interval)
                self.assertLessEqual(
                    advanced.schedule.interval_days, item.schedule.interval_days
                )

    def test_relearning_reset_preserves_fsrs_memory_and_lapses(self) -> None:
        schedule = replace(_item(mode="fsrs", phase=5).schedule, lapses=4)
        reset = reset_for_relearning(schedule)
        self.assertEqual((reset.interval_days, reset.repetitions), (1, 0))
        self.assertEqual(
            (reset.stability, reset.difficulty, reset.fsrs_reviewed_on, reset.lapses),
            (schedule.stability, schedule.difficulty, schedule.fsrs_reviewed_on, 4),
        )

    def test_unchecked_completion_does_not_replace_fsrs_memory_clock(self) -> None:
        item = FsrsAlgorithm().advance(
            _item(), _completion(date(2026, 10, 1), "correct")
        )
        after_unchecked = FsrsAlgorithm().advance(item, ReviewCompletion(
            "rv1", date(2026, 10, 30), "none", self_rating="fluent"
        ))
        self.assertEqual(after_unchecked.last_reviewed_on, date(2026, 10, 30))
        self.assertEqual(after_unchecked.schedule.fsrs_reviewed_on, date(2026, 10, 1))
        review_time = datetime(2026, 10, 31, tzinfo=timezone.utc)
        card = Card(
            card_id=1, state=State.Review, stability=item.schedule.stability,
            difficulty=item.schedule.difficulty,
            last_review=datetime(2026, 10, 1, tzinfo=timezone.utc),
        )
        expected, _ = _scheduler().review_card(card, Rating.Good, review_datetime=review_time)
        actual = FsrsAlgorithm().advance(
            after_unchecked, _completion(date(2026, 10, 31), "correct")
        )
        self.assertEqual(actual.schedule.stability, expected.stability)
        self.assertEqual(actual.schedule.difficulty, expected.difficulty)
        self.assertEqual(
            actual.schedule.interval_days,
            (expected.due.date() - review_time.date()).days,
        )

    def test_late_checked_completion_is_reported_without_fsrs_schedule_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ReviewShardStore(Path(temp_dir))
            fsrs_item = FsrsAlgorithm().advance(
                _item(), _completion(date(2026, 10, 10), "correct", completion_id="first")
            )
            store.write([fsrs_item])
            before = store.load()[0]
            seven = lambda item: (
                item.schedule.stability, item.schedule.difficulty,
                item.schedule.fsrs_reviewed_on, item.schedule.interval_days,
                item.due_date, item.schedule.repetitions, item.schedule.lapses,
            )
            report = advance_review_queue(store, CompletionEvent(
                date(2026, 10, 10), (_completion(date(2026, 10, 5), "incorrect",
                                                 completion_id="late"),),
            ), algorithm=FsrsAlgorithm())
            after = store.load()[0]
            self.assertEqual(seven(after), seven(before))
            self.assertEqual(report.fsrs_late_checks[0].review_id, "rv1")
            self.assertEqual(report.fsrs_late_checks[0].completion_id, "late")
            self.assertEqual(report.fsrs_late_checks[0].fsrs_reviewed_on, date(2026, 10, 10))
            self.assertEqual(after.last_reviewed_on, date(2026, 10, 10))
            self.assertIn("late", store.calculated_completion_ids())
            same_day = advance_review_queue(store, CompletionEvent(
                date(2026, 10, 10), (_completion(date(2026, 10, 10), "partial",
                                                 completion_id="same-day"),),
            ), algorithm=FsrsAlgorithm())
            self.assertEqual(same_day.fsrs_late_checks, ())
            self.assertEqual(store.load()[0].schedule.repetitions, before.schedule.repetitions + 1)

    def test_algorithm_switches_use_fsrs_then_return_to_sm2(self) -> None:
        item = FsrsAlgorithm().advance(
            _item(), _completion(date(2026, 10, 1), "correct")
        )
        ladder = create_review_algorithm("ladder", "strict")
        changed = ladder.advance(item, _completion(date(2026, 10, 10), "correct"))
        self.assertEqual(changed.schedule.mode, "sm2_lite")
        self.assertEqual(
            (changed.schedule.stability, changed.schedule.difficulty,
             changed.schedule.fsrs_reviewed_on),
            (None, None, None),
        )

    def test_repeated_input_is_deterministic_and_interval_is_bounded(self) -> None:
        completion = _completion(date(2026, 10, 1), "correct")
        first = FsrsAlgorithm().advance(_item(), completion)
        second = FsrsAlgorithm().advance(_item(), completion)
        self.assertEqual(first, second)
        self.assertLessEqual(first.schedule.interval_days, 180)

    def test_fsrs_queue_round_trip_preserves_precision(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ReviewShardStore(Path(temp_dir))
            original = FsrsAlgorithm().advance(
                _item(), _completion(date(2026, 10, 1), "partial")
            )
            store.write([original])
            loaded = store.load()[0]
            self.assertEqual(loaded.schedule.stability, original.schedule.stability)
            self.assertEqual(loaded.schedule.difficulty, original.schedule.difficulty)
            self.assertEqual(loaded.schedule.fsrs_reviewed_on, date(2026, 10, 1))

    def test_existing_ladder_shard_round_trip_is_byte_stable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source_store = ReviewShardStore(Path(temp_dir) / "source")
            target_store = ReviewShardStore(Path(temp_dir) / "target")
            source_store.write([_item()])
            source_shard = source_store.root / source_store._manifest().shards[0].path
            target_store.write(source_store.load())
            target_shard = target_store.root / target_store._manifest().shards[0].path
            self.assertEqual(target_shard.read_bytes(), source_shard.read_bytes())

    def test_storage_rejects_fsrs_fields_on_ladder_model(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ReviewShardStore(Path(temp_dir))
            malformed = replace(_item(), schedule=replace(_item().schedule, stability=2.0))
            with self.assertRaises(ContractError) as caught:
                store.write([malformed])
            self.assertIn("schedule.stability", caught.exception.path)
