"""Round-29: prove the extracted source_support formula reproduces every
existing weight value, and rejects anything it hasn't seen.

The hard gate from review/rounds/round-29-tree-split-task.md step 2: feed the
existing (evidence_tag, source_count, match_kind) of all 410 nodes in the
round-24 weighted tree into derive_source_support() and it must reproduce
every recorded weight, with zero mismatches.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from tree_source_support import (  # noqa: E402
    KNOWN_COMBINATIONS,
    UnknownSourceSupportCombination,
    derive_source_support,
)

WEIGHTED_TREE_PATH = ROOT / "data/structured_materials/cs408/knowledge_tree_weighted.yaml"


class ReproduceAllExistingWeightsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        doc = yaml.safe_load(WEIGHTED_TREE_PATH.read_text(encoding="utf-8"))
        cls.items = doc["items"]

    def test_reproduces_all_weight_values(self) -> None:
        mismatches = []
        for node in self.items:
            got = derive_source_support(node["evidence_tag"], node["source_count"], node["match_kind"])
            if got != node["weight"]:
                mismatches.append((node["knowledge_point_id"], node["weight"], got))
        self.assertEqual(mismatches, [], f"{len(mismatches)} node(s) did not reproduce: {mismatches[:10]}")

    def test_every_combination_seen_in_the_data_is_declared_known(self) -> None:
        seen = {(n["evidence_tag"], n["source_count"], n["match_kind"]) for n in self.items}
        self.assertEqual(seen, KNOWN_COMBINATIONS)


class RejectsUnknownCombinationsTest(unittest.TestCase):
    def test_unknown_tag_is_rejected(self) -> None:
        with self.assertRaises(UnknownSourceSupportCombination):
            derive_source_support("not_a_real_tag", 2, "exact")

    def test_known_tag_with_wrong_source_count_is_rejected(self) -> None:
        with self.assertRaises(UnknownSourceSupportCombination):
            derive_source_support("dual_source_exact", 1, "exact")

    def test_known_tag_with_wrong_match_kind_is_rejected(self) -> None:
        with self.assertRaises(UnknownSourceSupportCombination):
            derive_source_support("legacy_only_pending", 1, "exact")

    def test_ocr_risk_requires_a_known_match_kind(self) -> None:
        with self.assertRaises(UnknownSourceSupportCombination):
            derive_source_support("text_layer_ocr_risk", 2, "only_b")


if __name__ == "__main__":
    unittest.main()
