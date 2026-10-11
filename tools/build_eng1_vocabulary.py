"""Build the English-1 vocabulary database from the six supplied PDFs.

Only token forms, locations, hashes, and aggregate statistics are persisted;
extracted PDF text is never written to the project. Direction detection is
line-based and deterministic, and lemma restoration is deliberately
conservative: uncertain candidates are recorded but never frequency-merged.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "english_vocabulary" / "eng1_vocabulary.sqlite"
BACKUP_DB = ROOT / "data" / "english_vocabulary" / "eng1_vocabulary.v1.sqlite.bak"
STOPWORDS_PATH = ROOT / "data" / "english_vocabulary" / "stopwords.txt"
TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")
URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
BUILD_VERSION = "eng1-vocabulary-v2"
LOGICAL_GENERATED_AT = "2026-09-13T00:00:00+08:00"

SOURCE_SPECS = tuple(
    (year, kind, f"{kind}_e1_{year}.pdf")
    for year in (2024, 2025, 2026)
    for kind in ("bv", "lazy")
)

# These are phrase/line rules rather than hand-labelled words. A token is a
# direction token when its complete extracted line matches any expression.
# The exact expressions are also repeated by the verifier.
DIRECTION_RULES = (
    ("directions_label", re.compile(r"\bdirections?\s*:", re.IGNORECASE)),
    ("answer_sheet", re.compile(r"\banswer\s+sheet\b", re.IGNORECASE)),
    ("read_following", re.compile(r"\bread\s+the\s+following\s+(?:text|passage)\b", re.IGNORECASE)),
    ("choose_best", re.compile(r"\bchoose\s+the\s+best\s+(?:word|answer)\b", re.IGNORECASE)),
    ("write_answer", re.compile(r"\bwrite\s+(?:your\s+)?answer\b", re.IGNORECASE)),
    ("mark_answer", re.compile(r"\bmark\s+(?:your\s+)?answer\b", re.IGNORECASE)),
    ("select_best", re.compile(r"\bselect\s+the\s+best\b", re.IGNORECASE)),
    ("fill_blanks", re.compile(r"\bfill\s+in\s+the\s+blanks?\b", re.IGNORECASE)),
    ("one_word", re.compile(r"\buse\s+one\s+word\b", re.IGNORECASE)),
)

SAFE_USE_FAMILY = {"use", "used", "uses", "using"}
AMBIGUOUS_S_FORMS = {
    "analysis", "basis", "bus", "crisis", "economics", "ethics", "gas",
    "news", "physics", "politics", "series", "species", "status", "thesis",
    "thus", "us",
}


def load_stopwords(path: Path = STOPWORDS_PATH) -> frozenset[str]:
    if not path.is_file():
        raise FileNotFoundError(f"missing stopword source: {path}")
    words: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip().lower()
        if not line:
            continue
        if TOKEN_RE.fullmatch(line) is None or "'" in line or "-" in line:
            raise ValueError(f"invalid stopword: {line!r}")
        words.add(line)
    if not 150 <= len(words) <= 300:
        raise ValueError(f"stopword count outside 150..300: {len(words)}")
    return frozenset(words)


def source_dir() -> Path:
    return Path(os.environ.get("TEMP", tempfile.gettempdir())) / "kaoyan-probe" / "claude2" / "dl"


def source_paths(base: Path | None = None) -> list[tuple[int, str, str, Path]]:
    directory = base or source_dir()
    return [(year, kind, filename, directory / filename) for year, kind, filename in SOURCE_SPECS]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def section_for_page(text: str, current: str | None) -> str:
    lower = text.lower()
    if re.search(r"section\s+i\b", lower) or "use of english" in lower:
        return "Section I"
    if re.search(r"section\s+ii\b", lower) or "reading comprehension" in lower:
        return "Section II"
    if re.search(r"section\s+iii\b", lower) or "translation" in lower:
        return "Section III"
    if re.search(r"section\s+iv\b", lower) or "writing" in lower:
        return "Section IV"
    return current or "Unknown"


def direction_rule_names(line: str) -> tuple[str, ...]:
    return tuple(name for name, pattern in DIRECTION_RULES if pattern.search(line))


def is_direction_line(line: str) -> bool:
    return bool(direction_rule_names(line))


def _reduce_double_consonant(stem: str) -> str:
    if len(stem) >= 3 and stem[-1] == stem[-2] and stem[-1].lower() not in "aeiou":
        return stem[:-1]
    return stem


def restore_lemma(word: str) -> tuple[str, str]:
    """Return (candidate lemma, confidence) using spelling rules only."""
    if word in SAFE_USE_FAMILY:
        return "use", "rule"
    if not word.isalpha() or len(word) < 4:
        return word, "rule"

    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y", "rule"
    if word.endswith("ers") and len(word) > 5:
        return word[:-3], "rule"
    if word.endswith("sses"):
        return word[:-2], "rule"
    if word.endswith(("xes", "zes", "ches", "shes")):
        return word[:-2], "rule"
    if word.endswith("ses"):
        return word[:-1], "rule"
    if word.endswith("s") and not word.endswith(("ss", "us", "is")):
        if word in AMBIGUOUS_S_FORMS:
            return word[:-1], "uncertain"
        return word[:-1], "rule"

    if word.endswith("ied") and len(word) > 4:
        return word[:-3] + "y", "rule"
    if word.endswith("ed") and len(word) > 4:
        stem = word[:-2]
        if stem.endswith("e"):
            return word, "uncertain"
        reduced = _reduce_double_consonant(stem)
        if reduced != stem:
            return reduced, "rule"
        if stem.endswith(("v", "c", "g")):
            return stem + "e", "uncertain"
        return stem, "rule"

    if word.endswith("ying") and len(word) > 5:
        return word[:-4] + "y", "uncertain"
    if word.endswith("ing") and len(word) > 5:
        stem = word[:-3]
        if stem.endswith("e"):
            return word, "uncertain"
        reduced = _reduce_double_consonant(stem)
        if reduced != stem:
            return reduced, "rule"
        if len(stem) >= 3 and stem[-1] not in "aeiou":
            return stem, "rule"
        return stem, "uncertain"

    # Comparative/superlative spellings are recorded as guesses because the
    # same suffix is also productive in nouns and unrelated lexical forms.
    if word.endswith("iest") and len(word) > 5:
        return word[:-4] + "y", "uncertain"
    if word.endswith("est") and len(word) > 5:
        return _reduce_double_consonant(word[:-3]), "uncertain"
    if word.endswith("er") and len(word) > 5:
        return word[:-2], "uncertain"
    return word, "rule"


def extract_source(path: Path) -> dict:
    counts: Counter[str] = Counter()
    classified_counts: Counter[tuple[str, int]] = Counter()
    first_positions: dict[tuple[str, int], tuple[int, str]] = {}
    direction_lines = 0
    direction_tokens = 0
    total_lines = 0
    current_section: str | None = None
    reader = PdfReader(str(path))
    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        current_section = section_for_page(text, current_section)
        for line in text.splitlines() or [text]:
            total_lines += 1
            is_direction = int(is_direction_line(line))
            matches = list(TOKEN_RE.finditer(URL_RE.sub(" ", line)))
            if is_direction:
                direction_lines += 1
                direction_tokens += len(matches)
            for match in matches:
                word = match.group(0).lower()
                counts[word] += 1
                classified_counts[(word, is_direction)] += 1
                first_positions.setdefault((word, is_direction), (page_number, current_section))
    return {
        "source_file": path.name,
        "counts": counts,
        "classified_counts": classified_counts,
        "positions": first_positions,
        "direction_lines": direction_lines,
        "direction_tokens": direction_tokens,
        "total_lines": total_lines,
        "source_sha256": sha256_file(path),
    }


def build_payload(source_base: Path | None = None) -> dict:
    stopwords = load_stopwords()
    source_data = []
    global_counts: Counter[str] = Counter()
    years_by_word: dict[str, set[int]] = defaultdict(set)
    direction_by_word: set[str] = set()
    for year, kind, filename, path in source_paths(source_base):
        if not path.is_file():
            raise FileNotFoundError(f"missing source PDF: {path}")
        source = extract_source(path)
        source.update({"exam_year": year, "kind": kind, "source_file": filename})
        source_data.append(source)
        global_counts.update(source["counts"])
        for word in source["counts"]:
            years_by_word[word].add(year)
        direction_by_word.update(word for word, flag in source["classified_counts"] if flag)

    words = []
    for word in sorted(global_counts):
        years = sorted(years_by_word[word])
        lemma, confidence = restore_lemma(word)
        words.append(
            {
                "word_form": word,
                "lemma": lemma,
                "lemma_confidence": confidence,
                "pos": None,
                "total_count": global_counts[word],
                "year_count": len(years),
                "first_year": years[0],
                "last_year": years[-1],
                "is_stopword": int(word in stopwords),
                "in_directions": int(word in direction_by_word),
            }
        )
    groups: Counter[str] = Counter()
    for row in words:
        key = row["lemma"] if row["lemma_confidence"] == "rule" else row["word_form"]
        groups[key] += row["total_count"]
    for row in words:
        key = row["lemma"] if row["lemma_confidence"] == "rule" else row["word_form"]
        row["family_total_count"] = groups[key]
    word_ids = {row["word_form"]: index for index, row in enumerate(words, start=1)}
    return {"words": words, "word_ids": word_ids, "sources": source_data, "stopwords": sorted(stopwords)}


def create_database(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA journal_mode=DELETE")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(
            """
            CREATE TABLE words (
                word_id INTEGER PRIMARY KEY,
                word_form TEXT NOT NULL UNIQUE,
                lemma TEXT NOT NULL,
                lemma_confidence TEXT NOT NULL CHECK (lemma_confidence IN ('rule', 'uncertain')),
                family_total_count INTEGER NOT NULL CHECK (family_total_count > 0),
                pos TEXT,
                total_count INTEGER NOT NULL CHECK (total_count > 0),
                year_count INTEGER NOT NULL CHECK (year_count > 0),
                first_year INTEGER NOT NULL,
                last_year INTEGER NOT NULL,
                is_stopword INTEGER NOT NULL CHECK (is_stopword IN (0, 1)),
                in_directions INTEGER NOT NULL CHECK (in_directions IN (0, 1))
            );
            CREATE TABLE occurrences (
                occurrence_id INTEGER PRIMARY KEY,
                word_id INTEGER NOT NULL REFERENCES words(word_id),
                exam_year INTEGER NOT NULL,
                source_file TEXT NOT NULL,
                source_sha256 TEXT NOT NULL,
                page INTEGER NOT NULL CHECK (page > 0),
                section TEXT NOT NULL,
                count_in_source INTEGER NOT NULL CHECK (count_in_source > 0),
                is_direction_text INTEGER NOT NULL CHECK (is_direction_text IN (0, 1)),
                UNIQUE(word_id, source_file, is_direction_text)
            );
            CREATE TABLE stopwords (
                word_form TEXT PRIMARY KEY,
                CHECK (word_form = lower(word_form))
            );
            CREATE TABLE meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE delivery_log (
                delivered_on TEXT NOT NULL,
                word_id INTEGER NOT NULL REFERENCES words(word_id),
                batch_index INTEGER NOT NULL CHECK (batch_index > 0),
                PRIMARY KEY (delivered_on, word_id),
                UNIQUE(word_id),
                UNIQUE(delivered_on, batch_index)
            );
            CREATE INDEX idx_words_total_count_desc
                ON words(total_count DESC, year_count DESC, word_form ASC);
            CREATE INDEX idx_words_year_count_desc
                ON words(year_count DESC, total_count DESC, word_form ASC);
            CREATE INDEX idx_words_family_total_count_desc
                ON words(family_total_count DESC, year_count DESC, word_form ASC);
            CREATE VIEW v_top_words AS
                SELECT word_id, word_form, lemma, lemma_confidence, family_total_count,
                       pos, total_count, year_count, first_year, last_year,
                       is_stopword, in_directions
                FROM words
                ORDER BY family_total_count DESC, total_count DESC, word_form ASC;
            """
        )
        conn.executemany("INSERT INTO stopwords(word_form) VALUES (?)", [(word,) for word in payload["stopwords"]])
        conn.executemany(
            """
            INSERT INTO words
              (word_id, word_form, lemma, lemma_confidence, family_total_count, pos,
               total_count, year_count, first_year, last_year, is_stopword, in_directions)
            VALUES (:word_id, :word_form, :lemma, :lemma_confidence, :family_total_count, :pos,
                    :total_count, :year_count, :first_year, :last_year, :is_stopword, :in_directions)
            """,
            [{**row, "word_id": payload["word_ids"][row["word_form"]]} for row in payload["words"]],
        )
        occurrences = []
        for source in payload["sources"]:
            for (word, is_direction), count in sorted(source["classified_counts"].items()):
                page, section = source["positions"][(word, is_direction)]
                occurrences.append(
                    (payload["word_ids"][word], source["exam_year"], source["source_file"],
                     source["source_sha256"], page, section, count, is_direction)
                )
        conn.executemany(
            """
            INSERT INTO occurrences
              (word_id, exam_year, source_file, source_sha256, page, section,
               count_in_source, is_direction_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            occurrences,
        )
        source_hashes = {source["source_file"]: source["source_sha256"] for source in payload["sources"]}
        direction_tokens = sum(source["direction_tokens"] for source in payload["sources"])
        total_tokens = sum(row["total_count"] for row in payload["words"])
        rule_count = sum(row["lemma_confidence"] == "rule" and row["lemma"] != row["word_form"] for row in payload["words"])
        uncertain_count = sum(row["lemma_confidence"] == "uncertain" and row["lemma"] != row["word_form"] for row in payload["words"])
        meta = {
            "build_version": BUILD_VERSION,
            "generated_at": LOGICAL_GENERATED_AT,
            "token_regex": r"[A-Za-z][A-Za-z'-]*",
            "source_files": json.dumps(sorted(source_hashes), ensure_ascii=True),
            "source_sha256": json.dumps(source_hashes, sort_keys=True, ensure_ascii=True),
            "stopwords_source": str(STOPWORDS_PATH.relative_to(ROOT)).replace("\\", "/"),
            "stopword_count": str(len(payload["stopwords"])),
            "total_word_count": str(len(payload["words"])),
            "total_token_count": str(total_tokens),
            "non_stopword_count": str(sum(row["is_stopword"] == 0 for row in payload["words"])),
            "cross_year_word_count": str(sum(row["year_count"] >= 2 for row in payload["words"])),
            "family_count": str(len({
                row["lemma"] if row["lemma_confidence"] == "rule" else row["word_form"]
                for row in payload["words"]
            })),
            "direction_token_count": str(direction_tokens),
            "direction_token_ratio": f"{direction_tokens / total_tokens:.12f}",
            "direction_word_count": str(sum(row["in_directions"] for row in payload["words"])),
            "direction_rule_count": str(len(DIRECTION_RULES)),
            "lemmatized_count": str(rule_count),
            "lemma_uncertain_count": str(uncertain_count),
            "lemma_restored_count": str(rule_count + uncertain_count),
            "lemma_restored_ratio": f"{(rule_count + uncertain_count) / len(payload['words']):.12f}",
            "unlemmatized_ratio": f"{1 - (rule_count + uncertain_count) / len(payload['words']):.12f}",
            "content_notice": "only word forms, locations, hashes, and statistics; no original text is stored",
        }
        conn.executemany("INSERT INTO meta(key, value) VALUES (?, ?)", sorted(meta.items()))
        conn.commit()
        conn.execute("VACUUM")
    finally:
        conn.close()


