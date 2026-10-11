"""Knowledge-tree port contract for reader and mutation boundaries."""

from __future__ import annotations

import contextlib
import io
import shutil
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import yaml

from ky.knowledge import (
    ACTOR_DETERMINISTIC_SCRIPT,
    KnowledgePointError,
    apply_deterministic_frequency,
    learnable_tree,
    load_knowledge_points,
    load_knowledge_points_from_text,
    nearest_ancestor_with_scope,
    parent_id,
    tree_parent,
)
from ky.knowledge.tree_grammar import TreeGrammarError, select_tree_grammar
from ky.models import load_config
from ky.projection import build_projection
from ky.schedule.state_snapshot import build_snapshot
from ky.workspace import load_workspace
from tools.verify_tree import main as verify_tree
from tests._resources import require_path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "kaoyan.workspace.yaml"
CONFIG_PATH = ROOT / "tests/fixtures/config/config-minimal.yaml"


def _copy_registered_file(root: Path, source: str) -> str:
    relative = Path("copied") / source
    destination = root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / source, destination)
    return relative.as_posix()


def _clone_workspace(root: Path) -> Path:
    document = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
    reference = document["reference"]
    original_effective = dict(reference["knowledge_trees"])
    copied_effective: dict[str, str] = {}
    for subject, source in list(reference["knowledge_trees"].items()):
        reference["knowledge_trees"][subject] = _copy_registered_file(root, source)
        copied_effective[subject] = reference["knowledge_trees"][subject]
    for subject, record in document["reference"].get("syllabus_versions", {}).items():
        for version, source in list(record["versions"].items()):
            if source == original_effective.get(subject):
                record["versions"][version] = copied_effective[subject]
            else:
                record["versions"][version] = _copy_registered_file(root, source)
    for subject, sources in list(reference["exam_indexes"].items()):
        reference["exam_indexes"][subject] = [
            _copy_registered_file(root, source) for source in sources
        ]
    for field in ("topic_weights", "vocabulary_db", "weight_batches"):
        if field in reference:
            reference[field] = _copy_registered_file(root, reference[field])
    for name, view in document.get("supplementary", {}).items():
        for role, source in list(view["files"].items()):
            view["files"][role] = _copy_registered_file(root, source)
    projection = document.get("projection")
    if isinstance(projection, str):
        document["projection"] = "output/projection.sqlite"
    registry = root / "kaoyan.workspace.yaml"
    registry.write_text(
        yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return registry


def _select_test_tree(workspace_path: Path) -> tuple[str, Path]:
    workspace = load_workspace(workspace_path)
    configured = {subject.subject_id for subject in load_config(CONFIG_PATH).subjects}
    subject = next(
        subject_id
        for subject_id in workspace.knowledge_trees
        if subject_id in configured
    )
    return subject, workspace.require(f"reference.knowledge_trees.{subject}")


def _with_frequency(tree_path: Path, *, computed_by: str) -> None:
    raw = yaml.safe_load(tree_path.read_text(encoding="utf-8"))
    entries = raw["items"] if isinstance(raw, dict) else raw
    entries[0]["frequency"] = {
        "value": 2,
        "basis": "contract reader parity",
        "computed_by": computed_by,
        "as_of": "2026-09-25",
    }
    tree_path.write_text(
        yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


class KnowledgeTreePortContractTests(unittest.TestCase):
    def test_named_requirements_accepts_only_direct_numbered_items(self) -> None:
        grammar = select_tree_grammar("named_chapters")
        valid = [
            SimpleNamespace(knowledge_point_id="s.d.ch01.chapter", scope="chapter"),
            SimpleNamespace(knowledge_point_id="s.d.ch01.content", scope="section"),
            SimpleNamespace(knowledge_point_id="s.d.ch01.requirements", scope="section"),
            SimpleNamespace(
                knowledge_point_id="s.d.ch01.requirements.item-01", scope="item"
            ),
        ]
        self.assertEqual(grammar.structural_failures(valid), [])

        missing_parent = [
            valid[0],
            valid[1],
            SimpleNamespace(
                knowledge_point_id="s.d.ch01.requirements.item-01", scope="item"
            ),
        ]
        self.assertTrue(
            any(
                "item must be a direct child" in failure
                for failure in grammar.structural_failures(missing_parent)
            )
        )

        under_content = [
            *valid[:-1],
            SimpleNamespace(knowledge_point_id="s.d.ch01.content.item-01", scope="item"),
        ]
        self.assertTrue(
            any(
                "item must be a direct child" in failure
                for failure in grammar.structural_failures(under_content)
            )
        )

    def test_math1_learnable_leaves_are_content_sections_and_requirement_items(self) -> None:
        workspace = load_workspace(REGISTRY_PATH)
        tree_path = workspace.knowledge_trees["math1"]
        points = load_knowledge_points(tree_path)
        result = learnable_tree(points, "named_chapters")
        content_sections = [
            point for point in points
            if point.scope == "section" and point.knowledge_point_id.endswith(".content")
        ]
        item_nodes = [point for point in points if point.scope == "item"]
        chapter_count = sum(point.scope == "chapter" for point in points)
        expected = {
            point.knowledge_point_id for point in (*content_sections, *item_nodes)
        }
        self.assertEqual(len(content_sections), chapter_count)
        self.assertEqual(set(result.leaves), expected)
        requirements = [
            point for point in points
            if point.knowledge_point_id.endswith(".requirements")
        ]
        for section in requirements:
            self.assertTrue(
                any(
                    result.parents[point_id] == section.knowledge_point_id
                    for point_id in result.leaves
                ),
                section.knowledge_point_id,
            )

    def test_tree_parent_resolves_grammar_specific_syllabus_parents(self) -> None:
        cases = (
            ("named_chapters", "s.d.ch01.content.topic",
             {"s.d.subject", "s.d.ch01.chapter", "s.d.ch01.content",
              "s.d.ch01.content.topic"}, "s.d.ch01.content"),
            ("numbered_chapters", "s.d.chapter-01.section-01.item-01",
             {"s.d.subject", "s.d.chapter-01", "s.d.chapter-01.section-01",
              "s.d.chapter-01.section-01.item-01"}, "s.d.chapter-01.section-01"),
            ("flat", "s.d.subject.item", {"s.d.subject", "s.d.subject.item"},
             "s.d.subject"),
        )
        for grammar, point_id, ids, expected in cases:
            with self.subTest(grammar=grammar):
                points = {item: object() for item in ids}
                self.assertEqual(tree_parent(point_id, points, grammar), expected)

        named = {item: object() for item in (
            "s.d.subject", "s.d.ch01.chapter", "s.d.ch01.content",
        )}
        self.assertEqual(
            tree_parent("s.d.ch01.content", named, "named_chapters"),
            "s.d.ch01.chapter",
        )
        self.assertEqual(tree_parent("s.d.subject", named, "named_chapters"), None)
        self.assertEqual(
            tree_parent("root.without.parent", {"root.without.parent": object()}, "flat"),
            None,
        )
        with self.assertRaises(TreeGrammarError):
            tree_parent("x.y", {"x.y": object()}, "unknown")

    def test_tree_parent_keeps_parent_id_results_unchanged(self) -> None:
        expected = {
            "a": None, "a.b": "a", "a.b.c": "a.b", "a.b.c.d": "a.b.c",
            "x.y.chapter-01": None,
            "x.y.chapter-01.section-02": "x.y.chapter-01",
            "loose.branch.item": "loose.branch",
        }
        ids = set(expected) | {"loose.branch"}
        points = {item: object() for item in ids}
        for point_id, parent in expected.items():
            self.assertEqual(parent_id(point_id, ids), parent)
            self.assertEqual(parent_id(point_id, points.keys()), parent)

    def test_parent_id_returns_longest_existing_strict_prefix(self) -> None:
        tree_ids = {"alpha", "alpha.beta", "alpha.beta.item"}
        self.assertEqual(parent_id("alpha.beta.item.leaf", tree_ids), "alpha.beta.item")
        self.assertEqual(parent_id("alpha.beta", tree_ids), "alpha")
        self.assertIsNone(parent_id("alpha", tree_ids))
        self.assertIsNone(parent_id("other.branch", tree_ids))

    def test_parent_id_skips_missing_intermediate_prefix(self) -> None:
        tree_ids = {"x.a.chapter-01", "x.a.chapter-01.section-01.item-01"}
        self.assertEqual(
            parent_id("x.a.chapter-01.section-01.item-01", tree_ids),
            "x.a.chapter-01",
        )

    def test_nearest_ancestor_with_scope_includes_self_and_walks_parents(self) -> None:
        points = {
            "alpha": SimpleNamespace(scope="subject"),
            "alpha.chapter": SimpleNamespace(scope="chapter"),
            "alpha.chapter.section": SimpleNamespace(scope="section"),
            "alpha.chapter.section.item": SimpleNamespace(scope="item"),
        }
        self.assertEqual(
            nearest_ancestor_with_scope(
                "alpha.chapter.section", points, "section"
            ),
            "alpha.chapter.section",
        )
        self.assertEqual(
            nearest_ancestor_with_scope(
                "alpha.chapter.section.item", points, "chapter"
            ),
            "alpha.chapter",
        )
        self.assertIsNone(
            nearest_ancestor_with_scope("unknown.node", points, "chapter")
        )

    def test_nearest_ancestor_with_scope_skips_missing_intermediate_prefix(self) -> None:
        points = {
            "x.a.chapter-01": SimpleNamespace(scope="chapter"),
            "x.a.chapter-01.section-01.item-01": SimpleNamespace(scope="item"),
        }
        self.assertEqual(
            nearest_ancestor_with_scope(
                "x.a.chapter-01.section-01.item-01", points, "chapter"
            ),
            "x.a.chapter-01",
        )

    def test_mapping_schema_version_must_be_integer_one(self) -> None:
        for value in (2, True, "1"):
            with self.subTest(schema_version=value):
                text = yaml.safe_dump({"schema_version": value, "items": []})
                with self.assertRaises(KnowledgePointError) as ctx:
                    load_knowledge_points_from_text(text, source="probe")
                self.assertEqual(ctx.exception.path, "probe.schema_version")

    def _exercise_readers(self, computed_by: str) -> tuple[int, list[str]]:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = _clone_workspace(root)
            subject, tree_path = _select_test_tree(registry)
            _with_frequency(tree_path, computed_by=computed_by)
            workspace = load_workspace(registry)

            snapshot = build_snapshot(
                load_config(CONFIG_PATH), (), today=date(2026, 9, 25),
                vocab_db=root / "missing-vocabulary.sqlite", workspace=workspace,
            )
            snapshot_total = snapshot.subject(subject).tree_total

            projection_path = root / "out.sqlite"
            build_projection(workspace, projection_path)
            with closing(sqlite3.connect(projection_path)) as connection:
                projected_ids = [
                    row[0]
                    for row in connection.execute(
                        "SELECT knowledge_point_id FROM knowledge_points "
                        "WHERE subject_id=? ORDER BY knowledge_point_id",
                        (subject,),
                    )
                ]
            expected_ids = [
                point.knowledge_point_id for point in load_knowledge_points(tree_path)
            ]
            self.assertEqual(set(projected_ids), set(expected_ids))

            for point in load_knowledge_points(tree_path):
                for source in point.sources:
                    source_path = ROOT / source["path"]
                    require_path(
                        self,
                        source_path,
                        "按 data/materials.yaml 或知识树中的来源登记重新获取",
                    )

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = verify_tree([
                    str(tree_path), "--workspace", str(registry), "--root", str(ROOT)
                ])
            self.assertEqual(result, 0, output.getvalue())
            self.assertIn(f"({len(expected_ids)} nodes validated", output.getvalue())
            self.assertTrue(load_knowledge_points(tree_path)[0].frequency)
            return snapshot_total.count, projected_ids

    def test_readers_accept_same_tree_with_deterministic_frequency(self) -> None:
        count, projected_ids = self._exercise_readers(
            ACTOR_DETERMINISTIC_SCRIPT
        )
        self.assertEqual(count, len(projected_ids))

    def test_all_readers_reject_invalid_frequency_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = _clone_workspace(root)
            subject, tree_path = _select_test_tree(registry)
            _with_frequency(tree_path, computed_by="human")
            workspace = load_workspace(registry)

            with self.assertRaises(KnowledgePointError):
                build_snapshot(
                    load_config(CONFIG_PATH), (), today=date(2026, 9, 25),
                    vocab_db=root / "missing-vocabulary.sqlite", workspace=workspace,
                )
            with self.assertRaises(KnowledgePointError):
                build_projection(workspace, root / "out.sqlite")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = verify_tree([
                    str(tree_path), "--workspace", str(registry), "--root", str(ROOT)
                ])
            self.assertEqual(result, 2, output.getvalue())
            self.assertIn("frequency.computed_by", output.getvalue())

    def test_frequency_mutation_rejects_non_deterministic_writer(self) -> None:
        source = {
            "path": "materials/outline.pdf",
            "sha256": "a" * 64,
            "locator": {"page": 1},
        }
        raw = {
            "knowledge_point_id": "test.node",
            "title": "Node",
            "status": "raw",
            "source_kind": "manual",
            "sources": [source],
            "transition_history": [],
        }
        with self.assertRaises(KnowledgePointError):
            apply_deterministic_frequency(
                raw, 1, basis="test", as_of="2026-09-25", writer="human"
            )


if __name__ == "__main__":
    unittest.main()
