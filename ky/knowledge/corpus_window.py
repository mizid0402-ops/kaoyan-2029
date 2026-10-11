"""Which exam years may enter the structured corpus.

The requirements document asked for "the last ten years of exam papers". The
user narrowed that on 2026-09-12 to **the last three to five years**, because
older papers carry less reference value for a target exam that is years away.

That decision needs to be executable, not a note in a document. Without it, the
corpus definition drifts: someone registers a 2013 paper "for completeness",
it enters the frequency statistics, and the "most-tested knowledge point"
ranking quietly becomes a ranking of a decade-old syllabus.

Policy
------
The structured corpus is a **rolling window of the last ``window`` exam years
relative to the target exam year**. It is deliberately expressed relative to
the target rather than as a fixed start year, so advancing the target (or
deciding to sit a later exam) moves the window instead of silently invalidating
it.

Papers older than the window may still be registered in the material ledger as
a *reference baseline*, but they are excluded from frequency statistics and
syllabus-coverage denominators. That exclusion is what ``classify_exam_year``
answers.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "DEFAULT_CORPUS_WINDOW_YEARS",
    "MIN_CORPUS_WINDOW_YEARS",
    "ExamYearVerdict",
    "corpus_window",
    "classify_exam_year",
    "plan_corpus_years",
]

# "近 3–5 年" as decided by the user. Five is the default because it is the
# generous end of the stated range and the marginal cost of one more year is
# small, while three is the minimum that still supports a frequency trend.
DEFAULT_CORPUS_WINDOW_YEARS = 5
MIN_CORPUS_WINDOW_YEARS = 3
MAX_CORPUS_WINDOW_YEARS = 5


@dataclass(frozen=True)
class ExamYearVerdict:
    """Whether one exam year may enter the structured corpus."""

    exam_year: int
    in_corpus: bool
    in_reference_range: bool
    reason: str


def _require_window(window_years: int) -> int:
    if isinstance(window_years, bool) or not isinstance(window_years, int):
        raise ValueError(f"window_years must be an int, got {type(window_years).__name__}")
    if not MIN_CORPUS_WINDOW_YEARS <= window_years <= MAX_CORPUS_WINDOW_YEARS:
        raise ValueError(
            f"window_years must be between {MIN_CORPUS_WINDOW_YEARS} and "
            f"{MAX_CORPUS_WINDOW_YEARS} (the agreed '3-5 years'), got {window_years}"
        )
    return window_years


def corpus_window(
    target_exam_year: int, *, window_years: int = DEFAULT_CORPUS_WINDOW_YEARS
) -> tuple[int, int]:
    """Inclusive ``(first_year, last_year)`` of the structured corpus.

    ``target_exam_year`` is the year the exam is *sat* (e.g. 2028 for the 2029
    intake, because the initial exam is in December of the preceding year).
    """
    window = _require_window(window_years)
    if isinstance(target_exam_year, bool) or not isinstance(target_exam_year, int):
        raise ValueError("target_exam_year must be an int")
    return (target_exam_year - window + 1, target_exam_year)


def plan_corpus_years(
    target_exam_year: int, *, window_years: int = DEFAULT_CORPUS_WINDOW_YEARS
) -> tuple[int, ...]:
    """The corpus years in ascending order, for planning and reporting."""
    first, last = corpus_window(target_exam_year, window_years=window_years)
    return tuple(range(first, last + 1))


def classify_exam_year(
    exam_year: int,
    target_exam_year: int,
    *,
    window_years: int = DEFAULT_CORPUS_WINDOW_YEARS,
    reference_extra_years: int = 0,
) -> ExamYearVerdict:
    """Decide whether an exam year may enter the structured corpus.

    ``reference_extra_years`` extends how far back a paper may be kept for
    reference only. Papers inside that extension are *not* corpus-eligible:
    they may exist in the ledger, but frequency statistics and coverage
    denominators must ignore them.
    """
    if isinstance(exam_year, bool) or not isinstance(exam_year, int):
        raise ValueError("exam_year must be an int")
    first, last = corpus_window(target_exam_year, window_years=window_years)

    if exam_year > last:
        return ExamYearVerdict(
            exam_year,
            False,
            False,
            f"exam year {exam_year} is after the target exam year {last}; "
            "a paper that does not exist yet cannot be in the corpus",
        )
    if exam_year >= first:
        return ExamYearVerdict(
            exam_year,
            True,
            True,
            f"within the {window_years}-year corpus window {first}-{last} for target {last}",
        )

    reference_first = first - max(0, reference_extra_years)
    if reference_extra_years > 0 and exam_year >= reference_first:
        return ExamYearVerdict(
            exam_year,
            False,
            True,
            f"older than the corpus window {first}-{last} but within the reference range "
            f"{reference_first}-{first - 1}; keep as baseline, exclude from frequency and "
            "coverage statistics",
        )

    return ExamYearVerdict(
        exam_year,
        False,
        False,
        f"older than the corpus window {first}-{last}; reference value too low for this "
        "target exam",
    )
