from __future__ import annotations

import hashlib
import json
import argparse
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

from ky.models import ContractError, load_config, load_review_items
from ky.pacing.port import (
    PacingCycle, apply_pacing, build_report, cycle_for_date, load_settings,
    load_settings_file,
)
from ky.pacing.storage import read_report, report_path, write_report_once
from ky.pacing.cli import _read_previous
from ky.schedule.completion import CompletionEvent, ReviewCompletion
from ky.schedule.longitudinal import DayPlan
from ky.schedule.planning import Phase, RoutePlan, validate_route_plan
from ky.storage.day_plan_store import DayPlanStore
from ky.storage.review_shards import ReviewShardStore
from ky.storage.route_store import RoutePlanStore
from ky.workspace import WORKSPACE_FILENAME, load_workspace
from tests._baseline_harness import (
    ProcessResult, compare_runs, fixed_source, load_isolated, output_tree,
)

ROOT = Path(__file__).resolve().parents[2]
BASELINE = "dcbb5b6"
CONFIG = ROOT / "tests/fixtures/config/config-minimal.yaml"
REVIEWS = ROOT / "tests/fixtures/reviews/reviews-normal.yaml"


def settings_doc(**changes):
    result = {
        "schema_version": 1, "start": "2026-10-01", "exam_date": "2028-12-23",
        "base_daily_minutes": {"min": 120, "max": 240, "initial": 180},
        "max_step_minutes": 30,
        "cadence": [{"kind": "half_month", "until": "2026-12-01"},
                    {"kind": "month"}],
    }
    result.update(changes)
    return result


class PacingSettingsContractTests(unittest.TestCase):
    def test_settings_rules_and_cycle_boundaries(self) -> None:
        invalid = []
        for key in ("schema_version", "start", "exam_date", "base_daily_minutes",
                    "max_step_minutes", "cadence"):
            item = settings_doc()
            del item[key]
            invalid.append(item)
        invalid.extend([
            settings_doc(extra=True),
            settings_doc(schema_version=True),
            settings_doc(start="20261001"),
            settings_doc(exam_date=datetime(2028, 12, 23)),
            settings_doc(exam_date="2026-10-01"),
            settings_doc(base_daily_minutes={"min": -1, "max": 3, "initial": 2}),
            settings_doc(base_daily_minutes={"min": True, "max": 3, "initial": 2}),
            settings_doc(base_daily_minutes={"min": 0, "max": False, "initial": 0}),
            settings_doc(base_daily_minutes={"min": 0, "max": 3, "initial": True}),
            settings_doc(base_daily_minutes={"min": 4, "max": 3, "initial": 3}),
            settings_doc(base_daily_minutes={"min": 2, "max": 4, "initial": 1}),
            settings_doc(base_daily_minutes={"min": 2, "max": 4, "initial": 5}),
            settings_doc(max_step_minutes=True),
            settings_doc(cadence=[]),
            settings_doc(cadence=[{"kind": "other"}]),
            settings_doc(cadence=[{"kind": "month", "until": "2026-10-01"},
                                  {"kind": "month"}]),
            settings_doc(cadence=[{"kind": "month", "until": "2026-11-01"}]),
            settings_doc(cadence=[{"kind": "half_month", "until": "2026-12-01"},
                                  {"kind": "month", "until": "2026-11-01"},
                                  {"kind": "month"}]),
            settings_doc(cadence=[{"kind": "month", "until": "2026-11-16"},
                                  {"kind": "half_month"}]),
            settings_doc(cadence=[{"kind": "half_month", "until": "2026-11-16"},
                                  {"kind": "month"}]),
        ])
        for index, raw in enumerate(invalid):
            with self.subTest(case=index), self.assertRaises(ContractError):
                load_settings(raw)

        settings = load_settings(settings_doc())
        cases = {
            date(2026, 10, 1): (date(2026, 10, 1), date(2026, 10, 15)),
            date(2026, 10, 16): (date(2026, 10, 16), date(2026, 10, 31)),
            date(2026, 11, 30): (date(2026, 11, 16), date(2026, 11, 30)),
            date(2026, 12, 1): (date(2026, 12, 1), date(2026, 12, 31)),
        }
        for day, expected in cases.items():
            cycle = cycle_for_date(settings, day)
            self.assertEqual((cycle.start, cycle.end), expected)
        leap = load_settings(settings_doc(start="2028-02-01", exam_date="2028-12-01",
            cadence=[{"kind": "half_month", "until": "2028-03-01"},
                     {"kind": "month"}]))
        self.assertEqual(cycle_for_date(leap, date(2028, 2, 29)).end, date(2028, 2, 29))
        nonleap = load_settings(settings_doc(start="2027-02-01", exam_date="2027-12-01",
            cadence=[{"kind": "half_month", "until": "2027-03-01"},
                     {"kind": "month"}]))
        self.assertEqual(cycle_for_date(nonleap, date(2027, 2, 28)).end,
                         date(2027, 2, 28))
        self.assertIsNone(cycle_for_date(settings, date(2026, 9, 30)))
        starts_midmonth = load_settings(settings_doc(start="2026-10-16"))
        self.assertEqual(cycle_for_date(starts_midmonth, date(2026, 10, 16)).start,
                         date(2026, 10, 16))

        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "duplicate.yaml"
            path.write_text("schema_version: 1\nschema_version: 1\n", encoding="utf-8")
            with self.assertRaises(ContractError):
                load_settings_file(str(path))

    def test_start_off_boundary_snaps_to_nearer_boundary(self) -> None:
        def first(start: str, cadence=None) -> tuple[date, date]:
            doc = settings_doc(start=start) if cadence is None else settings_doc(
                start=start, cadence=cadence)
            settings = load_settings(doc)
            cycle = cycle_for_date(settings, settings.start)
            return cycle.start, cycle.end

        month = [{"kind": "month"}]
        cases = {
            ("2026-10-08", None): (date(2026, 10, 8), date(2026, 10, 15)),
            ("2026-10-09", None): (date(2026, 10, 9), date(2026, 10, 31)),
            ("2026-10-13", None): (date(2026, 10, 13), date(2026, 10, 31)),
            ("2026-10-24", None): (date(2026, 10, 24), date(2026, 10, 31)),
            ("2026-11-27", None): (date(2026, 11, 27), date(2026, 12, 31)),
            ("2026-10-16", "month"): (date(2026, 10, 16), date(2026, 10, 31)),
            ("2026-10-20", "month"): (date(2026, 10, 20), date(2026, 11, 30)),
        }
        for (start, kind), expected in cases.items():
            with self.subTest(start=start, kind=kind):
                self.assertEqual(first(start, month if kind else None), expected)
        settings = load_settings(settings_doc(start="2026-10-08"))
        self.assertIsNone(cycle_for_date(settings, date(2026, 10, 7)))
        self.assertEqual(cycle_for_date(settings, date(2026, 10, 16)),
                         PacingCycle(date(2026, 10, 16), date(2026, 11, 1)))
        self.assertEqual(cycle_for_date(settings, date(2026, 12, 5)),
                         PacingCycle(date(2026, 12, 1), date(2027, 1, 1)))

    def test_boundary_starts_match_fixed_baseline_cycles(self) -> None:
        source = fixed_source(ROOT, "a1e83d9", "ky/pacing/port.py",
                              lambda raw: b"invalid start for first cadence kind" in raw)
        old = load_isolated(source, "pacing_port")
        cadences = ([{"kind": "half_month", "until": "2026-12-01"}, {"kind": "month"}],
                    [{"kind": "month"}], [{"kind": "half_month"}],
                    [{"kind": "month", "until": "2027-02-01"}, {"kind": "half_month"}])
        for start in ("2026-10-01", "2026-10-16", "2026-11-01"):
            for cadence in cadences:
                if cadence[0]["kind"] == "month" and start.endswith("16"):
                    continue
                doc = settings_doc(start=start, cadence=cadence)
                new_settings, old_settings = load_settings(doc), old.load_settings(doc)
                day = new_settings.start
                while day < date(2027, 6, 1):
                    new_cycle = cycle_for_date(new_settings, day)
                    old_cycle = old.cycle_for_date(old_settings, day)
                    self.assertEqual((new_cycle.start, new_cycle.end_exclusive),
                                     (old_cycle.start, old_cycle.end_exclusive))
                    day += timedelta(days=1)


