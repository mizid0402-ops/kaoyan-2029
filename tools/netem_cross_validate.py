"""Cross-validate the NETEM word-frequency source against the eng1 exam-derived words table.

Computes three numbers, all defined over case-folded word forms:
  - overlap rate: of NETEM's distinct word forms, how many appear in the
    exam-derived vocabulary (words.is_stopword=0)
  - reverse coverage: of the exam-derived vocabulary (is_stopword=0), how many
    are NOT in NETEM (candidates for out-of-syllabus words, proper nouns, or
    tokenization artifacts)
  - layered overlap: for NETEM's top 500/1000/2000 words by rank (i.e. highest
    frequency first), how many appear in the exam-derived vocabulary

No `释义` text is read or touched by this script; it only reads word_form_norm,
rank, and is_stopword.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "english_vocabulary" / "eng1_vocabulary.sqlite"
SOURCE_ID = "netem-5530-wordfreq"


def load_netem(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    rows = conn.execute(
        "SELECT rank, word_form_norm FROM source_entries WHERE source_id=? ORDER BY rank",
        (SOURCE_ID,),
    ).fetchall()
    return [(r[0], r[1]) for r in rows]


def load_exam_words(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT word_form FROM words WHERE is_stopword=0").fetchall()
    return {r[0] for r in rows}


def load_exam_word_to_lemma(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute("SELECT word_form, lemma FROM words WHERE is_stopword=0").fetchall()
    return {r[0]: r[1] for r in rows}


def distinct_norms_up_to_rank(netem_rows: list[tuple[int, str]], top_n: int) -> set[str]:
    seen: set[str] = set()
    for rank, norm in netem_rows:
        if rank > top_n:
            continue
        seen.add(norm)
    return seen


def _load_comparison_data(path: Path):
    conn = sqlite3.connect(path)
    try:
        netem_rows = load_netem(conn)
        exam_words = load_exam_words(conn)
        word_to_lemma = load_exam_word_to_lemma(conn)
    finally:
        conn.close()
    return netem_rows, exam_words, word_to_lemma


def _lemma_adjusted_coverage(netem_rows, exam_words, word_to_lemma):
    netem_norms = {norm for _, norm in netem_rows}
    reverse_missing = exam_words - netem_norms
    # Supplementary (not one of the three required numbers): the words table is
    # form-level (inflected forms like "actions", "achieved") while NETEM is a
    # dictionary headword list. Re-check reverse_missing against each word's
    # lemma to separate "morphological form mismatch" from words that are truly
    # absent from NETEM even at the lemma level.
    still_missing_after_lemma = {
        w for w in reverse_missing
        if word_to_lemma.get(w, w).lower() not in netem_norms
    }
    recovered_by_lemma = reverse_missing - still_missing_after_lemma
    return netem_norms, reverse_missing, still_missing_after_lemma, recovered_by_lemma


def _cross_validation_lines(netem_rows, exam_words, word_to_lemma) -> list[str]:
    netem_norms, reverse_missing, still_missing_after_lemma, recovered_by_lemma = (
        _lemma_adjusted_coverage(netem_rows, exam_words, word_to_lemma)
    )
    overlap = netem_norms & exam_words

    lines = []
    lines.append(f"netem_total_rows={len(netem_rows)}")
    lines.append(f"netem_distinct_norms={len(netem_norms)}")
    lines.append(f"exam_nonstop_words={len(exam_words)}")
    lines.append("")
    lines.append(f"overlap_count={len(overlap)}")
    lines.append(f"overlap_rate_over_netem={len(overlap)/len(netem_norms):.4f}")
    lines.append("")
    lines.append(f"reverse_not_in_netem_count={len(reverse_missing)}")
    lines.append(f"reverse_not_in_netem_rate_over_exam={len(reverse_missing)/len(exam_words):.4f}")
    lines.append("")

    for top_n in (500, 1000, 2000):
        layer_norms = distinct_norms_up_to_rank(netem_rows, top_n)
        layer_overlap = layer_norms & exam_words
        lines.append(
            f"top{top_n}_distinct_norms={len(layer_norms)} "
            f"top{top_n}_overlap_count={len(layer_overlap)} "
            f"top{top_n}_overlap_rate={len(layer_overlap)/len(layer_norms):.4f}"
        )

    lines.append("")
    lines.append(
        "--- supplementary: lemma-adjusted reverse coverage "
        "(not one of the 3 required numbers) ---"
    )
    lines.append(f"recovered_by_lemma_count={len(recovered_by_lemma)}")
    lines.append(f"still_missing_after_lemma_count={len(still_missing_after_lemma)}")
    lines.append(
        "still_missing_after_lemma_rate_over_exam="
        f"{len(still_missing_after_lemma)/len(exam_words):.4f}"
    )
    apostrophe_artifacts = sorted(w for w in still_missing_after_lemma if "'" in w)
    hyphenated = sorted(w for w in still_missing_after_lemma if "-" in w)
    lines.append(
        f"still_missing_apostrophe_count={len(apostrophe_artifacts)} "
        f"sample={apostrophe_artifacts[:15]}"
    )
    lines.append(
        f"still_missing_hyphenated_count={len(hyphenated)} "
        f"sample={hyphenated[:15]}"
    )

    lines.append("")
    sample_missing = sorted(reverse_missing)[:40]
    lines.append(f"reverse_missing_sample_first40={sample_missing}")
    sample_still_missing = sorted(still_missing_after_lemma)[:40]
    lines.append(f"still_missing_after_lemma_sample_first40={sample_still_missing}")

    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--out", type=Path, default=Path("netem_cross_validate_result.txt"))
    args = parser.parse_args(argv)

    netem_rows, exam_words, word_to_lemma = _load_comparison_data(args.db)
    lines = _cross_validation_lines(netem_rows, exam_words, word_to_lemma)
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
