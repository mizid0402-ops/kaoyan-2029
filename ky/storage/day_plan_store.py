"""M13 atomic storage; see ``contracts/day_plan_store.md``,
``contracts/review_progress.md``, ``contracts/state_snapshot.md``,
``contracts/planner_port.md``, ``contracts/freeze.md``, and ``contracts/state_sources.md``.

Public interface includes ``DayPlanStore.read_state_sources``,
``DayPlanStore.write_freeze_record``, ``write_resume_record``, and ``freeze_events`` for the M27
append-only freeze latch, plus completion history, day-plan writes, and their validation seams.

Atomic, versioned storage for day plans, monthly closes, and completion events.

Reuses the commit pattern already proven in ``ky.storage.review_shards``: write the new bytes to
a temp file, re-read and re-validate the *temp* file through the same contract the writer used,
``os.replace`` it into place only once that reread succeeds, and never touch an old file's bytes.
A failed write can leave an unreferenced orphan temp file (safe to ignore/garbage-collect); it can
never leave the previous manifest pointing at a half-written file.

``ReviewShardStore`` cannot be reused directly here -- it hardcodes ``ReviewItem``'s shape into
its shard/manifest format, and a ``DayPlan`` does not fit that shape. This module is the
independent store the task calls for, following the same pattern rather than sharing its code.

Stored records and durability policies
---------------------------------------
* **day plans** are versioned: resubmitting a day before it happens is normal, so a new
  ``write_day_plan`` call adds a new version file and repoints the manifest -- it never
  overwrites the previous version's bytes.
* **month closes** and **completion events** are write-once: a month's close and a day's
  completion record are historical facts once written ("不能被改分"), so a second write for the
  same month/day is rejected outright rather than silently replaced.
* **freeze and resume events** are globally sequenced write-once markers beneath ``freeze/``.
  Readers reject misplaced files or mismatched sequence, kind, and date fields.

Every write runs the record through its own validator first (``check_invariants`` for a day
plan) and rejects -- with the exact violated field -- before anything touches disk.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

from ky.availability import Availability
from ky.freeze.port import FreezeEvent
from ky.models import ContractError, ReviewItem
from ky.schedule.completion import (
    CompletionEvent,
    ReviewAlgorithm,
    ReviewCompletion,
    create_review_algorithm,
    parse_completion_event,
)
from ky.schedule.longitudinal import DayPlan, check_invariants
from ky.schedule.monthly_close import MonthClose
from ky.storage.review_shards import ReviewShardStore, upgrade_legacy_queue
from ky.storage.review_shards import WriteReport as ReviewQueueWriteReport

__all__ = [
    "DayPlanRecord",
    "DayPlanStore",
    "DayPlanStateSources",
    "ReviewQueueAdvanceReport",
    "StorageError",
    "WriteReport",
    "advance_review_queue",
    "parse_day_plan",
    "preflight_review_queue",
    "upgrade_legacy_queue",
]

_DAY_PLAN_SCHEMA_VERSION = 1
_MONTH_CLOSE_SCHEMA_VERSION = 1

_DAY_PLAN_KEYS = frozenset({
    "schema_version", "day", "available_minutes", "knowledge_minutes", "vocab_minutes",
    "vocab_new_items", "phrase_minutes", "backlog_minutes", "subject_minutes", "notes",
})
_MONTH_CLOSE_KEYS = frozenset({
    "schema_version", "year", "month", "first_day", "last_day", "days_in_month", "days_planned",
    "days_unplanned", "available_minutes", "allocated_minutes", "by_channel",
    "vocab_items_introduced", "overshoot_days", "overshoot_minutes", "unused_minutes",
    "backlog_minutes", "backlog_days", "violations", "notes",
    "actual_data_available", "days_with_completion_events", "actual_reviews_completed",
    "actual_vocab_delivered_words", "actual_vocab_practiced_words", "vocab_delivered_vs_planned",
})


class StorageError(ContractError):
    """A day-plan-store error with a precise, field-oriented path."""


@dataclass(frozen=True)
class WriteReport:
    """What a write actually did. ``version`` is ``None`` for write-once records."""

    path: str
    sha256: str
    version: int | None


@dataclass(frozen=True)
class DayPlanRecord:
    """One current plan and the provenance committed with its manifest entry."""

    plan: DayPlan
    version: int
    actor: str
    input_hash: str | None


@dataclass(frozen=True)
class DayPlanStateSources:
    """Current M13 planning facts and hashes of the exact bytes parsed for them."""

    plans: tuple[DayPlanRecord, ...]
    completions: tuple[CompletionEvent, ...]
    freeze_events: tuple[FreezeEvent, ...]
    sources: Mapping[str, str]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _yaml_bytes(value: Any) -> bytes:
    if yaml is None:  # pragma: no cover
        raise StorageError("PyYAML is required for day-plan storage")
    return yaml.safe_dump(
        value,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    ).encode("utf-8")


def _read_yaml(path: Path) -> Any:
    if not path.is_file():
        raise StorageError(f"file does not exist: {path}", path.as_posix())
    if yaml is None:  # pragma: no cover
        raise StorageError("PyYAML is required for day-plan storage", path.as_posix())
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise StorageError(f"invalid YAML: {exc}", path.as_posix()) from exc


def _yaml_from_bytes(data: bytes, path: Path) -> Any:
    """Parse bytes already read by a source enumerator without opening the file again."""
    if yaml is None:  # pragma: no cover
        raise StorageError("PyYAML is required for day-plan storage", path.as_posix())
    try:
        return yaml.safe_load(data.decode("utf-8"))
    except (UnicodeError, yaml.YAMLError) as exc:
        raise StorageError(f"invalid YAML: {exc}", path.as_posix()) from exc


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise StorageError(f"expected a mapping, got {type(value).__name__}", path)
    return value


def _unknown(node: Mapping[str, Any], allowed: frozenset[str], path: str) -> None:
    extra = sorted(set(node) - allowed)
    if extra:
        key = extra[0]
        raise StorageError(f"unknown field {key!r}", f"{path}.{key}" if path else key)


def _write_atomically(final_path: Path, data: bytes, *, reread_check) -> None:
    """Write ``data`` to a temp file next to ``final_path``, verify it via ``reread_check``,
    then ``os.replace`` it into place. Cleans up the temp file on any failure; never touches an
    existing file at ``final_path``."""
    final_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = final_path.with_name(f".{final_path.name}.{uuid.uuid4().hex}.tmp")
    committed = False
    try:
        temp_path.write_bytes(data)
        reread_check(temp_path)
        os.replace(temp_path, final_path)
        committed = True
    finally:
        if not committed:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass


def _write_once_atomically(final_path: Path, data: bytes, *, reread_check) -> None:
    """Verify a temporary record, then publish it without replacing an existing path.

    ``os.link`` fails atomically when the target exists, so two writers that picked the same
    sequence cannot overwrite each other; the loser is told to retry. No cross-process lock is
    kept for that single-user race (AGENTS.md threat model; round 124 review).
    """
    final_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = final_path.with_name(f".{final_path.name}.{uuid.uuid4().hex}.tmp")
    published = False
    try:
        temp_path.write_bytes(data)
        reread_check(temp_path)
        try:
            os.link(temp_path, final_path)
        except FileExistsError as exc:
            raise StorageError("序号已被占用，请重试", final_path.as_posix()) from exc
        except OSError as exc:
            raise StorageError(
                f"cannot publish event with a hard link: {exc}", final_path.as_posix()
            ) from exc
        published = True
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            # sol 283 M2: after link, a temp-file cleanup error cannot undo publication.
            if not published:
                raise


# --------------------------------------------------------------------------
# DayPlan <-> mapping
# --------------------------------------------------------------------------


def _day_plan_mapping(plan: DayPlan) -> dict[str, Any]:
    return {
        "schema_version": _DAY_PLAN_SCHEMA_VERSION,
        "day": plan.day.isoformat(),
        "available_minutes": plan.available_minutes,
        "knowledge_minutes": plan.knowledge_minutes,
        "vocab_minutes": plan.vocab_minutes,
        "vocab_new_items": plan.vocab_new_items,
        "phrase_minutes": plan.phrase_minutes,
        "backlog_minutes": plan.backlog_minutes,
        "subject_minutes": dict(plan.subject_minutes),
        "notes": plan.notes,
    }


def _plan_day(value: Any, path: str) -> date:
    """Accept the ``day`` of a plan as an ISO string or an unquoted YAML date.

    A hand-written ``day: 2026-09-15`` loads as a ``date`` scalar; route plans, availability
    and completion events already accept that form, so day plans do too (round 153 D2). A
    ``datetime`` is not a day and keeps the old rejection. An impossible date string used to
    escape as a ``ValueError`` traceback from ``day-plan submit``.
    """
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        raise StorageError("expected an ISO date (YYYY-MM-DD)", path)
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise StorageError(f"expected an ISO date (YYYY-MM-DD), got {value!r}", path) from exc


def _plan_int(value: Any, path: str) -> int:
    """Require an integer quantity; sign is left to ``check_invariants``.

    A string would reach ``check_invariants`` and raise ``TypeError``; a boolean or float
    would be stored as a minute count (round 153 D3).
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise StorageError(f"expected an integer, got {type(value).__name__}", path)
    return value


