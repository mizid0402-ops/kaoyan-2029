from __future__ import annotations

import hashlib
import json
import os
import dataclasses
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

from ky.models import ContractError, load_config, load_review_items
from ky.planner import port
from ky.schedule.longitudinal import DayPlan
from ky.schedule.planning import (
    Phase,
    RoutePlan,
    route_plan_to_mapping,
)
from ky.__main__ import route_main
from ky.storage.day_plan_store import DayPlanStore, StorageError, WriteReport
from ky.storage.route_store import RoutePlanStore
from ky.storage.review_shards import ReviewShardStore
from ky.workspace import WORKSPACE_FILENAME, load_workspace
from tests._fixtures import LegacyConfigView

ROOT = Path(__file__).resolve().parents[2]
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
TARGET = DAY + timedelta(days=60)


class PlannerPortContractTests(unittest.TestCase):
    def test_pacing_registration_adds_resolved_base_to_availability_shape(self) -> None:
        cases = (
            (210, "base", 210, "route"),
            (0, "base", 0, "route"),
            (180, "base", 180, "pacing_initial"),
            (120, "config", 120, "config"),
        )
        for total, total_source, base, base_source in cases:
            with self.subTest(base_source=base_source, base_minutes=base):
                budget = port.DayBudget(
                    total, total_source, None, None, None, base, base_source,
                )
                self.assertEqual(
                    port._availability_mapping(
                        budget, settings_pacing_registered=True,
                    ),
                    {
                        "minutes": total, "source": total_source,
                        "base_minutes": base, "base_source": base_source,
                    },
                )
                self.assertEqual(
                    port._availability_mapping(
                        budget, settings_pacing_registered=False,
                    ),
                    {"minutes": total, "source": total_source},
                )

    def test_base_source_uses_override_and_frozen_policy_wins(self) -> None:
        budget = port.DayBudget(210, "base", None, None, None, 210, "route")
        self.assertEqual(
            port._day_clip_parameters(budget, frozen=False),
            ({"daily_minutes_override": 210}, {"floor_policy": "drop_when_short"}),
        )
        self.assertEqual(
            port._day_clip_parameters(budget, frozen=True),
            ({"daily_minutes_override": 0}, {"floor_policy": "drop_when_short"}),
        )

    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.root = Path(self._temporary.name)
        self.config_path = self.root / "config.yaml"
        self.config_path.write_bytes(CONFIG_SOURCE.read_bytes())
        config = load_config(self.config_path)
        workspace_doc = {
            "schema_version": 2,
            "subjects": {subject.subject_id: {"name": subject.display_name}
                         for subject in config.subjects},
            "reference": {
                "knowledge_trees": {}, "exam_indexes": {}, "paper_shapes": {},
                "topic_weights": "data/weights.json", "weight_batches": "data/batches.yaml",
                "vocabulary_db": "data/vocabulary.sqlite", "ledger": "data/ledger.yaml",
            },
            "supplementary": {}, "materials": {"raw_root": "data/raw"},
            "products": {}, "settings": {"exam_config": "config.yaml"},
            "state": {"review_queue": "data/review_queue", "plans": "data/plans",
                      "routes": "data/routes"},
            "staging": "staging", "projection": "data/projection.sqlite",
        }
        self.workspace_path = self.root / WORKSPACE_FILENAME
        self.workspace_path.write_text(
            yaml.safe_dump(workspace_doc, allow_unicode=True, sort_keys=False), encoding="utf-8",
        )
        self.workspace = load_workspace(self.workspace_path)
        self.queue = self.workspace.review_queue
        self.review_store = ReviewShardStore(self.queue)
        self.review_store.write(load_review_items(REVIEWS_SOURCE))
        weights = {subject.subject_id: subject.weight for subject in config.active_subjects()}
        self.store = DayPlanStore(self.workspace.plans, subject_weights=weights)
        self.staging = self.workspace.write_target("staging")
        self.proposal_dir = self.staging / "day_plans"
        self.proposal_dir.mkdir(parents=True)
        self.route_proposal_dir = self.staging / "routes"
        self.route_proposal_dir.mkdir(parents=True)
        self.route_store = RoutePlanStore(self.workspace.write_target("state.routes"))

    def _plan_mapping(self, **updates: object) -> dict[str, object]:
        config = load_config(self.config_path)
        subject_minutes = {subject.subject_id: 0 for subject in config.active_subjects()}
        data: dict[str, object] = {
            "schema_version": 1, "day": DAY.isoformat(), "available_minutes": 0,
            "knowledge_minutes": 0, "vocab_minutes": 0, "vocab_new_items": 0,
            "phrase_minutes": 0, "backlog_minutes": 0,
            "subject_minutes": subject_minutes, "notes": "",
        }
        data.update(updates)
        return data

    def _write_proposal(
        self, *, actor: str = "ai:test-model", input_hash: str | None = None,
        plan: dict[str, object] | None = None, path: Path | None = None,
    ) -> Path:
        target = path or self.proposal_dir / f"{DAY.isoformat()}--proposal.yaml"
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": 1, "kind": "day_plan_proposal", "actor": actor,
            "input_hash": input_hash, "plan": plan or self._plan_mapping(),
        }
        target.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        return target

    def _input(self) -> tuple[Path, str]:
        return port.create_planner_input(
            DAY, config_path=self.config_path, workspace_path=self.workspace_path,
        )

    def _route(
        self, digest: str, revision: int = 1, *, start: date = DAY,
        target: date = TARGET, boundaries: tuple[date, ...] = (),
    ) -> RoutePlan:
        points = (start, *boundaries, target)
        config = load_config(self.config_path)
        review_minutes = {
            subject.subject_id: 0 for subject in config.active_subjects()
        }
        review_minutes.update({"math1": 30, "eng1": 20})
        phases = tuple(
            Phase(
                index=index,
                start=start,
                end_exclusive=end,
                label=f"phase-{index}",
                review_minutes=review_minutes,
            )
            for index, (start, end) in enumerate(zip(points, points[1:]))
        )
        return RoutePlan(
            route_id="route-test", revision=revision, start_date=start,
            target_exam_date=target,
            policy_version="policy-v1", stage1_input_hash=digest, phases=phases,
        )

    def _route_input(self) -> tuple[Path, str]:
        return port.create_route_planner_input(
            DAY, config_path=self.config_path, workspace_path=self.workspace_path,
        )

    def _write_route_proposal(
        self, digest: str, *, plan: RoutePlan | None = None, kind: str = "route_proposal",
        path: Path | None = None, include_hash: bool = True,
    ) -> Path:
        target = path or self.route_proposal_dir / "route-proposal.yaml"
        payload: dict[str, object] = {
            "schema_version": 1, "kind": kind, "actor": "ai:route-agent",
            "route": route_plan_to_mapping(plan or self._route(digest)),
        }
        if include_hash:
            payload["input_hash"] = digest
        target.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        return target

    def test_input_bytes_are_stable_change_with_review_and_canonical_example(self) -> None:
        path, digest = self._input()
        first = path.read_bytes()
        second_path, second_digest = self._input()
        self.assertEqual(first, second_path.read_bytes())
        self.assertEqual(digest, second_digest)
        self.assertEqual(
            port.canonical_json_bytes({"z": "é", "a": [2]}),
            b'{"a":[2],"z":"\xc3\xa9"}',
        )

        package = json.loads(first)
        # sol round 96: compare values, not key presence, against `ky preflight --json`.
        preflight = subprocess.run(
            [sys.executable, "-m", "ky", "preflight", "--json", "--config",
             str(self.config_path), "--items", str(self.queue),
             "--workspace", str(self.workspace_path), "--date", DAY.isoformat()],
            cwd=ROOT, capture_output=True, check=False, text=True, encoding="utf-8",
        )
        self.assertEqual(preflight.returncode, 0, preflight.stderr)
        preflight_payload = json.loads(preflight.stdout)
        preflight_payload.pop("config")
        self.assertEqual(package["review_clip"], preflight_payload)
        self.assertNotIn("config", package["review_clip"])
        self.assertIn("config", package)

        items = load_review_items(REVIEWS_SOURCE)
        changed = (replace(items[0], due_date=items[0].due_date + timedelta(days=1)), *items[1:])
        self.review_store.write(changed)
        changed_path, changed_digest = self._input()
        self.assertNotEqual(digest, changed_digest)
        self.assertNotEqual(first, changed_path.read_bytes())

    def test_route_input_bytes_stable_and_current_route_is_mapping_or_null(self) -> None:
        first_path, first_hash = self._route_input()
        first_bytes = first_path.read_bytes()
        second_path, second_hash = self._route_input()
        self.assertEqual(first_bytes, second_path.read_bytes())
        self.assertEqual(first_hash, second_hash)
        self.assertIsNone(json.loads(first_bytes)["current_route"])

        unregistered_doc = yaml.safe_load(self.workspace_path.read_text(encoding="utf-8"))
        del unregistered_doc["state"]["routes"]
        unregistered_path = self.root / "unregistered-routes.workspace.yaml"
        unregistered_path.write_text(
            yaml.safe_dump(unregistered_doc, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        unregistered = load_workspace(unregistered_path)
        unregistered_data, _ = port.route_planner_input_data(
            DAY, config_path=self.config_path, workspace=unregistered,
        )
        self.assertIsNone(unregistered_data["current_route"])

        route = self._route("a" * 64)
        self.route_store.write_route_plan(route, actor="human")
        route_path, _ = self._route_input()
        self.assertEqual(
            json.loads(route_path.read_bytes())["current_route"], route_plan_to_mapping(route),
        )

    def test_day_package_reports_timetable_and_out_of_term_config_source(self) -> None:
        registry = yaml.safe_load(self.workspace_path.read_text(encoding="utf-8"))
        school_target = self.root / "data" / "timetable_schools" / "demo_school.yaml"
        timetable_target = self.root / "data" / "course_schedule" / "timetable.yaml"
        school_target.parent.mkdir(parents=True, exist_ok=True)
        timetable_target.parent.mkdir(parents=True, exist_ok=True)
        school_target.write_text(
            "schema_version: 1\nschool_id: demo_school\nname: Demo School\nsystem: demo\n"
            "source:\n  kind: official\n  recorded_on: 2026-09-30\n"
            "periods:\n  1: {start: '08:00', end: '08:45'}\nblocks: [[1]]\n",
            encoding="utf-8",
        )
        timetable_target.write_text(
            "schema_version: 1\nrules:\n  study_window: {start: '08:00', end: '22:00'}\n"
            "  buffer_minutes: 0\n  min_gap_minutes: 0\n"
            "  block_deduction_minutes: 0\n  daily_cap_minutes: 75\n"
            "semesters:\n  - label: test\n    school: demo_school\n"
            "    week1_monday: 2025-09-01\n    weeks: 1\n    courses: []\n",
            encoding="utf-8",
        )
        registry["reference"]["timetable_schools"] = {
            "demo_school": school_target.relative_to(self.root).as_posix()
        }
        registry["state"]["timetable"] = timetable_target.relative_to(self.root).as_posix()
        self.workspace_path.write_text(
            yaml.safe_dump(registry, allow_unicode=True, sort_keys=False), encoding="utf-8",
        )
        workspace = load_workspace(self.workspace_path)

        in_term, _ = port.planner_input_data(
            date(2025, 9, 1), config_path=self.config_path, workspace=workspace,
        )
        outside_term, _ = port.planner_input_data(
            date(2025, 9, 8), config_path=self.config_path, workspace=workspace,
        )

        self.assertEqual(
            in_term["availability"], {"minutes": 75, "source": "timetable"}
        )
        self.assertEqual(
            outside_term["availability"],
            {
                "minutes": load_config(self.config_path).default_daily_minutes,
                "source": "config",
            },
        )

    def test_day_input_without_route_matches_fixed_pre_e3b_bytes(self) -> None:
        commit = "f0df351d80e3cd0b042ecc88fa11ccc116b65c98"
        result = subprocess.run(
            ["git", "show", f"{commit}:ky/planner/port.py"], cwd=ROOT,
            capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))
        source = result.stdout.decode("utf-8")
        self.assertIn('"route_plan": None', source)
        self.assertNotIn("route_planner_input_data", source)
        baseline = types.ModuleType("planner_port_f0df351")
        exec(compile(source, "planner_port_f0df351.py", "exec"), baseline.__dict__)

        config = load_config(self.config_path)
        old_data = baseline._build_input_data(
            DAY, LegacyConfigView(config).as_dataclass(), self.workspace
        )
        new_data, _ = port.planner_input_data(
            DAY, config_path=self.config_path, workspace=self.workspace,
        )
        self.assertEqual(
            port.canonical_json_bytes(_rename_legacy_key(old_data)),
            port.canonical_json_bytes(new_data),
        )

    def test_day_input_selects_phase_at_boundary_and_is_null_on_exam_date(self) -> None:
        boundary = DAY + timedelta(days=30)
        route = self._route("a" * 64, boundaries=(boundary,))
        self.route_store.write_route_plan(route, actor="human")
        inside, _ = port.planner_input_data(DAY, config_path=self.config_path,
                                            workspace=self.workspace)
        expected = route_plan_to_mapping(route)["phases"][0]
        self.assertEqual(inside["route_plan"], {
            "route_id": route.route_id, "revision": route.revision, "phase": expected,
        })
        boundary_day, _ = port.planner_input_data(
            boundary, config_path=self.config_path, workspace=self.workspace,
        )
        self.assertEqual(
            boundary_day["route_plan"]["phase"], route_plan_to_mapping(route)["phases"][1],
        )
        exam_day, _ = port.planner_input_data(
            TARGET, config_path=self.config_path, workspace=self.workspace,
        )
        self.assertIsNone(exam_day["route_plan"])

    def test_route_proposal_applies_with_audited_source_and_stage1_hash(self) -> None:
        _, digest = self._route_input()
        proposal = self._write_route_proposal(digest)
        port.apply_staged_route_proposal(
            proposal, store=self.route_store, config_path=self.config_path,
            workspace_path=self.workspace_path,
        )
        self.assertEqual(self.route_store.provenance(1), ("ai:route-agent", digest))
        self.assertEqual(self.route_store.current().stage1_input_hash, digest)

    def test_route_proposal_skips_nonmatching_same_prefix_package(self) -> None:
        _, digest = self._route_input()
        decoy = self.staging / "inputs" / f"route--0000-01-01--{digest[:12]}.json"
        decoy.write_text("{}", encoding="utf-8")
        proposal = self._write_route_proposal(digest)
        port.apply_staged_route_proposal(
            proposal, store=self.route_store, config_path=self.config_path,
            workspace_path=self.workspace_path,
        )
        self.assertEqual(self.route_store.current().stage1_input_hash, digest)

    def test_inputs_junction_outside_staging_is_rejected_for_write_and_apply(self) -> None:
        import _winapi

        with tempfile.TemporaryDirectory() as temporary:
            outside = Path(temporary) / "outside-inputs"
            outside.mkdir()
            inputs_link = self.staging / "inputs"
            try:
                _winapi.CreateJunction(str(outside), str(inputs_link))
            except OSError as exc:
                self.skipTest(f"junction unavailable: {exc}")
            try:
                with self.assertRaisesRegex(ContractError, "outside staging/inputs"):
                    port.create_route_planner_input(
                        DAY, config_path=self.config_path,
                        workspace_path=self.workspace_path,
                    )

                proposal = self._write_route_proposal("a" * 64)
                with self.assertRaisesRegex(ContractError, "outside staging/inputs"):
                    port.apply_staged_route_proposal(
                        proposal, store=self.route_store,
                        workspace_path=self.workspace_path,
                    )
            finally:
                os.rmdir(inputs_link)

    def test_day_proposal_expires_after_route_revision_changes(self) -> None:
        first_route_input, first_route_hash = self._route_input()
        del first_route_input
        first_route_proposal = self._write_route_proposal(first_route_hash)
        port.apply_staged_route_proposal(
            first_route_proposal, store=self.route_store,
            config_path=self.config_path, workspace_path=self.workspace_path,
        )

        _, day_hash = self._input()
        day_proposal = self._write_proposal(input_hash=day_hash)

        _, second_route_hash = self._route_input()
        second_route_proposal = self._write_route_proposal(
            second_route_hash, plan=self._route(second_route_hash, revision=2),
        )
        port.apply_staged_route_proposal(
            second_route_proposal, store=self.route_store,
            config_path=self.config_path, workspace_path=self.workspace_path,
        )

        with self.assertRaisesRegex(ContractError, "输入已变化，请基于新输入包重新提案"):
            port.apply_staged_proposal(
                day_proposal, store=self.store, config_path=self.config_path,
                workspace_path=self.workspace_path,
            )

    def test_route_proposal_rejects_path_missing_hash_and_stage1_mismatch(self) -> None:
        _, digest = self._route_input()
        outside = self._write_route_proposal(digest, path=self.root / "outside-route.yaml")
        with self.assertRaisesRegex(ContractError, "under staging/routes"):
            port.apply_staged_route_proposal(outside, store=self.route_store,
                                             workspace_path=self.workspace_path)

        missing = self._write_route_proposal(
            digest, path=self.route_proposal_dir / "missing-hash.yaml", include_hash=False,
        )
        with self.assertRaisesRegex(ContractError, "missing field 'input_hash'"):
            port.apply_staged_route_proposal(missing, store=self.route_store,
                                             workspace_path=self.workspace_path)

        mismatched = self._write_route_proposal(
            digest, path=self.route_proposal_dir / "mismatch.yaml",
            plan=self._route("b" * 64),
        )
        with self.assertRaisesRegex(ContractError, "stage1_input_hash must equal input_hash"):
            port.apply_staged_route_proposal(mismatched, store=self.route_store,
                                             workspace_path=self.workspace_path)

    def test_route_proposal_rejects_missing_wrong_kind_stale_and_wrong_revision(self) -> None:
        missing_hash = "c" * 64
        missing = self._write_route_proposal(
            missing_hash, path=self.route_proposal_dir / "no-package.yaml",
        )
        with self.assertRaisesRegex(ContractError, "route input package does not exist"):
            port.apply_staged_route_proposal(missing, store=self.route_store,
                                             workspace_path=self.workspace_path)

        wrong_kind_data = {
            "schema_version": 1, "kind": "planner_input", "day": DAY.isoformat(),
        }
        wrong_kind_hash = hashlib.sha256(port.canonical_json_bytes(wrong_kind_data)).hexdigest()
        wrong_kind_path = self.staging / "inputs" / (
            f"route--{DAY.isoformat()}--{wrong_kind_hash[:12]}.json"
        )
        wrong_kind_path.parent.mkdir(parents=True, exist_ok=True)
        wrong_kind_path.write_bytes(port.canonical_json_bytes(wrong_kind_data))
        wrong_kind = self._write_route_proposal(
            wrong_kind_hash, path=self.route_proposal_dir / "wrong-kind.yaml",
        )
        with self.assertRaisesRegex(ContractError, "expected kind route_planner_input"):
            port.apply_staged_route_proposal(wrong_kind, store=self.route_store,
                                             workspace_path=self.workspace_path)

        _, stale_hash = self._route_input()
        items = load_review_items(REVIEWS_SOURCE)
        changed = (replace(items[0], due_date=items[0].due_date + timedelta(days=3)), *items[1:])
        self.review_store.write(changed)
        stale = self._write_route_proposal(
            stale_hash, path=self.route_proposal_dir / "stale.yaml",
        )
        with self.assertRaisesRegex(ContractError, "输入已变化，请基于新输入包重新提案"):
            port.apply_staged_route_proposal(
                stale, store=self.route_store, config_path=self.config_path,
                workspace_path=self.workspace_path,
            )

        _, current_hash = self._route_input()
        wrong_revision = self._write_route_proposal(
            current_hash, plan=self._route(current_hash, revision=2),
            path=self.route_proposal_dir / "wrong-revision.yaml",
        )
        with self.assertRaisesRegex(StorageError, "first revision must be 1"):
            port.apply_staged_route_proposal(
                wrong_revision, store=self.route_store, config_path=self.config_path,
                workspace_path=self.workspace_path,
            )

    def test_route_human_and_staged_submit_share_route_apply_function(self) -> None:
        _, digest = self._route_input()
        staged = self._write_route_proposal(digest)
        human_path = self.root / "human-route.yaml"
        human_path.write_text(
            yaml.safe_dump(route_plan_to_mapping(self._route("d" * 64)), sort_keys=False),
            encoding="utf-8",
        )
        human_store = RoutePlanStore(self.root / "human-routes")
        with patch("ky.planner.port._apply_route_plan", wraps=port._apply_route_plan) as apply:
            human_result = route_main([
                "submit", "--plan", str(human_path), "--store", str(human_store.root),
                "--workspace", str(self.workspace_path),
            ])
            staged_result = route_main([
                "submit", "--from-staging", str(staged), "--store", str(self.route_store.root),
                "--config", str(self.config_path), "--workspace", str(self.workspace_path),
            ])
        self.assertEqual((human_result, staged_result), (0, 0))
        self.assertEqual(apply.call_count, 2)
        self.assertEqual(human_store.provenance(1), ("human", None))
        self.assertEqual(self.route_store.provenance(1), ("ai:route-agent", digest))

    def test_input_package_replaces_hard_link_without_writing_through(self) -> None:
        data, digest = port.planner_input_data(DAY, config_path=self.config_path,
                                               workspace=self.workspace)
        self.assertIn("default_daily_minutes", data)
        self.assertNotIn("total_daily_minutes", data)
        self.assertIn("default_daily_minutes", data["config"])
        self.assertNotIn("total_daily_minutes", data["config"])
        target = self.staging / "inputs" / f"{DAY.isoformat()}--{digest[:12]}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as outside_dir:
            outside = Path(outside_dir) / "outside.json"
            original = b"OUTSIDE ORIGINAL"
            outside.write_bytes(original)
            try:
                os.link(outside, target)
            except OSError as exc:
                self.skipTest(f"hard links unavailable: {exc}")
            written_path, written_digest = port.create_planner_input(
                DAY, config_path=self.config_path, workspace_path=self.workspace_path,
            )
            self.assertEqual(written_path, target)
            self.assertEqual(written_digest, digest)
            self.assertEqual(outside.read_bytes(), original)
            self.assertEqual(target.read_bytes(), port.canonical_json_bytes(data))

    def test_staged_proposal_applies_with_audited_source(self) -> None:
        _, digest = self._input()
        proposal = self._write_proposal(input_hash=digest)
        port.apply_staged_proposal(
            proposal, store=self.store, config_path=self.config_path,
            workspace_path=self.workspace_path,
        )
        self.assertEqual(self.store.day_plan_provenance(DAY), (1, "ai:test-model", digest))

    def test_proposal_outside_day_plans_is_rejected(self) -> None:
        proposal = self._write_proposal(path=self.root / "outside.yaml")
        with self.assertRaisesRegex(ContractError, "under staging/day_plans"):
            port.apply_staged_proposal(
                proposal, store=self.store, workspace_path=self.workspace_path,
            )

    def test_ai_proposal_requires_input_hash(self) -> None:
        proposal = self._write_proposal()
        with self.assertRaisesRegex(ContractError, "requires a 64-character input_hash"):
            port.apply_staged_proposal(
                proposal, store=self.store, workspace_path=self.workspace_path,
            )

    def test_human_staging_proposal_requires_input_hash(self) -> None:
        proposal = self._write_proposal(actor="human")
        with self.assertRaisesRegex(
            ContractError, "staged proposal requires a 64-character input_hash",
        ):
            port.apply_staged_proposal(
                proposal, store=self.store, workspace_path=self.workspace_path,
            )

    def test_boolean_schema_version_is_rejected(self) -> None:
        _, digest = self._input()
        proposal = self._write_proposal(actor="human", input_hash=digest)
        payload = yaml.safe_load(proposal.read_text(encoding="utf-8"))
        payload["schema_version"] = True
        proposal.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        with self.assertRaisesRegex(ContractError, "schema_version must be integer 1"):
            port.apply_staged_proposal(
                proposal, store=self.store, config_path=self.config_path,
                workspace_path=self.workspace_path,
            )

    def test_missing_input_package_is_rejected(self) -> None:
        proposal = self._write_proposal(input_hash="a" * 64)
        with self.assertRaisesRegex(ContractError, "input package does not exist"):
            port.apply_staged_proposal(
                proposal, store=self.store, workspace_path=self.workspace_path,
            )

    def test_modified_input_package_is_rejected(self) -> None:
        input_path, digest = self._input()
        package = json.loads(input_path.read_text(encoding="utf-8"))
        package["default_daily_minutes"] += 1
        input_path.write_bytes(port.canonical_json_bytes(package))
        proposal = self._write_proposal(input_hash=digest)
        with self.assertRaisesRegex(ContractError, "input package hash mismatch"):
            port.apply_staged_proposal(proposal, store=self.store, config_path=self.config_path,
                                       workspace_path=self.workspace_path)

    def test_input_day_must_match_plan_day(self) -> None:
        input_path, _ = self._input()
        package = json.loads(input_path.read_text(encoding="utf-8"))
        package["day"] = "2026-09-16"
        encoded = port.canonical_json_bytes(package)
        digest = hashlib.sha256(encoded).hexdigest()
        renamed = input_path.with_name(f"{DAY.isoformat()}--{digest[:12]}.json")
        input_path.unlink()
        renamed.write_bytes(encoded)
        proposal = self._write_proposal(input_hash=digest)
        with self.assertRaisesRegex(ContractError, "day does not match plan.day"):
            port.apply_staged_proposal(proposal, store=self.store, config_path=self.config_path,
                                       workspace_path=self.workspace_path)

    def test_changed_current_input_is_stale(self) -> None:
        _, digest = self._input()
        items = load_review_items(REVIEWS_SOURCE)
        changed = (replace(items[0], due_date=items[0].due_date + timedelta(days=2)), *items[1:])
        self.review_store.write(changed)
        proposal = self._write_proposal(input_hash=digest)
        with self.assertRaisesRegex(ContractError, "输入已变化，请基于新输入包重新提案"):
            port.apply_staged_proposal(proposal, store=self.store, config_path=self.config_path,
                                       workspace_path=self.workspace_path)

    def test_invalid_actor_is_rejected(self) -> None:
        proposal = self._write_proposal(actor="ai:Bad Model", input_hash="a" * 64)
        with self.assertRaisesRegex(ContractError, "actor must be human"):
            port.apply_staged_proposal(
                proposal, store=self.store, workspace_path=self.workspace_path,
            )

    def test_existing_plan_guardrail_still_rejects(self) -> None:
        proposal = self._write_proposal(
            input_hash="a" * 64, plan=self._plan_mapping(available_minutes=-1),
        )
        with self.assertRaisesRegex(ContractError, "input package does not exist"):
            port.apply_staged_proposal(
                proposal, store=self.store, workspace_path=self.workspace_path,
            )
        _, digest = self._input()
        proposal = self._write_proposal(
            input_hash=digest, plan=self._plan_mapping(available_minutes=-1),
        )
        with self.assertRaisesRegex(StorageError, "available_minutes must be non-negative"):
            port.apply_staged_proposal(proposal, store=self.store, config_path=self.config_path,
                                       workspace_path=self.workspace_path)

    def test_legacy_plan_uses_shared_apply_and_records_human_source(self) -> None:
        plan_path = self.root / "manual.yaml"
        plan_path.write_text(yaml.safe_dump(self._plan_mapping()), encoding="utf-8")
        with patch("ky.planner.port._apply", wraps=port._apply) as apply:
            port.apply_human_plan(plan_path, store=self.store)
            apply.assert_called_once()
        self.assertEqual(self.store.day_plan_provenance(DAY), (1, "human", None))

    def test_legacy_manifest_reads_unknown_without_rewriting_and_new_write_has_source(self) -> None:
        plan = DayPlan(day=DAY, available_minutes=0, subject_minutes={
            subject.subject_id: 0 for subject in load_config(self.config_path).active_subjects()
        })
        self.store.write_day_plan(plan, actor="human")
        manifest_path = self.workspace.plans / "2026-09" / "day_plans_manifest.yaml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        manifest["schema_version"] = 1
        manifest["days"][0].pop("actor")
        manifest["days"][0].pop("input_hash")
        manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
        old_bytes = manifest_path.read_bytes()
        self.assertEqual(self.store.day_plan_provenance(DAY), (1, "unknown", None))
        self.assertEqual(manifest_path.read_bytes(), old_bytes)
        self.store.write_day_plan(plan, actor="ai:reviewer", input_hash="b" * 64)
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema_version"], 2)
        self.assertEqual(manifest["days"][0]["actor"], "ai:reviewer")
        self.assertEqual(manifest["days"][0]["input_hash"], "b" * 64)
        self.assertEqual(self.store.day_plan_provenance(DAY), (2, "ai:reviewer", "b" * 64))

    def test_day_plan_submit_plan_keeps_cli_compatibility(self) -> None:
        plan_path = self.root / "manual-cli.yaml"
        plan_path.write_text(yaml.safe_dump(self._plan_mapping()), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "-m", "ky", "day-plan", "submit", "--config",
             str(self.config_path), "--plan", str(plan_path), "--store", str(self.workspace.plans)],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.store.day_plan_provenance(DAY), (1, "human", None))

    def test_plan_cli_rejects_registered_staging_paths_but_skips_without_registry(self) -> None:
        day_path = self.proposal_dir / "bare-plan.yaml"
        day_path.write_text(yaml.safe_dump(self._plan_mapping()), encoding="utf-8")
        day_store_path = self.root / "rejected-day-plans"
        day_result = subprocess.run(
            [sys.executable, "-m", "ky", "day-plan", "submit", "--config",
             str(self.config_path), "--plan", str(day_path), "--store", str(day_store_path),
             "--workspace", str(self.workspace_path)],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(day_result.returncode, 2, day_result.stderr)
        self.assertIn("under staging", day_result.stderr)
        self.assertFalse(day_store_path.exists())

        route_path = self.route_proposal_dir / "bare-route.yaml"
        route_path.write_text(
            yaml.safe_dump(route_plan_to_mapping(self._route("e" * 64)), sort_keys=False),
            encoding="utf-8",
        )
        route_store_path = self.root / "rejected-routes"
        route_result = subprocess.run(
            [sys.executable, "-m", "ky", "route", "submit", "--plan", str(route_path),
             "--store", str(route_store_path), "--workspace", str(self.workspace_path)],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(route_result.returncode, 2, route_result.stderr)
        self.assertIn("under staging", route_result.stderr)
        self.assertFalse(route_store_path.exists())

        isolated = self.root / "without-workspace"
        isolated.mkdir()
        unstaged_day = isolated / "staging" / "day.yaml"
        unstaged_day.parent.mkdir()
        unstaged_day.write_text(yaml.safe_dump(self._plan_mapping()), encoding="utf-8")
        unstaged_route = isolated / "staging" / "route.yaml"
        unstaged_route.write_text(
            yaml.safe_dump(route_plan_to_mapping(self._route("f" * 64)), sort_keys=False),
            encoding="utf-8",
        )
        environment = os.environ.copy()
        environment.pop("KY_WORKSPACE", None)
        environment["PYTHONPATH"] = str(ROOT)
        no_registry_day = subprocess.run(
            [sys.executable, "-m", "ky", "day-plan", "submit", "--config",
             str(self.config_path), "--plan", str(unstaged_day), "--store",
             str(isolated / "day-plans")], cwd=isolated, env=environment,
            capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(no_registry_day.returncode, 0, no_registry_day.stderr)
        no_registry_route = subprocess.run(
            [sys.executable, "-m", "ky", "route", "submit", "--plan",
             str(unstaged_route), "--store", str(isolated / "routes")],
            cwd=isolated, env=environment, capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(no_registry_route.returncode, 0, no_registry_route.stderr)

    def test_plan_cli_fails_closed_for_discovered_invalid_registry(self) -> None:
        invalid_root = self.root / "invalid-workspace"
        staging = invalid_root / "staging"
        (staging / "day_plans").mkdir(parents=True)
        (staging / "routes").mkdir(parents=True)
        invalid_registry = invalid_root / WORKSPACE_FILENAME
        invalid_registry.write_text(
            "schema_version: 2\nsubjects: {}\n", encoding="utf-8",
        )
        day_path = staging / "day_plans" / "proposal.yaml"
        day_path.write_text(yaml.safe_dump(self._plan_mapping()), encoding="utf-8")
        route_path = staging / "routes" / "proposal.yaml"
        route_path.write_text(
            yaml.safe_dump(route_plan_to_mapping(self._route("a" * 64)), sort_keys=False),
            encoding="utf-8",
        )
        base = {key: value for key, value in os.environ.items() if key != "KY_WORKSPACE"}
        base["PYTHONPATH"] = str(ROOT)
        # Both discovery routes must fail closed: the environment variable, and the upward
        # search from the working directory (sol round 105, B2 suggestion).
        for label, environment in (
            ("KY_WORKSPACE", {**base, "KY_WORKSPACE": str(invalid_registry)}),
            ("upward search", base),
        ):
            with self.subTest(discovery=label):
                day_store = invalid_root / "day-store"
                day_result = subprocess.run(
                    [sys.executable, "-m", "ky", "day-plan", "submit", "--plan",
                     str(day_path), "--config", str(self.config_path),
                     "--store", str(day_store)],
                    cwd=invalid_root, env=environment, capture_output=True, text=True,
                    encoding="utf-8",
                )
                self.assertEqual(day_result.returncode, 2, day_result.stderr)
                self.assertFalse(day_store.exists())

                route_store = invalid_root / "route-store"
                route_result = subprocess.run(
                    [sys.executable, "-m", "ky", "route", "submit", "--plan",
                     str(route_path), "--store", str(route_store)],
                    cwd=invalid_root, env=environment, capture_output=True, text=True,
                    encoding="utf-8",
                )
                self.assertEqual(route_result.returncode, 2, route_result.stderr)
                self.assertFalse(route_store.exists())


if __name__ == "__main__":
    unittest.main()
