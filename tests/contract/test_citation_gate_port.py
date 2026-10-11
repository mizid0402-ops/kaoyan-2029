"""M3 citation-gate port: ``contracts/citation_gate.md``.

Pins what the spec states and ``tests/test_citation_gate.py`` does not: remote references never
resolve, the path normalisation, first-failing-rule reporting, what the gate deliberately does
not check (tier, subject), exact digest comparison, strict mode on a missing file, the report
shape, and ``check_ledger_citations``. Materials and points are built here; the repository's
own ledger and trees are never read (D5/D6).
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from ky.knowledge import KnowledgePointError, validate_knowledge_point
from ky.ledger import (
    LedgerError,
    check_knowledge_point_citations,
    check_ledger_citations,
    check_material_map,
    sha256_bytes,
    validate_material,
)
from ky.workspace import WORKSPACE_ENV, WORKSPACE_FILENAME

# Fixture subject ids of a temporary registry, not the repository's subjects.
SUBJECT_A = "alpha"
SUBJECT_B = "beta"
ALLOWED = frozenset({SUBJECT_A, SUBJECT_B, "general"})
PAYLOAD = b"section list\n"
DIGEST = sha256_bytes(PAYLOAD)
STORE_PATH = "data/raw/outline.txt"


def material_raw(resource_id: str = "res-a", *, path: str = STORE_PATH, **overrides) -> dict:
    raw = {
        "resource_id": resource_id,
        "title": "outline",
        "material_kind": "outline_structure",
        "subjects": [SUBJECT_A],
        "acquisition": "public_download",
        "rights": {
            "status": "official_public", "licence": None, "licence_url": None,
            "may_store": True, "may_display": False, "may_redistribute": False,
            "may_be_structured": True,
        },
        "storage": {"mode": "local_file", "path": path, "sha256": DIGEST,
                    "byte_size": len(PAYLOAD)},
        "provenance": {"source_url": "https://example.invalid/outline"},
    }
    raw.update(overrides)
    return raw


def material(resource_id: str = "res-a", **overrides):
    return validate_material(material_raw(resource_id, **overrides), subject_ids=ALLOWED)


def point_raw(point_id: str = "p1", *sources: tuple[str, str]) -> dict:
    """A raw-status knowledge point citing ``(path, sha256)`` pairs."""
    cited = sources or ((STORE_PATH, DIGEST),)
    return {
        "knowledge_point_id": point_id,
        "title": point_id,
        "status": "raw",
        "source_kind": "manual",
        "sources": [
            {"path": path, "sha256": digest, "locator": {"section": "s"}}
            for path, digest in cited
        ],
        "evidence": [],
        "transition_history": [],
    }


def point(point_id: str = "p1", *sources: tuple[str, str]):
    return validate_knowledge_point(point_raw(point_id, *sources))


class ResolutionTest(unittest.TestCase):
    def test_remote_references_are_never_indexed(self) -> None:
        raw = material_raw("remote")
        raw["rights"].update(status="unknown", may_store=False, may_be_structured=False)
        raw["storage"] = {"mode": "remote_reference", "url": "https://example.invalid/r"}
        remote = validate_material(raw, subject_ids=ALLOWED)
        self.assertEqual(check_material_map([remote]), {})
        report = check_knowledge_point_citations(
            [point("p1", ("https://example.invalid/r", DIGEST))], [remote])
        self.assertIn("no ledger entry stores this path", report.problems[0].reason)

    def test_leading_dot_slash_and_separators_normalise(self) -> None:
        stored = material(path="./data\\raw/outline.txt")
        self.assertEqual(list(check_material_map([stored])), [STORE_PATH])
        for cited in ("./data/raw/outline.txt", "/data/raw/outline.txt", STORE_PATH):
            with self.subTest(cited=cited):
                report = check_knowledge_point_citations([point("p1", (cited, DIGEST))],
                                                         [stored])
                self.assertTrue(report.ok, report.summary())

    def test_matching_is_case_sensitive(self) -> None:
        report = check_knowledge_point_citations(
            [point("p1", (STORE_PATH.upper(), DIGEST))], [material()])
        self.assertIn("no ledger entry stores this path", report.problems[0].reason)

    def test_a_shared_path_fails_before_any_citation_is_checked(self) -> None:
        pair = [material("res-a"), material("res-b", path="./" + STORE_PATH)]
        with self.assertRaises(LedgerError) as ctx:
            check_knowledge_point_citations([], pair)
        self.assertEqual(ctx.exception.path, STORE_PATH)


class RuleOrderTest(unittest.TestCase):
    def reasons(self, gated) -> list[str]:
        report = check_knowledge_point_citations([point()], [gated])
        return [problem.reason for problem in report.problems]

    def test_only_the_first_failing_rule_is_reported(self) -> None:
        raw = material_raw(review_status="withdrawn")
        raw["rights"].update(status="unknown", may_be_structured=False)
        [reason] = self.reasons(validate_material(raw, subject_ids=ALLOWED))
        self.assertIn("is withdrawn", reason)

        raw = material_raw()
        raw["rights"].update(status="unknown", may_be_structured=False)
        [reason] = self.reasons(validate_material(raw, subject_ids=ALLOWED))
        self.assertIn("an unclear right cannot authorise a claim", reason)

    def test_a_clear_but_prohibitive_status_fails_on_structuring(self) -> None:
        raw = material_raw()
        raw["rights"].update(status="scoring_rubric_restricted", may_store=False,
                             may_be_structured=False)
        [reason] = self.reasons(validate_material(raw, subject_ids=ALLOWED))
        self.assertIn("does not permit structuring", reason)

    def test_digest_is_compared_exactly_against_the_lowercase_ledger_digest(self) -> None:
        stored = material(storage={"mode": "local_file", "path": STORE_PATH,
                                   "sha256": DIGEST.upper(), "byte_size": len(PAYLOAD)})
        self.assertTrue(check_knowledge_point_citations([point()], [stored]).ok)
        upper = check_knowledge_point_citations([point("p1", (STORE_PATH, DIGEST.upper()))],
                                                [stored])
        self.assertIn("does not match the ledger digest", upper.problems[0].reason)


class NotGatedTest(unittest.TestCase):
    def test_source_tier_does_not_gate_a_citation(self) -> None:
        for tier in ("trusted_reprint", "community_archive"):
            provenance = {"source_url": "https://example.invalid/x", "source_tier": tier}
            gated = material(provenance=provenance)
            with self.subTest(tier=tier):
                self.assertFalse(gated.provenance.may_define_syllabus())
                self.assertTrue(check_knowledge_point_citations([point()], [gated]).ok)

    def test_subject_review_status_and_display_are_not_checked(self) -> None:
        gated = material(subjects=[SUBJECT_B], review_status="unreviewed")
        self.assertFalse(gated.rights.may_display)
        self.assertTrue(check_knowledge_point_citations([point("alpha.p1")], [gated]).ok)


class StrictModeTest(unittest.TestCase):
    def test_a_missing_file_is_a_problem_not_an_exception(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report = check_knowledge_point_citations([point()], [material()], root=temp,
                                                     strict=True)
        self.assertIn("no longer hash to the recorded digest", report.problems[0].reason)

    def test_non_strict_ignores_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            missing_root = Path(temp) / "absent"
            report = check_knowledge_point_citations([point()], [material()],
                                                     root=missing_root)
        self.assertTrue(report.ok)


class ReportTest(unittest.TestCase):
    def mixed_report(self):
        points = [
            point("p1", ("ghost/one.txt", DIGEST), (STORE_PATH, DIGEST)),
            point("p2", (STORE_PATH, "c" * 64)),
        ]
        return check_knowledge_point_citations(points, [material()])

    def test_counts_order_and_indices(self) -> None:
        report = self.mixed_report()
        self.assertEqual((report.checked_points, report.checked_citations), (2, 3))
        located = [(p.knowledge_point_id, p.source_index, p.path) for p in report.problems]
        self.assertEqual(located, [("p1", 0, "ghost/one.txt"), ("p2", 0, STORE_PATH)])

    def test_problem_path_is_the_raw_citation_path(self) -> None:
        cited = ".\\data\\raw\\outline.txt"
        report = check_knowledge_point_citations([point("p1", (cited, "c" * 64))],
                                                 [material()])
        self.assertEqual(report.problems[0].path, cited)

    def test_raise_for_problems_names_every_problem(self) -> None:
        report = self.mixed_report()
        with self.assertRaises(LedgerError) as ctx:
            report.raise_for_problems()
        self.assertEqual(ctx.exception.path, "sources")
        message = str(ctx.exception)
        self.assertIn("unsupported citations: ", message)
        self.assertIn("p1.sources[0] (ghost/one.txt): ", message)
        self.assertIn(f"; p2.sources[0] ({STORE_PATH}): ", message)
        self.assertIsNone(check_knowledge_point_citations([point()], [material()])
                          .raise_for_problems())

    def test_summary_has_exactly_the_documented_keys(self) -> None:
        summary = self.mixed_report().summary()
        self.assertEqual(set(summary), {"checked_points", "checked_citations", "ok", "problems"})
        self.assertIs(summary["ok"], False)
        for problem in summary["problems"]:
            self.assertEqual(set(problem),
                             {"knowledge_point_id", "source_index", "path", "reason"})


class InputTest(unittest.TestCase):
    def test_mapping_points_are_validated_and_errors_propagate(self) -> None:
        self.assertTrue(check_knowledge_point_citations([point_raw()], [material()]).ok)
        broken = point_raw()
        broken["sources"] = []
        with self.assertRaises(KnowledgePointError):
            check_knowledge_point_citations([broken], [material()])

    def test_check_ledger_citations_loads_with_registry_subjects(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            registry = write_registry(root, subjects=[SUBJECT_A])
            ledger = root / "ledger.yaml"
            write_yaml(ledger, {"items": [material_raw()]})
            with mock.patch.dict(os.environ, {WORKSPACE_ENV: str(registry)}):
                self.assertTrue(check_ledger_citations(ledger, [point_raw()]).ok)
                write_yaml(ledger, {"items": [material_raw(subjects=[SUBJECT_B])]})
                with self.assertRaises(LedgerError) as ctx:
                    check_ledger_citations(ledger, [point_raw()])
        self.assertEqual(ctx.exception.path, f"{ledger.as_posix()}.items[0].subjects[0]")


def write_yaml(path: Path, document: dict) -> None:
    path.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False),
                    encoding="utf-8")


def write_registry(root: Path, *, subjects: list[str]) -> Path:
    path = root / WORKSPACE_FILENAME
    write_yaml(path, {
        "schema_version": 2,
        "subjects": {subject: {"name": subject} for subject in subjects},
        "reference": {
            "knowledge_trees": {}, "exam_indexes": {}, "topic_weights": "data/weights.json",
            "vocabulary_db": "data/vocabulary.sqlite", "ledger": "ledger.yaml",
        },
        "materials": {"raw_root": "data/raw"},
        "state": {"review_queue": "data/review_queue", "plans": "data/plans"},
        "staging": "staging", "projection": "data/projection.sqlite",
    })
    return path


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
