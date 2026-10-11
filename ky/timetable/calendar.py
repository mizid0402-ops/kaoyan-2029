"""M18 day calculations; see ``contracts/timetable.md`` §§4, 5, and 7.

Public interfaces: :class:`TimetableCalendar`, :func:`timetable_for_workspace`,
:func:`build_calendar`, :func:`load_referenced_schools`, and
:func:`validate_semester_references`.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from types import MappingProxyType
from typing import Iterable, Mapping

from ky.models import ContractError
from ky.timetable._common import (
    check_integer,
    format_time,
    read_yaml_file,
)
from ky.timetable._models import (
    Course,
    DaySchedule,
    Follow,
    LoadedSchool,
    NoClass,
    SchoolProfile,
    Semester,
    Timetable,
)
from ky.timetable.school import _school_from_mapping
from ky.timetable.timetable import timetable_from_mapping
from ky.workspace import Workspace


def _course_rows(
    semester: Semester,
    school: SchoolProfile,
    day: date,
) -> tuple[tuple[tuple[str, int, int, str, str], ...], tuple[int, ...]]:
    week = (day - semester.week1_monday).days // 7 + 1
    weekday = day.isoweekday()
    rows: list[tuple[str, int, int, str, str]] = []
    periods: set[int] = set()
    for course in semester.courses:
        if course.weekday != weekday or week not in course.weeks:
            continue
        first = school.periods[course.first_period]
        last = school.periods[course.last_period]
        rows.append(
            (
                course.name,
                course.first_period,
                course.last_period,
                format_time(first.start),
                format_time(last.end),
            )
        )
        periods.update(range(course.first_period, course.last_period + 1))
    return tuple(rows), tuple(sorted(periods))


def _block_count(periods: tuple[int, ...], school: SchoolProfile) -> int:
    occupied_blocks = {
        block_index
        for block_index, block in enumerate(school.blocks)
        if any(period in block for period in periods)
    }
    return len(occupied_blocks)


def _occupied_intervals(
    periods: tuple[int, ...], school: SchoolProfile, start: int, end: int, buffer: int
) -> list[tuple[int, int]]:
    intervals = []
    for number in periods:
        period = school.periods[number]
        clipped_start = max(start, period.start - buffer)
        clipped_end = min(end, period.end + buffer)
        if clipped_start < clipped_end:
            intervals.append((clipped_start, clipped_end))
    intervals.sort()
    merged: list[tuple[int, int]] = []
    for interval_start, interval_end in intervals:
        if merged and interval_start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], interval_end))
        else:
            merged.append((interval_start, interval_end))
    return merged


def _is_free_gap(start: int, end: int, min_gap_minutes: int) -> bool:
    # A zero threshold must not turn an empty interval into a "free segment" (sol round 224 R2).
    return end > start and end - start >= min_gap_minutes


def _free_segments(
    periods: tuple[int, ...],
    school: SchoolProfile,
    timetable: Timetable,
) -> tuple[tuple[tuple[int, int], ...], int]:
    rules = timetable.rules
    occupied = _occupied_intervals(
        periods,
        school,
        rules.study_start,
        rules.study_end,
        rules.buffer_minutes,
    )
    gaps: list[tuple[int, int]] = []
    cursor = rules.study_start
    for start, end in occupied:
        if _is_free_gap(cursor, start, rules.min_gap_minutes):
            gaps.append((cursor, start))
        cursor = max(cursor, end)
    if _is_free_gap(cursor, rules.study_end, rules.min_gap_minutes):
        gaps.append((cursor, rules.study_end))
    return tuple(gaps), sum(end - start for start, end in gaps)


def _exception_for(semester: Semester, day: date) -> tuple[bool, date | None]:
    for item in semester.exceptions:
        if isinstance(item, NoClass) and item.start <= day <= item.end:
            return True, None
        if isinstance(item, Follow) and item.day == day:
            return False, item.target
    return False, None


def _is_day(value: object, path: str) -> date:
    if isinstance(value, datetime) or not isinstance(value, date):
        raise ContractError("expected a date", path)
    return value


@dataclass(frozen=True)
class TimetableCalendar:
    """Immutable timetable data and its auditable source fingerprints."""

    timetable: Timetable
    schools: Mapping[str, SchoolProfile]
    sources: Mapping[str, str]

    def _semester_for(self, day: date) -> Semester | None:
        for semester in self.timetable.semesters:
            if semester.week1_monday <= day < semester.end_exclusive:
                return semester
        return None

    def day(self, day: date, base_minutes: int) -> DaySchedule | None:
        """Return the schedule for a covered date, or ``None`` outside all terms.

        ``base_minutes`` is the day's base resolved by M8; M18 never reads the config or route
        itself, so a base adjusted by M28 reaches the cap unchanged (user 2026-09-30).
        """
        value = _is_day(day, "day")
        base = check_integer(base_minutes, "base_minutes", minimum=0)
        semester = self._semester_for(value)
        if semester is None:
            return None
        school = self.schools[semester.school]
        week = (value - semester.week1_monday).days // 7 + 1
        no_class, followed = _exception_for(semester, value)
        course_day = followed if followed is not None else value
        weekday_used = None if no_class else course_day.isoweekday()
        if no_class:
            classes, periods = (), ()
        else:
            classes, periods = _course_rows(semester, school, course_day)
        blocks = _block_count(periods, school)
        segments, free_minutes = _free_segments(periods, school, self.timetable)
        cap = self.timetable.rules.daily_cap_minutes
        if cap is None:
            cap = base
        minutes = max(
            0,
            min(
                cap - blocks * self.timetable.rules.block_deduction_minutes,
                free_minutes,
            ),
        )
        unconfirmed = tuple(
            number for number in periods if school.periods[number].unconfirmed
        )
        return DaySchedule(
            day=value,
            semester=semester.label,
            week=week,
            followed=followed,
            weekday_used=weekday_used,
            no_class=no_class,
            classes=classes,
            periods=periods,
            blocks=blocks,
            free_segments=tuple(
                (format_time(start), format_time(end)) for start, end in segments
            ),
            free_minutes=free_minutes,
            cap=cap,
            minutes=minutes,
            unconfirmed_periods=unconfirmed,
        )

    def minutes_for(self, day: date, base_minutes: int) -> int | None:
        """Return derived minutes for M26, preserving ``None`` outside terms."""
        schedule = self.day(day, base_minutes)
        return None if schedule is None else schedule.minutes

    def minutes_between(
        self,
        start: date,
        end_exclusive: date,
        base_minutes: int,
    ) -> Mapping[date, int]:
        """Return covered-day minutes in the half-open date interval for one fixed base."""
        first = _is_day(start, "start")
        end = _is_day(end_exclusive, "end_exclusive")
        check_integer(base_minutes, "base_minutes", minimum=0)
        if end < first:
            raise ContractError("end_exclusive precedes start", "end_exclusive")
        days: dict[date, int] = {}
        current = first
        while current < end:
            minutes = self.minutes_for(current, base_minutes)
            if minutes is not None:
                days[current] = minutes
            current += timedelta(days=1)
        return MappingProxyType(days)


def _source_key(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError as exc:
        raise ContractError("source path is outside the workspace", path.as_posix()) from exc


class _SchoolIdentityError(ContractError):
    """Keep M18's historical semester path while exposing school loading separately."""


