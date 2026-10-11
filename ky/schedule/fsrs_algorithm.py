"""M10 FSRS implementation; see ``contracts/review_progress.md`` §FSRS 算法.

Public port: ``FsrsAlgorithm`` implements ``ReviewAlgorithm`` for configured FSRS queues.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, time, timedelta, timezone

from fsrs import Card, Rating, Scheduler, State

from ky.models import ReviewItem, ReviewSchedule
from ky.schedule.completion import (
    CompletionError,
    ReviewCompletion,
    validate_review_completion,
)

__all__ = ["FsrsAlgorithm"]

_RATINGS = {"correct": Rating.Good, "partial": Rating.Hard, "incorrect": Rating.Again}
_QUALITY = {"correct": 4, "partial": 3, "incorrect": 1}


class FsrsAlgorithm:
    """M10 FSRS scheduler with deterministic UTC-day reviews and D9 handling."""

    def __init__(self, self_rating_mode: str = "strict") -> None:
        if not isinstance(self_rating_mode, str) or self_rating_mode not in {
            "strict", "lenient"
        }:
            raise CompletionError("self_rating_mode must be strict or lenient",
                                  "self_rating_mode")
        self.self_rating_mode = self_rating_mode
        self.scheduler = Scheduler(
            desired_retention=0.9,
            learning_steps=(),
            relearning_steps=(),
            maximum_interval=180,
            enable_fuzzing=False,
        )

    def progress_quality(self, completion: ReviewCompletion) -> int | None:
        if completion.check == "none":
            if completion.outcome is not None:
                raise CompletionError("outcome must be omitted when check is none", "outcome")
            return None
        if not isinstance(completion.check, str) or completion.check not in {
            "past_question", "exercise", "recall_vs_notes"
        }:
            raise CompletionError(f"unknown check {completion.check!r}", "check")
        if not isinstance(completion.outcome, str) or completion.outcome not in _QUALITY:
            raise CompletionError("outcome must be correct, partial, or incorrect", "outcome")
        return _QUALITY[completion.outcome]

    def is_late_check(self, item: ReviewItem, completion: ReviewCompletion) -> bool:
        return (
            item.schedule.mode == "fsrs"
            and completion.check != "none"
            and completion.completed_on < item.schedule.fsrs_reviewed_on
        )

    def advance(self, item: ReviewItem, completion: ReviewCompletion) -> ReviewItem:
        validate_review_completion(item, completion)
        quality = self.progress_quality(completion)
        if quality is None:
            interval = self._unchecked_interval(item, completion)
            next_interval = interval if interval is not None else item.schedule.interval_days
            next_schedule = (replace(item.schedule, interval_days=interval)
                             if interval is not None else item.schedule)
            return replace(
                item,
                due_date=completion.completed_on + timedelta(days=next_interval),
                last_reviewed_on=completion.completed_on,
                schedule=next_schedule,
                last_quality=None,
                last_self_rating=(completion.self_rating if completion.self_rating is not None
                                  else item.last_self_rating),
            )
        if self.is_late_check(item, completion):
            return replace(
                item,
                last_reviewed_on=completion.completed_on,
                last_quality=quality,
                last_self_rating=(completion.self_rating if completion.self_rating is not None
                                  else item.last_self_rating),
            )
        return self._advance_checked(item, completion)

    def _unchecked_interval(
        self, item: ReviewItem, completion: ReviewCompletion
    ) -> int | None:
        if self.self_rating_mode != "lenient" or completion.self_rating is None:
            return None
        if completion.self_rating == "unknown":
            return 1
        if completion.self_rating == "vague":
            return max(1, item.schedule.interval_days // 2)
        return None

    def _advance_checked(
        self, item: ReviewItem, completion: ReviewCompletion
    ) -> ReviewItem:
        schedule = item.schedule
        review_time = datetime.combine(completion.completed_on, time.min, timezone.utc)
        if schedule.mode == "fsrs":
            card = Card(
                card_id=1,
                state=State.Review,
                stability=schedule.stability,
                difficulty=schedule.difficulty,
                due=review_time,
                last_review=datetime.combine(
                    schedule.fsrs_reviewed_on, time.min, timezone.utc
                ),
            )
        else:
            card = Card(card_id=1)
        next_card, _ = self.scheduler.review_card(
            card, _RATINGS[completion.outcome], review_datetime=review_time
        )
        due_day = next_card.due.astimezone(timezone.utc).date()
        interval = max(1, (due_day - completion.completed_on).days)
        next_schedule = ReviewSchedule(
            mode="fsrs",
            phase=5,
            interval_days=interval,
            ease_factor=schedule.ease_factor,
            repetitions=schedule.repetitions + 1,
            lapses=schedule.lapses + (completion.outcome == "incorrect"),
            stability=next_card.stability,
            difficulty=next_card.difficulty,
            fsrs_reviewed_on=completion.completed_on,
        )
        return replace(
            item,
            due_date=completion.completed_on + timedelta(days=interval),
            last_reviewed_on=completion.completed_on,
            schedule=next_schedule,
            last_quality=_QUALITY[completion.outcome],
            last_self_rating=(completion.self_rating if completion.self_rating is not None
                              else item.last_self_rating),
        )
