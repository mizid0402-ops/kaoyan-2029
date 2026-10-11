"""Regression locks for the review-progress state machine (round-37 §6).

The core gap this closes: ``ReviewItem`` had ``with_deferral()`` for "the day never got to it"
but nothing moved ``due_date`` / ``interval_days`` / ``ease_factor`` / ``repetitions`` forward
for "the day got to it and it was actually completed". These tests pin down the advancement
rule and the plan-vs-actual / delivered-vs-practiced separation.
"""

from __future__ import annotations

import unittest
from datetime import date, timedelta

from ky.models import ReviewSchedule, validate_review_item
from ky.schedule.completion import (
    CompletionError,
    CompletionEvent,
    LadderSm2Algorithm,
    ReviewCompletion,
    VocabProgress,
    advance_review_item,
    parse_completion_event,
)


def make_item(**overrides):
    mapping = {
        "review_id": "rv1",
        "revision": 1,
        "subject_id": "math1",
        "knowledge_point_id": "math1.demo.rv1",
        "title": "demo",
        "granularity": "concept",
        "state": "queued",
        "estimated_minutes": 10,
        "introduced_on": "2026-09-01",
        "due_date": "2026-09-12",
        "schedule": {
            "mode": "fixed_bootstrap",
            "phase": 0,
            "interval_days": 1,
            "ease_factor": 2.5,
            "repetitions": 0,
            "lapses": 0,
        },
        "defer_count": 0,
        "last_quality": None,
    }
    mapping.update(overrides)
    return validate_review_item(mapping)


class AdvanceBootstrapTest(unittest.TestCase):
    def test_passing_quality_advances_the_ladder(self) -> None:
        item = make_item()
        completion = ReviewCompletion(
            review_id="rv1", completed_on=date(2026, 9, 12),
            check="past_question", outcome="correct",
        )
        advanced = advance_review_item(item, completion)
        self.assertEqual(advanced.schedule.mode, "fixed_bootstrap")
        self.assertEqual(advanced.schedule.phase, 1)
        self.assertEqual(advanced.schedule.repetitions, 1)
        self.assertEqual(advanced.due_date, completion.completed_on +
                         timedelta(days=advanced.schedule.interval_days))
        self.assertEqual(advanced.last_reviewed_on, date(2026, 9, 12))
        self.assertEqual(advanced.last_quality, 4)

    def test_clearing_the_last_bootstrap_phase_promotes_to_sm2_lite(self) -> None:
        item = make_item(schedule={
            "mode": "fixed_bootstrap", "phase": 4, "interval_days": 15,
            "ease_factor": 2.5, "repetitions": 4, "lapses": 0,
        })
        completion = ReviewCompletion(
            review_id="rv1", completed_on=date(2026, 9, 12),
            check="past_question", outcome="correct",
        )
        advanced = advance_review_item(item, completion)
        self.assertEqual(advanced.schedule.mode, "sm2_lite")
        self.assertEqual(advanced.schedule.phase, 5)
        # A promoted item must still validate against its own contract (models.py requires
        # sm2_lite items to have phase >= 5).
        self.assertEqual(validate_review_item({
            **_item_mapping(advanced),
        }).schedule.mode, "sm2_lite")

    def test_failing_quality_resets_to_a_one_day_interval_and_does_not_advance_phase(self) -> None:
        item = make_item(schedule={
            "mode": "fixed_bootstrap", "phase": 2, "interval_days": 4,
            "ease_factor": 2.5, "repetitions": 2, "lapses": 0,
        })
        completion = ReviewCompletion(
            review_id="rv1", completed_on=date(2026, 9, 12),
            check="exercise", outcome="incorrect",
        )
        advanced = advance_review_item(item, completion)
        self.assertEqual(advanced.schedule.phase, 2)  # unchanged, not advanced
        self.assertEqual(advanced.schedule.interval_days, 1)
        self.assertEqual(advanced.schedule.repetitions, 0)
        self.assertEqual(advanced.schedule.lapses, 1)
        self.assertEqual(advanced.due_date, date(2026, 9, 13))

    def test_defer_count_is_untouched_by_completion(self) -> None:
        # defer_count means "the day never got to it" -- a distinct fact from "it was completed
        # and failed". A completion, pass or fail, must never touch it.
        item = make_item(defer_count=3)
        passed = advance_review_item(
            item, ReviewCompletion(review_id="rv1", completed_on=date(2026, 9, 12),
                                   check="exercise", outcome="correct"))
        failed = advance_review_item(
            item, ReviewCompletion(review_id="rv1", completed_on=date(2026, 9, 12),
                                   check="exercise", outcome="incorrect"))
        self.assertEqual(passed.defer_count, 3)
        self.assertEqual(failed.defer_count, 3)


