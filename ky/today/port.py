"""M33 today and queue view ports; see ``contracts/today.md``.

Public interfaces: ``load_today``, ``load_queue_view``, ``today_view_hash``,
``record_day``, and ``advance_recorded_day``. Queue mapping follows web v2 §8.
"""

from __future__ import annotations

import hashlib
from datetime import date
from typing import Any, Mapping, Sequence

from ky.availability import availability_for_workspace
from ky.freeze import FreezePolicy, assess_freeze, latch_active
from ky.models import ContractError, load_config, validate_items_against_config
from ky.mastery import item_level
from ky.planner.port import canonical_json_bytes
from ky.pacing.port import (
    cycle_for_date, load_pacing_report_state, settings_for_workspace,
)
from ky.schedule.budget import resolve_day_budget
from ky.schedule.completion import (
    CompletionEvent, ReviewCompletion, VocabProgress,
)
from ky.schedule.review_clip import ReviewPolicy
from ky.storage.day_plan_store import DayPlanStore, StorageError
from ky.storage.review_shards import ReviewShardStore
from ky.storage.route_store import RoutePlanStore
from ky.timetable import timetable_for_workspace
from ky.today.compute import build_review_questions, calculate_preflight
from ky.today.questions import load_review_question_sources
from ky.today.record import advance_loaded_event, record_loaded_event, record_report_mapping
from ky.workspace import Workspace


def _validate_workspace_day(workspace: object, day: object) -> tuple[Workspace, date]:
    if not isinstance(workspace, Workspace):
        raise ContractError("expected Workspace", "workspace")
    if type(day) is not date:
        raise ContractError("expected date", "day")
    return workspace, day


def today_view_hash(view: Mapping[str, Any]) -> str:
    """Hash only day and review identity fields using M19 canonical JSON bytes."""
    if not isinstance(view, Mapping):
        raise ContractError("expected a mapping", "view")
    day = view.get("date")
    reviews = view.get("reviews")
    if not isinstance(day, str) or not isinstance(reviews, (list, tuple)):
        raise ContractError("expected date and reviews", "view")
    try:
        if date.fromisoformat(day).isoformat() != day:
            raise ValueError
    except ValueError as exc:
        raise ContractError("expected YYYY-MM-DD", "date") from exc
    identity = {"date": day, "reviews": []}
    for index, item in enumerate(reviews):
        if not isinstance(item, Mapping) or not isinstance(item.get("review_id"), str):
            raise ContractError("expected review identity", f"reviews[{index}]")
        check = item.get("check") or "recall_vs_notes"
        question_ref = item.get("question_ref")
        if not isinstance(check, str) or (question_ref is not None
                                          and not isinstance(question_ref, str)):
            raise ContractError("invalid review identity", f"reviews[{index}]")
        identity["reviews"].append({
            "review_id": item["review_id"],
            "check": check, "question_ref": question_ref,
        })
    return hashlib.sha256(canonical_json_bytes(identity)).hexdigest()


def load_today(workspace: Workspace, day: date) -> Mapping[str, Any]:
    """Assemble the registered workspace's current day view (M33 §3)."""
    view, _config, _sources = _load_today_context(workspace, day)
    return view


def load_queue_view(workspace: Workspace, day: date) -> Mapping[str, Any]:
    """Assemble M9 queue buckets and summaries without loading question sources."""
    workspace, day = _validate_workspace_day(workspace, day)
    sources = _read_today_sources(workspace, day, include_question_bank=False)
    budget, preflight, clip = _calculate_today_content(workspace, day, sources)
    return _assemble_queue_view(day, sources, budget, preflight, clip)


def _load_today_context(workspace: Workspace, day: date):
    """Load the view and its validated config once for M33 record construction."""
    workspace, day = _validate_workspace_day(workspace, day)
    sources = _read_today_sources(workspace, day)
    budget, preflight, clip = _calculate_today_content(workspace, day, sources)
    selected = clip.selected
    check_sources = _read_today_question_sources(
        workspace, selected, sources["plan_state"].completions,
    )
    reviews = build_review_questions(
        workspace, selected, sources["bank_path"], sources["bank"],
        sources["plan_state"].completions, check_sources,
    )
    sources["check_sources"] = check_sources
    view = _assemble_today_view(workspace, day, sources, budget, preflight, reviews)
    view["view_hash"] = today_view_hash(view)
    return view, sources["config"], sources


