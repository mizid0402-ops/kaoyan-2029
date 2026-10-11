"""Regression lock for the 408 question index and its source registration.

The index is the project's first artifact built from a *third-party* exam source, so the
things worth freezing are not just its shape but its restraint:

  * the file exists, parses, and passes the contract verifier;
  * its recorded hashes still equal the bytes of the registered PDFs on disk;
  * it assigns no *bare* (evidence-free) knowledge point while `calibration` says the
    official book is missing -- a knowledge point backed by `knowledge_point_weights`
    (round 15's three-coder, confidence-weighted attribution) is not "bare";
  * every `knowledge_point_weights` distribution sums to ~1.0, its argmax is exactly
    `knowledge_point_id`, and every node id it names is a real node in the cs408 tree;
  * the ledger keeps those two PDFs at `community_archive` with no structuring rights;
  * the free-text escape hatch stays closed (`notes` is null everywhere).

If any of these regress, this fails rather than letting the index quietly claim more
than the evidence supports.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

from tests._resources import require_path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "data" / "exam_questions" / "408_index_2024.json"
LEDGER = ROOT / "data" / "materials.yaml"
PAPER = ROOT / "data" / "raw_materials" / "cs408" / "past_papers_thirdparty" / "408_2024_paper_rebuild.pdf"
ANSWER = ROOT / "data" / "raw_materials" / "cs408" / "quiz_pages" / "cs408_quiz_2024.html"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ExamIndexTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = json.loads(INDEX.read_text(encoding="utf-8"))
        cls.entries = cls.data["entries"]

    def test_contract_verifier_passes(self) -> None:
        require_path(self, PAPER, "按 data/materials.yaml 的 cs408-paper-2024-rebuild 记录重取")
        require_path(self, ANSWER, "按 data/materials.yaml 的 cs408-answer-2024-scan 记录重取")
        proc = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "verify_408_index.py"), str(INDEX)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT,
        )
        self.assertEqual(proc.returncode, 0, f"verifier said:\n{proc.stdout}\n{proc.stderr}")
        self.assertIn("ALL INDEX FILES VERIFIED", proc.stdout)

    def test_shape_and_marks(self) -> None:
        self.assertEqual(
            [e["number"] for e in self.entries], list(range(1, len(self.entries) + 1))
        )
        self.assertEqual(sum(e["marks"] for e in self.entries), 150)
        choice = [e for e in self.entries if e["question_type"] == "single_choice"]
        essay = [e for e in self.entries if e["question_type"] == "comprehensive_application"]
        self.assertEqual(len(choice) + len(essay), len(self.entries))
        for entry in choice:
            self.assertIn(entry["answer"], {"A", "B", "C", "D"})
        for entry in essay:
            self.assertIsNone(entry["answer"])

    def test_no_bare_knowledge_points_before_calibration(self) -> None:
        """`calibration` is still `awaiting_official_book` for this index -- the official
        book still doesn't exist. A *bare* id (no evidence) is still forbidden. An id
        backed by `knowledge_point_weights` (the round-15 three-coder, confidence-weighted
        distribution recorded in data/review_weights/topic_weights.json) is not, because
        that distribution is its own independently-checkable evidence.
        `answer_confidence: official` is still forbidden either way.
        """
        self.assertEqual(self.data["calibration"], "awaiting_official_book")
        for entry in self.entries:
            with self.subTest(question=entry["question_id"]):
                if entry["knowledge_point_id"] is not None:
                    self.assertIsNotNone(
                        entry["knowledge_point_weights"],
                        "a knowledge point set before calibration must be weights-backed",
                    )
                self.assertNotEqual(entry["answer_confidence"], "official")

    def test_knowledge_point_weights_shape(self) -> None:
        """Regression lock for the round-15 write-back (tools/apply_knowledge_weights.py):
        every weighted entry's distribution sums to ~1.0, its argmax is exactly
        knowledge_point_id, and status reflects whether the coders converged on one node
        or spread across several -- the same invariants tools/verify_408_index.py checks,
        locked here independently of that script."""
        assigned = [e for e in self.entries if e["knowledge_point_weights"] is not None]
        self.assertEqual(len(assigned), len(self.entries))
        for entry in assigned:
            with self.subTest(question=entry["question_id"]):
                weights = entry["knowledge_point_weights"]
                self.assertTrue(weights, "distribution must not be empty")
                self.assertTrue(all(w > 0 for w in weights.values()))
                total = sum(weights.values())
                self.assertLess(abs(total - 1.0), 5e-3, f"weights sum to {total}, expected ~1.0")
                primary = max(weights, key=weights.get)
                self.assertEqual(entry["knowledge_point_id"], primary)
                expected_status = "assigned_multi_model" if len(weights) == 1 else "assigned_unreviewed"
                self.assertEqual(entry["knowledge_point_status"], expected_status)

    def test_knowledge_point_ids_are_real_tree_nodes(self) -> None:
        from ky.knowledge.knowledge_point import load_knowledge_points

        tree = ROOT / "data" / "structured_materials" / "cs408" / "knowledge_tree.yaml"
        valid_ids = {p.knowledge_point_id for p in load_knowledge_points(tree)}
        for entry in self.entries:
            if entry["knowledge_point_weights"] is None:
                continue
            with self.subTest(question=entry["question_id"]):
                self.assertIn(entry["knowledge_point_id"], valid_ids)
                for node_id in entry["knowledge_point_weights"]:
                    self.assertIn(node_id, valid_ids)

    def test_notes_escape_hatch_stays_closed(self) -> None:
        self.assertTrue(all(e["notes"] is None for e in self.entries))

    def test_hashes_match_the_registered_bytes(self) -> None:
        require_path(self, PAPER, "按 data/materials.yaml 的 cs408-paper-2024-rebuild 记录重取")
        require_path(self, ANSWER, "按 data/materials.yaml 的 cs408-answer-2024-scan 记录重取")
        self.assertTrue(PAPER.is_file(), "rebuilt paper missing")
        self.assertTrue(ANSWER.is_file(), "registered answer source missing")
        self.assertEqual(sha(PAPER), self.data["provenance"]["paper"]["sha256"])
        self.assertEqual(sha(ANSWER), self.data["provenance"]["answer"]["sha256"])

    def test_ledger_keeps_the_source_weak_and_unstructurable(self) -> None:
        from ky.ledger import load_ledger

        materials = {m.resource_id: m for m in load_ledger(LEDGER)}
        for rid in ("cs408-paper-2024-rebuild", "cs408-answer-2024-scan"):
            material = materials[rid]
            resource_path = Path(material.storage.path)
            if not resource_path.is_absolute():
                resource_path = ROOT / resource_path
            require_path(self, resource_path, f"按 data/materials.yaml 的 {rid} 记录重取")
            with self.subTest(resource=rid):
                self.assertEqual(material.provenance.source_tier, "community_archive")
                self.assertFalse(material.provenance.may_define_syllabus())
                self.assertFalse(material.may_be_structured())
                self.assertFalse(material.rights.may_display)
                self.assertFalse(material.rights.may_redistribute)
                self.assertTrue(material.verify_bytes(ROOT))

    def test_rehost_restoration_round_trip(self) -> None:
        """The 厦门工学院 rehosts were deleted, then restored on a later instruction.

        History, because this lock has already been reversed once and that is the
        whole point of freezing it:

          * 2026-09-13 (morning): registered as `trusted_reprint`, bytes held so the
            system could compute their sha256.
          * 2026-09-13 10:56: `tools/remove_408_reprints.py`（当时路径） deleted the six
            paper/solutions rows and their PDFs. `test_removed_rehost_stays_removed`
            was added to freeze that decision.
          * 2026-09-13 12:0x: the user instructed that the deletion be undone.
            `tools/restore_408_papers.py`（当时路径） re-downloaded the PDFs (6 of 7 byte-identical
            to the pre-deletion sha256 in `cache/probe/hashes.json`; the 2025 URL had
            been replaced upstream) and restored the rows. This lock was rewritten.

        What is frozen now is the *contract*, not the deletion: the rows exist, they
        stay `trusted_reprint` with no structuring right, and they still verify.
        Re-running the deletion would break this test, and that is intended -- it is
        the tripwire that makes the next reversal deliberate.
        """
        from ky.ledger import load_ledger

        REHOST = [
            "cs408-paper-2022", "cs408-paper-2023", "cs408-paper-2024", "cs408-paper-2025",
            "cs408-solutions-2022", "cs408-solutions-2023", "cs408-solutions-2024",
        ]
        materials = {m.resource_id: m for m in load_ledger(LEDGER)}
        # `cs408-paper-2024-rebuild` is a different source (a GitHub community rehost)
        # and is deliberately NOT part of this list -- it must not leak into the freeze.
        restored = [rid for rid in materials if rid in REHOST]
        self.assertEqual(sorted(restored), REHOST,
                         "the restored 408 rehost rows are gone again (or someone added more)")
        for rid in restored:
            material = materials[rid]
            resource_path = Path(material.storage.path)
            if not resource_path.is_absolute():
                resource_path = ROOT / resource_path
            require_path(self, resource_path, f"按 data/materials.yaml 的 {rid} 记录重取")
            with self.subTest(resource=rid):
                self.assertEqual(material.provenance.source_tier, "trusted_reprint")
                self.assertFalse(material.provenance.may_define_syllabus())
                self.assertFalse(material.may_be_structured())
                self.assertFalse(material.rights.may_display)
                self.assertFalse(material.rights.may_redistribute)
                self.assertTrue(material.rights.may_store,
                                "bytes must be holdable, otherwise the sha256 cannot be pinned")
                self.assertTrue(material.verify_bytes(ROOT))


if __name__ == "__main__":
    unittest.main()