def sha256_file_path(path: Path) -> str:
    return sha256_file(path)


OWNED_SCHEMA_OBJECTS = (
    "words", "occurrences", "stopwords", "meta", "delivery_log", "v_top_words",
    "idx_words_total_count_desc", "idx_words_year_count_desc", "idx_words_family_total_count_desc",
)


def static_content_hash(path: Path) -> str:
    """Hash schema plus build-owned rows, excluding mutable delivery history.

    Scoped to the objects this build script owns (OWNED_SCHEMA_OBJECTS) so that
    unrelated tables added by other importers (e.g. tools/import_netem_source.py's
    source_wordlists/source_entries, a second independent vocabulary source) do
    not perturb this script's own reproducibility check.
    """
    conn = sqlite3.connect(path)
    try:
        placeholders = ",".join("?" for _ in OWNED_SCHEMA_OBJECTS)
        objects = conn.execute(
            f"""
            SELECT type, name, COALESCE(sql, '')
            FROM sqlite_master
            WHERE name NOT LIKE 'sqlite_%' AND name IN ({placeholders})
            ORDER BY type, name
            """,
            OWNED_SCHEMA_OBJECTS,
        ).fetchall()
        payload = {"objects": objects, "rows": {}}
        for table in ("words", "occurrences", "stopwords", "meta"):
            payload["rows"][table] = conn.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()
        encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="build in a temporary file and compare without changing the DB")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        if args.check:
            if not args.db.is_file():
                print(f"CHECK FAIL missing database: {args.db}")
                return 1
            with tempfile.TemporaryDirectory(prefix="eng1-vocab-check-") as temp:
                expected = Path(temp) / "expected.sqlite"
                create_database(expected, build_payload())
                expected_hash = static_content_hash(expected)
            actual_hash = static_content_hash(args.db)
            if actual_hash != expected_hash:
                print(f"CHECK FAIL expected_content_sha256={expected_hash} actual_content_sha256={actual_hash}")
                return 1
            print(f"CHECK PASS content_sha256={actual_hash} db_sha256={sha256_file_path(args.db)}")
            return 0

        payload = build_payload()
        args.db.parent.mkdir(parents=True, exist_ok=True)
        if args.db == DEFAULT_DB and args.db.is_file() and not BACKUP_DB.exists():
            shutil.copy2(args.db, BACKUP_DB)
        with tempfile.TemporaryDirectory(prefix="eng1-vocab-build-", dir=args.db.parent) as temp:
            temp_db = Path(temp) / "eng1_vocabulary.sqlite"
            create_database(temp_db, payload)
            os.replace(temp_db, args.db)
        print(
            f"BUILD PASS db={args.db} words={len(payload['words'])} "
            f"tokens={sum(row['total_count'] for row in payload['words'])} "
            f"db_sha256={sha256_file_path(args.db)} "
            f"content_sha256={static_content_hash(args.db)} "
            f"backup={BACKUP_DB if args.db == DEFAULT_DB else 'none'}"
        )
        return 0
    except Exception as exc:
        print(f"BUILD FAIL {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