def _plan_quantity(node: Mapping[str, Any], name: str, path: str) -> int:
    """One optional top-level quantity; an absent field is 0, as before."""
    return _plan_int(node.get(name, 0), f"{path}.{name}")


def _plan_subject_minutes(value: Any, path: str) -> dict[str, int]:
    subject_minutes = {} if value is None else value
    if not isinstance(subject_minutes, Mapping):
        raise StorageError("expected a mapping", path)
    return {
        subject: _plan_int(minutes, f"{path}.{subject}")
        for subject, minutes in subject_minutes.items()
    }


def parse_day_plan(raw: Any, path: str) -> DayPlan:
    node = _mapping(raw, path)
    _unknown(node, _DAY_PLAN_KEYS, path)
    schema = node.get("schema_version", _DAY_PLAN_SCHEMA_VERSION)
    if schema != _DAY_PLAN_SCHEMA_VERSION:
        raise StorageError(f"unsupported schema_version {schema}", f"{path}.schema_version")
    day = _plan_day(node.get("day"), f"{path}.day")
    subject_minutes = _plan_subject_minutes(
        node.get("subject_minutes"), f"{path}.subject_minutes"
    )
    return DayPlan(
        day=day,
        available_minutes=_plan_quantity(node, "available_minutes", path),
        knowledge_minutes=_plan_quantity(node, "knowledge_minutes", path),
        vocab_minutes=_plan_quantity(node, "vocab_minutes", path),
        vocab_new_items=_plan_quantity(node, "vocab_new_items", path),
        phrase_minutes=_plan_quantity(node, "phrase_minutes", path),
        backlog_minutes=_plan_quantity(node, "backlog_minutes", path),
        subject_minutes=subject_minutes,
        notes=node.get("notes", ""),
    )


