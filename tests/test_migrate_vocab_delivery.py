from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import date
from pathlib import Path
from contextlib import redirect_stdout
from io import StringIO

import yaml

from ky.schedule.completion import CompletionEvent, VocabProgress, parse_completion_event
from ky.storage.day_plan_store import DayPlanStore, StorageError
from tools.archive.migrate_vocab_delivery import main, migrate_delivery

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY = REPO_ROOT / "kaoyan.workspace.yaml"


class MigrateVocabularyDeliveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.db = self.root / "vocabulary.sqlite"
        with closing(sqlite3.connect(self.db)) as con, con:
            con.execute("CREATE TABLE words (word_id TEXT PRIMARY KEY, word_form TEXT NOT NULL)")
            con.execute(
                "CREATE TABLE delivery_log (delivered_on TEXT, word_id TEXT, batch_index INTEGER)"
            )
            con.executemany(
                "INSERT INTO words VALUES (?, ?)",
                (("w1", "abate"), ("w2", "abdicate"), ("w3", "abjure")),
            )
            con.executemany(
                "INSERT INTO delivery_log VALUES (?, ?, ?)",
                (("2026-09-10", "w1", 1), ("2026-09-10", "w2", 2),
                 ("2026-09-11", "w3", 1)),
            )
        document = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
        document["reference"]["vocabulary_db"] = "vocabulary.sqlite"
        document["state"]["plans"] = "state/plans"
        self.registry = self.root / "kaoyan.workspace.yaml"
        self.registry.write_text(
            yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        self.plans = self.root / "state" / "plans"

    def test_dry_run_does_not_write_and_apply_writes_parseable_events(self) -> None:
        with redirect_stdout(StringIO()):
            self.assertEqual(main(["--workspace", str(self.registry)]), 0)
        self.assertFalse(self.plans.exists())

        self.assertEqual(main(["--workspace", str(self.registry), "--apply"]), 0)
        store = DayPlanStore(self.plans)
        first = store.load_completion_event(date(2026, 9, 10))
        second = store.load_completion_event(date(2026, 9, 11))
        self.assertEqual(first.vocab.delivered_words, ("abate", "abdicate"))
        self.assertEqual(second.vocab.delivered_words, ("abjure",))
        self.assertEqual(first.reviews, ())
        first_path = self.plans / "2026-09" / "completion--2026-09-10.yaml"
        raw = yaml.safe_load(first_path.read_text(encoding="utf-8"))
        self.assertEqual(parse_completion_event(raw, source=str(first_path)), first)

    def test_existing_date_is_refused_without_overwrite(self) -> None:
        store = DayPlanStore(self.plans)
        existing = CompletionEvent(
            day=date(2026, 9, 10), vocab=VocabProgress(delivered_words=("prior",))
        )
        store.write_completion_event(existing)
        path = self.plans / "2026-09" / "completion--2026-09-10.yaml"
        before = path.read_bytes()
        with self.assertRaises(StorageError):
            migrate_delivery(self.db, store, apply=True)
        self.assertEqual(path.read_bytes(), before)
        self.assertIsNone(store.load_completion_event(date(2026, 9, 11)))


if __name__ == "__main__":
    unittest.main()
