"""M12 read-only state snapshot; see ``contracts/state_snapshot.md``.

Public JSON interface: ``snapshot_to_mapping`` supplies the sole mapping shape used by the CLI
and M19 planner input. This module provides today's dashboard, not today's plan.

This module answers "where do things stand right now", never "what should happen today". It
belongs to the ①read category of the three-function boundary (read / verify / write, no fourth
kind): it opens files read-only, computes counts, and returns an immutable snapshot. It never
writes, never proposes a daily budget, a vocabulary count, or a subject split, and it is not
called ``suggest_*`` / ``recommend_*`` / ``default_*`` / ``optimal_*`` for exactly that reason.

Why every knowledge-tree number carries ``tree_status``
---------------------------------------------------------
As of this round, all three committed knowledge trees (math1/eng1/cs408) are entirely at
``status="extracted"`` -- none has reached ``approved`` -- and the knowledge-point contract
(``ky/knowledge/knowledge_point.py`` / ``eligible_for_frequency``) is explicit that ``extracted``
content must not feed frequency statistics, syllabus coverage, or a capability profile. "How much
is left / how much has been studied" is semantically adjacent to coverage, so a bare item count
here would risk being read as an authoritative coverage figure it has not earned. Every count
this module derives from a tree is therefore wrapped in :class:`TreeCount`, which always carries
the ``tree_status`` label describing what it actually counted (e.g. ``"extracted"``, or
``"extracted+approved"`` for a mixed tree) -- honest labelling, not a verdict on whether the
number may be used for something else.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, Sequence

from ky.knowledge import load_knowledge_points
from ky.freeze.port import overdue_review_items
from ky.models import ContractError, KaoyanConfig, ReviewItem
from ky.storage.day_plan_store import DayPlanStore
from ky.workspace import Workspace

__all__ = [
    "SubjectSnapshot",
    "StateSnapshot",
    "TreeCount",
    "VocabSnapshot",
    "ReviewCounts",
    "build_snapshot",
    "count_review_items_by_subject",
    "snapshot_to_mapping",
]


@dataclass(frozen=True)
class TreeCount:
    """A count derived from a knowledge tree, honestly labelled with the status(es) it covers.

    ``tree_status`` is never a single hardcoded value: it is computed from the actual points
    counted, so a tree that is still 100% ``extracted`` reports that plainly, and a partially
    reviewed tree reports ``"extracted+approved"`` rather than picking one label to display.
    """

    count: int
    tree_status: str


@dataclass(frozen=True)
class SubjectSnapshot:
    """One subject's dashboard row. Nothing here is a recommendation for today.

    ``tree_total`` is ``None`` when no knowledge-tree file is committed for this subject --
    absence is reported as ``None``, never padded with a fabricated zero.
    """

    subject_id: str
    tree_total: TreeCount | None
    in_review_queue: int
    due_today_count: int
    due_today_minutes: int
    backlog_minutes: int


@dataclass(frozen=True)
class ReviewCounts:
    """Queue counts for one subject and one caller-supplied date."""

    in_review_queue: int = 0
    due_today_count: int = 0
    due_today_minutes: int = 0
    backlog_minutes: int = 0


def count_review_items_by_subject(
    items: Sequence[ReviewItem], day: date,
) -> Mapping[str, ReviewCounts]:
    """Count queue, due-today, and M27 overdue backlog minutes for each subject."""
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
        raise ContractError("items must be a sequence of ReviewItem", "items")
    if isinstance(day, datetime) or not isinstance(day, date):
        raise ContractError("day must be a date", "day")
    totals: dict[str, list[int]] = {}
    for index, item in enumerate(items):
        if not isinstance(item, ReviewItem):
            raise ContractError("expected a ReviewItem", f"items[{index}]")
        counts = totals.setdefault(item.subject_id, [0, 0, 0, 0])
        if item.state in ("queued", "scheduled"):
            counts[0] += 1
        if item.state == "queued" and item.due_date == day:
            counts[1] += 1
            counts[2] += item.estimated_minutes
    for item in overdue_review_items(day, items):
        totals[item.subject_id][3] += item.estimated_minutes
    return MappingProxyType({
        subject_id: ReviewCounts(*counts)
        for subject_id, counts in sorted(totals.items())
    })


@dataclass(frozen=True)
class VocabSnapshot:
    """English-1 counts; delivered comes from M13 and remaining from the reference database."""

    delivered: int
    remaining: int


@dataclass(frozen=True)
class StateSnapshot:
    as_of: date
    days_to_exam: int | None
    subjects: tuple[SubjectSnapshot, ...]
    vocab: VocabSnapshot | None

    def subject(self, subject_id: str) -> SubjectSnapshot:
        for snapshot in self.subjects:
            if snapshot.subject_id == subject_id:
                return snapshot
        raise KeyError(subject_id)


def snapshot_to_mapping(snapshot: StateSnapshot) -> dict[str, object]:
    """Return the stable JSON mapping shared by the CLI and planner input port."""
    return {
        "as_of": snapshot.as_of.isoformat(),
        "days_to_exam": snapshot.days_to_exam,
        "subjects": [
            {
                "subject_id": subject.subject_id,
                "tree_total": (
                    {
                        "count": subject.tree_total.count,
                        "tree_status": subject.tree_total.tree_status,
                    }
                    if subject.tree_total is not None else None
                ),
                "in_review_queue": subject.in_review_queue,
                "due_today_count": subject.due_today_count,
                "due_today_minutes": subject.due_today_minutes,
                "backlog_minutes": subject.backlog_minutes,
            }
            for subject in snapshot.subjects
        ],
        "vocab": (
            {"delivered": snapshot.vocab.delivered, "remaining": snapshot.vocab.remaining}
            if snapshot.vocab is not None else None
        ),
    }


def _tree_status_label(statuses: Mapping[str, int]) -> str:
    if not statuses:
        return "empty"
    return "+".join(sorted(statuses))


def _tree_total(tree_path: Path) -> TreeCount:
    points = load_knowledge_points(tree_path)
    statuses: dict[str, int] = {}
    for point in points:
        statuses[point.status] = statuses.get(point.status, 0) + 1
    return TreeCount(count=len(points), tree_status=_tree_status_label(statuses))


def _vocab_snapshot(
    db: Path,
    delivered: frozenset[str] = frozenset(),
) -> VocabSnapshot | None:
    if not db.is_file():
        return None
    from ky.schedule.vocab_channel import remaining_pool

    remaining = remaining_pool(db=db, delivered=delivered)
    return VocabSnapshot(delivered=len(delivered), remaining=remaining)


def _validate_snapshot_sources(
    config: KaoyanConfig,
    tree_paths: Mapping[str, Path] | None,
    vocab_db: Path | None,
    workspace: Workspace | None,
) -> None:
    if tree_paths is None and vocab_db is None and workspace is None:
        raise ContractError(
            "provide tree_paths and/or vocab_db explicitly, or provide workspace",
            "workspace",
        )
    if workspace is not None:
        for index, subject in enumerate(config.subjects):
            if subject.subject_id not in workspace.subjects:
                raise ContractError(
                    f"subject_id {subject.subject_id!r} is not declared in workspace.subjects",
                    f"subjects[{index}].subject_id",
                )


def _snapshot_subject(
    subject_id: str,
    counts: ReviewCounts,
    tree_paths: Mapping[str, Path] | None,
    workspace: Workspace | None,
) -> SubjectSnapshot:
    if tree_paths is not None:
        # An explicit mapping replaces the workspace tree registry for this call.
        tree_path = tree_paths.get(subject_id)
        tree_total = (
            _tree_total(tree_path)
            if tree_path is not None and tree_path.is_file()
            else None
        )
    elif workspace is not None and subject_id in workspace.knowledge_trees:
        tree_path = workspace.require(f"reference.knowledge_trees.{subject_id}")
        tree_total = _tree_total(tree_path)
    else:
        tree_total = None
    return SubjectSnapshot(
        subject_id=subject_id,
        tree_total=tree_total,
        in_review_queue=counts.in_review_queue,
        due_today_count=counts.due_today_count,
        due_today_minutes=counts.due_today_minutes,
        backlog_minutes=counts.backlog_minutes,
    )


def _snapshot_subjects(
    config: KaoyanConfig,
    items: tuple[ReviewItem, ...],
    today: date,
    tree_paths: Mapping[str, Path] | None,
    workspace: Workspace | None,
) -> list[SubjectSnapshot]:
    review_counts = count_review_items_by_subject(items, today)
    return [
        _snapshot_subject(
            subject.subject_id,
            review_counts.get(subject.subject_id, ReviewCounts()),
            tree_paths,
            workspace,
        )
        for subject in config.subjects
    ]


def _snapshot_vocabulary(
    vocab_db: Path | None, workspace: Workspace | None
) -> VocabSnapshot | None:
    vocabulary_enabled = workspace is None or any(
        "vocabulary" in profile.features
        for profile in workspace.subject_profiles.values()
    )
    if not vocabulary_enabled:
        return None
    if vocab_db is not None:
        delivered = DayPlanStore(workspace.plans).delivered_words() if workspace else frozenset()
        return _vocab_snapshot(vocab_db, delivered)
    if workspace is not None:
        delivered = DayPlanStore(workspace.plans).delivered_words()
        return _vocab_snapshot(workspace.require("reference.vocabulary_db"), delivered)
    return None


def build_snapshot(
    config: KaoyanConfig,
    items: tuple[ReviewItem, ...],
    *,
    today: date,
    tree_paths: Mapping[str, Path] | None = None,
    target_exam_date: date | None = None,
    vocab_db: Path | None = None,
    workspace: Workspace | None = None,
) -> StateSnapshot:
    """Build today's read-only dashboard. Writes nothing, decides nothing.

    Data sources are supplied by the caller. Per source, an explicit ``tree_paths`` mapping or
    ``vocab_db`` overrides the corresponding workspace registry entry. If neither explicit
    source nor ``workspace`` is supplied, this function raises ``ContractError`` and never
    discovers a registry itself. If only one source is explicitly supplied without a workspace,
    the other source is omitted.

    With a workspace, every config subject must be listed in ``workspace.subjects``. A subject
    with no registered tree is valid and has ``tree_total=None``. A registered tree that is
    missing, has the wrong type, or resolves outside the workspace raises ``ContractError`` via
    ``workspace.require``. A registered vocabulary database has the same strict missing/type/
    containment behavior. A missing file passed explicitly as ``vocab_db`` retains the legacy
    override behavior and yields ``vocab=None``.

    ``items`` is whatever review queue the caller already loaded (e.g. via
    ``ky.storage.review_shards``) -- this function does not load it itself, so it stays a pure
    read over data the caller already has in hand.
    """
    _validate_snapshot_sources(config, tree_paths, vocab_db, workspace)
    subjects = _snapshot_subjects(config, items, today, tree_paths, workspace)
    days_to_exam = (target_exam_date - today).days if target_exam_date is not None else None
    vocab = _snapshot_vocabulary(vocab_db, workspace)
    return StateSnapshot(
        as_of=today,
        days_to_exam=days_to_exam,
        subjects=tuple(subjects),
        vocab=vocab,
    )