# --------------------------------------------------------------------------
# MonthClose <-> mapping
# --------------------------------------------------------------------------


def _month_close_mapping(mc: MonthClose) -> dict[str, Any]:
    return {
        "schema_version": _MONTH_CLOSE_SCHEMA_VERSION,
        "year": mc.year,
        "month": mc.month,
        "first_day": mc.first_day.isoformat(),
        "last_day": mc.last_day.isoformat(),
        "days_in_month": mc.days_in_month,
        "days_planned": mc.days_planned,
        "days_unplanned": mc.days_unplanned,
        "available_minutes": mc.available_minutes,
        "allocated_minutes": mc.allocated_minutes,
        "by_channel": dict(mc.by_channel),
        "vocab_items_introduced": mc.vocab_items_introduced,
        "overshoot_days": mc.overshoot_days,
        "overshoot_minutes": mc.overshoot_minutes,
        "unused_minutes": mc.unused_minutes,
        "backlog_minutes": mc.backlog_minutes,
        "backlog_days": mc.backlog_days,
        "actual_data_available": mc.actual_data_available,
        "days_with_completion_events": mc.days_with_completion_events,
        "actual_reviews_completed": mc.actual_reviews_completed,
        "actual_vocab_delivered_words": mc.actual_vocab_delivered_words,
        "actual_vocab_practiced_words": mc.actual_vocab_practiced_words,
        "vocab_delivered_vs_planned": mc.vocab_delivered_vs_planned,
        "violations": list(mc.violations),
        "notes": list(mc.notes),
    }


def _month_close_from_mapping(raw: Any, path: str) -> MonthClose:
    node = _mapping(raw, path)
    _unknown(node, _MONTH_CLOSE_KEYS, path)
    schema = node.get("schema_version", _MONTH_CLOSE_SCHEMA_VERSION)
    if schema != _MONTH_CLOSE_SCHEMA_VERSION:
        raise StorageError(f"unsupported schema_version {schema}", f"{path}.schema_version")
    return MonthClose(
        year=node["year"],
        month=node["month"],
        first_day=date.fromisoformat(node["first_day"]),
        last_day=date.fromisoformat(node["last_day"]),
        days_in_month=node.get("days_in_month", 0),
        days_planned=node.get("days_planned", 0),
        days_unplanned=node.get("days_unplanned", 0),
        available_minutes=node.get("available_minutes", 0),
        allocated_minutes=node.get("allocated_minutes", 0),
        by_channel=dict(node.get("by_channel") or {}),
        vocab_items_introduced=node.get("vocab_items_introduced", 0),
        overshoot_days=node.get("overshoot_days", 0),
        overshoot_minutes=node.get("overshoot_minutes", 0),
        unused_minutes=node.get("unused_minutes", 0),
        backlog_minutes=node.get("backlog_minutes", 0),
        backlog_days=node.get("backlog_days", 0),
        actual_data_available=node.get("actual_data_available", False),
        days_with_completion_events=node.get("days_with_completion_events", 0),
        actual_reviews_completed=node.get("actual_reviews_completed"),
        actual_vocab_delivered_words=node.get("actual_vocab_delivered_words"),
        actual_vocab_practiced_words=node.get("actual_vocab_practiced_words"),
        vocab_delivered_vs_planned=node.get("vocab_delivered_vs_planned"),
        violations=tuple(node.get("violations") or ()),
        notes=list(node.get("notes") or []),
    )


# --------------------------------------------------------------------------
# CompletionEvent <-> mapping
# --------------------------------------------------------------------------


def _completion_event_mapping(event: CompletionEvent) -> dict[str, Any]:
    node = {
        "schema_version": 2 if event.study_minutes is None else 3,
        "day": event.day.isoformat(),
        "reviews": [_review_completion_mapping(review) for review in event.reviews],
        "vocab": {
            "delivered_words": list(event.vocab.delivered_words),
            "practiced_words": list(event.vocab.practiced_words),
        },
    }
    if event.study_minutes is not None:
        node["study_minutes"] = event.study_minutes
    return node


def _review_completion_mapping(review: ReviewCompletion) -> dict[str, Any]:
    node: dict[str, Any] = {
        "review_id": review.review_id,
        "completed_on": review.completed_on.isoformat(),
        "check": review.check,
    }
    if review.outcome is not None:
        node["outcome"] = review.outcome
    if review.question_ref is not None:
        node["question_ref"] = review.question_ref
    if review.self_rating is not None:
        node["self_rating"] = review.self_rating
    if review.completion_id is not None:
        node["completion_id"] = review.completion_id
    return node


