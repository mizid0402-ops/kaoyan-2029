"""M33 calculations from loaded contexts; see ``contracts/today.md`` §1.

Public interfaces: ``calculate_preflight``, ``pacing_status_result``, and
``build_review_questions``.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Mapping

from ky.freeze import FreezeStatus
from ky.models import ContractError, KaoyanConfig
from ky.schedule.budget import allocate_new_content
from ky.schedule.review_clip import ReviewPolicy, preflight_to_mapping, select_daily_reviews


def calculate_preflight(
    config: KaoyanConfig, items: tuple, day: date, usage: Mapping[str, int],
    policy: ReviewPolicy, freeze: FreezeStatus, budget: Any,
) -> tuple[Any, tuple, dict[str, Any]]:
    """Calculate M9 result, allocations, and the exact ``preflight --json`` mapping."""
    clip_kwargs: dict[str, Any] = {}
    if freeze.frozen:
        clip_kwargs["daily_minutes_override"] = 0
    elif budget.total_source in {"availability", "timetable", "base"}:
        clip_kwargs["daily_minutes_override"] = budget.total_minutes
    if not freeze.frozen and budget.subject_review_quotas is not None:
        clip_kwargs["subject_review_quotas"] = budget.subject_review_quotas
    allocation_policy = (
        {"floor_policy": "drop_when_short"}
        if freeze.frozen or budget.total_source in {"availability", "timetable", "base"}
        else {}
    )
    result = select_daily_reviews(
        config, items, day, seven_day_usage=dict(usage), policy=policy, **clip_kwargs,
    )
    allocations = allocate_new_content(
        config, result.new_learning_minutes, **allocation_policy,
    )
    payload = preflight_to_mapping(config, result, allocations)
    if freeze.frozen:
        from ky.freeze import freeze_to_mapping
        payload["freeze"] = freeze_to_mapping(freeze)
    return result, allocations, payload


def pacing_status_result(settings, budget, cycle, missing) -> dict[str, Any]:
    """Build M28's status fields from already loaded context (M33 §1(c))."""
    if settings is None or budget is None:
        raise ContractError("pacing status context is incomplete", "pacing")
    return {
        "base_minutes": budget.base_minutes,
        "base_source": budget.base_source,
        "next_review": None if cycle is None else cycle.end.isoformat(),
        "unreported_cycles": [item.end.isoformat() for item in missing],
    }


def build_review_questions(
    workspace, items, bank_path, bank, completions, check_sources=None,
) -> list[dict[str, Any]]:
    """Construct M31's CLI question records from loaded review and history context."""
    from ky.question_bank import load_question_bank
    from ky.today.questions import load_review_question_sources, review_question_records

    active_bank = load_question_bank(bank_path) if bank_path is not None and bank is None else bank
    if check_sources is None:
        check_sources = load_review_question_sources(workspace, items, completions)
    return review_question_records(
        items, bank_path, active_bank, completions,
        check_sources, check_sources["outlines"],
    )
