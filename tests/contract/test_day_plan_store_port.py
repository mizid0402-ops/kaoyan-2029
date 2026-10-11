"""M11 / M13 day-plan store port contract (``contracts/day_plan_store.md``).

Pins the store layout, day-plan file format, write-guard order, reread gate, write-once record
paths, freeze payload validation, and the implicit completion ID used by the review-queue advance
path. Behaviour already pinned by ``tests/test_day_plan_store.py``,
``tests/test_review_queue_advance.py``, ``tests.contract.test_freeze_port``,
``tests.contract.test_state_sources_port`` and ``tests.contract.test_planner_port`` is not
repeated here.
"""

from __future__ import annotations

import hashlib
import tempfile
import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path

import yaml

from ky.availability import Availability
from ky.models import load_config, load_review_items
from ky.schedule.completion import CompletionEvent, ReviewCompletion, VocabProgress
from ky.schedule.longitudinal import DayPlan
from ky.schedule.monthly_close import close_month
from ky.storage.day_plan_store import (
    DayPlanStore,
    StorageError,
    advance_review_queue,
    parse_day_plan,
    preflight_review_queue,
)
from ky.storage.review_shards import ReviewShardStore

ROOT = Path(__file__).resolve().parents[2]
CONFIG = load_config(ROOT / "tests" / "fixtures" / "config" / "config-minimal.yaml")
REVIEWS_SOURCE = ROOT / "tests" / "fixtures" / "reviews" / "reviews-normal.yaml"
WEIGHTS = {subject.subject_id: subject.weight for subject in CONFIG.active_subjects()}
DAY = date(2026, 9, 20)
EARLIER_DAY = DAY.replace(day=5)

# The documented serialisation order of a stored day-plan file (contracts/day_plan_store.md §3).
PLAN_FILE_KEYS = [
    "schema_version", "day", "available_minutes", "knowledge_minutes", "vocab_minutes",
    "vocab_new_items", "phrase_minutes", "backlog_minutes", "subject_minutes", "notes",
]
MANIFEST_ENTRY_KEYS = {"date", "path", "sha256", "version", "actor", "input_hash"}


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _snapshot(root: Path) -> dict[str, bytes]:
    """Every file under ``root`` with its bytes; temp files included on purpose."""
    if not root.exists():
        return {}
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*") if path.is_file()
    }


def _plan(day: date, *, available: int = 60, notes: str = "") -> DayPlan:
    # Zero knowledge minutes for every active subject is valid for any weight set, so the
    # fixture's subjects can change without editing these tests (AGENTS.md rule 8).
    return DayPlan(
        day=day, available_minutes=available, vocab_minutes=available // 2,
        subject_minutes={subject_id: 0 for subject_id in WEIGHTS}, notes=notes,
    )


def _month_dir(root: Path, day: date) -> Path:
    return root / f"{day.year:04d}-{day.month:02d}"


class DayPlanLayoutTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "plans"
        self.store = DayPlanStore(self.root, subject_weights=WEIGHTS)

    def test_versions_count_per_day_and_manifest_entries_are_sorted_and_exact(self) -> None:
        first = self.store.write_day_plan(_plan(DAY, notes="first"))
        earlier = self.store.write_day_plan(_plan(EARLIER_DAY))
        second = self.store.write_day_plan(
            _plan(DAY, notes="second"), actor="ai:test", input_hash="c" * 64,
        )
        self.assertEqual((first.version, earlier.version, second.version), (1, 1, 2))

        month = _month_dir(self.root, DAY)
        expected_path = month / "day_plans" / f"{DAY.isoformat()}--v2.yaml"
        self.assertEqual(second.path, expected_path.as_posix())
        self.assertEqual(second.sha256, _digest(expected_path.read_bytes()))
        self.assertTrue((month / "day_plans" / f"{DAY.isoformat()}--v1.yaml").is_file())

        manifest = yaml.safe_load(
            (month / "day_plans_manifest.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(set(manifest), {"schema_version", "days"})
        self.assertEqual(manifest["schema_version"], 2)
        self.assertEqual(
            [entry["date"] for entry in manifest["days"]],
            [EARLIER_DAY.isoformat(), DAY.isoformat()],
        )
        for entry in manifest["days"]:
            with self.subTest(date=entry["date"]):
                self.assertEqual(set(entry), MANIFEST_ENTRY_KEYS)
                self.assertEqual(
                    entry["path"], f"day_plans/{entry['date']}--v{entry['version']}.yaml",
                )
                self.assertEqual(entry["sha256"], _digest((month / entry["path"]).read_bytes()))
        current = manifest["days"][1]
        self.assertEqual(
            (current["version"], current["actor"], current["input_hash"]),
            (2, "ai:test", "c" * 64),
        )
        self.assertEqual(
            (manifest["days"][0]["actor"], manifest["days"][0]["input_hash"]),
            ("unknown", None),
        )

    def test_plan_file_uses_the_documented_fields_and_parses_back(self) -> None:
        plan = _plan(DAY, notes="round trip")
        report = self.store.write_day_plan(plan)
        stored = yaml.safe_load(Path(report.path).read_text(encoding="utf-8"))
        self.assertEqual(list(stored), PLAN_FILE_KEYS)
        self.assertEqual(stored["schema_version"], 1)
        self.assertEqual(stored["day"], DAY.isoformat())
        self.assertEqual(parse_day_plan(stored, report.path), plan)

    def test_parse_day_plan_defaults_and_field_paths(self) -> None:
        minimal = parse_day_plan({"day": DAY.isoformat()}, "plan")
        self.assertEqual(minimal, DayPlan(day=DAY, available_minutes=0))
        for raw, field_path in (
            ({"day": DAY.isoformat(), "extra": 1}, "plan.extra"),
            ({"day": DAY.isoformat(), "schema_version": 2}, "plan.schema_version"),
            ({"day": DAY.isoformat(), "subject_minutes": [1]}, "plan.subject_minutes"),
        ):
            with self.subTest(field_path=field_path):
                with self.assertRaises(StorageError) as caught:
                    parse_day_plan(raw, "plan")
                self.assertEqual(caught.exception.path, field_path)

    def test_load_day_plan_rejects_a_current_file_that_no_longer_matches_its_digest(self) -> None:
        report = self.store.write_day_plan(_plan(DAY))
        current = Path(report.path)
        current.write_bytes(current.read_bytes() + b"\n")
        with self.assertRaises(StorageError) as caught:
            self.store.load_day_plan(DAY)
        self.assertEqual(caught.exception.path, current.as_posix())


class DayPlanWriteGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "plans"

    def test_store_without_subject_weights_rejects_every_plan(self) -> None:
        store = DayPlanStore(self.root)
        empty_plan = DayPlan(day=DAY, available_minutes=0)
        with self.assertRaisesRegex(StorageError, "no active subjects"):
            store.write_day_plan(empty_plan)
        self.assertFalse(self.root.exists())

    def test_invariants_then_availability_run_before_the_freeze_gate(self) -> None:
        gate_days: list[date] = []
        allowed = _plan(DAY).available_minutes
        store = DayPlanStore(
            self.root, subject_weights=WEIGHTS,
            availability=Availability({DAY: allowed}), freeze_gate=gate_days.append,
        )
        invalid_and_too_large = replace(_plan(DAY), available_minutes=allowed + 1,
                                        backlog_minutes=-1)
        too_large = replace(_plan(DAY), available_minutes=allowed + 1)
        for plan, field_path in ((invalid_and_too_large, "day_plan"),
                                 (too_large, "day_plan.available_minutes")):
            with self.subTest(field_path=field_path):
                with self.assertRaises(StorageError) as caught:
                    store.write_day_plan(plan)
                self.assertEqual(caught.exception.path, field_path)
                self.assertEqual(gate_days, [])
        self.assertFalse(self.root.exists())

    def test_timetable_reference_does_not_become_a_store_hard_limit(self) -> None:
        declared = _plan(DAY, available=200)
        store = DayPlanStore(self.root, subject_weights=WEIGHTS)
        store.write_day_plan(declared)
        self.assertEqual(store.load_day_plan(DAY).available_minutes, 200)

        limited_root = self.root.parent / "hand-entered"
        limited = DayPlanStore(
            limited_root,
            subject_weights=WEIGHTS,
            availability=Availability({DAY: 90}),
        )
        with self.assertRaises(StorageError) as caught:
            limited.write_day_plan(declared)
        self.assertEqual(caught.exception.path, "day_plan.available_minutes")

    def test_gate_failure_on_the_temp_reread_publishes_nothing(self) -> None:
        verdicts = [None, None, None, StorageError("已冻结，请先运行 ky resume")]
        calls: list[date] = []

        def gate(day: date) -> None:
            calls.append(day)
            verdict = verdicts[len(calls) - 1]
            if verdict is not None:
                raise verdict

        store = DayPlanStore(self.root, subject_weights=WEIGHTS, freeze_gate=gate)
        store.write_day_plan(_plan(DAY, notes="kept"))
        before = _snapshot(self.root)
        with self.assertRaisesRegex(StorageError, "已冻结"):
            store.write_day_plan(_plan(DAY, notes="rejected on reread"))
        self.assertEqual(calls, [DAY] * len(verdicts))
        self.assertEqual(_snapshot(self.root), before)
        self.assertEqual(store.load_day_plan(DAY), _plan(DAY, notes="kept"))


class WriteOnceRecordTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "plans"
        self.store = DayPlanStore(self.root, subject_weights=WEIGHTS)

    def test_completion_events_and_month_close_live_in_their_month_directory(self) -> None:
        later = self.store.write_completion_event(CompletionEvent(
            day=DAY, vocab=VocabProgress(delivered_words=("later",)),
        ))
        self.store.write_completion_event(CompletionEvent(day=EARLIER_DAY))
        month = _month_dir(self.root, DAY)
        later_path = month / f"completion--{DAY.isoformat()}.yaml"
        self.assertEqual(later.path, later_path.as_posix())
        self.assertIsNone(later.version)
        self.assertEqual(later.sha256, _digest(later_path.read_bytes()))
        self.assertEqual(
            [event.day for event in self.store.load_month_completions(DAY.year, DAY.month)],
            [EARLIER_DAY, DAY],
        )
        self.assertEqual(self.store.load_month_completions(DAY.year + 1, DAY.month), ())

        closed = self.store.write_month_close(
            close_month(DAY.year, DAY.month, [_plan(DAY)], subject_weights=WEIGHTS),
        )
        self.assertEqual(closed.path, (month / "month_close.yaml").as_posix())
        self.assertIsNone(closed.version)

    def test_freeze_and_resume_payloads_must_be_mappings(self) -> None:
        for writer, field_path in ((self.store.write_freeze_record, "freeze.status"),
                                   (self.store.write_resume_record, "resume.resume")):
            with self.subTest(field_path=field_path):
                with self.assertRaises(StorageError) as caught:
                    writer(DAY, ["not", "a", "mapping"])
                self.assertEqual(caught.exception.path, field_path)
        self.assertFalse(self.root.exists())


class ReviewQueueAdvancePathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.queue_root = Path(self.temporary.name) / "queue"
        self.queue = ReviewShardStore(self.queue_root)
        self.items = load_review_items(REVIEWS_SOURCE)
        self.queue.write(self.items)
        self.day = self.items[0].due_date

    def _completion(self, review_id: str, **fields) -> ReviewCompletion:
        return ReviewCompletion(review_id, self.day, "past_question", outcome="correct",
                                **fields)

    def test_implicit_completion_id_is_day_and_index_and_preflight_writes_nothing(self) -> None:
        event = CompletionEvent(day=self.day, reviews=(
            self._completion(self.items[0].review_id),
        ))
        before = _snapshot(self.queue_root)
        preflight_review_queue(self.queue, event)
        self.assertEqual(_snapshot(self.queue_root), before)

        report = advance_review_queue(self.queue, event)
        self.assertEqual(report.advanced_review_ids, (self.items[0].review_id,))
        self.assertEqual(
            self.queue.calculated_completion_ids(), frozenset({f"{self.day.isoformat()}#0"}),
        )

    def test_duplicate_completion_id_is_reported_before_an_unknown_review_id(self) -> None:
        unknown = "-".join(item.review_id for item in self.items)
        event = CompletionEvent(day=self.day, reviews=(
            self._completion(self.items[0].review_id, completion_id="same"),
            self._completion(unknown, completion_id="same"),
        ))
        with self.assertRaises(StorageError) as caught:
            preflight_review_queue(self.queue, event)
        self.assertEqual(caught.exception.path, "reviews[1].completion_id")


if __name__ == "__main__":
    unittest.main()