def _school_registration_path(school_id: str) -> str:
    return f"reference.timetable_schools.{school_id}"


def _load_school(
    workspace: Workspace, school_id: str, by_path: dict[Path, tuple[SchoolProfile, str]]
) -> LoadedSchool:
    # Registrations may share one file; ``by_path`` keeps it to a single read (sol round 236 R2).
    key = _school_registration_path(school_id)
    path = workspace.require(key)
    if path not in by_path:
        raw, data = read_yaml_file(path, error_path=key)
        by_path[path] = (_school_from_mapping(raw), hashlib.sha256(data).hexdigest())
    profile, digest = by_path[path]
    if profile.school_id != school_id:
        raise _SchoolIdentityError("school_id does not match registration", key)
    return LoadedSchool(profile, path, digest)


def load_referenced_schools(
    workspace: Workspace, school_ids: Iterable[str]
) -> Mapping[str, LoadedSchool]:
    by_path: dict[Path, tuple[SchoolProfile, str]] = {}
    loaded = {
        school_id: _load_school(workspace, school_id, by_path)
        for school_id in dict.fromkeys(school_ids)
    }
    return MappingProxyType(loaded)


def validate_semester_references(
    semester: Semester, school: SchoolProfile, path_prefix: str
) -> None:
    if school.school_id != semester.school:
        raise ContractError("school_id does not match registration", f"{path_prefix}.school")
    for course_index, course in enumerate(semester.courses):
        if any(
            number not in school.periods
            for number in range(course.first_period, course.last_period + 1)
        ):
            raise ContractError(
                "course period is not defined by the school",
                f"{path_prefix}.courses[{course_index}].periods",
            )


def build_calendar(
    timetable: Timetable,
    schools: Mapping[str, LoadedSchool],
    sources: Mapping[str, str] | None = None,
) -> TimetableCalendar:
    profiles: dict[str, SchoolProfile] = {}
    for index, semester in enumerate(timetable.semesters):
        loaded = schools.get(semester.school)
        if loaded is None:
            raise ContractError(
                "school is not registered", f"semesters[{index}].school"
            )
        validate_semester_references(semester, loaded.profile, f"semesters[{index}]")
        profiles[semester.school] = loaded.profile
    fingerprints = MappingProxyType(dict(sources or {}))
    return TimetableCalendar(timetable, MappingProxyType(profiles), fingerprints)


def timetable_for_workspace(workspace: Workspace) -> TimetableCalendar | None:
    """Load one registered timetable and only the school profiles it references."""
    if workspace.timetable is None:
        return None
    path = workspace.write_target("state.timetable")
    raw, data = read_yaml_file(path, error_path="state.timetable")
    timetable = timetable_from_mapping(raw)
    sources = {_source_key(workspace.root, path): hashlib.sha256(data).hexdigest()}
    loaded: dict[str, LoadedSchool] = {}
    by_path: dict[Path, tuple[SchoolProfile, str]] = {}
    for index, semester in enumerate(timetable.semesters):
        if semester.school not in workspace.timetable_schools:
            raise ContractError("school is not registered", f"semesters[{index}].school")
        if semester.school not in loaded:
            try:
                loaded[semester.school] = _load_school(workspace, semester.school, by_path)
            except _SchoolIdentityError as exc:
                raise ContractError(exc.message, f"semesters[{index}].school") from exc
        school = loaded[semester.school].profile
        validate_semester_references(semester, school, f"semesters[{index}]")
        loaded_school = loaded[semester.school]
        sources[_source_key(workspace.root, loaded_school.path)] = loaded_school.sha256
    return build_calendar(timetable, loaded, sources)
