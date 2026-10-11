"""M18 personal timetable loader; see ``contracts/timetable.md`` §3.

Public interfaces: :func:`load_timetable`, :func:`timetable_from_mapping`,
:func:`timetable_to_mapping`, :func:`semester_from_mapping`, and :func:`semester_to_mapping`.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

from ky.models import ContractError
from ky.timetable._common import (
    check_date,
    check_integer,
    check_keys,
    check_mapping,
    check_string,
    check_time,
    identifier,
    read_yaml_file,
)
from ky.timetable._models import (
    Course,
    Follow,
    NoClass,
    Semester,
    Timetable,
    TimetableException,
    TimetableRules,
)
from ky.timetable.weeks import parse_week_expression

_ROOT_KEYS = frozenset({"schema_version", "rules", "semesters"})
_RULE_KEYS = frozenset(
    {
        "study_window", "buffer_minutes", "min_gap_minutes",
        "block_deduction_minutes", "daily_cap_minutes",
    }
)
_WINDOW_KEYS = frozenset({"start", "end"})
_SEMESTER_KEYS = frozenset(
    {"label", "school", "week1_monday", "weeks", "courses", "exceptions"}
)
_COURSE_KEYS = frozenset({"name", "weekday", "periods", "weeks"})
_PERIODS_RE = re.compile(r"^([0-9]+)(?:-([0-9]+))?$")


def _rules(value: object) -> TimetableRules:
    raw = check_mapping(value, "rules")
    required = frozenset(
        {"study_window", "buffer_minutes", "min_gap_minutes", "block_deduction_minutes"}
    )
    check_keys(raw, required, _RULE_KEYS, "rules")
    window = check_mapping(raw["study_window"], "rules.study_window")
    check_keys(window, _WINDOW_KEYS, _WINDOW_KEYS, "rules.study_window")
    start = check_time(window["start"], "rules.study_window.start")
    end = check_time(window["end"], "rules.study_window.end")
    if start >= end:
        raise ContractError("study window start must precede end", "rules.study_window")
    buffer_minutes = check_integer(raw["buffer_minutes"], "rules.buffer_minutes", minimum=0)
    min_gap = check_integer(raw["min_gap_minutes"], "rules.min_gap_minutes", minimum=0)
    deduction = check_integer(
        raw["block_deduction_minutes"], "rules.block_deduction_minutes", minimum=0
    )
    cap = None
    if "daily_cap_minutes" in raw:
        cap = check_integer(raw["daily_cap_minutes"], "rules.daily_cap_minutes", minimum=0)
    return TimetableRules(start, end, buffer_minutes, min_gap, deduction, cap)


def _course_periods(value: object, path: str) -> tuple[int, int]:
    if not isinstance(value, str):
        raise ContractError("periods must be a string", path)
    match = _PERIODS_RE.fullmatch(value)
    if match is None:
        raise ContractError("expected N or N-M", path)
    first = int(match.group(1))
    last = int(match.group(2) or match.group(1))
    if first < 1 or last < first:
        raise ContractError("invalid period range", path)
    return first, last


def _course(value: object, path: str, total_weeks: int) -> Course:
    raw = check_mapping(value, path)
    check_keys(raw, _COURSE_KEYS, _COURSE_KEYS, path)
    name = check_string(raw["name"], f"{path}.name")
    weekday = check_integer(raw["weekday"], f"{path}.weekday", minimum=1)
    if weekday > 7:
        raise ContractError("weekday must be from 1 through 7", f"{path}.weekday")
    first, last = _course_periods(raw["periods"], f"{path}.periods")
    weeks = parse_week_expression(raw["weeks"], total_weeks, f"{path}.weeks")
    return Course(name, weekday, first, last, weeks)


def _semester_end(start: date, weeks: int, path: str) -> date:
    try:
        return start + timedelta(weeks=weeks)
    except OverflowError as exc:
        raise ContractError("semester end exceeds supported dates", path) from exc


def _exception(value: object, path: str, start: date, end: date) -> TimetableException:
    raw = check_mapping(value, path)
    check_keys(raw, frozenset({"kind"}), frozenset({"date", "from", "to", "kind", "follow"}), path)
    kind = check_string(raw["kind"], f"{path}.kind")
    if kind == "no_class":
        if set(raw) == {"date", "kind"}:
            first = last = check_date(raw["date"], f"{path}.date")
        elif set(raw) == {"from", "to", "kind"}:
            first = check_date(raw["from"], f"{path}.from")
            last = check_date(raw["to"], f"{path}.to")
            if first > last:
                raise ContractError("exception range is reversed", f"{path}.to")
        else:
            raise ContractError("invalid no_class exception shape", path)
        if first < start or last >= end:
            field = f"{path}.date" if first == last else (
                f"{path}.from" if first < start else f"{path}.to"
            )
            raise ContractError("exception date is outside semester", field)
        return NoClass(first, last)
    if kind == "follow":
        if set(raw) != {"date", "kind", "follow"}:
            raise ContractError("invalid follow exception shape", path)
        day = check_date(raw["date"], f"{path}.date")
        target = check_date(raw["follow"], f"{path}.follow")
        if day < start or day >= end:
            raise ContractError("exception date is outside semester", f"{path}.date")
        if target < start or target >= end:
            raise ContractError("follow target is outside semester", f"{path}.follow")
        return Follow(day, target)
    raise ContractError("kind must be no_class or follow", f"{path}.kind")


def _exception_bounds(item: TimetableException) -> tuple[date, date]:
    if isinstance(item, NoClass):
        return item.start, item.end
    return item.day, item.day


def _validate_exception_set(
    exceptions: tuple[TimetableException, ...], path: str
) -> None:
    for index, current in enumerate(exceptions):
        current_start, current_end = _exception_bounds(current)
        for previous in exceptions[:index]:
            previous_start, previous_end = _exception_bounds(previous)
            if current_start <= previous_end and previous_start <= current_end:
                raise ContractError("exception dates overlap", f"{path}[{index}]")
    for index, item in enumerate(exceptions):
        if not isinstance(item, Follow):
            continue
        for other in exceptions:
            first, last = _exception_bounds(other)
            if first <= item.target <= last:
                raise ContractError("follow target is an exception date", f"{path}[{index}].follow")


def semester_from_mapping(value: object, path_prefix: str) -> Semester:
    path = path_prefix
    raw = check_mapping(value, path)
    required = frozenset({"label", "school", "week1_monday", "weeks", "courses"})
    check_keys(raw, required, _SEMESTER_KEYS, path)
    label = check_string(raw["label"], f"{path}.label")
    school = identifier(raw["school"], f"{path}.school")
    monday = check_date(raw["week1_monday"], f"{path}.week1_monday")
    if monday.isoweekday() != 1:
        raise ContractError("week1_monday must be a Monday", f"{path}.week1_monday")
    weeks = check_integer(raw["weeks"], f"{path}.weeks", minimum=1)
    end = _semester_end(monday, weeks, f"{path}.weeks")
    raw_courses = raw["courses"]
    if not isinstance(raw_courses, list):
        raise ContractError("courses must be a list", f"{path}.courses")
    courses = tuple(
        _course(course, f"{path}.courses[{course_index}]", weeks)
        for course_index, course in enumerate(raw_courses)
    )
    raw_exceptions = raw.get("exceptions", [])
    if not isinstance(raw_exceptions, list):
        raise ContractError("exceptions must be a list", f"{path}.exceptions")
    exception_path = f"{path}.exceptions"
    exceptions = tuple(
        _exception(item, f"{exception_path}[{item_index}]", monday, end)
        for item_index, item in enumerate(raw_exceptions)
    )
    _validate_exception_set(exceptions, exception_path)
    return Semester(label, school, monday, weeks, courses, exceptions)


def _semester(value: object, index: int) -> Semester:
    return semester_from_mapping(value, f"semesters[{index}]")


def _validate_semesters(semesters: tuple[Semester, ...]) -> None:
    labels: set[str] = set()
    ordered = sorted(enumerate(semesters), key=lambda item: item[1].week1_monday)
    previous_end: date | None = None
    for index, semester in enumerate(semesters):
        if semester.label in labels:
            raise ContractError("semester labels must be unique", f"semesters[{index}].label")
        labels.add(semester.label)
    for index, semester in ordered:
        if previous_end is not None and semester.week1_monday < previous_end:
            raise ContractError(
                "semester intervals overlap", f"semesters[{index}].week1_monday"
            )
        previous_end = semester.end_exclusive


def timetable_from_mapping(raw: object) -> Timetable:
    root = check_mapping(raw, "")
    check_keys(root, _ROOT_KEYS, _ROOT_KEYS, "")
    version = check_integer(root["schema_version"], "schema_version")
    if version != 1:
        raise ContractError("unsupported schema_version", "schema_version")
    rules = _rules(root["rules"])
    raw_semesters = root["semesters"]
    if not isinstance(raw_semesters, list):
        raise ContractError("semesters must be a list", "semesters")
    semesters = tuple(_semester(value, index) for index, value in enumerate(raw_semesters))
    _validate_semesters(semesters)
    return Timetable(rules, semesters)


def _weeks_to_expressions(weeks: frozenset[int]) -> list[str]:
    ordered = sorted(weeks)
    ranges: list[str] = []
    index = 0
    while index < len(ordered):
        first = last = ordered[index]
        index += 1
        while index < len(ordered) and ordered[index] == last + 1:
            last = ordered[index]
            index += 1
        ranges.append(str(first) if first == last else f"{first}-{last}")
    return ranges


def semester_to_mapping(semester: Semester) -> dict[str, object]:
    courses = [
        {
            "name": course.name,
            "weekday": course.weekday,
            "periods": (
                str(course.first_period)
                if course.first_period == course.last_period
                else f"{course.first_period}-{course.last_period}"
            ),
            "weeks": ",".join(_weeks_to_expressions(course.weeks)),
        }
        for course in semester.courses
    ]
    return {
        "label": semester.label,
        "school": semester.school,
        "week1_monday": semester.week1_monday.isoformat(),
        "weeks": semester.weeks,
        "courses": courses,
        "exceptions": [_exception_to_mapping(item) for item in semester.exceptions],
    }


def _exception_to_mapping(item: TimetableException) -> dict[str, str]:
    if isinstance(item, NoClass):
        if item.start == item.end:
            return {"kind": "no_class", "date": item.start.isoformat()}
        return {
            "kind": "no_class",
            "from": item.start.isoformat(),
            "to": item.end.isoformat(),
        }
    return {
        "kind": "follow",
        "date": item.day.isoformat(),
        "follow": item.target.isoformat(),
    }


def timetable_to_mapping(timetable: Timetable) -> dict[str, object]:
    rules: dict[str, object] = {
        "study_window": {
            "start": _format_minute(timetable.rules.study_start),
            "end": _format_minute(timetable.rules.study_end),
        },
        "buffer_minutes": timetable.rules.buffer_minutes,
        "min_gap_minutes": timetable.rules.min_gap_minutes,
        "block_deduction_minutes": timetable.rules.block_deduction_minutes,
    }
    if timetable.rules.daily_cap_minutes is not None:
        rules["daily_cap_minutes"] = timetable.rules.daily_cap_minutes
    return {
        "schema_version": 1,
        "rules": rules,
        "semesters": [semester_to_mapping(item) for item in timetable.semesters],
    }


def _format_minute(value: int) -> str:
    return f"{value // 60:02d}:{value % 60:02d}"


def load_timetable(path: str | Path) -> Timetable:
    """Read and validate one schema-version-1 personal timetable."""
    source = Path(path)
    raw, _ = read_yaml_file(source)
    return timetable_from_mapping(raw)