def _read_today_sources(workspace: Workspace, day: date, *,
                        include_question_bank: bool = True) -> dict[str, Any]:
    """Read each registered source once and keep the parsed objects for calculation."""
    config = load_config(workspace.require("settings.exam_config"))
    queue_store = ReviewShardStore(workspace.write_target("state.review_queue"))
    queue_state = queue_store.read_state_sources()
    items = queue_state.items
    validate_items_against_config(config, items)
    plans = DayPlanStore(workspace.write_target("state.plans"))
    plan_state = plans.read_state_sources()
    route = (RoutePlanStore(workspace.write_target("state.routes")).current()
             if workspace.routes is not None else None)
    availability = availability_for_workspace(workspace)
    timetable = timetable_for_workspace(workspace)
    pacing = settings_for_workspace(workspace)
    pacing_reports = ({"missing": (), "reports": {}}
                      if pacing is None else _read_pacing_reports(
                          pacing, day, workspace.write_target("state.plans")))
    bank_path = (workspace.write_target("state.question_bank")
                 if workspace.question_bank is not None else None)
    bank = ()
    if bank_path is not None and include_question_bank:
        from ky.question_bank import load_question_bank
        bank = load_question_bank(bank_path)
    return {
        "config": config, "queue_state": queue_state, "items": items,
        "plan_state": plan_state, "plans": plans, "route": route,
        "availability": availability,
        "timetable": timetable, "pacing": pacing, "pacing_reports": pacing_reports,
        "bank_path": bank_path, "bank": bank,
    }


def _read_pacing_reports(pacing, day: date, plans_path):
    missing, reports = load_pacing_report_state(pacing, day, plans_path)
    return {"missing": missing, "reports": reports}


def _read_today_question_sources(workspace, items, completions):
    """Load only the selected M31 references, once, after preflight chooses items."""
    return load_review_question_sources(workspace, items, completions)


def _calculate_today_content(workspace: Workspace, day: date, sources: dict[str, Any]):
    """Compute schedule budget and preflight selection from the loaded M33 snapshot."""
    config = sources["config"]
    budget = resolve_day_budget(
        day, config, sources["availability"], sources["route"], sources["timetable"],
        pacing_initial=sources["pacing"],
    )
    freeze = assess_freeze(
        day, config, sources["items"], FreezePolicy(),
        latched=latch_active(sources["plan_state"].freeze_events),
    )
    selected, _, preflight = calculate_preflight(
        config, sources["items"], day, {}, ReviewPolicy(), freeze, budget,
    )
    return budget, preflight, selected


def _assemble_queue_view(day, sources, budget, preflight, clip):
    """Map the retained M9 result to the stable M33 §8 queue shape (sol 291 M2)."""
    config = sources["config"]
    names = {subject.subject_id: subject.display_name for subject in config.subjects}
    passed = _passed_past_question_ids(sources["plan_state"].completions)
    buckets = {
        name: _bucket_mapping(items)
        for name, items in (
            ("selected", clip.selected), ("deferred", clip.deferred),
            ("unschedulable", clip.unschedulable),
            ("scheduled_ahead", clip.scheduled_ahead),
            ("unreachable", clip.unreachable),
        )
    }
    selected = [_queue_item_mapping(item, day, names, passed) for item in clip.selected]
    backlog_items = clip.deferred + clip.unschedulable + clip.unreachable
    details = [_queue_item_mapping(item, day, names, passed) for item in backlog_items]
    by_subject = _queue_subject_totals(backlog_items)
    ahead = [item for item in sources["items"]
             if item.state in {"queued", "scheduled"} and item.due_date > day]
    quotas = clip.subject_review_quotas
    frozen = preflight.get("freeze") is not None
    return {
        "schema_version": 1, "date": day.isoformat(),
        "budget": {"total_minutes": budget.total_minutes,
                   "total_source": budget.total_source,
                   "base_minutes": budget.base_minutes,
                   "base_source": budget.base_source},
        "caps": {
            "soft_target_minutes": 0 if frozen else clip.soft_target_minutes,
            "hard_cap_minutes": 0 if frozen else clip.hard_cap_minutes,
            "soft_source": "freeze" if frozen else (
                "route_quota" if quotas is not None else "config_ratio"),
            "hard_source": "freeze" if frozen else "config_ratio",
            "subject_review_quotas": None if frozen or quotas is None else dict(quotas),
        },
        "freeze": preflight.get("freeze"), "queue_registered": True,
        "buckets": buckets, "selected": selected,
        "backlog": {
            "count": len(backlog_items),
            "minutes": sum(item.estimated_minutes for item in backlog_items),
            "by_subject": by_subject, "details": details[:20],
            "remaining_count": max(0, len(details) - 20),
        },
        "ahead": {
            "count": len(ahead),
            "due_dates": sorted({item.due_date.isoformat() for item in ahead})[:3],
        },
    }


