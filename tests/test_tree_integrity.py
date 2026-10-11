"""Integrity tests for the committed knowledge trees and the ledger's tier fixes.

These are regression locks on work that was previously only *live-verified* by
`tools/verify_tree.py`. Without them, nothing in the suite would notice if a tree's
recorded `sha256` drifted from its source file, if a `quote_ref` stopped resolving,
or if a bookseller page silently regained a syllabus-authoritative tier.

Two things are deliberately asserted here that the reviewer forced into the ledger:

  * no source holding `SYLLABUS_AUTHORITATIVE_TIERS` may be a bookseller page — the
    round-2 review found `math1/eng1-outline-pubinfo-2026` (书店商品页) holding
    `official_publisher`, i.e. booksellers with the right to define the syllabus;
  * the user-supplied third-party index must NOT be registered as a material, because
    it carries no `source_url`/`publisher`/`isbn` and registering it would mean
    inventing provenance.
"""

from __future__ import annotations

import hashlib
import html
import re
import unittest
from pathlib import Path

from ky.knowledge import load_knowledge_points
from ky.ledger import load_ledger
from ky.ledger.material import SYLLABUS_AUTHORITATIVE_TIERS, VALID_SOURCE_TIERS
from tests._resources import require_path

ROOT = Path(__file__).resolve().parents[1]

TREES = {
    "math1": ROOT / "data" / "structured_materials" / "math1" / "knowledge_tree.yaml",
    "eng1": ROOT / "data" / "structured_materials" / "eng1" / "knowledge_tree.yaml",
    "cs408": ROOT / "data" / "structured_materials" / "cs408" / "knowledge_tree.yaml",
}
LEDGER = ROOT / "data" / "materials.yaml"

# The attachment's sha256, quoted by the user and recomputed by the orchestrator.
USER_INDEX_SHA = "c99635318bb22179351edc6bb07d1f0883aa8403b73c9d14f3e9896ca6d072a0"


