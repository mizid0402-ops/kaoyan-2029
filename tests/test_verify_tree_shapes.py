"""Focused regression and mutation tests for verify_tree tree-shape rules."""
from __future__ import annotations

import copy
import hashlib
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path

import yaml
from tests._resources import require_path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from verify_tree import (  # noqa: E402
    TreeShapeError,
    _registered_subject,
)
from ky.knowledge.tree_grammar import (
    check_namespace,
    check_syntax,
    chapter_scope_failures,
    select_tree_grammar,
    subject_scope_failures,
)

VERIFY_TREE = ROOT / "tools/verify_tree.py"
CS408_TREE = ROOT / "data/structured_materials/cs408/knowledge_tree.yaml"
CS408_MAIN_TREE = ROOT / "data/structured_materials/cs408/knowledge_tree_multisource.yaml"
MATH1_TREE = ROOT / "data/structured_materials/math1/knowledge_tree.yaml"
ENG1_TREE = ROOT / "data/structured_materials/eng1/knowledge_tree.yaml"


def point(point_id: str, scope: str) -> SimpleNamespace:
    return SimpleNamespace(knowledge_point_id=point_id, scope=scope)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TreeShapeUnitTest(unittest.TestCase):
    def test_syllabus_version_tree_is_registered_for_its_subject(self) -> None:
        version_path = ROOT / "data/structured_materials/cs408/knowledge_tree_2027_probe.yaml"
        workspace = SimpleNamespace(
            knowledge_trees={},
            syllabus_versions={
                "cs408": SimpleNamespace(versions={"2027": version_path})
            },
            supplementary={},
        )
        self.assertEqual(
            _registered_subject(workspace, version_path.resolve()),
            ("cs408", "reference.syllabus_versions.cs408.versions.2027"),
        )

    def test_three_supported_shapes_are_distinct(self) -> None:
        self.assertEqual(select_tree_grammar("numbered_chapters").name, "numbered_chapters")
        self.assertEqual(select_tree_grammar("named_chapters").name, "named_chapters")
        self.assertEqual(select_tree_grammar("flat").name, "flat")

    def test_mixed_namespaces_are_rejected(self) -> None:
        with self.assertRaisesRegex(TreeShapeError, "tree namespace must equal"):
            check_namespace(
                [
                    point("cs408.ds.chapter-01", "chapter"),
                    point("math1.hs.ch01.chapter", "chapter"),
                ],
                "cs408",
            )

    def test_unknown_namespace_is_rejected(self) -> None:
        with self.assertRaisesRegex(TreeShapeError, "tree namespace must equal"):
            check_namespace([point("other.domain.unit-01", "section")], "cs408")

    def test_ambiguous_id_syntax_is_rejected_inside_one_namespace(self) -> None:
        with self.assertRaisesRegex(TreeShapeError, "ambiguous id syntax"):
            check_syntax(
                [
                    point("cs408.ds.chapter-01", "chapter"),
                    point("cs408.ds.synthetic.chapter", "chapter"),
                ],
                select_tree_grammar("numbered_chapters"),
            )

    def test_namespace_and_foreign_syntax_conflict_is_rejected(self) -> None:
        with self.assertRaisesRegex(TreeShapeError, "conflicts with named_chapters id syntax"):
            check_syntax(
                [point("cs408.ds.synthetic.chapter", "chapter")],
                select_tree_grammar("numbered_chapters"),
            )


