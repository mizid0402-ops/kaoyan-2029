"""Cross-contract tests: ledger rights gate the knowledge-point citations.

`ky.knowledge` and `ky.ledger` are each self-consistent. These tests pin the
joint behaviour, because the dangerous state is "both files valid, but the
citation points at something that may not support it".
"""

from __future__ import annotations

import unittest
from pathlib import Path

from ky.ledger import (
    LedgerError,
    check_knowledge_point_citations,
    check_material_map,
    sha256_bytes,
    validate_material,
)
from ky.knowledge import validate_knowledge_point

PAYLOAD = b"chapter 1: limits\nchapter 2: derivatives\n"
DIGEST = sha256_bytes(PAYLOAD)
STORE_PATH = "data/syllabus/cs408-outline.txt"


def material(**overrides) -> dict:
    raw = {
        "schema_version": 1,
        "resource_id": "cs408-outline",
        "title": "408 考试范围结构",
        "material_kind": "outline_structure",
        "subjects": ["cs408"],
        "acquisition": "public_download",
        "rights": {
            "status": "official_public",
            "licence": None,
            "licence_url": None,
            "may_store": True,
            "may_display": True,
            "may_redistribute": False,
            "may_be_structured": True,
        },
        "storage": {
            "mode": "local_file",
            "path": STORE_PATH,
            "sha256": DIGEST,
            "byte_size": len(PAYLOAD),
            "url": None,
            "retrieved_on": "2026-09-12",
        },
        "provenance": {
            "source_url": "https://example.invalid/outline",
            "publisher": "教育部教育考试院",
            "published_on": None,
            "isbn": None,
            "retrieved_at": None,
            "retrieved_by": "dsh",
        },
        "review_index": False,
        "review_status": "verified",
        "notes": None,
        "history": [],
    }
    for key, value in overrides.items():
        raw[key] = value
    return raw


def point(source_digest: str = DIGEST, path: str = STORE_PATH, **overrides) -> dict:
    raw = {
        "schema_version": 1,
        "knowledge_point_id": "cs408.ds.stack",
        "title": "栈",
        "status": "extracted",
        "source_kind": "official_outline",
        "sources": [{"path": path, "sha256": source_digest, "locator": {"section": "data structures"}}],
        "evidence": [],
        "transition_history": [
            {
                "from": "raw",
                "to": "extracted",
                "actor": "ai",
                "source": {"path": path, "sha256": source_digest, "locator": {"section": "ds"}},
            }
        ],
        "revision": 1,
    }
    raw.update(overrides)
    return raw


class CitationGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.material = validate_material(material())
        self.point = validate_knowledge_point(point())

    def test_a_supported_citation_passes(self) -> None:
        report = check_knowledge_point_citations([self.point], [self.material])
        self.assertTrue(report.ok)
        self.assertEqual(report.checked_points, 1)
        self.assertEqual(report.checked_citations, 1)
        self.assertEqual(report.summary()["problems"], [])

    def test_a_dangling_citation_is_a_problem(self) -> None:
        """Citing a path no ledger row stores is a broken chain, not a warning."""
        orphan = validate_knowledge_point(point(path="data/nowhere/ghost.txt"))
        report = check_knowledge_point_citations([orphan], [self.material])
        self.assertFalse(report.ok)
        self.assertIn("no ledger entry stores this path", report.problems[0].reason)
        with self.assertRaises(LedgerError):
            report.raise_for_problems()

    def test_a_wrong_digest_in_the_citation_is_a_problem(self) -> None:
        """A citation must not invent its own hash."""
        lying = validate_knowledge_point(point(source_digest="c" * 64))
        report = check_knowledge_point_citations([lying], [self.material])
        self.assertFalse(report.ok)
        self.assertIn("does not match the ledger digest", report.problems[0].reason)

    def test_rights_that_forbid_structuring_block_the_citation(self) -> None:
        """The core gate: locally stored and intact is not the same as permitted."""
        raw = material()
        raw["rights"]["may_be_structured"] = False
        restricted = validate_material(raw)
        report = check_knowledge_point_citations([self.point], [restricted])
        self.assertFalse(report.ok)
        self.assertIn("does not permit structuring", report.problems[0].reason)

    def test_unclear_rights_block_the_citation(self) -> None:
        raw = material()
        raw["rights"]["status"] = "unknown"
        raw["rights"]["may_display"] = False
        raw["rights"]["may_be_structured"] = False
        unclear = validate_material(raw)
        report = check_knowledge_point_citations([self.point], [unclear])
        self.assertFalse(report.ok)
        self.assertIn("unclear right", report.problems[0].reason)

    def test_a_withdrawn_material_blocks_the_citation(self) -> None:
        raw = material()
        raw["review_status"] = "withdrawn"
        withdrawn = validate_material(raw)
        report = check_knowledge_point_citations([self.point], [withdrawn])
        self.assertFalse(report.ok)
        self.assertIn("withdrawn", report.problems[0].reason)

    def test_two_materials_claiming_one_path_is_refused(self) -> None:
        """An ambiguous citation is refused rather than resolved silently."""
        second = validate_material(material(resource_id="cs408-outline-copy"))
        with self.assertRaises(LedgerError) as ctx:
            check_material_map([self.material, second])
        self.assertIn("must resolve to exactly one material", str(ctx.exception))

    def test_backslash_paths_resolve_the_same(self) -> None:
        windows_style = validate_knowledge_point(point(path="data\\syllabus\\cs408-outline.txt"))
        report = check_knowledge_point_citations([windows_style], [self.material])
        self.assertTrue(report.ok)

    def test_strict_mode_detects_changed_bytes(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / STORE_PATH
            target.parent.mkdir(parents=True)
            target.write_bytes(PAYLOAD)

            # Non-strict checks the record only, so it still passes on a
            # changed file -- that is the documented difference.
            target.write_bytes(b"tampered chapter list\n")
            self.assertTrue(check_knowledge_point_citations([self.point], [self.material]).ok)

            # Strict re-reads the bytes and fails closed.
            strict = check_knowledge_point_citations(
                [self.point], [self.material], root=root, strict=True
            )
            self.assertFalse(strict.ok)
            self.assertIn("no longer hash", strict.problems[0].reason)

    def test_strict_mode_passes_on_intact_bytes(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / STORE_PATH
            target.parent.mkdir(parents=True)
            target.write_bytes(PAYLOAD)
            report = check_knowledge_point_citations(
                [self.point], [self.material], root=root, strict=True
            )
            self.assertTrue(report.ok)

    def test_report_lists_every_problem_not_just_the_first(self) -> None:
        """A bulk check must not stop at the first bad citation."""
        points = [
            validate_knowledge_point(point(path="ghost/one.txt")),
            validate_knowledge_point(point(path="ghost/two.txt")),
        ]
        report = check_knowledge_point_citations(points, [self.material])
        self.assertEqual(len(report.problems), 2)
        self.assertEqual(report.checked_points, 2)

    def test_strict_bulk_report_preserves_all_six_reason_values_in_rule_order(self) -> None:
        import tempfile

        names_and_paths = (
            ("dangling", "unregistered.txt"),
            ("withdrawn", "withdrawn.txt"),
            ("unclear", "unclear.txt"),
            ("structure", "structure.txt"),
            ("digest", "digest.txt"),
            ("missing-bytes", "missing.txt"),
        )
        payload = b"evidence"
        digest = sha256_bytes(payload)
        materials = []
        points = []
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for index, (name, relative_path) in enumerate(names_and_paths):
                cited_digest = digest
                if name != "dangling":
                    raw = material(resource_id=name)
                    raw["review_status"] = "unreviewed"
                    raw["storage"].update(
                        path=relative_path, url=None, sha256=digest, byte_size=len(payload),
                    )
                    if name == "withdrawn":
                        raw["review_status"] = "withdrawn"
                    elif name == "unclear":
                        raw["rights"].update(
                            status="unknown", may_display=False, may_be_structured=True,
                        )
                    elif name == "structure":
                        raw["rights"]["may_be_structured"] = False
                    row = validate_material(raw)
                    materials.append(row)
                if name == "digest":
                    cited_digest = "0" * len(digest)
                points.append(validate_knowledge_point({
                    "schema_version": 1,
                    "knowledge_point_id": f"citation-{index}",
                    "title": name,
                    "status": "raw",
                    "source_kind": "manual",
                    "sources": [{
                        "path": relative_path,
                        "sha256": cited_digest,
                        "locator": {"section": "fixture"},
                    }],
                    "evidence": [],
                    "transition_history": [],
                    "revision": 1,
                }))

            report = check_knowledge_point_citations(
                points, materials, root=root, strict=True,
            )

        self.assertEqual(
            [problem.reason for problem in report.problems],
            [
                "no ledger entry stores this path; register the material before citing it",
                "material 'withdrawn' is withdrawn",
                "material 'unclear' has rights.status='unknown'; an unclear right cannot "
                "authorise a claim",
                "material 'structure' does not permit structuring "
                "(may_be_structured: false)",
                "cited sha256 does not match the ledger digest for 'digest'",
                "stored bytes for 'missing-bytes' are missing or no longer hash to the "
                "recorded digest",
            ],
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
