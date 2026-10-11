"""Round-24: tests for the 408 multi-source weighted knowledge tree.

Covers structural integrity of the emitted YAML plus mutation tests that
prove the validator actually rejects a corrupted tree instead of rubber
stamping anything shaped like YAML. Every mutation test operates on an
in-memory / temp-file copy only; the real tree file's sha256 is recorded
before and re-checked after the whole suite to prove it was never touched.
"""
from __future__ import annotations

import copy
import hashlib
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import yaml
from tests._resources import require_path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import validate_weighted_tree as validator  # noqa: E402

WEIGHTED_TREE_PATH = ROOT / "data/structured_materials/cs408/knowledge_tree_weighted.yaml"
BASELINE_TREE_PATH = ROOT / "data/structured_materials/cs408/knowledge_tree.yaml"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_temp_doc(doc: dict) -> Path:
    fd, name = tempfile.mkstemp(suffix=".yaml")
    path = Path(name)
    path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    import os
    os.close(fd)
    return path


class WeightedTreeStructureTest(unittest.TestCase):
    """The tree that actually ships must be internally valid."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.original_sha = file_sha256(WEIGHTED_TREE_PATH)
        cls.doc = validator.load_doc(WEIGHTED_TREE_PATH)

    def test_file_has_not_been_corrupted_by_this_test_module(self) -> None:
        # Guard that runs first (alphabetically 'a' < others isn't guaranteed
        # by unittest, so this also re-checked in tearDownClass).
        self.assertEqual(file_sha256(WEIGHTED_TREE_PATH), self.original_sha)

    def test_real_file_passes_validation(self) -> None:
        self._require_registered_sources()
        errors = validator.validate(self.doc)
        self.assertEqual(errors, [])

    def test_validator_cli_succeeds_on_registered_weighted_tree(self) -> None:
        self._require_registered_sources()
        self._require_source_b()
        output = io.StringIO()
        with redirect_stdout(output):
            result = validator.main(["--tree", str(WEIGHTED_TREE_PATH)])
        self.assertEqual(result, 0)
        self.assertIn("VALID:", output.getvalue())

    def test_validator_cli_rejects_approved_status(self) -> None:
        doc = copy.deepcopy(self.doc)
        doc["items"][0]["status"] = "approved"
        output = io.StringIO()
        with patch.object(validator, "load_doc", return_value=doc), patch.object(
            validator, "validate_alias_provenance", return_value=[]
        ), redirect_stdout(output):
            result = validator.main(["--tree", str(WEIGHTED_TREE_PATH)])
        self.assertEqual(result, 1)
        self.assertIn("status=approved is forbidden", output.getvalue())

    def test_validator_cli_preserves_dual_error_order_and_diagnostics(self) -> None:
        doc = copy.deepcopy(self.doc)
        node = doc["items"][0]
        node["status"] = "approved"
        node["sources"] = []
        expected_errors = [
            f"items[{node['knowledge_point_id']}]: status 'approved' not in "
            "['extracted', 'reviewed']",
            f"items[{node['knowledge_point_id']}]: status=approved is forbidden for "
            "AI-generated trees",
            f"items[{node['knowledge_point_id']}]: sources must be a non-empty list",
            f"items[{node['knowledge_point_id']}]: source_count={node['source_count']} != len(sources)=0",
        ]
        with patch.object(validator, "_validate_sources_registry"):
            self.assertEqual(validator.validate(doc), expected_errors)
        output = io.StringIO()
        with patch.object(validator, "load_doc", return_value=doc), patch.object(
            validator, "validate_alias_provenance", return_value=[]
        ), patch.object(validator, "_validate_sources_registry"), redirect_stdout(output):
            result = validator.main(["--tree", str(WEIGHTED_TREE_PATH)])
        self.assertEqual(result, 1)
        self.assertIn("status=approved is forbidden", output.getvalue())
        self.assertIn("sources must be a non-empty list", output.getvalue())

    def test_real_file_alias_provenance_passes(self) -> None:
        self._require_source_b()
        errors = validator.validate_alias_provenance(self.doc)
        self.assertEqual(errors, [])

    def test_baseline_relation_counts_match_items(self) -> None:
        counts = {
            relation: sum(item["baseline_relation"] == relation for item in self.doc["items"])
            for relation in ("kept", "new_vs_baseline")
        }
        self.assertEqual(self.doc["baseline_relation_counts"], counts)

    def test_weighted_tree_ids_are_a_superset_of_the_baseline_tree(self) -> None:
        baseline_ids = {n["knowledge_point_id"] for n in validator.load_yaml(BASELINE_TREE_PATH)}
        weighted_ids = {n["knowledge_point_id"] for n in self.doc["items"]}
        self.assertTrue(baseline_ids.issubset(weighted_ids))
        self.assertEqual(weighted_ids - baseline_ids, {
            node["knowledge_point_id"]
            for node in self.doc["items"]
            if node["baseline_relation"] == "new_vs_baseline"
        })

    def test_no_node_uses_status_approved(self) -> None:
        statuses = {n["status"] for n in self.doc["items"]}
        self.assertEqual(statuses, {"extracted"})

    def test_evidence_tags_are_known_and_counted(self) -> None:
        from collections import Counter
        counts = Counter(n["evidence_tag"] for n in self.doc["items"])
        self.assertEqual(sum(counts.values()), len(self.doc["items"]))
        self.assertEqual(set(counts), {
            "dual_source_exact", "structural_equivalent", "candidate_recent_new",
            "single_source_unverified", "text_layer_ocr_risk", "legacy_only_pending",
        })

    def test_ocr_risk_aliases_preserve_the_uncorrected_source_b_text(self) -> None:
        """The notice promises aliases are never silently rewritten -- check
        at least the known OCR-risk markers actually survive verbatim."""
        markers = ("Cach ", "页椎", "l/o", "1/O", "软件 次结构", "宽带、码元")
        ocr_nodes = [n for n in self.doc["items"] if n["evidence_tag"] == "text_layer_ocr_risk"]
        self.assertTrue(ocr_nodes)
        found_markers = set()
        for n in ocr_nodes:
            for alias in n["aliases"]:
                for m in markers:
                    if m in alias["text"]:
                        found_markers.add(m)
        self.assertTrue(found_markers, "no raw OCR marker text survived into any alias")

    @classmethod
    def tearDownClass(cls) -> None:
        assert file_sha256(WEIGHTED_TREE_PATH) == cls.original_sha, (
            "the weighted tree file changed on disk during this test module"
        )

    def _registered_source_path(self, tag: str) -> Path:
        path = Path(self.doc["sources_registry"][tag]["path"])
        return path if path.is_absolute() else ROOT / path

    def _require_registered_sources(self) -> None:
        for tag in ("A", "B"):
            require_path(
                self,
                self._registered_source_path(tag),
                "按 data/materials.yaml 对应的 cs408 来源记录重新获取",
            )

    def _require_source_b(self) -> None:
        require_path(
            self,
            self._registered_source_path("B"),
            "按 data/materials.yaml 对应的 2022 大纲来源重新获取",
        )


class MutationTest(unittest.TestCase):
    """Prove the validator actually rejects corruption, using scratch copies
    only. Each test records the real file's hash before and after."""

    def setUp(self) -> None:
        self.original_sha = file_sha256(WEIGHTED_TREE_PATH)
        self.doc = copy.deepcopy(validator.load_doc(WEIGHTED_TREE_PATH))
        self.temp_paths: list[Path] = []

    def tearDown(self) -> None:
        for p in self.temp_paths:
            p.unlink(missing_ok=True)
        self.assertEqual(
            file_sha256(WEIGHTED_TREE_PATH), self.original_sha,
            "mutation test touched the real weighted tree file on disk",
        )

    def _validate_mutated(self, doc: dict) -> list[str]:
        return validator.validate(doc)

    def test_wrong_weight_for_evidence_tag_is_rejected(self) -> None:
        node = next(n for n in self.doc["items"] if n["evidence_tag"] == "dual_source_exact")
        node["weight"] = 0.42
        errors = self._validate_mutated(self.doc)
        self.assertTrue(any("weight=0.42" in e for e in errors), errors)

    def test_source_count_mismatch_after_removing_a_source_is_rejected(self) -> None:
        node = next(n for n in self.doc["items"] if len(n["sources"]) >= 2)
        node["sources"].pop()  # source_count now stale
        errors = self._validate_mutated(self.doc)
        self.assertTrue(any("source_count" in e for e in errors), errors)

    def test_status_approved_is_rejected(self) -> None:
        node = self.doc["items"][0]
        node["status"] = "approved"
        errors = self._validate_mutated(self.doc)
        self.assertTrue(any("approved" in e for e in errors), errors)

    def test_fabricated_alias_text_is_rejected(self) -> None:
        source_path = Path(self.doc["sources_registry"]["B"]["path"])
        if not source_path.is_absolute():
            source_path = ROOT / source_path
        require_path(
            self,
            source_path,
            "按 data/materials.yaml 对应的 2022 大纲来源重新获取",
        )
        node = self.doc["items"][0]
        node.setdefault("aliases", []).append({
            "text": "这段别名文字完全不存在于任何来源文本之中的胡编乱造内容",
            "source": "B",
            "note": "fabricated_for_test",
        })
        errors = validator.validate_alias_provenance(self.doc)
        self.assertTrue(any("not found in source B" in e for e in errors), errors)

    def test_duplicate_knowledge_point_id_is_rejected(self) -> None:
        dup = copy.deepcopy(self.doc["items"][0])
        self.doc["items"].append(dup)
        errors = self._validate_mutated(self.doc)
        self.assertTrue(any("duplicate knowledge_point_id" in e for e in errors), errors)

    def test_missing_baseline_id_is_rejected(self) -> None:
        # Drop a node that belongs to the baseline (kept relation) to prove
        # the superset check fires.
        idx = next(i for i, n in enumerate(self.doc["items"]) if n.get("baseline_relation") == "kept")
        del self.doc["items"][idx]
        errors = self._validate_mutated(self.doc)
        self.assertTrue(any("missing" in e and "baseline" in e for e in errors), errors)

    def test_mutated_copy_written_to_temp_file_round_trips_and_still_fails(self) -> None:
        """Exercise the on-disk load path too (not just the in-memory dict),
        via a scratch temp file that gets deleted in tearDown."""
        node = next(n for n in self.doc["items"] if n["evidence_tag"] == "legacy_only_pending")
        node["weight"] = 0.99
        temp_path = write_temp_doc(self.doc)
        self.temp_paths.append(temp_path)
        reloaded = validator.load_doc(temp_path)
        errors = validator.validate(reloaded)
        self.assertTrue(any("weight=0.99" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
