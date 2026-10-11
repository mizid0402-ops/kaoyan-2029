"""Verify the reproducible integrity contract of the NETEM source_* tables."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

from import_netem_source import (  # noqa: E402
    EXPECTED_ENTRY_COUNT,
    RAW_FIELDS,
    SOURCE_ID,
    STRIPPED_JSON,
    derive_rows,
    normalize,
)

DB = ROOT / "data" / "english_vocabulary" / "eng1_vocabulary.sqlite"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_expected_rows() -> list[dict]:
    with STRIPPED_JSON.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    (key, entries), = payload.items()
    return derive_rows(entries)


def _verify_rank_sequence(rows, errors: list[str]) -> None:
    ranks = [row["rank"] for row in rows]
    if sorted(ranks) != list(range(1, len(rows) + 1)) and len(rows) == EXPECTED_ENTRY_COUNT:
        missing_ranks = sorted(set(range(1, EXPECTED_ENTRY_COUNT + 1)) - set(ranks))
        extra_ranks = sorted(set(ranks) - set(range(1, EXPECTED_ENTRY_COUNT + 1)))
        dup_ranks = sorted({r for r in ranks if ranks.count(r) > 1})
        errors.append(
            f"rank sequence broken: missing={missing_ranks[:5]} "
            f"extra={extra_ranks[:5]} dup={dup_ranks[:5]}"
        )


def _verify_entry_values(rows, errors: list[str]) -> None:
    for row in rows:
        if row["word_form_original"] is None or row["word_form_original"] == "":
            errors.append(f"empty word_form_original at rank={row['rank']}")
            continue
        expected_norm = normalize(row["word_form_original"])
        if row["word_form_norm"] != expected_norm:
            errors.append(
                f"word_form_norm mismatch at rank={row['rank']}: "
                f"{row['word_form_norm']!r} != "
                f"normalize({row['word_form_original']!r})={expected_norm!r}"
            )
        if row["source_freq"] is None or row["source_freq"] < 0:
            errors.append(f"invalid source_freq at rank={row['rank']}: {row['source_freq']!r}")


def _verify_reproducibility(rows, errors: list[str]) -> None:
    expected_rows = load_expected_rows()
    actual_by_rank = {row["rank"]: dict(row) for row in rows}
    expected_by_rank = {row["rank"]: row for row in expected_rows}
    if set(actual_by_rank) == set(expected_by_rank):
        for rank, expected in expected_by_rank.items():
            actual = actual_by_rank[rank]
            fields = (
                "word_form_original", "word_form_norm", "source_freq",
                "category", "subcategory", "other_spellings",
            )
            for field in fields:
                if actual.get(field) != expected.get(field):
                    errors.append(
                        f"rebuild mismatch at rank={rank} field={field}: "
                        f"db={actual.get(field)!r} rebuilt={expected.get(field)!r}"
                    )
    else:
        only_db = sorted(set(actual_by_rank) - set(expected_by_rank))[:5]
        only_rebuilt = sorted(set(expected_by_rank) - set(actual_by_rank))[:5]
        errors.append(
            f"rank sets differ from rebuilt source: only_in_db={only_db} "
            f"only_in_rebuilt={only_rebuilt}"
        )


def verify_database(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return [f"missing database: {path}"]
    if not STRIPPED_JSON.is_file():
        return [f"missing stripped source json: {STRIPPED_JSON}"]

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        required = {"source_wordlists", "source_entries"}
        missing_tables = required - tables
        if missing_tables:
            return [f"missing tables: {sorted(missing_tables)}"]

        entry_columns = {row["name"] for row in conn.execute("PRAGMA table_info(source_entries)")}
        forbidden_columns = {"释义", "definition", "meaning", "gloss", "translation"}
        leaked = entry_columns & forbidden_columns
        if leaked:
            errors.append(f"forbidden gloss-like column present: {sorted(leaked)}")

        wordlist_row = conn.execute(
            "SELECT * FROM source_wordlists WHERE source_id=?", (SOURCE_ID,)
        ).fetchone()
        if wordlist_row is None:
            errors.append(f"source_wordlists has no row for source_id={SOURCE_ID}")
        else:
            for col in ("name", "url", "sha256", "licence", "retrieved_on"):
                if not wordlist_row[col]:
                    errors.append(f"source_wordlists.{col} is empty")

        rows = conn.execute(
            "SELECT rank, word_form_original, word_form_norm, source_freq, "
            "category, subcategory, other_spellings "
            "FROM source_entries WHERE source_id=? ORDER BY rank",
            (SOURCE_ID,),
        ).fetchall()

        if len(rows) != EXPECTED_ENTRY_COUNT:
            errors.append(f"entry count={len(rows)}, expected {EXPECTED_ENTRY_COUNT}")

        _verify_rank_sequence(rows, errors)
        _verify_entry_values(rows, errors)
        # Rebuild comparison detects drift from the committed source data.
        _verify_reproducibility(rows, errors)
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

    def mutate_rank(db: Path) -> None:
        conn = sqlite3.connect(db)
        conn.execute(
            "UPDATE source_entries SET rank=99999 "
            "WHERE entry_id=(SELECT entry_id FROM source_entries WHERE source_id=? ORDER BY rank LIMIT 1)",
            (SOURCE_ID,),
        )
        conn.commit()
        conn.close()

    def mutate_delete(db: Path) -> None:
        conn = sqlite3.connect(db)
        conn.execute(
            "DELETE FROM source_entries WHERE entry_id=(SELECT entry_id FROM source_entries WHERE source_id=? ORDER BY rank DESC LIMIT 1)",
            (SOURCE_ID,),
        )
        conn.commit()
        conn.close()

    def mutate_norm_key(db: Path) -> None:
        conn = sqlite3.connect(db)
        conn.execute(
            "UPDATE source_entries SET word_form_norm='WRONG-CASEFOLD' "
            "WHERE entry_id=(SELECT entry_id FROM source_entries WHERE source_id=? ORDER BY rank LIMIT 1)",
            (SOURCE_ID,),
        )
        conn.commit()
        conn.close()

    mutations = (
        ("rank_value", mutate_rank),
        ("deleted_entry", mutate_delete),
        ("casefold_key", mutate_norm_key),
    )
    with tempfile.TemporaryDirectory(prefix="netem-source-mutations-") as temp:
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
    parser.add_argument("--db", type=Path, default=DB)
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
