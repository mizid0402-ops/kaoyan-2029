"""How strongly a CS408 knowledge-tree node is corroborated by its sources.

This extracts (unchanged in meaning) the ``evidence_tag`` -> weight half of
``evidence_for()`` in the archived weighted-tree builder into an
independent, testable function. It does *not* re-implement the classification
that decides *which* ``evidence_tag`` a node gets (that logic depends on the
document alignment in the archived builder and is reused from
there unchanged) -- only the second half: given an already-assigned
``evidence_tag`` plus its ``source_count``/``match_kind`` context, how much
that node's title is corroborated by the sources cited for it.

Naming
------
This repository already has two other, unrelated things called "weight":

  * ``ky/schedule/review_clip.py``'s ``weight`` -- a subject-level daily
    time-budget share (how many minutes/day a subject gets).
  * ``tools/apply_knowledge_weights.py``'s ``weight`` -- a
    question -> knowledge-point distribution confidence (how likely a given
    exam question maps to a given knowledge point).

Both are unrelated to "how well-evidenced is this tree node". To avoid a
third meaning colliding with those two, this module's field is called
``source_support`` everywhere -- same numeric values, same rule, new name
only.

The rule table
---------------
Empirically, ``source_support`` is a function of ``evidence_tag`` alone,
*except* for ``text_layer_ocr_risk``, which masks the tag a node would
otherwise have gotten while preserving that underlying match's support
level -- so it additionally needs ``match_kind`` to tell an OCR-glitched
*exact* match (support 1.0) from an OCR-glitched *fuzzy/structural* match
(support 0.75). ``source_count`` never independently changes the value; it
is accepted (and validated against ``KNOWN_COMBINATIONS``) purely so a
caller cannot silently feed in a stale/inconsistent triple.

+---------------------------+--------------+------------------------------+
| evidence_tag              | source_supp. | reason                       |
+---------------------------+--------------+------------------------------+
| dual_source_exact         | 1.00         | both sources, exact/full-text|
|                           |              | match                        |
| structural_equivalent     | 0.75         | both sources, but only a     |
|                           |              | reordered/renamed/fuzzy/     |
|                           |              | split/moved/promoted match   |
| candidate_recent_new      | 0.75         | new in the 2026 source, or a |
|                           |              | 2022 item known to be a      |
|                           |              | recently-added exam topic    |
| single_source_unverified  | 0.50         | only one source supports it, |
|                           |              | no independent corroboration |
| legacy_only_pending       | 0.50         | 2022-only node with no 2026  |
|                           |              | counterpart found            |
| text_layer_ocr_risk       | 1.00 if the underlying match_kind is        |
|                           | exact/reorder_exact/full_text_match, else   |
|                           | 0.75 (see above)                            |
+---------------------------+--------------+------------------------------+

Reproduction proof: ``tests/test_tree_source_support.py`` feeds every
``(evidence_tag, source_count, match_kind)`` triple actually present in the
410 nodes of ``data/structured_materials/cs408/knowledge_tree_weighted.yaml``
into :func:`derive_source_support` and asserts the result equals that node's
recorded ``weight``, for all 410 nodes with zero mismatches.
"""
from __future__ import annotations

BASE_SUPPORT_BY_TAG: dict[str, float] = {
    "dual_source_exact": 1.0,
    "structural_equivalent": 0.75,
    "candidate_recent_new": 0.75,
    "single_source_unverified": 0.5,
    "legacy_only_pending": 0.5,
}

# Only text_layer_ocr_risk needs match_kind to disambiguate; every match_kind
# that has co-occurred with it in the data is listed here. Adding a new
# match_kind under OCR risk requires a conscious decision about which side of
# the 1.0/0.75 split it falls on, so it is not covered by a default.
OCR_RISK_SUPPORT_BY_MATCH_KIND: dict[str, float] = {
    "exact": 1.0,
    "reorder_exact": 1.0,
    "full_text_match": 1.0,
    "fuzzy": 0.75,
    "manual_override": 0.75,
    "split_from_2022": 0.75,
    "cross_section_move": 0.75,
    "scope_promotion_from_item": 0.75,
}

# Every (evidence_tag, source_count, match_kind) triple confirmed to occur
# among the 410 nodes of the round-24 weighted tree. derive_source_support()
# refuses anything outside this set rather than guessing, so a corrupted or
# novel combination fails loudly instead of silently getting a value.
KNOWN_COMBINATIONS: frozenset[tuple[str, int, str]] = frozenset({
    ("candidate_recent_new", 1, "only_26"),
    ("candidate_recent_new", 1, "only_b"),
    ("dual_source_exact", 2, "exact"),
    ("dual_source_exact", 2, "full_text_match"),
    ("dual_source_exact", 2, "reorder_exact"),
    ("legacy_only_pending", 1, "only_a"),
    ("single_source_unverified", 1, "full_text_no_match"),
    ("single_source_unverified", 1, "only_b"),
    ("structural_equivalent", 1, "full_text_no_match"),
    ("structural_equivalent", 2, "cross_section_move"),
    ("structural_equivalent", 2, "fuzzy"),
    ("structural_equivalent", 2, "manual_override"),
    ("structural_equivalent", 2, "scope_promotion_from_item"),
    ("structural_equivalent", 2, "split_from_2022"),
    ("text_layer_ocr_risk", 2, "exact"),
    ("text_layer_ocr_risk", 2, "fuzzy"),
})


class UnknownSourceSupportCombination(ValueError):
    """Raised when (evidence_tag, source_count, match_kind) isn't recognized."""


def derive_source_support(evidence_tag: str, source_count: int, match_kind: str) -> float:
    """Return the source_support value for this (evidence_tag, source_count,
    match_kind) triple, or raise UnknownSourceSupportCombination.

    This is deliberately a *validated table lookup*, not a formula that
    extrapolates to unseen combinations: a knowledge tree is small and
    finite, and a combination nobody has looked at yet should block the
    build rather than receive a guessed value.
    """
    combo = (evidence_tag, source_count, match_kind)
    if combo not in KNOWN_COMBINATIONS:
        raise UnknownSourceSupportCombination(f"no source_support rule for {combo!r}")
    if evidence_tag == "text_layer_ocr_risk":
        return OCR_RISK_SUPPORT_BY_MATCH_KIND[match_kind]
    return BASE_SUPPORT_BY_TAG[evidence_tag]