class PacingRouteConversionTests(unittest.TestCase):
    def test_change_summary_uses_old_route_evidence_and_bounds(self) -> None:
        from contextlib import redirect_stdout
        from io import StringIO

        from ky.pacing.submit import _print_change_summary

        settings = load_settings(settings_doc())
        config = load_config(CONFIG)
        subjects = {subject.subject_id for subject in config.active_subjects()}
        old_route = RoutePlan("sample", 1, date(2026, 10, 1), date(2027, 1, 1),
            "test", "b" * 64,
            (Phase(0, date(2026, 10, 1), date(2027, 1, 1), "phase",
                   {subject: 10 for subject in subjects}, 180),))
        proposal = {
            "effective_from": "2026-10-17", "base_daily_minutes": 195,
            "review_minutes": {subject: 20 for subject in subjects},
            "rationale": [{"claim": "adjust", "evidence": ["report.base.mean"]}],
        }
        candidate = apply_pacing(old_route, {
            **proposal, "input_hash": "a" * 64,
        }, settings, date(2026, 10, 15))
        package = {"report": {"base": {"mean": 180}}}
        output = StringIO()
        with redirect_stdout(output):
            _print_change_summary(proposal, 180, old_route, candidate,
                                  {"exam_date": "2028-12-23"}, package)
        rendered = output.getvalue()
        for subject in subjects:
            self.assertIn(f"review_minutes.{subject}: 10 -> 20", rendered)
        self.assertIn("evidence: report.base.mean = 180", rendered)
        self.assertIn("调整在 2027-01-01 日阶段结束后失效", rendered)
        self.assertIn("生效日上限：2027-01-01（取自路线 target_exam_date）", rendered)
        self.assertIn("有课表的日子，M8 仍会按当日容量缩放复习配额", rendered)

    def test_five_route_conversion_boundaries(self) -> None:
        settings = load_settings(settings_doc())
        proposal = {
            "input_hash": "a" * 64,
            "effective_from": "2026-10-10",
            "base_daily_minutes": 195,
            "review_minutes": {"math1": 30},
        }
        first = Phase(0, date(2026, 10, 1), date(2026, 11, 1), "first",
                      {"math1": 20}, 180)
        second = Phase(1, date(2026, 11, 1), date(2027, 1, 1), "second",
                       {"math1": 25}, 185)
        route = RoutePlan("sample", 3, first.start, second.end_exclusive,
                          "test", "b" * 64, (first, second))
        d = date
        new = ({"math1": 30}, 195)
        old_first = ({"math1": 20}, 180)
        old_second = ({"math1": 25}, 185)
        # Each case lists every phase as (start, end_exclusive, label, review, base) so a
        # wrong-but-valid value in any kept, hit or later phase fails (sol 250 C4, 252).
        cases = (
            (None, "2026-10-10", 1, d(2026, 10, 10), d(2028, 12, 23), [
                (d(2026, 10, 10), d(2028, 12, 23), "复盘 2026-10-15", *new)]),
            (route, "2026-10-01", 4, first.start, second.end_exclusive, [
                (d(2026, 10, 1), d(2026, 11, 1), "first", *new),
                (d(2026, 11, 1), d(2027, 1, 1), "second", *old_second)]),
            (route, "2026-10-10", 4, first.start, second.end_exclusive, [
                (d(2026, 10, 1), d(2026, 10, 10), "first", *old_first),
                (d(2026, 10, 10), d(2026, 11, 1), "first · 复盘 2026-10-15", *new),
                (d(2026, 11, 1), d(2027, 1, 1), "second", *old_second)]),
            (route, "2026-11-01", 4, first.start, second.end_exclusive, [
                (d(2026, 10, 1), d(2026, 11, 1), "first", *old_first),
                (d(2026, 11, 1), d(2027, 1, 1), "second", *new)]),
            (route, "2026-11-10", 4, first.start, second.end_exclusive, [
                (d(2026, 10, 1), d(2026, 11, 1), "first", *old_first),
                (d(2026, 11, 1), d(2026, 11, 10), "second", *old_second),
                (d(2026, 11, 10), d(2027, 1, 1), "second · 复盘 2026-10-15", *new)]),
        )
        for source, effective, revision, start, end, expected in cases:
            with self.subTest(effective=effective, route=source is not None):
                candidate = apply_pacing(
                    source, {**proposal, "effective_from": effective}, settings,
                    date(2026, 10, 15),
                )
                self.assertEqual(candidate.revision, revision)
                self.assertEqual(candidate.start_date, start)
                self.assertEqual(candidate.target_exam_date, end)
                self.assertEqual(candidate.stage1_input_hash, "a" * 64)
                self.assertIs(validate_route_plan(candidate), candidate)
                self.assertEqual(
                    [(phase.index, phase.start, phase.end_exclusive, phase.label,
                      phase.review_minutes, phase.base_daily_minutes)
                     for phase in candidate.phases],
                    [(index, *row) for index, row in enumerate(expected)],
                )
                if source is None:
                    self.assertEqual(candidate.route_id, "pacing")
                else:
                    self.assertEqual(candidate.route_id, "sample")
                    self.assertEqual(candidate.policy_version, "test")

    def test_pacing_split_moves_targets_to_latter_phase_and_replace_keeps_them(self) -> None:
        settings = load_settings(settings_doc())
        start = date(2026, 10, 1)
        end = date(2028, 12, 23)
        targets = {"covered": 65, "consolidated": 30}
        route = RoutePlan(
            "sample", 3, start, end, "test", "b" * 64,
            (Phase(0, start, end, "phase", {"math1": 20}, 180, targets),),
        )
        proposal = {
            "input_hash": "a" * 64,
            "effective_from": "2026-11-01",
            "base_daily_minutes": 195,
            "review_minutes": {"math1": 30},
        }
        split = apply_pacing(route, proposal, settings, date(2026, 10, 15))
        self.assertIsNone(split.phases[0].targets)
        self.assertEqual(split.phases[1].targets, targets)

        replacement = apply_pacing(
            route, {**proposal, "effective_from": start.isoformat()}, settings,
            date(2026, 10, 15),
        )
        self.assertEqual(replacement.phases[0].targets, targets)

    def test_timetable_show_uses_registered_pacing_initial(self) -> None:
        from contextlib import redirect_stderr, redirect_stdout
        from io import StringIO
        from ky.__main__ import _timetable_show_date

        seen = []

        class Timetable:
            def day(self, day, base_minutes):
                seen.append((day, base_minutes))
                return None

        config = load_config(CONFIG)
        settings = load_settings(settings_doc())
        with redirect_stdout(StringIO()):
            result = _timetable_show_date(
                argparse.Namespace(date="2026-10-16"), Timetable(), config, None, settings,
            )
        self.assertEqual(result, 0)
        self.assertEqual(seen, [(date(2026, 10, 16), 180)])