def normalise(text: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", "", text)


def source_text(path: Path) -> str:
    """Mirror the extractor's view: comments/script/style stripped, tags to newlines."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    raw = re.sub(r"<!--.*?-->", " ", raw, flags=re.S)
    raw = re.sub(r"<script.*?</script>", " ", raw, flags=re.I | re.S)
    raw = re.sub(r"<style.*?</style>", " ", raw, flags=re.I | re.S)
    return normalise(html.unescape(re.sub(r"<[^>]+>", "\n", raw)))


def require_tree_sources(testcase: unittest.TestCase) -> None:
    """Keep real-source checks strict when assets exist, skippable when omitted."""
    checked: set[Path] = set()
    for tree_path in TREES.values():
        for point in load_knowledge_points(tree_path):
            for source in point.sources:
                path = ROOT / source["path"]
                if path in checked:
                    continue
                checked.add(path)
                require_path(
                    testcase,
                    path,
                    "按 data/materials.yaml 或该知识树的来源登记重新获取",
                )


class TreeIntegrityTest(unittest.TestCase):
    """Every committed tree must be internally verifiable, not just loadable."""

    def test_every_tree_loads_through_the_contract(self) -> None:
        for name, path in TREES.items():
            with self.subTest(tree=name):
                self.assertTrue(path.is_file(), f"{name} tree missing at {path}")
                points = load_knowledge_points(path)
                self.assertGreater(len(points), 0)
                ids = [p.knowledge_point_id for p in points]
                self.assertEqual(len(ids), len(set(ids)), f"{name}: duplicate knowledge_point_id")

    def test_recorded_sha256_matches_the_source_bytes(self) -> None:
        require_tree_sources(self)
        checked = 0
        for name, path in TREES.items():
            for point in load_knowledge_points(path):
                for source in point.sources:
                    resolved = ROOT / source["path"]
                    with self.subTest(tree=name, node=point.knowledge_point_id):
                        self.assertTrue(resolved.is_file(), f"missing source {source['path']}")
                        actual = hashlib.sha256(resolved.read_bytes()).hexdigest()
                        self.assertEqual(
                            actual, source["sha256"],
                            f"{point.knowledge_point_id}: recorded hash != bytes on disk",
                        )
                    checked += 1
        self.assertGreater(checked, 0)

    def test_every_quote_ref_locates_in_its_declared_source(self) -> None:
        require_tree_sources(self)
        cache: dict[str, str] = {}
        for name, path in TREES.items():
            for point in load_knowledge_points(path):
                for source in point.sources:
                    key = source["path"]
                    if key not in cache:
                        cache[key] = source_text(ROOT / key)
                    quote = source["locator"].get("quote_ref")
                    with self.subTest(tree=name, node=point.knowledge_point_id, quote=quote):
                        self.assertTrue(quote, "locator.quote_ref is required")
                        self.assertIn(
                            normalise(quote), cache[key],
                            f"{point.knowledge_point_id}: quote_ref not found in {key}",
                        )

    def test_ai_built_trees_stay_at_extracted(self) -> None:
        """extracted -> reviewed requires a human actor, so AI work must not pass it."""
        for name in ("math1", "eng1"):
            for point in load_knowledge_points(TREES[name]):
                with self.subTest(tree=name, node=point.knowledge_point_id):
                    self.assertEqual(point.status, "extracted")
                    self.assertIsNone(point.frequency)
                    self.assertEqual(tuple(point.evidence), ())
                    actors = {entry["actor"] for entry in point.transition_history}
                    self.assertEqual(actors, {"ai"})

    def test_math1_shape_is_locked(self) -> None:
        points = load_knowledge_points(TREES["math1"])
        subjects = {p.title for p in points if p.scope == "subject"}
        self.assertEqual(subjects, {"高等数学", "线性代数", "概率论与数理统计"})
        # every chapter carries exactly the two blocks we claim to model
        chapters = [p.knowledge_point_id[: -len(".chapter")] for p in points if p.scope == "chapter"]
        ids = {p.knowledge_point_id for p in points}
        for base in chapters:
            self.assertIn(base + ".content", ids)
            self.assertIn(base + ".requirements", ids)

    def test_eng1_shape_is_locked(self) -> None:
        points = load_knowledge_points(TREES["eng1"])
        ids = {p.knowledge_point_id for p in points}
        # the structure tree must still be a structure tree, not a fake catalog
        self.assertFalse([p for p in points if p.scope == "chapter"])
        for required in (
            "eng1.paper.part1", "eng1.paper.part2", "eng1.paper.part3", "eng1.paper.part4",
            "eng1.appendix.vocabulary", "eng1.appendix.affixes", "eng1.appendix.past-papers",
        ):
            self.assertIn(required, ids)


class LedgerTierRegressionTest(unittest.TestCase):
    """Lock the round-2 corrections so they cannot silently come back."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.materials = {m.resource_id: m for m in load_ledger(LEDGER)}

    def test_every_source_tier_is_known(self) -> None:
        for rid, material in self.materials.items():
            with self.subTest(resource=rid):
                self.assertIn(material.provenance.source_tier, VALID_SOURCE_TIERS)

    def test_bookseller_pages_may_not_define_syllabus(self) -> None:
        """The review found bookseller product pages holding official_publisher."""
        for rid in (
            "math1-outline-pubinfo-2026",
            "eng1-outline-pubinfo-2026",
            "eng1-exam-analysis-2026",
        ):
            material = self.materials[rid]
            with self.subTest(resource=rid):
                self.assertEqual(material.provenance.source_tier, "trusted_reprint")
                self.assertFalse(material.provenance.may_define_syllabus())
                self.assertFalse(material.may_be_structured())

    def test_syllabus_authoritative_rows_are_official_only(self) -> None:
        allowed = {
            "cs408-outline-notice-2022",       # 教育部教育考试院公告页
            "cs408-outline-book-2022",         # 高教社正式出版物
            "cs408-outline-book-2026",         # 人教社正式出版物
            "math1-outline-notice-2022",       # 教育部教育考试院公告页
            "math1-outline-book-2026",         # 人教社正式出版物
            "cs408-outline-analysis-hep-2026",  # 高教社官方产品页
            "math1-outline-pubinfo-hep-2027",   # 高教社 2027 大纲书目页（sol 256，无正文）
            "math1-outline-list-neea-round256",  # 教育部教育考试院大纲列表页（sol 256）
            "policy-scoring-rubric-not-publishable",  # 法规约束记录，非考纲内容
        }
        actual = {
            rid for rid, m in self.materials.items()
            if m.provenance.source_tier in SYLLABUS_AUTHORITATIVE_TIERS
        }
        self.assertEqual(actual, allowed)

    def test_user_index_is_not_registered_as_a_material(self) -> None:
        """It has no provenance; registering it would mean inventing a publisher."""
        for rid, material in self.materials.items():
            with self.subTest(resource=rid):
                self.assertNotEqual(material.storage.sha256, USER_INDEX_SHA)
        self.assertNotIn("user-index-math1-eng1-2026", self.materials)

    def test_transcript_sources_are_registered_and_local(self) -> None:
        for rid in (
            "math1-outline-transcript-eol-2022",
            "math1-outline-transcript-newdu-2026",
            "eng1-outline-transcript-eol-2022",
        ):
            material = self.materials[rid]
            resource_path = Path(material.storage.path)
            if not resource_path.is_absolute():
                resource_path = ROOT / resource_path
            require_path(
                self,
                resource_path,
                f"按 data/materials.yaml 的 {rid} 记录重新获取",
            )
            with self.subTest(resource=rid):
                self.assertEqual(material.storage.mode, "local_file")
                self.assertTrue(material.storage.has_verifiable_bytes())
                self.assertEqual(material.provenance.source_tier, "trusted_reprint")
                self.assertTrue(material.verify_bytes(ROOT), "byte integrity failed")

    def test_exam_material_may_never_be_displayed_or_redistributed(self) -> None:
        """The real boundary: the project may hold a user's own copy for its own
        metadata work, but it must never display or redistribute真题/答案原文.

        (An earlier version of this test asserted `may_store is False` for every
        `past_exam_paper` row, which was simply wrong — the 408 PDFs are the user's
        own copies, legally held, and the project needs their bytes to compute the
        sha256 it cites. Re-deriving the assertion from the ledger beat assuming.)
        """
        seen = 0
        for rid, material in self.materials.items():
            if material.material_kind != "past_exam_paper":
                continue
            seen += 1
            with self.subTest(resource=rid):
                self.assertFalse(material.rights.may_display)
                self.assertFalse(material.rights.may_redistribute)
        self.assertGreater(seen, 0, "no past_exam_paper rows found to check")

    def test_link_only_exam_rows_hold_no_bytes(self) -> None:
        """A link-only row must not be structurable: it has no verifiable bytes."""
        row = self.materials["ref-exam-material-links-2026"]
        self.assertEqual(row.storage.mode, "remote_reference")
        self.assertFalse(row.storage.has_verifiable_bytes())
        self.assertFalse(row.may_be_structured())
        self.assertFalse(row.rights.may_store)


if __name__ == "__main__":
    unittest.main()
