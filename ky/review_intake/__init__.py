"""M32 review intake port from ``contracts/review_intake.md``.

Public interfaces are :func:`new_review_items` and
:data:`DEFAULT_REVIEW_MINUTES`. The port validates completed knowledge points
and builds queued review items without reading or writing workspace state.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from datetime import date, datetime, timedelta

from ky.knowledge import KnowledgePoint, learnable_tree
from ky.models import (
    ContractError,
    MAX_SINGLE_PASS_MINUTES,
    ReviewItem,
    validate_review_item,
)

DEFAULT_REVIEW_MINUTES = 5

__all__ = ["DEFAULT_REVIEW_MINUTES", "new_review_items"]


def new_review_items(
    points: Sequence[KnowledgePoint],
    grammar: str,
    existing_items: Sequence[ReviewItem],
    knowledge_point_ids: Sequence[str] | None = None,
    leaves_under: str | None = None,
    day: date | None = None,
    minutes: int = DEFAULT_REVIEW_MINUTES,
) -> tuple[tuple[ReviewItem, ...], tuple[tuple[str, str], ...]]:
    """Build validated review items and report queued leaves that were skipped.

    ``knowledge_point_ids`` selects explicit nodes; ``leaves_under`` selects
    strict descendant learnable leaves. The second return value contains
    ``(knowledge_point_id, review_id)`` pairs for already queued leaves.
    """
    if knowledge_point_ids is not None and leaves_under is not None:
        raise ContractError("choose knowledge_point_ids or leaves_under, not both")
    if knowledge_point_ids is None and leaves_under is None:
        raise ContractError("a knowledge point selection is required")
    if knowledge_point_ids is not None:
        if (not isinstance(knowledge_point_ids, Sequence)
                or isinstance(knowledge_point_ids, (str, bytes))):
            raise ContractError("knowledge_point_ids must be a sequence", "--knowledge-point")
        if any(not isinstance(point_id, str) or not point_id for point_id in knowledge_point_ids):
            raise ContractError(
                "knowledge point IDs must be non-empty strings", "--knowledge-point"
            )
    if leaves_under is not None and (not isinstance(leaves_under, str) or not leaves_under):
        raise ContractError("leaves_under must be a non-empty string", "--leaves-under")
    if not isinstance(day, date) or isinstance(day, datetime):
        raise ContractError("day must be a date", "--date")
    if isinstance(minutes, bool) or not isinstance(minutes, int):
        raise ContractError("minutes must be an integer", "--minutes")
    if minutes < 1 or minutes > MAX_SINGLE_PASS_MINUTES:
        raise ContractError(
            f"minutes must be between 1 and {MAX_SINGLE_PASS_MINUTES}", "--minutes"
        )
    if not isinstance(existing_items, Sequence):
        raise ContractError("existing_items must be a sequence")
    if any(not isinstance(item, ReviewItem) for item in existing_items):
        raise ContractError("existing_items must contain ReviewItem values")

    try:
        outline = learnable_tree(points, grammar)
    except (TypeError, ValueError) as exc:
        raise ContractError(str(exc), "knowledge_tree") from exc

    requested = _selected_ids(outline, knowledge_point_ids, leaves_under)
    occupied_ids = {item.review_id for item in existing_items}
    queued_by_point = {
        item.knowledge_point_id: item
        for item in existing_items
        if item.state in {"queued", "scheduled"}
    }
    created: list[ReviewItem] = []
    skipped: list[tuple[str, str]] = []
    batch_ids: set[str] = set()

    for point_id in requested:
        point = outline.points_by_id.get(point_id)
        if point is None:
            raise ContractError("knowledge point is not in the effective tree", point_id)
        if point_id in outline.trackers:
            raise ContractError("knowledge point is a tracker, not learnable", point_id)
        prior = queued_by_point.get(point_id)
        if prior is not None:
            if leaves_under is None:
                raise ContractError(
                    f"knowledge point is already in the review queue as {prior.review_id}",
                    point_id,
                )
            skipped.append((point_id, prior.review_id))
            continue

        review_id = _available_review_id(point_id, occupied_ids | batch_ids)
        try:
            due_date = day + timedelta(days=1)
        except OverflowError as exc:
            raise ContractError("day cannot be advanced by one day", "--date") from exc
        item = validate_review_item(
            {
                "review_id": review_id,
                "revision": 1,
                "subject_id": point_id.split(".", 1)[0],
                "knowledge_point_id": point_id,
                "title": point.title,
                "granularity": "concept",
                "state": "queued",
                "estimated_minutes": minutes,
                "introduced_on": day,
                "due_date": due_date,
                "last_reviewed_on": None,
                "last_quality": None,
                "self_rating": None,
                "schedule": {
                    "mode": "fixed_bootstrap",
                    "phase": 0,
                    "interval_days": 1,
                    "ease_factor": 2.5,
                    "repetitions": 0,
                    "lapses": 0,
                },
                "defer_count": 0,
            }
        )
        created.append(item)
        batch_ids.add(review_id)

    return tuple(created), tuple(skipped)


def _selected_ids(outline, knowledge_point_ids, leaves_under) -> tuple[str, ...]:
    if knowledge_point_ids is not None:
        return tuple(knowledge_point_ids)
    if leaves_under not in outline.points_by_id:
        raise ContractError("parent knowledge point is not in the effective tree", leaves_under)

    selected: list[str] = []
    for candidate in outline.leaves:
        parent = outline.parents[candidate]
        while parent is not None and parent != leaves_under:
            parent = outline.parents.get(parent)
        if parent == leaves_under:
            selected.append(candidate)
    return tuple(selected)


def _available_review_id(point_id: str, occupied: Collection[str]) -> str:
    base = f"rv-{point_id}"
    if base not in occupied:
        return base
    suffix = 2
    while f"{base}-{suffix}" in occupied:
        suffix += 1
    return f"{base}-{suffix}"
