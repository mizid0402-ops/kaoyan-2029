from __future__ import annotations

import subprocess
import tarfile
import tempfile
import unittest
import os
import copy
import contextlib
import io
import shutil
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from ky.availability import (
    availability_for_workspace, load_availability, set_day_minutes,
)
from ky.models import ContractError, ReviewItem, ReviewSchedule, load_config
from ky.mastery import item_level
from ky.knowledge import load_knowledge_points
from ky.today import today_view_hash
from ky.today import advance_recorded_day, load_queue_view, load_today, record_day
from ky.today.compute import calculate_preflight
from ky.today.questions import load_review_question_sources
from ky.today.record import RecordPipelineError
from ky.storage.review_shards import ReviewShardStore
from ky.pacing.port import (
    load_pacing_report_state, load_settings, settings_for_workspace,
)
from ky.storage.day_plan_store import DayPlanStore
from ky.schedule.review_clip import ClipResult
from ky.schedule.planning import Phase, RoutePlan
from ky.storage.route_store import RoutePlanStore
from ky.timetable import timetable_for_workspace
from ky.workspace import WORKSPACE_FILENAME, load_workspace
from tests._baseline_harness import (
    ProcessResult,
    compare_results,
    compare_runs,
    fixed_source,
    output_tree,
)
import yaml

ROOT = Path(__file__).resolve().parents[2]
BASELINE = "60a4fd2"