class AdvanceSm2LiteTest(unittest.TestCase):
    def _sm2_item(self, **schedule_overrides):
        schedule = {
            "mode": "sm2_lite", "phase": 5, "interval_days": 6,
            "ease_factor": 2.5, "repetitions": 3, "lapses": 0,
        }
        schedule.update(schedule_overrides)
        return make_item(schedule=schedule)

    def test_high_quality_grows_the_interval_and_ease(self) -> None:
        item = self._sm2_item()
        completion = ReviewCompletion(
            review_id="rv1", completed_on=date(2026, 9, 12),
            check="past_question", outcome="correct",
        )
        advanced = advance_review_item(item, completion)
        self.assertGreater(advanced.schedule.interval_days, item.schedule.interval_days)
        self.assertGreaterEqual(advanced.schedule.ease_factor, item.schedule.ease_factor)
        self.assertEqual(advanced.schedule.repetitions, 4)

    def test_ease_factor_never_drops_below_the_contract_floor(self) -> None:
        item = self._sm2_item(ease_factor=1.3)
        for _ in range(5):
            item = advance_review_item(
                item, ReviewCompletion(review_id="rv1", completed_on=date(2026, 9, 12),
                                       check="recall_vs_notes", outcome="partial"))
        self.assertGreaterEqual(item.schedule.ease_factor, 1.3)

    def test_interval_never_exceeds_the_contract_ceiling(self) -> None:
        item = self._sm2_item(interval_days=170, ease_factor=3.0)
        completion = ReviewCompletion(
            review_id="rv1", completed_on=date(2026, 9, 12),
            check="exercise", outcome="correct",
        )
        advanced = advance_review_item(item, completion)
        self.assertLessEqual(advanced.schedule.interval_days, 180)

    def test_advanced_item_always_revalidates_against_its_own_contract(self) -> None:
        item = self._sm2_item()
        for outcome in ("correct", "partial", "incorrect"):
            with self.subTest(outcome=outcome):
                advanced = advance_review_item(
                    item, ReviewCompletion(review_id="rv1", completed_on=date(2026, 9, 12),
                                            check="past_question", outcome=outcome))
                # Round-trips through validate_review_item without raising.
                validate_review_item(_item_mapping(advanced))


class AdvanceValidationTest(unittest.TestCase):
    def test_mismatched_review_id_is_rejected(self) -> None:
        item = make_item()
        with self.assertRaises(CompletionError):
            advance_review_item(
                item, ReviewCompletion(review_id="other", completed_on=date(2026, 9, 12),
                                       check="exercise", outcome="correct"))

    def test_unknown_outcome_is_rejected(self) -> None:
        with self.assertRaises(CompletionError):
            advance_review_item(
                make_item(), ReviewCompletion(review_id="rv1", completed_on=date(2026, 9, 12),
                                              check="exercise", outcome="unknown"))

    def test_completed_before_introduced_is_rejected(self) -> None:
        item = make_item()
        with self.assertRaises(CompletionError):
            advance_review_item(
                item, ReviewCompletion(review_id="rv1", completed_on=date(2020, 1, 1),
                                       check="exercise", outcome="correct"))


