from __future__ import annotations

import re
import sqlite3
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "english_vocabulary" / "eng1_vocabulary.sqlite"
STRIPPED_JSON = ROOT / "data" / "english_vocabulary" / "netem_wordlist_stripped.json"
VERIFY = ROOT / "tools" / "verify_netem_source.py"
CROSS_VALIDATE = ROOT / "tools" / "netem_cross_validate.py"
SOURCE_ID = "netem-5530-wordfreq"


class NetemSourceTests(unittest.TestCase):
    def test_tables_exist_and_are_independent_of_words_table(self):
        conn = sqlite3.connect(DB)
        try:
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertIn("source_wordlists", tables)
            self.assertIn("source_entries", tables)
            # The words table (exam-derived, three years of past papers) must be
            # untouched by this import: it is a different source and must stay
            # a different table, per the round-21 task's rights/provenance split.
            self.assertEqual(conn.execute("SELECT value FROM meta WHERE key='build_version'").fetchone()[0], "eng1-vocabulary-v2")
            entry_columns = {row[1] for row in conn.execute("PRAGMA table_info(source_entries)")}
            self.assertIn("word_form_norm", entry_columns)
            self.assertIn("rank", entry_columns)
            self.assertNotIn("释义", entry_columns)
        finally:
            conn.close()

    def test_no_gloss_text_stored_anywhere_in_source_entries(self):
        conn = sqlite3.connect(DB)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT word_form_original, word_form_norm, other_spellings FROM source_entries WHERE source_id=?",
                (SOURCE_ID,),
            ).fetchall()
            chinese_pattern = re.compile(r"[一-鿿]")
            for row in rows:
                self.assertIsNone(chinese_pattern.search(row["word_form_original"]))
                self.assertIsNone(chinese_pattern.search(row["word_form_norm"]))
                if row["other_spellings"]:
                    self.assertIsNone(chinese_pattern.search(row["other_spellings"]))
        finally:
            conn.close()

    def test_stripped_json_has_no_definition_field(self):
        self.assertTrue(STRIPPED_JSON.is_file())
        text = STRIPPED_JSON.read_text(encoding="utf-8")
        self.assertNotIn("释义", text)

    def test_verifier_passes_and_mutation_tests_are_all_detected(self):
        verify = subprocess.run([sys.executable, str(VERIFY)], capture_output=True, text=True, encoding="utf-8", check=False)
        self.assertEqual(verify.returncode, 0, verify.stdout + verify.stderr)
        self.assertIn("VERIFY PASS", verify.stdout)

        mutation = subprocess.run(
            [sys.executable, str(VERIFY), "--mutation-test"], capture_output=True, text=True, encoding="utf-8", check=False
        )
        self.assertEqual(mutation.returncode, 0, mutation.stdout + mutation.stderr)
        self.assertEqual(
            len(re.findall(r"MUTATION PASS (?:rank_value|deleted_entry|casefold_key)", mutation.stdout)), 3
        )
        self.assertIn("restore_sha256=", mutation.stdout)
        self.assertIn("baseline_unchanged", mutation.stdout)

    def test_cross_validation_numbers_are_reproducible(self):
        out_path = ROOT / "netem_cross_validate_test_output.txt"
        result = subprocess.run(
            [sys.executable, str(CROSS_VALIDATE), "--out", str(out_path)],
            capture_output=True, text=True, encoding="utf-8", check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        try:
            text = out_path.read_text(encoding="utf-8")
            self.assertIn("netem_distinct_norms=5528", text)
            self.assertIn("overlap_count=", text)
            self.assertIn("reverse_not_in_netem_count=", text)
            self.assertIn("top500_overlap_count=", text)
            self.assertIn("top1000_overlap_count=", text)
            self.assertIn("top2000_overlap_count=", text)
        finally:
            out_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
