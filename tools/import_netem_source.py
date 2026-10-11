"""Import the NETEM word-frequency list as a second, independent source for English-1.

Rights boundary (see review/rounds/round-21-netem-import-task.md): the upstream
repo `exam-data/NETEMVocabulary` publishes data under CC BY-NC-SA 4.0 and its
`释义` (Chinese gloss) field may be sourced from a third-party dictionary. This
script therefore:
  - reads the raw upstream JSON only to compute its SHA-256 and to strip the
    `释义` field out before anything touches disk again;
  - writes a *stripped* JSON (word form, rank, frequency, other spellings,
    category, subcategory only) under data/english_vocabulary/ as the
    reproducible input for the database build;
  - never writes `释义` text into any project file, including this script's
    own stdout/log files.

The result lives in two new tables inside the existing eng1_vocabulary.sqlite,
kept separate from the `words` table (which represents a different source:
three years of actual exam papers) so the "source" dimension survives for
future multi-source weighting.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "english_vocabulary" / "eng1_vocabulary.sqlite"
STRIPPED_JSON = ROOT / "data" / "english_vocabulary" / "netem_wordlist_stripped.json"

SOURCE_ID = "netem-5530-wordfreq"
SOURCE_NAME = "考研词汇词频排序表（NETEM，5530 条）"
SOURCE_URL = "https://github.com/exam-data/NETEMVocabulary/blob/master/netem_full_list.json"
SOURCE_LICENCE = "data: CC BY-NC-SA 4.0; code: MIT (see upstream LICENSE / LICENSE-CODE)"
EXPECTED_SHA256 = "6d71a301321056291902bc4804e223c6926dca0d629a45076a6ca5adab185f62"
EXPECTED_BYTE_SIZE = 1_106_068
EXPECTED_ENTRY_COUNT = 5530

RAW_FIELDS = ("序号", "词频", "单词", "其他拼写", "分类", "子分类")

SCHEMA = """
CREATE TABLE IF NOT EXISTS source_wordlists (
    source_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    licence TEXT NOT NULL,
    retrieved_on TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_entries (
    entry_id INTEGER PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES source_wordlists(source_id),
    rank INTEGER NOT NULL,
    word_form_original TEXT NOT NULL,
    word_form_norm TEXT NOT NULL,
    source_freq INTEGER NOT NULL,
    category TEXT,
    subcategory TEXT,
    other_spellings TEXT,
    UNIQUE(source_id, rank)
);

CREATE INDEX IF NOT EXISTS idx_source_entries_norm
    ON source_entries(source_id, word_form_norm);
"""


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize(word: str) -> str:
    return word.strip().lower()


def load_raw_entries(raw_path: Path) -> list[dict]:
    with raw_path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if len(data) != 1:
        raise ValueError(f"expected exactly 1 top-level key, found {len(data)}")
    (key, entries), = data.items()
    if not isinstance(entries, list):
        raise ValueError("top-level value is not a list")
    return entries


def strip_entries(entries: list[dict]) -> list[dict]:
    stripped = []
    for item in entries:
        stripped.append({field: item.get(field) for field in RAW_FIELDS})
    return stripped


def derive_rows(stripped_entries: list[dict]) -> list[dict]:
    rows = []
    for item in stripped_entries:
        word = item["单词"]
        rows.append(
            {
                "rank": item["序号"],
                "word_form_original": word,
                "word_form_norm": normalize(word),
                "source_freq": item["词频"],
                "category": item.get("分类"),
                "subcategory": item.get("子分类"),
                "other_spellings": item.get("其他拼写"),
            }
        )
    return rows


def write_stripped_json(stripped_entries: list[dict], out_path: Path) -> str:
    payload = {"5530考研词汇词频排序表": stripped_entries}
    text = json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=False)
    out_path.write_text(text, encoding="utf-8", newline="\n")
    return file_sha256(out_path)


def build(raw_path: Path, retrieved_on: str, db_path: Path, *, verbose: bool = True) -> dict:
    raw_bytes = raw_path.stat().st_size
    raw_sha256 = file_sha256(raw_path)
    entries = load_raw_entries(raw_path)
    stripped_entries = strip_entries(entries)
    stripped_sha256 = write_stripped_json(stripped_entries, STRIPPED_JSON)
    rows = derive_rows(stripped_entries)

    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.execute("DELETE FROM source_entries WHERE source_id=?", (SOURCE_ID,))
        conn.execute("DELETE FROM source_wordlists WHERE source_id=?", (SOURCE_ID,))
        conn.execute(
            "INSERT INTO source_wordlists (source_id, name, url, sha256, licence, retrieved_on) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (SOURCE_ID, SOURCE_NAME, SOURCE_URL, raw_sha256, SOURCE_LICENCE, retrieved_on),
        )
        conn.executemany(
            "INSERT INTO source_entries "
            "(source_id, rank, word_form_original, word_form_norm, source_freq, category, subcategory, other_spellings) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    SOURCE_ID,
                    row["rank"],
                    row["word_form_original"],
                    row["word_form_norm"],
                    row["source_freq"],
                    row["category"],
                    row["subcategory"],
                    row["other_spellings"],
                )
                for row in rows
            ],
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "raw_byte_size": raw_bytes,
        "raw_sha256": raw_sha256,
        "stripped_sha256": stripped_sha256,
        "entry_count": len(rows),
        "unique_norm_count": len({row["word_form_norm"] for row in rows}),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-json", type=Path, required=True)
    parser.add_argument("--retrieved-on", default="2026-09-14")
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--out", type=Path, default=Path("import_netem_result.txt"))
    args = parser.parse_args(argv)

    result = build(args.raw_json, args.retrieved_on, args.db)
    lines = [
        f"raw_byte_size={result['raw_byte_size']}",
        f"raw_sha256={result['raw_sha256']}",
        f"raw_sha256_expected_match={result['raw_sha256'] == EXPECTED_SHA256}",
        f"raw_byte_size_expected_match={result['raw_byte_size'] == EXPECTED_BYTE_SIZE}",
        f"stripped_sha256={result['stripped_sha256']}",
        f"entry_count={result['entry_count']}",
        f"entry_count_expected_match={result['entry_count'] == EXPECTED_ENTRY_COUNT}",
        f"unique_norm_count={result['unique_norm_count']}",
    ]
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