class ParseCompletionEventTest(unittest.TestCase):
    def test_study_minutes_distinguishes_v1_v2_v3_and_zero(self) -> None:
        for version in (1, 2):
            raw = {"schema_version": version, "day": "2026-09-15"}
            if version == 1:
                raw["reviews"] = []
            event = parse_completion_event(raw)
            self.assertIsNone(event.study_minutes)
        event = parse_completion_event({"schema_version": 3, "day": "2026-09-15",
                                        "study_minutes": 0})
        self.assertEqual(event.study_minutes, 0)

    def test_study_minutes_rejects_bool_negative_and_old_schema(self) -> None:
        for value in (True, -1, "0"):
            with self.subTest(value=value), self.assertRaises(CompletionError):
                parse_completion_event({"schema_version": 3, "day": "2026-09-15",
                                        "study_minutes": value})
        with self.assertRaises(CompletionError):
            parse_completion_event({"schema_version": 2, "day": "2026-09-15",
                                    "study_minutes": 1})
        with self.assertRaises(CompletionError):
            parse_completion_event({"schema_version": 3, "day": "2026-09-15"})

    def test_duplicate_explicit_completion_ids_are_rejected(self) -> None:
        raw = {"schema_version": 2, "day": "2026-09-12", "reviews": [
            {"review_id": "rv1", "completed_on": "2026-09-12", "check": "none",
             "completion_id": "same"},
            {"review_id": "rv2", "completed_on": "2026-09-12", "check": "none",
             "completion_id": "same"},
        ]}
        with self.assertRaises(CompletionError) as ctx:
            parse_completion_event(raw, source="probe")
        self.assertEqual(ctx.exception.path, "probe.reviews[1].completion_id")

    def test_explicit_completion_id_cannot_match_another_automatic_id(self) -> None:
        raw = {"schema_version": 2, "day": "2026-09-12", "reviews": [
            {"review_id": "rv1", "completed_on": "2026-09-12", "check": "none",
             "completion_id": "2026-09-12#1"},
            {"review_id": "rv2", "completed_on": "2026-09-12", "check": "none"},
        ]}
        with self.assertRaises(CompletionError) as ctx:
            parse_completion_event(raw, source="probe")
        self.assertEqual(ctx.exception.path, "probe.reviews[1].completion_id")

    def test_well_formed_event_parses(self) -> None:
        raw = {
            "day": "2026-09-15",
            "schema_version": 2,
            "reviews": [{"review_id": "rv1", "completed_on": "2026-09-15",
                         "check": "past_question", "outcome": "correct",
                         "question_ref": "cs408-2023-1", "self_rating": "fluent"}],
            "vocab": {"delivered_words": ["abate", "abdicate"], "practiced_words": ["abate"]},
        }
        event = parse_completion_event(raw)
        self.assertEqual(event.day, date(2026, 9, 15))
        self.assertEqual(len(event.reviews), 1)
        self.assertEqual(event.reviews[0].outcome, "correct")
        self.assertEqual(event.reviews[0].question_ref, "cs408-2023-1")
        self.assertEqual(event.reviews[0].completion_id, "2026-09-15#0")
        self.assertEqual(event.vocab.delivered_words, ("abate", "abdicate"))
        self.assertEqual(event.vocab.practiced_words, ("abate",))

    def test_delivered_and_practiced_are_kept_as_separate_counts(self) -> None:
        # abdicate was delivered but not practiced: delivered != practiced, on purpose.
        raw = {
            "day": "2026-09-15",
            "vocab": {"delivered_words": ["abate", "abdicate"], "practiced_words": ["abate"]},
        }
        event = parse_completion_event(raw)
        self.assertEqual(len(event.vocab.delivered_words), 2)
        self.assertEqual(len(event.vocab.practiced_words), 1)
        self.assertNotEqual(event.vocab.delivered_words, event.vocab.practiced_words)

    def test_unknown_field_is_rejected(self) -> None:
        with self.assertRaises(CompletionError):
            parse_completion_event({"day": "2026-09-15", "bogus": 1})

    def test_same_review_id_can_have_distinct_completion_records(self) -> None:
        raw = {
            "schema_version": 1,
            "day": "2026-09-15",
            "reviews": [
                {"review_id": "rv1", "completed_on": "2026-09-15", "quality": 4},
                {"review_id": "rv1", "completed_on": "2026-09-15", "quality": 2},
            ],
        }
        event = parse_completion_event(raw)
        completion_ids = {review.completion_id for review in event.reviews}
        self.assertEqual(len(completion_ids), len(event.reviews))

    def test_quality_out_of_range_is_rejected(self) -> None:
        raw = {"schema_version": 1, "day": "2026-09-15",
               "reviews": [{"review_id": "rv1", "completed_on": "2026-09-15", "quality": 7}]}
        with self.assertRaises(CompletionError):
            parse_completion_event(raw)

    def test_missing_vocab_defaults_to_empty(self) -> None:
        event = parse_completion_event({"day": "2026-09-15"})
        self.assertEqual(event.vocab, VocabProgress())

    def test_v1_self_assessment_parses_as_unchecked(self) -> None:
        event = parse_completion_event({
            "schema_version": 1,
            "day": "2026-09-15",
            "reviews": [{"review_id": "rv1", "completed_on": "2026-09-15", "quality": 5}],
        })
        self.assertEqual(event.reviews[0].check, "none")
        self.assertIsNone(LadderSm2Algorithm().progress_quality(event.reviews[0]))

    def test_none_check_rejects_even_null_outcome(self) -> None:
        with self.assertRaises(CompletionError):
            parse_completion_event({
                "schema_version": 2,
                "day": "2026-09-15",
                "reviews": [{"review_id": "rv1", "completed_on": "2026-09-15",
                             "check": "none", "outcome": None}],
            })


