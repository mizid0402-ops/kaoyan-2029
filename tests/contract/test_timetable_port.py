from __future__ import annotations

import copy
import io
import hashlib
import json
import subprocess
import tarfile
import tempfile
import unittest
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import yaml

from ky.models import ContractError
from ky.timetable import (
    DaySchedule,
    LoadedSchool,
    TimetableCalendar,
    build_calendar,
    load_school,
    load_referenced_schools,
    load_timetable,
    semester_from_mapping,
    semester_to_mapping,
    timetable_from_mapping,
    timetable_for_workspace,
    timetable_to_mapping,
    validate_semester_references,
)
from ky.workspace import WORKSPACE_FILENAME, load_workspace
from tests._baseline_harness import ProcessResult, compare_runs, fixed_source
from tests._resources import require_path

ROOT = Path(__file__).resolve().parents[2]
PERIOD_TIMES = {
    1: ("08:00", "08:45"),
    2: ("08:55", "09:40"),
    3: ("10:10", "10:55"),
    4: ("11:05", "11:50"),
    5: ("13:30", "14:15"),
    6: ("14:25", "15:10"),
    7: ("15:40", "16:25"),
    8: ("16:35", "17:20"),
    9: ("18:30", "19:15"),
    10: ("19:25", "20:10"),
}


def _school_document(school_id: str = "demo") -> dict:
    return {
        "schema_version": 1,
        "school_id": school_id,
        "name": "Example School",
        "aliases": ["Example"],
        "system": "sample_system",
        "source": {"kind": "user_statement", "recorded_on": "2026-09-30"},
        "periods": {
            number: {"start": start, "end": end}
            for number, (start, end) in PERIOD_TIMES.items()
        },
        "blocks": [[1, 2], [3, 4], [5, 6], [7, 8], [9, 10]],
    }


def _course(weekday: int, periods: str, weeks: str = "1", name: str = "Course") -> dict:
    return {"name": name, "weekday": weekday, "periods": periods, "weeks": weeks}


def _semester(
    *,
    label: str = "term-a",
    school: str = "demo",
    monday: str = "2026-09-07",
    weeks: int = 18,
    courses: list[dict] | None = None,
    exceptions: list[dict] | None = None,
) -> dict:
    result = {
        "label": label,
        "school": school,
        "week1_monday": monday,
        "weeks": weeks,
        "courses": [] if courses is None else courses,
    }
    if exceptions is not None:
        result["exceptions"] = exceptions
    return result


def _timetable_document(
    *,
    courses: list[dict] | None = None,
    rules: dict | None = None,
    semesters: list[dict] | None = None,
) -> dict:
    return {
        "schema_version": 1,
        "rules": {
            "study_window": {"start": "08:00", "end": "22:00"},
            "buffer_minutes": 15,
            "min_gap_minutes": 25,
            "block_deduction_minutes": 15,
            **({} if rules is None else rules),
        },
        "semesters": (
            [_semester(courses=courses)] if semesters is None else semesters
        ),
    }


