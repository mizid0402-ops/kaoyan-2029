from __future__ import annotations

import contextlib
import dataclasses
import io
import json
import math
import os
import subprocess
import sys
import tempfile
import types
import unittest
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

import yaml

from ky.freeze import FreezeEvent, FreezePolicy, assess_freeze, latch_active
from ky.models import ContractError, load_config, load_review_items
from ky.planner import port
from ky.storage.review_shards import ReviewShardStore
from ky.storage.day_plan_store import DayPlanStore, StorageError
from ky.workspace import WORKSPACE_FILENAME, load_workspace
from tests._fixtures import LegacyConfigView, git_source

ROOT = Path(__file__).resolve().parents[2]
BASELINE = "6f91af13bc5118ef2242797f088df51b6be9935c"
CONFIG_SOURCE = ROOT / "tests" / "fixtures" / "config" / "config-minimal.yaml"


def _rename_legacy_key(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            ("default_daily_minutes" if key == "total_daily_minutes" else key):
            _rename_legacy_key(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_rename_legacy_key(item) for item in value]
    return value
REVIEWS_SOURCE = ROOT / "tests" / "fixtures" / "reviews" / "reviews-normal.yaml"
DAY = date(2026, 9, 15)


class FreezePortContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.config_path = self.root / "config.yaml"
        self.config_path.write_bytes(CONFIG_SOURCE.read_bytes())
        self.config = load_config(self.config_path)
        self.base_items = load_review_items(REVIEWS_SOURCE)
        workspace_doc = {
            "schema_version": 2,
            "subjects": {
                subject.subject_id: {"name": subject.display_name}
                for subject in self.config.subjects
            },
            "reference": {
                "knowledge_trees": {}, "exam_indexes": {}, "paper_shapes": {},
                "topic_weights": "data/weights.json", "weight_batches": "data/batches.yaml",
                "vocabulary_db": "data/vocabulary.sqlite", "ledger": "data/ledger.yaml",
            },
            "supplementary": {}, "materials": {"raw_root": "data/raw"},
            "products": {}, "settings": {"exam_config": "config.yaml"},
            "state": {
                "review_queue": "data/review_queue", "plans": "data/plans",
            },
            "staging": "staging", "projection": "data/projection.sqlite",
        }
        self.workspace_path = self.root / WORKSPACE_FILENAME
        self.workspace_path.write_text(
            yaml.safe_dump(workspace_doc, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        self.workspace = load_workspace(self.workspace_path)

    def _overdue_items(self, *, minutes: int | None = None) -> tuple:
        cap = self.config.review_hard_cap_minutes()
        base = self.base_items[0]
        item_minutes = min(cap, base.estimated_minutes) if minutes is None else minutes
        threshold = FreezePolicy().backlog_days * cap
        count = max(1, math.ceil(threshold / item_minutes))
        return tuple(
            replace(
                base,
                review_id=f"{base.review_id}-freeze-{index}",
                due_date=DAY - timedelta(days=1),
                estimated_minutes=item_minutes,
            )
            for index in range(count)
        )

    def _write_queue(self, items: tuple) -> None:
        ReviewShardStore(self.workspace.review_queue).write(items)

    def _run_ky(self, *args: str) -> subprocess.CompletedProcess[bytes]:
        environment = os.environ.copy()
        current = environment.get("PYTHONPATH")
        environment["PYTHONPATH"] = (
            str(ROOT) if not current else str(ROOT) + os.pathsep + current
        )
        return subprocess.run(
            [sys.executable, "-m", "ky", *args], cwd=self.root,
            env=environment, capture_output=True, check=False,
        )

    def _preflight_args(self, *extra: str) -> tuple[str, ...]:
        return (
            "preflight", "--config", str(self.config_path), "--items",
            str(self.workspace.review_queue), "--workspace", str(self.workspace_path),
            "--date", DAY.isoformat(), *extra,
        )

    def _git_source(self, path: str) -> str:
        return git_source(self, ROOT, BASELINE, path)

    def test_assessment_threshold_and_strictly_overdue_queued_and_scheduled_count(self) -> None:
        cap = self.config.review_hard_cap_minutes()
        threshold = FreezePolicy().backlog_days * cap
        base = self.base_items[0]
        days_overdue = replace(
            base, state="queued", due_date=DAY - timedelta(days=1),
            estimated_minutes=threshold - 1,
        )
        exact = replace(days_overdue, estimated_minutes=threshold)
        ignored = (
            replace(days_overdue, state="scheduled", estimated_minutes=threshold),
            replace(days_overdue, due_date=DAY, estimated_minutes=threshold),
            replace(days_overdue, due_date=DAY + timedelta(days=1),
                    estimated_minutes=threshold),
        )

        below = assess_freeze(DAY, self.config, (days_overdue,))
        self.assertFalse(below.frozen)
        self.assertEqual(below.overdue_minutes, threshold - 1)
        self.assertTrue(assess_freeze(DAY, self.config, (exact,)).frozen)
        status = assess_freeze(DAY, self.config, (days_overdue, *ignored))
        self.assertEqual(status.overdue_count, 2)
        self.assertEqual(status.overdue_minutes, (threshold * 2) - 1)
        with self.assertRaises(ValueError):
            FreezePolicy(backlog_days=0)

    def test_zero_capacity_threshold_needs_an_overdue_item(self) -> None:
        # A tiny configured day floors the hard cap to 0; an empty backlog must not freeze.
        tiny = replace(self.config, default_daily_minutes=1)
        self.assertEqual(tiny.review_hard_cap_minutes(), 0)
        empty = assess_freeze(DAY, tiny, ())
        self.assertEqual(empty.threshold_minutes, 0)
        self.assertFalse(empty.frozen)

    def test_unfrozen_preflight_and_input_are_byte_identical_to_fixed_baseline(self) -> None:
        self._write_queue(self.base_items)
        old_main_source = self._git_source("ky/__main__.py")
        self.assertIn("--freeze-backlog-days", old_main_source)
        self.assertIn("def _reject_submission_while_frozen", old_main_source)
        self.assertNotIn("latch_active", old_main_source)
        old_main = types.ModuleType("freeze_baseline_main")
        old_main.__package__ = "ky"
        exec(compile(old_main_source, "freeze_baseline_main.py", "exec"), old_main.__dict__)

        args = self._preflight_args("--json")
        with contextlib.redirect_stdout(io.StringIO()) as current_json, \
                contextlib.redirect_stderr(io.StringIO()) as current_json_err:
            current_code = __import__("ky.__main__", fromlist=["main"]).main(
                [*args[1:]],
            )
        with contextlib.redirect_stdout(io.StringIO()) as old_json, \
                contextlib.redirect_stderr(io.StringIO()) as old_json_err:
            old_code = old_main.main([*args[1:]])
        self.assertEqual(current_code, old_code)
        self.assertEqual(
            current_json.getvalue().encode("utf-8"), old_json.getvalue().encode("utf-8"),
        )
        self.assertEqual(current_json_err.getvalue(), old_json_err.getvalue())
        self.assertNotIn("freeze", json.loads(current_json.getvalue()))

        text_args = self._preflight_args()
        with contextlib.redirect_stdout(io.StringIO()) as current_text, \
                contextlib.redirect_stderr(io.StringIO()) as current_text_err:
            current_text_code = __import__("ky.__main__", fromlist=["main"]).main(
                [*text_args[1:]],
            )
        with contextlib.redirect_stdout(io.StringIO()) as old_text, \
                contextlib.redirect_stderr(io.StringIO()) as old_text_err:
            old_text_code = old_main.main([*text_args[1:]])
        self.assertEqual(current_text_code, old_text_code)
        self.assertEqual(
            current_text.getvalue().encode("utf-8"), old_text.getvalue().encode("utf-8"),
        )
        self.assertEqual(current_text_err.getvalue(), old_text_err.getvalue())

        old_port_source = self._git_source("ky/planner/port.py")
        self.assertIn("assess_freeze", old_port_source)
        self.assertNotIn("latch_active", old_port_source)
        old_port = types.ModuleType("freeze_baseline_port")
        exec(compile(old_port_source, "freeze_baseline_port.py", "exec"), old_port.__dict__)
        old_data = old_port._build_input_data(
            DAY, LegacyConfigView(self.config).as_dataclass(), self.workspace
        )
        new_data, _ = port.planner_input_data(
            DAY, config_path=self.config_path, workspace=self.workspace,
        )
        self.assertEqual(
            port.canonical_json_bytes(new_data),
            port.canonical_json_bytes(_rename_legacy_key(old_data)),
        )

    def test_frozen_preflight_and_planner_input_share_freeze_payload(self) -> None:
        items = self._overdue_items()
        self._write_queue(items)
        preflight = self._run_ky(*self._preflight_args("--json"))
        self.assertEqual(preflight.returncode, 0, preflight.stderr.decode("utf-8"))
        payload = json.loads(preflight.stdout)
        self.assertIn("freeze", payload)
        self.assertEqual(payload["selected"], [])
        self.assertEqual(
            {entry["review_id"] for entry in payload["deferred"]},
            {item.review_id for item in items},
        )
        self.assertEqual(payload["new_learning_minutes"], 0)
        self.assertTrue(
            all(entry["new_content_minutes"] == 0 for entry in payload["subject_allocation"])
        )

        text = self._run_ky(*self._preflight_args())
        self.assertEqual(text.returncode, 0, text.stderr.decode("utf-8"))
        self.assertIn("FROZEN             : 积压", text.stdout.decode("utf-8"))

        input_path, _ = port.create_planner_input(
            DAY, config_path=self.config_path, workspace_path=self.workspace_path,
        )
        package = json.loads(input_path.read_text(encoding="utf-8"))
        preflight_clip = dict(payload)
        preflight_clip.pop("config")
        self.assertEqual(package["review_clip"], preflight_clip)
        self.assertEqual(DayPlanStore(self.workspace.plans).freeze_events(), ())

    def test_frozen_text_marks_review_limits_inactive_and_hides_timeline_phase(self) -> None:
        items = self._overdue_items()
        self._write_queue(items)
        registry = yaml.safe_load(self.workspace_path.read_text(encoding="utf-8"))
        registry["state"]["routes"] = "data/routes"
        self.workspace_path.write_text(
            yaml.safe_dump(registry, allow_unicode=True, sort_keys=False), encoding="utf-8",
        )
        phase = types.SimpleNamespace(index=1, label="阶段")
        route = types.SimpleNamespace(phases=(phase,))
        budget = types.SimpleNamespace(
            total_source="timeline", total_minutes=60,
            subject_review_quotas={self.config.active_subjects()[0].subject_id: 60},
            phase_index=1,
        )
        arguments = ["preflight", *self._preflight_args()[1:]]
        with patch("ky.__main__.RoutePlanStore", return_value=types.SimpleNamespace(
                current=lambda: route)), patch(
                "ky.__main__.resolve_day_budget", return_value=budget):
            with contextlib.redirect_stdout(io.StringIO()) as output_stream:
                result = __import__("ky.__main__", fromlist=["main"]).main(arguments)
        self.assertEqual(result, 0)
        output = output_stream.getvalue()
        self.assertIn("review soft / hard : 冻结期间不生效", output)
        self.assertNotIn("timeline phase", output)

    def test_cli_freeze_policy_usage_and_threshold_override(self) -> None:
        self._write_queue(self._overdue_items())
        invalid = self._run_ky(*self._preflight_args("--freeze-backlog-days", "0", "--json"))
        self.assertEqual(invalid.returncode, 3)

        larger = self._run_ky(*self._preflight_args(
            "--freeze-backlog-days", str(FreezePolicy().backlog_days + 1), "--json",
        ))
        self.assertEqual(larger.returncode, 0, larger.stderr.decode("utf-8"))
        self.assertNotIn("freeze", json.loads(larger.stdout))

    def test_submit_is_rejected_while_record_remains_allowed(self) -> None:
        self._write_queue(self._overdue_items())
        config = self.config
        subject_minutes = {subject.subject_id: 0 for subject in config.active_subjects()}
        plan_mapping = {
            "schema_version": 1, "day": DAY.isoformat(), "available_minutes": 0,
            "knowledge_minutes": 0, "vocab_minutes": 0, "vocab_new_items": 0,
            "phrase_minutes": 0, "backlog_minutes": 0,
            "subject_minutes": subject_minutes, "notes": "",
        }
        plan_path = self.root / "plan.yaml"
        plan_path.write_text(yaml.safe_dump(plan_mapping), encoding="utf-8")
        plan_store = self.workspace.plans

        human = self._run_ky(
            "day-plan", "submit", "--plan", str(plan_path), "--config", str(self.config_path),
            "--workspace", str(self.workspace_path), "--store", str(plan_store),
        )
        self.assertEqual(human.returncode, 2)
        self.assertIn("已冻结，请先运行 ky resume", human.stderr.decode("utf-8"))
        self.assertFalse((plan_store / "2026-09" / "day_plans_manifest.yaml").exists())

        staged_path = self.workspace.write_target("staging") / "day_plans" / "frozen.yaml"
        staged_path.parent.mkdir(parents=True, exist_ok=True)
        _, input_hash = port.create_planner_input(
            DAY, config_path=self.config_path, workspace_path=self.workspace_path,
        )
        staged_path.write_text(yaml.safe_dump({
            "schema_version": 1, "kind": "day_plan_proposal", "actor": "human",
            "input_hash": input_hash, "plan": plan_mapping,
        }), encoding="utf-8")
        staged = self._run_ky(
            "day-plan", "submit", "--from-staging", str(staged_path),
            "--config", str(self.config_path), "--workspace", str(self.workspace_path),
            "--store", str(plan_store),
        )
        self.assertEqual(staged.returncode, 2)
        self.assertIn("已冻结，请先运行 ky resume", staged.stderr.decode("utf-8"))
        self.assertFalse((plan_store / "2026-09" / "day_plans_manifest.yaml").exists())

        done_path = self.root / "done.yaml"
        done_path.write_text(yaml.safe_dump({
            "schema_version": 2, "day": DAY.isoformat(), "reviews": [],
        }), encoding="utf-8")
        record = self._run_ky(
            "day-plan", "record", "--config", str(self.config_path),
            "--done", str(done_path), "--workspace", str(self.workspace_path),
            "--store", str(plan_store),
        )
        self.assertEqual(record.returncode, 0, record.stderr.decode("utf-8"))

    def test_record_latches_freeze_until_a_resume_record(self) -> None:
        items = self._overdue_items(minutes=8)
        self.assertEqual(sum(item.estimated_minutes for item in items),
                         FreezePolicy().backlog_days * self.config.review_hard_cap_minutes())
        self._write_queue(items)
        done_path = self.root / "done.yaml"
        done_path.write_text(yaml.safe_dump({
            "schema_version": 2, "day": DAY.isoformat(),
            "reviews": [{"review_id": items[0].review_id, "completed_on": DAY.isoformat(),
                         "check": "past_question", "outcome": "correct"}],
        }), encoding="utf-8")

        recorded = self._run_ky(
            "day-plan", "record", "--config", str(self.config_path), "--done", str(done_path),
            "--workspace", str(self.workspace_path), "--review-store",
            str(self.workspace.review_queue), "--json",
        )
        self.assertEqual(recorded.returncode, 0, recorded.stderr.decode("utf-8"))
        record_payload = json.loads(recorded.stdout)
        self.assertIn(items[0].review_id, record_payload["review_queue"]["advanced_review_ids"])
        self.assertEqual(len(ReviewShardStore(self.workspace.review_queue).load()), len(items))
        updated_queue = ReviewShardStore(self.workspace.review_queue).load()
        remaining_overdue_minutes = sum(
            item.estimated_minutes for item in updated_queue
            if item.state == "queued" and item.due_date < DAY
        )
        self.assertLess(
            remaining_overdue_minutes,
            FreezePolicy().backlog_days * self.config.review_hard_cap_minutes(),
        )

        plans_store = DayPlanStore(self.workspace.plans)
        events = plans_store.freeze_events()
        self.assertEqual([(event.sequence, event.kind, event.day) for event in events],
                         [(1, "freeze", DAY)])
        record = yaml.safe_load((self.workspace.plans / "freeze" / f"000001-freeze--{DAY}.yaml")
                                .read_text(encoding="utf-8"))
        self.assertTrue(record["status"]["latched"])

        preflight = self._run_ky(*self._preflight_args("--json"))
        self.assertEqual(preflight.returncode, 0, preflight.stderr.decode("utf-8"))
        self.assertTrue(json.loads(preflight.stdout)["freeze"]["latched"])

        plan_mapping = {
            "schema_version": 1, "day": DAY.isoformat(), "available_minutes": 0,
            "knowledge_minutes": 0, "vocab_minutes": 0, "vocab_new_items": 0,
            "phrase_minutes": 0, "backlog_minutes": 0,
            "subject_minutes": {subject.subject_id: 0 for subject in self.config.active_subjects()},
            "notes": "",
        }
        plan_path = self.root / "plan.yaml"
        plan_path.write_text(yaml.safe_dump(plan_mapping), encoding="utf-8")
        submitted = self._run_ky(
            "day-plan", "submit", "--plan", str(plan_path), "--config", str(self.config_path),
            "--workspace", str(self.workspace_path),
        )
        self.assertEqual(submitted.returncode, 2)
        self.assertIn("已冻结，请先运行 ky resume", submitted.stderr.decode("utf-8"))

        plans_store.write_resume_record(DAY, {"replanned": True})
        self.assertFalse(latch_active(plans_store.freeze_events()))
        resumed = self._run_ky(*self._preflight_args("--json"))
        self.assertEqual(resumed.returncode, 0, resumed.stderr.decode("utf-8"))
        self.assertNotIn("freeze", json.loads(resumed.stdout))

    def test_freeze_gate_checks_the_final_plan_day_before_writing(self) -> None:
        from ky.schedule.longitudinal import DayPlan

        root = self.root / "gate-store"
        seen_days: list[date] = []

        def gate(day: date) -> None:
            seen_days.append(day)
            if day == DAY:
                raise StorageError("已冻结，请先运行 ky resume")

        store = DayPlanStore(root, subject_weights={
            subject.subject_id: subject.weight for subject in self.config.active_subjects()
        }, freeze_gate=gate)
        frozen_plan = DayPlan(
            day=DAY, available_minutes=0,
            subject_minutes={subject.subject_id: 0 for subject in self.config.active_subjects()},
        )
        with self.assertRaisesRegex(StorageError, "已冻结"):
            store.write_day_plan(frozen_plan)
        self.assertFalse(root.exists())

        open_day = DAY + timedelta(days=1)
        open_plan = replace(frozen_plan, day=open_day)
        store.write_day_plan(open_plan)
        self.assertEqual(seen_days, [DAY, open_day, open_day])

    def test_ordered_events_are_write_once_and_path_checked(self) -> None:
        store = DayPlanStore(self.root / "records")
        records_root = store.root / "freeze"
        store.write_freeze_record(DAY, {"threshold_minutes": 216, "latched": True})
        store.write_resume_record(DAY, {"replanned": True})
        store.write_freeze_record(DAY, {"latched": True})
        self.assertEqual(
            [(event.sequence, event.kind, event.day) for event in store.freeze_events()],
            [(1, "freeze", DAY), (2, "resume", DAY), (3, "freeze", DAY)],
        )

        misplaced = records_root / "nested" / f"000001-freeze--{DAY}.yaml"
        misplaced.parent.mkdir(parents=True)
        original = records_root / f"000001-freeze--{DAY}.yaml"
        misplaced.write_bytes(original.read_bytes())
        with self.assertRaisesRegex(StorageError, "not at its store path"):
            store.freeze_events()
        misplaced.unlink()
        mismatched = records_root / f"000001-freeze--{DAY + timedelta(days=1)}.yaml"
        mismatched.write_bytes(original.read_bytes())
        with self.assertRaisesRegex(StorageError, "not at its store path"):
            store.freeze_events()
        mismatched.unlink()
        mismatched_content = yaml.safe_load(original.read_text(encoding="utf-8"))
        mismatched_content["sequence"] = 4
        mismatched.write_text(yaml.safe_dump(mismatched_content), encoding="utf-8")
        with self.assertRaisesRegex(StorageError, "not at its store path"):
            store.freeze_events()

    def test_latch_active_resume_boundaries_and_multiple_cycles(self) -> None:
        first = DAY
        second = DAY + timedelta(days=4)
        third = DAY + timedelta(days=9)
        self.assertTrue(latch_active((
            FreezeEvent(1, "freeze", first), FreezeEvent(2, "resume", first),
            FreezeEvent(3, "freeze", first),
        )))
        self.assertTrue(latch_active((
            FreezeEvent(1, "freeze", first), FreezeEvent(2, "resume", first - timedelta(days=1)),
        )))
        self.assertFalse(latch_active((
            FreezeEvent(1, "freeze", first), FreezeEvent(2, "resume", second),
        )))
        self.assertTrue(latch_active((
            FreezeEvent(1, "freeze", first), FreezeEvent(2, "resume", second),
            FreezeEvent(3, "freeze", third), FreezeEvent(4, "resume", second),
        )))
        self.assertFalse(latch_active((
            FreezeEvent(1, "freeze", first), FreezeEvent(2, "resume", second),
            FreezeEvent(3, "freeze", third), FreezeEvent(4, "resume", third),
        )))

    def test_link_race_does_not_overwrite_the_other_writer(self) -> None:
        store = DayPlanStore(self.root / "race")
        target = store.root / "freeze" / f"000001-freeze--{DAY}.yaml"
        sentinel = b"first-writer-sentinel"
        original_link = os.link

        def competing_link(source, destination, *args, **kwargs):
            Path(destination).write_bytes(sentinel)
            return original_link(source, destination, *args, **kwargs)

        with patch("ky.storage.day_plan_store.os.link", side_effect=competing_link):
            with self.assertRaisesRegex(StorageError, "序号已被占用，请重试"):
                store.write_freeze_record(DAY, {"latched": True})
        self.assertEqual(target.read_bytes(), sentinel)

    def test_same_day_resume_then_refreeze_is_an_ordered_second_cycle(self) -> None:
        items = self._overdue_items(minutes=8)
        self._write_queue(items)
        plans = DayPlanStore(self.workspace.plans)
        plans.write_freeze_record(DAY, {"latched": True})
        plans.write_resume_record(DAY, {"replanned": True})
        done_path = self.root / "same-day-done.yaml"
        done_path.write_text(yaml.safe_dump({
            "schema_version": 2, "day": DAY.isoformat(),
            "reviews": [{"review_id": items[0].review_id, "completed_on": DAY.isoformat(),
                         "check": "past_question", "outcome": "correct"}],
        }), encoding="utf-8")

        recorded = self._run_ky(
            "day-plan", "record", "--config", str(self.config_path), "--done", str(done_path),
            "--workspace", str(self.workspace_path), "--review-store",
            str(self.workspace.review_queue), "--json",
        )
        self.assertEqual(recorded.returncode, 0, recorded.stderr.decode("utf-8"))
        events = plans.freeze_events()
        self.assertEqual([event.kind for event in events], ["freeze", "resume", "freeze"])
        preflight = self._run_ky(*self._preflight_args("--json"))
        self.assertEqual(preflight.returncode, 0, preflight.stderr.decode("utf-8"))
        self.assertTrue(json.loads(preflight.stdout)["freeze"]["latched"])


if __name__ == "__main__":
    unittest.main()
