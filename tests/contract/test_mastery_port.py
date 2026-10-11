from __future__ import annotations

import unittest
from datetime import date, datetime

from ky.knowledge import KnowledgePoint
from ky.mastery import (
    CONSOLIDATED_MIN_DAYS,
    LEARNED_MAX_DAYS,
    WEAK_MIN_LAPSES,
    item_level,
    mastery_gap,
    subject_mastery,
)
from ky.models import ContractError, ReviewItem, ReviewSchedule
from ky.schedule.planning import Phase, RoutePlan


SUBJECT = "alpha"
ROOT = f"{SUBJECT}.area.subject"
CHAPTER_ONE = f"{SUBJECT}.area.chapter-01"
SECTION_ONE = f"{CHAPTER_ONE}.section-01"
LEAF_A = f"{SECTION_ONE}.item-01"
LEAF_B = f"{SECTION_ONE}.item-02"
CHAPTER_TWO = f"{SUBJECT}.area.chapter-02"
SECTION_TWO = f"{CHAPTER_TWO}.section-01"
LEAF_C = f"{SECTION_TWO}.item-01"
LEAF_D = f"{SECTION_TWO}.item-02"
TRACKER = f"{SUBJECT}.goal.subject"


def _point(point_id: str, scope: str, title: str | None = None) -> KnowledgePoint:
    return KnowledgePoint(
        point_id, title or point_id, "active", "manual", (), None, (), (), None, 1, scope,
    )


def _item(
    point_id: str, *, state: str = "queued", mode: str = "ladder",
    interval: int = 1, stability: float | None = None, lapses: int = 0,
    review_id: str | None = None, self_rating: str | None = None,
) -> ReviewItem:
    return ReviewItem(
        review_id or f"review-{point_id}-{state}-{interval}-{lapses}", 1, SUBJECT,
        point_id, point_id, "item", state, 10, date(2026, 1, 1), date(2026, 1, 2), None,
        ReviewSchedule(mode, 0, interval, 2.5, 0, lapses, stability), 0, None, self_rating,
    )


def _tree() -> tuple[KnowledgePoint, ...]:
    return (
        _point(ROOT, "subject", "科目根"),
        _point(CHAPTER_ONE, "chapter", "第一章"),
        _point(SECTION_ONE, "section", "第一节"),
        _point(LEAF_A, "item", "叶子甲"),
        _point(LEAF_B, "item", "叶子乙"),
        _point(CHAPTER_TWO, "chapter", "第二章"),
        _point(SECTION_TWO, "section", "第二节"),
        _point(LEAF_C, "item", "叶子丙"),
        _point(LEAF_D, "item", "叶子丁"),
        _point(TRACKER, "subject", "跟踪节点"),
    )