# --------------------------------------------------------------------------
# CompletionEvent -> ReviewShardStore (round-38: the missing half of round-37's state machine)
# --------------------------------------------------------------------------
#
# ``ky.schedule.completion.advance_review_item`` computes the next state of one ``ReviewItem``
# from one ``ReviewCompletion`` -- but a pure function that nobody calls against the real queue
# changes nothing. This is the wiring: for every ``ReviewCompletion`` in a ``CompletionEvent``,
# look the item up in a ``ReviewShardStore``, advance it, and write the whole queue back through
# the store's own atomic ``write()`` (never a bespoke write path). It fails closed: if any
# ``review_id`` named by the event has no matching item, nothing is written. A completion earlier
# than the stored date is reported out of order; an equal date with equal algorithm quality is
# replayed; an equal date with different quality is rejected before any queue write.


@dataclass(frozen=True)
class ReviewQueueAdvanceReport:
    """What advancing a review queue for one ``CompletionEvent`` actually did.

    ``replayed`` identifies stable completion records already committed. ``late`` completions
    predate the stored review date but still advance state. ``needs_check_review_ids`` marks
    unchecked basic/fluent lenient self-ratings for upstream question generation.
    """

    advanced_review_ids: tuple[str, ...]
    replayed_review_ids: tuple[str, ...]
    late_review_ids: tuple[str, ...]
    needs_check_review_ids: tuple[str, ...]
    fsrs_late_checks: tuple["FsrsLateCheck", ...]
    write_report: ReviewQueueWriteReport | None


@dataclass(frozen=True)
class FsrsLateCheck:
    """A checked completion skipped because it predates the FSRS memory clock."""

    review_id: str
    completion_id: str | None
    completed_on: date
    fsrs_reviewed_on: date


def preflight_review_queue(
    review_store: ReviewShardStore,
    event: CompletionEvent,
    *,
    source_state=None,
) -> None:
    """Check unknown queue IDs and duplicate completion IDs without writing."""
    _review_queue_plan(review_store, event, source_state=source_state)


def advance_review_queue(
    review_store: ReviewShardStore,
    event: CompletionEvent,
    *,
    algorithm: ReviewAlgorithm | None = None,
    source_state=None,
) -> ReviewQueueAdvanceReport:
    """Advance new completion records and report replays and late completions."""
    active_algorithm = algorithm or create_review_algorithm("ladder", "strict")
    current, actions = _review_queue_plan(review_store, event, source_state=source_state)
    by_id = {item.review_id: item for item in current}
    advanced: list[str] = []
    replayed: list[str] = []
    late: list[str] = []
    needs_check: list[str] = []
    fsrs_late_checks: list[FsrsLateCheck] = []

    for completion, action in actions:
        if action == "replayed":
            replayed.append(completion.review_id)
        else:
            original = by_id[completion.review_id]
            if completion.completed_on < (original.last_reviewed_on or completion.completed_on):
                late.append(completion.review_id)
            is_late_check = getattr(active_algorithm, "is_late_check", None)
            if is_late_check is not None and is_late_check(original, completion):
                assert original.schedule.fsrs_reviewed_on is not None
                fsrs_late_checks.append(FsrsLateCheck(
                    completion.review_id,
                    completion.completion_id,
                    completion.completed_on,
                    original.schedule.fsrs_reviewed_on,
                ))
            advanced_item = active_algorithm.advance(original, completion)
            if original.last_reviewed_on is not None:
                advanced_item = replace(
                    advanced_item,
                    last_reviewed_on=max(original.last_reviewed_on, completion.completed_on),
                )
            by_id[completion.review_id] = advanced_item
            advanced.append(completion.review_id)
            if (getattr(active_algorithm, "self_rating_mode", "strict") == "lenient"
                    and completion.check == "none"
                    and completion.self_rating in {"basic", "fluent", None}):
                needs_check.append(completion.review_id)

    if not advanced:
        return ReviewQueueAdvanceReport(
            (), tuple(replayed), tuple(late), tuple(needs_check),
            tuple(fsrs_late_checks), None
        )

    calculated = set(
        source_state.calculated_completion_ids if source_state is not None
        else review_store.calculated_completion_ids()
    )
    calculated.update(completion.completion_id for completion, action in actions
                      if action == "advance")
    write_report = review_store.write(
        by_id.values(), calculated_completion_ids=calculated,
        source_state=source_state,
    )
    return ReviewQueueAdvanceReport(
        tuple(advanced), tuple(replayed), tuple(late), tuple(needs_check),
        tuple(fsrs_late_checks), write_report
    )


