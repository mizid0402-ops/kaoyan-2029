from __future__ import annotations

import io
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import plotly.offline
import yaml

from ky.availability import Availability
from ky.charts.data import ability_chart_data, progress_chart_data, week_chart_data
from ky.charts.render import render_ability, render_progress
from ky.models import ContractError, load_config
from ky.knowledge import KnowledgePoint
from ky.mastery import mastery_gap, subject_mastery
from ky.models import ReviewItem, ReviewSchedule
from ky.pacing.port import PacingSettings
from ky.schedule.budget import resolve_day_budget
from ky.schedule.completion import CompletionEvent
from ky.schedule.longitudinal import DayPlan
from ky.schedule.planning import Phase, RoutePlan
from ky.timetable import (
    LoadedSchool, SchoolProfile, Semester, Timetable,
    TimetableCalendar, TimetableRules, build_calendar,
)
from ky.timetable._models import Course, Follow, NoClass, Period
from ky.__main__ import main, timetable_main
from ky.workspace import WORKSPACE_FILENAME, load_workspace
from ky.timetable_io.preview import base_resolver


ROOT = Path(__file__).resolve().parents[2]
CONFIG_SOURCE = ROOT / "tests" / "fixtures" / "config" / "config-minimal.yaml"


def _calendar() -> TimetableCalendar:
    periods = {
        index: Period(start, end, unconfirmed=(index == 4))
        for index, (start, end) in enumerate((
            (480, 525), (535, 580), (610, 655), (665, 710),
            (810, 855), (865, 910), (940, 985), (995, 1040),
        ), 1)
    }
    school = SchoolProfile(
        "demo", "Synthetic", (), "test", date(2026, 1, 1), periods,
        ((1, 2), (3, 4), (5, 6), (7, 8)),
    )
    semester = Semester(
        "term-a", "demo", date(2026, 9, 7), 2,
        (Course("跨午休课程", 1, 3, 8, frozenset({1, 2})),),
        (NoClass(date(2026, 9, 8), date(2026, 9, 8)),
         Follow(date(2026, 9, 9), date(2026, 9, 7))),
    )
    timetable = Timetable(TimetableRules(450, 1320, 0, 10, 15, None), (semester,))
    return build_calendar(timetable, {
        "demo": LoadedSchool(school, Path("school.yaml"), "0" * 64),
    })


class ChartsPortTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config_path = self.root / "config.yaml"
        shutil.copyfile(CONFIG_SOURCE, self.config_path)
        self.config = load_config(self.config_path)
        self.workspace_index = 0

    def _workspace(self, *, timetable: bool = True, charts: bool = True,
                   routes: bool = True, pacing: bool = False) -> Path:
        self.workspace_index += 1
        workspace_root = self.root / f"workspace-{self.workspace_index}"
        workspace_root.mkdir()
        shutil.copyfile(CONFIG_SOURCE, workspace_root / "config.yaml")
        subjects = {
            subject.subject_id: {"name": subject.display_name}
            for subject in self.config.subjects
        }
        reference = {
            "knowledge_trees": {}, "exam_indexes": {}, "paper_shapes": {},
            "topic_weights": "data/weights.json", "vocabulary_db": "data/vocab.sqlite",
            "ledger": "data/ledger.yaml",
        }
        state = {"review_queue": "data/queue", "plans": "data/plans"}
        if timetable:
            reference["timetable_schools"] = {"demo": "data/school.yaml"}
            state["timetable"] = "data/timetable.yaml"
        if routes:
            state["routes"] = "data/routes"
        products = {"charts": "outputs/charts"} if charts else {}
        raw = {
            "schema_version": 2, "subjects": subjects,
            "reference": reference, "supplementary": {}, "materials": {"raw_root": "data/raw"},
            "products": products,
            "settings": {"exam_config": "config.yaml",
                         **({"pacing": "pacing.yaml"} if pacing else {})},
            "state": state, "staging": "staging", "projection": "data/projection.sqlite",
        }
        workspace_path = workspace_root / WORKSPACE_FILENAME
        workspace_path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
        if pacing:
            (workspace_root / "pacing.yaml").write_text(yaml.safe_dump({
                "schema_version": 1, "start": "2026-09-01", "exam_date": "2028-12-23",
                "base_daily_minutes": {"min": 180, "max": 240, "initial": 222},
                "max_step_minutes": 30, "cadence": [{"kind": "half_month"}],
            }), encoding="utf-8")
        if timetable:
            data_root = workspace_root / "data"
            data_root.mkdir(exist_ok=True)
            school = {
                "schema_version": 1, "school_id": "demo", "name": "Synthetic",
                "system": "sample_system",
                "source": {"kind": "user_statement", "recorded_on": "2026-09-01"},
                "periods": {
                    index: {"start": f"{start // 60:02d}:{start % 60:02d}",
                            "end": f"{end // 60:02d}:{end % 60:02d}",
                            **({"unconfirmed": True} if index == 4 else {})}
                    for index, (start, end) in enumerate((
                        (480, 525), (535, 580), (610, 655), (665, 710),
                        (810, 855), (865, 910), (940, 985), (995, 1040),
                    ), 1)
                }, "blocks": [[1, 2], [3, 4], [5, 6], [7, 8]],
            }
            timetable = {
                "schema_version": 1,
                "rules": {"study_window": {"start": "07:30", "end": "22:00"},
                          "buffer_minutes": 0, "min_gap_minutes": 10,
                          "block_deduction_minutes": 15},
                "semesters": [{
                    "label": "term-a", "school": "demo", "week1_monday": "2026-09-07",
                    "weeks": 2,
                    "courses": [{"name": "跨午休课程", "weekday": 1,
                                 "periods": "3-8", "weeks": "1-2"}],
                    "exceptions": [
                        {"kind": "no_class", "date": "2026-09-08"},
                        {"kind": "follow", "date": "2026-09-09", "follow": "2026-09-07"},
                    ],
                }],
            }
            (data_root / "school.yaml").write_text(
                yaml.safe_dump(school, allow_unicode=True), encoding="utf-8",
            )
            (data_root / "timetable.yaml").write_text(
                yaml.safe_dump(timetable, allow_unicode=True), encoding="utf-8",
            )
        return workspace_path

    def test_data_port_none_parameters_fail_with_contract_paths(self) -> None:
        with self.assertRaises(ContractError) as caught:
            week_chart_data("term-a", 1, None)
        self.assertEqual(caught.exception.path, "week.days")
        self.assertIn("week.days", str(caught.exception))

        with self.assertRaises(ContractError) as caught:
            progress_chart_data(
                start=None, end=date(2026, 9, 20), today=date(2026, 9, 21),
                config=self.config, subject_names={}, reference_minutes={}, plans=(),
                completions=(), queue_items=(), knowledge_trees={}, tree_grammars={},
                route=None,
            )
        self.assertEqual(caught.exception.path, "progress.start")
        self.assertIn("progress.start", str(caught.exception))

        with self.assertRaises(ContractError) as caught:
            ability_chart_data(
                today=None, subjects=(), subject_names={}, masteries={},
                gap={"subjects": []}, knowledge_trees={}, tree_grammars={},
                weighted_subjects=(),
            )
        self.assertEqual(caught.exception.path, "ability.today")
        self.assertIn("ability.today", str(caught.exception))

    @staticmethod
    def _point(point_id: str, title: str, scope: str = "item") -> KnowledgePoint:
        return KnowledgePoint(point_id, title, "active", "manual", (), None, (), (), None,
                              1, scope)

    @staticmethod
    def _review(
        subject: str, point_id: str, state: str = "queued", *,
        interval: int = 1, lapses: int = 0,
    ) -> ReviewItem:
        return ReviewItem(
            f"review-{point_id}", 1, subject, point_id, point_id, "item", state,
            20, date(2026, 1, 1), date(2026, 1, 2), None,
            ReviewSchedule("ladder", 0, interval, 2.5, 0, lapses), 0, None,
        )

    def test_week_mapping_covers_exceptions_unconfirmed_and_out_of_term(self) -> None:
        calendar = _calendar()
        expected_days = [date(2026, 9, 7) + timedelta(days=index) for index in range(6)]
        rows = [(day, calendar.day(day, 180), 180) for day in expected_days]
        outside = date(2026, 9, 21)
        rows.append((outside, calendar.day(outside, 180), 180))
        data = week_chart_data("term-a", 1, rows)
        self.assertEqual(len(data["days"]), 7)
        monday = data["days"][0]
        self.assertEqual(monday, {
            "date": "2026-09-07", "weekday": 1, "covered": True,
            "no_class": False, "followed": None,
            "classes": [{"name": "跨午休课程", "first_period": 3, "last_period": 8,
                         "start": "10:10", "end": "17:20", "unconfirmed": True}],
            "free_segments": [["07:30", "10:10"], ["10:55", "11:05"],
                              ["11:50", "13:30"], ["14:15", "14:25"],
                              ["15:10", "15:40"], ["16:25", "16:35"],
                              ["17:20", "22:00"]],
            "free_minutes": 600, "blocks": 3, "base_minutes": 180, "minutes": 135,
        })
        self.assertTrue(data["days"][1]["no_class"])
        self.assertEqual(data["days"][2]["followed"], "2026-09-07")
        self.assertFalse(data["days"][-1]["covered"])
        self.assertEqual(data["days"][-1]["base_minutes"], None)
        self.assertEqual(data["time_range"], ["07:00", "22:00"])
        pacing_workspace = load_workspace(self._workspace(pacing=True))
        base = base_resolver(pacing_workspace, self.config)(date(2026, 9, 7))
        self.assertEqual(base, 222)
        self.assertEqual(week_chart_data("term-a", 1, [
            (expected_days[0], calendar.day(expected_days[0], base), base),
        ] * 7)["days"][0]["base_minutes"], 222)

    def test_progress_data_daily_weekly_coverage_and_route_contract(self) -> None:
        start, end, today = date(2026, 6, 3), date(2026, 6, 16), date(2026, 6, 17)
        subjects = tuple(item.subject_id for item in self.config.active_subjects())
        manual_day = start
        timetable_day = start + timedelta(days=1)
        availability = Availability({manual_day: 77})

        class Derived:
            def minutes_for(self, day, base_minutes):
                return 91 if day == timetable_day else None

        expected_budgets = {
            day: resolve_day_budget(day, self.config, availability, None, Derived()).total_minutes
            for day in (manual_day, timetable_day)
        }
        reference = {day: expected_budgets.get(day, self.config.default_daily_minutes)
                     for day in (start + timedelta(days=i) for i in range((end - start).days + 1))}
        plan_days = [start + timedelta(days=index) for index in (0, 6, 13)]
        plans = [DayPlan(day, 120, subject_minutes={
            subjects[0]: 30 if index == 0 else 0,
            subjects[1]: 15 if index == 1 else 0,
        }) for index, day in enumerate(plan_days)]
        events = [CompletionEvent(start, study_minutes=50),
                  CompletionEvent(start + timedelta(days=1), study_minutes=None)]
        named = subjects[0]
        chapter = f"{named}.area.ch01.chapter"
        content = f"{named}.area.ch01.content"
        points = (
            self._point(f"{named}.area.subject", "科目根", "subject"),
            self._point(chapter, "第一章", "chapter"),
            self._point(content, "内容", "section"),
            self._point(f"{content}.a", "叶子甲"),
            self._point(f"{content}.b", "叶子乙"),
            self._point(f"{named}.area.ch01.requirements", "要求", "section"),
        )
        tracker_subject = subjects[1]
        tracker = f"{tracker_subject}.goal.subject"
        numbered = (
            self._point(f"{tracker_subject}.area.subject", "第二科根", "subject"),
            self._point(f"{tracker_subject}.area.chapter-01", "第二科第一章", "chapter"),
            self._point(f"{tracker_subject}.area.chapter-01.section-01", "节", "section"),
            self._point(f"{tracker_subject}.area.chapter-02", "第二章", "chapter"),
            self._point(f"{tracker_subject}.area.chapter-02.section-01", "第二节", "section"),
            self._point(tracker, "跟踪目标", "subject"),
        )
        queue = [self._review(named, chapter, "paused"),
                 self._review(named, f"{content}.a", "done"),
                 self._review(named, f"{named}.unknown", "suspended"),
                 self._review(tracker_subject, tracker, "queued")]
        route = RoutePlan(
            "route-test", 2, start, date(2026, 7, 1), "policy", "0" * 64,
            (Phase(0, start, date(2026, 7, 1), "阶段一", {subjects[0]: 10}, 150),),
        )
        data = progress_chart_data(
            start=start, end=end, today=today, config=self.config,
            reference_minutes=reference, plans=plans, completions=events,
            queue_items=queue,
            subject_names={subject: f"科目名{index}"
                           for index, subject in enumerate(subjects)},
            knowledge_trees={subjects[0]: points, subjects[1]: numbered,
                             **{subject: None for subject in subjects[2:]}},
            tree_grammars={subjects[0]: "named_chapters",
                           subjects[1]: "numbered_chapters"}, route=route,
        )
        self.assertIsNone(data["daily"][1]["actual"])
        self.assertIsNone(data["daily"][2]["actual"])
        self.assertEqual(data["daily_totals"], {
            "recorded_days": 1, "actual_sum": 50,
            "reference_sum_on_recorded_days": expected_budgets[manual_day],
        })
        self.assertEqual(data["daily"][0]["reference"], expected_budgets[manual_day])
        self.assertEqual(data["daily"][1]["reference"], expected_budgets[timetable_day])
        self.assertEqual(data["daily"][2]["reference"], self.config.default_daily_minutes)
        self.assertEqual(len(data["weekly_plan"]), 3)
        self.assertEqual(tuple(data["weekly_plan"][0]["minutes"]), subjects)
        self.assertEqual(data["weekly_plan"][1]["minutes"][subjects[-1]], 0)
        # Only active subjects are charted; the fixture's politics is inactive.
        inactive = {item.subject_id for item in self.config.subjects} - set(subjects)
        self.assertTrue(inactive)
        self.assertEqual([row["subject_id"] for row in data["coverage"]], list(subjects))
        self.assertEqual(data["coverage"][0]["covered"], 3)
        self.assertEqual(data["coverage"][0]["total"], 3)
        self.assertEqual(data["coverage"][0]["unknown_refs"], [f"{named}.unknown"])
        self.assertEqual(data["coverage"][0]["tracker_refs"], [])
        root = data["coverage"][0]["tree"]["children"][0]
        chapter_node = root["children"][0]
        self.assertEqual(root["title"], "科目根")
        self.assertEqual([node["title"] for node in chapter_node["children"]],
                         ["内容", "要求"])
        self.assertEqual([node["title"] for node in chapter_node["children"][0]["children"]],
                         ["叶子甲", "叶子乙"])
        self.assertEqual(chapter_node["lit"], 3)
        self.assertEqual(chapter_node["leaves"], 3)
        self.assertEqual(data["coverage"][1]["total"], 2)
        self.assertEqual(data["coverage"][1]["tracker_refs"], [tracker])
        self.assertEqual(data["coverage"][1]["unknown_refs"], [])
        self.assertEqual(data["coverage"][1]["covered"], 0)
        self.assertIsNone(data["coverage"][-1]["covered"])
        self.assertIsNone(data["coverage"][-1]["total"])
        self.assertIsNone(data["coverage"][-1]["tree"])
        self.assertEqual(data["route"]["days_to_exam"], 14)
        self.assertEqual(data["route"]["phases"][0]["label"], "阶段一")
        no_route = progress_chart_data(
            start=start, end=start, today=today, config=self.config,
            reference_minutes={start: 0}, plans=(), completions=(), queue_items=(),
            subject_names={subject: subject for subject in subjects},
            knowledge_trees={subject: None for subject in subjects},
            tree_grammars={}, route=None,
        )
        self.assertIsNone(no_route["route"])

    def test_progress_render_daily_tiles_order_and_weekly_empty_states(self) -> None:
        subjects = tuple(item.subject_id for item in self.config.active_subjects())
        names = {subject: f"科目名{index}" for index, subject in enumerate(subjects)}
        start, end, today = date(2026, 6, 3), date(2026, 6, 5), date(2026, 6, 6)
        common = {
            "start": start, "end": end, "today": today, "config": self.config,
            "subject_names": names,
            "reference_minutes": {start: 0, end - timedelta(days=1): 77, end: 22},
            "completions": [CompletionEvent(end, study_minutes=11),
                            CompletionEvent(end - timedelta(days=1), study_minutes=50)],
            "queue_items": (), "knowledge_trees": {subject: None for subject in subjects},
            "tree_grammars": {}, "route": None,
        }
        no_plans = progress_chart_data(**common, plans=())
        html = render_progress(no_plans, subjects, names)
        self.assertIn("2 / 3", html)
        self.assertIn("61 分钟", html)
        self.assertIn("99 分钟", html)
        self.assertIn("62%", html)
        self.assertLess(html.index("6/5"), html.index("6/4"))
        self.assertIn("区间内没有日计划", html)
        for subject in subjects:
            self.assertNotIn(subject, html)
        for name in names.values():
            self.assertIn(name, html)

        zeros = progress_chart_data(
            **{**common, "end": start, "completions": (),
               "reference_minutes": {start: 0}},
            plans=(DayPlan(start, 0, subject_minutes={}),),
        )
        zero_html = render_progress(zeros, subjects, names)
        self.assertIn("0 / 1", zero_html)
        self.assertIn("0 分钟", zero_html)
        self.assertIn("达成率</div><div class=\"tile-value\">—", zero_html)
        self.assertIn("未记录", zero_html)
        self.assertNotIn("区间内没有日计划", zero_html)
        for name in names.values():
            self.assertIn(name, zero_html)
        for subject in subjects:
            self.assertNotIn(subject, zero_html)

    def test_ability_mapping_and_render_key_text(self) -> None:
        subjects = tuple(item.subject_id for item in self.config.active_subjects())
        weighted_subject = subjects[0]
        names = {subject: f"科目名{index}" for index, subject in enumerate(subjects)}
        root_id = f"{weighted_subject}.area.subject"
        chapter_id = f"{weighted_subject}.area.chapter-01"
        section_id = f"{chapter_id}.section-01"
        leaf_id = f"{section_id}.item-01"
        tree = (
            self._point(root_id, "科目根", "subject"),
            self._point(chapter_id, "第一章", "chapter"),
            self._point(section_id, "第一节", "section"),
            self._point(leaf_id, "薄弱叶子"),
        )
        mastery = subject_mastery(
            weighted_subject, tree, "numbered_chapters",
            (self._review(weighted_subject, leaf_id, interval=7, lapses=2),),
            {chapter_id: 1}, (),
        )
        masteries = {weighted_subject: mastery}
        trees = {weighted_subject: tree}
        grammars = {weighted_subject: "numbered_chapters"}
        for subject in subjects[1:]:
            masteries[subject] = None
            trees[subject] = None
        today = date(2026, 6, 6)
        gap = mastery_gap(
            [{"subject_id": subject,
              "covered": None if masteries[subject] is None else masteries[subject]["covered"],
              "ability": None if masteries[subject] is None else masteries[subject]["ability"]}
             for subject in subjects], today,
            RoutePlan(
                "route-test", 1, date(2026, 6, 1), date(2026, 6, 11), "policy", "c" * 64,
                (Phase(0, date(2026, 6, 1), date(2026, 6, 6), "base", {"alpha": 1},
                       targets={"covered": 50, "consolidated": 50}),
                 Phase(1, date(2026, 6, 6), date(2026, 6, 11), "next", {"alpha": 1},
                       targets={"covered": 100, "consolidated": 100})),
            ),
        )
        data = ability_chart_data(
            today=today, subjects=subjects, subject_names=names, masteries=masteries,
            gap=gap, knowledge_trees=trees, tree_grammars=grammars,
            weighted_subjects=(weighted_subject,),
        )
        row = data["subjects"][0]
        leaf = (row["tree"]["children"][0]["children"][0]["children"][0]
                ["children"][0])
        self.assertEqual(leaf["level"], "progressing")
        self.assertTrue(leaf["weak"])
        self.assertEqual(row["covered"], "1.0000")
        self.assertEqual(row["gap_covered"], "+0.5000")
        self.assertEqual(row["gap_consolidated"], "-0.5000")
        self.assertEqual(data["weak_items"][0]["chapter"], "第一章")
        html = render_ability(data)
        self.assertIn("能力 0.0%", html)
        self.assertIn("应到 50.0%", html)
        self.assertIn("覆盖 当前 100.0% / 应到 50.0%", html)
        self.assertIn("巩固 当前 0.0% / 应到 50.0%", html)
        self.assertIn("落后", html)
        self.assertIn("⚠ 遗忘 ≥2", html)
        self.assertIn("遗忘次数", html)
        self.assertIn(">2</td>", html)

        no_weak = subject_mastery(
            weighted_subject, tree, "numbered_chapters", (), None, (),
        )
        no_weak_data = ability_chart_data(
            today=today, subjects=(weighted_subject,), subject_names=names,
            masteries={weighted_subject: no_weak}, gap=mastery_gap(
                [{"subject_id": weighted_subject, "covered": no_weak["covered"],
                  "ability": no_weak["ability"]}], today, None,
            ), knowledge_trees={weighted_subject: tree}, tree_grammars=grammars,
            weighted_subjects=(),
        )
        self.assertIn("暂无薄弱点", render_ability(no_weak_data))
        self.assertIn("目标差距需要路线", render_ability(no_weak_data))
        no_targets_route = RoutePlan(
            "route-no-targets", 1, date(2026, 6, 1), date(2026, 6, 11),
            "policy", "d" * 64,
            (Phase(0, date(2026, 6, 1), date(2026, 6, 11), "only", {"alpha": 1}),),
        )
        no_targets_gap = mastery_gap(
            [{"subject_id": weighted_subject, "covered": no_weak["covered"],
              "ability": no_weak["ability"]}], today, no_targets_route,
        )
        no_targets_data = ability_chart_data(
            today=today, subjects=(weighted_subject,), subject_names=names,
            masteries={weighted_subject: no_weak}, gap=no_targets_gap,
            knowledge_trees={weighted_subject: tree}, tree_grammars=grammars,
            weighted_subjects=(),
        )
        self.assertIn("路线还没写阶段目标", render_ability(no_targets_data))

    def test_ability_cli_is_deterministic_and_uses_one_timeline_source(self) -> None:
        workspace = self._workspace(timetable=False)
        args = ["chart", "ability", "--workspace", str(workspace),
                "--today", "2026-06-06"]
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(args), 0)
        output = workspace.parent / "outputs" / "charts"
        html_path = output / "ability--2026-06-06.html"
        first = html_path.read_bytes()
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(args), 0)
        content = html_path.read_bytes()
        self.assertEqual(first, content)
        self.assertNotIn(b"cdn.plot.ly", content)
        self.assertNotIn(b"http://cdn.plot.ly", content)

        pacing = PacingSettings(
            date(2026, 6, 5), date(2026, 6, 15), 120, 240, 180, 30, (),
        )
        route = RoutePlan(
            "route-test", 1, date(2026, 6, 1), date(2026, 6, 11), "policy",
            "0" * 64,
            (Phase(0, date(2026, 6, 1), date(2026, 6, 6), "base", {"alpha": 1},
                   targets={"covered": 50, "consolidated": 50}),
             Phase(1, date(2026, 6, 6), date(2026, 6, 11), "next", {"alpha": 1},
                   targets={"covered": 100, "consolidated": 100})),
        )
        captured = []
        with patch("ky.storage.route_store.RoutePlanStore.read_state_sources",
                   return_value=SimpleNamespace(route=route)), \
                patch("ky.charts.cli.settings_for_workspace", return_value=pacing) as settings, \
                patch("ky.charts.cli._write_page",
                      side_effect=lambda _directory, _filename, page, _open:
                      captured.append(page) or 0):
            self.assertEqual(main(args), 0)
            settings.assert_not_called()
        self.assertIn("应到 50.0%", captured[-1])
        self.assertNotIn("应到 10.0%", captured[-1])

        with patch("ky.storage.route_store.RoutePlanStore.read_state_sources",
                   return_value=SimpleNamespace(route=None)), \
                patch("ky.charts.cli._write_page",
                      side_effect=lambda _directory, _filename, page, _open:
                      captured.append(page) or 0):
            self.assertEqual(main(args), 0)
        self.assertIn("目标差距需要路线", captured[-1])

        registry = yaml.safe_load(workspace.read_text(encoding="utf-8"))
        subject = next(item.subject_id for item in self.config.active_subjects())
        registry["subjects"][subject]["features"] = ["weighted_mastery"]
        weights_path = workspace.parent / "data" / "weights.json"
        weights_path.parent.mkdir(parents=True, exist_ok=True)
        weights_path.write_text('{"topic_weight": {}}', encoding="utf-8")
        workspace.write_text(yaml.safe_dump(registry, allow_unicode=True), encoding="utf-8")
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main(args), 2)

        del registry["reference"]["topic_weights"]
        workspace.write_text(yaml.safe_dump(registry, allow_unicode=True), encoding="utf-8")
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main(args), 2)

    def test_cli_html_is_deterministic_offline_and_reports_contract_codes(self) -> None:
        workspace = self._workspace()
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main([
                "chart", "week", "--workspace", str(workspace), "--week", "1",
            ]), 0)
        product = workspace.parent / "outputs" / "charts"
        first_week = (product / "week--term-a--w01.html").read_bytes()
        with redirect_stdout(out):
            self.assertEqual(main([
                "chart", "week", "--workspace", str(workspace), "--week", "1",
            ]), 0)
        week_html = (product / "week--term-a--w01.html").read_bytes()
        self.assertEqual(first_week, week_html)
        self.assertNotIn(b"cdn.plot.ly", week_html)
        self.assertNotIn(b"http://cdn.plot.ly", week_html)
        self.assertNotIn(b"https://cdn.plot.ly", week_html)
        self.assertEqual((product / "plotly.min.js").read_bytes(),
                         plotly.offline.get_plotlyjs().encode("utf-8"))

        progress_args = [
            "progress", "--workspace", str(workspace), "--today", "2026-09-21",
            "--from", "2026-09-01", "--to", "2026-09-20",
        ]
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(["chart", *progress_args]), 0)
        first_progress = (product / "progress--2026-09-01--2026-09-20.html").read_bytes()
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(["chart", *progress_args]), 0)
        progress_html = (product / "progress--2026-09-01--2026-09-20.html").read_bytes()
        self.assertEqual(first_progress, progress_html)
        self.assertNotIn(b"cdn.plot.ly", progress_html)
        self.assertEqual((product / "plotly.min.js").read_bytes(),
                         plotly.offline.get_plotlyjs().encode("utf-8"))

        missing_product = self._workspace(charts=False)
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main(["chart",
                "week", "--workspace", str(missing_product), "--week", "1",
            ]), 2)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(["chart",
                "week", "--workspace", str(missing_product), "--week", "1",
                "--out", str(self.root / "alternate"),
            ]), 0)
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main(["chart",
                "progress", "--workspace", str(workspace), "--today", "2026-09-21",
                "--from", "2026-09-12", "--to", "2026-09-11",
            ]), 3)
            self.assertEqual(main(["chart",
                "week", "--workspace", str(workspace), "--week", "3",
            ]), 3)

        no_timetable = self._workspace(timetable=False)
        with redirect_stderr(io.StringIO()) as chart_err:
            self.assertEqual(main(["chart",
                "week", "--workspace", str(no_timetable), "--week", "1",
            ]), 3)
        with redirect_stderr(io.StringIO()) as timetable_err:
            self.assertEqual(timetable_main([
                "show", "--workspace", str(no_timetable), "--week", "1",
                "--config", str(self.config_path),
            ]), 3)
        self.assertEqual(chart_err.getvalue(), timetable_err.getvalue())

        invalid_event = workspace.parent / "data" / "plans" / "2026-09"
        invalid_event.mkdir(parents=True, exist_ok=True)
        (invalid_event / "completion--2026-09-10.yaml").write_text("invalid: [", encoding="utf-8")
        with redirect_stderr(io.StringIO()) as err:
            self.assertEqual(main(["chart",
                "progress", "--workspace", str(workspace), "--today", "2026-09-21",
                "--from", "2026-09-01", "--to", "2026-09-20",
            ]), 2)
        self.assertNotIn("Traceback", err.getvalue())


if __name__ == "__main__":
    unittest.main()
