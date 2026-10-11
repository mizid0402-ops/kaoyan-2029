"""Contract tests for M10's replaceable review-progress algorithm port."""

from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import date, timedelta

from ky.models import (
    KaoyanConfig,
    ContractError,
    SubjectBudget,
    VALID_SELF_RATINGS,
    validate_config,
    validate_review_item,
)
from ky.schedule.completion import (
    LadderSm2Algorithm,
    ReviewAlgorithm,
    ReviewCompletion,
    parse_completion_event,
)
from ky.schedule.review_clip import select_daily_reviews

ALGORITHMS: list[ReviewAlgorithm] = [LadderSm2Algorithm(), LadderSm2Algorithm("lenient")]
COMPLETED_ON = date(2026, 9, 25)


def make_item(**schedule_overrides):
    schedule = {
        "mode": "fixed_bootstrap",
        "phase": 0,
        "interval_days": 1,
        "ease_factor": 2.5,
        "repetitions": 0,
        "lapses": 0,
    }
    schedule.update(schedule_overrides)
    return validate_review_item({
        "review_id": "rv1",
        "revision": 1,
        "subject_id": "math1",
        "knowledge_point_id": "math1.demo.rv1",
        "title": "demo",
        "granularity": "concept",
        "state": "queued",
        "estimated_minutes": 10,
        "introduced_on": "2026-09-01",
        "due_date": "2026-09-25",
        "schedule": schedule,
        "defer_count": 0,
        "last_quality": None,
    })


