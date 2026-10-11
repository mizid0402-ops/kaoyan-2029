"""M13 completion pipeline used by M33 and M14; see ``contracts/today.md`` §1(d).

Public interfaces: ``record_loaded_event``, ``advance_loaded_event``,
``latch_freeze_if_needed``, and ``record_report_mapping``. Inputs are already loaded by
their CLI or port adapter.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from ky.freeze import (
    FreezePolicy, FreezeStatus, assess_freeze, freeze_to_mapping, latch_active,
)
from ky.freeze.port import overdue_review_items
from ky.models import ContractError, validate_items_against_config
from ky.schedule.completion import CompletionEvent, create_review_algorithm
from ky.storage.day_plan_store import (
    DayPlanStore, StorageError, advance_review_queue,
    preflight_review_queue,
)
from ky.storage.review_shards import ReviewQueueStateSources, ReviewShardStore
from ky.workspace import Workspace


class RecordPipelineError(ContractError):
    """A pipeline failure with the last durable stage recorded."""

    def __init__(self, message: str, stage: str, path: str = "",
                 record_path: str | None = None) -> None:
        self.stage = stage
        self.record_path = record_path
        super().__init__(message, path)


def record_loaded_event(workspace: Workspace | None, event: CompletionEvent, config,
                        store_path: str | Path, review_store: ReviewShardStore | None, *,
                        advance_handler=advance_review_queue,
                        queue_state: ReviewQueueStateSources | None = None,
                        freeze_sources=None):
    """Validate then latch, append, and advance one already parsed event."""
    if review_store is not None and event.reviews:
        try:
            preflight_review_queue(review_store, event, source_state=queue_state)
        except (StorageError, OSError) as exc:
            message = getattr(exc, "message", str(exc))
            path = getattr(exc, "path", "")
            raise RecordPipelineError(message, "rejected", path) from exc
    freeze_written = False
    if workspace is not None:
        try:
            if freeze_sources is None:
                _, freeze_written = latch_freeze_if_needed(workspace, event.day, config)
            else:
                items, freeze_events, plans = freeze_sources
                _, freeze_written = _latch_freeze_from_sources(
                    event.day, config, items, freeze_events, plans,
                )
        except (StorageError, ContractError, OSError) as exc:
            stage = "freeze_written" if freeze_written else "rejected"
            message = getattr(exc, "message", str(exc))
            path = getattr(exc, "path", "")
            raise RecordPipelineError(message, stage, path) from exc
    try:
        report = DayPlanStore(store_path).write_completion_event(event)
    except (StorageError, OSError) as exc:
        stage = "freeze_written" if freeze_written else "rejected"
        message = getattr(exc, "message", str(exc))
        path = getattr(exc, "path", "")
        raise RecordPipelineError(message, stage, path) from exc
    queue_report = None
    if review_store is not None and event.reviews:
        try:
            queue_report = advance_handler(
                review_store, event,
                algorithm=create_review_algorithm(
                    config.review_policy.algorithm, config.review_policy.self_rating_mode,
                ),
                source_state=queue_state,
            )
        except (ContractError, StorageError, OSError) as exc:
            message = getattr(exc, "message", str(exc))
            path = getattr(exc, "path", "")
            raise RecordPipelineError(message, "event_written", path,
                                      report.path) from exc
    return report, queue_report


def advance_loaded_event(event: CompletionEvent, config, review_store: ReviewShardStore,
                         queue_state: ReviewQueueStateSources | None = None):
    """Advance a loaded event through the shared M13 review-queue pipeline."""
    return advance_review_queue(
        review_store, event,
        algorithm=create_review_algorithm(
            config.review_policy.algorithm, config.review_policy.self_rating_mode,
        ),
        source_state=queue_state,
    )


def record_report_mapping(
    report, workspace, queue_report, candidates, skip_reason,
) -> dict[str, Any]:
    """Create the existing day-plan record JSON shape from its loaded results."""
    payload = {
        "path": str(report.path), "sha256": report.sha256,
        "review_queue": None if queue_report is None else {
            "advanced_review_ids": list(queue_report.advanced_review_ids),
            "replayed_review_ids": list(queue_report.replayed_review_ids),
            "late_review_ids": list(queue_report.late_review_ids),
            "needs_check_review_ids": list(queue_report.needs_check_review_ids),
        },
        "check_question_candidates": candidates,
    }
    if queue_report is not None and queue_report.fsrs_late_checks:
        payload["review_queue"]["fsrs_late_checks"] = [
            {"review_id": late.review_id, "completion_id": late.completion_id,
             "completed_on": late.completed_on.isoformat(),
             "fsrs_reviewed_on": late.fsrs_reviewed_on.isoformat()}
            for late in queue_report.fsrs_late_checks
        ]
    if workspace is None:
        payload["freeze_latch_warning"] = (
            "未找到可用的工作区注册表，未检查冻结锁存"
        )
    if skip_reason is not None:
        payload["check_question_suggestions_skipped"] = skip_reason
    return payload


def latch_freeze_if_needed(workspace: Workspace, day, config) -> tuple[FreezeStatus, bool]:
    """Persist a newly reached threshold before a mutating action proceeds (D11/B5).

    Returns the status after any write and whether a freeze event was written; shared by
    ``day-plan submit`` / ``record`` and M33 so the latch exists once.
    """
    queue = ReviewShardStore(workspace.write_target("state.review_queue"))
    queue_state = queue.read_state_sources()
    plans = DayPlanStore(workspace.write_target("state.plans"))
    state = plans.read_state_sources()
    return _latch_freeze_from_sources(
        day, config, queue_state.items, state.freeze_events, plans,
    )


def _latch_freeze_from_sources(day, config, items, freeze_events, plans: DayPlanStore):
    """Latch M27 from the M33 snapshot, so record does not reopen source files."""
    status = assess_freeze(
        day, config, items, FreezePolicy(), latched=latch_active(freeze_events),
    )
    if not status.frozen or status.latched:
        return status, False
    validate_items_against_config(config, overdue_review_items(day, items))
    plans.write_freeze_record(day, {**freeze_to_mapping(status), "latched": True})
    return replace(status, latched=True), True