def _review_queue_plan(
    review_store: ReviewShardStore,
    event: CompletionEvent,
    *,
    source_state=None,
) -> tuple[list[ReviewItem], list[tuple[ReviewCompletion, str]]]:
    """Classify stable completion IDs and reject queue references before writing."""
    if source_state is None:
        current = list(review_store.load()) if review_store.manifest_path.exists() else []
        schema_version = review_store.manifest_schema_version() \
            if review_store.manifest_path.exists() else None
        calculated_completion_ids = review_store.calculated_completion_ids()
    else:
        current = list(source_state.items)
        schema_version = source_state.schema_version
        calculated_completion_ids = source_state.calculated_completion_ids
    # Checked here, not only when advancing, so that `day-plan record` refuses before it writes
    # the write-once completion event (sol round 60, C2). The whole queue is refused -- not just
    # the reviewed items in this event -- because committing any fresh item would upgrade the
    # manifest and erase the fact that its older history is unproven.
    if (schema_version == 1
            and any(item.last_reviewed_on is not None for item in current)):
        raise StorageError(
            "旧版队列无已计算记录，无法保证只算一次；请先升级队列",
            "calculated_completion_ids",
        )
    by_id = {item.review_id: item for item in current}
    seen_completion_ids: set[str] = set()
    actions: list[tuple[ReviewCompletion, str]] = []

    for index, completion in enumerate(event.reviews):
        completion_id = completion.completion_id or f"{event.day}#{index}"
        if completion_id in seen_completion_ids:
            raise StorageError("duplicate completion_id in event",
                               f"reviews[{index}].completion_id")
        seen_completion_ids.add(completion_id)
        item = by_id.get(completion.review_id)
        path = f"reviews[{index}]"
        if item is None:
            raise StorageError(
                f"unknown review_id {completion.review_id!r}, not present in the review queue",
                f"{path}.review_id",
            )
        identified = replace(completion, completion_id=completion_id)
        if completion_id in calculated_completion_ids:
            actions.append((identified, "replayed"))
        else:
            actions.append((identified, "advance"))

    return current, actions


# --------------------------------------------------------------------------
# The store
# --------------------------------------------------------------------------