class ChapterScopeUnitTest(unittest.TestCase):
    def test_chapter_id_with_wrong_scope_is_rejected(self) -> None:
        self.assertEqual(
            chapter_scope_failures(
                [point("cs408.ds.chapter-01", "section")],
                select_tree_grammar("numbered_chapters"),
            ),
            ["cs408.ds.chapter-01: id matches chapter pattern but scope='section'"],
        )

    def test_chapter_scope_with_wrong_id_is_rejected(self) -> None:
        self.assertEqual(
            chapter_scope_failures(
                [point("cs408.ds.section-01", "chapter")],
                select_tree_grammar("numbered_chapters"),
            ),
            [
                "cs408.ds.section-01: scope='chapter' but id does not match "
                "numbered_chapters chapter pattern"
            ],
        )

    def test_math1_chapter_id_with_wrong_scope_is_rejected(self) -> None:
        self.assertEqual(
            chapter_scope_failures(
                [point("math1.hs.ch01.chapter", "section")],
                select_tree_grammar("named_chapters"),
            ),
            ["math1.hs.ch01.chapter: id matches chapter pattern but scope='section'"],
        )

    def test_math1_chapter_scope_with_wrong_id_is_rejected(self) -> None:
        self.assertEqual(
            chapter_scope_failures(
                [point("math1.hs.ch01.content", "chapter")],
                select_tree_grammar("named_chapters"),
            ),
            [
                "math1.hs.ch01.content: scope='chapter' but id does not match "
                "named_chapters chapter pattern"
            ],
        )

    def test_eng1_rejects_any_chapter_scope(self) -> None:
        self.assertEqual(
            chapter_scope_failures(
                [point("eng1.exam.nature", "chapter")],
                select_tree_grammar("flat"),
            ),
            [
                "eng1.exam.nature: scope='chapter' but id does not match "
                "flat chapter pattern"
            ],
        )


class SubjectScopeUnitTest(unittest.TestCase):
    def test_same_parent_subject_peers_are_allowed(self) -> None:
        points = [point("x.d.subject", "subject"), point("x.d.objectives", "subject")]
        self.assertEqual(subject_scope_failures(points), [])

    def test_id_exclusion_does_not_treat_duplicate_object_as_a_child(self) -> None:
        points = [point("x.d.subject", "subject"), point("x.d.subject", "subject")]
        failures = subject_scope_failures(points)
        self.assertEqual(failures, ["x.d.subject: subject node has no descendants"] * 2)

    def test_same_scope_direct_child_is_rejected(self) -> None:
        points = [point("x.d.objectives", "subject"), point("x.d.objectives.child", "subject")]
        failures = subject_scope_failures(points)
        self.assertTrue(any("must be narrower than subject" in item for item in failures))


class VerifierMutationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.protected_trees = (CS408_TREE, CS408_MAIN_TREE, MATH1_TREE, ENG1_TREE)
        self.real_hashes = {path: sha256(path) for path in self.protected_trees}
        self.temp_paths: list[Path] = []

    def tearDown(self) -> None:
        for path in self.temp_paths:
            path.unlink(missing_ok=True)
        self.assertEqual(
            {path: sha256(path) for path in self.protected_trees},
            self.real_hashes,
        )

    def _load(self, path: Path) -> list[dict]:
        return copy.deepcopy(yaml.safe_load(path.read_text(encoding="utf-8")))

    def _verify_mutation(self, source: Path, items: list[dict], message: str) -> None:
        for node in yaml.safe_load(source.read_text(encoding="utf-8")):
            for reference in node.get("sources", []):
                source_path = Path(reference["path"])
                if not source_path.is_absolute():
                    source_path = ROOT / source_path
                require_path(
                    self,
                    source_path,
                    "按 data/materials.yaml 或知识树中的来源登记重新获取",
                )
        original_bytes = source.read_bytes()
        with tempfile.NamedTemporaryFile("wb", suffix=".yaml", delete=False) as handle:
            handle.write(original_bytes)
            path = Path(handle.name)
        self.temp_paths.append(path)
        original_hash = sha256(path)
        path.write_text(
            yaml.safe_dump(items, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        mutated_hash = sha256(path)
        try:
            registry_doc = yaml.safe_load((ROOT / "kaoyan.workspace.yaml").read_text(encoding="utf-8"))
            subject = "cs408" if source in {CS408_TREE, CS408_MAIN_TREE} else "math1"
            with tempfile.TemporaryDirectory() as temporary:
                temporary_root = Path(temporary)
                registered_tree = temporary_root / "mutated.yaml"
                registered_tree.write_bytes(path.read_bytes())
                registry_doc["reference"]["knowledge_trees"][subject] = "mutated.yaml"
                versions = registry_doc["reference"]["syllabus_versions"][subject]["versions"]
                effective_version = next(iter(versions))
                versions[effective_version] = "mutated.yaml"
                registry = temporary_root / "kaoyan.workspace.yaml"
                registry.write_text(
                    yaml.safe_dump(registry_doc, allow_unicode=True, sort_keys=False),
                    encoding="utf-8",
                )
                result = subprocess.run(
                    [
                        sys.executable,
                        str(VERIFY_TREE),
                        str(registered_tree),
                        "--workspace",
                        str(registry),
                        "--root",
                        str(ROOT),
                    ],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                )
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn(message, result.stdout)
        finally:
            path.write_bytes(original_bytes)
        restored_hash = sha256(path)
        self.assertNotEqual(mutated_hash, original_hash)
        self.assertEqual(restored_hash, original_hash)
        print(
            f"MUTATION HASH {self._testMethodName}: "
            f"before={original_hash} mutated={mutated_hash} restored={restored_hash}"
        )

    def test_cs408_all_chapters_deleted_is_rejected(self) -> None:
        items = [node for node in self._load(CS408_TREE) if node["scope"] != "chapter"]
        self._verify_mutation(CS408_TREE, items, "section has no direct chapter-NN ancestor")

    def test_cs408_chapter_scopes_relabelled_is_rejected(self) -> None:
        items = self._load(CS408_TREE)
        for node in items:
            if node["scope"] == "chapter":
                node["scope"] = "section"
        self._verify_mutation(
            CS408_TREE,
            items,
            "id matches chapter pattern but scope='section'",
        )

    def test_cs408_missing_chapter_prefix_is_rejected(self) -> None:
        items = self._load(CS408_TREE)
        chapter = next(node for node in items if node["scope"] == "chapter")
        items.remove(chapter)
        self._verify_mutation(CS408_TREE, items, "section has no direct chapter-NN ancestor")

    def test_mixed_namespace_is_rejected(self) -> None:
        items = self._load(CS408_TREE)
        items[0]["knowledge_point_id"] = items[0]["knowledge_point_id"].replace(
            "cs408", "math1", 1
        )
        self._verify_mutation(CS408_TREE, items, "tree namespace must equal registered subject")

    def test_unknown_namespace_is_rejected(self) -> None:
        items = self._load(CS408_TREE)
        for node in items:
            node["knowledge_point_id"] = node["knowledge_point_id"].replace(
                "cs408", "unknown", 1
            )
        self._verify_mutation(CS408_TREE, items, "tree namespace must equal registered subject")

    def test_math1_missing_content_is_rejected(self) -> None:
        items = self._load(MATH1_TREE)
        chapter_id = next(node["knowledge_point_id"] for node in items if node["scope"] == "chapter")
        content_id = chapter_id.removesuffix(".chapter") + ".content"
        items = [node for node in items if node["knowledge_point_id"] != content_id]
        self._verify_mutation(MATH1_TREE, items, f"missing {content_id}")

    def test_math1_all_chapters_deleted_is_rejected(self) -> None:
        items = [node for node in self._load(MATH1_TREE) if node["scope"] != "chapter"]
        self._verify_mutation(MATH1_TREE, items, "section has no ancestor node")

    def test_math1_required_content_wrong_scope_is_rejected(self) -> None:
        items = self._load(MATH1_TREE)
        chapter_id = next(node["knowledge_point_id"] for node in items if node["scope"] == "chapter")
        content_id = chapter_id.removesuffix(".chapter") + ".content"
        content = next(node for node in items if node["knowledge_point_id"] == content_id)
        content["scope"] = "item"
        self._verify_mutation(
            MATH1_TREE,
            items,
            f"required section {content_id} has scope='item'",
        )

    def test_subject_scope_node_below_cs408_section_is_rejected(self) -> None:
        items = self._load(CS408_TREE)
        section = next(node for node in items if node["scope"] == "section")
        injected = copy.deepcopy(section)
        injected["knowledge_point_id"] = section["knowledge_point_id"] + ".subject-child"
        injected["scope"] = "subject"
        items.append(injected)
        self._verify_mutation(CS408_TREE, items, "must be narrower than chapter")

    def test_ambiguous_cs408_and_math1_markers_are_rejected(self) -> None:
        items = self._load(CS408_TREE)
        chapter = next(node for node in items if node["scope"] == "chapter")
        chapter["knowledge_point_id"] = "cs408.ds.synthetic.chapter"
        self._verify_mutation(CS408_TREE, items, "ambiguous id syntax")


if __name__ == "__main__":
    unittest.main()