def _item_mapping(item) -> dict:
    schedule = item.schedule
    return {
        "review_id": item.review_id,
        "revision": item.revision,
        "subject_id": item.subject_id,
        "knowledge_point_id": item.knowledge_point_id,
        "title": item.title,
        "granularity": item.granularity,
        "state": item.state,
        "estimated_minutes": item.estimated_minutes,
        "introduced_on": item.introduced_on.isoformat(),
        "due_date": item.due_date.isoformat(),
        "last_reviewed_on": item.last_reviewed_on.isoformat() if item.last_reviewed_on else None,
        "schedule": {
            "mode": schedule.mode,
            "phase": schedule.phase,
            "interval_days": schedule.interval_days,
            "ease_factor": schedule.ease_factor,
            "repetitions": schedule.repetitions,
            "lapses": schedule.lapses,
        },
        "defer_count": item.defer_count,
        "last_quality": item.last_quality,
        "self_rating": item.last_self_rating,
    }


class DoesNotPrescribeTest(unittest.TestCase):
    """Mirrors monthly_close's test_close_does_not_prescribe_next_month, replicated per round-37
    §1: advancing a ReviewItem is a deterministic mechanical rule, not a recommendation -- no
    public name here may look like one."""

    def test_no_prescriptive_public_names(self) -> None:
        import ky.schedule.completion as module

        banned_prefixes = ("recommend", "suggest", "default", "optimal", "next_month_")
        names = list(dir(module))
        for cls in (module.CompletionEvent, module.ReviewCompletion, module.VocabProgress):
            names.extend(cls.__dataclass_fields__)
        for name in names:
            if name.startswith("_"):
                continue
            lowered = name.lower()
            for prefix in banned_prefixes:
                self.assertFalse(
                    lowered.startswith(prefix), f"{name} looks prescriptive (matches {prefix!r})"
                )


if __name__ == "__main__":
    unittest.main()
