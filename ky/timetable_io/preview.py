"""M29 preview and base resolution for ``contracts/timetable_import.md`` §4/6.

Public interfaces: :func:`base_resolver` and :func:`preview_lines`.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Callable, Mapping
from pathlib import Path

from ky.models import KaoyanConfig, load_config
from ky.pacing import settings_for_workspace
from ky.schedule.budget import daily_base_minutes
from ky.storage.route_store import RoutePlanStore
from ky.timetable import (
    Semester,
    LoadedSchool,
    Timetable,
    TimetableRules,
    build_calendar,
    load_referenced_schools,
    load_timetable,
)
from ky.workspace import Workspace


def _week_grid(calendar, semester: Semester) -> tuple[str, ...]:
    monday = semester.week1_monday
    schedules = [calendar.day(monday + timedelta(days=i), 0) for i in range(7)]
    profile = calendar.schools[semester.school]
    weekdays = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")
    rows: list[str] = []
    for number, period in profile.periods.items():
        cells = []
        for weekday, schedule in zip(weekdays, schedules):
            names = [] if schedule is None else [
                name for name, first, last, _start, _end in schedule.classes
                if first <= number <= last
            ]
            cells.append(f"{weekday} {'/'.join(names) if names else '-'}")
        marker = "*" if period.unconfirmed else ""
        rows.append(
            f"{number:>2}{marker} {_time(period.start)}-{_time(period.end)} | "
            + " | ".join(cells)
        )
    return tuple(rows)


def _time(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _calendar_for_semester(
    workspace: Workspace,
    semester: Semester,
    schools: Mapping[str, LoadedSchool] | None,
):
    loaded = schools
    if loaded is None:
        loaded = load_referenced_schools(workspace, (semester.school,))
    return build_calendar(
        Timetable(
            rules=_preview_rules(workspace),
            semesters=(semester,),
        ),
        loaded,
    )


def _preview_rules(workspace: Workspace):
    if workspace.timetable is None:
        return TimetableRules(0, 1440, 0, 0, 0, None)
    return load_timetable(workspace.write_target("state.timetable")).rules


def base_resolver(
    workspace: Workspace, config: KaoyanConfig
) -> Callable[[date], int]:
    """Return the M8 base for each day, reading the registered route and pacing settings once.

    The base varies by route phase since M28b and by the pacing ``initial`` since M28c
    (``contracts/pacing_review.md`` §5), so callers resolve it per shown day instead of one
    configured value.
    """
    route = None
    if workspace.routes is not None:
        route = RoutePlanStore(workspace.write_target("state.routes")).current()
    pacing_settings = settings_for_workspace(workspace)

    def resolve(day: date) -> int:
        return daily_base_minutes(day, config, route, pacing_initial=pacing_settings)[0]

    return resolve


def preview_lines(
    workspace: Workspace,
    semester: Semester,
    config_path: str | Path | None = None,
    *,
    schools: Mapping[str, LoadedSchool] | None = None,
) -> tuple[str, ...]:
    """Render the candidate's first-week grid and optional daily M8 minutes."""
    calendar = _calendar_for_semester(workspace, semester, schools)
    lines = list(_week_grid(calendar, semester))
    config_source = Path(config_path) if config_path is not None else workspace.exam_config
    if workspace.timetable is not None and config_source is not None:
        base_for = base_resolver(workspace, load_config(config_source))
        days = [semester.week1_monday + timedelta(days=i) for i in range(7)]
        values = [calendar.minutes_for(day, base_for(day)) for day in days]
        lines.append("minutes            : " + " ".join(str(value) for value in values))
    return tuple(lines)
