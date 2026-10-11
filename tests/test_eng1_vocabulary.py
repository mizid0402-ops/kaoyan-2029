from __future__ import annotations

import re
import hashlib
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path

import yaml

from tests._resources import require_path

from ky.schedule.completion import CompletionEvent, VocabProgress
from ky.storage.day_plan_store import DayPlanStore


ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "english_vocabulary" / "eng1_vocabulary.sqlite"
BACKUP = ROOT / "data" / "english_vocabulary" / "eng1_vocabulary.v1.sqlite.bak"
DAILY = ROOT / "tools" / "daily_words.py"
BUILD = ROOT / "tools" / "build_eng1_vocabulary.py"
VERIFY = ROOT / "tools" / "verify_eng1_vocabulary.py"


def family_key(row: sqlite3.Row | tuple) -> str:
    word, lemma, confidence = row[0], row[1], row[2]
    return lemma if confidence == "rule" else word


class English1VocabularyRegressionTests(unittest.TestCase):
    def test_v2_schema_family_and_frequency_order(self):
        self.assertTrue(DB.is_file())
        self.assertTrue(BACKUP.is_file())
        conn = sqlite3.connect(DB)
        try:
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertTrue({"words", "occurrences", "stopwords", "meta", "delivery_log"} <= tables)
            word_columns = {row[1] for row in conn.execute("PRAGMA table_info(words)")}
            self.assertTrue({
                "total_count", "year_count", "first_year", "last_year", "is_stopword",
                "in_directions", "lemma", "lemma_confidence", "family_total_count", "pos",
            } <= word_columns)
            occurrence_columns = {row[1] for row in conn.execute("PRAGMA table_info(occurrences)")}
            self.assertIn("is_direction_text", occurrence_columns)
            rows = conn.execute("SELECT family_total_count, total_count, word_form FROM v_top_words").fetchall()
            self.assertEqual(rows, sorted(rows, key=lambda row: (-row[0], -row[1], row[2])))
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM occurrences").fetchone()[0],
                conn.execute("SELECT COUNT(DISTINCT word_id || ':' || source_file || ':' || is_direction_text) FROM occurrences").fetchone()[0],
            )
            self.assertEqual(conn.execute("SELECT value FROM meta WHERE key='build_version'").fetchone()[0], "eng1-vocabulary-v2")
            self.assertGreaterEqual(conn.execute("SELECT COUNT(*) FROM stopwords").fetchone()[0], 150)
        finally:
            conn.close()

    def test_removed_date_option_is_rejected(self):
        # The tool records nothing, so --date had no effect and was removed (sol round 86, R4).
        result = subprocess.run(
            [sys.executable, str(DAILY), "--count", "15", "--date", "2026-09-25"],
            capture_output=True, text=True, encoding="utf-8", check=False,
        )
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("--date", result.stderr)

    def test_default_delivery_is_filtered_idempotent_and_family_sorted(self):
        with tempfile.TemporaryDirectory(prefix="eng1-daily-test-") as temp:
            test_db = Path(temp) / "vocab.sqlite"
            shutil.copy2(DB, test_db)
            conn = sqlite3.connect(test_db)
            conn.execute("DELETE FROM delivery_log")
            conn.commit()
            conn.close()
            command = [sys.executable, str(DAILY), "--db", str(test_db), "--count", "15"]
            first = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=False)
            second = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=False)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(first.stdout, second.stdout)
            word_output = first.stdout.split("vocab:\n", 1)[0]
            lines = [line for line in word_output.splitlines() if line]
            self.assertEqual(len(lines), 15)
            self.assertTrue(all("——" not in line and "(" not in line and ")" not in line for line in lines))
            forbidden = {"text", "answer", "sheet", "following", "directions"}
            self.assertTrue(forbidden.isdisjoint({form for line in lines for form in line.split()}))

            conn = sqlite3.connect(test_db)
            conn.row_factory = sqlite3.Row
            try:
                info = {
                    row["word_form"]: row
                    for row in conn.execute("SELECT word_form, lemma, lemma_confidence, total_count, family_total_count, is_stopword, in_directions FROM words")
                }
                seen_families = set()
                family_totals = []
                for line in lines:
                    forms = line.split()
                    keys = {family_key((info[form]["word_form"], info[form]["lemma"], info[form]["lemma_confidence"])) for form in forms}
                    self.assertEqual(len(keys), 1, line)
                    key = next(iter(keys))
                    self.assertNotIn(key, seen_families, line)
                    seen_families.add(key)
                    self.assertTrue(all(info[form]["is_stopword"] == 0 and info[form]["in_directions"] == 0 for form in forms))
                    family_totals.append(info[forms[0]]["family_total_count"])
                    counts = [info[form]["total_count"] for form in forms]
                    self.assertEqual(counts, sorted(counts, reverse=True))
                self.assertEqual(family_totals, sorted(family_totals, reverse=True))
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM delivery_log").fetchone()[0], 0)
            finally:
                conn.close()

            evidence = subprocess.run(command + ["--show-evidence"], capture_output=True, text=True, encoding="utf-8", check=False)
            self.assertEqual(evidence.returncode, 0, evidence.stderr)
            self.assertIn("——", evidence.stdout)
            self.assertIn("2024/", evidence.stdout)

    def test_fixed_baseline_output_matches_and_new_reader_does_not_write(self):
        baseline_commit = "162a9e1"
        with tempfile.TemporaryDirectory(prefix="eng1-baseline-test-") as temp:
            root = Path(temp)
            baseline_db = root / "baseline.sqlite"
            current_db = root / "current.sqlite"
            shutil.copy2(DB, baseline_db)
            with closing(sqlite3.connect(baseline_db)) as conn, conn:
                conn.execute("DELETE FROM delivery_log")
                rows = conn.execute(
                    "SELECT word_id, word_form, lemma, lemma_confidence FROM words "
                    "WHERE is_stopword=0 AND in_directions=0 "
                    "ORDER BY family_total_count DESC, total_count DESC, word_form ASC"
                ).fetchall()
                picked = []
                groups = set()
                for word_id, word, lemma, confidence in rows:
                    group = lemma if confidence == "rule" else word
                    if group not in groups:
                        picked.append((word_id, word))
                        groups.add(group)
                    if len(picked) == 2:
                        break
                conn.executemany(
                    "INSERT INTO delivery_log(delivered_on, word_id, batch_index) "
                    "VALUES (?, ?, ?)",
                    [("2097-12-31", word_id, index)
                     for index, (word_id, _) in enumerate(picked, start=1)],
                )
            baseline_seed = root / "baseline-seed.sqlite"
            shutil.copy2(baseline_db, baseline_seed)
            shutil.copy2(baseline_seed, current_db)
            with closing(sqlite3.connect(current_db)) as conn, conn:
                conn.execute("DELETE FROM delivery_log")

            old_source = subprocess.run(
                ["git", "show", f"{baseline_commit}:tools/daily_words.py"],
                cwd=ROOT, capture_output=True, check=True,
            ).stdout
            old_blob = subprocess.run(
                ["git", "rev-parse", f"{baseline_commit}:tools/daily_words.py"],
                cwd=ROOT, capture_output=True, text=True, check=True,
            ).stdout.strip()
            source_file = root / "baseline_daily_words.py"
            source_file.write_bytes(old_source)
            actual_blob = subprocess.run(
                ["git", "hash-object", str(source_file)], cwd=ROOT,
                capture_output=True, text=True, check=True,
            ).stdout.strip()
            self.assertEqual(actual_blob, old_blob, "baseline script must be the pinned Git blob")
            self.assertIn(b"INSERT INTO delivery_log", old_source)

            plan_root = root / "state" / "plans"
            store = DayPlanStore(plan_root)
            store.write_completion_event(CompletionEvent(
                day=date(2097, 12, 31),
                vocab=VocabProgress(delivered_words=tuple(word for _, word in picked)),
            ))
            registry = yaml.safe_load((ROOT / "kaoyan.workspace.yaml").read_text(encoding="utf-8"))
            registry["state"]["plans"] = "state/plans"
            registry["reference"]["vocabulary_db"] = "current.sqlite"
            registry_path = root / "kaoyan.workspace.yaml"
            registry_path.write_text(
                yaml.safe_dump(registry, allow_unicode=True, sort_keys=False), encoding="utf-8"
            )

            flag_groups = ((), ("--show-evidence",), ("--include-stopwords",))
            for index, flags in enumerate(flag_groups):
                old_db = root / f"baseline-{index}.sqlite"
                new_db = root / f"current-{index}.sqlite"
                shutil.copy2(baseline_seed, old_db)
                shutil.copy2(current_db, new_db)
                before = hashlib.sha256(new_db.read_bytes()).hexdigest()
                run_date = (date(2098, 1, 1) + timedelta(days=index)).isoformat()
                # The old tool recorded deliveries under --date; the new one records nothing,
                # so --date was removed (sol round 86, R4) and is passed to the old tool only.
                args = ["--count", "15", *flags]
                old = subprocess.run(
                    [sys.executable, str(source_file), "--db", str(old_db),
                     "--date", run_date, *args], cwd=ROOT,
                    capture_output=True, check=False,
                )
                new = subprocess.run(
                    [sys.executable, str(DAILY), "--db", str(new_db),
                     "--workspace", str(registry_path), *args],
                    cwd=ROOT, capture_output=True, check=False,
                )
                self.assertEqual(old.returncode, 0, old.stderr.decode("utf-8", errors="replace"))
                self.assertEqual(new.returncode, 0, new.stderr.decode("utf-8", errors="replace"))
                marker = b"vocab:\r\n  delivered_words:"
                self.assertIn(marker, new.stdout)
                fragment = yaml.safe_load(new.stdout[new.stdout.rfind(b"vocab:"):])
                self.assertEqual(len(fragment["vocab"]["delivered_words"]), 15)
                self.assertEqual(
                    new.stdout[:new.stdout.rfind(b"vocab:")], old.stdout,
                    f"flags={flags!r}; old_args={args!r}; old={old.stdout!r}; "
                    f"new_args={args[2:]!r}; new={new.stdout!r}",
                )
                after = hashlib.sha256(new_db.read_bytes()).hexdigest()
                self.assertEqual(
                    before, after, "daily_words must keep the reference copy byte-identical"
                )

    def test_verifier_deterministic_check_and_mutations(self):
        require_path(
            self,
            Path(tempfile.gettempdir()) / "kaoyan-probe" / "claude2" / "dl" / "bv_e1_2024.pdf",
            "按 data/materials.yaml 的 eng1-paper-2024-bv 记录重新获取",
        )
        build = subprocess.run([sys.executable, str(BUILD), "--check"], capture_output=True, text=True, encoding="utf-8", check=False)
        self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
        verify = subprocess.run([sys.executable, str(VERIFY)], capture_output=True, text=True, encoding="utf-8", check=False)
        self.assertEqual(verify.returncode, 0, verify.stdout + verify.stderr)
        mutation = subprocess.run([sys.executable, str(VERIFY), "--mutation-test"], capture_output=True, text=True, encoding="utf-8", check=False)
        self.assertEqual(mutation.returncode, 0, mutation.stdout + mutation.stderr)
        self.assertEqual(len(re.findall(r"MUTATION PASS (?:in_directions|stopwords_row|lemma_family_count)", mutation.stdout)), 3)
        self.assertIn("restore_sha256=", mutation.stdout)


if __name__ == "__main__":
    unittest.main()