class MasteryPortTests(unittest.TestCase):
    def test_item_level_boundaries_and_self_rating_has_no_effect(self) -> None:
        self.assertEqual(LEARNED_MAX_DAYS, 7)
        self.assertEqual(CONSOLIDATED_MIN_DAYS, 30)
        self.assertEqual(WEAK_MIN_LAPSES, 2)
        cases = ((6, "learned"), (7, "progressing"),
                 (29, "progressing"), (30, "consolidated"))
        for interval, expected in cases:
            item = _item(LEAF_A, interval=interval)
            self.assertEqual(item_level(item, True), expected)
            self.assertEqual(item_level(_item(LEAF_A, interval=interval,
                                              self_rating="fluent"), True), expected)
            self.assertEqual(item_level(_item(LEAF_A, interval=interval,
                                              self_rating="vague"), True), expected)
        fsrs_cases = ((6.9, "learned"), (7, "progressing"),
                      (29.9, "progressing"), (30, "consolidated"))
        for stability, expected in fsrs_cases:
            self.assertEqual(
                item_level(_item(LEAF_A, mode="fsrs", interval=1, stability=stability), True),
                expected,
            )
        self.assertEqual(
            item_level(_item(LEAF_A, mode="fsrs", interval=1, stability=30), False),
            "progressing",
        )
        self.assertEqual(
            item_level(_item(LEAF_A, mode="fsrs", interval=1, stability=30), True),
            "consolidated",
        )
        self.assertEqual(
            item_level(_item(LEAF_A, interval=30), False), "progressing",
        )
        self.assertIsNone(item_level(_item(LEAF_A, state="suspended"), False))
        self.assertIsNone(item_level(_item(LEAF_A, state="retired"), False))

    def test_past_question_gate_requires_correct_past_question(self) -> None:
        item = _item(LEAF_A, mode="fsrs", interval=1, stability=30,
                     review_id="question-review")
        exercise = _item(LEAF_B, mode="fsrs", interval=1, stability=30,
                         review_id="exercise-review")
        result = subject_mastery(
            SUBJECT, _tree(), "numbered_chapters", (item, exercise), None,
            {"question-review"},
        )
        self.assertEqual(result["leaves"][LEAF_A]["level"], "consolidated")
        self.assertEqual(result["leaves"][LEAF_B]["level"], "progressing")
        self.assertEqual(result["covered"], "0.5000")

    def test_subject_mastery_inheritance_weights_and_reference_classes(self) -> None:
        items = (
            _item(LEAF_A, interval=6, lapses=1, review_id="a-learned"),
            _item(LEAF_A, interval=30, lapses=3, state="scheduled", review_id="a-consolidated"),
            _item(CHAPTER_ONE, interval=1, mode="fsrs", stability=30, lapses=2,
                  review_id="chapter-one"),
            _item(LEAF_C, state="suspended", review_id="c-suspended"),
            _item(TRACKER, review_id="tracker-reference"),
            _item(f"{SUBJECT}.outside.item", state="retired", review_id="unknown-reference"),
        )
        weighted = subject_mastery(
            SUBJECT, _tree(), "numbered_chapters", items, {CHAPTER_ONE: 10},
            {"chapter-one"},
        )
        self.assertEqual(weighted["leaves"][LEAF_A]["level"], "learned")
        self.assertEqual(weighted["leaves"][LEAF_A]["lapses"], 3)
        self.assertTrue(weighted["leaves"][LEAF_A]["weak"])
        self.assertEqual(weighted["leaves"][LEAF_B]["level"], "consolidated")
        self.assertEqual(weighted["leaves"][LEAF_B]["lapses"], 2)
        self.assertTrue(weighted["leaves"][LEAF_B]["weak"])
        self.assertEqual(weighted["leaves"][LEAF_C]["level"], "unlearned")
        self.assertEqual(weighted["leaves"][LEAF_C]["lapses"], 0)
        self.assertEqual(weighted["leaves"][LEAF_A]["weight"], "5.0000")
        self.assertEqual(weighted["leaves"][LEAF_B]["weight"], "5.0000")
        self.assertEqual(weighted["unweighted_leaves"], [LEAF_C, LEAF_D])
        self.assertEqual(weighted["counts"], {
            "unlearned": 2, "learned": 1, "progressing": 0, "consolidated": 1,
        })
        self.assertEqual(weighted["shares"], {
            "unlearned": "0.0000", "learned": "0.5000",
            "progressing": "0.0000", "consolidated": "0.5000",
        })
        self.assertEqual(weighted["covered"], "1.0000")
        self.assertEqual(weighted["ability"], "0.5000")
        self.assertEqual(weighted["weak_leaves"], [LEAF_A, LEAF_B])
        self.assertEqual(weighted["unknown_refs"], [f"{SUBJECT}.outside.item"])
        self.assertEqual(weighted["tracker_refs"], [TRACKER])
        self.assertEqual(weighted["excluded_refs"], ["c-suspended"])

        equal = subject_mastery(
            SUBJECT, _tree(), "numbered_chapters", items, None, {"chapter-one"},
        )
        self.assertEqual(equal["unweighted_leaves"], [])
        self.assertEqual(equal["shares"], {
            "unlearned": "0.5000", "learned": "0.2500",
            "progressing": "0.0000", "consolidated": "0.2500",
        })
        self.assertEqual(equal["ability"], "0.2500")
        self.assertEqual(equal["covered"], "0.5000")

        no_weights = subject_mastery(
            SUBJECT, _tree(), "numbered_chapters", items, {}, {"chapter-one"},
        )
        self.assertIsNone(no_weights["ability"])
        self.assertIsNone(no_weights["covered"])
        self.assertTrue(all(value is None for value in no_weights["shares"].values()))
        self.assertEqual(no_weights["unweighted_leaves"], [LEAF_A, LEAF_B, LEAF_C, LEAF_D])

    def test_subject_mastery_rounds_exact_fractions_half_even(self) -> None:
        third_leaf = f"{SECTION_ONE}.item-03"
        points = (_point(ROOT, "subject"), _point(CHAPTER_ONE, "chapter"),
                  _point(SECTION_ONE, "section"), _point(LEAF_A, "item"),
                  _point(LEAF_B, "item"), _point(third_leaf, "item"))
        mastery = subject_mastery(
            SUBJECT, points, "numbered_chapters", (),
            {LEAF_A: 0.12345, LEAF_B: 0.87655}, (),
        )
        self.assertEqual(mastery["leaves"][LEAF_A]["weight"], "0.1234")
        self.assertEqual(mastery["leaves"][LEAF_B]["weight"], "0.8766")
        self.assertEqual(mastery["shares"]["unlearned"], "1.0000")
        equal = subject_mastery(
            SUBJECT, points, "numbered_chapters",
            (_item(LEAF_A, interval=1), _item(LEAF_B, interval=7),
             _item(third_leaf, interval=30)), None,
            {f"review-{third_leaf}-queued-30-0"},
        )
        self.assertEqual(equal["shares"]["learned"], "0.3333")
        self.assertEqual(equal["shares"]["progressing"], "0.3333")
        self.assertEqual(equal["shares"]["consolidated"], "0.3333")
        self.assertNotEqual(sum(float(value) for value in equal["shares"].values()), 1)

    def test_mastery_gap_interpolates_targets_clamps_signs_and_nulls(self) -> None:
        subjects = [
            {"subject_id": "alpha", "covered": "0.2500", "ability": "0.2500"},
            {"subject_id": "beta", "covered": "0.7500", "ability": "0.7500"},
            {"subject_id": "gamma", "covered": None, "ability": None},
        ]
        start = date(2026, 1, 1)
        middle_route = RoutePlan(
            "route-synthetic", 1, start, date(2026, 1, 21), "policy", "a" * 64,
            (
                Phase(0, start, date(2026, 1, 11), "first", {"alpha": 1},
                      targets={"covered": 50, "consolidated": 20}),
                Phase(1, date(2026, 1, 11), date(2026, 1, 21), "second", {"alpha": 1},
                      targets={"covered": 100, "consolidated": 80}),
            ),
        )
        middle = mastery_gap(subjects, date(2026, 1, 16), middle_route)
        self.assertEqual(middle["expected"], {"covered": "0.7500", "consolidated": "0.5000"})
        self.assertEqual(
            [(row["gap_covered"], row["gap_consolidated"]) for row in middle["subjects"]],
            [("-0.5000", "-0.2500"), ("+0.0000", "+0.2500"), (None, None)],
        )
        early = mastery_gap(subjects, date(2025, 12, 1), middle_route)
        self.assertEqual(early["expected"], {"covered": "0.0000", "consolidated": "0.0000"})
        late = mastery_gap(subjects, date(2027, 1, 1), middle_route)
        self.assertEqual(late["expected"], {"covered": "1.0000", "consolidated": "0.8000"})
        self.assertEqual(mastery_gap(subjects, date(2026, 1, 1), None)["status"],
                         "missing_route")
        no_targets = RoutePlan(
            "route-empty", 1, start, date(2026, 1, 11), "policy", "b" * 64,
            (Phase(0, start, date(2026, 1, 11), "phase", {"alpha": 1}),),
        )
        self.assertEqual(mastery_gap(subjects, start, no_targets)["status"], "no_targets")

    def test_public_parameters_fail_with_contract_paths(self) -> None:
        with self.assertRaises(ContractError) as caught:
            item_level(object(), False)
        self.assertEqual(caught.exception.path, "item")
        with self.assertRaises(ContractError) as caught:
            item_level(_item(LEAF_A), 1)
        self.assertEqual(caught.exception.path, "past_question_passed")
        with self.assertRaises(ContractError) as caught:
            subject_mastery(SUBJECT, _tree(), "unknown", (), None, ())
        self.assertEqual(caught.exception.path, "grammar")
        with self.assertRaises(ContractError) as caught:
            subject_mastery(1, _tree(), "numbered_chapters", (), None, ())
        self.assertEqual(caught.exception.path, "subject_id")
        with self.assertRaises(ContractError) as caught:
            subject_mastery(SUBJECT, [object()], "numbered_chapters", (), None, ())
        self.assertEqual(caught.exception.path, "points[0]")
        with self.assertRaises(ContractError) as caught:
            subject_mastery(SUBJECT, _tree(), "numbered_chapters", (), [], ())
        self.assertEqual(caught.exception.path, "weights")
        with self.assertRaises(ContractError) as caught:
            subject_mastery(SUBJECT, _tree(), "numbered_chapters", (), None, "review-1")
        self.assertEqual(caught.exception.path, "past_question_passed")
        with self.assertRaises(ContractError) as caught:
            mastery_gap([], datetime(2026, 1, 1), None)
        self.assertEqual(caught.exception.path, "today")
        with self.assertRaises(ContractError) as caught:
            mastery_gap([], date(2026, 1, 1), object())
        self.assertEqual(caught.exception.path, "route")
        with self.assertRaises(ContractError) as caught:
            mastery_gap([{"subject_id": "alpha", "ability": 0.5}],
                        date(2026, 1, 1), None)
        self.assertEqual(caught.exception.path, "subjects[0].ability")


if __name__ == "__main__":
    unittest.main()
