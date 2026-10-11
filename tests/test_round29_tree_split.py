"""Round-29: tests for the CS408 tree split (main table + agreement side table).

Covers the round-29 task's completion criteria:
  1. verify_tree.py passes contract/hashes/quote_ref on the main table.
  2. The main table's node-id set is a strict superset of the baseline's
     (403 kept + 7 new), and the diff is exactly the expected 7 ids.
  3. The agreement table's source_support values are pixel-identical to the
     historical knowledge_tree_weighted.yaml's weight values for the shared
     403+... nodes (nothing drifted during the split).
  4. The agreement table's own validator (schema + id cross-reference +
     re-derived source_support) passes on the real files.
  5. Mutation tests: corrupting a source sha256, an agreement source_support,
     or adding an unknown id to the agreement table must each be rejected --
     with the real files' sha256 proven unchanged before and after.

The verifier now recognizes CS408's embedded ``chapter-NN`` convention as a
separate strict tree shape. Both the pristine baseline and the multisource
main table therefore have to pass the complete verifier, not merely fail in
the same way.
"""
from __future__ import annotations

import copy
import hashlib
import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import validate_supplementary_agreement as agreement_validator  # noqa: E402
from archive.round29_build_tree_split import build as build_split  # noqa: E402
import archive.round29_build_tree_split as tree_split_builder  # noqa: E402
from tree_source_support import derive_source_support  # noqa: E402
from tests._resources import require_path

MAIN_TREE_PATH = ROOT / "data/structured_materials/cs408/knowledge_tree_multisource.yaml"
AGREEMENT_PATH = ROOT / "data/structured_materials/cs408/knowledge_tree_agreement.yaml"
BASELINE_TREE_PATH = ROOT / "data/structured_materials/cs408/knowledge_tree.yaml"
WEIGHTED_TREE_PATH = ROOT / "data/structured_materials/cs408/knowledge_tree_weighted.yaml"
VERIFY_TREE = ROOT / "tools/verify_tree.py"

def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def require_main_table_sources(testcase_or_none) -> None:
    for node in load_yaml(MAIN_TREE_PATH):
        for source in node.get("sources", []):
            path = Path(source["path"])
            if not path.is_absolute():
                path = ROOT / path
            require_path(
                testcase_or_none,
                path,
                "按 data/materials.yaml 或知识树中的来源登记重新获取",
            )


class MainTableVerifyTreeTest(unittest.TestCase):
    """Criterion (1): verify_tree.py on the main table."""

    @classmethod
    def setUpClass(cls) -> None:
        require_main_table_sources(None)
        cls.result = subprocess.run(
            [sys.executable, str(VERIFY_TREE), str(MAIN_TREE_PATH)],
            capture_output=True, text=True, cwd=ROOT,
        )
        cls.baseline_result = subprocess.run(
            [sys.executable, str(VERIFY_TREE), str(BASELINE_TREE_PATH)],
            capture_output=True, text=True, cwd=ROOT,
        )

    def test_contract_hashes_quote_ref_all_pass(self) -> None:
        out = self.result.stdout
        self.assertIn("contract        : OK", out)
        self.assertIn("hashes          : OK", out)
        self.assertIn("quote_ref       : OK", out)

    def test_baseline_and_main_table_both_pass_complete_verifier(self) -> None:
        self.assertEqual(self.baseline_result.returncode, 0, self.baseline_result.stdout)
        self.assertEqual(self.result.returncode, 0, self.result.stdout)
        self.assertIn("ALL CHECKS PASSED", self.baseline_result.stdout)
        self.assertIn("ALL CHECKS PASSED", self.result.stdout)


class SupersetRelationTest(unittest.TestCase):
    """Criterion (2): main table ids are a superset of the baseline's."""

    def test_main_table_is_403_kept_plus_7_new(self) -> None:
        baseline_ids = {n["knowledge_point_id"] for n in load_yaml(BASELINE_TREE_PATH)}
        main_ids = {n["knowledge_point_id"] for n in load_yaml(MAIN_TREE_PATH)}
        self.assertTrue(baseline_ids.issubset(main_ids))
        self.assertEqual(len(main_ids), len(baseline_ids) + 7)

    def test_the_7_new_ids_match_the_historical_weighted_tree(self) -> None:
        """The 7 new-vs-baseline ids must be exactly the same 7 the round-24
        weighted tree already identified (reproducible diff, not a new set)."""
        old_ids = {
            n["knowledge_point_id"] for n in load_yaml(WEIGHTED_TREE_PATH)["items"]
            if n["baseline_relation"] == "new_vs_baseline"
        }
        baseline_ids = {n["knowledge_point_id"] for n in load_yaml(BASELINE_TREE_PATH)}
        main_ids = {n["knowledge_point_id"] for n in load_yaml(MAIN_TREE_PATH)}
        new_ids = main_ids - baseline_ids
        self.assertEqual(new_ids, old_ids)
        self.assertEqual(len(new_ids), 7)


class SourceSupportUnchangedTest(unittest.TestCase):
    """Criterion (3): agreement table's source_support == historical weight,
    for all 410 nodes, with zero drift."""

    def test_all_410_values_identical_to_the_historical_weight(self) -> None:
        old_by_id = {n["knowledge_point_id"]: n["weight"] for n in load_yaml(WEIGHTED_TREE_PATH)["items"]}
        new_by_id = {n["knowledge_point_id"]: n["source_support"] for n in load_yaml(AGREEMENT_PATH)["items"]}
        self.assertEqual(set(old_by_id), set(new_by_id))
        mismatches = {pid: (old_by_id[pid], new_by_id[pid]) for pid in old_by_id if old_by_id[pid] != new_by_id[pid]}
        self.assertEqual(mismatches, {})


