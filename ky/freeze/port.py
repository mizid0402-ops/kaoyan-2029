"""M27 backlog freeze decision; see ``contracts/freeze.md``.

Public interface: :func:`assess_freeze` derives whether queued or scheduled overdue work
reaches the configured multi-day review capacity or has an active latch;
:func:`latch_active` resolves append-only freeze/resume records;
:func:`freeze_to_mapping` is the only frozen JSON payload shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal, Sequence

from ky.models import KaoyanConfig, ReviewItem


@dataclass(frozen=True)
class FreezePolicy:
    """Controls how many configured review-capacity days trigger a freeze."""

    backlog_days: int = 3

    def __post_init__(self) -> None:
        if type(self.backlog_days) is not int or self.backlog_days < 1:
            raise ValueError("backlog_days must be an integer >= 1")


@dataclass(frozen=True)
class FreezeStatus:
    """Derived backlog totals and the resulting freeze decision."""

    frozen: bool
    overdue_minutes: int
    overdue_count: int
    threshold_minutes: int
    backlog_days: int
    latched: bool


@dataclass(frozen=True)
class FreezeEvent:
    """One globally ordered freeze or resume record stored by M13."""

    sequence: int
    kind: Literal["freeze", "resume"]
    day: date


def unresolved_freezes(events: Sequence[FreezeEvent]) -> tuple[FreezeEvent, ...]:
    """Return freeze events with no later resume on the same or a later day."""
    return tuple(
        freeze for freeze in events
        if freeze.kind == "freeze" and not any(
            resume.kind == "resume"
            and resume.sequence > freeze.sequence
            and resume.day >= freeze.day
            for resume in events
        )
    )


def latch_active(events: Sequence[FreezeEvent]) -> bool:
    """Return whether any freeze event is still unresolved."""
    return bool(unresolved_freezes(events))


def overdue_review_items(day: date, items: Sequence[ReviewItem]) -> tuple[ReviewItem, ...]:
    """Select queued or scheduled work strictly before ``day`` (D11)."""
    return tuple(
        item for item in items
        if item.state in ("queued", "scheduled") and item.due_date < day
    )


def assess_freeze(
    day: date,
    config: KaoyanConfig,
    items: Sequence[ReviewItem],
    policy: FreezePolicy | None = None,
    *,
    latched: bool = False,
) -> FreezeStatus:
    """Return freeze status for queued or scheduled review items overdue before ``day``."""
    active_policy = policy or FreezePolicy()
    overdue = overdue_review_items(day, items)
    overdue_minutes = sum(item.estimated_minutes for item in overdue)
    threshold_minutes = (
        active_policy.backlog_days * config.review_hard_cap_minutes()
    )
    return FreezeStatus(
        # A tiny configured day can floor the hard cap to 0; without the overdue check an
        # empty backlog would then count as "reached the threshold" and freeze.
        frozen=latched or (bool(overdue) and overdue_minutes >= threshold_minutes),
        overdue_minutes=overdue_minutes,
        overdue_count=len(overdue),
        threshold_minutes=threshold_minutes,
        backlog_days=active_policy.backlog_days,
        latched=latched,
    )


def freeze_to_mapping(status: FreezeStatus) -> dict[str, object]:
    """The ``freeze`` payload shown while frozen (D11)."""
    return {
        "overdue_minutes": status.overdue_minutes,
        "overdue_count": status.overdue_count,
        "threshold_minutes": status.threshold_minutes,
        "backlog_days": status.backlog_days,
        "latched": status.latched,
        "resume": "ky resume",
    }
