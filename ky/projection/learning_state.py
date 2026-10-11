"""M15 learning-state tables; see ``contracts/learning_state_projection.md``.

Public interface: :func:`read_learning_state` and :func:`write_learning_state`.
State is consumed only through the M13 and M26 source ports.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Any, Mapping

from ky.availability.port import load_availability_with_source
from ky.freeze.port import FreezeEvent, latch_active
from ky.models import ContractError, ReviewItem
from ky.schedule.completion import CompletionEvent
from ky.schedule.longitudinal import DayPlan
from ky.schedule.planning import RoutePlan
from ky.storage.day_plan_store import DayPlanRecord, DayPlanStore
from ky.storage.review_shards import ReviewShardStore
from ky.storage.route_store import RoutePlanStore
from ky.workspace import Workspace


@dataclass(frozen=True)
class LearningState:
    review_items: tuple[ReviewItem, ...]
    day_plans: tuple[DayPlanRecord, ...]
    completions: tuple[CompletionEvent, ...]
    freeze_events: tuple[FreezeEvent, ...]
    route: RoutePlan | None
    availability: Mapping[date, int]
    state_inputs: Mapping[str, str]
    freeze_events_latched: bool


def read_learning_state(workspace: Workspace) -> LearningState:
    """Read all registered state through its public source ports exactly once."""
    queue = ReviewShardStore(workspace.write_target("state.review_queue"))
    plans = DayPlanStore(workspace.write_target("state.plans")).read_state_sources()
    queue_sources = queue.read_state_sources()
    route = None
    route_sources: Mapping[str, str] = {}
    if workspace.routes is not None:
        route_result = RoutePlanStore(workspace.write_target("state.routes")).read_state_sources()
        route = route_result.route
        route_sources = route_result.sources
    availability: Mapping[date, int] = MappingProxyType({})
    availability_sources: dict[str, str] = {}
    if workspace.availability is not None:
        path = workspace.write_target("state.availability")
        source = load_availability_with_source(path)
        availability = source.availability.days
        availability_sources[path.name] = source.sha256

    sources: dict[str, str] = {}
    _add_sources(sources, "state.review_queue", queue_sources.sources)
    _add_sources(sources, "state.plans", plans.sources)
    _add_sources(sources, "state.routes", route_sources)
    _add_sources(sources, "state.availability", availability_sources)
    return LearningState(
        review_items=queue_sources.items,
        day_plans=plans.plans,
        completions=plans.completions,
        freeze_events=plans.freeze_events,
        route=route,
        availability=availability,
        state_inputs=MappingProxyType(dict(sorted(sources.items()))),
        freeze_events_latched=latch_active(plans.freeze_events),
    )


def _add_sources(target: dict[str, str], key: str, sources: Mapping[str, str]) -> None:
    for path, digest in sources.items():
        target[f"{key}/{path}"] = digest


def _date(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _review_rows(items: tuple[ReviewItem, ...]) -> list[tuple[Any, ...]]:
    rows = []
    for item in items:
        schedule = item.schedule
        rows.append((
            item.review_id, item.revision, item.subject_id, item.knowledge_point_id,
            item.title, item.granularity, item.state, item.estimated_minutes,
            _date(item.introduced_on), _date(item.due_date), _date(item.last_reviewed_on),
            schedule.mode, schedule.phase, schedule.interval_days, schedule.ease_factor,
            schedule.repetitions, schedule.lapses, schedule.stability, schedule.difficulty,
            _date(schedule.fsrs_reviewed_on), item.defer_count, item.last_quality,
            item.last_self_rating,
        ))
    return rows


def _day_plan_rows(
    records: tuple[DayPlanRecord, ...],
) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]]]:
    plans = []
    subjects = []
    for record in records:
        plan = record.plan
        plans.append((
            _date(plan.day), plan.available_minutes, plan.knowledge_minutes,
            plan.vocab_minutes, plan.vocab_new_items, plan.phrase_minutes,
            plan.backlog_minutes, plan.notes, record.version, record.actor, record.input_hash,
        ))
        subjects.extend((plan.day.isoformat(), key, value)
                        for key, value in sorted(plan.subject_minutes.items()))
    return plans, subjects


def _completion_rows(
    events: tuple[CompletionEvent, ...],
) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]], list[tuple[Any, ...]]]:
    event_rows = []
    review_rows = []
    vocab_rows = []
    for event in events:
        event_rows.append((
            event.day.isoformat(), len(event.reviews), len(event.vocab.delivered_words),
            len(event.vocab.practiced_words),
        ))
        for ordinal, review in enumerate(event.reviews):
            review_rows.append((
                event.day.isoformat(), ordinal, review.completion_id, review.review_id,
                _date(review.completed_on), review.check, review.outcome, review.question_ref,
                review.self_rating,
            ))
        for kind, words in (("delivered", event.vocab.delivered_words),
                            ("practiced", event.vocab.practiced_words)):
            vocab_rows.extend((event.day.isoformat(), kind, ordinal, word)
                              for ordinal, word in enumerate(words))
    return event_rows, review_rows, vocab_rows


def _route_rows(route: RoutePlan | None) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]]]:
    phases = []
    minutes = []
    if route is None:
        return phases, minutes
    for phase in route.phases:
        phases.append((
            route.route_id, route.revision, phase.index, phase.label,
            phase.start.isoformat(), phase.end_exclusive.isoformat(),
        ))
        minutes.extend((phase.index, subject, value)
                       for subject, value in sorted(phase.review_minutes.items()))
    return phases, minutes


def _create_tables(con: sqlite3.Connection) -> None:
    con.execute("""CREATE TABLE review_items (
        review_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, subject_id TEXT NOT NULL,
        knowledge_point_id TEXT NOT NULL, title TEXT NOT NULL, granularity TEXT NOT NULL,
        state TEXT NOT NULL, estimated_minutes INTEGER NOT NULL, introduced_on TEXT NOT NULL,
        due_date TEXT NOT NULL, last_reviewed_on TEXT, schedule_mode TEXT NOT NULL,
        schedule_phase INTEGER NOT NULL, interval_days INTEGER NOT NULL,
        ease_factor REAL NOT NULL, repetitions INTEGER NOT NULL, lapses INTEGER NOT NULL,
        stability REAL, difficulty REAL, fsrs_reviewed_on TEXT,
        defer_count INTEGER NOT NULL, last_quality INTEGER, last_self_rating TEXT)""")
    con.execute("""CREATE TABLE day_plans (
        day TEXT PRIMARY KEY, available_minutes INTEGER NOT NULL,
        knowledge_minutes INTEGER NOT NULL,
        vocab_minutes INTEGER NOT NULL, vocab_new_items INTEGER NOT NULL,
        phrase_minutes INTEGER NOT NULL, backlog_minutes INTEGER NOT NULL, notes TEXT NOT NULL,
        version INTEGER NOT NULL, actor TEXT NOT NULL, input_hash TEXT)""")
    con.execute("""CREATE TABLE day_plan_subject_minutes (
        day TEXT NOT NULL, subject_id TEXT NOT NULL, minutes INTEGER NOT NULL,
        PRIMARY KEY (day, subject_id))""")
    con.execute("""CREATE TABLE completion_events (
        event_day TEXT PRIMARY KEY, review_count INTEGER NOT NULL,
        delivered_word_count INTEGER NOT NULL, practiced_word_count INTEGER NOT NULL)""")
    con.execute("""CREATE TABLE completion_reviews (
        event_day TEXT NOT NULL, ordinal INTEGER NOT NULL, completion_id TEXT,
        review_id TEXT NOT NULL, completed_on TEXT NOT NULL, check_method TEXT NOT NULL,
        outcome TEXT, question_ref TEXT, self_rating TEXT,
        PRIMARY KEY (event_day, ordinal))""")
    con.execute("""CREATE TABLE completion_vocab_words (
        event_day TEXT NOT NULL,
        vocab_kind TEXT NOT NULL CHECK(vocab_kind IN ('delivered','practiced')),
        ordinal INTEGER NOT NULL, word TEXT NOT NULL,
        PRIMARY KEY (event_day, vocab_kind, ordinal))""")
    con.execute("""CREATE TABLE freeze_events (
        sequence INTEGER PRIMARY KEY, kind TEXT NOT NULL, day TEXT NOT NULL)""")
    con.execute("""CREATE TABLE route_phases (
        route_id TEXT NOT NULL, revision INTEGER NOT NULL, phase INTEGER PRIMARY KEY,
        label TEXT NOT NULL, start TEXT NOT NULL, end_exclusive TEXT NOT NULL)""")
    con.execute("""CREATE TABLE route_phase_review_minutes (
        phase INTEGER NOT NULL, subject_id TEXT NOT NULL, minutes INTEGER NOT NULL,
        PRIMARY KEY (phase, subject_id))""")
    con.execute("CREATE TABLE availability_days (day TEXT PRIMARY KEY, minutes INTEGER NOT NULL)")


def write_learning_state(con: sqlite3.Connection, state: LearningState) -> None:
    """Create and fill deterministic learning-state tables from a validated snapshot."""
    _create_tables(con)
    review_rows = _review_rows(state.review_items)
    plan_rows, subject_rows = _day_plan_rows(state.day_plans)
    event_rows, completion_rows, vocab_rows = _completion_rows(state.completions)
    phase_rows, route_minutes = _route_rows(state.route)
    con.executemany("INSERT INTO review_items VALUES (" + ",".join("?" * 23) + ")",
                    sorted(review_rows))
    con.executemany("INSERT INTO day_plans VALUES (" + ",".join("?" * 11) + ")",
                    sorted(plan_rows))
    con.executemany("INSERT INTO day_plan_subject_minutes VALUES (?,?,?)", sorted(subject_rows))
    con.executemany("INSERT INTO completion_events VALUES (?,?,?,?)", sorted(event_rows))
    con.executemany("INSERT INTO completion_reviews VALUES (?,?,?,?,?,?,?,?,?)",
                    sorted(completion_rows))
    con.executemany("INSERT INTO completion_vocab_words VALUES (?,?,?,?)", sorted(vocab_rows))
    con.executemany("INSERT INTO freeze_events VALUES (?,?,?)", sorted(
        (event.sequence, event.kind, event.day.isoformat()) for event in state.freeze_events
    ))
    con.executemany("INSERT INTO route_phases VALUES (?,?,?,?,?,?)", sorted(phase_rows))
    con.executemany("INSERT INTO route_phase_review_minutes VALUES (?,?,?)", sorted(route_minutes))
    con.executemany("INSERT INTO availability_days VALUES (?,?)", sorted(
        (day.isoformat(), minutes) for day, minutes in state.availability.items()
    ))
