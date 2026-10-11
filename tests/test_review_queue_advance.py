"""Regression locks for round-38 residual A: a CompletionEvent must actually advance the review
queue, not just get recorded as a historical fact.

Round-37 built ``advance_review_item`` (the pure function) and ``DayPlanStore.write_completion_event``
(the historical record) but never connected them to ``ReviewShardStore`` -- so the queue stayed
dead and ``review_clip.select_daily_reviews`` kept operating as if nothing was ever completed.
``ky.storage.day_plan_store.advance_review_queue`` is the missing wire; these tests prove it
actually moves the queue, not just that the underlying pure function returns the right value.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch
from datetime import date, timedelta
from pathlib import Path

import yaml

from ky.models import validate_review_item
from ky.schedule.completion import CompletionEvent, LadderSm2Algorithm, ReviewCompletion
from ky.storage.day_plan_store import (
    StorageError,
    advance_review_queue,
    preflight_review_queue,
    upgrade_legacy_queue,
)
from ky.storage.review_shards import ReviewShardStore
from ky.storage.review_shards import StorageError as ReviewStorageError


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.is_dir():
        return digest.hexdigest()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode("utf-8"))
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _mark_manifest_schema_one(store: ReviewShardStore) -> None:
    manifest = yaml.safe_load(store.manifest_path.read_text(encoding="utf-8"))
    manifest["schema_version"] = 1
    manifest.pop("calculated_completion_ids", None)
    payload = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    manifest["manifest_sha256"] = hashlib.sha256(canonical).hexdigest()
    store.manifest_path.write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
    )


def make_item(review_id: str, **overrides) -> dict:
    mapping = {
        "review_id": review_id,
        "revision": 1,
        "subject_id": "math1",
        "knowledge_point_id": f"math1.demo.{review_id}",
        "title": "demo",
        "granularity": "concept",
        "state": "queued",
        "estimated_minutes": 10,
        "introduced_on": "2026-09-01",
        "due_date": "2026-09-12",
        "schedule": {
            "mode": "fixed_bootstrap",
            "phase": 0,
            "interval_days": 1,
            "ease_factor": 2.5,
            "repetitions": 0,
            "lapses": 0,
        },
        "defer_count": 0,
        "last_quality": None,
    }
    mapping.update(overrides)
    return mapping


class EndToEndAdvanceTest(unittest.TestCase):
    """Standard 1: build a queue, submit a completion, read the queue back and see the change."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.store = ReviewShardStore(self.root)
        self.store.write([
            make_item("rv1"),
            make_item("rv2", subject_id="eng1", knowledge_point_id="eng1.demo.rv2"),
        ])

    def test_due_date_and_interval_actually_change_in_the_reloaded_queue(self) -> None:
        before = {item.review_id: item for item in self.store.load()}
        self.assertEqual(before["rv1"].due_date, date(2026, 9, 12))
        self.assertEqual(before["rv1"].schedule.interval_days, 1)
        self.assertIsNone(before["rv1"].last_reviewed_on)

        event = CompletionEvent(
            day=date(2026, 9, 12),
            reviews=(ReviewCompletion(review_id="rv1", completed_on=date(2026, 9, 12),
                                      check="past_question", outcome="correct"),),
        )
        report = advance_review_queue(self.store, event)
        self.assertEqual(report.advanced_review_ids, ("rv1",))
        self.assertEqual(report.replayed_review_ids, ())
        self.assertIsNotNone(report.write_report)

        # This is the crux: read the queue back from disk through a brand-new store instance,
        # not the object advance_review_queue just used -- prove it is durable, not in-memory.
        reread = {item.review_id: item for item in ReviewShardStore(self.root).load()}
        self.assertEqual(reread["rv1"].due_date, date(2026, 9, 12) + timedelta(days=2))
        self.assertEqual(reread["rv1"].schedule.interval_days, 2)
        self.assertEqual(reread["rv1"].schedule.phase, 1)
        self.assertEqual(reread["rv1"].last_reviewed_on, date(2026, 9, 12))
        self.assertEqual(reread["rv1"].last_quality, 4)
        # rv2 was not named in the completion event -- must be untouched.
        self.assertEqual(reread["rv2"].due_date, date(2026, 9, 12))
        self.assertEqual(reread["rv2"].schedule.interval_days, 1)

    def test_multiple_reviews_in_one_event_all_advance(self) -> None:
        event = CompletionEvent(
            day=date(2026, 9, 12),
            reviews=(
                ReviewCompletion(review_id="rv1", completed_on=date(2026, 9, 12),
                                 check="past_question", outcome="correct"),
                ReviewCompletion(review_id="rv2", completed_on=date(2026, 9, 12),
                                 check="exercise", outcome="incorrect"),
            ),
        )
        report = advance_review_queue(self.store, event)
        self.assertEqual(set(report.advanced_review_ids), {"rv1", "rv2"})
        reread = {item.review_id: item for item in self.store.load()}
        self.assertEqual(reread["rv1"].schedule.phase, 1)  # passed
        self.assertEqual(reread["rv2"].schedule.lapses, 1)  # failed (quality 1 < 3)
        self.assertEqual(reread["rv2"].schedule.interval_days, 1)


