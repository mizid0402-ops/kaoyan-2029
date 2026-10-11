"""M7 vocabulary reference adapter; see ``contracts/vocabulary.md``.

Public interface: ``remaining_pool``, ``preview_batch`` and
``import_delivery_baseline_with_dates``. Delivery state is supplied by M13 callers.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "VocabBatch",
    "VocabChannelError",
    "import_delivery_baseline_with_dates",
    "preview_batch",
    "remaining_pool",
]



class VocabChannelError(RuntimeError):
    """Raised when the vocabulary database is missing or lacks the expected shape."""


@dataclass(frozen=True)
class VocabBatch:
    """A day's vocabulary allocation, sized by the caller."""

    words: tuple[str, ...]
    minutes: int
    per_word_minutes: float
    lemma_families: int = 0
    note: str = ""

    @property
    def count(self) -> int:
        return len(self.words)


def _connect(db: Path) -> sqlite3.Connection:
    if not db.is_file():
        raise VocabChannelError(f"vocabulary database not found: {db}")
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise VocabChannelError(f"vocabulary database: {exc}") from exc
    con.row_factory = sqlite3.Row
    return con


def _select_relation(
    con: sqlite3.Connection,
    *,
    exclude_stopwords: bool,
    exclude_directions: bool,
) -> tuple[str, frozenset[str], list[str], list[Any]]:
    """Return a supported relation and its optional filters after validating its shape."""
    try:
        names = {
            row["name"]
            for row in con.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('view','table')"
            )
        }
    except sqlite3.Error as exc:
        raise VocabChannelError(f"v_top_words/words: {exc}") from exc
    relation = next((name for name in ("v_top_words", "words") if name in names), None)
    if relation is None:
        raise VocabChannelError("v_top_words/words: neither supported relation exists")
    try:
        columns = frozenset(
            row["name"] for row in con.execute(f"PRAGMA table_info({relation})")
        )
    except sqlite3.Error as exc:
        raise VocabChannelError(f"{relation}: {exc}") from exc
    missing = {"word_id", "word_form"} - columns
    if missing:
        raise VocabChannelError(
            f"{relation}: missing required columns {', '.join(sorted(missing))}"
        )
    filters = []
    if exclude_stopwords and "is_stopword" in columns:
        filters.append("is_stopword = 0")
    if exclude_directions and "in_directions" in columns:
        filters.append("in_directions = 0")
    return relation, columns, filters, []


def _where_clause(filters: list[str]) -> str:
    return " WHERE " + " AND ".join(filters) if filters else ""


def remaining_pool(
    db: Path,
    *,
    exclude_stopwords: bool = True,
    exclude_directions: bool = True,
    delivered: frozenset[str] | set[str] = frozenset(),
) -> int:
    """Count rows available in the registered vocabulary reference database.

    Delivered word forms come from the caller; the reference database stores no learning state.
    The caller decides how many words to take.
    """
    con = _connect(db)
    try:
        relation, _, filters, _ = _select_relation(
            con,
            exclude_stopwords=exclude_stopwords,
            exclude_directions=exclude_directions,
        )

        try:
            clause = _where_clause(filters)
            rows = con.execute(f"SELECT word_form FROM {relation}{clause}").fetchall()
        except sqlite3.Error as exc:
            raise VocabChannelError(f"{relation}: {exc}") from exc
        return sum(row["word_form"] not in delivered for row in rows)
    finally:
        con.close()