class PacingWorkspaceContractTests(unittest.TestCase):
    def _registry(self, root: Path, settings: dict, local: bool = False) -> Path:
        doc = {
            "schema_version": 2,
            "subjects": {"alpha": {"name": "Alpha"}},
            "reference": {"knowledge_trees": {}, "exam_indexes": {}, "paper_shapes": {},
                "topic_weights": "data/weights.json", "vocabulary_db": "data/vocab.sqlite",
                "ledger": "data/ledger.yaml"},
            "supplementary": {}, "materials": {"raw_root": "data/raw"}, "products": {},
            "settings": {} if local else {"pacing": "settings/pacing.yaml"},
            "state": {"review_queue": "data/queue", "plans": "data/plans"},
            "staging": "staging", "projection": "data/projection.sqlite",
        }
        path = root / WORKSPACE_FILENAME
        path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
        if local:
            (root / "kaoyan.workspace.local.yaml").write_text(yaml.safe_dump({
                "schema_version": 1, "settings": {"pacing": "settings/pacing.yaml"}
            }, sort_keys=False), encoding="utf-8")
        return path

    def test_main_local_duplicate_and_absent_registration(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "settings").mkdir()
            (root / "settings/pacing.yaml").write_text("schema_version: 1\n", encoding="utf-8")
            main_path = self._registry(root, {}, False)
            self.assertEqual(load_workspace(main_path).pacing, root / "settings/pacing.yaml")
            local_path = self._registry(root, {}, True)
            self.assertEqual(load_workspace(local_path).pacing, root / "settings/pacing.yaml")
            doc = yaml.safe_load(main_path.read_text(encoding="utf-8"))
            doc["settings"] = {"pacing": "settings/pacing.yaml"}
            local = {"schema_version": 1, "settings": {"pacing": "settings/pacing.yaml"}}
            (root / "kaoyan.workspace.local.yaml").write_text(
                yaml.safe_dump(local), encoding="utf-8")
            main_path.write_text(yaml.safe_dump(doc), encoding="utf-8")
            with self.assertRaisesRegex(ContractError, "local.settings.pacing"):
                load_workspace(main_path)
            (root / "kaoyan.workspace.local.yaml").unlink()
            doc["settings"] = {}
            main_path.write_text(yaml.safe_dump(doc), encoding="utf-8")
            self.assertIsNone(load_workspace(main_path).pacing)


