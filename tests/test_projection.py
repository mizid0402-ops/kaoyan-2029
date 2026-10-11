"""Regression locks for the read-only projection.

The projection is a derived view, so what matters is that it stays (a) rebuildable and
deterministic, (b) faithful to its inputs, and (c) honest about the fact that no knowledge tree is
approved. If a future change makes it embed a build timestamp, silently drop master-data gaps, or
start reporting extracted counts as authoritative coverage, one of these must go red.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock

from ky.knowledge import load_knowledge_points
from ky.projection import PROJECTION_SCHEMA_VERSION, ProjectionInUseError, build_projection
from ky.workspace import load_workspace

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = load_workspace(REPO_ROOT / "kaoyan.workspace.yaml")
_TEMP: tempfile.TemporaryDirectory[str] | None = None
_DB: Path


def setUpModule() -> None:
    """Build only in a temporary directory; never touch the checked-in projection."""
    global _TEMP, _DB
    _TEMP = tempfile.TemporaryDirectory()
    _DB = Path(_TEMP.name) / "projection.sqlite"
    build_projection(WORKSPACE, _DB)


def tearDownModule() -> None:
    if _TEMP is not None:
        _TEMP.cleanup()


def _content_hash(p: Path) -> str:
    """Hash table contents in a stable order, so it cannot depend on file layout or rowid drift."""
    con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    h = hashlib.sha256()
    names = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    for name in names:
        h.update(name.encode())
        cols = [r[1] for r in con.execute(f"PRAGMA table_info({name})")]
        h.update(",".join(cols).encode())
        order = "key" if name == "projection_meta" else "rowid"
        for row in con.execute(f"SELECT * FROM {name} ORDER BY {order}"):
            h.update(repr(row).encode())
    con.close()
    return h.hexdigest()


class ProjectionShapeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.con = sqlite3.connect(f"file:{_DB}?mode=ro", uri=True)
        self.addCleanup(self.con.close)

    def test_expected_tables_exist(self) -> None:
        names = {r[0] for r in self.con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        for t in ("knowledge_points", "supplementary_views", "supplementary_knowledge_points",
                  "exam_questions", "question_knowledge_weights", "topic_weights", "projection_meta"):
            self.assertIn(t, names)

    def test_all_three_trees_are_present(self) -> None:
        got = {r[0] for r in self.con.execute(
            "SELECT DISTINCT subject_id FROM knowledge_points")}
        self.assertEqual(got, {"cs408", "math1", "eng1"})

    def test_cs408_domain_is_a_separate_column_not_a_subject(self) -> None:
        # cs408 node ids carry ds/co/os/cn as their second segment. Treating that as the subject
        # once split one subject into four and made the projection disagree with the config.
        subjects = {r[0] for r in self.con.execute(
            "SELECT DISTINCT subject_id FROM knowledge_points WHERE subject_id LIKE '%s%'")}
        self.assertNotIn("ds", subjects)
        domains = {r[0] for r in self.con.execute(
            "SELECT DISTINCT domain FROM knowledge_points WHERE subject_id='cs408'")}
        self.assertEqual(domains, {"ds", "co", "os", "cn"})

    def test_every_question_weight_resolves_to_a_real_knowledge_point(self) -> None:
        orphan = self.con.execute("""
            SELECT COUNT(*) FROM question_knowledge_weights w
            LEFT JOIN knowledge_points k ON k.knowledge_point_id = w.knowledge_point_id
            WHERE k.knowledge_point_id IS NULL""").fetchone()[0]
        self.assertEqual(orphan, 0)

    def test_node_count_matches_the_source_trees(self) -> None:
        expected = sum(len(load_knowledge_points(WORKSPACE.require(f"reference.knowledge_trees.{subject}")))
                       for subject in WORKSPACE.knowledge_trees)
        got = self.con.execute("SELECT COUNT(*) FROM knowledge_points").fetchone()[0]
        self.assertEqual(got, expected)


class TreeStatusHonestyTest(unittest.TestCase):
    """The trees are all 'extracted'; the projection must not pretend otherwise."""

    def test_no_knowledge_point_claims_approval(self) -> None:
        con = sqlite3.connect(f"file:{_DB}?mode=ro", uri=True)
        self.addCleanup(con.close)
        rows = dict(con.execute("SELECT tree_status, COUNT(*) FROM knowledge_points GROUP BY 1"))
        self.assertEqual(set(rows), {"extracted"},
                         f"unexpected statuses: {rows}")

    def test_every_row_carries_a_tree_status(self) -> None:
        con = sqlite3.connect(f"file:{_DB}?mode=ro", uri=True)
        self.addCleanup(con.close)
        missing = con.execute(
            "SELECT COUNT(*) FROM knowledge_points WHERE tree_status IS NULL OR tree_status=''"
        ).fetchone()[0]
        self.assertEqual(missing, 0)

    def test_meta_records_the_limitation(self) -> None:
        con = sqlite3.connect(f"file:{_DB}?mode=ro", uri=True)
        self.addCleanup(con.close)
        notice = con.execute(
            "SELECT value FROM projection_meta WHERE key='content_notice'").fetchone()[0]
        self.assertIn("extracted", notice)


class DeterminismTest(unittest.TestCase):
    def test_rebuild_produces_identical_content(self) -> None:
        before = _content_hash(_DB)
        build_projection(WORKSPACE, _DB)
        after = _content_hash(_DB)
        self.assertEqual(before, after,
                         "two builds of the same inputs must be byte-identical in content")

    def test_meta_records_input_hashes(self) -> None:
        import json
        con = sqlite3.connect(f"file:{_DB}?mode=ro", uri=True)
        self.addCleanup(con.close)
        raw = con.execute("SELECT value FROM projection_meta WHERE key='inputs'").fetchone()[0]
        inputs = json.loads(raw)
        self.assertTrue(inputs, "input hashes must be recorded for provenance")
        for path, digest in inputs.items():
            self.assertRegex(digest, r"^[0-9a-f]{64}$", path)

    def test_schema_version_is_recorded(self) -> None:
        con = sqlite3.connect(f"file:{_DB}?mode=ro", uri=True)
        self.addCleanup(con.close)
        got = con.execute(
            "SELECT value FROM projection_meta WHERE key='projection_schema_version'").fetchone()[0]
        self.assertEqual(int(got), PROJECTION_SCHEMA_VERSION)


class MasterDataGapsStayVisibleTest(unittest.TestCase):
    """Known-unset marks must remain unset, not be filled in with a guess."""

    def test_2026_408_essay_marks_are_still_null(self) -> None:
        con = sqlite3.connect(f"file:{_DB}?mode=ro", uri=True)
        self.addCleanup(con.close)
        n_null = con.execute(
            "SELECT COUNT(*) FROM exam_questions WHERE exam_year=2026 AND subject_id='cs408' "
            "AND marks IS NULL").fetchone()[0]
        self.assertEqual(n_null, 7,
                         "the seven 2026 comprehensive questions have no verified marks; "
                         "they must stay NULL rather than be invented")

    def test_2025_math1_marks_are_still_null_where_unverified(self) -> None:
        con = sqlite3.connect(f"file:{_DB}?mode=ro", uri=True)
        self.addCleanup(con.close)
        n_null = con.execute(
            "SELECT COUNT(*) FROM exam_questions WHERE exam_year=2025 AND subject_id='math1' "
            "AND marks IS NULL").fetchone()[0]
        self.assertEqual(n_null, 4)


class FreshEnvironmentRebuildTest(unittest.TestCase):
    def test_missing_projection_is_built_from_sources(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "fresh" / "projection.sqlite"
            self.assertFalse(out.exists())
            summary = build_projection(WORKSPACE, out)
            self.assertTrue(out.is_file())
            expected = sum(len(load_knowledge_points(path)) for path in WORKSPACE.knowledge_trees.values())
            expected_questions = sum(
                len(json.loads(path.read_text(encoding="utf-8"))["entries"])
                for paths in WORKSPACE.exam_indexes.values()
                for path in paths
            )
            self.assertEqual(summary["knowledge_points"], expected)
            with closing(sqlite3.connect(f"file:{out}?mode=ro", uri=True)) as con:
                self.assertEqual(
                    con.execute("SELECT COUNT(*) FROM exam_questions").fetchone()[0],
                    expected_questions,
                )

    def test_windows_lock_failure_preserves_old_file_and_explains_remedy(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "projection.sqlite"
            old = b"existing projection"
            out.write_bytes(old)
            with mock.patch("ky.projection.os.replace", side_effect=PermissionError(32, "in use")):
                with self.assertRaisesRegex(ProjectionInUseError, "Stop the Datasette"):
                    build_projection(WORKSPACE, out)
            self.assertEqual(out.read_bytes(), old)
            self.assertFalse(out.with_suffix(".building").exists())


if __name__ == "__main__":
    unittest.main()
