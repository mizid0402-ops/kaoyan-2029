from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import yaml

from ky.freeze import assess_freeze, freeze_to_mapping, latch_active
from ky.freeze.resume import plan_resume, resume_plan_to_mapping
from ky.models import load_config, load_review_items, scale_minutes
from ky.schedule.completion import reset_for_relearning
from ky.schedule.planning import Phase, RoutePlan
from ky.storage.day_plan_store import DayPlanStore
from ky.storage.review_shards import ReviewShardStore
from ky.workspace import WORKSPACE_FILENAME, load_workspace

ROOT = Path(__file__).resolve().parents[2]
CONFIG_SOURCE = ROOT / "tests" / "fixtures" / "config" / "config-minimal.yaml"
REVIEWS_SOURCE = ROOT / "tests" / "fixtures" / "reviews" / "reviews-normal.yaml"
DAY = date(2026, 9, 15)


class ResumePortContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.config_path = self.root / "config.yaml"
        self.config_path.write_bytes(CONFIG_SOURCE.read_bytes())
        self.config = load_config(self.config_path)
        self.items = load_review_items(REVIEWS_SOURCE)
        subjects = {
            subject.subject_id: {"name": subject.display_name}
            for subject in self.config.subjects
        }
        doc = {
            "schema_version": 2,
            "subjects": subjects,
            "reference": {
                "knowledge_trees": {}, "exam_indexes": {}, "paper_shapes": {},
                "topic_weights": "data/weights.json", "weight_batches": "data/batches.yaml",
                "vocabulary_db": "data/vocabulary.sqlite", "ledger": "data/ledger.yaml",
            },
            "supplementary": {}, "materials": {"raw_root": "data/raw"},
            "products": {}, "settings": {"exam_config": "config.yaml"},
            "state": {"review_queue": "data/review_queue", "plans": "data/plans"},
            "staging": "staging", "projection": "data/projection.sqlite",
        }
        self.registry = self.root / WORKSPACE_FILENAME
        self.registry.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
        self.workspace = load_workspace(self.registry)

    def _item(self, index: int, *, overdue_days: int = 3, minutes: int = 1,
              subject_id: str | None = None):
        base = self.items[0]
        return replace(
            base,
            review_id=f"resume-{index}",
            subject_id=subject_id or base.subject_id,
            due_date=DAY - timedelta(days=overdue_days),
            estimated_minutes=minutes,
            defer_count=4,
        )

    def test_reset_boundary_tiers_and_preserved_unmodified_items(self) -> None:
        schedule = self.items[0].schedule
        reset = reset_for_relearning(schedule)
        self.assertEqual(reset.interval_days, 1)
        self.assertEqual(reset.repetitions, 0)
        self.assertEqual(replace(reset, interval_days=schedule.interval_days,
                                 repetitions=schedule.repetitions), schedule)

        boundary = self._item(1, overdue_days=schedule.interval_days)
        forgotten = self._item(2, overdue_days=schedule.interval_days + 1)
        not_due = replace(self.items[-1], due_date=DAY + timedelta(days=1))
        plan = plan_resume(
            DAY, self.config, (boundary, forgotten, not_due),
            availability=None, route=None,
        )
        by_id = {entry.review_id: entry for entry in plan.entries}
        self.assertFalse(by_id[boundary.review_id].reset_for_relearning)
        self.assertTrue(by_id[forgotten.review_id].reset_for_relearning)
        self.assertEqual(plan.updated_items[-1], not_due)
        self.assertEqual(plan.updated_items[0].schedule, schedule)
        self.assertEqual(plan.updated_items[1].schedule, reset)
        self.assertEqual(plan.updated_items[0].defer_count, 0)
        self.assertTrue(all(
            changed.schedule.interval_days <= original.schedule.interval_days
            for original, changed in zip((boundary, forgotten, not_due), plan.updated_items)
        ))
        self.assertFalse(assess_freeze(DAY, self.config, plan.updated_items).frozen)

    def test_shared_capacity_existing_due_item_layer_order_and_determinism(self) -> None:
        base = self.items[0]
        cap = scale_minutes(self.config.default_daily_minutes, self.config.review_reserve_ratio)
        existing = replace(
            base, review_id="existing-today", due_date=DAY,
            estimated_minutes=max(0, cap - 1),
        )
        old = self._item(1, overdue_days=base.schedule.interval_days + 2, minutes=1)
        recent = self._item(2, overdue_days=1, minutes=1)
        inputs = (recent, existing, old)
        first = plan_resume(DAY, self.config, inputs, availability=None, route=None)
        again = plan_resume(DAY, self.config, inputs, availability=None, route=None)
        self.assertEqual(first, again)
        by_id = {entry.review_id: entry for entry in first.entries}
        self.assertEqual(by_id[old.review_id].new_due_date, DAY)
        self.assertGreater(by_id[recent.review_id].new_due_date, DAY)
        self.assertEqual(by_id[old.review_id].tier, "possible_forgetting")
        self.assertEqual(by_id[recent.review_id].tier, "recent_overdue")

    def test_one_timetable_provider_is_reused_across_candidate_days(self) -> None:
        capacity = scale_minutes(
            self.config.default_daily_minutes, self.config.review_reserve_ratio
        )

        class Timetable:
            def __init__(self) -> None:
                self.calls: list[tuple[date, int]] = []

            def minutes_for(self, day: date, base_minutes: int) -> int:
                self.calls.append((day, base_minutes))
                return 0 if day == DAY else base_minutes

        timetable = Timetable()
        items = (
            self._item(1, overdue_days=2, minutes=capacity),
            self._item(2, overdue_days=2, minutes=capacity),
        )
        plan = plan_resume(
            DAY,
            self.config,
            items,
            availability=None,
            route=None,
            timetable=timetable,
        )

        assigned = [entry.new_due_date for entry in plan.entries]
        self.assertEqual(assigned, [DAY + timedelta(days=1), DAY + timedelta(days=2)])
        self.assertEqual(
            timetable.calls,
            [
                (DAY, self.config.default_daily_minutes),
                (DAY + timedelta(days=1), self.config.default_daily_minutes),
                (DAY + timedelta(days=2), self.config.default_daily_minutes),
            ],
        )

    def test_registered_pacing_initial_is_passed_to_future_day_budgets(self) -> None:
        class Timetable:
            def __init__(self) -> None:
                self.calls: list[tuple[date, int]] = []

            def minutes_for(self, day: date, base_minutes: int) -> int:
                self.calls.append((day, base_minutes))
                return base_minutes

        pacing = SimpleNamespace(start=DAY, initial=180)
        timetable = Timetable()
        plan_resume(
            DAY, self.config, (self._item(1, overdue_days=2, minutes=1),),
            availability=None, route=None, timetable=timetable, pacing_initial=pacing,
        )
        self.assertTrue(timetable.calls)
        self.assertTrue(all(minutes == 180 for _, minutes in timetable.calls))

    def test_route_phase_bases_are_resolved_for_each_resume_candidate_day(self) -> None:
        subject_ids = [subject.subject_id for subject in self.config.active_subjects()]
        quotas = {subject_id: 0 for subject_id in subject_ids}
        quotas[subject_ids[0]] = 10_000
        next_day = DAY + timedelta(days=1)
        route = RoutePlan(
            route_id="route-bases", revision=1, start_date=DAY,
            target_exam_date=DAY + timedelta(days=2), policy_version="1",
            stage1_input_hash="0" * 64,
            phases=(
                Phase(
                    0, DAY, next_day, "base-180", quotas,
                    base_daily_minutes=180,
                ),
                Phase(
                    1, next_day, DAY + timedelta(days=2), "base-240", quotas,
                    base_daily_minutes=240,
                ),
            ),
        )
        item = self._item(
            1, overdue_days=3, minutes=120, subject_id=subject_ids[0],
        )
        plan = plan_resume(DAY, self.config, (item,), availability=None, route=route)
        self.assertEqual(plan.entries[0].new_due_date, next_day)
        self.assertEqual(plan.unschedulable_review_ids, ())

    def test_route_uses_independent_subject_quotas_and_marks_unfit_item(self) -> None:
        subject_ids = [subject.subject_id for subject in self.config.active_subjects()]
        first, second = subject_ids[:2]
        route = RoutePlan(
            route_id="route", revision=1, start_date=DAY,
            target_exam_date=DAY + timedelta(days=370), policy_version="1",
            stage1_input_hash="", phases=(Phase(
                0, DAY, DAY + timedelta(days=370), "phase",
                {subject_id: 2 for subject_id in subject_ids},
            ),),
        )
        items = (
            self._item(1, overdue_days=4, minutes=2, subject_id=first),
            self._item(2, overdue_days=4, minutes=2, subject_id=second),
            self._item(3, overdue_days=4, minutes=10000, subject_id=first),
        )
        plan = plan_resume(DAY, self.config, items, availability=None, route=route)
        assignment = {entry.review_id: entry.new_due_date for entry in plan.entries}
        self.assertEqual(assignment[items[0].review_id], DAY)
        self.assertEqual(assignment[items[1].review_id], DAY)
        self.assertEqual(assignment[items[2].review_id], DAY)
        self.assertIn(items[2].review_id, plan.unschedulable_review_ids)

    def test_cli_dry_run_execute_repeat_and_audit(self) -> None:
        overdue = tuple(self._item(i, overdue_days=2, minutes=1) for i in range(2))
        queue = ReviewShardStore(self.workspace.review_queue)
        queue.write(overdue)
        manifest_before = queue.manifest_path.read_bytes()
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")

        def run(*args: str) -> subprocess.CompletedProcess[bytes]:
            return subprocess.run(
                [sys.executable, "-m", "ky", "resume", "--date", DAY.isoformat(), *args,
                 "--workspace", str(self.registry)],
                cwd=self.root, env=env, capture_output=True, check=False,
            )

        dry = run("--dry-run", "--json")
        self.assertEqual(dry.returncode, 0, dry.stderr.decode("utf-8"))
        self.assertEqual(queue.manifest_path.read_bytes(), manifest_before)
        self.assertEqual(DayPlanStore(self.workspace.plans).freeze_events(), ())

        applied = run("--json")
        self.assertEqual(applied.returncode, 0, applied.stderr.decode("utf-8"))
        mapping = json.loads(applied.stdout)
        self.assertEqual(len(mapping["items"]), len(overdue))
        self.assertEqual(len(queue.load()), len(overdue))
        plans = DayPlanStore(self.workspace.plans)
        self.assertEqual([event.kind for event in plans.freeze_events()], ["resume"])
        self.assertFalse(assess_freeze(DAY, self.config, queue.load()).frozen)

        repeated = run("--json")
        self.assertEqual(repeated.returncode, 0, repeated.stderr.decode("utf-8"))
        self.assertEqual(json.loads(repeated.stdout)["items"], [])
        self.assertEqual([event.kind for event in plans.freeze_events()], ["resume"])

    def test_resume_clears_a_latch_when_nothing_is_overdue(self) -> None:
        # The learner caught up while frozen: nothing to replan, but the latch must still lift.
        queue = ReviewShardStore(self.workspace.review_queue)
        queue.write((replace(self._item(1), due_date=DAY + timedelta(days=1)),))
        plans = DayPlanStore(self.workspace.plans)
        frozen_on = DAY - timedelta(days=1)
        latched = assess_freeze(frozen_on, self.config, (), latched=True)
        plans.write_freeze_record(frozen_on, freeze_to_mapping(latched))
        self.assertTrue(latch_active(plans.freeze_events()))
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")

        def run(*args: str) -> subprocess.CompletedProcess[bytes]:
            return subprocess.run(
                [sys.executable, "-m", "ky", "resume", "--date", DAY.isoformat(), *args,
                 "--workspace", str(self.registry)],
                cwd=self.root, env=env, capture_output=True, check=False,
            )

        dry = run("--dry-run")
        self.assertEqual(dry.returncode, 0, dry.stderr.decode("utf-8"))
        self.assertTrue(latch_active(plans.freeze_events()))
        applied = run()
        self.assertEqual(applied.returncode, 0, applied.stderr.decode("utf-8"))
        self.assertFalse(latch_active(plans.freeze_events()))

        plans.write_freeze_record(DAY, {"latched": True})
        self.assertTrue(latch_active(plans.freeze_events()))
        second_resume = run()
        self.assertEqual(second_resume.returncode, 0, second_resume.stderr.decode("utf-8"))
        self.assertEqual(
            [event.kind for event in plans.freeze_events()],
            ["freeze", "resume", "freeze", "resume"],
        )
        self.assertEqual(
            [event.day for event in plans.freeze_events()],
            [frozen_on, DAY, DAY, DAY],
        )
        self.assertFalse(latch_active(plans.freeze_events()))

    def test_resume_dated_before_an_unresolved_freeze_is_rejected(self) -> None:
        # sol round 125: a back-filled --date cannot clear a later freeze, so it must not claim to.
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")

        def run(*args: str) -> subprocess.CompletedProcess[bytes]:
            return subprocess.run(
                [sys.executable, "-m", "ky", "resume", "--date", DAY.isoformat(), *args,
                 "--workspace", str(self.registry)],
                cwd=self.root, env=env, capture_output=True, check=False,
            )

        def snapshot() -> dict[str, bytes]:
            state = self.root / "data"
            return {
                path.relative_to(state).as_posix(): path.read_bytes()
                for path in sorted(state.rglob("*")) if path.is_file()
            }

        queue = ReviewShardStore(self.workspace.review_queue)
        plans = DayPlanStore(self.workspace.plans)
        frozen_on = DAY + timedelta(days=1)
        plans.write_freeze_record(frozen_on, {"latched": True})
        for queue_items in ((), (self._item(1, overdue_days=2),)):
            queue.write(queue_items)
            before = snapshot()
            for extra in (("--dry-run",), ()):
                with self.subTest(overdue=len(queue_items), args=extra):
                    result = run(*extra)
                    self.assertEqual(result.returncode, 2, result.stdout.decode("utf-8"))
                    self.assertIn(f"冻结发生在 {frozen_on.isoformat()}",
                                  result.stderr.decode("utf-8"))
                    self.assertEqual(snapshot(), before)
        self.assertTrue(latch_active(plans.freeze_events()))

        # A later freeze that has already been resumed must not block an earlier resume date.
        plans.write_resume_record(frozen_on, {"replanned": True})
        plans.write_freeze_record(DAY - timedelta(days=1), {"latched": True})
        resumed = run()
        self.assertEqual(resumed.returncode, 0, resumed.stderr.decode("utf-8"))
        self.assertFalse(latch_active(plans.freeze_events()))


if __name__ == "__main__":
    unittest.main()
