"""M29 deterministic calendar export for ``contracts/timetable_import.md`` §6.

Public interface: :func:`export_ics`.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from icalendar import Calendar, Event

from ky.models import ContractError, load_config
from ky.planner.port import canonical_json_bytes
from ky.timetable_io.preview import base_resolver
from ky.timetable import timetable_for_workspace
from ky.timetable_io import check_isolated_path, inspect_isolation
from ky.workspace import Workspace


def _minute_time(value: int) -> time:
    return time(value // 60, value % 60)


def _intersects_gap(gap_start: int, gap_end: int, segments) -> bool:
    return any(
        max(gap_start, _minutes(start)) < min(gap_end, _minutes(end))
        for start, end in segments
    )


def _minutes(value: str) -> int:
    hour, minute = map(int, value.split(":"))
    return hour * 60 + minute


def _class_events(calendar, day, schedule):
    profile = calendar.schools[next(
        item.school for item in calendar.timetable.semesters if item.label == schedule.semester
    )]
    grouped = []
    for name, first, last, _start, _end in schedule.classes:
        periods = list(range(first, last + 1))
        segments = []
        begin = periods[0]
        previous = periods[0]
        for number in periods[1:]:
            gap_start = profile.periods[previous].end
            gap_end = profile.periods[number].start
            same_block = any(previous in block and number in block for block in profile.blocks)
            if same_block and not _intersects_gap(gap_start, gap_end, schedule.free_segments):
                previous = number
                continue
            segments.append((begin, previous))
            begin = previous = number
        segments.append((begin, previous))
        for first_period, last_period in segments:
            grouped.append((
                "class", day,
                _minute_time(profile.periods[first_period].start),
                _minute_time(profile.periods[last_period].end),
                name,
            ))
    return grouped


def _events(calendar, start: date, end: date, base_for, *, free_only: bool,
            classes_only: bool):
    records = []
    covered = False
    current = start
    while current < end:
        schedule = calendar.day(current, base_for(current))
        if schedule is not None:
            covered = True
            if not free_only:
                records.extend(_class_events(calendar, current, schedule))
            if not classes_only:
                for free_start, free_end in schedule.free_segments:
                    duration = _minutes(free_end) - _minutes(free_start)
                    records.append((
                        "free", current, time.fromisoformat(free_start),
                        time.fromisoformat(free_end), f"可学习 {duration} 分钟",
                    ))
        current += timedelta(days=1)
    if not covered:
        raise ContractError("timetable does not cover any date in range", "--from")
    return records


def _assign_indexes(records):
    counts = defaultdict(int)
    result = []
    for record in sorted(records, key=lambda row: (row[1], row[2], row[3], row[0], row[4])):
        identity = (record[0], record[1], record[2], record[3], record[4])
        index = counts[identity]
        counts[identity] += 1
        result.append((*record, index))
    return result


def _uid(record) -> str:
    kind, day, start, end, summary, index = record
    payload = {
        "kind": kind, "date": day.isoformat(), "start": start.isoformat(),
        "end": end.isoformat(), "summary": summary, "index": index,
    }
    digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()[:16]
    return f"{digest}@kaoyan-ai-system"


def _calendar_bytes(records, stamp: date) -> bytes:
    result = Calendar()
    result.add("version", "2.0")
    result.add("prodid", "-//kaoyan-ai-system//M29//ZH")
    for kind, day, start, end, summary, index in _assign_indexes(records):
        event = Event()
        event.add("uid", _uid((kind, day, start, end, summary, index)))
        event.add("dtstamp", datetime.combine(stamp, time.min, timezone.utc))
        event.add("dtstart", datetime.combine(day, start))
        event.add("dtend", datetime.combine(day, end))
        event.add("summary", summary)
        event.add("transp", "TRANSPARENT" if kind == "free" else "OPAQUE")
        if kind == "free":
            event.add("categories", "STUDY")
        result.add_component(event)
    return result.to_ical()


def _publish(target: Path, data: bytes, isolation) -> None:
    check_isolated_path(isolation, target)
    if target.exists():
        raise ContractError("output already exists", target.as_posix())
    temporary = check_isolated_path(
        isolation, target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    )
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with temporary.open("xb") as stream:
            stream.write(data)
        if temporary.read_bytes() != data:
            raise ContractError("temporary export changed", temporary.as_posix())
        check_isolated_path(isolation, temporary)
        try:
            os.link(temporary, target)
        except FileExistsError as exc:
            raise ContractError("output already exists", target.as_posix()) from exc
    except OSError as exc:
        raise ContractError(f"cannot publish calendar: {exc}", target.as_posix()) from exc
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError as exc:
            raise ContractError(
                f"cannot remove temporary calendar: {exc}", temporary.as_posix()
            ) from exc


def export_ics(workspace: Workspace, start: date, end: date, config_path: str | Path,
               output: str | Path, *, free_only: bool = False,
               classes_only: bool = False) -> Path:
    """Export covered M18 schedules into a deterministic floating-time calendar."""
    if type(start) is not date:
        raise ContractError("expected ISO date", "--from")
    if type(end) is not date:
        raise ContractError("expected ISO date", "--to")
    if type(free_only) is not bool:
        raise ContractError("expected a boolean", "--free-only")
    if type(classes_only) is not bool:
        raise ContractError("expected a boolean", "--classes-only")
    if end <= start:
        raise ContractError("--from must precede --to", "--from")
    if free_only and classes_only:
        raise ContractError("export filters are mutually exclusive", "--free-only")
    calendar = timetable_for_workspace(workspace)
    if calendar is None:
        raise ContractError("timetable is not registered", "state.timetable")
    base_for = base_resolver(workspace, load_config(config_path))
    records = _events(
        calendar, start, end, base_for,
        free_only=free_only, classes_only=classes_only,
    )
    data = _calendar_bytes(records, start)
    isolation = inspect_isolation(workspace.root)
    target = Path(output)
    _publish(target, data, isolation)
    return target
