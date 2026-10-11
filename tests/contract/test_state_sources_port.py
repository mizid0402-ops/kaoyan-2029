"""M13/M26 parsed-state and same-read source-hash contracts."""

from __future__ import annotations

import hashlib
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from ky.availability.port import load_availability_with_source
from ky.models import ContractError, load_config, load_review_items
from ky.schedule.completion import CompletionEvent, VocabProgress
from ky.schedule.longitudinal import DayPlan
from ky.schedule.planning import Phase, RoutePlan
from ky.storage.day_plan_store import DayPlanRecord, DayPlanStore, StorageError
from ky.schedule.monthly_close import close_month
from ky.storage.review_shards import ReviewShardStore
from ky.storage.review_shards import StorageError as ReviewStorageError
from ky.storage.route_store import RoutePlanStore


ROOT = Path(__file__).resolve().parents[2]
CONFIG = load_config(ROOT / "tests" / "fixtures" / "config" / "config-minimal.yaml")
WEIGHTS = {subject.subject_id: subject.weight for subject in CONFIG.active_subjects()}


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _assert_each_source_read_once(test_case, read_port, source_paths):
    reads: dict[Path, int] = {}
    text_reads: dict[Path, int] = {}
    original_read_bytes = Path.read_bytes
    original_read_text = Path.read_text

    def counted_bytes(path: Path) -> bytes:
        reads[path] = reads.get(path, 0) + 1
        return original_read_bytes(path)

    def counted_text(path: Path, *args, **kwargs) -> str:
        text_reads[path] = text_reads.get(path, 0) + 1
        return original_read_text(path, *args, **kwargs)

    with patch.object(Path, "read_bytes", autospec=True, side_effect=counted_bytes):
        with patch.object(Path, "read_text", autospec=True, side_effect=counted_text):
            result = read_port()

    expected = set(source_paths(result))
    test_case.assertEqual(reads, {path: 1 for path in expected})
    test_case.assertEqual(text_reads, {})
    return result


def _next_month(day: date) -> date:
    if day.month == 12:
        return date(day.year + 1, 1, 5)
    return date(day.year, day.month + 1, 5)


def _plan(day: date, *, notes: str = "") -> DayPlan:
    portions = {key: int(weight * 60) for key, weight in WEIGHTS.items()}
    remaining = 60 - sum(portions.values())
    for subject_id in sorted(portions)[:remaining]:
        portions[subject_id] += 1
    return DayPlan(
        day=day,
        available_minutes=120,
        knowledge_minutes=60,
        vocab_minutes=60,
        vocab_new_items=15,
        subject_minutes=portions,
        notes=notes,
    )


class DayPlanSourcesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.store = DayPlanStore(self.root, subject_weights=WEIGHTS)
        self.first_day = date.today().replace(day=5)
        self.second_day = _next_month(self.first_day)

    def _populate(self) -> tuple[DayPlan, ...]:
        first = _plan(self.first_day, notes="older")
        current = _plan(self.first_day, notes="current")
        other = _plan(self.second_day)
        self.store.write_day_plan(first, actor="human")
        self.store.write_day_plan(current, actor="ai:test", input_hash="a" * 64)
        self.store.write_day_plan(other)
        for day in (self.first_day, self.second_day):
            self.store.write_completion_event(CompletionEvent(
                day=day, vocab=VocabProgress(delivered_words=(day.isoformat(),))
            ))
        self.store.write_freeze_record(self.first_day, {"reason": "test"})
        self.store.write_resume_record(self.second_day, {"reason": "test"})
        return current, other

    def test_current_plans_events_and_sources_match_their_stores(self) -> None:
        current_plans = self._populate()
        self.store.write_month_close(
            close_month(
                self.first_day.year, self.first_day.month, (current_plans[0],),
                subject_weights=WEIGHTS,
            )
        )

        result = self.store.read_state_sources()
        self.assertEqual(
            result.plans,
            tuple(
                DayPlanRecord(plan, 2 if plan.day == self.first_day else 1,
                              "ai:test" if plan.day == self.first_day else "unknown",
                              "a" * 64 if plan.day == self.first_day else None)
                for plan in current_plans
            ),
        )
        for record in result.plans:
            self.assertEqual(self.store.load_day_plan(record.plan.day), record.plan)
        self.assertEqual(
            result.completions,
            tuple(
                event
                for month in sorted({(day.year, day.month) for day in
                                     (self.first_day, self.second_day)})
                for event in self.store.load_month_completions(*month)
            ),
        )
        self.assertEqual(result.freeze_events, self.store.freeze_events())
        self.assertEqual(
            [event.kind for event in result.freeze_events], ["freeze", "resume"]
        )

        expected_sources = {}
        for path in self.root.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(self.root).as_posix()
            if (path.name == "day_plans_manifest.yaml"
                    or path.name.startswith("completion--")
                    or "freeze" in path.parts):
                expected_sources[relative] = _digest(path.read_bytes())
            elif path.name == f"{self.first_day.isoformat()}--v2.yaml":
                expected_sources[relative] = _digest(path.read_bytes())
            elif path.name == f"{self.second_day.isoformat()}--v1.yaml":
                expected_sources[relative] = _digest(path.read_bytes())
        self.assertEqual(dict(result.sources), expected_sources)
        self.assertFalse(any("--v1.yaml" in path for path in result.sources
                             if self.first_day.isoformat() in path))
        self.assertFalse(any(path.endswith("month_close.yaml") for path in result.sources))
        with self.assertRaises(TypeError):
            result.sources["unexpected.yaml"] = "0" * 64

    def test_each_month_manifest_is_read_once(self) -> None:
        self._populate()
        result = _assert_each_source_read_once(
            self, self.store.read_state_sources,
            lambda value: (self.root / relative for relative in value.sources),
        )
        manifest_paths = [
            self.root / relative for relative in result.sources
            if relative.endswith("day_plans_manifest.yaml")
        ]
        self.assertTrue(manifest_paths)
        self.assertEqual(len(manifest_paths), len(set(manifest_paths)))

    def test_misplaced_day_plan_manifest_is_rejected(self) -> None:
        misplaced = self.root / "archive" / "day_plans_manifest.yaml"
        misplaced.parent.mkdir()
        misplaced.write_bytes(b"schema_version: 2\ndays: []\n")
        with self.assertRaisesRegex(StorageError, "not at its store path"):
            self.store.read_state_sources()

    def test_misplaced_completion_event_is_rejected(self) -> None:
        self.store.write_completion_event(CompletionEvent(day=self.first_day))
        original = self.root / self.first_day.strftime("%Y-%m") / (
            f"completion--{self.first_day.isoformat()}.yaml"
        )
        misplaced = self.root / f"completion--{self.first_day.isoformat()}.yaml"
        misplaced.write_bytes(original.read_bytes())
        with self.assertRaises(StorageError):
            self.store.read_state_sources()

    def test_current_plan_hash_mismatch_is_rejected(self) -> None:
        self.store.write_day_plan(_plan(self.first_day))
        current_path = next((self.root / self.first_day.strftime("%Y-%m") /
                             "day_plans").glob("*.yaml"))
        current_path.write_bytes(current_path.read_bytes() + b"\n")
        with self.assertRaises(StorageError):
            self.store.read_state_sources()

    def test_missing_root_is_empty(self) -> None:
        result = DayPlanStore(self.root / "absent").read_state_sources()
        self.assertEqual(result.plans, ())
        self.assertEqual(result.completions, ())
        self.assertEqual(result.freeze_events, ())
        self.assertEqual(dict(result.sources), {})