class IdempotencyTest(unittest.TestCase):
    """D8': completion IDs, rather than dates or qualities, define replay."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.store = ReviewShardStore(self.root)
        self.store.write([make_item("rv1")])

    def test_same_completion_applied_twice_leaves_the_queue_identical_to_applying_once(self) -> None:
        event = CompletionEvent(
            day=date(2026, 9, 12),
            reviews=(ReviewCompletion(review_id="rv1", completed_on=date(2026, 9, 12),
                                      check="past_question", outcome="correct"),),
        )
        first = advance_review_queue(self.store, event)
        self.assertEqual(first.advanced_review_ids, ("rv1",))
        after_first = self.store.load()
        manifest_after_first = (self.root / "manifest.yaml").read_bytes()

        second = advance_review_queue(self.store, event)
        self.assertEqual(second.advanced_review_ids, ())
        self.assertEqual(second.replayed_review_ids, ("rv1",))
        self.assertIsNone(second.write_report)  # no write happened at all

        after_second = self.store.load()
        self.assertEqual(after_first, after_second)
        # Not merely "same content" -- literally untouched: no new manifest version was cut.
        self.assertEqual((self.root / "manifest.yaml").read_bytes(), manifest_after_first)

        # A different, later completion on the same item is a *new* fact and must still advance.
        third_event = CompletionEvent(
            day=date(2026, 9, 14),
            reviews=(ReviewCompletion(review_id="rv1", completed_on=date(2026, 9, 14),
                                      check="past_question", outcome="correct"),),
        )
        third = advance_review_queue(self.store, third_event)
        self.assertEqual(third.advanced_review_ids, ("rv1",))

    def test_two_different_same_day_completions_both_advance(self) -> None:
        event = CompletionEvent(
            day=date(2026, 9, 12),
            reviews=tuple(ReviewCompletion("rv1", date(2026, 9, 12),
                                           "past_question", "correct") for _ in range(2)),
        )
        report = advance_review_queue(self.store, event)
        self.assertEqual(report.advanced_review_ids, ("rv1", "rv1"))
        self.assertEqual(len(self.store.calculated_completion_ids()), len(event.reviews))
        self.assertEqual(self.store.load()[0].schedule.repetitions, len(event.reviews))

    def test_older_completion_advances_and_last_reviewed_date_does_not_retreat(self) -> None:
        newer = CompletionEvent(
            day=date(2026, 9, 14),
            reviews=(ReviewCompletion("rv1", date(2026, 9, 14), "past_question", "correct"),),
        )
        advance_review_queue(self.store, newer)
        late = CompletionEvent(
            day=date(2026, 9, 15),
            reviews=(ReviewCompletion("rv1", date(2026, 9, 12), "past_question", "partial"),),
        )
        report = advance_review_queue(self.store, late)
        self.assertEqual(report.advanced_review_ids, ("rv1",))
        self.assertEqual(report.late_review_ids, ("rv1",))
        self.assertEqual(self.store.load()[0].last_reviewed_on, date(2026, 9, 14))

    def test_queue_and_completion_ids_stay_unchanged_if_write_fails(self) -> None:
        before_items = self.store.load()
        before_ids = self.store.calculated_completion_ids()
        before_manifest = (self.root / "manifest.yaml").read_bytes()
        event = CompletionEvent(
            day=date(2026, 9, 12),
            reviews=(ReviewCompletion("rv1", date(2026, 9, 12), "none"),),
        )
        with patch.object(self.store, "write", side_effect=OSError("interrupted")):
            with self.assertRaises(OSError):
                advance_review_queue(self.store, event)
        self.assertEqual(self.store.load(), before_items)
        self.assertEqual(self.store.calculated_completion_ids(), before_ids)
        self.assertEqual((self.root / "manifest.yaml").read_bytes(), before_manifest)

    def test_schema_one_reviewed_item_cannot_be_replayed_as_a_new_advance(self) -> None:
        event = CompletionEvent(
            day=date(2026, 9, 12),
            reviews=(ReviewCompletion("rv1", date(2026, 9, 12), "none",
                                      completion_id="first"),),
        )
        advance_review_queue(self.store, event)
        _mark_manifest_schema_one(self.store)
        with self.assertRaises(StorageError) as ctx:
            advance_review_queue(self.store, event)
        self.assertIn("旧版队列无已计算记录，无法保证只算一次；请先升级队列",
                      str(ctx.exception))

    def test_schema_one_unreviewed_item_advances_and_writes_schema_two(self) -> None:
        _mark_manifest_schema_one(self.store)
        event = CompletionEvent(
            day=date(2026, 9, 12),
            reviews=(ReviewCompletion("rv1", date(2026, 9, 12), "none",
                                      completion_id="first"),),
        )
        report = advance_review_queue(self.store, event)
        self.assertEqual(report.advanced_review_ids, ("rv1",))
        self.assertEqual(self.store.manifest_schema_version(), 2)
        self.assertEqual(self.store.calculated_completion_ids(), frozenset({"first"}))

    def test_schema_one_mixed_queue_refuses_fresh_item_and_direct_writes(self) -> None:
        # sol round 60, C2: advancing fresh rv2 used to upgrade the manifest, after which the
        # old rv1 completion replayed as new.
        first = CompletionEvent(
            day=date(2026, 9, 12),
            reviews=(ReviewCompletion("rv1", date(2026, 9, 12), "none",
                                      completion_id="old-rv1"),),
        )
        advance_review_queue(self.store, first)
        _mark_manifest_schema_one(self.store)
        before_manifest = self.store.manifest_path.read_bytes()
        fresh = CompletionEvent(
            day=date(2026, 9, 13),
            reviews=(ReviewCompletion("rv2", date(2026, 9, 13), "none",
                                      completion_id="new-rv2"),),
        )
        for attempt in (lambda: preflight_review_queue(self.store, fresh),
                        lambda: advance_review_queue(self.store, fresh)):
            with self.assertRaises(StorageError):
                attempt()
        with self.assertRaises(ReviewStorageError):
            self.store.upsert(make_item("rv3"))
        self.assertEqual(self.store.manifest_path.read_bytes(), before_manifest)

    def test_explicit_legacy_upgrade_starts_with_empty_calculated_ids(self) -> None:
        advance_review_queue(self.store, CompletionEvent(
            day=date(2026, 9, 12),
            reviews=(ReviewCompletion("rv1", date(2026, 9, 12), "none",
                                      completion_id="historic"),),
        ))
        _mark_manifest_schema_one(self.store)
        with self.assertRaises(ReviewStorageError):
            upgrade_legacy_queue(self.store, acknowledge_unknown_history=False)
        upgrade_legacy_queue(self.store, acknowledge_unknown_history=True)
        self.assertEqual(self.store.manifest_schema_version(), 2)
        self.assertEqual(self.store.calculated_completion_ids(), frozenset())

    def test_manifest_replace_failure_preserves_old_manifest_and_ids(self) -> None:
        before_manifest = self.store.manifest_path.read_bytes()
        before_ids = self.store.calculated_completion_ids()
        event = CompletionEvent(
            day=date(2026, 9, 12),
            reviews=(ReviewCompletion("rv1", date(2026, 9, 12), "none",
                                      completion_id="not-committed"),),
        )
        original_replace = __import__("os").replace

        def fail_manifest_replace(source, destination):
            if Path(destination) == self.store.manifest_path:
                raise OSError("manifest replacement failed")
            return original_replace(source, destination)

        with patch("ky.storage.review_shards.os.replace", side_effect=fail_manifest_replace):
            with self.assertRaises(OSError):
                advance_review_queue(self.store, event)
        self.assertEqual(self.store.manifest_path.read_bytes(), before_manifest)
        self.assertEqual(self.store.calculated_completion_ids(), before_ids)

    def test_lenient_basic_self_rating_is_reported_for_checking(self) -> None:
        event = CompletionEvent(
            day=date(2026, 9, 12),
            reviews=(ReviewCompletion("rv1", date(2026, 9, 12), "none",
                                      self_rating="basic"),),
        )
        report = advance_review_queue(self.store, event,
                                      algorithm=LadderSm2Algorithm("lenient"))
        self.assertEqual(report.needs_check_review_ids, ("rv1",))

    def test_duplicate_completion_id_is_the_only_event_duplicate_error(self) -> None:
        event = CompletionEvent(
            day=date(2026, 9, 12),
            reviews=(
                ReviewCompletion("rv1", date(2026, 9, 12), "none", completion_id="same"),
                ReviewCompletion("rv1", date(2026, 9, 12), "none", completion_id="same"),
            ),
        )
        with self.assertRaises(StorageError) as ctx:
            preflight_review_queue(self.store, event)
        self.assertEqual(ctx.exception.path, "reviews[1].completion_id")


class UnknownReviewIdTest(unittest.TestCase):
    """Standard 3: an unknown review_id must error, and leave the queue byte-for-byte unchanged."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.store = ReviewShardStore(self.root)
        self.store.write([make_item("rv1")])

    def test_unknown_id_raises_and_touches_nothing(self) -> None:
        before = _tree_hash(self.root)
        event = CompletionEvent(
            day=date(2026, 9, 12),
            reviews=(ReviewCompletion(review_id="does-not-exist", completed_on=date(2026, 9, 12),
                                     check="past_question", outcome="correct"),),
        )
        with self.assertRaises(StorageError) as ctx:
            advance_review_queue(self.store, event)
        self.assertIn("does-not-exist", str(ctx.exception))
        after = _tree_hash(self.root)
        self.assertEqual(before, after)

    def test_one_bad_id_among_several_good_ones_writes_nothing_for_any_of_them(self) -> None:
        # The valid rv1 must NOT be advanced just because it happened to share an event with a
        # bad id -- the whole event is rejected together, or not at all.
        before = _tree_hash(self.root)
        event = CompletionEvent(
            day=date(2026, 9, 12),
            reviews=(
                ReviewCompletion(review_id="rv1", completed_on=date(2026, 9, 12),
                                 check="past_question", outcome="correct"),
                ReviewCompletion(review_id="ghost", completed_on=date(2026, 9, 12),
                                 check="past_question", outcome="correct"),
            ),
        )
        with self.assertRaises(StorageError):
            advance_review_queue(self.store, event)
        after = _tree_hash(self.root)
        self.assertEqual(before, after)
        reread = self.store.load()[0]
        self.assertEqual(reread.schedule.phase, 0)  # rv1 untouched
        self.assertIsNone(reread.last_reviewed_on)

    def test_empty_queue_and_a_review_completion_is_also_unknown_id(self) -> None:
        empty_root = Path(self._tmp.name) / "empty"
        empty_store = ReviewShardStore(empty_root)
        event = CompletionEvent(
            day=date(2026, 9, 12),
            reviews=(ReviewCompletion(review_id="rv1", completed_on=date(2026, 9, 12),
                                      check="past_question", outcome="correct"),),
        )
        with self.assertRaises(StorageError):
            advance_review_queue(empty_store, event)
        self.assertFalse(empty_root.exists())


