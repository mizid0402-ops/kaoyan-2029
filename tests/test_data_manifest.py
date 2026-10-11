"""Data-version manifest checks.

这是当前数据版本的快照；数据合法增长时只改这里
"""

from __future__ import annotations

# 这是当前数据版本的快照；数据合法增长时只改这里

import json
import sqlite3
import subprocess
import unittest
from pathlib import Path

import yaml

from ky.knowledge import load_knowledge_points
from ky.workspace import load_workspace

REPO_ROOT = Path(__file__).resolve().parents[1]


class DataManifestTest(unittest.TestCase):
    def test_tracked_data_text_files_use_lf(self) -> None:
        try:
            tracked = subprocess.run(
                # review/attach-audit is tracked data too (WP-G1 scope; sol round 121, C3-2).
                ["git", "ls-files", "-z", "--", "data", "review/attach-audit"],
                cwd=REPO_ROOT,
                capture_output=True,
                check=True,
            ).stdout
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            self.skipTest(f"git index unavailable for archived source: {exc}")

        extensions = {".json", ".yaml", ".yml", ".md", ".csv", ".txt"}
        paths = [
            REPO_ROOT / entry.decode("utf-8")
            for entry in tracked.split(b"\0")
            if entry and Path(entry.decode("utf-8")).suffix.lower() in extensions
        ]
        for path in paths:
            with self.subTest(path=path.relative_to(REPO_ROOT)):
                self.assertNotIn(b"\r\n", path.read_bytes())

    def test_current_workspace_data_version(self) -> None:
        workspace = load_workspace(REPO_ROOT / "kaoyan.workspace.yaml")
        view = next(
            view
            for view in workspace.supplementary.values()
            if view.kind == "cross_year_tree"
        )
        effective = load_knowledge_points(
            workspace.require(f"reference.knowledge_trees.{view.subject}")
        )
        supplementary = load_knowledge_points(
            workspace.require(f"supplementary.{view.name}.files.tree")
        )
        effective_ids = {point.knowledge_point_id for point in effective}
        supplementary_ids = {point.knowledge_point_id for point in supplementary}
        index_count = sum(len(paths) for paths in workspace.exam_indexes.values())

        self.assertEqual(len(effective), 403)
        self.assertEqual(len(supplementary), 410)
        self.assertEqual(len(supplementary_ids - effective_ids), 7)
        self.assertEqual(index_count, 11)

    def test_knowledge_tree_shape_counts(self) -> None:
        workspace = load_workspace(REPO_ROOT / "kaoyan.workspace.yaml")
        math1 = next(
            load_knowledge_points(path)
            for subject, path in workspace.knowledge_trees.items()
            if workspace.subject_profiles[subject].tree_grammar == "named_chapters"
        )
        eng1 = next(
            load_knowledge_points(path)
            for subject, path in workspace.knowledge_trees.items()
            if workspace.subject_profiles[subject].tree_grammar == "flat"
        )
        self.assertEqual(
            {scope: sum(point.scope == scope for point in math1)
             for scope in ("subject", "chapter", "section", "item")},
            {"subject": 3, "chapter": 22, "section": 44, "item": 123},
        )
        self.assertEqual(len(math1), 192)
        self.assertEqual(
            {scope: sum(point.scope == scope for point in eng1)
             for scope in ("section", "item")},
            {"section": 13, "item": 11},
        )
        self.assertEqual(len(eng1), 24)

    def test_weighted_tree_counts(self) -> None:
        workspace = load_workspace(REPO_ROOT / "kaoyan.workspace.yaml")
        tree_path = next(
            path for subject, path in workspace.knowledge_trees.items()
            if workspace.subject_profiles[subject].domain_segment
        )
        path = tree_path.with_name("knowledge_tree_weighted.yaml")
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        items = doc["items"]
        relation_counts = {
            "kept": sum(item["baseline_relation"] == "kept" for item in items),
            "new_vs_baseline": sum(
                item["baseline_relation"] == "new_vs_baseline" for item in items
            ),
        }
        evidence_counts: dict[str, int] = {}
        for item in items:
            tag = item["evidence_tag"]
            evidence_counts[tag] = evidence_counts.get(tag, 0) + 1

        self.assertEqual(len(items), 410)
        self.assertEqual(relation_counts, {"kept": 403, "new_vs_baseline": 7})
        self.assertEqual(evidence_counts, {
            "dual_source_exact": 315,
            "structural_equivalent": 65,
            "candidate_recent_new": 7,
            "single_source_unverified": 8,
            "text_layer_ocr_risk": 8,
            "legacy_only_pending": 7,
        })

    def test_netem_database_counts(self) -> None:
        workspace = load_workspace(REPO_ROOT / "kaoyan.workspace.yaml")
        with sqlite3.connect(workspace.vocabulary_db) as conn:
            word_count = conn.execute("SELECT COUNT(*) FROM words").fetchone()[0]
            source_count = conn.execute(
                "SELECT COUNT(*) FROM source_entries WHERE source_id=?",
                ("netem-5530-wordfreq",),
            ).fetchone()[0]
        self.assertEqual(word_count, 3409)
        self.assertEqual(source_count, 5530)

    def test_registered_exam_index_counts(self) -> None:
        workspace = load_workspace(REPO_ROOT / "kaoyan.workspace.yaml")
        counts = []
        for paths in workspace.exam_indexes.values():
            for path in paths:
                entries = json.loads(path.read_text(encoding="utf-8"))["entries"]
                choice_count = sum(
                    entry["question_type"] == "single_choice" for entry in entries
                )
                essay_count = sum(
                    entry["question_type"] == "comprehensive_application"
                    for entry in entries
                )
                assigned_count = sum(
                    entry["knowledge_point_weights"] is not None for entry in entries
                )
                counts.append(
                    (len(entries), choice_count, essay_count, assigned_count)
                )

        self.assertEqual(counts, [
            (47, 40, 7, 47), (47, 40, 7, 47), (47, 40, 7, 47), (47, 40, 7, 47),
            (22, 10, 6, 22), (22, 10, 6, 22), (22, 10, 6, 22), (22, 10, 6, 22),
            (52, 40, 0, 52), (52, 40, 0, 52), (52, 40, 0, 52),
        ])


if __name__ == "__main__":
    unittest.main()