def _bucket_mapping(items):
    return {"count": len(items),
            "minutes": sum(item.estimated_minutes for item in items)}


def _queue_subject_totals(items):
    totals = {}
    for item in items:
        row = totals.setdefault(item.subject_id, {"count": 0, "minutes": 0})
        row["count"] += 1
        row["minutes"] += item.estimated_minutes
    return totals


def _passed_past_question_ids(completions):
    return {review.review_id for event in completions for review in event.reviews
            if review.check == "past_question" and review.outcome == "correct"}


def _queue_item_mapping(item, day, subject_names, passed):
    return {
        "review_id": item.review_id,
        "knowledge_point_id": item.knowledge_point_id,
        "title": item.title, "subject_id": item.subject_id,
        "subject_name": subject_names[item.subject_id],
        "level": item_level(item, item.review_id in passed),
        "due_date": item.due_date.isoformat(),
        "overdue_days": item.overdue_days(day),
        "defer_count": item.defer_count, "lapses": item.schedule.lapses,
        "estimated_minutes": item.estimated_minutes,
    }


def _assemble_today_view(workspace, day, sources, budget, preflight, reviews):
    """Construct the stable public mapping from already loaded and computed values."""
    return {
        "schema_version": 1, "date": day.isoformat(),
        "budget": {"total_minutes": budget.total_minutes,
                   "total_source": budget.total_source,
                   "base_minutes": budget.base_minutes,
                   "base_source": budget.base_source},
        "timetable": _timetable_mapping(sources["timetable"], day, budget),
        "route_phase": _route_phase_mapping(sources["route"], day),
        "preflight": preflight, "reviews": reviews,
        "pacing": _pacing_mapping(sources["pacing"], day, budget,
                                  sources["pacing_reports"]),
        "recorded": _recorded_mapping(
            sources["plan_state"], sources["queue_state"].calculated_completion_ids, day,
        ),
        "availability_registered": workspace.availability is not None,
    }


def _timetable_mapping(timetable, day, budget):
    if timetable is None:
        return None
    schedule = timetable.day(day, budget.base_minutes)
    if schedule is None:
        # Outside every registered semester (holidays, looking ahead): today.md §3 null
        # (sol 279 N1).
        return None
    return {"semester": schedule.semester, "week": schedule.week,
            "weekday_used": schedule.weekday_used, "no_class": schedule.no_class,
            "blocks": schedule.blocks, "free_minutes": schedule.free_minutes}


def _route_phase_mapping(route, day):
    if route is None:
        return None
    for index, phase in enumerate(route.phases):
        if phase.start <= day < phase.end_exclusive:
            return {"index": index, "label": phase.label,
                    "review_minutes": dict(phase.review_minutes)}
    return None


def _pacing_mapping(pacing, day, budget, report_state):
    if pacing is None:
        return None
    cycle = cycle_for_date(pacing, day)
    missing_cycles = report_state["missing"]
    return {"base_minutes": budget.base_minutes, "base_source": budget.base_source,
            "next_review": None if cycle is None else cycle.end.isoformat(),
            "unreported_cycles": [item.end.isoformat() for item in missing_cycles]}


def _recorded_mapping(plan_state, calculated_completion_ids, day):
    event = next((item for item in plan_state.completions if item.day == day), None)
    if event is None:
        return None
    return {
        "reviews": [{"review_id": item.review_id, "outcome": item.outcome,
                     "check": item.check, "question_ref": item.question_ref}
                    for item in event.reviews],
        "study_minutes": event.study_minutes,
        "advanced": all(
            (item.completion_id or f"{day.isoformat()}#{index}") in calculated_completion_ids
            for index, item in enumerate(event.reviews)
        ),
    }