def _write_yaml(path: Path, document: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


def _workspace(
    root: Path,
    school_documents: dict[str, dict],
    timetable_document: dict,
    *,
    timetable_registered: bool = True,
) -> tuple[object, dict[str, Path], Path]:
    root.mkdir(parents=True, exist_ok=True)
    school_paths: dict[str, Path] = {}
    for school_id, document in school_documents.items():
        path = root / "data" / "schools" / f"{school_id}.yaml"
        _write_yaml(path, document)
        school_paths[school_id] = path
    timetable_path = root / "data" / "timetable.yaml"
    _write_yaml(timetable_path, timetable_document)
    reference = {
        "knowledge_trees": {},
        "exam_indexes": {},
        "paper_shapes": {},
        "topic_weights": "data/topic_weights.json",
        "vocabulary_db": "data/vocabulary.sqlite",
        "ledger": "data/ledger.yaml",
        "timetable_schools": {
            school_id: path.relative_to(root).as_posix()
            for school_id, path in school_paths.items()
        },
    }
    state = {"review_queue": "data/queue", "plans": "data/plans"}
    if timetable_registered:
        state["timetable"] = timetable_path.relative_to(root).as_posix()
    registry = {
        "schema_version": 2,
        "subjects": {"alpha": {"name": "Alpha"}},
        "reference": reference,
        "materials": {"raw_root": "data/raw"},
        "products": {},
        "settings": {},
        "state": state,
        "staging": "staging",
        "projection": "data/projection.sqlite",
    }
    source = root / WORKSPACE_FILENAME
    _write_yaml(source, registry)
    return load_workspace(source), school_paths, timetable_path


# The day's base resolved by M8; M18 takes it as an argument (contracts/timetable.md §4 step 7).
BASE = 120


class TimetablePortTests(unittest.TestCase):
    def _school_error(self, document: dict, expected_path: str) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "school.yaml"
            _write_yaml(path, document)
            with self.assertRaises(ContractError) as caught:
                load_school(path)
            self.assertEqual(caught.exception.path, expected_path)

    def _timetable_error(self, document: dict, expected_path: str) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "timetable.yaml"
            _write_yaml(path, document)
            with self.assertRaises(ContractError) as caught:
                load_timetable(path)
            self.assertEqual(caught.exception.path, expected_path)

    def _calendar(
        self,
        document: dict,
        *,
        school_document: dict | None = None,
    ) -> TimetableCalendar:
        with tempfile.TemporaryDirectory() as temporary:
            workspace, _, _ = _workspace(
                Path(temporary) / "workspace",
                {"demo": _school_document() if school_document is None else school_document},
                document,
            )
            calendar = timetable_for_workspace(workspace)
            self.assertIsInstance(calendar, TimetableCalendar)
            return calendar

    def test_school_profile_acceptance_and_immutable_periods(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "school.yaml"
            _write_yaml(path, _school_document())
            school = load_school(path)
            self.assertEqual(school.school_id, "demo")
            self.assertEqual(school.aliases, ("Example",))
            self.assertEqual(school.periods[1].start, 8 * 60)
            self.assertFalse(school.periods[1].unconfirmed)
            with self.assertRaises(TypeError):
                school.periods[1] = school.periods[1]

    def test_school_schema_fields_and_numbered_rules_reject_invalid_values(self) -> None:
        cases = []

        def add(name: str, path: str, mutate) -> None:
            document = _school_document()
            mutate(document)
            cases.append((name, path, document))

        add("schema bool", "schema_version", lambda doc: doc.update(schema_version=True))
        add("schema version", "schema_version", lambda doc: doc.update(schema_version=2))
        add("school id", "school_id", lambda doc: doc.update(school_id="Bad-ID"))
        add("empty name", "name", lambda doc: doc.update(name=""))
        add("aliases container", "aliases", lambda doc: doc.update(aliases="Example"))
        add("empty alias", "aliases[0]", lambda doc: doc.update(aliases=[""]))
        add("duplicate alias", "aliases[1]", lambda doc: doc.update(aliases=["Same", "Same"]))
        add("system id", "system", lambda doc: doc.update(system="Bad-ID"))
        add(
            "source kind", "source.kind",
            lambda doc: doc["source"].update(kind="inferred"),
        )
        add(
            "source date", "source.recorded_on",
            lambda doc: doc["source"].update(recorded_on="2026-02-30"),
        )
        add(
            "source datetime", "source.recorded_on",
            lambda doc: doc["source"].update(recorded_on="2026-09-30T12:00:00"),
        )
        add("periods container", "periods", lambda doc: doc.update(periods=[]))
        add("periods empty", "periods", lambda doc: doc.update(periods={}))
        add(
            "period key type", "periods.1",
            lambda doc: doc.update(periods={"1": doc["periods"][1]}),
        )
        add("period gap", "periods.2", lambda doc: doc["periods"].pop(1))
        add("period object", "periods.1", lambda doc: doc["periods"].update({1: "08:00"}))
        add("period time type", "periods.1.start", lambda doc: doc["periods"][1].update(start=800))
        add("invalid time", "periods.1.start", lambda doc: doc["periods"][1].update(start="24:00"))
        add(
            "time order", "periods.1",
            lambda doc: doc["periods"][1].update(start="09:00", end="08:00"),
        )
        add("time overlap", "periods.2.start", lambda doc: doc["periods"][2].update(start="08:30"))
        add(
            "unconfirmed type", "periods.1.unconfirmed",
            lambda doc: doc["periods"][1].update(unconfirmed=1),
        )
        add("blocks container", "blocks", lambda doc: doc.update(blocks=[]))
        add("empty block", "blocks[0]", lambda doc: doc.update(blocks=[[], [1, 2]]))
        add("block integer", "blocks[0][0]", lambda doc: doc.update(blocks=[[True, 2], [3, 4]]))
        add(
            "block adjacency", "blocks[0]",
            lambda doc: doc.update(blocks=[[1, 3], [2], [4, 5, 6, 7, 8, 9, 10]]),
        )
        add(
            "block omission", "blocks",
            lambda doc: doc.update(blocks=[[1, 2], [3, 4], [5, 6], [7, 8], [9]]),
        )
        add(
            "block ordering", "blocks[1]",
            lambda doc: doc.update(blocks=[[1, 2], [4, 3], [5, 6, 7, 8, 9, 10]]),
        )
        add("root unknown", "extra", lambda doc: doc.update(extra=True))
        add("source unknown", "source.extra", lambda doc: doc["source"].update(extra=True))
        add("period unknown", "periods.1.extra", lambda doc: doc["periods"][1].update(extra=True))

        for name, expected_path, document in cases:
            with self.subTest(case=name):
                self._school_error(document, expected_path)

    def test_school_time_and_duplicate_key_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "school.yaml"
            path.write_text(
                "schema_version: 1\nschool_id: demo\nschool_id: other\n",
                encoding="utf-8",
            )
            with self.assertRaises(ContractError) as caught:
                load_school(path)
            self.assertEqual(caught.exception.path, "school_id")

            path.write_text(
                "schema_version: 1\nschool_id: demo\nname: Example\nsystem: demo\n"
                "source:\n  kind: official\n  kind: user_statement\n",
                encoding="utf-8",
            )
            with self.assertRaises(ContractError) as caught:
                load_school(path)
            self.assertEqual(caught.exception.path, "source.kind")

            path.write_text(
                "schema_version: 1\nschool_id: demo\nname: Example\nsystem: demo\n"
                "source: {kind: official, recorded_on: 2026-09-30}\n"
                "periods:\n  1: {start: 13:30, end: '14:00'}\nblocks: [[1]]\n",
                encoding="utf-8",
            )
            with self.assertRaises(ContractError) as caught:
                load_school(path)
            self.assertEqual(caught.exception.path, "periods.1.start")

    def test_timetable_rule_fields_and_numbered_rules_reject_invalid_values(self) -> None:
        cases = []

        def add(name: str, path: str, mutate) -> None:
            document = _timetable_document()
            mutate(document)
            cases.append((name, path, document))

        add("schema bool", "schema_version", lambda doc: doc.update(schema_version=True))
        add("schema value", "schema_version", lambda doc: doc.update(schema_version=2))
        add("unknown root", "extra", lambda doc: doc.update(extra=True))
        add("rules object", "rules", lambda doc: doc.update(rules=[]))
        add("unknown rule", "rules.extra", lambda doc: doc["rules"].update(extra=1))
        add("window object", "rules.study_window", lambda doc: doc["rules"].update(study_window=[]))
        add(
            "window time", "rules.study_window.start",
            lambda doc: doc["rules"]["study_window"].update(start=800),
        )
        add(
            "window invalid", "rules.study_window.end",
            lambda doc: doc["rules"]["study_window"].update(end="24:00"),
        )
        add(
            "window order", "rules.study_window",
            lambda doc: doc["rules"].update(
                study_window={"start": "22:00", "end": "08:00"}
            ),
        )
        add(
            "buffer bool", "rules.buffer_minutes",
            lambda doc: doc["rules"].update(buffer_minutes=True),
        )
        add(
            "buffer float", "rules.buffer_minutes",
            lambda doc: doc["rules"].update(buffer_minutes=1.0),
        )
        add(
            "buffer negative", "rules.buffer_minutes",
            lambda doc: doc["rules"].update(buffer_minutes=-1),
        )
        add(
            "gap bool", "rules.min_gap_minutes",
            lambda doc: doc["rules"].update(min_gap_minutes=False),
        )
        add(
            "deduction negative", "rules.block_deduction_minutes",
            lambda doc: doc["rules"].update(block_deduction_minutes=-1),
        )
        add(
            "cap bool", "rules.daily_cap_minutes",
            lambda doc: doc["rules"].update(daily_cap_minutes=True),
        )
        add(
            "cap negative", "rules.daily_cap_minutes",
            lambda doc: doc["rules"].update(daily_cap_minutes=-1),
        )
        add("semesters container", "semesters", lambda doc: doc.update(semesters={}))
        add("semester object", "semesters[0]", lambda doc: doc.update(semesters=["term-a"]))
        add(
            "semester label", "semesters[0].label",
            lambda doc: doc["semesters"][0].update(label=""),
        )
        add(
            "school identifier", "semesters[0].school",
            lambda doc: doc["semesters"][0].update(school="Bad-ID"),
        )
        add(
            "monday date", "semesters[0].week1_monday",
            lambda doc: doc["semesters"][0].update(week1_monday="2026-09-08"),
        )
        add("weeks bool", "semesters[0].weeks", lambda doc: doc["semesters"][0].update(weeks=True))
        add("weeks zero", "semesters[0].weeks", lambda doc: doc["semesters"][0].update(weeks=0))
        add(
            "courses container", "semesters[0].courses",
            lambda doc: doc["semesters"][0].update(courses={}),
        )
        add(
            "course object", "semesters[0].courses[0]",
            lambda doc: doc["semesters"][0].update(courses=["course"]),
        )
        add(
            "course name", "semesters[0].courses[0].name",
            lambda doc: doc["semesters"][0].update(
                courses=[_course(1, "1") | {"name": ""}]
            ),
        )
        add(
            "weekday bool", "semesters[0].courses[0].weekday",
            lambda doc: doc["semesters"][0].update(courses=[_course(True, "1")]),
        )
        add(
            "weekday range", "semesters[0].courses[0].weekday",
            lambda doc: doc["semesters"][0].update(courses=[_course(8, "1")]),
        )
        add(
            "period type", "semesters[0].courses[0].periods",
            lambda doc: doc["semesters"][0].update(courses=[_course(1, 1)]),
        )
        add(
            "period syntax", "semesters[0].courses[0].periods",
            lambda doc: doc["semesters"][0].update(courses=[_course(1, "1-2-3")]),
        )
        add(
            "period lower bound", "semesters[0].courses[0].periods",
            lambda doc: doc["semesters"][0].update(courses=[_course(1, "0-2")]),
        )
        add(
            "period order", "semesters[0].courses[0].periods",
            lambda doc: doc["semesters"][0].update(courses=[_course(1, "2-1")]),
        )
        add(
            "unknown semester", "semesters[0].extra",
            lambda doc: doc["semesters"][0].update(extra=1),
        )

        for name, expected_path, document in cases:
            with self.subTest(case=name):
                self._timetable_error(document, expected_path)

    def test_week_expression_examples_and_empty_parity_rejection(self) -> None:
        accepted = {
            "1-6周(单)": {1, 3, 5},
            "2-6(双)": {2, 4, 6},
            "1周,2-4周": {1, 2, 3, 4},
            "1-6(单),2-6(双)": {1, 2, 3, 4, 5, 6},
        }
        for expression, expected in accepted.items():
            with self.subTest(expression=expression):
                timetable = _timetable_document(
                    courses=[_course(1, "1", expression)]
                )
                with tempfile.TemporaryDirectory() as temporary:
                    path = Path(temporary) / "timetable.yaml"
                    _write_yaml(path, timetable)
                    parsed = load_timetable(path)
                self.assertEqual(parsed.semesters[0].courses[0].weeks, expected)

        rejected = (
            "1-3,3", "1-6(单),3", "0", "19", "1-19(单)", "1, 2", "2(单)",
        )
        for expression in rejected:
            with self.subTest(expression=expression):
                timetable = _timetable_document(
                    courses=[_course(1, "1", expression)]
                )
                self._timetable_error(
                    timetable, "semesters[0].courses[0].weeks"
                )

    def test_semester_intervals_exceptions_and_course_overlap(self) -> None:
        overlap = _timetable_document(
            semesters=[
                _semester(label="first", monday="2026-09-07", weeks=2),
                _semester(label="second", monday="2026-09-14", weeks=2),
            ]
        )
        self._timetable_error(overlap, "semesters[1].week1_monday")
        adjacent = _timetable_document(
            semesters=[
                _semester(label="first", monday="2026-09-07", weeks=2),
                _semester(label="second", monday="2026-09-21", weeks=2),
            ]
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "timetable.yaml"
            _write_yaml(path, adjacent)
            self.assertEqual(len(load_timetable(path).semesters), 2)

        duplicate_label = _timetable_document(
            semesters=[
                _semester(label="same", monday="2026-09-07", weeks=1),
                _semester(label="same", monday="2026-09-14", weeks=1),
            ]
        )
        self._timetable_error(duplicate_label, "semesters[1].label")

        exceptions = [
            {"from": "2026-09-08", "to": "2026-09-10", "kind": "no_class"},
            {"date": "2026-09-10", "kind": "no_class"},
        ]
        self._timetable_error(
            _timetable_document(semesters=[_semester(exceptions=exceptions)]),
            "semesters[0].exceptions[1]",
        )

        invalid_exceptions = (
            (
                [{"date": "2026-09-08", "kind": "no_class", "follow": "2026-09-09"}],
                "semesters[0].exceptions[0]",
            ),
            ([{"date": "2026-09-08", "kind": "follow"}], "semesters[0].exceptions[0]"),
            (
                [{"from": "2026-09-10", "to": "2026-09-08", "kind": "no_class"}],
                "semesters[0].exceptions[0].to",
            ),
            (
                [{"date": "2026-09-08", "kind": "follow", "follow": "2026-09-08"}],
                "semesters[0].exceptions[0].follow",
            ),
            (
                [
                    {"date": "2026-09-08", "kind": "follow", "follow": "2026-09-09"},
                    {"date": "2026-09-09", "kind": "no_class"},
                ],
                "semesters[0].exceptions[0].follow",
            ),
            (
                [
                    {"date": "2026-09-08", "kind": "follow", "follow": "2026-09-09"},
                    {"date": "2026-09-09", "kind": "follow", "follow": "2026-09-10"},
                ],
                "semesters[0].exceptions[0].follow",
            ),
            ([{"date": "2027-01-11", "kind": "no_class"}], "semesters[0].exceptions[0].date"),
            (
                [{"date": "2026-09-08", "kind": "follow", "follow": "2027-01-11"}],
                "semesters[0].exceptions[0].follow",
            ),
            (
                [{"from": "2026-09-08", "to": "2027-01-11", "kind": "no_class"}],
                "semesters[0].exceptions[0].to",
            ),
        )
        for values, expected_path in invalid_exceptions:
            with self.subTest(exceptions=values):
                self._timetable_error(
                    _timetable_document(semesters=[_semester(exceptions=values)]),
                    expected_path,
                )

        overlapping_courses = _timetable_document(
            courses=[_course(4, "3-6"), _course(4, "5-8")]
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "timetable.yaml"
            _write_yaml(path, overlapping_courses)
            parsed = load_timetable(path)
            self.assertEqual(len(parsed.semesters[0].courses), 2)

    def test_calculation_examples_from_round_217(self) -> None:
        week1_monday = date(2025, 9, 1)
        cases = (
            ("Thursday 3-8", {}, [_course(4, "3-8")], 4, 120, 75, 450, 3),
            ("Monday period 1", {}, [_course(1, "1")], 1, 120, 105, 780, 1),
            (
                "overlapping courses", {},
                [_course(4, "3-6"), _course(4, "5-8")],
                4, 120, 75, 450, 3,
            ),
            (
                "cap below deductions", {"daily_cap_minutes": 30},
                [_course(4, "3-8")], 4, 120, 0, 450, 3,
            ),
            ("empty courses", {"daily_cap_minutes": 120}, [], 1, 120, 120, 840, 0),
            ("cap above window", {"daily_cap_minutes": 1000}, [], 1, 120, 840, 840, 0),
            (
                "cap applies before free time", {"daily_cap_minutes": 1000},
                [_course(4, "3-8")], 4, 120, 450, 450, 3,
            ),
            ("base is default cap", {}, [_course(4, "3-8")], 4, 180, 135, 450, 3),
            (
                "minimum gap boundary",
                {"study_window": {"start": "08:00", "end": "10:00"}},
                [_course(1, "1")], 1, 120, 60, 60, 1,
            ),
            (
                "gap shorter than minimum",
                {
                    "study_window": {"start": "08:00", "end": "10:00"},
                    "min_gap_minutes": 61,
                },
                [_course(1, "1")], 1, 120, 0, 0, 1,
            ),
        )
        for name, rule_changes, courses, weekday, base, minutes, free, blocks in cases:
            with self.subTest(case=name), tempfile.TemporaryDirectory() as temporary:
                document = _timetable_document(
                    courses=courses,
                    rules=rule_changes,
                    semesters=[_semester(monday=week1_monday.isoformat(), courses=courses)],
                )
                workspace, _, _ = _workspace(
                    Path(temporary) / "workspace", {"demo": _school_document()}, document
                )
                calendar = timetable_for_workspace(workspace)
                self.assertIsInstance(calendar, TimetableCalendar)
                day = week1_monday + timedelta(days=weekday - 1)
                schedule = calendar.day(day, base)
                self.assertIsInstance(schedule, DaySchedule)
                self.assertEqual(schedule.minutes, minutes)
                self.assertEqual(schedule.free_minutes, free)
                self.assertEqual(schedule.blocks, blocks)
                if "daily_cap_minutes" not in rule_changes:
                    self.assertEqual(
                        calendar.minutes_for(day, base + 30),
                        min(minutes + 30, free),
                    )

    def test_fully_occupied_window_has_no_empty_free_segments(self) -> None:
        # sol round 224 R2: a zero minimum gap must not yield zero-length "free" segments.
        rules = {
            "study_window": {"start": "08:00", "end": "08:45"},
            "buffer_minutes": 0,
            "min_gap_minutes": 0,
            "block_deduction_minutes": 0,
        }
        calendar = self._calendar(
            _timetable_document(courses=[_course(1, "1")], rules=rules)
        )
        schedule = calendar.day(date(2026, 9, 7), BASE)
        self.assertEqual(schedule.free_segments, ())
        self.assertEqual(schedule.free_minutes, 0)
        self.assertEqual(schedule.minutes, 0)

    def test_minutes_between_validates_base_even_for_an_empty_range(self) -> None:
        calendar = self._calendar(_timetable_document())
        day = date(2026, 9, 7)
        with self.assertRaises(ContractError) as caught:
            calendar.minutes_between(day, day, "bad")
        self.assertEqual(caught.exception.path, "base_minutes")

    def test_blocks_count_periods_outside_the_study_window(self) -> None:
        rules = {
            "study_window": {"start": "08:00", "end": "09:00"},
            "daily_cap_minutes": 60,
        }
        calendar = self._calendar(
            _timetable_document(courses=[_course(1, "9-10")], rules=rules)
        )
        schedule = calendar.day(date(2026, 9, 7), BASE)
        self.assertEqual(schedule.free_minutes, 60)
        self.assertEqual(schedule.periods, (9, 10))
        self.assertEqual(schedule.blocks, 1)
        self.assertEqual(schedule.minutes, 45)

    def test_follow_semantics_and_term_boundaries(self) -> None:
        courses = [_course(2, "3-4", "1")]
        exception = {"date": "2026-09-17", "kind": "follow", "follow": "2026-09-08"}
        calendar = self._calendar(
            _timetable_document(
                courses=courses,
                semesters=[_semester(courses=courses, exceptions=[exception])],
            )
        )
        schedule = calendar.day(date(2026, 9, 17), BASE)
        self.assertEqual(schedule.week, 2)
        self.assertEqual(schedule.followed, date(2026, 9, 8))
        self.assertEqual(schedule.weekday_used, 2)
        self.assertEqual(schedule.periods, (3, 4))
        self.assertEqual(schedule.minutes, 105)

        no_class = {"date": "2026-09-08", "kind": "no_class"}
        off_day = self._calendar(
            _timetable_document(
                semesters=[_semester(courses=courses, exceptions=[no_class])]
            )
        )
        schedule = off_day.day(date(2026, 9, 8), BASE)
        self.assertTrue(schedule.no_class)
        self.assertIsNone(schedule.weekday_used)
        self.assertEqual(schedule.periods, ())
        self.assertEqual(schedule.minutes, 120)

        boundary_calendar = self._calendar(_timetable_document())
        self.assertEqual(boundary_calendar.minutes_for(date(2027, 1, 10), BASE), 120)
        self.assertIsNone(boundary_calendar.minutes_for(date(2027, 1, 11), BASE))
        self.assertIsNone(boundary_calendar.minutes_for(date(2027, 1, 20), BASE))
        self.assertIsNone(boundary_calendar.minutes_for(date(2027, 2, 1), BASE))
        self.assertEqual(
            boundary_calendar.minutes_between(date(2027, 1, 10), date(2027, 1, 12), BASE),
            {date(2027, 1, 10): 120},
        )

    def test_workspace_school_reference_and_period_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            document = _timetable_document(
                semesters=[_semester(school="missing-school")]
            )
            workspace, _, _ = _workspace(
                Path(temporary) / "workspace", {"demo": _school_document()}, document
            )
            with self.assertRaises(ContractError) as caught:
                timetable_for_workspace(workspace)
            self.assertEqual(caught.exception.path, "semesters[0].school")

        with tempfile.TemporaryDirectory() as temporary:
            other_school = _school_document("other")
            document = _timetable_document(semesters=[_semester(school="demo")])
            workspace, _, _ = _workspace(
                Path(temporary) / "workspace", {"demo": other_school}, document
            )
            with self.assertRaises(ContractError) as caught:
                timetable_for_workspace(workspace)
            self.assertEqual(caught.exception.path, "semesters[0].school")

        with tempfile.TemporaryDirectory() as temporary:
            document = _timetable_document(
                courses=[_course(1, "10-11")]
            )
            workspace, _, _ = _workspace(
                Path(temporary) / "workspace", {"demo": _school_document()}, document
            )
            with self.assertRaises(ContractError) as caught:
                timetable_for_workspace(workspace)
            self.assertEqual(
                caught.exception.path, "semesters[0].courses[0].periods"
            )

    def test_timetable_registration_absence_and_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace, _, _ = _workspace(
                Path(temporary) / "workspace",
                {"demo": _school_document()},
                _timetable_document(),
                timetable_registered=False,
            )
            self.assertIsNone(timetable_for_workspace(workspace))

        with tempfile.TemporaryDirectory() as temporary:
            workspace, _, timetable_path = _workspace(
                Path(temporary) / "workspace",
                {"demo": _school_document()},
                _timetable_document(),
            )
            timetable_path.unlink()
            with self.assertRaises(ContractError) as caught:
                timetable_for_workspace(workspace)
            self.assertEqual(caught.exception.path, "state.timetable")

    def test_referenced_sources_are_read_once_and_hashed_from_parsed_bytes(self) -> None:
        semesters = [
            _semester(label="first", monday="2026-09-07", weeks=1),
            _semester(label="second", monday="2026-09-14", weeks=1),
        ]
        document = _timetable_document(semesters=semesters)
        with tempfile.TemporaryDirectory() as temporary:
            workspace, school_paths, timetable_path = _workspace(
                Path(temporary) / "workspace",
                {"demo": _school_document(), "unused": _school_document("unused")},
                document,
            )
            original_read = Path.read_bytes
            reads: dict[Path, int] = {}

            def counted_read(path: Path) -> bytes:
                reads[path] = reads.get(path, 0) + 1
                return original_read(path)

            with patch.object(Path, "read_bytes", counted_read):
                calendar = timetable_for_workspace(workspace)

            self.assertEqual(reads[timetable_path], 1)
            self.assertEqual(reads[school_paths["demo"]], 1)
            self.assertNotIn(school_paths["unused"], reads)
            self.assertEqual(
                calendar.sources,
                {
                    "data/timetable.yaml": hashlib.sha256(
                        original_read(timetable_path)
                    ).hexdigest(),
                    "data/schools/demo.yaml": hashlib.sha256(
                        original_read(school_paths["demo"])
                    ).hexdigest(),
                },
            )
            with self.assertRaises(TypeError):
                calendar.sources["other"] = "hash"

    def test_repository_timetable_and_school_real_data(self) -> None:
        reason = "个人数据只在本机（`contracts/workspace.md` §2.6）"
        local_registry = ROOT / "kaoyan.workspace.local.yaml"
        require_path(None, local_registry, reason)
        workspace = load_workspace(ROOT / WORKSPACE_FILENAME)
        if workspace.timetable is None or not workspace.timetable_schools:
            self.skipTest(reason)
        require_path(None, ROOT / "data" / "personal", reason)
        school_paths = tuple(workspace.timetable_schools.values())
        if (
            not workspace.timetable.is_file()
            or not all(path.is_file() for path in school_paths)
        ):
            self.skipTest(reason)
        calendar = timetable_for_workspace(workspace)
        # Personal timetable contents stay out of tracked files (user 2026-09-30, sol round 224
        # R3): assert only general invariants here; exact numbers live in the synthetic cases.
        for semester in calendar.timetable.semesters:
            days = [
                semester.week1_monday + timedelta(days=offset)
                for offset in range(7 * semester.weeks)
            ]
            for day in days:
                with self.subTest(semester=semester.label, day=day):
                    schedule = calendar.day(day, BASE)
                    self.assertIsInstance(schedule, DaySchedule)
                    self.assertTrue(0 <= schedule.minutes <= schedule.cap)
                    self.assertLessEqual(schedule.minutes, schedule.free_minutes)
        if calendar.timetable.semesters:
            first_monday = min(item.week1_monday for item in calendar.timetable.semesters)
            self.assertIsNone(calendar.minutes_for(first_monday - timedelta(days=1), BASE))

    def test_public_m18_entry_validation_scopes(self) -> None:
        candidate = _semester(school="unregistered")
        semester = semester_from_mapping(candidate, "candidate")
        self.assertEqual(semester.school, "unregistered")
        with self.assertRaises(ContractError) as single_error:
            semester_from_mapping(
                _semester(courses=[_course(1, "1", "0")]), "candidate"
            )
        self.assertEqual(
            single_error.exception.path, "candidate.courses[0].weeks"
        )

        duplicate_labels = _timetable_document(
            semesters=[
                _semester(label="same", monday="2026-09-07"),
                _semester(label="same", monday="2026-10-05"),
            ]
        )
        with self.assertRaises(ContractError) as duplicate:
            timetable_from_mapping(duplicate_labels)
        self.assertEqual(duplicate.exception.path, "semesters[1].label")
        overlapping = _timetable_document(
            semesters=[
                _semester(label="first", monday="2026-09-07", weeks=3),
                _semester(label="second", monday="2026-09-21", weeks=2),
            ]
        )
        with self.assertRaises(ContractError) as overlap:
            timetable_from_mapping(overlapping)
        self.assertEqual(overlap.exception.path, "semesters[1].week1_monday")

        school = load_school_from_mapping_for_test()
        with self.assertRaises(ContractError) as missing_period:
            validate_semester_references(
                semester_from_mapping(
                    _semester(courses=[_course(1, "1-11")]), "candidate"
                ),
                school,
                "candidate",
            )
        self.assertEqual(
            missing_period.exception.path, "candidate.courses[0].periods"
        )
        with self.assertRaises(ContractError) as mismatch:
            validate_semester_references(
                semester_from_mapping(_semester(), "candidate"),
                load_school_from_mapping_for_test("other"),
                "candidate",
            )
        self.assertEqual(mismatch.exception.path, "candidate.school")

    def test_public_m18_loading_calendar_and_serialization(self) -> None:
        document = _timetable_document(
            courses=[_course(1, "1", "1,2,3,5,7-9")],
            semesters=[
                _semester(
                    courses=[_course(1, "1", "1-2,4")],
                    exceptions=[
                        {"kind": "follow", "date": "2026-09-08", "follow": "2026-09-07"},
                        {"kind": "no_class", "from": "2026-09-09", "to": "2026-09-10"},
                    ],
                )
            ],
        )
        timetable = timetable_from_mapping(document)
        encoded = timetable_to_mapping(timetable)
        self.assertNotIn("daily_cap_minutes", encoded["rules"])
        self.assertEqual(encoded["semesters"][0]["week1_monday"], "2026-09-07")
        self.assertEqual(encoded["semesters"][0]["courses"][0]["weeks"], "1-2,4")
        self.assertEqual(timetable_from_mapping(encoded), timetable)
        self.assertEqual(semester_from_mapping(
            semester_to_mapping(timetable.semesters[0]), "semester"
        ), timetable.semesters[0])

        with tempfile.TemporaryDirectory() as temporary:
            workspace, school_paths, _ = _workspace(
                Path(temporary) / "workspace",
                {"demo": _school_document(), "unused": _school_document("unused")},
                _timetable_document(),
                timetable_registered=False,
            )
            school_paths["unused"].unlink()
            loaded = load_referenced_schools(workspace, ["demo"])
            self.assertEqual(tuple(loaded), ("demo",))
            school = loaded["demo"]
            self.assertEqual(school.path, school_paths["demo"])
            self.assertEqual(len(school.sha256), 64)
            calendar = build_calendar(timetable, loaded)
            self.assertEqual(calendar.timetable, timetable)
            self.assertEqual(calendar.sources, {})

            with patch.object(Path, "read_bytes", side_effect=AssertionError("unexpected read")):
                direct = build_calendar(
                    timetable,
                    {"demo": LoadedSchool(school.profile, school.path, school.sha256)},
                )
            self.assertEqual(direct.timetable, timetable)
            self.assertEqual(direct.schools["demo"], school.profile)

    def test_timetable_for_workspace_matches_fixed_4816a14(self) -> None:
        repository = ROOT
        baseline = "4816a14"
        old_calendar_source = fixed_source(
            repository,
            baseline,
            "ky/timetable/calendar.py",
            lambda source: (
                b"def _load_referenced_schools(" in source
                and b"def timetable_for_workspace(" in source
                and b"def load_referenced_schools(" not in source
            ),
        )
        old_timetable_source = fixed_source(
            repository,
            baseline,
            "ky/timetable/timetable.py",
            lambda source: b"def _timetable_from_mapping(" in source,
        )
        self.assertIn(b"_load_referenced_schools", old_calendar_source)
        self.assertIn(b"_timetable_from_mapping", old_timetable_source)

        script = (
            "import json, sys\n"
            "from collections import Counter\n"
            "from dataclasses import asdict\n"
            "from datetime import date\n"
            "from pathlib import Path\n"
            "sys.path.insert(0, sys.argv[1])\n"
            "from ky.models import ContractError\n"
            "from ky.timetable import timetable_for_workspace\n"
            "from ky.workspace import load_workspace\n"
            "root = Path(sys.argv[2])\n"
            "counts = Counter()\n"
            "original = Path.read_bytes\n"
            "def counted(path):\n"
            "    data = original(path)\n"
            "    if path.name in {'timetable.yaml', 'demo.yaml'}:\n"
            "        counts[path.name] += 1\n"
            "    return data\n"
            "Path.read_bytes = counted\n"
            "try:\n"
            "    workspace = load_workspace(root / 'kaoyan.workspace.yaml')\n"
            "    calendar = timetable_for_workspace(workspace)\n"
            "    result = {'schedule': asdict(calendar.day(date(2026, 9, 7), 120)), "
            "'sources': dict(calendar.sources)}\n"
            "except ContractError as error:\n"
            "    result = {'error': error.path}\n"
            "result['reads'] = dict(sorted(counts.items()))\n"
            "print(json.dumps(result, sort_keys=True, default=str))\n"
        )

        def run_side(root: Path, python_path: Path) -> tuple[ProcessResult, dict[str, bytes]]:
            completed = subprocess.run(
                ["py", "-3.12", "-c", script, str(python_path), str(root)],
                cwd=repository,
                capture_output=True,
                check=False,
            )
            return ProcessResult(
                completed.returncode, completed.stdout, completed.stderr
            ), {}

        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            archive_root = temporary_root / "old"
            archive_root.mkdir()
            archive = subprocess.run(
                ["git", "archive", baseline, "ky"],
                cwd=repository,
                capture_output=True,
                check=True,
            ).stdout
            with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as bundle:
                bundle.extractall(archive_root, filter="data")
            fixture = temporary_root / "fixture"
            workspace, _, timetable_path = _workspace(
                fixture,
                {"demo": _school_document()},
                _timetable_document(courses=[_course(1, "1-2", "1-3")]),
            )
            # Both implementations receive identical fixture bytes and files.
            old_fixture = temporary_root / "old-fixture"
            import shutil
            shutil.copytree(fixture, old_fixture)
            new_run = lambda: run_side(fixture, repository)
            old_run = lambda: run_side(old_fixture, archive_root)
            compare_runs(old_run, new_run)

            broken = _timetable_document(
                courses=[_course(1, "1-11", "1-3")]
            )
            _write_yaml(timetable_path, broken)
            old_broken = old_fixture / "data" / "timetable.yaml"
            _write_yaml(old_broken, broken)
            compare_runs(old_run, new_run)


def load_school_from_mapping_for_test(school_id: str = "demo"):
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "school.yaml"
        _write_yaml(path, _school_document(school_id))
        return load_school(path)


if __name__ == "__main__":
    unittest.main()
