from __future__ import annotations

import json
import io
import os
import shutil
import subprocess
import sys
import tempfile
import tarfile
import unittest
from types import SimpleNamespace
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

import yaml
from ky.availability import Availability

from ky.models import ContractError, load_config, load_review_items
from ky.freeze import FreezeStatus
from ky.__main__ import _preflight_calculate
from ky.planner import port
from ky.schedule.budget import daily_base_minutes, resolve_day_budget
from ky.schedule.planning import Phase, RoutePlan
from ky.schedule.review_clip import select_daily_reviews
from ky.schedule.review_clip import ReviewPolicy
from ky.storage.review_shards import ReviewShardStore
from ky.storage.route_store import RoutePlanStore
from ky.workspace import WORKSPACE_FILENAME, load_workspace
from tests._baseline_harness import ProcessResult, compare_runs, fixed_source, output_tree

ROOT = Path(__file__).resolve().parents[2]
CONFIG_SOURCE = ROOT / "tests" / "fixtures" / "config" / "config-minimal.yaml"
REVIEWS_SOURCE = ROOT / "tests" / "fixtures" / "reviews" / "reviews-normal.yaml"
DAY = date(2026, 9, 15)


def _rename_legacy_package_keys(package: dict[str, Any]) -> dict[str, Any]:
    """Rename only the legacy budget keys in the fixed-baseline input package."""
    normalized = dict(package)
    if "total_daily_minutes" in normalized:
        normalized["default_daily_minutes"] = normalized.pop("total_daily_minutes")
    config = normalized.get("config")
    if isinstance(config, dict) and "total_daily_minutes" in config:
        normalized_config = dict(config)
        normalized_config["default_daily_minutes"] = normalized_config.pop(
            "total_daily_minutes"
        )
        normalized["config"] = normalized_config
    return normalized


class DayBudgetPortContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.root = Path(self._temporary.name)
        self.config_path = self.root / "config.yaml"
        self.config_path.write_bytes(CONFIG_SOURCE.read_bytes())
        self.config = load_config(self.config_path)
        self.workspace_path = self._workspace(register_route=False)
        self.workspace = load_workspace(self.workspace_path)
        ReviewShardStore(self.workspace.review_queue).write(load_review_items(REVIEWS_SOURCE))

    def _workspace(
        self, *, register_route: bool, availability: bool = False, name: str = "workspace",
    ) -> Path:
        state = {"review_queue": "data/review_queue", "plans": "data/plans"}
        if register_route:
            state["routes"] = f"data/routes-{name}"
        if availability:
            state["availability"] = "data/availability.yaml"
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
            "state": state, "staging": "staging", "projection": "data/projection.sqlite",
        }
        path = self.root / f"{name}-{WORKSPACE_FILENAME}"
        path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
        return path

    def _route(
        self,
        review_minutes: dict[str, int] | None = None,
        *,
        start: date = DAY,
        end: date | None = None,
    ) -> RoutePlan:
        subjects = self.config.active_subjects()
        minutes = review_minutes or {subject.subject_id: 10 for subject in subjects}
        return RoutePlan(
            route_id="route-budget-test", revision=1, start_date=start,
            target_exam_date=end or DAY + timedelta(days=30),
            policy_version="policy-v1", stage1_input_hash="0" * 64,
            phases=(Phase(
                index=0, start=start, end_exclusive=end or DAY + timedelta(days=30),
                label="test-phase", review_minutes=minutes,
            ),),
        )

    def _store_route(self, plan: RoutePlan, workspace_path: Path | None = None) -> None:
        workspace = load_workspace(workspace_path or self.workspace_path)
        RoutePlanStore(workspace.write_target("state.routes")).write_route_plan(plan)

    def _run_preflight(self, *, workspace_path: Path, json_output: bool = True,
                       script: Path | None = None):
        command = [sys.executable, str(script)] if script else [sys.executable, "-m", "ky", "preflight"]
        command.extend([
            "--config", str(self.config_path), "--items", str(self.workspace.review_queue),
            "--workspace", str(workspace_path), "--date", DAY.isoformat(),
        ])
        if json_output:
            command.append("--json")
        environment = os.environ.copy()
        environment.pop("KY_WORKSPACE", None)
        environment["PYTHONPATH"] = str(ROOT)
        return subprocess.run(
            command, cwd=self.root, capture_output=True, check=False, env=environment,
        )

    def test_unconstrained_day_resolves_to_config_source(self) -> None:
        budget = resolve_day_budget(DAY, self.config, None, None)
        self.assertEqual(budget.total_minutes, self.config.default_daily_minutes)
        self.assertEqual(budget.total_source, "config")
        self.assertEqual(budget.base_source, "config")

    def test_base_precedence_and_fallback_source(self) -> None:
        config = replace(self.config, default_daily_minutes=180)
        initial = SimpleNamespace(start=DAY, initial=180)
        phase = Phase(
            index=0, start=DAY, end_exclusive=DAY + timedelta(days=5),
            label="base-phase", review_minutes={
                subject.subject_id: 0 for subject in self.config.active_subjects()
            }, base_daily_minutes=210,
        )
        route = replace(self._route(), phases=(phase,))
        route_day = resolve_day_budget(
            DAY, config, None, route, pacing_initial=initial,
        )
        self.assertEqual((route_day.base_minutes, route_day.base_source), (210, "route"))
        self.assertEqual((route_day.total_minutes, route_day.total_source), (210, "base"))
        class NoTimetableValue:
            def minutes_for(self, day: date, base_minutes: int) -> int | None:
                return None

        timetable_fallback = resolve_day_budget(
            DAY, config, None, route, NoTimetableValue(), pacing_initial=initial,
        )
        self.assertEqual(
            (timetable_fallback.base_minutes, timetable_fallback.total_minutes,
             timetable_fallback.total_source),
            (210, 210, "base"),
        )
        class DeductBlocks:
            def minutes_for(self, day, base_minutes):
                return base_minutes - 45

        route_timetable = resolve_day_budget(
            DAY, config, None, route, DeductBlocks(), pacing_initial=initial,
        )
        self.assertEqual((route_timetable.total_minutes, route_timetable.total_source),
                         (165, "timetable"))
        later = DAY + timedelta(days=10)
        paced = resolve_day_budget(
            later, config, None, None, pacing_initial=initial,
        )
        self.assertEqual((paced.base_minutes, paced.base_source), (180, "pacing_initial"))
        paced_timetable = resolve_day_budget(
            later, config, None, None, DeductBlocks(), pacing_initial=initial,
        )
        self.assertEqual((paced_timetable.total_minutes, paced_timetable.total_source),
                         (135, "timetable"))
        before = resolve_day_budget(
            DAY - timedelta(days=1), config, None, None,
            pacing_initial=initial,
        )
        self.assertEqual(before.base_source, "config")
        entered = resolve_day_budget(
            DAY, config, Availability({DAY: 90}), route,
            pacing_initial=initial,
        )
        self.assertEqual((entered.total_minutes, entered.total_source), (90, "availability"))
        outside = DAY + timedelta(days=40)
        route_outside = resolve_day_budget(outside, config, None, route)
        pacing_outside = resolve_day_budget(
            outside, config, None, None, pacing_initial=initial,
        )
        self.assertEqual((route_outside.total_minutes, route_outside.total_source),
                         (180, "config"))
        self.assertEqual((pacing_outside.total_minutes, pacing_outside.total_source),
                         (180, "base"))

    def test_daily_base_rejects_invalid_public_inputs_before_resolution(self) -> None:
        for day in ("2026-09-15",):
            with self.subTest(day=day), self.assertRaises(ContractError):
                daily_base_minutes(day, self.config, None)  # type: ignore[arg-type]
        for initial in (True, -1, 1.5):
            settings = SimpleNamespace(start=DAY, initial=initial)
            with self.subTest(initial=initial), self.assertRaises(ContractError):
                daily_base_minutes(DAY, self.config, None, settings)

    def test_phase_quotas_gate_regular_items_and_allow_urgent_borrowing(self) -> None:
        subjects = [subject.subject_id for subject in self.config.active_subjects()]
        math_id, other_id = subjects[:2]
        template = load_review_items(REVIEWS_SOURCE)[0]

        def item(review_id: str, subject_id: str, minutes: int, *, defer_count: int = 0):
            return replace(
                template, review_id=review_id, subject_id=subject_id,
                estimated_minutes=minutes, due_date=DAY, defer_count=defer_count,
            )

        quotas = {subject_id: 0 for subject_id in subjects}
        quotas[math_id] = 0
        quotas[other_id] = 8
        regular = item("regular-zero", math_id, 8)
        other_regular = item("regular-fit", other_id, 8)
        urgent = item("urgent-over-quota", math_id, 12, defer_count=2)
        result = select_daily_reviews(
            self.config, (regular, other_regular, urgent), DAY,
            subject_review_quotas=quotas,
        )
        self.assertEqual(set(result.selected_ids), {"regular-fit", "urgent-over-quota"})
        self.assertIn("regular-zero", result.deferred_ids)
        self.assertLessEqual(result.review_minutes, result.hard_cap_minutes)
        self.assertEqual(result.soft_target_minutes, sum(quotas.values()))

    def test_urgent_backlog_only_borrows_leftover_capacity(self) -> None:
        # D10 supplement (sol round 114): an urgent backlog in one subject must not displace
        # another subject's in-quota regular items; it may only use what the hard cap has left.
        subjects = [subject.subject_id for subject in self.config.active_subjects()]
        busy_id, calm_id = subjects[:2]
        template = load_review_items(REVIEWS_SOURCE)[0]
        hard_cap = select_daily_reviews(self.config, (), DAY).hard_cap_minutes
        half = hard_cap // 2
        quotas = {subject_id: 0 for subject_id in subjects}
        quotas[busy_id] = half
        quotas[calm_id] = hard_cap - half
        urgent_cost = half - 1
        calm_cost = (hard_cap - half) // 2

        def item(review_id: str, subject_id: str, minutes: int, due: date):
            return replace(
                template, review_id=review_id, subject_id=subject_id,
                estimated_minutes=minutes, due_date=due, defer_count=0,
            )

        overdue = DAY - timedelta(days=5)
        backlog = [item(f"urgent-{n}", busy_id, urgent_cost, overdue) for n in range(3)]
        calm = [item(f"calm-{n}", calm_id, calm_cost, DAY) for n in range(2)]
        result = select_daily_reviews(
            self.config, (*backlog, *calm), DAY, subject_review_quotas=quotas,
        )
        self.assertIn("calm-0", result.selected_ids)
        self.assertIn("calm-1", result.selected_ids)
        self.assertIn("urgent-0", result.selected_ids)
        self.assertLessEqual(result.review_minutes, hard_cap)

    def test_urgent_item_precedes_longer_overdue_regular_in_its_own_quota(self) -> None:
        # sol round 116, B1: rank alone put a longer-overdue regular item first.
        subjects = [subject.subject_id for subject in self.config.active_subjects()]
        own_id, other_id = subjects[:2]
        template = load_review_items(REVIEWS_SOURCE)[0]
        hard_cap = select_daily_reviews(self.config, (), DAY).hard_cap_minutes
        cost = 10
        quotas = {subject_id: 0 for subject_id in subjects}
        quotas[own_id] = cost
        quotas[other_id] = hard_cap - cost
        regular = replace(
            template, review_id="regular", subject_id=own_id, estimated_minutes=cost,
            due_date=DAY - timedelta(days=1), defer_count=0,
        )
        urgent = replace(
            template, review_id="urgent", subject_id=own_id, estimated_minutes=cost,
            due_date=DAY, defer_count=2,
        )
        other = replace(
            template, review_id="other", subject_id=other_id,
            estimated_minutes=hard_cap - cost, due_date=DAY, defer_count=0,
        )
        result = select_daily_reviews(
            self.config, (regular, urgent, other), DAY, subject_review_quotas=quotas,
        )
        self.assertEqual(set(result.selected_ids), {"urgent", "other"})
        self.assertIn("regular", result.deferred_ids)

    def test_raw_quotas_above_hard_cap_are_refused(self) -> None:
        subjects = [subject.subject_id for subject in self.config.active_subjects()]
        hard_cap = select_daily_reviews(self.config, (), DAY).hard_cap_minutes
        quotas = {subject_id: 0 for subject_id in subjects}
        quotas[subjects[0]] = hard_cap + 1
        with self.assertRaises(ContractError) as caught:
            select_daily_reviews(self.config, (), DAY, subject_review_quotas=quotas)
        self.assertEqual(caught.exception.path, "subject_review_quotas")

    def test_oversized_quotas_scale_to_hard_cap_deterministically(self) -> None:
        subject_ids = sorted(
            subject.subject_id for subject in self.config.active_subjects()
        )
        large = {subject_id: 2 for subject_id in subject_ids}
        large[subject_ids[-1]] = 316
        route = self._route(large)
        first = resolve_day_budget(DAY, self.config, None, route)
        second = resolve_day_budget(DAY, self.config, None, route)
        hard = select_daily_reviews(self.config, (), DAY).hard_cap_minutes
        self.assertEqual(dict(first.subject_review_quotas or {}),
                         dict(second.subject_review_quotas or {}))
        self.assertEqual(sum((first.subject_review_quotas or {}).values()), hard)
        quotas = first.subject_review_quotas or {}
        self.assertEqual(quotas[subject_ids[0]], 1)
        self.assertEqual(quotas[subject_ids[1]], 0)

    def test_availability_total_and_route_quotas_resolve_independently(self) -> None:
        workspace_path = self._workspace(register_route=True, availability=True)
        workspace = load_workspace(workspace_path)
        availability_path = workspace.write_target("state.availability")
        availability_path.parent.mkdir(parents=True, exist_ok=True)
        availability_path.write_text(
            f"schema_version: 1\ndays:\n  {DAY.isoformat()}: 60\n", encoding="utf-8",
        )
        quotas = {subject.subject_id: 20 for subject in self.config.active_subjects()}
        route = self._route(quotas)
        RoutePlanStore(workspace.write_target("state.routes")).write_route_plan(route)
        preflight = self._run_preflight(workspace_path=workspace_path)
        self.assertEqual(preflight.returncode, 0, preflight.stderr.decode("utf-8"))
        payload = json.loads(preflight.stdout)
        self.assertEqual(payload["hard_cap_minutes"], 36)
        self.assertEqual(sum(payload["subject_review_quotas"].values()), 36)

        data, _ = port.planner_input_data(
            DAY, config_path=self.config_path, workspace=workspace,
        )
        self.assertEqual(data["availability"], {"minutes": 60, "source": "availability"})
        payload.pop("config")
        self.assertEqual(data["review_clip"], payload)

    def test_timetable_total_scales_route_quotas_to_hard_cap(self) -> None:
        subjects = self.config.active_subjects()
        quotas = {subject.subject_id: 0 for subject in subjects}
        for subject in subjects[:2]:
            quotas[subject.subject_id] = 30
        route = self._route(quotas)

        class Timetable:
            def minutes_for(self, day: date, base_minutes: int) -> int:
                self.asserted = (day, base_minutes)
                return 75

        timetable = Timetable()
        budget = resolve_day_budget(
            DAY, self.config, None, route, timetable=timetable
        )

        self.assertEqual((budget.total_minutes, budget.total_source), (75, "timetable"))
        scaled_subjects = sorted(
            subject_id for subject_id, minutes in quotas.items() if minutes
        )
        self.assertEqual(
            budget.subject_review_quotas,
            {
                **{subject_id: 0 for subject_id in quotas if not quotas[subject_id]},
                scaled_subjects[0]: 23,
                scaled_subjects[1]: 22,
            },
        )
        self.assertEqual(sum((budget.subject_review_quotas or {}).values()), 45)
        self.assertEqual(timetable.asserted, (DAY, self.config.default_daily_minutes))

    # The calculation moved to M33 (contracts/today.md §1 (a)); the stubbed result has no
    # summary, so the JSON mapping step is stubbed too. Assertions are unchanged.
    @patch("ky.today.compute.preflight_to_mapping", return_value={})
    def test_preflight_floor_and_override_follow_resolved_source_and_freeze(self, _mapping) -> None:
        class Timetable:
            def minutes_for(self, day: date, base_minutes: int) -> int | None:
                return 75 if day == DAY else None

        timetable = Timetable()
        budget = replace(
            resolve_day_budget(DAY, self.config, None, None, timetable),
            total_source="base",
        )
        not_frozen = FreezeStatus(False, 0, 0, 0, 3, False)
        result = SimpleNamespace(new_learning_minutes=10)
        with patch("ky.today.compute.select_daily_reviews", return_value=result) as select:
            with patch("ky.today.compute.allocate_new_content", return_value=()) as allocate:
                _preflight_calculate(
                    self.config, (), DAY, {}, ReviewPolicy(), not_frozen, budget
                )
        self.assertEqual(select.call_args.kwargs["daily_minutes_override"], 75)
        self.assertEqual(allocate.call_args.kwargs["floor_policy"], "drop_when_short")

        frozen = replace(not_frozen, frozen=True)
        with patch("ky.today.compute.select_daily_reviews", return_value=result) as select:
            with patch("ky.today.compute.allocate_new_content", return_value=()) as allocate:
                _preflight_calculate(
                    self.config, (), DAY, {}, ReviewPolicy(), frozen, budget
                )
        self.assertEqual(select.call_args.kwargs["daily_minutes_override"], 0)
        self.assertEqual(allocate.call_args.kwargs["floor_policy"], "drop_when_short")

        outside = resolve_day_budget(
            DAY + timedelta(days=1), self.config, None, None, timetable
        )
        self.assertEqual(outside.total_source, "config")
        with patch("ky.today.compute.select_daily_reviews", return_value=result) as select:
            with patch("ky.today.compute.allocate_new_content", return_value=()) as allocate:
                _preflight_calculate(
                    self.config,
                    (),
                    DAY + timedelta(days=1),
                    {},
                    ReviewPolicy(),
                    not_frozen,
                    outside,
                )
        self.assertNotIn("daily_minutes_override", select.call_args.kwargs)
        self.assertNotIn("floor_policy", allocate.call_args.kwargs)

    def test_unregistered_pacing_outputs_match_post_merge_fixed_baseline(self) -> None:
        commit = "636bd09"
        old_main = fixed_source(
            ROOT, commit, "ky/__main__.py",
            lambda source: b"pacing_initial=None" in source
            and b"pacing_initial=pacing_settings" not in source,
        )
        self.assertIn(b"pacing_initial=None", old_main)
        self.assertNotIn(b"pacing_initial=pacing_settings", old_main)
        current_main = (ROOT / "ky/__main__.py").read_bytes()
        self.assertIn(b"pacing_initial=pacing_settings", current_main)
        self.assertNotIn(
            b"today, config, availability, route, timetable, pacing_initial=None",
            current_main,
        )
        archive = subprocess.run(
            ["git", "archive", commit, "ky"], cwd=ROOT, check=True,
            capture_output=True,
        ).stdout
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            old_root = base / "old"
            old_root.mkdir()
            with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as bundle:
                bundle.extractall(old_root, filter="data")
            seed = base / "seed"
            shutil.copytree(self.root, seed)
            workspace = base / "workspace"
            registry = str(workspace / self.workspace_path.name)
            config = str(workspace / "config.yaml")
            items = str(workspace / "data/review_queue")
            commands = (
                ["preflight", "--config", config, "--items", items,
                 "--workspace", registry, "--date", DAY.isoformat()],
                ["preflight", "--json", "--config", config, "--items", items,
                 "--workspace", registry, "--date", DAY.isoformat()],
                ["planner-input", "--kind", "day", "--date", DAY.isoformat(),
                 "--config", config, "--workspace", registry],
                ["resume", "--date", DAY.isoformat(), "--dry-run", "--config", config,
                 "--workspace", registry],
                ["timetable", "show", "--date", DAY.isoformat(), "--config", config,
                 "--workspace", registry],
            )

            def run(source: Path, arguments: list[str]):
                if workspace.exists():
                    shutil.rmtree(workspace)
                shutil.copytree(seed, workspace)
                environment = os.environ.copy()
                environment.pop("KY_WORKSPACE", None)
                environment["PYTHONPATH"] = str(source)
                process = subprocess.run(
                    [sys.executable, "-m", "ky", *arguments], cwd=workspace,
                    env=environment, capture_output=True, check=False,
                )
                return (ProcessResult(process.returncode, process.stdout, process.stderr),
                        output_tree(workspace))

            for arguments in commands:
                with self.subTest(command=arguments[0:2]):
                    result, _ = compare_runs(
                        lambda: run(old_root, arguments), lambda: run(ROOT, arguments),
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)

    def test_unregistered_m28_commands_match_dcbb5b6_bytes(self) -> None:
        commit = "dcbb5b6"
        old_budget = fixed_source(
            ROOT,
            commit,
            "ky/schedule/budget.py",
            lambda source: (
                b"def daily_base_minutes(config: KaoyanConfig) -> int:" in source
            ),
        )
        old_planning = fixed_source(
            ROOT,
            commit,
            "ky/schedule/planning.py",
            lambda source: (
                b"class Phase:" in source
                and b"review_minutes: Mapping[str, int]" in source
                and b"base_daily_minutes" not in source
            ),
        )
        self.assertIn(
            b"def daily_base_minutes(config: KaoyanConfig) -> int:", old_budget,
        )
        self.assertIn(b"review_minutes: Mapping[str, int]", old_planning)
        # The retired 20f4391 comparison also covered a registered route that has not started yet;
        # keep that case so replacing the baseline does not drop coverage (AGENTS.md 13).
        route_workspace = self._workspace(register_route=True, name="route-workspace")
        self._store_route(self._route(start=DAY + timedelta(days=2)), route_workspace)
        active_route_workspace = self._workspace(
            register_route=True, name="active-route-workspace",
        )
        self._store_route(self._route(start=DAY - timedelta(days=2)), active_route_workspace)
        archive = subprocess.run(
            ["git", "archive", commit, "ky"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        ).stdout

        with tempfile.TemporaryDirectory() as temporary:
            temp_root = Path(temporary)
            old_root = temp_root / "old-source"
            old_root.mkdir()
            with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as bundle:
                bundle.extractall(old_root, filter="data")
            self.assertEqual(
                (old_root / "ky" / "schedule" / "budget.py").read_bytes(),
                old_budget,
            )
            self.assertEqual(
                (old_root / "ky" / "schedule" / "planning.py").read_bytes(),
                old_planning,
            )
            seed = temp_root / "seed"
            shutil.copytree(self.root, seed)
            workspace = temp_root / "workspace"
            for registry_name in (
                self.workspace_path.name, route_workspace.name, active_route_workspace.name,
            ):
                with self.subTest(registry=registry_name):
                    self._compare_baseline_commands(old_root, seed, workspace, registry_name)

    def _compare_baseline_commands(
        self, old_root: Path, seed: Path, workspace: Path, registry_name: str,
    ) -> None:
        registry = str(workspace / registry_name)
        config = str(workspace / "config.yaml")
        items = str(workspace / "data" / "review_queue")
        day = DAY.isoformat()
        commands = (
            ("preflight-text", ["preflight", "--config", config, "--items", items,
                                "--workspace", registry, "--date", day]),
            ("preflight-json", ["preflight", "--json", "--config", config, "--items", items,
                                "--workspace", registry, "--date", day]),
            ("planner-input-day", ["planner-input", "--kind", "day", "--date", day,
                                    "--config", config, "--workspace", registry]),
            ("planner-input-route", ["planner-input", "--kind", "route", "--date", day,
                                      "--config", config, "--workspace", registry]),
            ("resume-dry-run", ["resume", "--date", day, "--dry-run",
                                 "--config", config, "--workspace", registry]),
            ("route-show", ["route", "show", "--workspace", registry, "--json"]),
        )

        def run(python_path: Path, arguments: list[str]):
            if workspace.exists():
                shutil.rmtree(workspace)
            shutil.copytree(seed, workspace)
            environment = os.environ.copy()
            environment.pop("KY_WORKSPACE", None)
            environment["PYTHONPATH"] = str(python_path)
            process = subprocess.run(
                [sys.executable, "-m", "ky", *arguments],
                cwd=workspace, env=environment, capture_output=True, check=False,
            )
            return (
                ProcessResult(process.returncode, process.stdout, process.stderr),
                output_tree(workspace),
            )

        for name, arguments in commands:
            with self.subTest(command=name):
                result, _ = compare_runs(
                    lambda: run(old_root, arguments), lambda: run(ROOT, arguments),
                )
                # Equal failures on both sides must not pass as "identical" (sol round 224 S1).
                if name == "route-show" and registry_name == self.workspace_path.name:
                    self.assertEqual(result.returncode, 2, result.stderr)
                else:
                    self.assertEqual(result.returncode, 0, result.stderr)

    def test_invalid_route_subject_minutes_are_preflight_contract_errors(self) -> None:
        active = [subject.subject_id for subject in self.config.active_subjects()]
        missing_subject = active[-1]
        cases = (
            (
                {subject_id: 5 for subject_id in active[:-1]}, "missing",
                f"route.phases[0].review_minutes.{missing_subject}",
            ),
            (
                {**{subject_id: 5 for subject_id in active}, "unknown": 1}, "unknown",
                "route.phases[0].review_minutes.unknown",
            ),
            (
                {**{subject_id: 5 for subject_id in active}, "politics": 1}, "inactive",
                "route.phases[0].review_minutes.politics",
            ),
        )
        workspace_path = self._workspace(register_route=True)
        for revision, (minutes, label, path) in enumerate(cases, 1):
            with self.subTest(case=label):
                self._store_route(
                    replace(self._route(minutes), revision=revision), workspace_path,
                )
                result = self._run_preflight(workspace_path=workspace_path)
                self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
                self.assertNotIn(b"Traceback", result.stderr)
                self.assertIn(b"contract violation:", result.stderr)
                self.assertIn(path.encode("utf-8"), result.stderr)

    def test_planner_review_clip_matches_preflight_with_phase_quotas(self) -> None:
        workspace_path = self._workspace(register_route=True)
        workspace = load_workspace(workspace_path)
        quotas = {subject.subject_id: 10 for subject in self.config.active_subjects()}
        RoutePlanStore(workspace.write_target("state.routes")).write_route_plan(self._route(quotas))
        data, _ = port.planner_input_data(
            DAY, config_path=self.config_path, workspace=workspace,
        )
        preflight = self._run_preflight(workspace_path=workspace_path)
        self.assertEqual(preflight.returncode, 0, preflight.stderr.decode("utf-8"))
        expected = json.loads(preflight.stdout)
        expected.pop("config")
        self.assertEqual(data["review_clip"], expected)
        self.assertEqual(data["review_clip"]["subject_review_quotas"], quotas)

    def test_input_package_reads_the_route_once(self) -> None:
        # sol round 114: a revision published between two reads must not mix into one package.
        workspace = load_workspace(self._workspace(register_route=True))
        active = [subject.subject_id for subject in self.config.active_subjects()]
        first = self._route({subject_id: 0 for subject_id in active})
        second = replace(
            self._route({subject_id: 20 for subject_id in active}), revision=2,
        )
        with patch.object(RoutePlanStore, "current", side_effect=[first, second]) as current:
            data, _ = port.planner_input_data(
                DAY, config_path=self.config_path, workspace=workspace,
            )
        self.assertEqual(current.call_count, 1)
        self.assertEqual(data["route_plan"]["revision"], first.revision)
        self.assertEqual(
            data["review_clip"]["subject_review_quotas"],
            dict(first.phases[0].review_minutes),
        )

    def test_public_clip_rejects_non_integer_quota_with_path(self) -> None:
        subject_id = self.config.active_subjects()[0].subject_id
        with self.assertRaises(ContractError) as caught:
            select_daily_reviews(
                self.config, (), DAY, subject_review_quotas={subject_id: "2"},
            )
        self.assertEqual(caught.exception.path, f"subject_review_quotas.{subject_id}")

    def test_phase_selection_is_half_open_at_both_ends(self) -> None:
        minutes = {subject.subject_id: 5 for subject in self.config.active_subjects()}
        middle = DAY + timedelta(days=2)
        exam = DAY + timedelta(days=4)
        route = RoutePlan(
            route_id="route-boundaries", revision=1, start_date=DAY, target_exam_date=exam,
            policy_version="policy-v1", stage1_input_hash="0" * 64,
            phases=(
                Phase(index=0, start=DAY, end_exclusive=middle, label="a",
                      review_minutes=minutes),
                Phase(index=1, start=middle, end_exclusive=exam, label="b",
                      review_minutes=minutes),
            ),
        )
        expected = {
            DAY - timedelta(days=1): None,
            DAY: 0,
            middle - timedelta(days=1): 0,
            middle: 1,
            exam - timedelta(days=1): 1,
            exam: None,
        }
        for day, phase_index in expected.items():
            with self.subTest(day=day.isoformat()):
                budget = resolve_day_budget(day, self.config, None, route)
                self.assertEqual(budget.phase_index, phase_index)
                self.assertEqual(budget.subject_review_quotas is None, phase_index is None)


if __name__ == "__main__":
    unittest.main()