class ReviewProgressPortContractTest(unittest.TestCase):
    def test_unchecked_self_ratings_follow_both_policies_without_lengthening(self) -> None:
        item = make_item(interval_days=7)
        strict = LadderSm2Algorithm()
        strict_baseline = strict.advance(item, ReviewCompletion("rv1", COMPLETED_ON, "none"))
        for mode in ("strict", "lenient"):
            algorithm = LadderSm2Algorithm(mode)
            results = [algorithm.advance(item, ReviewCompletion(
                "rv1", COMPLETED_ON, "none", self_rating=rating,
            )) for rating in VALID_SELF_RATINGS]
            for rating, result in zip(VALID_SELF_RATINGS, results):
                with self.subTest(mode=mode, rating=rating):
                    self.assertLessEqual(result.due_date, strict_baseline.due_date)
                    self.assertLessEqual(result.schedule.interval_days,
                                         strict_baseline.schedule.interval_days)
                    self.assertEqual(result.last_self_rating, rating)
            if mode == "strict":
                self.assertEqual({(r.due_date, r.schedule) for r in results},
                                 {(strict_baseline.due_date, strict_baseline.schedule)})
            else:
                by_rating = dict(zip(VALID_SELF_RATINGS, results))
                self.assertEqual(by_rating["unknown"].schedule.phase, item.schedule.phase)
                self.assertEqual(by_rating["unknown"].schedule.ease_factor,
                                 item.schedule.ease_factor)
                self.assertEqual(by_rating["unknown"].schedule.repetitions,
                                 item.schedule.repetitions)
                self.assertEqual(by_rating["unknown"].schedule.lapses, item.schedule.lapses)
                self.assertEqual(by_rating["unknown"].schedule.interval_days, 1)
                self.assertEqual(by_rating["vague"].schedule.phase, item.schedule.phase)
                self.assertEqual(by_rating["vague"].schedule.ease_factor,
                                 item.schedule.ease_factor)
                self.assertEqual(by_rating["vague"].schedule.repetitions,
                                 item.schedule.repetitions)
                self.assertEqual(by_rating["vague"].schedule.lapses, item.schedule.lapses)
                self.assertEqual(by_rating["vague"].schedule.interval_days,
                                 max(1, item.schedule.interval_days // 2))
                for rating in ("basic", "fluent"):
                    self.assertEqual(by_rating[rating].schedule, strict_baseline.schedule)
                    self.assertEqual(by_rating[rating].due_date, strict_baseline.due_date)

    def test_review_policy_defaults_to_strict_and_rejects_unknown_values(self) -> None:
        mapping = {
            "schema_version": 1, "project_id": "demo", "default_daily_minutes": 10,
            "review_reserve_ratio": 0.2, "hard_max_ratio": 0.5,
            "subjects": [{"subject_id": "math1", "display_name": "Math", "weight": 1,
                          "active": True}],
        }
        self.assertEqual(validate_config(mapping).review_policy.self_rating_mode, "strict")
        mapping["review_policy"] = {"self_rating_mode": "unsupported"}
        with self.assertRaises(ContractError):
            validate_config(mapping)

    def test_algorithm_owns_exact_quality_mapping_and_sm2_ceiling(self) -> None:
        for algorithm in ALGORITHMS:
            with self.subTest(algorithm=type(algorithm).__name__):
                expected = {"correct": 4, "partial": 3, "incorrect": 1}
                for outcome, quality in expected.items():
                    completion = ReviewCompletion(
                        "rv1", COMPLETED_ON, "past_question", outcome
                    )
                    self.assertEqual(algorithm.progress_quality(completion), quality)

                boundary_item = make_item(
                    mode="sm2_lite", phase=5, interval_days=180, ease_factor=3.0,
                    repetitions=5, lapses=0,
                )
                boundary_result = algorithm.advance(boundary_item, ReviewCompletion(
                    "rv1", COMPLETED_ON, "past_question", "correct"
                ))
                self.assertEqual(boundary_result.schedule.interval_days, 180)
                self.assertEqual(boundary_result.schedule.ease_factor, 3.0)

    def test_recorded_self_rating_changes_the_clip_tiebreak(self) -> None:
        for algorithm in ALGORITHMS:
            with self.subTest(algorithm=type(algorithm).__name__):
                initial = replace(make_item(), review_id="rv_a", last_self_rating="unknown")
                updated = algorithm.advance(initial, ReviewCompletion(
                    "rv_a", COMPLETED_ON, "none", self_rating="fluent"
                ))
                other = replace(
                    initial,
                    review_id="rv_z",
                    due_date=updated.due_date,
                    last_self_rating="unknown",
                )
                subject = SubjectBudget(
                    subject_id="math1", display_name="Math", weight=1.0,
                    active=True, min_daily_minutes=0,
                )
                config = KaoyanConfig(
                    schema_version=1,
                    project_id="review-progress-contract",
                    default_daily_minutes=10,
                    review_reserve_ratio=1.0,
                    hard_max_ratio=1.0,
                    subjects=(subject,),
                )
                result = select_daily_reviews(
                    config, [updated, other], updated.due_date + timedelta(days=1)
                )
                self.assertEqual(updated.last_self_rating, "fluent")
                self.assertEqual(result.selected_ids, ("rv_z",))

    def test_anchored_outcomes_follow_fixed_mapping(self) -> None:
        for algorithm in ALGORITHMS:
            with self.subTest(algorithm=type(algorithm).__name__):
                item = make_item()
                for outcome in ("correct", "partial"):
                    result = algorithm.advance(item, ReviewCompletion(
                        item.review_id, COMPLETED_ON, "past_question", outcome
                    ))
                    self.assertGreater(result.schedule.phase, item.schedule.phase)
                    self.assertEqual(result.schedule.lapses, item.schedule.lapses)
                    self.assertGreater(result.due_date, COMPLETED_ON)
                incorrect = algorithm.advance(item, ReviewCompletion(
                    item.review_id, COMPLETED_ON, "exercise", "incorrect"
                ))
                self.assertEqual(incorrect.schedule.interval_days, 1)
                self.assertEqual(incorrect.schedule.lapses, item.schedule.lapses + 1)
                self.assertEqual(incorrect.schedule.phase, item.schedule.phase)
                self.assertGreater(incorrect.due_date, COMPLETED_ON)

    def test_v1_self_assessment_advances_as_unchecked(self) -> None:
        event = parse_completion_event({
            "schema_version": 1,
            "day": COMPLETED_ON.isoformat(),
            "reviews": [{
                "review_id": "rv1",
                "completed_on": COMPLETED_ON.isoformat(),
                "quality": 5,
            }],
        })
        for algorithm in ALGORITHMS:
            with self.subTest(algorithm=type(algorithm).__name__):
                item = make_item(interval_days=7)
                result = algorithm.advance(item, event.reviews[0])
                self.assertEqual(result.schedule, item.schedule)
                self.assertEqual(result.due_date,
                                 COMPLETED_ON + timedelta(days=item.schedule.interval_days))
                self.assertEqual(result.last_quality, None)
                self.assertGreater(result.due_date, COMPLETED_ON)


if __name__ == "__main__":
    unittest.main()
