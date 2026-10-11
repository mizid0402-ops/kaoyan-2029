"""M15 read-only status queries; see ``contracts/projection_status.md``.

Public interfaces: :func:`status_as_of` and :func:`status_to_mapping`.
The query uses the latest successfully rebuilt projection facts of the builder's current
schema version (``PROJECTION_SCHEMA_VERSION``).
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from ky.freeze.port import FreezeEvent, FreezePolicy, FreezeStatus, assess_freeze, latch_active
from ky.models import (
    ContractError,
    KaoyanConfig,
    ReviewItem,
    validate_items_against_config,
    validate_review_item,
)
from ky.projection import PROJECTION_SCHEMA_VERSION
from ky.schedule.state_snapshot import ReviewCounts, count_review_items_by_subject

# One source for the version: a literal here would drift from the builder (WP-M15-small).
_SCHEMA_VERSION = str(PROJECTION_SCHEMA_VERSION)
__all__ = [
    "StatusAsOf",
    "StatusDayPlan",
    "StatusRoutePhase",
    "SubjectStatus",
    "status_as_of",
    "status_to_mapping",
]
_REVIEW_COLUMNS = (
    "review_id", "revision", "subject_id", "knowledge_point_id", "title", "granularity",
    "state", "estimated_minutes", "introduced_on", "due_date", "last_reviewed_on",
    "schedule_mode", "schedule_phase", "interval_days", "ease_factor", "repetitions",
    "lapses", "stability", "difficulty", "fsrs_reviewed_on", "defer_count",
    "last_quality", "last_self_rating",
)
_REQUIRED_COLUMNS = {
    "projection_meta": {"key", "value"},
    "review_items": set(_REVIEW_COLUMNS),
    "freeze_events": {"sequence", "kind", "day"},
    "day_plans": {
        "day", "available_minutes", "knowledge_minutes", "vocab_minutes", "vocab_new_items",
        "phrase_minutes", "backlog_minutes", "notes", "version", "actor", "input_hash",
    },
    "day_plan_subject_minutes": {"day", "subject_id", "minutes"},
    "completion_events": {"event_day"},
    "availability_days": {"day", "minutes"},
    "route_phases": {
        "route_id", "revision", "phase", "label", "start", "end_exclusive",
    },
    "route_phase_review_minutes": {"phase", "subject_id", "minutes"},
}


@dataclass(frozen=True)
class SubjectStatus:
    subject_id: str
    counts: ReviewCounts


@dataclass(frozen=True)
class StatusDayPlan:
    day: date
    available_minutes: int
    knowledge_minutes: int
    vocab_minutes: int
    vocab_new_items: int
    phrase_minutes: int
    backlog_minutes: int
    notes: str
    version: int
    actor: str
    input_hash: str | None
    subject_minutes: Mapping[str, int]


@dataclass(frozen=True)
class StatusRoutePhase:
    route_id: str
    revision: int
    phase: int
    label: str
    start: date
    end_exclusive: date
    review_minutes: Mapping[str, int]


@dataclass(frozen=True)
class StatusAsOf:
    as_of: date
    subjects: tuple[SubjectStatus, ...]
    freeze: FreezeStatus
    day_plan: StatusDayPlan | None
    completion_event_exists: bool
    availability_minutes: int | None
    route_phase: StatusRoutePhase | None


def _contract(message: str, path: Path) -> ContractError:
    return ContractError(message, path.as_posix())


def _open_projection(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise _contract(f"projection file is missing; rebuild it: {path}", path)
    try:
        uri = f"{path.resolve(strict=True).as_uri()}?mode=ro"
        return sqlite3.connect(uri, uri=True)
    except (OSError, RuntimeError, sqlite3.DatabaseError) as exc:
        raise _contract(f"cannot open projection read-only; rebuild it: {exc}", path) from exc


def _table_columns(connection: sqlite3.Connection) -> dict[str, set[str]]:
    return {
        name: {row[1] for row in connection.execute(f"PRAGMA table_info({name})")}
        for name in _REQUIRED_COLUMNS
    }


def _check_schema(connection: sqlite3.Connection, path: Path) -> None:
    tables = {
        row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    if "projection_meta" not in tables:
        raise _contract("projection_meta is missing; rebuild the projection", path)
    try:
        row = connection.execute(
            "SELECT value FROM projection_meta WHERE key='projection_schema_version'"
        ).fetchone()
    except sqlite3.DatabaseError as exc:
        raise _contract(f"projection metadata is invalid; rebuild it: {exc}", path) from exc
    if row is None or row[0] != _SCHEMA_VERSION:
        got = "missing" if row is None else repr(row[0])
        raise _contract(
            f"projection schema version is {got}; rebuild with schema {_SCHEMA_VERSION}", path,
        )
    missing_tables = set(_REQUIRED_COLUMNS) - tables
    if missing_tables:
        names = ", ".join(sorted(missing_tables))
        raise _contract(f"projection tables are missing ({names}); rebuild it", path)
    columns = _table_columns(connection)
    for table, required in _REQUIRED_COLUMNS.items():
        missing = required - columns[table]
        if missing:
            names = ", ".join(sorted(missing))
            raise _contract(
                f"projection columns are missing from {table} ({names}); rebuild it", path,
            )


def _day_value(value: object, field: str, path: Path) -> date:
    if not isinstance(value, str):
        raise _contract(f"invalid date in {field}; rebuild the projection", path)
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise _contract(f"invalid date in {field}; rebuild the projection", path) from exc
    if parsed.isoformat() != value:
        raise _contract(f"invalid date in {field}; rebuild the projection", path)
    return parsed


def _review_item(row: sqlite3.Row, index: int) -> ReviewItem:
    source = "projection.review_items"
    schedule = {
        "mode": row["schedule_mode"],
        "phase": row["schedule_phase"],
        "interval_days": row["interval_days"],
        "ease_factor": row["ease_factor"],
        "repetitions": row["repetitions"],
        "lapses": row["lapses"],
    }
    if row["schedule_mode"] == "fsrs":
        schedule.update({
            "stability": row["stability"],
            "difficulty": row["difficulty"],
            "fsrs_reviewed_on": row["fsrs_reviewed_on"],
        })
    return validate_review_item({
        "review_id": row["review_id"],
        "revision": row["revision"],
        "subject_id": row["subject_id"],
        "knowledge_point_id": row["knowledge_point_id"],
        "title": row["title"],
        "granularity": row["granularity"],
        "state": row["state"],
        "estimated_minutes": row["estimated_minutes"],
        "introduced_on": row["introduced_on"],
        "due_date": row["due_date"],
        "last_reviewed_on": row["last_reviewed_on"],
        "schedule": schedule,
        "defer_count": row["defer_count"],
        "last_quality": row["last_quality"],
        "self_rating": row["last_self_rating"],
    }, index=index, source=source)


def _read_review_items(connection: sqlite3.Connection) -> tuple[ReviewItem, ...]:
    connection.row_factory = sqlite3.Row
    columns = ", ".join(_REVIEW_COLUMNS)
    rows = connection.execute(f"SELECT {columns} FROM review_items ORDER BY review_id")
    return tuple(_review_item(row, index) for index, row in enumerate(rows))


def _read_freeze_events(connection: sqlite3.Connection, path: Path) -> tuple[FreezeEvent, ...]:
    events = []
    for row in connection.execute(
        "SELECT sequence, kind, day FROM freeze_events ORDER BY sequence"
    ):
        sequence, kind, event_day = row
        if type(sequence) is not int or sequence < 1 or kind not in ("freeze", "resume"):
            raise _contract("invalid freeze event row; rebuild the projection", path)
        events.append(FreezeEvent(sequence, kind, _day_value(event_day, "freeze_events.day", path)))
    return tuple(events)


def _read_subjects(connection: sqlite3.Connection, config: KaoyanConfig,
                   items: tuple[ReviewItem, ...], day: date) -> tuple[SubjectStatus, ...]:
    counts = count_review_items_by_subject(items, day)
    return tuple(
        SubjectStatus(subject.subject_id, counts.get(subject.subject_id, ReviewCounts()))
        for subject in config.subjects
    )


def _read_day_plan(
    connection: sqlite3.Connection, day: date, path: Path,
) -> StatusDayPlan | None:
    row = connection.execute(
        "SELECT day, available_minutes, knowledge_minutes, vocab_minutes, vocab_new_items, "
        "phrase_minutes, backlog_minutes, notes, version, actor, input_hash "
        "FROM day_plans WHERE day = ?", (day.isoformat(),),
    ).fetchone()
    if row is None:
        return None
    subject_minutes = {
        subject_id: minutes for subject_id, minutes in connection.execute(
            "SELECT subject_id, minutes FROM day_plan_subject_minutes "
            "WHERE day = ? ORDER BY subject_id", (day.isoformat(),),
        )
    }
    return StatusDayPlan(
        day=_day_value(row[0], "day_plans.day", path),
        available_minutes=row[1], knowledge_minutes=row[2], vocab_minutes=row[3],
        vocab_new_items=row[4], phrase_minutes=row[5], backlog_minutes=row[6], notes=row[7],
        version=row[8], actor=row[9], input_hash=row[10],
        subject_minutes=MappingProxyType(subject_minutes),
    )


def _read_route_phase(
    connection: sqlite3.Connection, day: date, path: Path,
) -> StatusRoutePhase | None:
    rows = connection.execute(
        "SELECT route_id, revision, phase, label, start, end_exclusive FROM route_phases "
        "WHERE start <= ? AND ? < end_exclusive ORDER BY phase",
        (day.isoformat(), day.isoformat()),
    ).fetchall()
    if len(rows) > 1:
        raise _contract(
            "multiple route phases contain the requested day; rebuild the projection", path,
        )
    if not rows:
        return None
    row = rows[0]
    review_minutes = {
        subject_id: minutes for subject_id, minutes in connection.execute(
            "SELECT subject_id, minutes FROM route_phase_review_minutes "
            "WHERE phase = ? ORDER BY subject_id", (row[2],),
        )
    }
    return StatusRoutePhase(
        route_id=row[0], revision=row[1], phase=row[2], label=row[3],
        start=_day_value(row[4], "route_phases.start", path),
        end_exclusive=_day_value(row[5], "route_phases.end_exclusive", path),
        review_minutes=MappingProxyType(review_minutes),
    )


def _read_availability(connection: sqlite3.Connection, day: date) -> int | None:
    row = connection.execute(
        "SELECT minutes FROM availability_days WHERE day = ?", (day.isoformat(),),
    ).fetchone()
    return None if row is None else row[0]


def _read_snapshot(
    connection: sqlite3.Connection,
    path: Path,
    day: date,
    config: KaoyanConfig,
    policy: FreezePolicy,
) -> StatusAsOf:
    _check_schema(connection, path)
    items = _read_review_items(connection)
    validate_items_against_config(config, items)
    events = _read_freeze_events(connection, path)
    latched = latch_active(events)
    freeze = assess_freeze(day, config, items, policy, latched=latched)
    return StatusAsOf(
        as_of=day,
        subjects=_read_subjects(connection, config, items, day),
        freeze=freeze,
        day_plan=_read_day_plan(connection, day, path),
        completion_event_exists=connection.execute(
            "SELECT 1 FROM completion_events WHERE event_day = ?", (day.isoformat(),)
        ).fetchone() is not None,
        availability_minutes=_read_availability(connection, day),
        route_phase=_read_route_phase(connection, day, path),
    )


def status_as_of(
    projection_path: str | Path,
    day: date,
    config: KaoyanConfig,
    policy: FreezePolicy = FreezePolicy(),
) -> StatusAsOf:
    """Evaluate date ``day`` against the most recently rebuilt current-schema projection."""
    if isinstance(day, datetime) or not isinstance(day, date):
        raise ContractError("day must be a date", "day")
    if not isinstance(projection_path, (str, Path)) or not str(projection_path):
        raise ContractError("projection_path must be a non-empty path", "projection_path")
    if not isinstance(config, KaoyanConfig):
        raise ContractError("config must be a KaoyanConfig", "config")
    if not isinstance(policy, FreezePolicy):
        raise ContractError("policy must be a FreezePolicy", "policy")
    path = Path(projection_path)
    connection = _open_projection(path)
    try:
        with closing(connection):
            return _read_snapshot(connection, path, day, config, policy)
    except sqlite3.DatabaseError as exc:
        raise _contract(f"cannot read projection; rebuild it: {exc}", path) from exc


def _freeze_mapping(status: FreezeStatus) -> dict[str, object]:
    result: dict[str, object] = {
        "frozen": status.frozen,
        "overdue_minutes": status.overdue_minutes,
        "overdue_count": status.overdue_count,
        "threshold_minutes": status.threshold_minutes,
        "backlog_days": status.backlog_days,
        "latched": status.latched,
    }
    if status.frozen:
        result["resume"] = "ky resume"
    return result


def status_to_mapping(status: StatusAsOf) -> dict[str, object]:
    """Return the sole JSON shape for :func:`status_as_of`."""
    plan = status.day_plan
    phase = status.route_phase
    return {
        "as_of": status.as_of.isoformat(),
        "subjects": [
            {
                "subject_id": subject.subject_id,
                "in_review_queue": subject.counts.in_review_queue,
                "due_today_count": subject.counts.due_today_count,
                "due_today_minutes": subject.counts.due_today_minutes,
                "backlog_minutes": subject.counts.backlog_minutes,
            }
            for subject in status.subjects
        ],
        "freeze": _freeze_mapping(status.freeze),
        "day_plan": None if plan is None else {
            "day": plan.day.isoformat(),
            "available_minutes": plan.available_minutes,
            "knowledge_minutes": plan.knowledge_minutes,
            "vocab_minutes": plan.vocab_minutes,
            "vocab_new_items": plan.vocab_new_items,
            "phrase_minutes": plan.phrase_minutes,
            "backlog_minutes": plan.backlog_minutes,
            "notes": plan.notes,
            "version": plan.version,
            "actor": plan.actor,
            "input_hash": plan.input_hash,
            "subject_minutes": dict(plan.subject_minutes),
        },
        "completion_event_exists": status.completion_event_exists,
        "availability_minutes": status.availability_minutes,
        "route_phase": None if phase is None else {
            "route_id": phase.route_id,
            "revision": phase.revision,
            "phase": phase.phase,
            "label": phase.label,
            "start": phase.start.isoformat(),
            "end_exclusive": phase.end_exclusive.isoformat(),
            "review_minutes": dict(phase.review_minutes),
        },
    }
