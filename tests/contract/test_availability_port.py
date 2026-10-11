from __future__ import annotations

import json
import os
import dataclasses
import subprocess
import sys
import tempfile
import types
import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from ky.availability import (
    Availability,
    availability_for_workspace,
    load_availability,
    resolve_daily_minutes,
)
from ky.models import ContractError, load_config, load_review_items
from ky.planner import port
from ky.schedule.budget import allocate_new_content
from ky.schedule.longitudinal import DayPlan
from ky.schedule.review_clip import select_daily_reviews
from ky.storage.day_plan_store import DayPlanStore, StorageError
from ky.storage.review_shards import ReviewShardStore
from ky.workspace import WORKSPACE_FILENAME, load_workspace
from tests._fixtures import LegacyConfigView, git_source

ROOT = Path(__file__).resolve().parents[2]
BASELINE = "79623ee630c49c74944413f43dab0032516c88c0"
CONFIG_SOURCE = ROOT / "tests" / "fixtures" / "config" / "config-minimal.yaml"
REVIEWS_SOURCE = ROOT / "tests" / "fixtures" / "reviews" / "reviews-normal.yaml"
DAY = date(2026, 9, 15)


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


class AvailabilityPortContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.config_path = self.root / "config.yaml"
        self.config_path.write_bytes(CONFIG_SOURCE.read_bytes())
        self.config = load_config(self.config_path)

    def _availability_file(self, content: str) -> Path:
        path = self.root / "availability.yaml"
        path.write_text(content, encoding="utf-8")
        return path

    def _workspace(self, *, registered: bool, create_availability: bool = True) -> Path:
        doc = {
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
            "state": {"review_queue": "data/review_queue", "plans": "data/plans"},
            "staging": "staging", "projection": "data/projection.sqlite",
        }
        if registered:
            doc["state"]["availability"] = "data/availability.yaml"
        self.workspace_path = self.root / WORKSPACE_FILENAME
        self.workspace_path.write_text(
            yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8",
        )
        if registered and create_availability:
            path = self.root / "data" / "availability.yaml"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("schema_version: 1\ndays: {}\n", encoding="utf-8")
        return self.workspace_path

    def test_valid_file_accepts_yaml_date_and_iso_string(self) -> None:
        path = self._availability_file(
            "schema_version: 1\ndays:\n  2026-09-15: 60\n  '2026-09-16': 0\n",
        )
        value = load_availability(path)
        self.assertEqual(value.days, {date(2026, 9, 15): 60, date(2026, 9, 16): 0})

    def test_format_errors_report_the_field_path(self) -> None:
        invalid = (
            ("schema_version: 1\ndays: {}\nextra: true\n", "extra"),
            ("schema_version: 1\ndays: {}\nextra: 1\n2: 3\n", "2"),
            ("schema_version: true\ndays: {}\n", "schema_version"),
            ("schema_version: 1\ndays:\n  2026-10-01: -1\n", "days.2026-10-01"),
            ("schema_version: 1\ndays:\n  2026-10-01: 1.5\n", "days.2026-10-01"),
            (
                "schema_version: 1\ndays:\n  2026-10-01T12:00:00Z: 60\n",
                "days.2026-10-01 12:00:00+00:00",
            ),
            (
                "schema_version: 1\ndays:\n  2026-10-01: 60\n  '2026-10-01': 30\n",
                "days.2026-10-01",
            ),
        )
        for content, expected_path in invalid:
            with self.subTest(expected_path=expected_path):
                with self.assertRaises(ContractError) as caught:
                    load_availability(self._availability_file(content))
                self.assertEqual(caught.exception.path, expected_path)

    def test_mixed_top_level_keys_are_contract_errors_in_preflight(self) -> None:
        workspace_path = self._workspace(registered=True)
        availability_path = self.root / "data" / "availability.yaml"
        availability_path.write_text(
            "schema_version: 1\ndays: {}\nextra: 1\n2: 3\n", encoding="utf-8",
        )
        with self.assertRaises(ContractError) as caught:
            load_availability(availability_path)
        self.assertEqual(caught.exception.path, "2")

        result = self._run_preflight(workspace_path=workspace_path)
        self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
        self.assertNotIn(b"Traceback", result.stderr)

    def test_resolve_prefers_day_entry_and_falls_back_to_config(self) -> None:
        availability = Availability({DAY: 60})
        self.assertEqual(
            resolve_daily_minutes(DAY, 120, availability),
            type(resolve_daily_minutes(DAY, 120, availability))(60, "availability"),
        )
        self.assertEqual(
            resolve_daily_minutes(date(2026, 9, 16), 120, availability).minutes,
            120,
        )
        self.assertEqual(
            resolve_daily_minutes(DAY, 120, None).source,
            "config",
        )

    def test_resolve_priority_includes_derived_timetable_and_zero(self) -> None:
        class Timetable:
            def __init__(self, minutes: int | None) -> None:
                self.minutes = minutes

            def minutes_for(self, day: date, base_minutes: int) -> int | None:
                self.asserted = (day, base_minutes)
                return self.minutes

        override = Availability({DAY: 0})
        provider = Timetable(75)
        self.assertEqual(
            resolve_daily_minutes(DAY, 120, override, provider).source,
            "availability",
        )
        self.assertEqual(
            resolve_daily_minutes(DAY, 120, override, provider).minutes,
            0,
        )
        self.assertEqual(
            resolve_daily_minutes(date(2026, 9, 16), 120, None, provider),
            type(resolve_daily_minutes(DAY, 120, None))(75, "timetable"),
        )
        self.assertEqual(provider.asserted, (date(2026, 9, 16), 120))

        zero_timetable = Timetable(0)
        resolved_zero = resolve_daily_minutes(DAY, 120, None, zero_timetable)
        self.assertEqual((resolved_zero.minutes, resolved_zero.source), (0, "timetable"))

        no_value = Timetable(None)
        self.assertEqual(
            resolve_daily_minutes(DAY, 120, None, no_value).minutes,
            120,
        )

    def test_registry_requires_registered_file_and_unregistered_is_none(self) -> None:
        registered = load_workspace(self._workspace(registered=True, create_availability=False))
        with self.assertRaises(ContractError) as caught:
            availability_for_workspace(registered)
        self.assertEqual(caught.exception.path, "state.availability")

        unregistered = load_workspace(self._workspace(registered=False))
        self.assertIsNone(availability_for_workspace(unregistered))

    def test_preflight_uses_override_and_config_only_output_matches_baseline(self) -> None:
        workspace_path = self._workspace(registered=True)
        availability_path = self.root / "data" / "availability.yaml"
        availability_path.write_text(
            f"schema_version: 1\ndays:\n  {DAY.isoformat()}: 60\n", encoding="utf-8",
        )
        overridden = self._run_preflight(workspace_path=workspace_path)
        self.assertEqual(overridden.returncode, 0, overridden.stderr.decode("utf-8"))
        payload = json.loads(overridden.stdout)
        self.assertEqual(payload["hard_cap_minutes"], 36)
        self.assertEqual(payload["soft_target_minutes"], 27)
        text_output = self._run_preflight(workspace_path=workspace_path, json_output=False)
        self.assertEqual(text_output.returncode, 0, text_output.stderr.decode("utf-8"))
        self.assertIn(b"daily budget       : 60 min", text_output.stdout)

        (self.root / "data" / "availability.yaml").write_text(
            "schema_version: 1\ndays: {}\n", encoding="utf-8",
        )
        config_only = self._run_preflight()
        self.assertEqual(config_only.returncode, 0, config_only.stderr.decode("utf-8"))
        old_source = self._git_source("ky/__main__.py").replace(
            ".total_daily_minutes", ".default_daily_minutes"
        )
        self.assertIn("select_daily_reviews(config, items, today", old_source)
        self.assertNotIn("availability_for_workspace", old_source)
        baseline_script = self.root / "baseline_main.py"
        baseline_script.write_text(old_source, encoding="utf-8")
        baseline = self._run_preflight(script=baseline_script)
        self.assertEqual(baseline.returncode, 0, baseline.stderr.decode("utf-8"))
        self.assertEqual(
            config_only.stdout,
            baseline.stdout.replace(b'"total_daily_minutes"', b'"default_daily_minutes"', 1),
        )
        self.assertEqual(config_only.stderr, baseline.stderr)

        config_text = self._run_preflight(json_output=False)
        baseline_text = self._run_preflight(script=baseline_script, json_output=False)
        self.assertEqual(config_text.returncode, 0, config_text.stderr.decode("utf-8"))
        self.assertEqual(baseline_text.returncode, 0, baseline_text.stderr.decode("utf-8"))
        self.assertEqual(config_text.stdout, baseline_text.stdout)
        self.assertEqual(config_text.stderr, baseline_text.stderr)

        workspace_path.unlink()
        undiscovered = self._run_preflight()
        self.assertEqual(undiscovered.returncode, 0, undiscovered.stderr.decode("utf-8"))
        self.assertEqual(
            undiscovered.stdout,
            baseline.stdout.replace(b'"total_daily_minutes"', b'"default_daily_minutes"', 1),
        )

    def test_short_availability_budget_drops_floors_in_preflight_and_input(self) -> None:
        workspace_path = self._workspace(registered=True)
        workspace = load_workspace(workspace_path)
        ReviewShardStore(workspace.review_queue).write(load_review_items(REVIEWS_SOURCE))
        availability_path = workspace.write_target("state.availability")
        floor_total = sum(
            subject.min_daily_minutes for subject in self.config.active_subjects()
        )
        self.assertGreater(floor_total, 0)

        for minutes in (0, 30):
            with self.subTest(minutes=minutes):
                availability_path.write_text(
                    f"schema_version: 1\ndays:\n  {DAY.isoformat()}: {minutes}\n",
                    encoding="utf-8",
                )
                preflight = self._run_preflight(workspace_path=workspace_path)
                self.assertEqual(preflight.returncode, 0, preflight.stderr.decode("utf-8"))
                payload = json.loads(preflight.stdout)
                self.assertLess(payload["new_learning_minutes"], floor_total)
                preflight_allocations = payload["subject_allocation"]
                self.assertEqual(
                    sum(item["new_content_minutes"] for item in preflight_allocations),
                    payload["new_learning_minutes"],
                )

                allocations = allocate_new_content(
                    self.config,
                    payload["new_learning_minutes"],
                    floor_policy="drop_when_short",
                )
                self.assertTrue(all(item.floor_minutes == 0 for item in allocations))

                data, _ = port.planner_input_data(
                    DAY, config_path=self.config_path, workspace=workspace,
                )
                self.assertEqual(
                    sum(
                        item["new_content_minutes"]
                        for item in data["review_clip"]["subject_allocation"]
                    ),
                    data["review_clip"]["new_learning_minutes"],
                )
                input_allocations = allocate_new_content(
                    self.config,
                    data["review_clip"]["new_learning_minutes"],
                    floor_policy="drop_when_short",
                )
                self.assertTrue(
                    all(item.floor_minutes == 0 for item in input_allocations)
                )
        with self.assertRaises(ValueError):
            allocate_new_content(self.config, 0)

    def test_zero_availability_defers_fit_items_but_keeps_oversized_unschedulable(self) -> None:
        items = load_review_items(REVIEWS_SOURCE)
        due_ids = {item.review_id for item in items if item.is_due(DAY)}
        self.assertTrue(due_ids)
        clipped = select_daily_reviews(
            self.config, items, DAY, daily_minutes_override=0,
        )
        self.assertEqual(set(clipped.deferred_ids), due_ids)
        self.assertEqual(clipped.unschedulable, ())
        original_by_id = {item.review_id: item for item in items}
        for deferred in clipped.deferred:
            original = original_by_id[deferred.review_id]
            self.assertEqual(deferred.due_date, original.due_date)
            self.assertEqual(deferred.defer_count, original.defer_count + 1)

        due_item = next(item for item in items if item.review_id in due_ids)
        oversized = replace(
            due_item,
            estimated_minutes=self.config.review_hard_cap_minutes() + 1,
        )
        mutated_items = tuple(
            oversized if item.review_id == due_item.review_id else item for item in items
        )
        oversized_clip = select_daily_reviews(
            self.config, mutated_items, DAY, daily_minutes_override=0,
        )
        oversized_ids = {item.review_id for item in oversized_clip.unschedulable}
        self.assertIn(due_item.review_id, oversized_ids)
        self.assertNotIn(due_item.review_id, oversized_clip.deferred_ids)

    def test_long_availability_day_schedules_item_above_configured_cap(self) -> None:
        # sol round 109, N1: an item that fits today's larger hard cap must not be told to split.
        # Legal inputs, as sol round 110 asked: a short configured day and a normal-sized item.
        raw = yaml.safe_load(CONFIG_SOURCE.read_text(encoding="utf-8"))
        raw["default_daily_minutes"] = 30
        for subject in raw["subjects"]:
            subject["min_daily_minutes"] = 0
        short_config_path = self.root / "short-config.yaml"
        short_config_path.write_text(
            yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8",
        )
        short_config = load_config(short_config_path)
        configured_cap = short_config.review_hard_cap_minutes()
        items = load_review_items(REVIEWS_SOURCE)
        due_item = next(item for item in items if item.is_due(DAY))
        long_item = replace(due_item, estimated_minutes=configured_cap + 2)
        long_day = short_config.default_daily_minutes * 2
        clipped = select_daily_reviews(
            short_config, (long_item,), DAY, daily_minutes_override=long_day,
        )
        self.assertGreater(clipped.hard_cap_minutes, configured_cap)
        self.assertEqual(clipped.unschedulable, ())
        self.assertIn(long_item.review_id, {item.review_id for item in clipped.selected})

    def test_input_package_null_bytes_match_baseline_when_unregistered(self) -> None:
        workspace_path = self._workspace(registered=False)
        workspace = load_workspace(workspace_path)
        queue = workspace.review_queue
        ReviewShardStore(queue).write(load_review_items(REVIEWS_SOURCE))
        baseline_source = self._git_source("ky/planner/port.py")
        self.assertIn('"availability": None', baseline_source)
        baseline_module = types.ModuleType("planner_port_baseline")
        exec(compile(baseline_source, "planner_port_baseline.py", "exec"), baseline_module.__dict__)
        old = baseline_module._build_input_data(
            DAY, LegacyConfigView(self.config).as_dataclass(), workspace
        )
        current, _ = port.planner_input_data(
            DAY, config_path=self.config_path, workspace=workspace,
        )
        self.assertIsNone(current["availability"])
        self.assertEqual(
            port.canonical_json_bytes(current),
            port.canonical_json_bytes(_rename_legacy_key(old)),
        )

    def test_registered_input_package_exposes_source_and_matches_preflight_clip(self) -> None:
        workspace_path = self._workspace(registered=True)
        workspace = load_workspace(workspace_path)
        ReviewShardStore(workspace.review_queue).write(load_review_items(REVIEWS_SOURCE))
        availability_path = workspace.write_target("state.availability")
        availability_path.write_text(
            f"schema_version: 1\ndays:\n  {DAY.isoformat()}: 60\n", encoding="utf-8",
        )
        data, _ = port.planner_input_data(
            DAY, config_path=self.config_path, workspace=workspace,
        )
        self.assertEqual(data["availability"], {"minutes": 60, "source": "availability"})

        preflight = self._run_preflight(workspace_path=workspace_path)
        self.assertEqual(preflight.returncode, 0, preflight.stderr.decode("utf-8"))
        expected = json.loads(preflight.stdout)
        expected.pop("config")
        self.assertEqual(data["review_clip"], expected)

        availability_path.write_text("schema_version: 1\ndays: {}\n", encoding="utf-8")
        fallback, _ = port.planner_input_data(
            DAY, config_path=self.config_path, workspace=workspace,
        )
        self.assertEqual(fallback["availability"], {
            "minutes": self.config.default_daily_minutes, "source": "config",
        })

    def test_day_plan_guard_and_both_submit_forms_use_registered_limit(self) -> None:
        availability = Availability({DAY: 60})
        weights = {subject.subject_id: subject.weight for subject in self.config.active_subjects()}
        store = DayPlanStore(self.root / "direct", subject_weights=weights, availability=availability)
        too_large = self._plan(90)
        before = list((self.root / "direct").rglob("*")) if (self.root / "direct").exists() else []
        with self.assertRaises(StorageError) as caught:
            store.write_day_plan(too_large)
        self.assertEqual(caught.exception.path, "day_plan.available_minutes")
        after = list((self.root / "direct").rglob("*")) if (self.root / "direct").exists() else []
        self.assertEqual(before, after)
        self.assertEqual(store.write_day_plan(self._plan(60)).version, 1)
        self.assertEqual(store.write_day_plan(self._plan(45)).version, 2)
        no_entry_store = DayPlanStore(
            self.root / "no-entry", subject_weights=weights, availability=Availability({}),
        )
        self.assertEqual(no_entry_store.write_day_plan(too_large).version, 1)

        workspace_path = self._workspace(registered=True)
        workspace = load_workspace(workspace_path)
        ReviewShardStore(workspace.review_queue).write(load_review_items(REVIEWS_SOURCE))
        availability_path = workspace.write_target("state.availability")
        availability_path.write_text(
            f"schema_version: 1\ndays:\n  {DAY.isoformat()}: 60\n", encoding="utf-8",
        )
        plan_path = self.root / "plan.yaml"
        plan_path.write_text(yaml.safe_dump(self._plan_mapping(90), sort_keys=False), encoding="utf-8")
        human = self._run_day_plan(workspace_path, "--plan", plan_path)
        self.assertEqual(human.returncode, 2, human.stderr.decode("utf-8"))
        self.assertFalse(workspace.plans.exists())

        _, digest = port.create_planner_input(
            DAY, config_path=self.config_path, workspace_path=workspace_path,
        )
        staged_path = workspace.write_target("staging") / "day_plans" / "proposal.yaml"
        staged_path.parent.mkdir(parents=True, exist_ok=True)
        staged_path.write_text(yaml.safe_dump({
            "schema_version": 1, "kind": "day_plan_proposal", "actor": "human",
            "input_hash": digest, "plan": self._plan_mapping(90),
        }, sort_keys=False), encoding="utf-8")
        staged = self._run_day_plan(workspace_path, "--from-staging", staged_path)
        self.assertEqual(staged.returncode, 2, staged.stderr.decode("utf-8"))
        self.assertFalse(workspace.plans.exists())

    def _plan(self, available_minutes: int) -> DayPlan:
        knowledge_minutes = min(30, available_minutes)
        vocab_minutes = min(30, available_minutes - knowledge_minutes)
        return DayPlan(
            day=DAY, available_minutes=available_minutes,
            knowledge_minutes=knowledge_minutes, vocab_minutes=vocab_minutes,
            vocab_new_items=15,
            subject_minutes={
                "math1": int(knowledge_minutes * 0.4),
                "eng1": int(knowledge_minutes * 0.2),
                "cs408": int(knowledge_minutes * 0.4),
            },
        )

    def _plan_mapping(self, available_minutes: int) -> dict[str, object]:
        plan = self._plan(available_minutes)
        return {
            "schema_version": 1, "day": DAY.isoformat(),
            "available_minutes": available_minutes,
            "knowledge_minutes": plan.knowledge_minutes,
            "vocab_minutes": plan.vocab_minutes,
            "vocab_new_items": 15, "phrase_minutes": 0,
            "backlog_minutes": 0,
            "subject_minutes": dict(plan.subject_minutes), "notes": "",
        }

    def _run_preflight(
        self,
        *,
        workspace_path: Path | None = None,
        script: Path | None = None,
        config_path: Path | None = None,
        json_output: bool = True,
    ):
        command = (
            [sys.executable, str(script)]
            if script else [sys.executable, "-m", "ky", "preflight"]
        )
        command.extend([
            "--config", str(config_path or self.config_path), "--items", str(REVIEWS_SOURCE),
            "--date", DAY.isoformat(),
        ])
        if json_output:
            command.append("--json")
        if workspace_path is not None:
            command.extend(["--workspace", str(workspace_path)])
        environment = os.environ.copy()
        environment.pop("KY_WORKSPACE", None)
        environment["PYTHONPATH"] = str(ROOT)
        return subprocess.run(
            command, cwd=self.root, capture_output=True, check=False, env=environment,
        )

    def _run_day_plan(self, workspace_path: Path, option: str, path: Path):
        environment = os.environ.copy()
        environment.pop("KY_WORKSPACE", None)
        environment["PYTHONPATH"] = str(ROOT)
        return subprocess.run(
            [sys.executable, "-m", "ky", "day-plan", "submit", option, str(path),
             "--config", str(self.config_path), "--workspace", str(workspace_path)],
            cwd=self.root, capture_output=True, check=False, env=environment,
        )

    def _git_source(self, path: str) -> str:
        return git_source(self, ROOT, BASELINE, path)


if __name__ == "__main__":
    unittest.main()