class TodayPortContractTests(unittest.TestCase):
    def _workspace(self, root: Path):
        root.mkdir(parents=True, exist_ok=True)
        config_path = root / "config.yaml"
        config_path.write_bytes((ROOT / "tests/fixtures/config/config-minimal.yaml").read_bytes())
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        registry = {
            "schema_version": 2,
            "subjects": {item["subject_id"]: {"name": item["display_name"]}
                         for item in raw["subjects"]},
            "reference": {"knowledge_trees": {}, "exam_indexes": {}, "paper_shapes": {},
                          "topic_weights": "data/weights.json",
                          "weight_batches": "data/batches.yaml",
                          "vocabulary_db": "data/vocab.sqlite", "ledger": "data/ledger.yaml"},
            "supplementary": {}, "materials": {"raw_root": "data/raw"}, "products": {},
            "settings": {"exam_config": "config.yaml"},
            "state": {"review_queue": "state/review_queue", "plans": "state/plans"},
            "staging": "staging", "projection": "data/projection.sqlite",
        }
        path = root / WORKSPACE_FILENAME
        path.write_text(yaml.safe_dump(registry, allow_unicode=True, sort_keys=False),
                        encoding="utf-8")
        workspace = load_workspace(path)
        ReviewShardStore(workspace.write_target("state.review_queue")).write([])
        return workspace

    def _workspace_with_reviews(self, root: Path):
        root.mkdir(parents=True, exist_ok=True)
        workspace_path = root / WORKSPACE_FILENAME
        config_path = root / "config.yaml"
        config_path.write_bytes(
            (ROOT / "tests/fixtures/config/config-minimal.yaml").read_bytes()
        )
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        subjects = {}
        tree_paths = {}
        for item in config["subjects"]:
            subject = item["subject_id"]
            subjects[subject] = {"name": item["display_name"], "tree_grammar": "flat"}
            tree_paths[subject] = f"trees/{subject}.yaml"
        registry = {
            "schema_version": 2, "subjects": subjects,
            "reference": {"knowledge_trees": tree_paths, "exam_indexes": {},
                          "paper_shapes": {}, "topic_weights": "data/weights.json",
                          "weight_batches": "data/batches.yaml",
                          "vocabulary_db": "data/vocab.sqlite",
                          "ledger": "data/ledger.yaml"},
            "supplementary": {}, "materials": {"raw_root": "data/raw"}, "products": {},
            "settings": {"exam_config": "config.yaml"},
            "state": {"review_queue": "state/review_queue", "plans": "state/plans",
                      "routes": "state/routes"},
            "staging": "staging", "projection": "data/projection.sqlite",
        }
        workspace_path.write_text(
            yaml.safe_dump(registry, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        queue = yaml.safe_load(
            (ROOT / "tests/fixtures/reviews/reviews-normal.yaml").read_text(encoding="utf-8")
        )["items"]
        by_subject = {}
        for item in queue:
            by_subject.setdefault(item["subject_id"], []).append({
                "schema_version": 1, "knowledge_point_id": item["knowledge_point_id"],
                "title": item["title"], "scope": "item", "status": "raw",
                "source_kind": "manual",
                "sources": [{"path": "synthetic.pdf", "sha256": "0" * 64,
                             "locator": {"page": 1}}],
            })
        for subject, nodes in by_subject.items():
            path = root / tree_paths[subject]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(yaml.safe_dump(nodes, allow_unicode=True), encoding="utf-8")
        workspace = load_workspace(workspace_path)
        ReviewShardStore(workspace.write_target("state.review_queue")).write(queue)
        return workspace

    def _live_queue_inputs(self, root: Path):
        workspace = self._workspace_with_reviews(root)
        config_path = workspace.require("settings.exam_config")
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        config["default_daily_minutes"] = 20
        config["review_reserve_ratio"] = 0.2
        config["hard_max_ratio"] = 0.2
        for subject in config["subjects"]:
            subject["min_daily_minutes"] = 0
        config_path.write_text(
            yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        RoutePlanStore(workspace.write_target("state.routes")).write_route_plan(
            RoutePlan(
                "queue-test", 1, date(2026, 10, 1), date(2026, 10, 20), "v1",
                "a" * 64,
                (Phase(0, date(2026, 10, 1), date(2026, 10, 20), "合成阶段",
                       {"math1": 8, "eng1": 4, "cs408": 8}),),
            )
        )
        items = yaml.safe_load(
            (ROOT / "tests/fixtures/reviews/reviews-normal.yaml").read_text(
                encoding="utf-8",
            )
        )["items"]
        items = copy.deepcopy(items)
        for item in items:
            item["due_date"] = "2026-10-02"
        template = items[0]
        for identifier, minutes, state, due in (
            ("extra-selected", 2, "queued", "2026-10-02"),
            ("extra-scheduled", 8, "scheduled", "2026-10-02"),
            ("extra-ahead", 8, "scheduled", "2026-10-04"),
            ("extra-queued-ahead", 8, "queued", "2026-10-05"),
        ):
            item = copy.deepcopy(template)
            item["review_id"] = identifier
            item["estimated_minutes"] = minutes
            item["state"] = state
            item["due_date"] = due
            item["introduced_on"] = "2026-09-01"
            items.append(item)
        for index in range(25):
            item = copy.deepcopy(template)
            item["review_id"] = f"extra-deferred-{index}"
            item["estimated_minutes"] = 2
            item["state"] = "queued"
            item["due_date"] = "2026-10-02"
            item["introduced_on"] = "2026-09-01"
            items.append(item)
        ReviewShardStore(workspace.write_target("state.review_queue")).write(items)
        return workspace, date(2026, 10, 2), config_path

    def _read_queue_and_today_once(self, workspace, day):
        clips = []

        def preflight(*args, **kwargs):
            result = calculate_preflight(*args, **kwargs)
            clips.append(result[0])
            return result

        with patch("ky.today.port.calculate_preflight", side_effect=preflight), \
             patch("ky.today.port.load_config", wraps=load_config) as config_reader, \
             patch("ky.today.port.ReviewShardStore.read_state_sources",
                   autospec=True,
                   side_effect=ReviewShardStore.read_state_sources) as queue_reader, \
             patch("ky.today.port.DayPlanStore.read_state_sources",
                   autospec=True,
                   side_effect=DayPlanStore.read_state_sources) as plans_reader, \
             patch("ky.today.port.RoutePlanStore.current",
                   autospec=True,
                   side_effect=RoutePlanStore.current) as route_reader, \
             patch("ky.today.port.availability_for_workspace",
                   wraps=availability_for_workspace) as availability_reader, \
             patch("ky.today.port.timetable_for_workspace",
                   wraps=timetable_for_workspace) as timetable_reader, \
             patch("ky.today.port.settings_for_workspace",
                   wraps=settings_for_workspace) as pacing_reader, \
             patch("ky.today.port.load_pacing_report_state",
                   wraps=load_pacing_report_state) as report_reader, \
             patch("ky.today.port.load_review_question_sources",
                   wraps=load_review_question_sources) as question_reader, \
             patch("ky.today.questions.load_knowledge_points",
                   wraps=load_knowledge_points) as tree_reader:
            queue_view = load_queue_view(workspace, day)
            today_view = load_today(workspace, day)
        self.assertEqual((config_reader.call_count, queue_reader.call_count,
                          plans_reader.call_count, route_reader.call_count,
                          availability_reader.call_count, timetable_reader.call_count,
                          pacing_reader.call_count), (2,) * 7)
        self.assertEqual(question_reader.call_count, 1)
        self.assertEqual(report_reader.call_count, 0)
        self.assertEqual(tree_reader.call_count, len({
            item.subject_id for item in clips[1].selected
        }))
        return queue_view, today_view, clips

    def _expected_queue_item(self, item, config, day):
        return {
            "review_id": item.review_id,
            "knowledge_point_id": item.knowledge_point_id,
            "title": item.title, "subject_id": item.subject_id,
            "subject_name": config.subject(item.subject_id).display_name,
            "level": item_level(item, False), "due_date": item.due_date.isoformat(),
            "overdue_days": item.overdue_days(day),
            "defer_count": item.defer_count, "lapses": item.schedule.lapses,
            "estimated_minutes": item.estimated_minutes,
        }

    def _assert_queue_bucket_values(self, view, clip):
        groups = {
            "selected": clip.selected, "deferred": clip.deferred,
            "unschedulable": clip.unschedulable,
            "scheduled_ahead": clip.scheduled_ahead,
            "unreachable": clip.unreachable,
        }
        self.assertEqual(set(view["buckets"]), set(groups))
        self.assertEqual(view["buckets"], {
            name: {"count": len(group),
                  "minutes": sum(item.estimated_minutes for item in group)}
            for name, group in groups.items()
        })

    def _assert_queue_item_summaries(self, view, clip, config, day, original):
        self.assertEqual(
            view["selected"],
            [self._expected_queue_item(item, config, day) for item in clip.selected],
        )
        backlog_items = clip.deferred + clip.unschedulable + clip.unreachable
        self.assertEqual(view["backlog"]["count"], len(backlog_items))
        self.assertEqual(
            view["backlog"]["details"],
            [self._expected_queue_item(item, config, day)
             for item in backlog_items[:20]],
        )
        self.assertEqual(view["backlog"]["minutes"], sum(
            item.estimated_minutes for item in backlog_items
        ))
        self.assertEqual(view["backlog"]["remaining_count"],
                         max(0, len(backlog_items) - 20))
        expected_subjects = {}
        for item in backlog_items:
            total = expected_subjects.setdefault(
                item.subject_id, {"count": 0, "minutes": 0},
            )
            total["count"] += 1
            total["minutes"] += item.estimated_minutes
        self.assertEqual(view["backlog"]["by_subject"], expected_subjects)
        self.assertEqual(view["ahead"], {
            "count": sum(item.state in {"queued", "scheduled"} and item.due_date > day
                          for item in original),
            "due_dates": sorted({item.due_date.isoformat() for item in original
                                 if item.state in {"queued", "scheduled"}
                                 and item.due_date > day})[:3],
        })

    def test_load_queue_view_has_stable_empty_shape_and_parameter_guards(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = self._workspace(Path(temporary))
            day = date(2026, 10, 2)
            original_read = ReviewShardStore.read_state_sources
            with patch("ky.today.port.ReviewShardStore.read_state_sources",
                       autospec=True, side_effect=original_read) as reader:
                view = load_queue_view(workspace, day)
            self.assertEqual(reader.call_count, 1)
            today = load_today(workspace, day)
        self.assertEqual(set(view), {
            "schema_version", "date", "budget", "caps", "freeze",
            "queue_registered", "buckets", "selected", "backlog", "ahead",
        })
        self.assertTrue(view["queue_registered"])
        self.assertEqual(view["budget"], today["budget"])
        self.assertEqual(view["buckets"], {
            name: {"count": 0, "minutes": 0} for name in (
                "selected", "deferred", "unschedulable", "scheduled_ahead", "unreachable",
            )
        })
        self.assertEqual(view["selected"], [])
        self.assertEqual(view["backlog"], {
            "count": 0, "minutes": 0, "by_subject": {}, "details": [],
            "remaining_count": 0,
        })
        self.assertEqual(view["ahead"], {"count": 0, "due_dates": []})
        for workspace_arg, day_arg, path in (
            (None, date(2026, 10, 2), "workspace"),
            (workspace, "2026-10-02", "day"),
        ):
            with self.subTest(path=path), self.assertRaises(ContractError) as caught:
                load_queue_view(workspace_arg, day_arg)
            self.assertEqual(caught.exception.path, path)

    def test_load_queue_view_uses_five_m9_buckets_and_matches_today(self) -> None:
        # sol 293 R3: bind every bucket minute to the M9 ClipResult.
        with tempfile.TemporaryDirectory() as temporary:
            workspace, day, config_path = self._live_queue_inputs(Path(temporary))
            queue_view, today_view, clips = self._read_queue_and_today_once(workspace, day)
            original = ReviewShardStore(
                workspace.write_target("state.review_queue")
            ).read_state_sources().items
            clip = clips[0]
            config = load_config(config_path)

        self._assert_queue_bucket_values(queue_view, clip)
        self.assertEqual(queue_view["caps"], {
            "soft_target_minutes": clip.soft_target_minutes,
            "hard_cap_minutes": clip.hard_cap_minutes,
            "soft_source": "route_quota", "hard_source": "config_ratio",
            "subject_review_quotas": dict(clip.subject_review_quotas),
        })
        self.assertEqual(sum(queue_view["caps"]["subject_review_quotas"].values()),
                         queue_view["caps"]["hard_cap_minutes"])
        self.assertLess(
            sum(queue_view["caps"]["subject_review_quotas"].values()),
            sum((8, 4, 8)),
        )
        self.assertEqual(queue_view["budget"], today_view["budget"])
        self.assertEqual([row["review_id"] for row in queue_view["selected"]],
                         [row["review_id"] for row in today_view["preflight"]["selected"]])
        self._assert_queue_bucket_values(queue_view, clips[1])
        deferred = next(item for item in queue_view["backlog"]["details"]
                        if item["defer_count"] == 1)
        self.assertEqual(deferred["defer_count"], 1)
        self.assertTrue(all(item.defer_count == 0 for item in original))
        self._assert_queue_item_summaries(queue_view, clip, config, day, original)

    def test_load_queue_view_route_caps_freeze_and_summary_limits(self) -> None:
        def item(identifier: str, due: date, *, state: str = "queued",
                 defer_count: int = 0) -> ReviewItem:
            return ReviewItem(
                identifier, 1, "math1", identifier, identifier, "concept", state, 2,
                date(2026, 9, 1), due, None,
                ReviewSchedule("fixed_bootstrap", 1, 4, 2.5, 1, 0),
                defer_count, None,
            )

        with tempfile.TemporaryDirectory() as temporary:
            workspace = self._workspace(Path(temporary))
            day = date(2026, 10, 2)
            selected = (item("selected", day),)
            deferred = tuple(item(f"deferred-{index}", day, defer_count=1)
                             for index in range(25))
            future = tuple(item(f"future-{index}", date(2026, 10, 3 + index))
                           for index in range(5))
            config = load_config(workspace.require("settings.exam_config"))
            sources = {"config": config, "plan_state": SimpleNamespace(completions=()),
                       "items": selected + deferred + future}
            clip = ClipResult(
                day, selected, deferred, 2, 0, 20, 40, 50, True, (), (), (),
                {"math1": 20}, {"math1": 2},
            )
            budget = SimpleNamespace(
                total_minutes=120, total_source="config", base_minutes=120,
                base_source="config",
            )
            with patch("ky.today.port._read_today_sources", return_value=sources), \
                 patch("ky.today.port._calculate_today_content",
                       return_value=(budget, {"freeze": None}, clip)):
                view = load_queue_view(workspace, day)
            with patch("ky.today.port._read_today_sources", return_value=sources), \
                 patch("ky.today.port._calculate_today_content",
                       return_value=(budget, {"freeze": {"overdue_minutes": 50}}, clip)):
                frozen = load_queue_view(workspace, day)

        self.assertEqual(view["caps"], {
            "soft_target_minutes": 20, "hard_cap_minutes": 40,
            "soft_source": "route_quota", "hard_source": "config_ratio",
            "subject_review_quotas": {"math1": 20},
        })
        self.assertEqual(view["backlog"]["count"], 25)
        self.assertEqual(len(view["backlog"]["details"]), 20)
        self.assertEqual(view["backlog"]["remaining_count"], 5)
        self.assertEqual(view["ahead"], {
            "count": 5, "due_dates": ["2026-10-03", "2026-10-04", "2026-10-05"],
        })
        self.assertEqual(frozen["caps"], {
            "soft_target_minutes": 0, "hard_cap_minutes": 0,
            "soft_source": "freeze", "hard_source": "freeze",
            "subject_review_quotas": None,
        })

    def test_hash_uses_only_ordered_review_identity(self) -> None:
        view = {"date": "2026-10-02", "reviews": [
            {"review_id": "r1", "title": "A", "question": {"stem": "x"},
             "check": "exercise", "question_ref": "qb:a"},
            {"review_id": "r2", "title": "B", "status": "缺题"},
        ]}
        value = today_view_hash(view)
        changed = {**view, "reviews": [dict(item) for item in view["reviews"]]}
        changed["reviews"][0]["title"] = "changed"
        changed["reviews"][0]["question"] = {"stem": "changed"}
        self.assertEqual(value, today_view_hash(changed))
        changed["reviews"][0]["question_ref"] = "qb:b"
        self.assertNotEqual(value, today_view_hash(changed))

    def test_set_day_minutes_rewrites_canonically_and_rejects_without_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "availability.yaml"
            path.write_text("# comment\nschema_version: 1\ndays:\n  2026-10-03: 60\n",
                            encoding="utf-8")
            set_day_minutes(path, date(2026, 10, 2), 75)
            self.assertEqual(load_availability(path).days, {
                date(2026, 10, 2): 75, date(2026, 10, 3): 60,
            })
            self.assertNotIn(b"comment", path.read_bytes())
            before = path.read_bytes()
            for value in (True, -1, 1441, 2.5):
                with self.subTest(value=value), self.assertRaises(ContractError):
                    set_day_minutes(path, date(2026, 10, 2), value)
                self.assertEqual(path.read_bytes(), before)
            with self.assertRaises(ContractError):
                set_day_minutes(path, date(2026, 10, 4), None)
            self.assertEqual(path.read_bytes(), before)

    def test_today_record_rejects_before_write_and_advance_is_repeatable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = self._workspace(Path(temporary))
            day = date(2026, 10, 2)
            view = load_today(workspace, day)
            store = workspace.write_target("state.plans")
            with self.assertRaises(ContractError):
                record_day(workspace, day, {}, study_minutes=5,
                           expected_view_hash="0" * 64)
            self.assertFalse(list(store.rglob("completion--*.yaml")))
            with self.assertRaises(ContractError):
                record_day(workspace, day, {"unknown": "correct"}, study_minutes=None,
                           expected_view_hash=view["view_hash"])
            self.assertFalse(list(store.rglob("completion--*.yaml")))
            with self.assertRaises(ContractError):
                record_day(workspace, day, {}, study_minutes=None,
                           expected_view_hash=view["view_hash"])
            with self.assertRaises(ContractError):
                record_day(workspace, day, {}, study_minutes=True,
                           expected_view_hash=view["view_hash"])
            self.assertFalse(list(store.rglob("completion--*.yaml")))
            result = record_day(workspace, day, {}, study_minutes=5,
                                expected_view_hash=view["view_hash"])
            self.assertEqual(result["review_queue"], None)
            first = advance_recorded_day(workspace, day)
            second = advance_recorded_day(workspace, day)
            self.assertTrue(first["advanced"])
            self.assertTrue(second["advanced"])
            updated = load_today(workspace, day)
            self.assertTrue(updated["recorded"]["advanced"])

    def test_load_today_shows_freeze_and_null_timetable_when_absent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = self._workspace(Path(temporary))
            day = date(2026, 10, 2)
            DayPlanStore(workspace.write_target("state.plans")).write_freeze_record(
                day, {"latched": True},
            )
            view = load_today(workspace, day)
            self.assertIsNone(view["timetable"])
            self.assertIsNotNone(view["preflight"].get("freeze"))
            self.assertEqual(view["reviews"], [])
            queue_view = load_queue_view(workspace, day)
            self.assertIsNotNone(queue_view["freeze"])
            self.assertEqual(queue_view["caps"], {
                "soft_target_minutes": 0, "hard_cap_minutes": 0,
                "soft_source": "freeze", "hard_source": "freeze",
                "subject_review_quotas": None,
            })
            self.assertEqual(queue_view["selected"], [])
            self.assertTrue(all(value == {"count": 0, "minutes": 0}
                                for value in queue_view["buckets"].values()))

    def test_registered_timetable_outside_every_semester_maps_to_null(self) -> None:
        # M18 returns None for a day outside every semester; the view must not crash (sol 279 N1).
        outside = SimpleNamespace(day=lambda day, base_minutes: None,
                                  minutes_for=lambda day, base_minutes: None)
        with tempfile.TemporaryDirectory() as temporary:
            workspace = self._workspace(Path(temporary))
            with patch("ky.today.port.timetable_for_workspace", return_value=outside):
                view = load_today(workspace, date(2027, 8, 1))
        self.assertIsNone(view["timetable"])

    def test_success_record_matches_cli_event_and_queue_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            api_workspace = self._workspace_with_reviews(root / "api")
            cli_workspace = self._workspace_with_reviews(root / "cli")
            day = date(2026, 10, 2)
            view = load_today(api_workspace, day)
            review_id = view["reviews"][0]["review_id"]
            record_day(api_workspace, day, {review_id: "correct"}, study_minutes=20,
                       expected_view_hash=view["view_hash"])

            cli_view = load_today(cli_workspace, day)
            self.assertEqual(cli_view["reviews"][0]["review_id"], review_id)
            event_path = root / "done.yaml"
            event_path.write_text(yaml.safe_dump({
                "schema_version": 3, "day": day.isoformat(),
                "reviews": [{"review_id": review_id, "completed_on": day.isoformat(),
                             "check": cli_view["reviews"][0].get("check") or "recall_vs_notes",
                             "outcome": "correct"}],
                "vocab": {"delivered_words": [], "practiced_words": []},
                "study_minutes": 20,
            }, allow_unicode=True, sort_keys=False), encoding="utf-8")
            command = ["py", "-3.12", "-m", "ky", "day-plan", "record",
                       "--done", str(event_path), "--store",
                       str(cli_workspace.write_target("state.plans")), "--review-store",
                       str(cli_workspace.write_target("state.review_queue")), "--config",
                       str(cli_workspace.require("settings.exam_config")), "--workspace",
                       str(cli_workspace.source)]
            result = subprocess.run(command, cwd=root, capture_output=True, env={
                **os.environ, "KY_WORKSPACE": str(cli_workspace.source),
                "PYTHONPATH": str(ROOT),
            })
            self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
            api_events = sorted(api_workspace.write_target("state.plans").rglob(
                "completion--*.yaml"))
            cli_events = sorted(cli_workspace.write_target("state.plans").rglob(
                "completion--*.yaml"))
            self.assertEqual([path.read_bytes() for path in api_events],
                             [path.read_bytes() for path in cli_events])
            api_items = ReviewShardStore(
                api_workspace.write_target("state.review_queue")
            ).load()
            cli_items = ReviewShardStore(
                cli_workspace.write_target("state.review_queue")
            ).load()
            self.assertEqual(api_items, cli_items)

    def test_partial_event_failure_can_be_replayed_and_replay_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = self._workspace_with_reviews(Path(temporary))
            day = date(2026, 10, 2)
            view = load_today(workspace, day)
            review_id = view["reviews"][0]["review_id"]
            from ky.today.record import record_loaded_event as run_loaded

            def fail_queue(workspace_arg, event, config, store_path, queue, **loaded):
                return run_loaded(
                    workspace_arg, event, config, store_path, queue,
                    advance_handler=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                        ContractError("injected queue failure")
                    ),
                    **loaded,
                )

            with patch("ky.today.port.record_loaded_event", side_effect=fail_queue):
                with self.assertRaises(RecordPipelineError) as raised:
                    record_day(workspace, day, {review_id: "correct"}, study_minutes=None,
                               expected_view_hash=view["view_hash"])
            self.assertEqual(raised.exception.stage, "event_written")
            store = DayPlanStore(workspace.write_target("state.plans"))
            self.assertIsNotNone(store.load_completion_event(day))
            pending_view = load_today(workspace, day)
            self.assertIsNotNone(pending_view["recorded"])
            self.assertFalse(pending_view["recorded"]["advanced"])
            self.assertFalse(ReviewShardStore(
                workspace.write_target("state.review_queue")
            ).calculated_completion_ids())
            first = advance_recorded_day(workspace, day)
            second = advance_recorded_day(workspace, day)
            self.assertTrue(first["advanced"])
            self.assertTrue(second["advanced"])
            self.assertTrue(first["advanced_review_ids"])
            self.assertFalse(second["advanced_review_ids"])
            self.assertTrue(second["replayed_review_ids"])

    def test_oserror_failures_keep_the_last_durable_stage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = self._workspace_with_reviews(Path(temporary))
            day = date(2026, 10, 2)
            view = load_today(workspace, day)
            from ky.today.record import record_loaded_event as run_loaded

            with patch.object(DayPlanStore, "write_completion_event",
                              side_effect=OSError("injected completion IO failure")):
                with self.assertRaises(RecordPipelineError) as raised:
                    record_day(workspace, day, {}, study_minutes=5,
                               expected_view_hash=view["view_hash"])
            self.assertEqual(raised.exception.stage, "rejected")

            items = yaml.safe_load(
                (ROOT / "tests/fixtures/reviews/reviews-normal.yaml").read_text(
                    encoding="utf-8"
                )
            )["items"]
            queue = ReviewShardStore(workspace.write_target("state.review_queue"))
            queue.write(items)
            day = date(2026, 10, 3)
            view = load_today(workspace, day)
            review_id = view["reviews"][0]["review_id"]

            def fail_queue(*_args, **_kwargs):
                raise OSError("injected queue IO failure")

            with patch("ky.today.port.record_loaded_event", side_effect=lambda *args, **kwargs:
                    run_loaded(*args, **kwargs, advance_handler=fail_queue)):
                with self.assertRaises(RecordPipelineError) as raised:
                    record_day(workspace, day, {review_id: "correct"}, study_minutes=None,
                               expected_view_hash=view["view_hash"])
            self.assertEqual(raised.exception.stage, "event_written")
            self.assertIsNotNone(DayPlanStore(
                workspace.write_target("state.plans")
            ).load_completion_event(day))

    def test_freeze_written_stage_tracks_only_a_new_freeze_event(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = self._workspace_with_reviews(Path(temporary))
            queue = ReviewShardStore(workspace.write_target("state.review_queue"))
            items = yaml.safe_load(
                (ROOT / "tests/fixtures/reviews/reviews-normal.yaml").read_text(
                    encoding="utf-8"
                )
            )["items"]
            config = load_config(workspace.require("settings.exam_config"))
            threshold = config.review_hard_cap_minutes() * 3
            item_count = threshold // 30 + 1
            template = items[0]
            items = [dict(template, review_id=f"rv_math1_limit_{index:04d}")
                     for index in range(1, item_count + 1)]
            for item in items:
                item["estimated_minutes"] = 30
                item["introduced_on"] = "2026-08-01"
                item["last_reviewed_on"] = "2026-08-30"
                item["due_date"] = "2026-09-01"
            queue.write(items)
            day = date(2026, 10, 2)
            view = load_today(workspace, day)
            self.assertIsNotNone(view["preflight"].get("freeze"))
            with patch.object(DayPlanStore, "write_completion_event",
                              side_effect=OSError("injected event write failure")):
                with self.assertRaises(RecordPipelineError) as raised:
                    record_day(workspace, day, {}, study_minutes=5,
                               expected_view_hash=view["view_hash"])
            self.assertEqual(raised.exception.stage, "freeze_written")
            plans = DayPlanStore(workspace.write_target("state.plans"))
            self.assertTrue(plans.freeze_events())
            self.assertIsNone(plans.load_completion_event(day))
            refreshed = load_today(workspace, day)
            record_day(workspace, day, {}, study_minutes=5,
                       expected_view_hash=refreshed["view_hash"])
            self.assertEqual(len(plans.freeze_events()), 1)

    def test_today_carries_review_kinds_and_schedule_context(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = self._workspace_with_reviews(Path(temporary))
            records = [
                {"review_id": "missing", "title": "缺题", "level": "learned"},
                {"review_id": "adapted", "title": "改编题", "level": "learned",
                 "question": {"question": "x<0", "choices": ["A"]}},
                {"review_id": "past", "title": "真题", "level": "progressing",
                 "question_ref": "2025-1", "check": "past_question"},
            ]
            schedule = type("Schedule", (), {
                "semester": "term", "week": 3, "weekday_used": 2,
                "no_class": False, "blocks": 4, "free_minutes": 120,
            })()
            phase = type("Phase", (), {
                "start": date(2026, 10, 1), "end_exclusive": date(2026, 11, 1),
                "label": "阶段甲", "review_minutes": {"math1": 10},
            })()
            route = type("Route", (), {"phases": (phase,)})()
            budget = SimpleNamespace(
                total_minutes=120, total_source="config", base_minutes=120,
                base_source="config", subject_review_quotas=None,
            )
            pacing = load_settings({
                "schema_version": 1, "start": "2026-08-01", "exam_date": "2027-06-01",
                "base_daily_minutes": {"min": 60, "max": 180, "initial": 120},
                "max_step_minutes": 15, "cadence": [{"kind": "month"}],
            })
            missing_cycle = SimpleNamespace(end=date(2026, 9, 30))
            with patch("ky.today.port.build_review_questions", return_value=records), \
                    patch("ky.today.port.timetable_for_workspace", return_value=type(
                        "Timetable", (), {"day": lambda self, day, minutes: schedule}
                    )()), \
                    patch("ky.today.port.RoutePlanStore.current", return_value=route), \
                    patch("ky.today.port.resolve_day_budget", return_value=budget), \
                    patch("ky.today.port.settings_for_workspace", return_value=pacing), \
                    patch("ky.today.port.load_pacing_report_state",
                          return_value=((missing_cycle,), {})):
                view = load_today(workspace, date(2026, 10, 2))
            self.assertEqual([item["title"] for item in view["reviews"]],
                             ["缺题", "改编题", "真题"])
            self.assertEqual(view["timetable"]["week"], 3)
            self.assertEqual(view["route_phase"]["label"], "阶段甲")
            self.assertEqual(view["pacing"]["unreported_cycles"], ["2026-09-30"])
            self.assertIsNone(load_today(self._workspace(Path(temporary) / "empty"),
                                         date(2026, 10, 2))["timetable"])

    def test_fixed_cli_baseline_matrix_matches_process_and_output_tree(self) -> None:
        old_source = fixed_source(
            ROOT, BASELINE, "ky/__main__.py",
            lambda source: b"def _day_plan_record_freeze(" in source
            and b"def _day_plan_record_advance_queue(" in source,
        )
        legacy_record_identity = (
            b"def _day_plan_record_freeze(" in old_source
            and b"def _day_plan_record_advance_queue(" in old_source
        )
        self.assertTrue(legacy_record_identity)
        current_source = (ROOT / "ky/__main__.py").read_bytes()
        self.assertFalse(
            b"def _day_plan_record_freeze(" in current_source
            and b"def _day_plan_record_advance_queue(" in current_source
        )
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            baseline_root = temp / "baseline"
            archive = subprocess.run(
                ["git", "archive", BASELINE], cwd=ROOT, check=True, capture_output=True,
            ).stdout
            archive_path = temp / "baseline.tar"
            archive_path.write_bytes(archive)
            baseline_root.mkdir()
            with tarfile.open(archive_path) as bundle:
                bundle.extractall(baseline_root, filter="data")

            seed = temp / "seed"
            workspace = self._workspace_with_reviews(seed)
            registry_path = workspace.source
            registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
            registry["reference"]["exam_indexes"] = {}
            registry["state"]["question_bank"] = "state/question_bank"
            registry["settings"]["pacing"] = "settings/pacing.yaml"
            registry_path.write_text(
                yaml.safe_dump(registry, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            for subject in ("math1", "cs408"):
                registry["reference"]["exam_indexes"][subject] = [
                    f"indexes/{subject}.json"
                ]
                index_path = seed / "indexes" / f"{subject}.json"
                index_path.parent.mkdir(parents=True, exist_ok=True)
                index_path.write_text('{"entries": []}', encoding="utf-8")
            registry_path.write_text(
                yaml.safe_dump(registry, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            weights = seed / "weights/topic_weights.json"
            weights.parent.mkdir(parents=True, exist_ok=True)
            weights.write_text('{"per_question": {}}', encoding="utf-8")
            bank_dir = seed / "state/question_bank/math1.limit.equivalent-infinitesimal"
            bank_dir.mkdir(parents=True)
            bank_question = {
                "schema_version": 1,
                "id": "qb-math1.limit.equivalent-infinitesimal-01",
                "knowledge_point_id": "math1.limit.equivalent-infinitesimal",
                "difficulty": "basic", "basis": "syllabus", "based_on": [],
                "stem": "合成基线题面", "answer": "合成答案", "validation": "guided",
                "created_by": "ai:test-model", "created_on": "2026-10-01",
            }
            (bank_dir / "qb-math1.limit.equivalent-infinitesimal-01.yaml").write_text(
                yaml.safe_dump(bank_question, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            pacing = seed / "settings/pacing.yaml"
            pacing.parent.mkdir(parents=True, exist_ok=True)
            pacing.write_text(yaml.safe_dump({
                "schema_version": 1, "start": "2026-08-01", "exam_date": "2027-06-01",
                "base_daily_minutes": {"min": 60, "max": 180, "initial": 120},
                "max_step_minutes": 15, "cadence": [{"kind": "month"}],
            }, sort_keys=False), encoding="utf-8")
            usage = seed / "usage.json"
            usage.write_text('{"math1": 45}', encoding="utf-8")
            reviews = seed / "reviews.yaml"
            reviews.write_bytes(
                (ROOT / "tests/fixtures/reviews/reviews-normal.yaml").read_bytes()
            )
            done = seed / "empty-event.yaml"
            done.write_text(yaml.safe_dump({
                "schema_version": 3, "day": "2026-10-02", "reviews": [],
                "vocab": {"delivered_words": [], "practiced_words": []},
                "study_minutes": 5,
            }, sort_keys=False), encoding="utf-8")
            done_review = seed / "review-event.yaml"
            done_review.write_text(yaml.safe_dump({
                "schema_version": 3, "day": "2026-09-15",
                "reviews": [{"review_id": "rv_math1_limit_0001",
                             "completed_on": "2026-09-15",
                             "check": "recall_vs_notes", "outcome": "correct"}],
                "vocab": {"delivered_words": [], "practiced_words": []},
                "study_minutes": 5,
            }, sort_keys=False), encoding="utf-8")

            frozen_seed = temp / "frozen-seed"
            shutil.copytree(seed, frozen_seed)
            frozen_workspace = load_workspace(
                frozen_seed / WORKSPACE_FILENAME
            )
            DayPlanStore(frozen_workspace.write_target("state.plans")).write_freeze_record(
                date(2026, 9, 12), {"latched": True},
            )

            cases = [
                ("preflight registered defaults text", seed, True,
                 lambda root: ["preflight", "--config", str(root / "config.yaml"),
                               "--workspace", str(root / WORKSPACE_FILENAME),
                               "--date", "2026-09-12"]),
                ("preflight registered defaults json", seed, True,
                 lambda root: ["preflight", "--config", str(root / "config.yaml"),
                               "--workspace", str(root / WORKSPACE_FILENAME),
                               "--date", "2026-09-12", "--json"]),
                ("preflight explicit without registry", seed, False,
                 lambda root: ["preflight", "--config", str(root / "config.yaml"),
                               "--items", str(root / "reviews.yaml"),
                               "--date", "2026-09-12"]),
                ("preflight usage file", seed, True,
                 lambda root: ["preflight", "--config", str(root / "config.yaml"),
                               "--workspace", str(root / WORKSPACE_FILENAME),
                               "--usage", str(root / "usage.json"), "--date", "2026-09-12",
                               "--json"]),
                ("preflight urgent and freeze policy", seed, True,
                 lambda root: ["preflight", "--config", str(root / "config.yaml"),
                               "--workspace", str(root / WORKSPACE_FILENAME),
                               "--urgent-overdue-days", "0", "--urgent-defer-count", "0",
                               "--freeze-backlog-days", "1", "--date", "2026-09-12",
                               "--json"]),
                ("preflight latched freeze day", frozen_seed, True,
                 lambda root: ["preflight", "--config", str(root / "config.yaml"),
                               "--workspace", str(root / WORKSPACE_FILENAME),
                               "--date", "2026-09-12", "--json"]),
                ("review questions text with adapted retirement prompt", seed, True,
                 lambda root: ["review-questions", "--workspace",
                               str(root / WORKSPACE_FILENAME), "--date", "2026-09-12"]),
                ("review questions json with adapted question", seed, True,
                 lambda root: ["review-questions", "--workspace",
                               str(root / WORKSPACE_FILENAME), "--date", "2026-09-12",
                               "--json"]),
                ("pacing status", seed, True,
                 lambda root: ["pacing", "status", "--workspace",
                               str(root / WORKSPACE_FILENAME), "--today", "2026-10-02"]),
                ("record explicit stores", seed, True,
                 lambda root: ["day-plan", "record", "--done", str(root / "empty-event.yaml"),
                               "--store", str(root / "state/plans"), "--review-store",
                               str(root / "state/review_queue"), "--config",
                               str(root / "config.yaml"), "--workspace",
                               str(root / WORKSPACE_FILENAME)]),
                ("record registered defaults", seed, True,
                 lambda root: ["day-plan", "record", "--done", str(root / "empty-event.yaml"),
                               "--workspace", str(root / WORKSPACE_FILENAME)]),
                ("record registered defaults json", seed, True,
                 lambda root: ["day-plan", "record", "--done", str(root / "empty-event.yaml"),
                               "--workspace", str(root / WORKSPACE_FILENAME), "--json"]),
                ("record registered defaults with review advance", seed, True,
                 lambda root: ["day-plan", "record", "--done",
                               str(root / "review-event.yaml"), "--review-store",
                               str(root / "state/review_queue"), "--workspace",
                               str(root / WORKSPACE_FILENAME)]),
            ]

            def run_case(case, source_root):
                name, source_seed, use_registry, build_args = case
                runtime = temp / "runtime"

                def run():
                    if runtime.exists():
                        shutil.rmtree(runtime)
                    shutil.copytree(source_seed, runtime)
                    if not use_registry:
                        (runtime / WORKSPACE_FILENAME).unlink()
                    args = build_args(runtime)
                    env = os.environ.copy()
                    env["PYTHONPATH"] = str(source_root)
                    env.pop("KY_WORKSPACE", None)
                    if use_registry:
                        env["KY_WORKSPACE"] = str(runtime / WORKSPACE_FILENAME)
                    process = subprocess.run(
                        ["py", "-3.12", "-m", "ky", *args], cwd=runtime,
                        env=env, capture_output=True,
                    )
                    result = ProcessResult(process.returncode, process.stdout, process.stderr)
                    return result, output_tree(runtime)

                return run

            for case in cases:
                with self.subTest(branch=case[0]):
                    old_result, old_files = run_case(case, baseline_root)()
                    new_result, new_files = run_case(case, ROOT)()
                    if b"--reason <" in old_result.stdout:
                        self._assert_only_retire_hint_differs(
                            old_result, old_files, new_result, new_files,
                        )
                    else:
                        compare_results(old_result, new_result, old_files, new_files)
                    if "review questions text" in case[0]:
                        self.assertIn("有问题可停用".encode("utf-8"), new_result.stdout)

    def _assert_only_retire_hint_differs(
        self, old_result, old_files, new_result, new_files,
    ) -> None:
        """Allow exactly the retirement hint line to differ from baseline 60a4fd2.

        sol 289 M2: only the reason placeholder may change in this line.
        The hint quotes that placeholder so the printed command
        parses in PowerShell. Every other byte of the branch stays identical; the
        allowance is written down in contracts/today.md §6 (AGENTS.md rule 12).
        """
        old_lines = old_result.stdout.splitlines(keepends=True)
        new_lines = new_result.stdout.splitlines(keepends=True)
        self.assertEqual(len(old_lines), len(new_lines))
        differences = [
            (old, new) for old, new in zip(old_lines, new_lines) if old != new
        ]
        self.assertEqual(len(differences), 1, differences)
        old_line, new_line = differences[0]
        old_hint = "--reason <原因>".encode("utf-8")
        new_hint = '--reason "替换为原因"'.encode("utf-8")
        self.assertEqual(old_line.count(old_hint), 1)
        self.assertEqual(new_line, old_line.replace(old_hint, new_hint, 1))
        normalized = b"".join(
            old if old != new else new for old, new in zip(old_lines, new_lines)
        )
        compare_results(
            old_result,
            ProcessResult(new_result.returncode, normalized, new_result.stderr),
            old_files,
            new_files,
        )

    def test_event_written_baseline_adds_only_recovery_command_line(self) -> None:
        old_source = fixed_source(
            ROOT, BASELINE, "ky/__main__.py",
            lambda source: b"def _day_plan_record(" in source
            and b"def review_questions_main(" in source,
        )
        self.assertIn(b"def _day_plan_record(", old_source)
        self.assertIn(b"def _day_plan_record_freeze(", old_source)
        self.assertIn(b"def _day_plan_record_advance_queue(", old_source)
        self.assertNotIn(b"def _day_plan_record_freeze(",
                         (ROOT / "ky/__main__.py").read_bytes())
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            baseline_root = temp / "baseline"
            archive_path = temp / "baseline.tar"
            archive_path.write_bytes(subprocess.run(
                ["git", "archive", BASELINE], cwd=ROOT, check=True, capture_output=True,
            ).stdout)
            baseline_root.mkdir()
            with tarfile.open(archive_path) as bundle:
                bundle.extractall(baseline_root, filter="data")
            seed = temp / "seed"
            workspace = self._workspace_with_reviews(seed)
            event_path = seed / "done.yaml"
            event_path.write_text(yaml.safe_dump({
                "schema_version": 3, "day": "2026-10-02",
                "reviews": [{"review_id": "rv_math1_limit_0001",
                             "completed_on": "2026-10-02", "check": "recall_vs_notes",
                             "outcome": "correct"}],
                "vocab": {"delivered_words": [], "practiced_words": []},
                "study_minutes": 5,
            }, sort_keys=False), encoding="utf-8")
            sitecustomize = seed / "sitecustomize.py"
            sitecustomize.write_text(
                "import ky.storage.day_plan_store as store\n"
                "from ky.models import ContractError\n"
                "def fail_advance(*args, **kwargs):\n"
                "    raise ContractError('injected queue failure', 'review_queue')\n"
                "store.advance_review_queue = fail_advance\n",
                encoding="utf-8",
            )
            runtime = temp / "runtime"
            args = ["day-plan", "record", "--done", str(runtime / "done.yaml"),
                    "--store", str(runtime / "state/plans"), "--review-store",
                    str(runtime / "state/review_queue"), "--config",
                    str(runtime / "config.yaml"), "--workspace",
                    str(runtime / WORKSPACE_FILENAME)]

            def run(source_root):
                if runtime.exists():
                    shutil.rmtree(runtime)
                shutil.copytree(seed, runtime)
                env = os.environ.copy()
                env["PYTHONPATH"] = str(source_root) + os.pathsep + str(runtime)
                env["KY_WORKSPACE"] = str(runtime / WORKSPACE_FILENAME)
                env["PYTHONDONTWRITEBYTECODE"] = "1"
                process = subprocess.run(
                    ["py", "-3.12", "-m", "ky", *args], cwd=runtime,
                    env=env, capture_output=True,
                )
                return (ProcessResult(process.returncode, process.stdout, process.stderr),
                        output_tree(runtime))

            old_result, old_tree = run(baseline_root)
            new_result, new_tree = run(ROOT)
            self.assertEqual(old_result.returncode, new_result.returncode)
            self.assertEqual(old_result.stdout, new_result.stdout)
            self.assertEqual(new_tree, old_tree)
            recovery = subprocess.list2cmdline([
                "py", "-3.12", "-m", "ky", "day-plan", "advance", "--date",
                "2026-10-02", "--store", str(runtime / "state/plans"),
                "--review-store", str(runtime / "state/review_queue"), "--config",
                str(runtime / "config.yaml"), "--workspace",
                str(runtime / WORKSPACE_FILENAME),
            ]).encode("utf-8") + os.linesep.encode("ascii")
            self.assertEqual(
                new_result.stderr, old_result.stderr + recovery,
                f"old={old_result.stderr!r}; new={new_result.stderr!r}; "
                f"expected={old_result.stderr + recovery!r}",
            )

    def test_recovery_command_pins_registered_default_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            seed = temp / "seed"
            workspace = self._workspace_with_reviews(seed)
            event = seed / "done.yaml"
            event.write_text(yaml.safe_dump({
                "schema_version": 3, "day": "2026-10-02",
                "reviews": [{"review_id": "rv_math1_limit_0001",
                             "completed_on": "2026-10-02",
                             "check": "recall_vs_notes", "outcome": "correct"}],
                "vocab": {"delivered_words": [], "practiced_words": []},
                "study_minutes": 5,
            }, sort_keys=False), encoding="utf-8")
            (seed / "sitecustomize.py").write_text(
                "import ky.storage.day_plan_store as store\n"
                "from ky.models import ContractError\n"
                "def fail_advance(*args, **kwargs):\n"
                "    raise ContractError('injected queue failure', 'review_queue')\n"
                "store.advance_review_queue = fail_advance\n",
                encoding="utf-8",
            )
            runtime = temp / "runtime"
            shutil.copytree(seed, runtime)
            runtime_workspace = load_workspace(runtime / WORKSPACE_FILENAME)
            expected_paths = (
                runtime_workspace.write_target("state.plans"),
                runtime_workspace.write_target("state.review_queue"),
                runtime_workspace.require("settings.exam_config"),
            )
            env = os.environ.copy()
            env["PYTHONPATH"] = str(ROOT) + os.pathsep + str(runtime)
            env.pop("KY_WORKSPACE", None)
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            process = subprocess.run(
                ["py", "-3.12", "-m", "ky", "day-plan", "record", "--done",
                 str(runtime / "done.yaml"), "--review-store", str(expected_paths[1])],
                cwd=runtime, env=env, capture_output=True,
            )
            self.assertEqual(process.returncode, 2, process.stderr.decode("utf-8"))
            stderr = process.stderr.decode("utf-8")
            recovery = stderr.splitlines()[-1]
            for option, path in zip(("--store", "--review-store", "--config"),
                                    expected_paths):
                self.assertIn(option, recovery)
                self.assertIn(str(path), recovery)
            self.assertIn("--workspace", recovery)
            self.assertIn(str(runtime / WORKSPACE_FILENAME), recovery)


if __name__ == "__main__":
    unittest.main()
