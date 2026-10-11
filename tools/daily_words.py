"""M7 English-1 vocabulary CLI; see ``contracts/vocabulary.md``.

Public entry point: ``main``. It previews lemma-frequency-ordered words from read-only reference
data and prints their completion-event fragment.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ky.storage.day_plan_store import DayPlanStore
from ky.workspace import find_workspace, load_workspace



def group_key_sql(alias: str = "w") -> str:
    return f"CASE WHEN {alias}.lemma_confidence = 'rule' THEN {alias}.lemma ELSE {alias}.word_form END"


def fetch_evidence(conn: sqlite3.Connection, group_key: str) -> str:
    rows = conn.execute(
        f"""
        SELECT w.word_form, o.exam_year, o.source_file, o.page, o.section,
               o.count_in_source, o.is_direction_text
        FROM words AS w JOIN occurrences AS o ON o.word_id = w.word_id
        WHERE {group_key_sql()} = ?
        ORDER BY w.word_form, o.exam_year, o.source_file, o.is_direction_text
        """,
        (group_key,),
    ).fetchall()
    return "; ".join(
        f"{word}/{year}/{source} p.{page} {section} x{count}"
        f"{' [direction]' if is_direction else ''}"
        for word, year, source, page, section, count, is_direction in rows
    )


def _eligible_where(include_stopwords: bool, include_directions: bool) -> str:
    clauses = []
    if not include_stopwords:
        clauses.append("w.is_stopword = 0")
    if not include_directions:
        clauses.append("w.in_directions = 0")
    return "WHERE " + " AND ".join(clauses) if clauses else ""


def family_forms(
    conn: sqlite3.Connection,
    group_key: str,
    include_stopwords: bool,
    include_directions: bool,
):
    where = _eligible_where(include_stopwords, include_directions)
    query = f"""
        SELECT w.word_form, w.total_count
        FROM words AS w
        {where}{' AND' if where else 'WHERE'} {group_key_sql()} = ?
        ORDER BY w.total_count DESC, w.word_form ASC
    """
    return conn.execute(query, (group_key,)).fetchall()


def select_candidates(
    conn: sqlite3.Connection, include_stopwords: bool, include_directions: bool,
    count: int,
    delivered_groups: set[str],
):
    where = _eligible_where(include_stopwords, include_directions)
    query = f"""
        WITH eligible AS (
            SELECT w.word_id, w.word_form, w.lemma, w.lemma_confidence,
                   w.total_count, w.year_count, w.family_total_count, w.in_directions,
                   {group_key_sql()} AS group_key
            FROM words AS w
            {where}
        ), grouped AS (
            SELECT group_key, MAX(family_total_count) AS family_total_count,
                   MAX(year_count) AS group_year_count
            FROM eligible
            GROUP BY group_key
        ), ranked AS (
            SELECT e.*, g.family_total_count, g.group_year_count,
                   ROW_NUMBER() OVER (
                       PARTITION BY e.group_key
                       ORDER BY e.total_count DESC, e.word_form ASC
                   ) AS representative_rank
            FROM eligible AS e JOIN grouped AS g ON g.group_key = e.group_key
        )
        SELECT word_id, word_form, group_key, family_total_count, group_year_count
        FROM ranked
        WHERE representative_rank = 1
        ORDER BY family_total_count DESC, group_year_count DESC, word_form ASC
    """
    page_query = query + " LIMIT ? OFFSET ?"
    selected = []
    offset = 0
    while len(selected) < count:
        page = conn.execute(page_query, (500, offset)).fetchall()
        if not page:
            break
        selected.extend(row for row in page if row["group_key"] not in delivered_groups)
        offset += len(page)
        if len(page) < 500:
            break
    return selected[:count]


def format_family(conn: sqlite3.Connection, group_key: str, include_stopwords: bool, include_directions: bool) -> str:
    return "  ".join(row["word_form"] for row in family_forms(
        conn, group_key, include_stopwords, include_directions
    ))


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=15, help="number of words, from 10 to 20")
    parser.add_argument("--show-evidence", action="store_true")
    parser.add_argument("--include-stopwords", action="store_true")
    parser.add_argument("--include-directions", action="store_true")
    parser.add_argument("--workspace")
    parser.add_argument("--db", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if not 10 <= args.count <= 20:
        parser.error("--count must be between 10 and 20")

    conn: sqlite3.Connection | None = None
    try:
        workspace = load_workspace(find_workspace(explicit=args.workspace))
        db = args.db or workspace.require("reference.vocabulary_db")
        delivered = DayPlanStore(workspace.plans).delivered_words()
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        delivered_groups = _delivered_groups(conn, delivered)
        rows = select_candidates(
            conn, args.include_stopwords, args.include_directions, args.count, delivered_groups
        )

        for row in rows:
            output = format_family(
                conn, row["group_key"], args.include_stopwords, args.include_directions
            )
            if not output:
                output = row["word_form"]
            if args.show_evidence:
                print(f"{output} —— {fetch_evidence(conn, row['group_key'])}")
            else:
                print(output)

        if len(rows) < args.count:
            remaining = len(select_candidates(
                conn, args.include_stopwords, args.include_directions, 100000,
                delivered_groups,
            ))
            print(f"已投递完，剩余 {remaining} 个", file=sys.stderr)
        _print_completion_yaml(rows)
        return 0
    except Exception as exc:
        print(f"DAILY WORDS FAIL {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        if conn is not None:
            conn.close()


def _delivered_groups(conn: sqlite3.Connection, delivered: frozenset[str]) -> set[str]:
    if not delivered:
        return set()
    rows = conn.execute(
        "SELECT word_form, lemma, lemma_confidence FROM words"
    )
    return {
        lemma if confidence == "rule" else word
        for word, lemma, confidence in rows
        if word in delivered
    }


def _print_completion_yaml(rows: list[sqlite3.Row]) -> None:
    print("vocab:")
    if not rows:
        print("  delivered_words: []")
        return
    print("  delivered_words:")
    for row in rows:
        print(f"    - {row['word_form']}")


if __name__ == "__main__":
    sys.exit(main())