class ContractRevalidationTest(unittest.TestCase):
    """Standard 4: the advanced item must still pass validate_review_item, quality 0..5."""

    def test_full_quality_sweep_round_trips_through_the_queue(self) -> None:
        for outcome in ("correct", "partial", "incorrect"):
            with self.subTest(outcome=outcome):
                with tempfile.TemporaryDirectory() as tmp:
                    store = ReviewShardStore(Path(tmp))
                    store.write([make_item("rv1", schedule={
                        "mode": "sm2_lite", "phase": 5, "interval_days": 6,
                        "ease_factor": 2.5, "repetitions": 3, "lapses": 0,
                    })])
                    event = CompletionEvent(
                        day=date(2026, 9, 12),
                        reviews=(ReviewCompletion(review_id="rv1", completed_on=date(2026, 9, 12),
                                                  check="past_question", outcome=outcome),),
                    )
                    advance_review_queue(store, event)
                    # ReviewShardStore.write() already re-validates through validate_review_items
                    # on every write and again on load(); a second explicit validate here pins the
                    # contract down independently of that internal call.
                    reread = store.load()[0]
                    validate_review_item({
                        "review_id": reread.review_id, "revision": reread.revision,
                        "subject_id": reread.subject_id, "knowledge_point_id": reread.knowledge_point_id,
                        "title": reread.title, "granularity": reread.granularity, "state": reread.state,
                        "estimated_minutes": reread.estimated_minutes,
                        "introduced_on": reread.introduced_on.isoformat(),
                        "due_date": reread.due_date.isoformat(),
                        "last_reviewed_on": reread.last_reviewed_on.isoformat() if reread.last_reviewed_on else None,
                        "schedule": {
                            "mode": reread.schedule.mode, "phase": reread.schedule.phase,
                            "interval_days": reread.schedule.interval_days,
                            "ease_factor": reread.schedule.ease_factor,
                            "repetitions": reread.schedule.repetitions, "lapses": reread.schedule.lapses,
                        },
                        "defer_count": reread.defer_count, "last_quality": reread.last_quality,
                        "self_rating": reread.last_self_rating,
                    })


class NoReviewsIsANoOpTest(unittest.TestCase):
    def test_completion_event_with_no_reviews_touches_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = ReviewShardStore(root)
            store.write([make_item("rv1")])
            before = _tree_hash(root)
            report = advance_review_queue(store, CompletionEvent(day=date(2026, 9, 12)))
            self.assertEqual(report.advanced_review_ids, ())
            self.assertIsNone(report.write_report)
            self.assertEqual(_tree_hash(root), before)


if __name__ == "__main__":
    unittest.main()
