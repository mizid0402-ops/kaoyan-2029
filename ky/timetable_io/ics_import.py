"""M29 iCalendar import for ``contracts/timetable_import.md`` §4.

Public interface: :func:`import_ics`.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dateutil.rrule import rrulestr
from icalendar import Calendar

from ky.models import ContractError
from ky.timetable import (
    Semester, load_referenced_schools, semester_from_mapping,
    validate_semester_references,
)
from ky.timetable_io import (
    StagedSemester, inspect_isolation, publish_staging,
)
from ky.timetable_io.preview import preview_lines
from ky.workspace import Workspace


def _components(data: bytes, source: Path):
    try:
        parsed = Calendar.from_ical(data)
    except Exception as exc:
        raise ContractError(f"invalid iCalendar: {exc}", source.as_posix()) from exc
    return [item for item in parsed.walk("VEVENT")]


def _groups(components):
    grouped = defaultdict(list)
    for component in components:
        uid = str(component.get("UID", ""))
        if not uid:
            raise ContractError("VEVENT requires UID", "VEVENT.UID")
        grouped[uid].append(component)
    result = {}
    for uid, items in grouped.items():
        masters = [item for item in items if item.get("RECURRENCE-ID") is None]
        if len(masters) > 1:
            raise ContractError("multiple master events for UID", f"UID {uid}")
        result[uid] = (masters[0] if masters else None, [
            item for item in items if item.get("RECURRENCE-ID") is not None
        ])
    return result


def _date_property(component, name: str, uid: str):
    value = component.get(name)
    if value is None:
        return None
    try:
        return value.dt
    except (AttributeError, TypeError, ValueError) as exc:
        raise ContractError("invalid date-time property", f"UID {uid}.{name}") from exc


def _duration(component, uid: str) -> timedelta:
    start = _date_property(component, "DTSTART", uid)
    end = _date_property(component, "DTEND", uid)
    duration = component.get("DURATION")
    if end is not None and duration is not None:
        raise ContractError("DTEND and DURATION are mutually exclusive", f"UID {uid}")
    if end is not None:
        if type(start) is not type(end):
            raise ContractError("DTSTART and DTEND types differ", f"UID {uid}")
        if isinstance(start, datetime) and (
            (start.tzinfo is None) != (end.tzinfo is None)
        ):
            raise ContractError("DTSTART and DTEND timezone types differ", f"UID {uid}.DTEND")
        result = end - start
    elif duration is not None:
        # M29 / sol 281 M1: retain the malformed field's path at this boundary.
        try:
            result = duration.dt
        except (AttributeError, TypeError, ValueError) as exc:
            raise ContractError(
                "invalid duration property", f"UID {uid}.DURATION"
            ) from exc
    else:
        raise ContractError("event requires DTEND or DURATION", f"UID {uid}")
    if result <= timedelta(0):
        raise ContractError("event end must follow start", f"UID {uid}")
    return result


def _check_master_shape(master, start, uid: str) -> None:
    """Spec section 4 step 3: these shapes are rejected even for events that are skipped.

    They ran before the skip decision originally; keep them there (sol round 249 N1).
    """
    if master.get("DTEND") is not None and master.get("DURATION") is not None:
        raise ContractError("DTEND and DURATION are mutually exclusive", f"UID {uid}")
    end = _date_property(master, "DTEND", uid)
    if start is not None and end is not None and type(start) is not type(end):
        raise ContractError("DTSTART and DTEND types differ", f"UID {uid}")


def _excluded_masters(groups) -> tuple[set[str], list[str]]:
    excluded, notes = set(), []
    for uid, (master, overrides) in groups.items():
        if master is None:
            continue
        status = str(master.get("STATUS", "")).upper()
        start = _date_property(master, "DTSTART", uid)
        _check_master_shape(master, start, uid)
        if isinstance(start, date) and not isinstance(start, datetime):
            excluded.add(uid)
            notes.append(f"忽略全天事件 UID {uid}")
        elif status == "CANCELLED":
            excluded.add(uid)
            notes.append(f"忽略取消事件 UID {uid}")
        elif master.get("DTEND") is None and master.get("DURATION") is None:
            excluded.add(uid)
            notes.append(f"忽略无结束时间事件 UID {uid}")
        else:
            if not isinstance(start, datetime):
                raise ContractError("DTSTART must be date-time", f"UID {uid}.DTSTART")
            _duration(master, uid)
            continue
        if overrides:
            notes.append(f"忽略已排除主事件的覆盖 UID {uid}")
    return excluded, notes


def _target_time(value: datetime, target_zone: ZoneInfo, uid: str) -> datetime:
    if value.tzinfo is None:
        return value
    try:
        return value.astimezone(target_zone)
    except (OverflowError, ValueError) as exc:
        raise ContractError("cannot convert event timezone", f"UID {uid}") from exc


def _original_key(value):
    if isinstance(value, datetime):
        return (type(value), value.replace(tzinfo=None), str(value.tzinfo))
    return (type(value), value, None)


def _expand_master(master, uid: str, weeks: int | None, week1: date,
                   target_zone: ZoneInfo, notes: list[str]):
    start = _date_property(master, "DTSTART", uid)
    duration = _duration(master, uid)
    rule_prop = master.get("RRULE")
    if master.get("RDATE") is not None:
        raise ContractError("RDATE is unsupported", f"UID {uid}.RDATE")
    if rule_prop is None:
        bounded = True
        result = [(start, start + duration)]
    else:
        rule_map = dict(rule_prop)
        allowed = {"FREQ", "INTERVAL", "BYDAY", "UNTIL", "COUNT"}
        unknown = set(rule_map) - allowed
        if unknown or str(rule_map.get("FREQ", [""])[0]).upper() != "WEEKLY":
            raise ContractError("unsupported RRULE", f"UID {uid}.RRULE")
        if "UNTIL" in rule_map and "COUNT" in rule_map:
            raise ContractError("UNTIL and COUNT cannot be combined", f"UID {uid}.RRULE")
        bounded = "UNTIL" in rule_map or "COUNT" in rule_map
        if not bounded and weeks is None:
            raise ContractError("unbounded RRULE requires --weeks", f"UID {uid}.RRULE")
        try:
            parsed_rule = rrulestr(rule_prop.to_ical().decode("ascii"), dtstart=start)
            if bounded:
                starts = list(parsed_rule)
            else:
                target_end = datetime.combine(
                    week1 + timedelta(days=weeks * 7 + 1), time.min
                )
                if start.tzinfo is not None:
                    target_end = target_end.replace(tzinfo=target_zone).astimezone(start.tzinfo)
                starts = list(parsed_rule.between(start, target_end, inc=True))
        except Exception as exc:
            raise ContractError(f"invalid RRULE: {exc}", f"UID {uid}.RRULE") from exc
        result = [(item, item + duration) for item in starts]
    exdates = []
    properties = master.get("EXDATE", [])
    if not isinstance(properties, list):
        properties = [properties]
    for prop in properties:
        exdates.extend(prop.dts)
    excluded = {_original_key(item.dt) for item in exdates}
    result = [item for item in result if _original_key(item[0]) not in excluded]
    if not bounded:
        notes.append(f"规则无终止，截至第 {weeks} 周")
    return result, bounded


def _overrides(master, overrides, uid: str, instances, duration: timedelta):
    by_identity = {_original_key(start): (start, end) for start, end in instances}
    applied = {}
    override_keys = set()
    for component in overrides:
        recurrence_id = _date_property(component, "RECURRENCE-ID", uid)
        if not isinstance(recurrence_id, datetime):
            raise ContractError("RECURRENCE-ID must be date-time", f"UID {uid}.RECURRENCE-ID")
        params = component.get("RECURRENCE-ID").params
        if str(params.get("RANGE", "")).upper() == "THISANDFUTURE":
            raise ContractError("THISANDFUTURE is unsupported", f"UID {uid}.RECURRENCE-ID")
        key = _original_key(recurrence_id)
        if key in applied:
            raise ContractError("duplicate override", f"UID {uid}.RECURRENCE-ID")
        applied[key] = component
        override_keys.add(key)
        if key not in by_identity:
            raise ContractError("orphan override", f"UID {uid}.RECURRENCE-ID")
        if str(component.get("STATUS", "")).upper() == "CANCELLED":
            by_identity.pop(key)
            continue
        new_start = _date_property(component, "DTSTART", uid)
        master_start = _date_property(master, "DTSTART", uid)
        if not isinstance(new_start, datetime) or type(new_start) is not type(master_start):
            raise ContractError("override DTSTART type differs", f"UID {uid}.DTSTART")
        if (component.get("DTEND") is not None and component.get("DURATION") is not None):
            raise ContractError("DTEND and DURATION are mutually exclusive", f"UID {uid}")
        if component.get("DTEND") is None and component.get("DURATION") is None:
            new_duration = duration
        else:
            new_duration = _duration(component, uid)
        by_identity.pop(key)
        by_identity[key] = (new_start, new_start + new_duration)
    for component in overrides:
        if component.get("RRULE") is not None or component.get("EXDATE") is not None:
            raise ContractError("override cannot contain RRULE or EXDATE", f"UID {uid}")
    return [
        (start, end, key in override_keys, applied.get(key))
        for key, (start, end) in by_identity.items()
    ]


def _local_interval(start, end, zone: ZoneInfo, uid: str):
    local_start = _target_time(start, zone, uid)
    local_end = _target_time(end, zone, uid)
    if local_start.date() != local_end.date():
        return None
    return local_start.date(), local_start.time(), local_end.time()


def _period_for_time(value: time, periods, *, ending: bool = False) -> int | None:
    if value.second or value.microsecond:
        return None
    minutes = value.hour * 60 + value.minute
    boundary = "end" if ending else "start"
    matches = [
        number for number, period in periods.items()
        if getattr(period, boundary) == minutes
    ]
    return matches[0] if matches else None


def _period_mismatches(uid, local_day, local_start, local_end, first, last) -> list[str]:
    """Describe every unmatched endpoint so all of them are reported at once (sol 246 R3)."""
    day = local_day.isoformat()
    errors = []
    if first is None:
        errors.append(f"UID {uid}.DTSTART date={day} time={local_start.isoformat()}")
    if last is None:
        errors.append(f"UID {uid}.DTEND date={day} time={local_end.isoformat()}")
    if not errors and first > last:
        errors.append(
            f"UID {uid}.DTSTART/DTEND date={day} "
            f"time={local_start.isoformat()}-{local_end.isoformat()}"
        )
    return errors


def _event_summary(override_component, summary: str, uid: str) -> str:
    """An override's own SUMMARY wins; otherwise the master's (spec section 4 step 5)."""
    if override_component is not None and override_component.get("SUMMARY") is not None:
        value = str(override_component.get("SUMMARY")).strip()
    else:
        value = summary
    if not value:
        raise ContractError("SUMMARY must not be empty", f"UID {uid}.SUMMARY")
    return value


def _instance_rows(groups, excluded, week1, weeks, zone, profile, notes):
    result = []
    period_errors = []
    domain_end = None if weeks is None else week1 + timedelta(days=weeks * 7)
    for uid, (master, overrides) in groups.items():
        if uid in excluded:
            continue  # its note (and any override's) was written when it was excluded
        if master is None:
            raise ContractError("orphan override", f"UID {uid}.RECURRENCE-ID")
        instances, bounded = _expand_master(master, uid, weeks, week1, zone, notes)
        duration = _duration(master, uid)
        final = _overrides(master, overrides, uid, instances, duration)
        summary = str(master.get("SUMMARY", "")).strip()
        for start, end, was_overridden, override_component in final:
            interval = _local_interval(start, end, zone, uid)
            if interval is None:
                notes.append(f"跨本地日期事件未导入 UID {uid}")
                continue
            local_day, local_start, local_end = interval
            if (
                not bounded and weeks is not None and domain_end is not None
                and local_day >= domain_end and not was_overridden
            ):
                continue
            if local_day < week1:
                raise ContractError("event precedes import domain", f"UID {uid}.DTSTART")
            if domain_end is not None and local_day >= domain_end:
                raise ContractError("event follows import domain", f"UID {uid}.DTSTART")
            first = _period_for_time(local_start, profile.periods)
            last = _period_for_time(local_end, profile.periods, ending=True)
            errors = _period_mismatches(uid, local_day, local_start, local_end, first, last)
            if errors:
                period_errors.extend(errors)
                continue
            event_summary = _event_summary(override_component, summary, uid)
            result.append((event_summary, local_day.isoweekday(), first, last,
                           (local_day - week1).days // 7 + 1))
    if period_errors:
        raise ContractError(
            "period boundary mismatches: " + "; ".join(period_errors),
            "VEVENT.periods",
        )
    return result


def _semester(rows, school: str, label: str, week1: date, weeks: int | None):
    if not rows:
        raise ContractError("no importable courses", "VEVENT")
    count = weeks if weeks is not None else max(row[4] for row in rows)
    grouped = defaultdict(set)
    for name, weekday, first, last, week in rows:
        key = (name, weekday, first, last)
        if week in grouped[key]:
            raise ContractError("duplicate course occurrence in week", "VEVENT")
        grouped[key].add(week)
    courses = [
        {
            "name": name,
            "weekday": weekday,
            "periods": str(first) if first == last else f"{first}-{last}",
            "weeks": ",".join(map(str, sorted(course_weeks))),
        }
        for (name, weekday, first, last), course_weeks in sorted(grouped.items())
    ]
    return semester_from_mapping({
        "label": label,
        "school": school,
        "week1_monday": week1.isoformat(),
        "weeks": count, "courses": courses, "exceptions": [],
    }, "semester")


def _target_timezone(timezone_name: str | None) -> ZoneInfo | None:
    if timezone_name is None:
        return None
    if not isinstance(timezone_name, str) or not timezone_name:
        raise ContractError("expected IANA timezone", "--timezone")
    try:
        return ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ContractError("unknown IANA timezone", "--timezone") from exc


def _validate_timezones(components, zone: ZoneInfo | None) -> ZoneInfo:
    for component in components:
        fields = ["DTSTART", "DTEND", "RECURRENCE-ID"]
        exdates = component.get("EXDATE", [])
        if not isinstance(exdates, list):
            exdates = [exdates]
        fields.append("EXDATE")
        for field in fields:
            if component.get(field) is None:
                continue
            properties = exdates if field == "EXDATE" else [component.get(field)]
            if not isinstance(properties, list):
                properties = [properties]
            for prop in properties:
                tzid = prop.params.get("TZID")
                if tzid is not None:
                    try:
                        ZoneInfo(str(tzid))
                    except (ZoneInfoNotFoundError, ValueError) as exc:
                        raise ContractError(
                            "unknown IANA TZID",
                            f"UID {component.get('UID', '')}.{field}.TZID",
                        ) from exc
                values = [item.dt for item in prop.dts] if field == "EXDATE" else [prop.dt]
                for value in values:
                    if isinstance(value, datetime) and value.tzinfo is not None and zone is None:
                        raise ContractError(
                            "--timezone is required for zoned events",
                            f"UID {component.get('UID', '')}.{field}",
                        )
    return zone if zone is not None else ZoneInfo("UTC")


def import_ics(workspace: Workspace, source: str | Path, *, school: str,
               label: str, week1: date, weeks: int | None = None,
               timezone_name: str | None = None, config_path: str | Path | None = None):
    """Parse an iCalendar file, validate one candidate semester, then stage it."""
    if type(week1) is not date:
        raise ContractError("expected ISO date", "--week1")
    if weeks is not None and (type(weeks) is not int or weeks < 1):
        raise ContractError("--weeks must be >= 1", "--weeks")
    if not isinstance(school, str) or not school:
        raise ContractError("school ID must not be empty", "--school")
    if not isinstance(label, str) or not label:
        raise ContractError("label must not be empty", "--label")
    zone = _target_timezone(timezone_name)
    path = Path(source)
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ContractError(f"cannot read iCalendar: {exc}", path.as_posix()) from exc
    components = _components(data, path)
    groups = _groups(components)
    excluded, notes = _excluded_masters(groups)
    active = [
        component
        for uid, (master, overrides) in groups.items()
        if uid not in excluded
        for component in ([master] if master is not None else []) + overrides
    ]
    zone = _validate_timezones(active, zone)
    loaded = load_referenced_schools(workspace, (school,))
    profile = loaded[school].profile
    rows = _instance_rows(groups, excluded, week1, weeks, zone, profile, notes)
    semester = _semester(rows, school, label, week1, weeks)
    validate_semester_references(semester, profile, "semester")
    staged = StagedSemester("ics", hashlib.sha256(data).hexdigest(), semester, tuple(notes))
    isolation = inspect_isolation(workspace.root)
    target, _ = publish_staging(workspace, staged, isolation)
    print(f"暂存文件：{target}")
    print(
        f"学期 {semester.label}：学校 {semester.school}，"
        f"第 1 周 {semester.week1_monday.isoformat()}，"
        f"共 {semester.weeks} 周，课程 {len(semester.courses)} 门"
    )
    for note in staged.notes:
        print(f"备注：{note}")
    for line in preview_lines(workspace, semester, config_path, schools=loaded):
        print(line)
    return target
