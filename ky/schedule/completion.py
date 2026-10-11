"""M10 review progress, specified by ``contracts/review_progress.md``.

Public ports: ``ReviewAlgorithm``, ``LadderSm2Algorithm``, ``create_review_algorithm``,
``advance_review_item``, ``validate_review_completion`` and ``reset_for_relearning`` (D11).

Why this exists
----------------
``ReviewItem`` (``ky/models.py``) only ever moves forward through ``with_deferral()`` -- +1 to
``defer_count`` when a day does not get to an item. Nothing moves it forward when the item *is*
actually completed: ``due_date``, ``schedule.interval_days``, ``schedule.ease_factor`` and
``schedule.repetitions`` never advance. So the review queue is dead -- everything that gets done
still looks, to ``review_clip.select_daily_reviews``, exactly like it was never touched.

This module is that missing half. Per the user's decision (round-37 §6), it lives inside the
"AI-assigned study" surface -- the day-plan submit/completion-record pair -- rather than as its
own subsystem; ``ky.storage.day_plan_store`` is where a :class:`CompletionEvent` gets persisted.

Two things this module is careful to keep separate, because conflating them was the second gap
the audit found:

* **plan vs. actual.** A ``DayPlan`` (``ky.schedule.longitudinal``) is a proposal for what a day
  will hold; a :class:`CompletionEvent` is a record of what a day actually did. Nothing here
  reads or writes a ``DayPlan``.
* **delivered vs. practiced.** A vocabulary word being served to the learner
  (``vocab_channel.preview_batch``) is not the same fact as the learner having practiced it.
  :class:`VocabProgress` keeps ``delivered_words`` and ``practiced_words`` as two separate
  tuples; nothing here ever substitutes one for the other.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Any, Mapping, Protocol, Sequence

from ky.models import VALID_SELF_RATINGS, ReviewItem, ReviewSchedule

__all__ = [
    "CompletionError",
    "CompletionEvent",
    "ReviewCompletion",
    "ReviewAlgorithm",
    "LadderSm2Algorithm",
    "create_review_algorithm",
    "VocabProgress",
    "advance_review_item",
    "reset_for_relearning",
    "parse_completion_event",
    "validate_review_completion",
]

# A fixed_bootstrap item ladders through these gaps (days) as it clears each phase 0..4 with a
# passing quality; index i is the interval granted for clearing phase i. This is the same
# 5-step ladder VALID_SCHEDULE_MODES / _load_schedule (ky/models.py) already assumes exists
# once phase reaches 5 (sm2_lite takes over).
_BOOTSTRAP_LADDER_DAYS = (1, 2, 4, 7, 15)
_PASSING_QUALITY = 3  # SM-2 convention: quality >= 3 is a "remembered" recall.
_VALID_OUTCOMES = frozenset({"correct", "partial", "incorrect"})
_OUTCOME_CHECKS = frozenset({"past_question", "exercise", "recall_vs_notes"})


class CompletionError(ValueError):
    """Raised when a completion event is structurally or semantically invalid.

    Mirrors ``ky.models.ContractError``: ``path`` names the offending field.
    """

    def __init__(self, message: str, path: str = "") -> None:
        self.path = path
        super().__init__(f"{path}: {message}" if path else message)


@dataclass(frozen=True)
class ReviewCompletion:
    """One review item completed, with an optional anchored check and recorded self-rating."""

    review_id: str
    completed_on: date
    check: str = "none"
    outcome: str | None = None
    question_ref: str | None = None
    self_rating: str | None = None
    completion_id: str | None = None

class ReviewAlgorithm(Protocol):
    """Port for mapping completion outcomes and advancing review items."""

    def progress_quality(self, completion: ReviewCompletion) -> int | None:
        """Map a checked completion to progress quality; return ``None`` when unchecked."""

    def advance(self, item: ReviewItem, completion: ReviewCompletion) -> ReviewItem:
        """Return the next review state for one completion."""


class LadderSm2Algorithm:
    """M10 ladder and SM-2 Lite with configured unchecked self-rating policy."""

    _OUTCOME_QUALITY = {"correct": 4, "partial": 3, "incorrect": 1}

    def __init__(self, self_rating_mode: str = "strict") -> None:
        if not isinstance(self_rating_mode, str) or self_rating_mode not in {"strict", "lenient"}:
            raise CompletionError("self_rating_mode must be strict or lenient",
                                 "self_rating_mode")
        self.self_rating_mode = self_rating_mode

    def progress_quality(self, completion: ReviewCompletion) -> int | None:
        """Return this algorithm's fixed outcome mapping, or ``None`` for check=none."""
        if completion.check == "none":
            if completion.outcome is not None:
                raise CompletionError("outcome must be omitted when check is none", "outcome")
            return None
        if not isinstance(completion.check, str) or completion.check not in _OUTCOME_CHECKS:
            raise CompletionError(f"unknown check {completion.check!r}", "check")
        if (not isinstance(completion.outcome, str)
                or completion.outcome not in self._OUTCOME_QUALITY):
            raise CompletionError("outcome must be correct, partial, or incorrect", "outcome")
        return self._OUTCOME_QUALITY[completion.outcome]

    def is_late_check(self, item: ReviewItem, completion: ReviewCompletion) -> bool:
        return False

    def advance(self, item: ReviewItem, completion: ReviewCompletion) -> ReviewItem:
        quality = self.progress_quality(completion)
        if (self.self_rating_mode == "lenient" and quality is None
                and completion.self_rating in {"unknown", "vague"}):
            interval = (1 if completion.self_rating == "unknown"
                        else max(1, item.schedule.interval_days // 2))
            return _advance_review_item(item, completion, quality, interval_days=interval)
        return _advance_review_item(item, completion, quality)


@dataclass(frozen=True)
class VocabProgress:
    """A day's vocabulary progress. ``delivered`` and ``practiced`` are deliberately separate:
    every delivered word is a word the learner was *shown*, not a word they have *learned*."""

    delivered_words: tuple[str, ...] = ()
    practiced_words: tuple[str, ...] = ()


@dataclass(frozen=True)
class CompletionEvent:
    """What actually happened on ``day`` -- the "actual" half of plan vs. actual."""

    day: date
    reviews: tuple[ReviewCompletion, ...] = ()
    vocab: VocabProgress = VocabProgress()
    study_minutes: int | None = None


def advance_review_item(item: ReviewItem, completion: ReviewCompletion) -> ReviewItem:
    """Advance a review item with the default algorithm."""
    return _DEFAULT_REVIEW_ALGORITHM.advance(item, completion)


def create_review_algorithm(algorithm: str, self_rating_mode: str) -> ReviewAlgorithm:
    """Create the configured M10 implementation in one place."""
    if algorithm == "ladder":
        return LadderSm2Algorithm(self_rating_mode)
    if algorithm == "fsrs":
        from ky.schedule.fsrs_algorithm import FsrsAlgorithm

        return FsrsAlgorithm(self_rating_mode)
    raise CompletionError("algorithm must be ladder or fsrs", "review_policy.algorithm")


def reset_for_relearning(schedule: ReviewSchedule) -> ReviewSchedule:
    """Reset spacing progress without recording a failed check (D3/D11)."""
    return replace(schedule, interval_days=1, repetitions=0)


_DEFAULT_REVIEW_ALGORITHM = LadderSm2Algorithm()


def _advance_review_item(
    item: ReviewItem, completion: ReviewCompletion, quality: int | None,
    *, interval_days: int | None = None,
) -> ReviewItem:
    """Validate a completion and apply its schedule effect to an immutable review item."""
    validate_review_completion(item, completion)
    if quality is None:
        new_schedule = (replace(item.schedule, interval_days=interval_days)
                        if interval_days is not None else item.schedule)
        new_interval = interval_days or item.schedule.interval_days
    else:
        new_schedule, new_interval = _advance_checked_schedule(item.schedule, quality)

    return ReviewItem(
        review_id=item.review_id,
        revision=item.revision,
        subject_id=item.subject_id,
        knowledge_point_id=item.knowledge_point_id,
        title=item.title,
        granularity=item.granularity,
        state=item.state,
        estimated_minutes=item.estimated_minutes,
        introduced_on=item.introduced_on,
        due_date=completion.completed_on + timedelta(days=new_interval),
        last_reviewed_on=completion.completed_on,
        schedule=new_schedule,
        defer_count=item.defer_count,
        last_quality=quality,
        last_self_rating=(completion.self_rating if completion.self_rating is not None
                          else item.last_self_rating),
    )


def validate_review_completion(item: ReviewItem, completion: ReviewCompletion) -> None:
    """Validate a completion against the M10 item and completion contracts."""
    if completion.review_id != item.review_id:
        raise CompletionError(
            f"completion is for {completion.review_id!r}, not {item.review_id!r}", "review_id"
        )
    if not isinstance(completion.check, str) or (
        completion.check != "none" and completion.check not in _OUTCOME_CHECKS
    ):
        raise CompletionError(f"unknown check {completion.check!r}", "check")
    if completion.check == "none":
        if completion.outcome is not None:
            raise CompletionError("outcome must be omitted when check is none", "outcome")
    elif not isinstance(completion.outcome, str) or completion.outcome not in _VALID_OUTCOMES:
        raise CompletionError("outcome must be correct, partial, or incorrect", "outcome")
    if completion.question_ref is not None and not isinstance(completion.question_ref, str):
        raise CompletionError("question_ref must be a string", "question_ref")
    if completion.self_rating is not None and completion.self_rating not in VALID_SELF_RATINGS:
        raise CompletionError("self_rating must be one of the four supported values", "self_rating")
    if completion.completed_on < item.introduced_on:
        raise CompletionError(
            f"completed_on ({completion.completed_on}) precedes introduced_on "
            f"({item.introduced_on})",
            "completed_on",
        )


def _advance_checked_schedule(
    schedule: ReviewSchedule, quality: int
) -> tuple[ReviewSchedule, int]:
    """Apply the existing bootstrap ladder or SM-2 Lite update for anchored quality."""
    if quality < _PASSING_QUALITY:
        return ReviewSchedule(
            mode="sm2_lite" if schedule.mode == "fsrs" else schedule.mode,
            phase=5 if schedule.mode == "fsrs" else schedule.phase,
            interval_days=1,
            ease_factor=max(1.3, schedule.ease_factor - 0.2),
            repetitions=0,
            lapses=schedule.lapses + 1,
        ), 1
    if schedule.mode == "fixed_bootstrap":
        return _advance_bootstrap_schedule(schedule)

    ease_delta = 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
    new_ease = min(3.0, max(1.3, schedule.ease_factor + ease_delta))
    interval = min(180, max(1, round(schedule.interval_days * new_ease)))
    return ReviewSchedule(
        mode="sm2_lite",
        phase=5,
        interval_days=interval,
        ease_factor=new_ease,
        repetitions=schedule.repetitions + 1,
        lapses=schedule.lapses,
    ), interval


def _advance_bootstrap_schedule(schedule: ReviewSchedule) -> tuple[ReviewSchedule, int]:
    """Move one passing item through the fixed bootstrap ladder."""
    if schedule.phase >= len(_BOOTSTRAP_LADDER_DAYS) - 1:
        interval = _BOOTSTRAP_LADDER_DAYS[-1]
        return ReviewSchedule(
            mode="sm2_lite",
            phase=5,
            interval_days=interval,
            ease_factor=schedule.ease_factor,
            repetitions=schedule.repetitions + 1,
            lapses=schedule.lapses,
        ), interval

    phase = schedule.phase + 1
    interval = _BOOTSTRAP_LADDER_DAYS[phase]
    return ReviewSchedule(
        mode="fixed_bootstrap",
        phase=phase,
        interval_days=interval,
        ease_factor=schedule.ease_factor,
        repetitions=schedule.repetitions + 1,
        lapses=schedule.lapses,
    ), interval


_EVENT_KEYS = frozenset({"schema_version", "day", "reviews", "vocab", "study_minutes"})
_REVIEW_KEYS_V1 = frozenset({"review_id", "completed_on", "quality"})
_REVIEW_KEYS_V2 = frozenset({
    "review_id", "completed_on", "check", "outcome", "question_ref", "self_rating",
    "completion_id",
})
_VOCAB_KEYS = frozenset({"delivered_words", "practiced_words"})
COMPLETION_SCHEMA_VERSION = 3


def _require_mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CompletionError(f"expected a mapping, got {type(value).__name__}", path)
    return value


def _reject_unknown(node: Mapping[str, Any], allowed: frozenset[str], path: str) -> None:
    unknown = sorted(set(node) - allowed)
    if unknown:
        key = unknown[0]
        raise CompletionError(f"unknown field {key!r}", f"{path}.{key}" if path else key)


def _parse_date(value: Any, path: str) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError as exc:
            raise CompletionError(
                f"expected an ISO date (YYYY-MM-DD), got {value!r}", path
            ) from exc
    raise CompletionError(f"expected an ISO date (YYYY-MM-DD), got {type(value).__name__}", path)


def _parse_word_list(value: Any, path: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise CompletionError("expected a list of words", path)
    words: list[str] = []
    seen: set[str] = set()
    for index, entry in enumerate(value):
        if not isinstance(entry, str) or not entry.strip():
            raise CompletionError("expected a non-empty string", f"{path}[{index}]")
        if entry in seen:
            raise CompletionError(f"duplicate word {entry!r}", f"{path}[{index}]")
        seen.add(entry)
        words.append(entry)
    return tuple(words)


def _parse_review_completions(
    node: Mapping[str, Any], day: date, schema_version: int, source: str
) -> tuple[ReviewCompletion, ...]:
    raw_reviews = node.get("reviews", [])
    if not isinstance(raw_reviews, Sequence) or isinstance(raw_reviews, (str, bytes)):
        raise CompletionError("expected a list of reviews", f"{source}.reviews")
    reviews: list[ReviewCompletion] = []
    seen_completion_ids: set[str] = set()
    for index, entry in enumerate(raw_reviews):
        path = f"{source}.reviews[{index}]"
        entry_node = _require_mapping(entry, path)
        allowed = _REVIEW_KEYS_V1 if schema_version == 1 else _REVIEW_KEYS_V2
        _reject_unknown(entry_node, allowed, path)
        review_id = entry_node.get("review_id")
        if not isinstance(review_id, str) or not review_id.strip():
            raise CompletionError("expected a non-empty string", f"{path}.review_id")
        completed_on = _parse_date(entry_node.get("completed_on"), f"{path}.completed_on")
        if schema_version == 1:
            quality = entry_node.get("quality")
            if isinstance(quality, bool) or not isinstance(quality, int) or not 0 <= quality <= 5:
                raise CompletionError(
                    f"quality must be an integer 0..5, got {quality!r}", f"{path}.quality"
                )
            completion_id = f"{day}#{index}"
            if completion_id in seen_completion_ids:
                raise CompletionError("duplicate completion_id", f"{path}.completion_id")
            seen_completion_ids.add(completion_id)
            reviews.append(ReviewCompletion(
                review_id, completed_on, check="none", completion_id=completion_id
            ))
            continue
        completion = _parse_v2_review(entry_node, review_id, completed_on, path)
        completion_id = entry_node.get("completion_id")
        if completion_id is not None and (
            not isinstance(completion_id, str) or not completion_id.strip()
        ):
            raise CompletionError("expected a non-empty string", f"{path}.completion_id")
        resolved_id = completion_id or f"{day}#{index}"
        if resolved_id in seen_completion_ids:
            raise CompletionError("duplicate completion_id", f"{path}.completion_id")
        seen_completion_ids.add(resolved_id)
        reviews.append(ReviewCompletion(
            completion.review_id, completion.completed_on, completion.check,
            completion.outcome, completion.question_ref, completion.self_rating,
            resolved_id,
        ))
    return tuple(reviews)


def _parse_completion_vocab(node: Mapping[str, Any], source: str) -> VocabProgress:
    raw_vocab = node.get("vocab") or {}
    vocab_node = _require_mapping(raw_vocab, f"{source}.vocab")
    _reject_unknown(vocab_node, _VOCAB_KEYS, f"{source}.vocab")
    delivered = _parse_word_list(
        vocab_node.get("delivered_words"), f"{source}.vocab.delivered_words"
    )
    # practiced_words is deliberately NOT required to be a subset of this event's
    # delivered_words: a word can be practiced on a later day than the one it was delivered on,
    # and a single event has no view of earlier days' delivered_words. Cross-event consistency
    # (a practiced word was delivered on *some* day) is the store's job when it has the history,
    # not this pure per-event parser's.
    practiced = _parse_word_list(
        vocab_node.get("practiced_words"), f"{source}.vocab.practiced_words"
    )
    return VocabProgress(delivered, practiced)


def parse_completion_event(raw: Any, *, source: str = "<completion_event>") -> CompletionEvent:
    """Validate a parsed mapping (e.g. from ``day-plan record``'s ``--done`` YAML) into a
    :class:`CompletionEvent`. Pure validation -- no I/O, mirrors ``ky.models.validate_config``."""
    node = _require_mapping(raw, source)
    _reject_unknown(node, _EVENT_KEYS, source)
    inferred_version = 3 if "study_minutes" in node else 2
    schema_version = node.get("schema_version", inferred_version)
    if (isinstance(schema_version, bool) or not isinstance(schema_version, int)
            or schema_version not in {1, 2, COMPLETION_SCHEMA_VERSION}):
        raise CompletionError(
            f"unsupported schema_version {schema_version}", f"{source}.schema_version"
        )
    day = _parse_date(node.get("day"), f"{source}.day")
    reviews = _parse_review_completions(node, day, schema_version, source)
    vocab = _parse_completion_vocab(node, source)
    study_minutes = node.get("study_minutes")
    if "study_minutes" in node and schema_version != 3:
        raise CompletionError("study_minutes requires schema_version 3",
                              f"{source}.study_minutes")
    if schema_version == 3 and "study_minutes" not in node:
        raise CompletionError("schema_version 3 requires study_minutes",
                              f"{source}.study_minutes")
    if "study_minutes" in node and (type(study_minutes) is not int or study_minutes < 0):
        raise CompletionError("study_minutes must be a non-negative integer",
                              f"{source}.study_minutes")
    return CompletionEvent(day=day, reviews=reviews, vocab=vocab,
                           study_minutes=study_minutes)


def _parse_v2_review(
    node: Mapping[str, Any], review_id: str, completed_on: date, path: str
) -> ReviewCompletion:
    check = node.get("check")
    valid_checks = _OUTCOME_CHECKS | {"none"}
    if not isinstance(check, str) or check not in valid_checks:
        raise CompletionError("check must be past_question, exercise, recall_vs_notes, or none",
                              f"{path}.check")
    outcome = node.get("outcome")
    if check == "none" and "outcome" in node:
        raise CompletionError("outcome must be omitted when check is none", f"{path}.outcome")
    if check != "none" and (
        not isinstance(outcome, str) or outcome not in _VALID_OUTCOMES
    ):
        raise CompletionError("outcome must be correct, partial, or incorrect", f"{path}.outcome")
    question_ref = node.get("question_ref")
    if "question_ref" in node and not isinstance(question_ref, str):
        raise CompletionError("question_ref must be a string", f"{path}.question_ref")
    self_rating = node.get("self_rating")
    if "self_rating" in node and (
        not isinstance(self_rating, str) or self_rating not in VALID_SELF_RATINGS
    ):
        raise CompletionError("self_rating must be one of the four supported values",
                              f"{path}.self_rating")
    return ReviewCompletion(review_id, completed_on, check, outcome, question_ref, self_rating)