def import_delivery_baseline_with_dates(db: Path) -> tuple[tuple[str, str], ...]:
    """Return legacy ``(delivered_on, word_form)`` rows in delivery order, read-only.

    ``data/english_vocabulary/eng1_vocabulary.sqlite`` is frozen (round-37 §6, §8): its recorded
    SHA-256 must never change again, so nothing may write to its ``delivery_log`` table going
    forward. This function is the one-time, read-only bridge for that freeze -- it lets a caller
    seed an external completion-event log (``ky.storage.day_plan_store``) with the words already
    delivered before the freeze, without ever opening the database for writing. It is a plain
    read like :func:`remaining_pool`: no transaction, no INSERT, connected ``mode=ro``.
    """
    con = _connect(db)
    try:
        try:
            tables = {r["name"] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            if "delivery_log" not in tables:
                return ()
            rows = con.execute(
                "SELECT d.delivered_on, w.word_form FROM delivery_log AS d "
                "JOIN words AS w ON w.word_id = d.word_id "
                "ORDER BY d.delivered_on, d.batch_index"
            ).fetchall()
        except sqlite3.Error as exc:
            raise VocabChannelError(f"delivery_log/words: {exc}") from exc
        return tuple((r["delivered_on"], r["word_form"]) for r in rows)
    finally:
        con.close()


def _preview_rows(
    con: sqlite3.Connection,
    relation: str,
    columns: frozenset[str],
    filters: list[str],
    params: list[Any],
    count: int,
    delivered: frozenset[str] | set[str],
) -> list[sqlite3.Row]:
    order_columns = []
    if "family_total_count" in columns:
        order_columns.append("family_total_count DESC")
    if "year_count" in columns:
        order_columns.append("year_count DESC")
    order_columns.append("word_form ASC")
    order = "ORDER BY " + ", ".join(order_columns)
    clause = _where_clause(filters)
    query = f"SELECT * FROM {relation}{clause} {order} LIMIT ? OFFSET ?"
    selected: list[sqlite3.Row] = []
    offset = 0
    try:
        while len(selected) < count:
            page = con.execute(query, (*params, 500, offset)).fetchall()
            if not page:
                break
            selected.extend(row for row in page if row["word_form"] not in delivered)
            offset += len(page)
            if len(page) < 500:
                break
        return selected[:count]
    except sqlite3.Error as exc:
        raise VocabChannelError(f"{relation}: {exc}") from exc


def _make_batch(
    rows: list[sqlite3.Row],
    columns: frozenset[str],
    count: int,
    minutes_per_word: float,
) -> VocabBatch:
    words = tuple(row["word_form"] for row in rows)
    families = len({
        row["lemma"] if "lemma" in columns and row["lemma"] else row["word_form"]
        for row in rows
    })
    shortfall = count - len(words)
    note = ""
    if shortfall > 0:
        note = (
            f"pool exhausted: asked for {count}, only {len(words)} rows were available "
            f"(short by {shortfall})"
        )
    return VocabBatch(
        words=words,
        minutes=int(round(len(words) * minutes_per_word)),
        per_word_minutes=minutes_per_word,
        lemma_families=families,
        note=note,
    )


def preview_batch(
    count: int,
    *,
    minutes_per_word: float = 0.5,
    db: Path,
    exclude_stopwords: bool = True,
    exclude_directions: bool = True,
    delivered: frozenset[str] | set[str] = frozenset(),
) -> VocabBatch:
    """Return the next ``count`` word families and the minutes they cost at ``minutes_per_word``.

    ``count`` is an input, not a default: this function has no opinion about how many words a day
    should contain. ``minutes_per_word`` is likewise declared by the caller, because the real cost
    depends on how the learner studies (recognition vs production) and should be calibrated from
    observed data rather than assumed.

    ``delivered`` contains the word forms already present in learning state.
    """
    if count < 0:
        raise VocabChannelError(f"count must be >= 0, got {count}")
    if minutes_per_word < 0:
        raise VocabChannelError(f"minutes_per_word must be >= 0, got {minutes_per_word}")
    if count == 0:
        return VocabBatch(words=(), minutes=0, per_word_minutes=minutes_per_word,
                          note="zero words requested")
    con = _connect(db)
    try:
        relation, cols, filters, params = _select_relation(
            con,
            exclude_stopwords=exclude_stopwords,
            exclude_directions=exclude_directions,
        )
        rows = _preview_rows(
            con,
            relation,
            cols,
            filters,
            params,
            count,
            delivered,
        )
        return _make_batch(rows, cols, count, minutes_per_word)
    finally:
        con.close()