class ReviewQueueSourcesTests(unittest.TestCase):
    def test_queue_sources_and_missing_manifest_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = ReviewShardStore(root, shard_size=1, bucket_count=1)
            empty = store.read_state_sources()
            self.assertEqual(empty.items, ())
            self.assertEqual(dict(empty.sources), {})

            items = load_review_items(ROOT / "tests" / "fixtures" / "reviews" /
                                     "reviews-normal.yaml")
            store.write(items)
            result = _assert_each_source_read_once(
                self, store.read_state_sources,
                lambda value: (root / relative for relative in value.sources),
            )
            self.assertEqual(result.items, store.load())
            self.assertIn("manifest.yaml", result.sources)
            self.assertEqual(
                dict(result.sources),
                {
                    path.relative_to(root).as_posix(): _digest(path.read_bytes())
                    for path in root.rglob("*.yaml") if path.is_file()
                },
            )

    def test_modified_shard_bytes_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = ReviewShardStore(root, shard_size=1, bucket_count=1)
            items = load_review_items(ROOT / "tests" / "fixtures" / "reviews" /
                                     "reviews-normal.yaml")
            store.write(items)
            import yaml

            manifest = yaml.safe_load((root / "manifest.yaml").read_text(encoding="utf-8"))
            shard_path = root / manifest["shards"][0]["path"]
            shard_path.write_bytes(shard_path.read_bytes() + b"\n# changed\n")
            with self.assertRaises(ReviewStorageError):
                store.read_state_sources()


def _route(revision: int, start: date) -> RoutePlan:
    end = start + timedelta(days=30)
    return RoutePlan(
        route_id="route-alpha",
        revision=revision,
        start_date=start,
        target_exam_date=end,
        policy_version="policy-v1",
        stage1_input_hash="a" * 64,
        phases=(Phase(
            index=0,
            start=start,
            end_exclusive=end,
            label="phase",
            review_minutes={subject.subject_id: 0 for subject in CONFIG.active_subjects()},
        ),),
    )


class RouteAndAvailabilitySourcesTests(unittest.TestCase):
    def test_current_route_only_and_empty_route(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = RoutePlanStore(root)
            empty = store.read_state_sources()
            self.assertIsNone(empty.route)
            self.assertEqual(dict(empty.sources), {})

            start = date.today() + timedelta(days=1)
            first = store.write_route_plan(_route(1, start))
            second = store.write_route_plan(_route(2, start))
            result = _assert_each_source_read_once(
                self, store.read_state_sources,
                lambda value: (root / relative for relative in value.sources),
            )
            self.assertEqual(result.route, store.current())
            self.assertEqual(result.route, _route(2, start))
            self.assertEqual(
                set(result.sources), {"routes_manifest.yaml", Path(second.path).name}
            )
            self.assertNotIn(Path(first.path).name, result.sources)
            self.assertEqual(
                dict(result.sources),
                {
                    relative: _digest((root / relative).read_bytes())
                    for relative in result.sources
                },
            )

    def test_availability_hash_and_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "availability.yaml"
            data = b"schema_version: 1\ndays: {}\n"
            path.write_bytes(data)
            result = _assert_each_source_read_once(
                self, lambda: load_availability_with_source(path), lambda _value: (path,)
            )
            self.assertEqual(result.sha256, _digest(data))
            self.assertEqual(dict(result.availability.days), {})
            with self.assertRaises(ContractError):
                load_availability_with_source(path.with_name("missing.yaml"))


class InvalidStoreRootTests(unittest.TestCase):
    """sol round 136: invalid registered state is an error, never an empty store."""

    def test_root_occupied_by_a_file_is_an_error_for_every_store(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            occupied = Path(directory) / "state"
            occupied.write_bytes(b"occupied")
            for store in (DayPlanStore(occupied), ReviewShardStore(occupied),
                          RoutePlanStore(occupied)):
                with self.subTest(store=type(store).__name__):
                    with self.assertRaisesRegex(ContractError, "not a directory"):
                        store.read_state_sources()

    def test_missing_registered_current_plan_is_a_storage_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = DayPlanStore(Path(directory) / "plans", subject_weights=WEIGHTS)
            written = store.write_day_plan(_plan(date(2026, 9, 15)))
            Path(written.path).unlink()
            with self.assertRaisesRegex(StorageError, "cannot read registered day plan"):
                store.read_state_sources()


if __name__ == "__main__":
    unittest.main()
