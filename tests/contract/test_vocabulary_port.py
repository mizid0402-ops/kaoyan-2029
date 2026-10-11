"""Contract tests for the replaceable vocabulary reference database."""

from __future__ import annotations

import shutil
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

import yaml

from ky.models import ContractError
from ky.schedule.vocab_channel import (
    VocabChannelError,
    preview_batch,
    remaining_pool,
)
from ky.workspace import load_workspace

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY = REPO_ROOT / "kaoyan.workspace.yaml"


def _registry_with_vocab(directory: Path, vocab_rel: str) -> Path:
    document = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    document["reference"]["vocabulary_db"] = vocab_rel
    registry = directory / "kaoyan.workspace.yaml"
    registry.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False),
                        encoding="utf-8", newline="\n")
    return registry


class VocabularyPortContractTest(unittest.TestCase):
    def test_replacement_reads_another_registered_relative_path(self) -> None:
        original_workspace = load_workspace(REGISTRY)
        original_db = original_workspace.require("reference.vocabulary_db")
        original_count = remaining_pool(db=original_db)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            moved_rel = "replacement/vocabulary.sqlite"
            moved = root / moved_rel
            moved.parent.mkdir()
            shutil.copyfile(original_db, moved)
            registry = _registry_with_vocab(root, moved_rel)
            replacement_workspace = load_workspace(registry)
            self.assertEqual(replacement_workspace.require("reference.vocabulary_db"), moved)
            replaced_db = replacement_workspace.require("reference.vocabulary_db")
            self.assertEqual(remaining_pool(db=replaced_db), original_count)

    def test_delivery_log_is_ignored_unless_caller_supplies_word_forms(self) -> None:
        workspace = load_workspace(REGISTRY)
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "vocabulary.sqlite"
            shutil.copyfile(workspace.require("reference.vocabulary_db"), db)
            with closing(sqlite3.connect(db)) as con:
                con.row_factory = sqlite3.Row
                top = con.execute(
                    "SELECT w.word_id, w.word_form FROM v_top_words AS w "
                    "WHERE w.is_stopword=0 AND w.in_directions=0 "
                    "ORDER BY w.family_total_count DESC, w.year_count DESC, w.word_form ASC"
                ).fetchone()
                eligible_count = con.execute(
                    "SELECT COUNT(*) FROM v_top_words "
                    "WHERE is_stopword=0 AND in_directions=0"
                ).fetchone()[0]
                con.execute("DELETE FROM delivery_log")
                con.execute(
                    "INSERT INTO delivery_log(delivered_on, word_id, batch_index) "
                    "VALUES (?, ?, ?)",
                    ("2098-01-01", top["word_id"], 1),
                )
                con.commit()

            word = top["word_form"]
            self.assertEqual(remaining_pool(db=db), eligible_count)
            self.assertEqual(remaining_pool(db=db, delivered={word}), eligible_count - 1)
            self.assertIn(word, preview_batch(1, db=db).words)
            self.assertNotIn(word, preview_batch(1, db=db, delivered={word}).words)

    def test_words_view_without_v_top_words_is_a_supported_minimal_database(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "minimum.sqlite"
            with closing(sqlite3.connect(db)) as con:
                con.execute(
                    "CREATE TABLE source_words "
                    "(word_id TEXT PRIMARY KEY, word_form TEXT NOT NULL)"
                )
                words = [("w1", "alpha"), ("w2", "beta"), ("w3", "gamma")]
                con.executemany("INSERT INTO source_words VALUES (?, ?)", words)
                con.execute("CREATE VIEW words AS SELECT word_id, word_form FROM source_words")
                con.commit()
            self.assertEqual(remaining_pool(db=db), len(words))

    def test_supported_relation_names_work_as_tables_and_views(self) -> None:
        for relation in ("v_top_words", "words"):
            for relation_kind in ("table", "view"):
                with self.subTest(relation=relation, kind=relation_kind), \
                        tempfile.TemporaryDirectory() as td:
                    db = Path(td) / "relation.sqlite"
                    with closing(sqlite3.connect(db)) as con:
                        con.execute(
                            "CREATE TABLE source_words "
                            "(word_id TEXT, word_form TEXT)"
                        )
                        con.execute(
                            "INSERT INTO source_words VALUES ('one', 'alpha')"
                        )
                        if relation_kind == "table":
                            con.execute(
                                f"CREATE TABLE {relation} "
                                "(word_id TEXT, word_form TEXT)"
                            )
                            con.execute(
                                f"INSERT INTO {relation} VALUES ('one', 'alpha')"
                            )
                        else:
                            con.execute(
                                f"CREATE VIEW {relation} AS "
                                "SELECT word_id, word_form FROM source_words"
                            )
                        con.commit()
                    self.assertEqual(remaining_pool(db=db), 1)
                    self.assertEqual(preview_batch(1, db=db).words, ("alpha",))

    def test_missing_required_relation_columns_raise_named_adapter_error(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "malformed.sqlite"
            with closing(sqlite3.connect(db)) as con:
                con.execute("CREATE TABLE words (id INTEGER)")
                con.commit()
            with self.assertRaises(VocabChannelError) as caught:
                remaining_pool(db=db)
            self.assertIn("words", str(caught.exception))
            self.assertIn("word_id", str(caught.exception))

    def test_missing_registered_database_is_a_contract_violation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            registry = _registry_with_vocab(Path(td), "moved-but-missing.sqlite")
            workspace = load_workspace(registry)
            with self.assertRaises(ContractError):
                workspace.require("reference.vocabulary_db")
            with self.assertRaises(VocabChannelError):
                remaining_pool(db=workspace.vocabulary_db)


if __name__ == "__main__":
    unittest.main()