class PacingReportContractTests(unittest.TestCase):
    def test_completion_storage_writes_legacy_v2_or_v3_for_value(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            store = DayPlanStore(name)
            old = CompletionEvent(date(2026, 10, 1))
            old_path = Path(store.write_completion_event(old).path)
            self.assertIn(b"schema_version: 2\n", old_path.read_bytes())
            self.assertNotIn(b"study_minutes", old_path.read_bytes())
            self.assertIsNone(store.load_completion_event(date(2026, 10, 1)).study_minutes)
            new = CompletionEvent(date(2026, 10, 2), study_minutes=0)
            new_path = Path(store.write_completion_event(new).path)
            self.assertIn(b"schema_version: 3\n", new_path.read_bytes())
            self.assertIn(b"study_minutes: 0\n", new_path.read_bytes())
            self.assertEqual(store.load_completion_event(date(2026, 10, 2)).study_minutes, 0)

    def test_report_fields_and_write_once(self) -> None:
        config = load_config(CONFIG)
        settings = load_settings(settings_doc())
        cycle = PacingCycle(date(2026, 10, 1), date(2026, 10, 16))
        today = date(2026, 10, 20)
        samples = load_review_items(REVIEWS)
        subject = samples[0].subject_id
        item = replace(samples[0], review_id="r1", subject_id=subject,
                       state="queued", due_date=date(2026, 10, 19), estimated_minutes=12)
        next_item = replace(item, review_id="r-next", due_date=date(2026, 10, 25))
        late_review = ReviewCompletion("r1", date(2026, 10, 10), check="past_question",
                                       outcome="incorrect", completion_id="same")
        early_duplicate = ReviewCompletion("r1", date(2026, 10, 12), check="past_question",
                                           outcome="partial", completion_id="same")
        missing_review = ReviewCompletion("absent", date(2026, 10, 11), check="none",
                                          completion_id="unattributed")
        event = CompletionEvent(date(2026, 10, 14), (late_review, missing_review),
                                study_minutes=0)
        prior_event = CompletionEvent(date(2026, 10, 9), (early_duplicate,), study_minutes=None)
        freeze = (
            __import__("ky.freeze.port", fromlist=["FreezeEvent"]).FreezeEvent(
                1, "freeze", date(2026, 10, 10)),
            __import__("ky.freeze.port", fromlist=["FreezeEvent"]).FreezeEvent(
                2, "resume", date(2026, 10, 20)),
        )
        report = build_report(settings, config, cycle, today,
            plans=[DayPlan(date(2026, 10, 5), 170)], completions=(event, prior_event),
            items=(item, next_item), freeze_events=freeze,
            sources={"state/plans/a.yaml": "a" * 64})
        before_split = yaml.safe_load(
            (ROOT / "tests/fixtures/pacing/report-before-split.yaml").read_text(
                encoding="utf-8"))
        before_split["base"]["source_note"] = report["base"]["source_note"]
        before_split["base"].update({"min": 180, "max": 180, "mean": 180})
        before_split["reference_minutes"] = 2700
        before_split["reference_source_note"] = report["reference_source_note"]
        before_split.pop("report_hash")
        before_split["report_hash"] = hashlib.sha256(
            __import__("ky.planner.port", fromlist=["canonical_json_bytes"])
            .canonical_json_bytes(before_split)).hexdigest()
        self.assertEqual(report, before_split)
        class OneDayTimetable:
            def minutes_for(self, day, base_minutes):
                return 75 if day == date(2026, 10, 1) else None

        scheduled = build_report(settings, config, cycle, today,
            plans=[DayPlan(date(2026, 10, 5), 170)], completions=(event, prior_event),
            items=(item, next_item), freeze_events=freeze, timetable=OneDayTimetable(),
            sources={"state/plans/a.yaml": "a" * 64})
        self.assertEqual(report["reference_minutes"] - scheduled["reference_minutes"], 105)
        self.assertEqual(report["declared_minutes"], {"days": 1, "sum": 170})
        self.assertEqual(report["recorded_event_days"], 2)
        self.assertEqual(report["study_minutes"], {"days": 1, "sum": 0})
        self.assertEqual(report["reviews"][subject]["completed"], 1)
        self.assertEqual(report["reviews"][subject]["partial"], 1)
        self.assertEqual(report["duplicate_completion_ids"], 1)
        self.assertEqual(report["reviews_unattributed"], 1)
        self.assertEqual(report["backlog_observed"]["total"], 12)
        self.assertEqual(report["due_next"].get(subject), 24)
        self.assertTrue(report["freeze"]["latched_at_end"])
        self.assertIsNone(report["previous"])
        self.assertEqual(report["base"]["min"], 180)
        self.assertEqual(
            report["base"]["source_note"],
            "路线阶段 > 复盘设置 initial > 考试配置",
        )
        without_hash = dict(report)
        digest = without_hash.pop("report_hash")
        self.assertEqual(digest, hashlib.sha256(
            __import__("ky.planner.port", fromlist=["canonical_json_bytes"])
            .canonical_json_bytes(without_hash)).hexdigest())
        with tempfile.TemporaryDirectory() as name:
            target = report_path(name, cycle.end.isoformat())
            stored = write_report_once(target, report)
            target_bytes = target.read_bytes()
            changed_sources = dict(report, sources={"changed": "b" * 64})
            changed_sources.pop("report_hash")
            changed_sources["report_hash"] = hashlib.sha256(
                __import__("ky.planner.port", fromlist=["canonical_json_bytes"])
                .canonical_json_bytes(changed_sources)).hexdigest()
            again = write_report_once(target, changed_sources)
            self.assertEqual(again, stored)
            self.assertEqual(target.read_bytes(), target_bytes)
            self.assertEqual(read_report(target), stored)

    def test_previous_report_does_not_bridge_a_missing_cycle(self) -> None:
        settings = load_settings(settings_doc())
        current = cycle_for_date(settings, date(2026, 12, 5))
        with tempfile.TemporaryDirectory() as name:
            plans = Path(name)
            older = report_path(plans, "2026-10-31")
            older.parent.mkdir(parents=True)
            older.write_text("not read because November report is missing", encoding="utf-8")
            self.assertIsNone(_read_previous(settings, current, plans))


class PacingLegacyBaselineTests(unittest.TestCase):
    def test_legacy_commands_match_dcbb5b6(self) -> None:
        source = fixed_source(ROOT, BASELINE, "ky/workspace.py",
            lambda raw: b"class Workspace" in raw and b"pacing:" not in raw)
        self.assertIn(b"def load_workspace", source)
        archive = subprocess.run(["git", "archive", BASELINE, "ky"], cwd=ROOT,
                                 capture_output=True, check=True).stdout
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            old_root = base / "old"
            old_root.mkdir()
            with tarfile.open(fileobj=__import__("io").BytesIO(archive), mode="r:") as tar:
                tar.extractall(old_root, filter="data")
            workspace = base / "workspace"
            workspace.mkdir()
            (workspace / "config.yaml").write_bytes(CONFIG.read_bytes())
            doc = {
                "schema_version": 2,
                "subjects": {"math1": {"name": "Math"}, "eng1": {"name": "English"},
                             "cs408": {"name": "CS"}, "politics": {"name": "Politics"}},
                "reference": {"knowledge_trees": {}, "exam_indexes": {}, "paper_shapes": {},
                    "topic_weights": "data/weights.json", "vocabulary_db": "data/vocab.sqlite",
                    "ledger": "data/ledger.yaml"}, "supplementary": {},
                "materials": {"raw_root": "data/raw"}, "products": {},
                "settings": {"exam_config": "config.yaml"},
                "state": {"review_queue": "data/queue", "plans": "data/plans"},
                "staging": "staging", "projection": "data/projection.sqlite",
            }
            (workspace / WORKSPACE_FILENAME).write_text(
                yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
            ReviewShardStore(workspace / "data/queue").write(load_review_items(REVIEWS))
            (workspace / "data/plans").mkdir(parents=True)
            (workspace / "reviews.yaml").write_bytes(REVIEWS.read_bytes())
            (workspace / "done.yaml").write_text(
                "schema_version: 2\nday: 2026-09-15\nreviews: []\nvocab: {}\n",
                encoding="utf-8")
            seed = base / "seed"
            shutil.copytree(workspace, seed)
            old_env = os.environ.copy()
            old_env.pop("KY_WORKSPACE", None)

            def run(root: Path, args: list[str]):
                if workspace.exists():
                    shutil.rmtree(workspace)
                shutil.copytree(seed, workspace)
                env = old_env.copy()
                env["PYTHONPATH"] = str(root)
                process = subprocess.run([sys.executable, "-m", "ky", *args], cwd=workspace,
                    env=env, capture_output=True, check=False)
                return (ProcessResult(process.returncode, process.stdout, process.stderr),
                        output_tree(workspace))

            commands = (
                ["day-plan", "record", "--config", str(workspace / "config.yaml"),
                 "--done", str(workspace / "done.yaml"), "--store", str(workspace / "data/plans")],
                ["preflight", "--config", str(workspace / "config.yaml"),
                 "--items", str(workspace / "reviews.yaml"), "--date", "2026-09-15"],
                ["preflight", "--json", "--config", str(workspace / "config.yaml"),
                 "--items", str(workspace / "reviews.yaml"), "--date", "2026-09-15"],
                ["planner-input", "--kind", "day", "--date", "2026-09-15",
                 "--config", str(workspace / "config.yaml"), "--workspace",
                 str(workspace / WORKSPACE_FILENAME)],
            )
            for args in commands:
                with self.subTest(command=args[:2]):
                    result, _ = compare_runs(lambda: run(old_root, args),
                                             lambda: run(ROOT, args))
                    self.assertEqual(result.returncode, 0, result.stderr)


class PacingCliContractTests(unittest.TestCase):
    def test_submit_guardrail_rejections(self) -> None:
        from types import SimpleNamespace

        from ky.freeze.port import FreezeEvent
        from ky.pacing.submit import _check_evidence, _find_input, _validate_guardrails

        settings = load_settings(settings_doc())
        config = load_config(CONFIG)
        subjects = {subject.subject_id for subject in config.active_subjects()}
        proposal = {
            "effective_from": "2026-10-16", "base_daily_minutes": 180,
            "review_minutes": {subject: 20 for subject in subjects},
            "rationale": [{"claim": "adjust", "evidence": ["report.cycle.end"]}],
        }
        package = {"report": {"report_hash": "a" * 64, "cycle": {"end": "2026-10-15"}}}
        self.assertRaises(ContractError, _check_evidence,
            dict(proposal, rationale=[{"claim": "adjust", "evidence": ["report.missing"]}]),
            package)
        with tempfile.TemporaryDirectory() as temporary:
            self.assertRaises(ContractError, _find_input, Path(temporary), "a" * 64)
            plans = SimpleNamespace(freeze_events=lambda: ())
            snapshot = (config, None, None, None, None, plans, ())
            for invalid in (
                dict(proposal, effective_from="2026-10-15"),
                dict(proposal, base_daily_minutes=500),
                dict(proposal, base_daily_minutes=220),
                dict(proposal, review_minutes={"unknown": 10}),
                dict(proposal, review_minutes={subject: 100 for subject in subjects}),
            ):
                with self.subTest(proposal=invalid):
                    self.assertRaises(ContractError, _validate_guardrails, invalid, settings,
                        package, date(2026, 10, 15), date(2026, 10, 16), snapshot)
            frozen_snapshot = (*snapshot[:5],
                SimpleNamespace(freeze_events=lambda: (
                    FreezeEvent(1, "freeze", date(2026, 10, 16)),)), snapshot[6])
            self.assertRaises(ContractError, _validate_guardrails, proposal, settings,
                package, date(2026, 10, 15), date(2026, 10, 16), frozen_snapshot)
            route = RoutePlan("existing", 1, date(2026, 10, 17), date(2028, 12, 23),
                "policy-v1", "b" * 64,
                (Phase(0, date(2026, 10, 17), date(2028, 12, 23), "later", {}, 120),))
            self.assertRaises(ContractError, apply_pacing, route, {
                **proposal, "input_hash": "a" * 64,
            }, settings, date(2026, 10, 15))

    def test_interrupted_submit_dry_run_then_restore(self) -> None:
        from contextlib import redirect_stderr, redirect_stdout
        from io import StringIO

        from ky.pacing.submit import _route_state
        from ky.planner.port import canonical_json_bytes
        from ky.schedule.planning import route_plan_to_mapping
        from ky.storage.route_store import RoutePlanStore

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            route_store = RoutePlanStore(root / "routes")
            proposal = {
                "schema_version": 1, "kind": "pacing_proposal", "actor": "human",
                "input_hash": "a" * 64, "effective_from": "2026-10-16",
                "base_daily_minutes": 180, "review_minutes": {"math1": 30},
                "rationale": [{"claim": "adjust", "evidence": ["report.cycle.end"]}],
            }
            route = RoutePlan("pacing", 1, date(2026, 10, 16), date(2028, 12, 23),
                "pacing-v1", "a" * 64,
                (Phase(0, date(2026, 10, 16), date(2028, 12, 23), "pacing",
                       {"math1": 30}, 180),))
            route_mapping = route_plan_to_mapping(route)
            proposal_hash = hashlib.sha256(canonical_json_bytes(proposal)).hexdigest()
            route_hash = hashlib.sha256(canonical_json_bytes(route_mapping)).hexdigest()
            intent = {
                "schema_version": 1, "report_hash": "b" * 64,
                "input_hash": "a" * 64, "actor": "human", "proposal": proposal,
                "proposal_sha256": proposal_hash, "base_revision": 0,
                "target_revision": 1, "b0": 180, "route": route_mapping,
                "route_sha256": route_hash,
            }
            intent_path = root / "plans/pacing/applied--2026-10-15.yaml"
            intent_path.parent.mkdir(parents=True)
            intent_path.write_text(yaml.safe_dump(intent, sort_keys=False), encoding="utf-8")
            package = {
                "report": {"report_hash": "b" * 64,
                           "cycle": {"end": "2026-10-15"}},
                "settings": {"exam_date": "2028-12-23"},
                "current_route": None,
            }
            output = StringIO()
            with redirect_stdout(output):
                dry_status = _route_state(route_store, intent_path, proposal, package,
                                          date(2026, 10, 20), dry_run=True)
            self.assertEqual(dry_status, 0)
            self.assertIn("dry-run：将恢复提交", output.getvalue())
            self.assertFalse(route_store.manifest_path.exists())
            output = StringIO()
            with redirect_stdout(output):
                status = _route_state(route_store, intent_path, proposal, package,
                                      date(2026, 10, 20), dry_run=False)
            self.assertEqual(status, 0)
            self.assertEqual(route_store.current(), route)
            self.assertIn("已完成上次中断的提交", output.getvalue())
            self.assertIn("生效日已过", output.getvalue())
            revision_two = replace(route, revision=2, stage1_input_hash="c" * 64)
            revision_three = replace(route, revision=3, stage1_input_hash="d" * 64)
            route_store.write_route_plan(revision_two, actor="human")
            route_store.write_route_plan(revision_three, actor="human")
            for dry_run in (True, False):
                output = StringIO()
                with redirect_stdout(output):
                    historical = _route_state(
                        route_store, intent_path, proposal, package,
                        date(2026, 10, 20), dry_run=dry_run,
                    )
                self.assertEqual(historical, 0)
                self.assertIn(
                    "本报告已有提交（修订 1），实际应用如下；不发布"
                    f"{'（dry-run）' if dry_run else ''}", output.getvalue())
                self.assertIn("这是历史应用：当前路线已是修订 3，以当前路线为准",
                              output.getvalue())
                self.assertEqual(route_store.current(), revision_three)
            route_bytes = route_store.manifest_path.read_bytes()
            output = StringIO()
            with redirect_stdout(output):
                repeated = _route_state(route_store, intent_path, proposal, package,
                                        date(2026, 10, 20), dry_run=True)
            self.assertEqual(repeated, 0)
            self.assertEqual(route_store.current(), revision_three)
            self.assertEqual(route_store.manifest_path.read_bytes(), route_bytes)

            changed_store = RoutePlanStore(root / "changed-routes")
            other = RoutePlan("other", 1, date(2026, 10, 1), date(2028, 12, 23),
                "policy-v1", "c" * 64,
                (Phase(0, date(2026, 10, 1), date(2028, 12, 23), "other",
                       {"math1": 0}, 120),))
            changed_store.write_route_plan(other, actor="human")
            historical_intent = root / "plans/pacing/applied--2026-10-16.yaml"
            historical_intent.write_text(yaml.safe_dump(intent, sort_keys=False),
                                         encoding="utf-8")
            for dry_run in (True, False):
                output = StringIO()
                errors = StringIO()
                with redirect_stdout(output), redirect_stderr(errors):
                    historical = _route_state(changed_store, historical_intent, proposal,
                        package, date(2026, 10, 20), dry_run=dry_run)
                self.assertEqual(historical, 2)
                self.assertIn("历史应用；不发布", errors.getvalue())
                self.assertEqual(changed_store.current(), other)

    def test_report_cli_saved_report_repeat_and_exit_codes(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "data/queue").mkdir(parents=True)
            (root / "data/plans").mkdir(parents=True)
            (root / "data/availability.yaml").write_text(
                "schema_version: 1\ndays:\n  2026-10-01: 0\n", encoding="utf-8")
            (root / "settings").mkdir()
            (root / "config.yaml").write_bytes(CONFIG.read_bytes())
            pacing_file = root / "settings/pacing.yaml"
            pacing_file.write_text(yaml.safe_dump(settings_doc(), sort_keys=False),
                                   encoding="utf-8")
            doc = {
                "schema_version": 2,
                "subjects": {"math1": {"name": "Math"}, "eng1": {"name": "English"},
                    "cs408": {"name": "CS"}, "politics": {"name": "Politics"}},
                "reference": {"knowledge_trees": {}, "exam_indexes": {}, "paper_shapes": {},
                    "topic_weights": "data/weights.json", "vocabulary_db": "data/vocab.sqlite",
                    "ledger": "data/ledger.yaml"}, "supplementary": {},
                "materials": {"raw_root": "data/raw"}, "products": {},
                "settings": {"exam_config": "config.yaml", "pacing": "settings/pacing.yaml"},
                "state": {"review_queue": "data/queue", "plans": "data/plans",
                          "routes": "data/routes"},
                "staging": "staging", "projection": "data/projection.sqlite",
            }
            (root / WORKSPACE_FILENAME).write_text(yaml.safe_dump(doc, sort_keys=False),
                                                  encoding="utf-8")
            doc["state"]["availability"] = "data/availability.yaml"
            (root / WORKSPACE_FILENAME).write_text(yaml.safe_dump(doc, sort_keys=False),
                                                  encoding="utf-8")
            DayPlanStore(root / "data/plans").write_completion_event(
                CompletionEvent(date(2026, 10, 1)))
            queue_store = ReviewShardStore(root / "data/queue")
            queue_store.write(load_review_items(REVIEWS))
            queue_sources = queue_store.read_state_sources().sources
            external_config = root.parent / f"{root.name}-external-config.yaml"
            external_config.write_bytes(CONFIG.read_bytes())
            env = os.environ.copy()
            env.pop("KY_WORKSPACE", None)
            env["PYTHONPATH"] = str(ROOT)

            def invoke(*arguments):
                return subprocess.run([sys.executable, "-m", "ky", *arguments], cwd=root,
                    env=env, capture_output=True, check=False)

            args = ("pacing", "report", "--cycle-end", "2026-10-15", "--today", "2026-10-16")
            preflight_before = invoke("preflight", "--config", str(external_config),
                "--items", str(root / "data/queue"), "--workspace",
                str(root / WORKSPACE_FILENAME), "--date", "2026-10-16")
            self.assertEqual(preflight_before.returncode, 0,
                             preflight_before.stderr.decode("utf-8"))
            self.assertIn("daily budget       : 180 min",
                          preflight_before.stdout.decode("utf-8"))
            self.assertIn("尚无报告", preflight_before.stdout.decode("utf-8"))
            self.assertIn("复盘提醒：", preflight_before.stdout.decode("utf-8"))
            first = invoke(*args, "--config", str(external_config))
            self.assertEqual(first.returncode, 0, first.stderr.decode("utf-8"))
            target = root / "data/plans/pacing/report--2026-10-15.yaml"
            original = target.read_bytes()
            preflight_after = invoke("preflight", "--config", str(external_config),
                "--items", str(root / "data/queue"), "--workspace",
                str(root / WORKSPACE_FILENAME), "--date", "2026-10-16")
            self.assertEqual(preflight_after.returncode, 0,
                             preflight_after.stderr.decode("utf-8"))
            self.assertNotIn("复盘提醒：", preflight_after.stdout.decode("utf-8"))

            from unittest.mock import patch
            from ky.__main__ import resume_main, timetable_main
            from ky.freeze.resume import ResumePlan

            timetable_bases = []

            class FakeTimetable:
                def day(self, day, base_minutes):
                    timetable_bases.append((day, base_minutes))
                    return None

            with patch("ky.__main__.timetable_for_workspace", return_value=FakeTimetable()):
                shown = timetable_main(["show", "--date", "2026-10-16", "--config",
                    str(external_config), "--workspace", str(root / WORKSPACE_FILENAME)])
            self.assertEqual(shown, 0)
            self.assertEqual(timetable_bases, [(date(2026, 10, 16), 180)])
            resume_values = []

            def record_resume(day, config, items, **kwargs):
                resume_values.append(kwargs.get("pacing_initial"))
                return ResumePlan(day, (), (), 0, 0, None, (), 0)

            with patch("ky.__main__.plan_resume", side_effect=record_resume):
                resumed = resume_main(["--date", "2026-10-16", "--dry-run", "--config",
                    str(external_config), "--workspace", str(root / WORKSPACE_FILENAME)])
            self.assertEqual(resumed, 0)
            self.assertEqual(len(resume_values), 1)
            self.assertEqual(resume_values[0].initial, 180)
            first_mapping = yaml.safe_load(first.stdout.decode("utf-8"))
            self.assertEqual(first_mapping["reference_minutes"], 2520)
            self.assertEqual(first_mapping["base"]["min"], 180)
            self.assertEqual(first_mapping["base"]["source_note"],
                             "路线阶段 > 复盘设置 initial > 考试配置")
            self.assertIn(f"external:{external_config.resolve().as_posix()}",
                          first_mapping["sources"])
            day_input = invoke("planner-input", "--kind", "day", "--date", "2026-10-16",
                "--config", str(external_config), "--workspace", str(root / WORKSPACE_FILENAME))
            self.assertEqual(day_input.returncode, 0, day_input.stderr.decode("utf-8"))
            day_package_path = Path(day_input.stdout.decode("utf-8").splitlines()[0][7:])
            day_package = json.loads(day_package_path.read_text(encoding="utf-8"))
            self.assertEqual(day_package["availability"]["base_minutes"], 180)
            self.assertEqual(day_package["availability"]["base_source"], "pacing_initial")
            no_availability_doc = yaml.safe_load((root / WORKSPACE_FILENAME).read_text(
                encoding="utf-8"))
            del no_availability_doc["state"]["availability"]
            (root / WORKSPACE_FILENAME).write_text(
                yaml.safe_dump(no_availability_doc, sort_keys=False), encoding="utf-8")
            pacing_only_day = invoke("planner-input", "--kind", "day", "--date",
                "2026-10-16", "--config", str(external_config), "--workspace",
                str(root / WORKSPACE_FILENAME))
            self.assertEqual(pacing_only_day.returncode, 0,
                             pacing_only_day.stderr.decode("utf-8"))
            pacing_only_package_path = Path(
                pacing_only_day.stdout.decode("utf-8").splitlines()[0][7:])
            pacing_only_package = json.loads(
                pacing_only_package_path.read_text(encoding="utf-8"))
            self.assertEqual(pacing_only_package["availability"]["base_source"],
                             "pacing_initial")
            (root / WORKSPACE_FILENAME).write_text(
                yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
            pacing_input = invoke("planner-input", "--kind", "pacing", "--cycle-end",
                "2026-10-15", "--today", "2026-10-16", "--config", str(external_config),
                "--workspace", str(root / WORKSPACE_FILENAME))
            self.assertEqual(pacing_input.returncode, 0,
                             pacing_input.stderr.decode("utf-8"))
            pacing_package_path = Path(
                pacing_input.stdout.decode("utf-8").splitlines()[0][7:])
            pacing_package = json.loads(pacing_package_path.read_text(encoding="utf-8"))
            self.assertEqual(pacing_package["base_at"]["minutes"], 180)
            self.assertEqual(pacing_package["base_at"]["source"], "pacing_initial")
            proposal_path = root / "staging/pacing/proposal.yaml"
            proposal_path.parent.mkdir(parents=True)
            proposal = {
                "schema_version": 1, "kind": "pacing_proposal", "actor": "human",
                "input_hash": pacing_input.stdout.decode("utf-8").splitlines()[1].split()[-1],
                "effective_from": "2026-10-16", "base_daily_minutes": 180,
                "review_minutes": {subject.subject_id: 20 for subject in
                                   load_config(CONFIG).active_subjects()},
                "rationale": [{"claim": "adjust", "evidence": ["report.cycle.end"]}],
            }
            proposal_path.write_text(yaml.safe_dump(proposal, allow_unicode=True,
                sort_keys=False), encoding="utf-8")
            submit_args = ("pacing", "submit", "--from-staging", str(proposal_path),
                           "--today", "2026-10-16")
            stale_submit = invoke("pacing", "submit", "--from-staging", str(proposal_path),
                                  "--today", "2026-10-17")
            self.assertEqual(stale_submit.returncode, 2)
            self.assertFalse((root / "data/plans/pacing/applied--2026-10-15.yaml").exists())
            self.assertFalse((root / "data/routes/routes_manifest.yaml").exists())
            invalid_proposal = dict(proposal, effective_from="2026-10-15")
            proposal_path.write_text(yaml.safe_dump(invalid_proposal, allow_unicode=True,
                sort_keys=False), encoding="utf-8")
            rejected = invoke(*submit_args, "--dry-run")
            self.assertEqual(rejected.returncode, 2)
            self.assertFalse((root / "data/plans/pacing/applied--2026-10-15.yaml").exists())
            self.assertFalse((root / "data/routes/routes_manifest.yaml").exists())
            proposal_path.write_text(yaml.safe_dump(proposal, allow_unicode=True,
                sort_keys=False), encoding="utf-8")
            dry_submit = invoke(*submit_args, "--dry-run")
            self.assertEqual(dry_submit.returncode, 0, dry_submit.stderr.decode("utf-8"))
            self.assertIn("生效日上限：2028-12-23（取自设置 exam_date）",
                          dry_submit.stdout.decode("utf-8"))
            # Proposals written like the spec / prompt example carry an unquoted YAML date.
            proposal_path.write_text(yaml.safe_dump(
                dict(proposal, effective_from=date(2026, 10, 16)), allow_unicode=True,
                sort_keys=False), encoding="utf-8")
            self.assertIn("effective_from: 2026-10-16" + chr(10),
                          proposal_path.read_text(encoding="utf-8"))
            unquoted = invoke(*submit_args, "--dry-run")
            self.assertEqual(unquoted.returncode, 0, unquoted.stderr.decode("utf-8"))
            proposal_path.write_text(yaml.safe_dump(proposal, allow_unicode=True,
                sort_keys=False), encoding="utf-8")
            self.assertFalse((root / "data/plans/pacing/applied--2026-10-15.yaml").exists())
            self.assertFalse((root / "data/routes/routes_manifest.yaml").exists())
            from contextlib import redirect_stderr, redirect_stdout
            from io import StringIO
            from unittest.mock import patch

            from ky.pacing.submit import pacing_submit_main

            registered_workspace = load_workspace(root / WORKSPACE_FILENAME)
            rejected_output = StringIO()
            with patch("ky.pacing.submit.load_workspace", return_value=registered_workspace), \
                    patch("ky.pacing.submit.apply_pacing",
                          side_effect=ContractError("candidate rejected", "route")), \
                    redirect_stdout(rejected_output), redirect_stderr(rejected_output):
                rejected_candidate = pacing_submit_main([
                    "--from-staging", str(proposal_path), "--today", "2026-10-16",
                ])
            self.assertEqual(rejected_candidate, 2)
            self.assertIn("contract violation: route: candidate rejected",
                          rejected_output.getvalue())
            self.assertFalse((root / "data/plans/pacing/applied--2026-10-15.yaml").exists())
            self.assertFalse((root / "data/routes/routes_manifest.yaml").exists())
            successful_submit = invoke(*submit_args)
            self.assertEqual(successful_submit.returncode, 0,
                             successful_submit.stderr.decode("utf-8"))
            successful_text = successful_submit.stdout.decode("utf-8")
            self.assertIn("review_minutes.math1: - -> 20", successful_text)
            self.assertLess(successful_text.index("review_minutes."),
                            successful_text.index("submitted:"))
            (root / "data/plans/pacing/applied--2026-10-15.yaml").unlink()
            for route_file in (root / "data/routes").glob("*"):
                if route_file.is_file():
                    route_file.unlink()
            from ky.storage.day_plan_store import StorageError

            combined = StringIO()
            with patch("ky.pacing.submit.load_workspace", return_value=registered_workspace), \
                    patch("ky.pacing.submit._publish_intent",
                          side_effect=StorageError("intent injection", "intent")), \
                    redirect_stdout(combined), redirect_stderr(combined):
                intent_failure = pacing_submit_main([
                    "--from-staging", str(proposal_path), "--today", "2026-10-16",
                ])
            self.assertEqual(intent_failure, 2)
            failure_text = combined.getvalue()
            self.assertLess(failure_text.index("review_minutes."),
                            failure_text.index("contract violation:"))
            self.assertNotIn("提交意图已保存", failure_text)
            intent_path = root / "data/plans/pacing/applied--2026-10-15.yaml"
            self.assertFalse(intent_path.exists())

            combined = StringIO()
            with patch("ky.pacing.submit.load_workspace", return_value=registered_workspace), \
                    patch("ky.pacing.submit.RoutePlanStore.write_route_plan",
                          side_effect=StorageError("route injection", "state.routes")), \
                    redirect_stdout(combined), redirect_stderr(combined):
                route_failure = pacing_submit_main([
                    "--from-staging", str(proposal_path), "--today", "2026-10-16",
                ])
            self.assertEqual(route_failure, 2)
            self.assertIn("contract violation: state.routes: route injection", combined.getvalue())
            self.assertIn("提交意图已保存：重跑同一命令完成提交", combined.getvalue())
            self.assertTrue(intent_path.is_file())
            self.assertFalse((root / "data/routes/routes_manifest.yaml").exists())

            status = invoke("pacing", "status", "--today", "2026-10-16",
                            "--workspace", str(root / WORKSPACE_FILENAME),
                            "--config", str(external_config))
            self.assertEqual(status.returncode, 0, status.stderr.decode("utf-8"))
            self.assertIn("base: 180 (pacing_initial)", status.stdout.decode("utf-8"))
            self.assertIn("unreported_cycles: none", status.stdout.decode("utf-8"))

            registry_doc = yaml.safe_load((root / WORKSPACE_FILENAME).read_text(
                encoding="utf-8"))
            del registry_doc["settings"]["pacing"]
            (root / WORKSPACE_FILENAME).write_text(
                yaml.safe_dump(registry_doc, sort_keys=False), encoding="utf-8")
            changed_settings = settings_doc(exam_date="2027-12-23")
            pacing_file.write_text(yaml.safe_dump(changed_settings, sort_keys=False),
                                   encoding="utf-8")
            unregistered_workspace = load_workspace(root / WORKSPACE_FILENAME)
            self.assertIsNone(unregistered_workspace.pacing)
            intent_bytes = intent_path.read_bytes()
            routes_before = {item.relative_to(root / "data/routes").as_posix():
                             item.read_bytes() for item in (root / "data/routes").rglob("*")
                             if item.is_file()}
            combined = StringIO()
            with patch("ky.pacing.submit.load_workspace", return_value=unregistered_workspace), \
                    redirect_stdout(combined), redirect_stderr(combined):
                recovery_preview = pacing_submit_main([
                    "--from-staging", str(proposal_path), "--today", "2026-10-16",
                    "--dry-run",
                ])
            self.assertEqual(recovery_preview, 0, combined.getvalue())
            self.assertIn("dry-run：将恢复提交（不写任何文件）", combined.getvalue())
            self.assertIn("route_id: pacing", combined.getvalue())
            self.assertEqual(intent_path.read_bytes(), intent_bytes)
            self.assertEqual(routes_before, {
                item.relative_to(root / "data/routes").as_posix(): item.read_bytes()
                for item in (root / "data/routes").rglob("*") if item.is_file()
            })
            with patch("ky.pacing.submit.load_workspace", return_value=unregistered_workspace):
                recovered = pacing_submit_main([
                    "--from-staging", str(proposal_path), "--today", "2026-10-16",
                ])
            self.assertEqual(recovered, 0)
            self.assertTrue((root / "data/routes/routes_manifest.yaml").is_file())
            restored_route = RoutePlanStore(root / "data/routes").current()
            self.assertEqual(restored_route.target_exam_date, date(2028, 12, 23))
            registry_doc["settings"]["pacing"] = "settings/pacing.yaml"
            (root / WORKSPACE_FILENAME).write_text(
                yaml.safe_dump(registry_doc, sort_keys=False), encoding="utf-8")
            plan_keys = [key for key in first_mapping["sources"]
                         if key.startswith("data/plans/")]
            self.assertTrue(any("completion--2026-10-01" in key for key in plan_keys))
            self.assertIn("data/queue/manifest.yaml", first_mapping["sources"])
            for relative in queue_sources:
                self.assertIn(f"data/queue/{relative}", first_mapping["sources"])
            changed = settings_doc()
            changed["max_step_minutes"] = 31
            pacing_file.write_text(yaml.safe_dump(changed, sort_keys=False), encoding="utf-8")
            second = invoke(*args)
            self.assertEqual(second.returncode, 0, second.stderr.decode("utf-8"))
            self.assertIn("报告生成后记录有变化", second.stdout.decode("utf-8"))
            self.assertEqual(target.read_bytes(), original)
            (root / "data/availability.yaml").write_text(
                "schema_version: 1\ndays:\n  2026-10-01: 15\n", encoding="utf-8")
            changed_source_run = invoke(*args, "--config", str(external_config))
            self.assertEqual(changed_source_run.returncode, 0,
                             changed_source_run.stderr.decode("utf-8"))
            self.assertIn("报告生成后记录有变化",
                          changed_source_run.stdout.decode("utf-8"))
            next_report = invoke("pacing", "report", "--cycle-end", "2026-10-31",
                                 "--today", "2026-11-01")
            self.assertEqual(next_report.returncode, 0, next_report.stderr.decode("utf-8"))
            next_mapping = yaml.safe_load(next_report.stdout.decode("utf-8"))
            self.assertEqual(next_mapping["previous"]["report_hash"],
                             yaml.safe_load(original)["report_hash"])
            self.assertIn("data/plans/pacing/report--2026-10-15.yaml",
                          next_mapping["sources"])
            no_config_doc = yaml.safe_load((root / WORKSPACE_FILENAME).read_text(
                encoding="utf-8"))
            del no_config_doc["settings"]["exam_config"]
            (root / WORKSPACE_FILENAME).write_text(
                yaml.safe_dump(no_config_doc, sort_keys=False), encoding="utf-8")
            missing_config = invoke("pacing", "report", "--cycle-end", "2026-11-30",
                                    "--today", "2026-12-01")
            self.assertEqual(missing_config.returncode, 2)
            self.assertIn("--config", missing_config.stderr.decode("utf-8"))
            self.assertFalse((root / "data/plans/pacing/report--2026-11-30.yaml").exists())
            no_config_doc["settings"]["exam_config"] = "config.yaml"
            (root / WORKSPACE_FILENAME).write_text(
                yaml.safe_dump(no_config_doc, sort_keys=False), encoding="utf-8")
            (root / "data/availability.yaml").unlink()
            missing_availability = invoke("pacing", "report", "--cycle-end", "2026-11-30",
                "--today", "2026-12-01", "--config", str(external_config))
            self.assertEqual(missing_availability.returncode, 2)
            self.assertFalse((root / "data/plans/pacing/report--2026-11-30.yaml").exists())
            invalid_cycle = invoke("pacing", "report", "--cycle-end", "2026-10-15",
                                   "--today", "2026-10-15")
            self.assertEqual(invalid_cycle.returncode, 2)
            self.assertEqual(invoke("pacing").returncode, 3)


if __name__ == "__main__":
    unittest.main()