class AgreementValidatorRealFileTest(unittest.TestCase):
    """Criterion (4): the agreement table's own independent validator."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.main_sha = file_sha256(MAIN_TREE_PATH)
        cls.agreement_sha = file_sha256(AGREEMENT_PATH)
        cls.doc = agreement_validator.load_agreement()
        cls.main_counts = agreement_validator.load_main_source_counts()

    def test_real_files_pass(self) -> None:
        errors = agreement_validator.validate(self.doc, self.main_counts)
        self.assertEqual(errors, [])

    def test_agreement_validator_cli_succeeds_on_registered_files(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            result = agreement_validator.main()
        self.assertEqual(result, 0)
        self.assertIn("VALID:", output.getvalue())

    def test_agreement_validator_cli_rejects_source_support_error(self) -> None:
        doc = copy.deepcopy(self.doc)
        doc["items"][0]["source_support"] = 0.42
        output = io.StringIO()
        with patch.object(agreement_validator, "load_agreement", return_value=doc), patch.object(
            agreement_validator, "load_main_source_counts", return_value=self.main_counts
        ), redirect_stdout(output):
            result = agreement_validator.main()
        self.assertEqual(result, 1)
        self.assertIn("source_support=0.42", output.getvalue())

    @classmethod
    def tearDownClass(cls) -> None:
        assert file_sha256(MAIN_TREE_PATH) == cls.main_sha, "main table changed on disk during this test module"
        assert file_sha256(AGREEMENT_PATH) == cls.agreement_sha, "agreement table changed on disk during this test module"


class ReproducibilityTest(unittest.TestCase):
    """Criterion (3, cont'd): re-running the builder against the same inputs
    reproduces the same items, byte-for-byte in content (timestamps in the
    agreement doc's own top-level metadata are the sole intentional
    exception -- item-level content carries no wall-clock timestamps)."""

    def test_build_is_deterministic_across_two_runs(self) -> None:
        for path in (
            tree_split_builder.SOURCE_A_PATH,
            tree_split_builder.SOURCE_B_RAW_PATH,
            tree_split_builder.SOURCE_B_TEXT_PATH,
            tree_split_builder.SOURCE_C_PATH,
        ):
            require_path(
                self,
                path,
                "按 data/materials.yaml 或知识树中的来源登记重新获取",
            )
        main_1, agreement_1 = build_split()
        main_2, agreement_2 = build_split()
        self.assertEqual(main_1, main_2)
        self.assertEqual(agreement_1, agreement_2)


class MutationTest(unittest.TestCase):
    """Criterion (5): corruption must be rejected, and must never touch the
    real committed files."""

    def setUp(self) -> None:
        self.main_sha = file_sha256(MAIN_TREE_PATH)
        self.agreement_sha = file_sha256(AGREEMENT_PATH)
        self.main_items = copy.deepcopy(load_yaml(MAIN_TREE_PATH))
        self.agreement_doc = copy.deepcopy(agreement_validator.load_agreement())
        self.main_counts = agreement_validator.load_main_source_counts()
        self.temp_paths: list[Path] = []

    def tearDown(self) -> None:
        for p in self.temp_paths:
            p.unlink(missing_ok=True)
        self.assertEqual(file_sha256(MAIN_TREE_PATH), self.main_sha, "mutation test touched the real main table")
        self.assertEqual(file_sha256(AGREEMENT_PATH), self.agreement_sha, "mutation test touched the real agreement table")

    def _write_temp_yaml(self, data) -> Path:
        fd, name = tempfile.mkstemp(suffix=".yaml")
        import os
        os.close(fd)
        path = Path(name)
        path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        self.temp_paths.append(path)
        return path

    def test_corrupted_source_sha256_is_rejected_by_verify_tree(self) -> None:
        require_main_table_sources(self)
        node = next(n for n in self.main_items if len(n["sources"]) >= 1)
        node["sources"][0] = dict(node["sources"][0])
        node["sources"][0]["sha256"] = "0" * 64
        temp_path = self._write_temp_yaml(self.main_items)
        # A mutated copy is an unregistered candidate tree, so it names its subject (WP-H2).
        result = subprocess.run(
            [sys.executable, str(VERIFY_TREE), str(temp_path), "--subject", "cs408"],
            capture_output=True, text=True, cwd=ROOT,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("sha256 mismatch", result.stdout)

    def test_wrong_source_support_is_rejected_by_agreement_validator(self) -> None:
        node = next(n for n in self.agreement_doc["items"] if n["evidence_tag"] == "dual_source_exact")
        node["source_support"] = 0.42
        errors = agreement_validator.validate(self.agreement_doc, self.main_counts)
        self.assertTrue(any("source_support=0.42" in e for e in errors), errors)

    def test_unknown_id_in_agreement_table_is_rejected(self) -> None:
        fabricated = copy.deepcopy(self.agreement_doc["items"][0])
        fabricated["knowledge_point_id"] = "cs408.does-not-exist-anywhere"
        self.agreement_doc["items"].append(fabricated)
        errors = agreement_validator.validate(self.agreement_doc, self.main_counts)
        self.assertTrue(any("not found in main table" in e for e in errors), errors)

    def test_source_count_drift_from_main_table_is_rejected(self) -> None:
        node = next(n for n in self.agreement_doc["items"] if n["source_count"] == 2)
        node["source_count"] = 99
        errors = agreement_validator.validate(self.agreement_doc, self.main_counts)
        self.assertTrue(any("source_count=99" in e for e in errors), errors)

    def test_missing_id_from_agreement_table_is_rejected(self) -> None:
        del self.agreement_doc["items"][0]
        errors = agreement_validator.validate(self.agreement_doc, self.main_counts)
        self.assertTrue(any("missing" in e and "id" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