def record_day(workspace: Workspace, day: date, outcomes: Mapping[str, str], *,
               study_minutes: int | None, expected_view_hash: str,
               submitted_review_ids: Sequence[str] = ()) -> Mapping[str, Any]:
    """Validate and persist a single M13 completion record for a day."""
    workspace, day = _validate_workspace_day(workspace, day)
    if not isinstance(outcomes, Mapping) or any(not isinstance(k, str) for k in outcomes):
        raise ContractError("expected string-keyed mapping", "outcomes")
    if not isinstance(expected_view_hash, str):
        raise ContractError("expected a string", "expected_view_hash")
    if (not isinstance(submitted_review_ids, (list, tuple))
            or any(not isinstance(review_id, str) for review_id in submitted_review_ids)):
        raise ContractError("expected a sequence of review IDs", "submitted_review_ids")
    if type(study_minutes) is not int and study_minutes is not None:
        raise ContractError("expected a non-negative integer or null", "study_minutes")
    if study_minutes is not None and study_minutes < 0:
        raise ContractError("expected a non-negative integer or null", "study_minutes")
    view, config, sources = _load_today_context(workspace, day)
    if expected_view_hash != view["view_hash"]:
        raise ContractError("页面已过期，请刷新后再记录", "view_hash")
    if view["recorded"] is not None:
        raise ContractError("这一天已经记录过", "day")
    by_id = {item["review_id"]: item for item in view["reviews"]}
    submitted_ids = set(outcomes) | set(submitted_review_ids)
    for review_id in submitted_ids:
        if review_id not in by_id:
            raise ContractError("review_id is not in today's view", f"outcomes.{review_id}")
    for review_id, outcome in outcomes.items():
        if not isinstance(outcome, str) or outcome not in {"correct", "partial", "incorrect"}:
            raise ContractError("invalid outcome", f"outcomes.{review_id}")
    if not outcomes and study_minutes is None:
        raise ContractError("没有可记录的内容")
    completions = []
    for item in view["reviews"]:
        if item["review_id"] not in outcomes:
            continue
        completions.append(ReviewCompletion(
            item["review_id"], day, item.get("check") or "recall_vs_notes",
            outcomes[item["review_id"]], item.get("question_ref"),
            completion_id=f"{day.isoformat()}#{len(completions)}",
        ))
    event = CompletionEvent(day, tuple(completions), VocabProgress(), study_minutes)
    queue = ReviewShardStore(workspace.write_target("state.review_queue"))
    report, queue_report = record_loaded_event(
        workspace, event, config, workspace.write_target("state.plans"), queue,
        queue_state=sources["queue_state"],
        freeze_sources=(sources["items"], sources["plan_state"].freeze_events,
                        sources["plans"]),
    )
    return record_report_mapping(report, workspace, queue_report, [], None)


def advance_recorded_day(workspace: Workspace, day: date) -> Mapping[str, Any]:
    """Replay one saved completion event through M13, idempotently (M33 §4.1)."""
    workspace, day = _validate_workspace_day(workspace, day)
    store = DayPlanStore(workspace.write_target("state.plans"))
    plan_state = store.read_state_sources()
    event = next((item for item in plan_state.completions if item.day == day), None)
    if event is None:
        raise ContractError("没有这一天的完成事件", f"day.{day.isoformat()}")
    config = load_config(workspace.require("settings.exam_config"))
    queue = ReviewShardStore(workspace.write_target("state.review_queue"))
    queue_state = queue.read_state_sources()
    report = advance_loaded_event(event, config, queue, queue_state)
    calculated = set(queue_state.calculated_completion_ids)
    completed = set(report.advanced_review_ids) | set(report.replayed_review_ids)
    calculated.update(
        item.completion_id or f"{day.isoformat()}#{index}"
        for index, item in enumerate(event.reviews) if item.review_id in completed
    )
    advanced = all((item.completion_id or f"{day.isoformat()}#{index}") in calculated
                   for index, item in enumerate(event.reviews))
    return {"advanced": advanced, "advanced_review_ids": list(report.advanced_review_ids),
            "replayed_review_ids": list(report.replayed_review_ids)}