class DayPlanStore:
    """Read and atomically update a directory of day plans, month closes and completion events.

    ``subject_weights`` / ``max_single_item_minutes`` are the guard-rail inputs handed to
    ``check_invariants`` on every ``write_day_plan`` call -- the caller (the CLI, in practice)
    supplies them from the loaded config, the store does not invent a default for either.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        subject_weights: Mapping[str, float] | None = None,
        max_single_item_minutes: int | None = None,
        availability: Availability | None = None,
        freeze_gate: Callable[[date], None] | None = None,
    ) -> None:
        """``subject_weights`` is only consulted by :meth:`write_day_plan` (it is fed straight
        into ``check_invariants``); a store used only for month-closes / completion events may
        omit it -- it defaults to empty, which ``write_day_plan`` would then correctly reject
        with "no active subjects" rather than silently accepting a bogus placeholder weight."""
        self.root = Path(root)
        self.subject_weights = dict(subject_weights) if subject_weights is not None else {}
        self.max_single_item_minutes = max_single_item_minutes
        self.availability = availability
        self.freeze_gate = freeze_gate

    def _check_availability(self, day_plan: DayPlan) -> None:
        """Apply the registered per-day ceiling outside longitudinal invariants."""
        if self.availability is None:
            return
        maximum = self.availability.days.get(day_plan.day)
        if maximum is not None and day_plan.available_minutes > maximum:
            raise StorageError(
                f"available_minutes ({day_plan.available_minutes}) exceeds hand-entered "
                f"availability ({maximum})",
                "day_plan.available_minutes",
            )

    def _month_dir(self, year: int, month: int) -> Path:
        return self.root / f"{year:04d}-{month:02d}"

    def _day_plans_manifest_path(self, year: int, month: int) -> Path:
        return self._month_dir(year, month) / "day_plans_manifest.yaml"

    def _month_close_path(self, year: int, month: int) -> Path:
        return self._month_dir(year, month) / "month_close.yaml"

    def _completion_event_path(self, day: date) -> Path:
        return self._month_dir(day.year, day.month) / f"completion--{day.isoformat()}.yaml"

    def _event_path(self, event: FreezeEvent) -> Path:
        name = f"{event.sequence:06d}-{event.kind}--{event.day.isoformat()}.yaml"
        return self.root / "freeze" / name

    def _next_event_sequence(self) -> int:
        events = self.freeze_events()
        return max((event.sequence for event in events), default=0) + 1

    def _read_freeze_event(
        self, record_path: Path, *, verify_path: bool = True,
    ) -> FreezeEvent:
        if not record_path.is_file():
            raise StorageError(f"file does not exist: {record_path}", record_path.as_posix())
        return self._parse_freeze_event_bytes(
            record_path, record_path.read_bytes(), verify_path=verify_path
        )

    def _parse_freeze_event_bytes(
        self, record_path: Path, data: bytes, *, verify_path: bool = True,
    ) -> FreezeEvent:
        """Parse and validate one freeze event from bytes already read by its caller."""
        record = _mapping(_yaml_from_bytes(data, record_path), record_path.as_posix())
        sequence = record.get("sequence")
        kind = record.get("kind")
        day_text = record.get("day")
        try:
            record_day = date.fromisoformat(day_text)
        except (TypeError, ValueError) as exc:
            raise StorageError("expected an ISO date", f"{record_path.as_posix()}.day") from exc
        if not isinstance(day_text, str) or record_day.isoformat() != day_text:
            raise StorageError("expected an ISO date", f"{record_path.as_posix()}.day")
        payload_key = "status" if kind == "freeze" else "resume"
        if (type(record.get("schema_version")) is not int or record.get("schema_version") != 1
                or type(sequence) is not int or sequence < 1
                or kind not in ("freeze", "resume")
                or not isinstance(record.get(payload_key), Mapping)):
            raise StorageError("invalid freeze event", record_path.as_posix())
        event = FreezeEvent(sequence, kind, record_day)
        if verify_path and record_path != self._event_path(event):
            raise StorageError(
                f"event {sequence} is not at its store path", record_path.as_posix(),
            )
        return event

    def _append_freeze_event(
        self, kind: str, day: date, mapping: Mapping[str, Any],
    ) -> WriteReport:
        payload_key = "status" if kind == "freeze" else "resume"
        if not isinstance(mapping, Mapping):
            raise StorageError("expected a mapping", f"{kind}.{payload_key}")
        event = FreezeEvent(self._next_event_sequence(), kind, day)
        path = self._event_path(event)
        data = _yaml_bytes({
            "schema_version": 1, "sequence": event.sequence, "kind": event.kind,
            "day": day.isoformat(), payload_key: dict(mapping),
        })
        digest = _sha256(data)

        def _reread(temp_path: Path) -> None:
            if self._read_freeze_event(temp_path, verify_path=False) != event:
                raise StorageError("invalid freeze event", temp_path.as_posix())

        _write_once_atomically(path, data, reread_check=_reread)
        return WriteReport(path=path.as_posix(), sha256=digest, version=None)

    def write_freeze_record(
        self, day: date, status_mapping: Mapping[str, Any],
    ) -> WriteReport:
        """Append one globally sequenced freeze event with its triggering status."""
        return self._append_freeze_event("freeze", day, status_mapping)

    def write_resume_record(self, day: date, mapping: Mapping[str, Any]) -> WriteReport:
        """Append one globally sequenced resume event; R2 owns its operational meaning."""
        return self._append_freeze_event("resume", day, mapping)

    def freeze_events(self) -> tuple[FreezeEvent, ...]:
        """Read globally ordered events, rejecting malformed and misplaced records."""
        event_root = self.root / "freeze"
        if not event_root.is_dir():
            return ()
        events = [
            self._read_freeze_event(path)
            for path in sorted(event_root.rglob("*.yaml"))
        ]
        events.sort(key=lambda event: event.sequence)
        sequences = [event.sequence for event in events]
        if len(sequences) != len(set(sequences)):
            raise StorageError("duplicate freeze event sequence", event_root.as_posix())
        return tuple(events)

    def read_state_sources(self) -> DayPlanStateSources:
        """Read current plans and recorded events once, with hashes of their parsed bytes."""
        if self.root.exists() and not self.root.is_dir():
            # An existing non-directory is an invalid registered path, not an empty store
            # (sol round 136, M2).
            raise StorageError("store root is not a directory", self.root.as_posix())
        if not self.root.exists():
            return DayPlanStateSources((), (), (), MappingProxyType({}))
        files = sorted(path for path in self.root.rglob("*") if path.is_file())
        manifest_candidates = [
            path for path in files if path.name == "day_plans_manifest.yaml"
        ]
        manifest_paths = []
        for path in manifest_candidates:
            if not self._is_day_plan_manifest_path(path):
                raise StorageError("day-plan manifest is not at its store path", path.as_posix())
            manifest_paths.append(path)
        completion_paths = [
            path for path in files
            if path.name.startswith("completion--") and path.suffix == ".yaml"
        ]
        freeze_root = self.root / "freeze"
        freeze_paths = [
            path for path in files
            if path.suffix == ".yaml" and freeze_root in path.parents
        ]
        sources: dict[str, str] = {}
        plans = self._read_current_plans(manifest_paths, sources)
        completions = self._read_completion_sources(completion_paths, sources)
        events = self._read_freeze_sources(freeze_paths, sources)
        plans.sort(key=lambda item: item.plan.day)
        return DayPlanStateSources(
            tuple(plans), tuple(completions), tuple(events), MappingProxyType(sources)
        )

    def _is_day_plan_manifest_path(self, path: Path) -> bool:
        """Accept only the M13 ``<root>/<YYYY-MM>/`` manifest layout."""
        month_name = path.parent.name
        if (path.parent.parent != self.root or len(month_name) != 7
                or month_name[4] != "-" or not month_name[:4].isdigit()
                or not month_name[5:].isdigit()):
            return False
        year, month = int(month_name[:4]), int(month_name[5:])
        if not 1 <= month <= 12:
            return False
        return path == self._day_plans_manifest_path(year, month)

    def _read_current_plans(
        self, manifest_paths: list[Path], sources: dict[str, str]
    ) -> list[DayPlanRecord]:
        plans: list[DayPlanRecord] = []
        for manifest_path in manifest_paths:
            manifest_bytes = manifest_path.read_bytes()
            sources[manifest_path.relative_to(self.root).as_posix()] = _sha256(
                manifest_bytes
            )
            entries = self._parse_day_plans_manifest(manifest_bytes, manifest_path)

            month_dir = manifest_path.parent
            for date_key in sorted(entries):
                entry = entries[date_key]
                plan_path = month_dir / entry["path"]
                try:
                    plan_bytes = plan_path.read_bytes()
                except OSError as exc:
                    # A registered current version that cannot be read is invalid state,
                    # reported with its path rather than as a traceback (sol round 136, M1).
                    raise StorageError(
                        f"cannot read registered day plan: {exc}", plan_path.as_posix()
                    ) from exc
                actual_hash = _sha256(plan_bytes)
                if actual_hash != entry["sha256"]:
                    raise StorageError(
                        f"SHA-256 mismatch (manifest {entry['sha256']}, actual {actual_hash})",
                        plan_path.as_posix(),
                    )
                plan = parse_day_plan(
                    _yaml_from_bytes(plan_bytes, plan_path), plan_path.as_posix()
                )
                plans.append(DayPlanRecord(
                    plan=plan,
                    version=entry["version"],
                    actor=entry.get("actor", "unknown"),
                    input_hash=entry.get("input_hash"),
                ))
                sources[plan_path.relative_to(self.root).as_posix()] = actual_hash
        return plans

    def _parse_day_plans_manifest(
        self, data: bytes, manifest_path: Path
    ) -> dict[str, dict[str, Any]]:
        """Validate and normalize manifest entries from bytes already read once."""
        raw = _mapping(_yaml_from_bytes(data, manifest_path), manifest_path.as_posix())
        entries: dict[str, dict[str, Any]] = {}
        for entry in (raw.get("days") or []):
            normalized = dict(entry)
            normalized.setdefault("actor", "unknown")
            normalized.setdefault("input_hash", None)
            entries[entry["date"]] = normalized
        return entries

    def _read_completion_sources(
        self, event_paths: list[Path], sources: dict[str, str]
    ) -> list[CompletionEvent]:
        completions: list[CompletionEvent] = []
        for event_path in event_paths:
            event_bytes = event_path.read_bytes()
            event = parse_completion_event(
                _yaml_from_bytes(event_bytes, event_path), source=event_path.as_posix()
            )
            if event_path != self._completion_event_path(event.day):
                raise StorageError(
                    f"completion event for {event.day.isoformat()} is not at its store path",
                    event_path.as_posix(),
                )
            completions.append(event)
            sources[event_path.relative_to(self.root).as_posix()] = _sha256(event_bytes)
        completions.sort(key=lambda event: event.day)
        return completions

    def _read_freeze_sources(
        self, event_paths: list[Path], sources: dict[str, str]
    ) -> list[FreezeEvent]:
        events: list[FreezeEvent] = []
        for event_path in event_paths:
            event_bytes = event_path.read_bytes()
            event = self._parse_freeze_event_bytes(event_path, event_bytes)
            events.append(event)
            sources[event_path.relative_to(self.root).as_posix()] = _sha256(event_bytes)
        events.sort(key=lambda event: event.sequence)
        sequences = [event.sequence for event in events]
        if len(sequences) != len(set(sequences)):
            raise StorageError(
                "duplicate freeze event sequence", (self.root / "freeze").as_posix()
            )
        return events

    # -- day plans (versioned) --------------------------------------------

    def _load_day_plans_manifest(self, year: int, month: int) -> dict[str, dict[str, Any]]:
        manifest_path = self._day_plans_manifest_path(year, month)
        if not manifest_path.is_file():
            return {}
        return self._parse_day_plans_manifest(
            manifest_path.read_bytes(), manifest_path
        )

    def write_day_plan(
        self,
        day_plan: DayPlan,
        *,
        actor: str = "unknown",
        input_hash: str | None = None,
    ) -> WriteReport:
        """Validate ``day_plan`` via ``check_invariants`` and commit it, or reject with the
        exact violated field(s) and touch nothing."""
        self._check_day_plan_before_write(day_plan)
        return self._commit_day_plan(day_plan, actor=actor, input_hash=input_hash)

    def _check_day_plan_before_write(self, day_plan: DayPlan) -> None:
        result = check_invariants(
            day_plan,
            subject_weights=self.subject_weights,
            max_single_item_minutes=self.max_single_item_minutes,
        )
        if not result.ok:
            raise StorageError("; ".join(result.violations), "day_plan")
        self._check_availability(day_plan)
        if self.freeze_gate is not None:
            self.freeze_gate(day_plan.day)

    def _commit_day_plan(
        self,
        day_plan: DayPlan,
        *,
        actor: str,
        input_hash: str | None,
    ) -> WriteReport:
        year, month = day_plan.day.year, day_plan.day.month
        manifest = self._load_day_plans_manifest(year, month)
        date_key = day_plan.day.isoformat()
        previous = manifest.get(date_key)
        version = (previous["version"] + 1) if previous else 1

        data = _yaml_bytes(_day_plan_mapping(day_plan))
        digest = _sha256(data)
        rel_path = f"day_plans/{date_key}--v{version}.yaml"
        final_path = self._month_dir(year, month) / rel_path

        def _reread(temp_path: Path) -> None:
            reread = parse_day_plan(_read_yaml(temp_path), temp_path.as_posix())
            reread_result = check_invariants(
                reread, subject_weights=self.subject_weights,
                max_single_item_minutes=self.max_single_item_minutes,
            )
            if not reread_result.ok:  # pragma: no cover - defensive, mirrors the pre-write check
                raise StorageError("; ".join(reread_result.violations), "day_plan")
            self._check_availability(reread)
            if self.freeze_gate is not None:
                self.freeze_gate(reread.day)

        _write_atomically(final_path, data, reread_check=_reread)

        manifest[date_key] = {
            "date": date_key,
            "path": rel_path,
            "sha256": digest,
            "version": version,
            "actor": actor,
            "input_hash": input_hash,
        }
        manifest_payload = {
            "schema_version": 2,
            "days": [manifest[key] for key in sorted(manifest)],
        }
        manifest_data = _yaml_bytes(manifest_payload)
        _write_atomically(
            self._day_plans_manifest_path(year, month), manifest_data,
            reread_check=lambda p: _read_yaml(p),
        )
        return WriteReport(path=final_path.as_posix(), sha256=digest, version=version)

    def day_plan_provenance(
        self, day: date,
    ) -> tuple[int, str, str | None] | None:
        """Return the current plan version and its proposal source, if one exists."""
        entry = self._load_day_plans_manifest(day.year, day.month).get(day.isoformat())
        if entry is None:
            return None
        return entry["version"], entry.get("actor", "unknown"), entry.get("input_hash")

    def load_day_plan(self, day: date) -> DayPlan | None:
        manifest = self._load_day_plans_manifest(day.year, day.month)
        entry = manifest.get(day.isoformat())
        if entry is None:
            return None
        file_path = self._month_dir(day.year, day.month) / entry["path"]
        data = file_path.read_bytes()
        if _sha256(data) != entry["sha256"]:
            raise StorageError(
                f"SHA-256 mismatch (manifest {entry['sha256']}, actual {_sha256(data)})",
                file_path.as_posix(),
            )
        return parse_day_plan(_read_yaml(file_path), file_path.as_posix())

    def load_month(self, year: int, month: int) -> tuple[DayPlan, ...]:
        manifest = self._load_day_plans_manifest(year, month)
        plans = [self.load_day_plan(date.fromisoformat(key)) for key in sorted(manifest)]
        return tuple(plan for plan in plans if plan is not None)

    # -- month close (write-once) ------------------------------------------

    def write_month_close(self, month_close: MonthClose) -> WriteReport:
        path = self._month_close_path(month_close.year, month_close.month)
        if path.exists():
            raise StorageError(
                "month_close has already been written for this month and is append-only; "
                "it cannot be overwritten",
                path.as_posix(),
            )
        data = _yaml_bytes(_month_close_mapping(month_close))
        digest = _sha256(data)

        def _reread(temp_path: Path) -> None:
            _month_close_from_mapping(_read_yaml(temp_path), temp_path.as_posix())

        _write_atomically(path, data, reread_check=_reread)
        return WriteReport(path=path.as_posix(), sha256=digest, version=None)

    def load_month_close(self, year: int, month: int) -> MonthClose | None:
        path = self._month_close_path(year, month)
        if not path.is_file():
            return None
        return _month_close_from_mapping(_read_yaml(path), path.as_posix())

    # -- completion events (write-once per day) -----------------------------

    def write_completion_event(self, event: CompletionEvent) -> WriteReport:
        path = self._completion_event_path(event.day)
        if path.exists():
            raise StorageError(
                "a completion event has already been written for this day and is append-only; "
                "it cannot be overwritten",
                path.as_posix(),
            )
        data = _yaml_bytes(_completion_event_mapping(event))
        digest = _sha256(data)

        def _reread(temp_path: Path) -> None:
            parse_completion_event(_read_yaml(temp_path), source=temp_path.as_posix())

        _write_atomically(path, data, reread_check=_reread)
        return WriteReport(path=path.as_posix(), sha256=digest, version=None)

    def load_completion_event(self, day: date) -> CompletionEvent | None:
        path = self._completion_event_path(day)
        if not path.is_file():
            return None
        return parse_completion_event(_read_yaml(path), source=path.as_posix())

    def load_month_completions(self, year: int, month: int) -> tuple[CompletionEvent, ...]:
        """Every completion event recorded for this month, sorted by day.

        A month directory with no ``completion--*.yaml`` files returns ``()`` -- a real, looked-
        at "zero events", the same distinction ``close_month``'s ``completions`` parameter relies
        on to tell "no data" apart from "confirmed nothing happened".
        """
        month_dir = self._month_dir(year, month)
        if not month_dir.is_dir():
            return ()
        return tuple(
            parse_completion_event(_read_yaml(path), source=path.as_posix())
            for path in sorted(month_dir.glob("completion--*.yaml"))
        )

    def delivered_words(self) -> frozenset[str]:
        """Return the union of delivered word forms in all stored completion events.

        Only files at the path this store writes for their own ``day`` count. A
        ``completion--*.yaml`` anywhere else, or named for another day, is refused rather than
        silently counted: it would shrink the daily-word pool (sol round 86, M1).
        """
        if not self.root.is_dir():
            return frozenset()
        words: set[str] = set()
        # rglob, not "*/…": a misplaced file at the root or deeper must be refused too (sol 87).
        for event_path in sorted(self.root.rglob("completion--*.yaml")):
            event = parse_completion_event(_read_yaml(event_path), source=event_path.as_posix())
            if event_path != self._completion_event_path(event.day):
                raise StorageError(
                    f"completion event for {event.day.isoformat()} is not at its store path",
                    event_path.as_posix(),
                )
            words.update(event.vocab.delivered_words)
        return frozenset(words)
