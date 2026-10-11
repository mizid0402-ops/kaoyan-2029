"""M18 immutable values for ``contracts/timetable.md``."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class Period:
    start: int
    end: int
    unconfirmed: bool = False


@dataclass(frozen=True)
class SchoolProfile:
    school_id: str
    name: str
    aliases: tuple[str, ...]
    system: str
    recorded_on: date
    periods: Mapping[int, Period]
    blocks: tuple[tuple[int, ...], ...]


@dataclass(frozen=True)
class LoadedSchool:
    profile: SchoolProfile
    path: Path
    sha256: str


@dataclass(frozen=True)
class Course:
    name: str
    weekday: int
    first_period: int
    last_period: int
    weeks: frozenset[int]


@dataclass(frozen=True)
class NoClass:
    start: date
    end: date


@dataclass(frozen=True)
class Follow:
    day: date
    target: date


TimetableException = NoClass | Follow


@dataclass(frozen=True)
class Semester:
    label: str
    school: str
    week1_monday: date
    weeks: int
    courses: tuple[Course, ...]
    exceptions: tuple[TimetableException, ...]

    @property
    def end_exclusive(self) -> date:
        return self.week1_monday + timedelta(weeks=self.weeks)


@dataclass(frozen=True)
class TimetableRules:
    study_start: int
    study_end: int
    buffer_minutes: int
    min_gap_minutes: int
    block_deduction_minutes: int
    daily_cap_minutes: int | None


@dataclass(frozen=True)
class Timetable:
    rules: TimetableRules
    semesters: tuple[Semester, ...]


@dataclass(frozen=True)
class DaySchedule:
    day: date
    semester: str
    week: int
    followed: date | None
    weekday_used: int | None
    no_class: bool
    classes: tuple[tuple[str, int, int, str, str], ...]
    periods: tuple[int, ...]
    blocks: int
    free_segments: tuple[tuple[str, str], ...]
    free_minutes: int
    cap: int
    minutes: int
    unconfirmed_periods: tuple[int, ...]
