"""Verify the reproducible integrity contract of the English-1 v2 database."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

from build_eng1_vocabulary import (  # noqa: E402
    BUILD_VERSION,
    DIRECTION_RULES,
    DEFAULT_DB,
    extract_source,
    load_stopwords,
    source_paths,
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_schema(conn: sqlite3.Connection, errors: list[str]) -> bool:
    tables = {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    required_tables = {"words", "occurrences", "stopwords", "meta", "delivery_log"}
    missing = required_tables - tables
    if missing:
        errors.append(f"missing tables: {sorted(missing)}")
        return False
    word_columns = {row["name"] for row in conn.execute("PRAGMA table_info(words)")}
    occurrence_columns = {row["name"] for row in conn.execute("PRAGMA table_info(occurrences)")}
    for column in ("lemma_confidence", "family_total_count", "in_directions"):
        if column not in word_columns:
            errors.append(f"words missing column: {column}")
    if "is_direction_text" not in occurrence_columns:
        errors.append("occurrences missing column: is_direction_text")
    return not errors


def _verify_source_rows(conn, errors: list[str]):
    meta = dict(conn.execute("SELECT key, value FROM meta"))
    if meta.get("build_version") != BUILD_VERSION:
        errors.append(f"build_version={meta.get('build_version')!r}, expected {BUILD_VERSION!r}")
    if meta.get("direction_rule_count") != str(len(DIRECTION_RULES)):
        errors.append("direction_rule_count does not match the code rules")
    source_stopwords = set(load_stopwords())
    db_stopwords = {
        row["word_form"] for row in conn.execute("SELECT word_form FROM stopwords")
    }
    if db_stopwords != source_stopwords:
        errors.append(
            "stopwords table differs from source: "
            f"missing={sorted(source_stopwords - db_stopwords)[:5]} "
            f"extra={sorted(db_stopwords - source_stopwords)[:5]}"
        )
    words = conn.execute("SELECT * FROM words ORDER BY word_id").fetchall()
    if not words:
        errors.append("words table is empty")
    for row in words:
        if row["is_stopword"] != int(row["word_form"] in db_stopwords):
            errors.append(f"is_stopword mismatch for {row['word_form']}")
    actual_occurrences = {
        (row["word_form"], row["source_file"], row["is_direction_text"]): row["count_in_source"]
        for row in conn.execute(
            """
            SELECT w.word_form, o.source_file, o.is_direction_text, o.count_in_source
            FROM occurrences AS o JOIN words AS w ON w.word_id = o.word_id
            """
        )
    }
    expected_occurrences: dict[tuple[str, str, int], int] = {}
    expected_direction_words: set[str] = set()
    expected_hashes: dict[str, str] = {}
    for year, kind, filename, source_path in source_paths():
        if not source_path.is_file():
            errors.append(f"missing source PDF: {source_path}")
            continue
        source = extract_source(source_path)
        expected_hashes[filename] = source["source_sha256"]
        for (word, flag), count in source["classified_counts"].items():
            expected_occurrences[(word, filename, flag)] = count
            if flag:
                expected_direction_words.add(word)
    if actual_occurrences != expected_occurrences:
        missing = sorted(set(expected_occurrences) - set(actual_occurrences))[:3]
        extra = sorted(set(actual_occurrences) - set(expected_occurrences))[:3]
        errors.append(f"occurrences mismatch: missing={missing} extra={extra}")
    return meta, db_stopwords, words, actual_occurrences, expected_direction_words, expected_hashes


def _verify_word_totals(conn, words, actual_occurrences, expected_direction_words, errors) -> None:
    actual_by_word = {row["word_form"]: row for row in words}
    for word, row in actual_by_word.items():
        occurrence_total = conn.execute(
            "SELECT COALESCE(SUM(count_in_source), 0) FROM occurrences WHERE word_id=?",
            (row["word_id"],),
        ).fetchone()[0]
        if occurrence_total != row["total_count"]:
            errors.append(
                f"total_count mismatch for {word}: "
                f"{occurrence_total} != {row['total_count']}"
            )
        observed_direction = int(any(
            key[0] == word and key[2] == 1 for key in actual_occurrences
        ))
        if row["in_directions"] != observed_direction:
            errors.append(f"in_directions mismatch for {word}")
        if row["in_directions"] != int(word in expected_direction_words):
            errors.append(f"in_directions is not reproducible for {word}")


def _verify_family_totals(words, errors: list[str]) -> None:
    expected_families: dict[str, int] = {}
    for row in words:
        key = row["lemma"] if row["lemma_confidence"] == "rule" else row["word_form"]
        expected_families[key] = expected_families.get(key, 0) + row["total_count"]
    for row in words:
        key = row["lemma"] if row["lemma_confidence"] == "rule" else row["word_form"]
        if row["family_total_count"] != expected_families[key]:
            errors.append(
                f"family_total_count mismatch for {row['word_form']}: "
                f"{row['family_total_count']} != {expected_families[key]}"
            )


def _verify_metadata(conn, meta, db_stopwords, words, expected_hashes, errors) -> None:
    if meta.get("stopword_count") != str(len(db_stopwords)):
        errors.append("stopword_count metadata mismatch")
    if meta.get("total_word_count") != str(len(words)):
        errors.append("total_word_count metadata mismatch")
    token_count = sum(row["total_count"] for row in words)
    if meta.get("total_token_count") != str(token_count):
        errors.append("total_token_count metadata mismatch")
    direction_token_count = sum(
        row["count_in_source"]
        for row in conn.execute("SELECT count_in_source FROM occurrences WHERE is_direction_text=1")
    )
    if meta.get("direction_token_count") != str(direction_token_count):
        errors.append("direction_token_count metadata mismatch")
    recorded_hashes = meta.get("source_sha256")
    if recorded_hashes:
        import json
        if json.loads(recorded_hashes) != expected_hashes:
            errors.append("source_sha256 metadata mismatch")
    else:
        errors.append("source_sha256 metadata missing")


def verify_database(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return [f"missing database: {path}"]
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        if not _verify_schema(conn, errors):
            return errors
        meta, db_stopwords, words, actual, direction_words, hashes = _verify_source_rows(
            conn, errors,
        )
        _verify_word_totals(conn, words, actual, direction_words, errors)
        _verify_family_totals(words, errors)
        _verify_metadata(conn, meta, db_stopwords, words, hashes, errors)
    finally:
        conn.close()
    return errors


def run_mutation_tests(path: Path) -> int:
    baseline_hash = file_sha256(path)
    baseline_errors = verify_database(path)
    if baseline_errors:
        print("MUTATION FAIL baseline verifier is red")
        for error in baseline_errors:
            print(f"  {error}")
        return 1

    def mutate_direction(db: Path) -> None:
        conn = sqlite3.connect(db)
        try:
            conn.execute(
                "UPDATE words SET in_directions=0 WHERE word_id=(SELECT word_id FROM words WHERE in_directions=1 LIMIT 1)"
            )
            conn.commit()
        finally:
            conn.close()

    def mutate_stopword(db: Path) -> None:
        conn = sqlite3.connect(db)
        conn.execute("DELETE FROM stopwords WHERE rowid=(SELECT rowid FROM stopwords LIMIT 1)")
        conn.commit()
        conn.close()

    def mutate_lemma(db: Path) -> None:
        conn = sqlite3.connect(db)
        conn.execute(
            """
            UPDATE words SET lemma='__mutation__'
            WHERE word_id=(
                SELECT word_id FROM words
                WHERE lemma_confidence='rule' AND family_total_count > total_count
                LIMIT 1
            )
            """
        )
        conn.commit()
        conn.close()

    mutations = (
        ("in_directions", mutate_direction),
        ("stopwords_row", mutate_stopword),
        ("lemma_family_count", mutate_lemma),
    )
    with tempfile.TemporaryDirectory(prefix="eng1-vocab-mutations-") as temp:
        for name, mutator in mutations:
            mutated = Path(temp) / f"{name}.sqlite"
            shutil.copy2(path, mutated)
            mutator(mutated)
            errors = verify_database(mutated)
            if not errors:
                print(f"MUTATION FAIL {name} was not detected")
                return 1
            print(f"MUTATION PASS {name} verifier=RED detected={len(errors)} restore_sha256={baseline_hash}")
    if file_sha256(path) != baseline_hash:
        print("MUTATION FAIL baseline database changed")
        return 1
    print(f"MUTATION PASS baseline_unchanged restore_sha256={baseline_hash}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--mutation-test", action="store_true")
    args = parser.parse_args(argv)
    if args.mutation_test:
        return run_mutation_tests(args.db)
    errors = verify_database(args.db)
    if errors:
        print(f"VERIFY FAIL errors={len(errors)}")
        for error in errors:
            print(f"  {error}")
        return 1
    print(f"VERIFY PASS db_sha256={file_sha256(args.db)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
