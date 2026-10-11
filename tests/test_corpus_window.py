"""Corpus-window tests.

The user narrowed the corpus from "the last ten years" to "the last three to
five years" because older papers carry less reference value. The risk this
protects against is drift: a 2013 paper registered "for completeness" quietly
entering the frequency statistics and turning a recent-trend ranking into a
decade-old-syllabus ranking.
"""

from __future__ import annotations

import unittest

from ky.knowledge import (
    DEFAULT_CORPUS_WINDOW_YEARS,
    MAX_CORPUS_WINDOW_YEARS,
    MIN_CORPUS_WINDOW_YEARS,
    classify_exam_year,
    corpus_window,
    plan_corpus_years,
)

# The project target: 2029 intake, so the initial exam is sat in December 2028.
TARGET_EXAM_YEAR = 2028


class CorpusWindowTest(unittest.TestCase):
    def test_window_is_relative_to_the_target_exam_year(self) -> None:
        # 5 years ending at 2028 -> 2024..2028.
        self.assertEqual(corpus_window(TARGET_EXAM_YEAR), (2024, 2028))
        self.assertEqual(plan_corpus_years(TARGET_EXAM_YEAR), (2024, 2025, 2026, 2027, 2028))

    def test_the_agreed_range_is_three_to_five_years(self) -> None:
        self.assertEqual(DEFAULT_CORPUS_WINDOW_YEARS, 5)
        self.assertEqual(corpus_window(TARGET_EXAM_YEAR, window_years=3), (2026, 2028))
        self.assertEqual(corpus_window(TARGET_EXAM_YEAR, window_years=4), (2025, 2028))

    def test_a_window_outside_the_agreed_range_is_refused(self) -> None:
        """Ten years is what the requirements doc asked for; it is now out of range."""
        for bad in (MIN_CORPUS_WINDOW_YEARS - 1, MAX_CORPUS_WINDOW_YEARS + 1, 10, 0, -1):
            with self.subTest(window=bad):
                with self.assertRaises(ValueError) as ctx:
                    corpus_window(TARGET_EXAM_YEAR, window_years=bad)
                self.assertIn("3-5", str(ctx.exception))

    def test_advancing_the_target_moves_the_window(self) -> None:
        """Expressed relative to the target, so a later exam does not break it."""
        self.assertEqual(corpus_window(2028), (2024, 2028))
        self.assertEqual(corpus_window(2030), (2026, 2030))
        # A corpus year for the later target would have been out of range before.
        self.assertTrue(classify_exam_year(2026, 2030).in_corpus)
        self.assertTrue(classify_exam_year(2026, 2028).in_corpus)

    # -- classification --------------------------------------------------

    def test_a_recent_paper_is_corpus_eligible(self) -> None:
        for year in (2024, 2025, 2026, 2027, 2028):
            with self.subTest(year=year):
                verdict = classify_exam_year(year, TARGET_EXAM_YEAR)
                self.assertTrue(verdict.in_corpus)
                self.assertTrue(verdict.in_reference_range)

    def test_the_boundary_year_is_inclusive(self) -> None:
        self.assertTrue(classify_exam_year(2024, TARGET_EXAM_YEAR).in_corpus)
        self.assertFalse(classify_exam_year(2023, TARGET_EXAM_YEAR).in_corpus)

    def test_an_old_paper_is_excluded_with_a_reason(self) -> None:
        """2022 is still registerable as a baseline, but never counted."""
        verdict = classify_exam_year(
            2022, TARGET_EXAM_YEAR, reference_extra_years=3
        )
        self.assertFalse(verdict.in_corpus)
        self.assertTrue(verdict.in_reference_range)
        self.assertIn("exclude from frequency", verdict.reason)

    def test_an_old_paper_is_fully_excluded_without_a_reference_range(self) -> None:
        verdict = classify_exam_year(2022, TARGET_EXAM_YEAR)
        self.assertFalse(verdict.in_corpus)
        self.assertFalse(verdict.in_reference_range)
        self.assertIn("reference value too low", verdict.reason)

    def test_a_paper_older_than_ten_years_is_excluded(self) -> None:
        """The exact case the user called out as low value."""
        verdict = classify_exam_year(2013, TARGET_EXAM_YEAR, reference_extra_years=5)
        self.assertFalse(verdict.in_corpus)
        self.assertFalse(verdict.in_reference_range)

    def test_a_future_paper_is_refused(self) -> None:
        verdict = classify_exam_year(2029, TARGET_EXAM_YEAR)
        self.assertFalse(verdict.in_corpus)
        self.assertIn("does not exist yet", verdict.reason)

    def test_reference_range_extends_only_as_far_as_asked(self) -> None:
        self.assertTrue(
            classify_exam_year(2023, TARGET_EXAM_YEAR, reference_extra_years=1).in_reference_range
        )
        self.assertFalse(
            classify_exam_year(2022, TARGET_EXAM_YEAR, reference_extra_years=1).in_reference_range
        )

    # -- 408 sizing implication ------------------------------------------

    def test_corpus_year_count_is_reported_for_capacity_planning(self) -> None:
        """5 years instead of 10 roughly halves the 408 paper corpus.

        408 has ~40 single-choice plus ~7 comprehensive questions per year, so
        the decision changes the estimated item count materially even though it
        does not change the knowledge-point total.
        """
        years = plan_corpus_years(TARGET_EXAM_YEAR)
        self.assertEqual(len(years), 5)
        self.assertEqual(years, (2024, 2025, 2026, 2027, 2028))
        self.assertEqual(len(plan_corpus_years(TARGET_EXAM_YEAR, window_years=3)), 3)

    def test_invalid_types_are_refused(self) -> None:
        with self.assertRaises(ValueError):
            corpus_window(True)  # bool is not an acceptable year
        with self.assertRaises(ValueError):
            classify_exam_year("2024", TARGET_EXAM_YEAR)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
