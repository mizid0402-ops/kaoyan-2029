"""Material ledger contract tests.

The ledger is the gate that stops an unclear right or an unverifiable source
from quietly authorising a knowledge point. These tests pin that gate.
"""

from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from ky.ledger import (
    LedgerError,
    evidence_capable_materials,
    integrity_report,
    ledger_summary,
    load_ledger,
    sha256_bytes,
    structurable_materials,
    validate_ledger,
    validate_material,
)


def local_material(**overrides) -> dict:
    """A well-formed locally stored, fully permitted material."""
    material = {
        "schema_version": 1,
        "resource_id": "cs408-outline-structure-2026",
        "title": "408 考试范围结构（章节级）",
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
            "path": "data/syllabus/cs408-outline-structure.yaml",
            "sha256": "a" * 64,
            "byte_size": 1024,
            "url": None,
            "retrieved_on": "2026-09-12",
        },
        "provenance": {
            "source_url": "https://example.invalid/official/outline",
            "publisher": "教育部教育考试院",
            "published_on": None,
            "isbn": None,
            "retrieved_at": "2026-09-12T10:00:00+08:00",
            "retrieved_by": "dsh",
        },
        "review_index": True,
        "review_status": "verified",
        "notes": None,
        "history": [
            {
                "at": "2026-09-12T10:00:00+08:00",
                "action": "registered",
                "actor": "dsh",
                "detail": "initial registration",
            }
        ],
    }
    material.update(overrides)
    return material


def remote_material(**overrides) -> dict:
    """A link-only material: no local bytes, nothing may be derived from it."""
    material = {
        "schema_version": 1,
        "resource_id": "cs408-textbook-toc-link",
        "title": "408 教材目录（仅链接）",
        "material_kind": "outline_structure",
        "subjects": ["cs408"],
        "acquisition": "public_download",
        "rights": {
            "status": "unknown",
            "licence": None,
            "licence_url": None,
            "may_store": False,
            "may_display": False,
            "may_redistribute": False,
            "may_be_structured": False,
        },
        "storage": {
            "mode": "remote_reference",
            "path": None,
            "sha256": None,
            "byte_size": None,
            "url": "https://example.invalid/book/toc",
            "retrieved_on": "2026-09-12",
        },
        "provenance": {
            "source_url": "https://example.invalid/book",
            "publisher": None,
            "published_on": None,
            "isbn": None,
            "retrieved_at": None,
            "retrieved_by": None,
        },
        "review_index": False,
        "review_status": "unreviewed",
        "notes": None,
        "history": [],
    }
    material.update(overrides)
    return material


class LedgerContractTest(unittest.TestCase):
    def test_a_well_formed_material_loads(self) -> None:
        material = validate_material(local_material())
        self.assertEqual(material.resource_id, "cs408-outline-structure-2026")
        self.assertEqual(material.subjects, ("cs408",))
        self.assertTrue(material.rights.is_clear())
        self.assertTrue(material.may_be_structured())
        self.assertTrue(material.can_back_evidence())

    # -- rights gate ------------------------------------------------------

    def test_unknown_rights_cannot_permit_display(self) -> None:
        raw = local_material()
        raw["rights"]["status"] = "unknown"
        raw["rights"]["may_display"] = True
        with self.assertRaises(LedgerError) as ctx:
            validate_material(raw)
        self.assertIn("unknown", str(ctx.exception))

    def test_unknown_rights_material_is_never_structurable(self) -> None:
        raw = local_material()
        raw["rights"]["status"] = "unknown"
        raw["rights"]["may_display"] = False
        raw["rights"]["may_be_structured"] = False
        material = validate_material(raw)
        self.assertFalse(material.rights.is_clear())
        self.assertFalse(material.may_be_structured())
        self.assertIn("cs408-outline-structure-2026", ledger_summary([material])["unclear_rights"])

    def test_restricted_rights_cannot_permit_redistribution(self) -> None:
        raw = local_material()
        raw["rights"]["status"] = "restricted"
        raw["rights"]["may_redistribute"] = True
        with self.assertRaises(LedgerError):
            validate_material(raw)

    def test_redistribution_requires_display(self) -> None:
        raw = local_material()
        raw["rights"]["may_display"] = False
        raw["rights"]["may_redistribute"] = True
        with self.assertRaises(LedgerError) as ctx:
            validate_material(raw)
        self.assertIn("may_redistribute", str(ctx.exception.path))

    def test_structured_requires_stored_bytes(self) -> None:
        """Structure can only come from bytes the project actually holds."""
        raw = remote_material()
        raw["rights"]["may_be_structured"] = True
        with self.assertRaises(LedgerError) as ctx:
            validate_material(raw)
        self.assertIn("may_be_structured", str(ctx.exception.path))

    # -- storage modes ----------------------------------------------------

    def test_remote_reference_cannot_carry_a_verified_hash(self) -> None:
        raw = remote_material()
        raw["storage"]["sha256"] = "b" * 64
        with self.assertRaises(LedgerError) as ctx:
            validate_material(raw)
        self.assertIn("sha256", str(ctx.exception.path))

    def test_remote_reference_cannot_claim_storage_permission(self) -> None:
        raw = remote_material()
        raw["rights"]["may_store"] = True
        with self.assertRaises(LedgerError) as ctx:
            validate_material(raw)
        self.assertIn("may_store", str(ctx.exception.path))

    def test_local_file_requires_hash_and_size(self) -> None:
        raw = local_material()
        raw["storage"]["sha256"] = None
        with self.assertRaises(LedgerError):
            validate_material(raw)
        raw = local_material()
        raw["storage"]["byte_size"] = None
        with self.assertRaises(LedgerError):
            validate_material(raw)

    def test_remote_reference_is_not_evidence_capable(self) -> None:
        material = validate_material(remote_material())
        self.assertFalse(material.can_back_evidence())
        self.assertFalse(material.verify_bytes())
        self.assertEqual(evidence_capable_materials([material]), ())

    # -- provenance -------------------------------------------------------

    def test_untraceable_material_is_rejected(self) -> None:
        raw = local_material()
        raw["acquisition"] = "user_provided"
        raw["provenance"] = {
            "source_url": None,
            "publisher": None,
            "published_on": None,
            "isbn": None,
            "retrieved_at": None,
            "retrieved_by": None,
        }
        with self.assertRaises(LedgerError) as ctx:
            validate_material(raw)
        self.assertIn("provenance", str(ctx.exception.path))

    def test_generated_material_needs_no_external_origin(self) -> None:
        raw = local_material()
        raw["resource_id"] = "ai-practice-limits"
        raw["material_kind"] = "ai_generated"
        raw["acquisition"] = "generated"
        raw["rights"]["status"] = "official_public"
        raw["provenance"] = {
            "source_url": None,
            "publisher": None,
            "published_on": None,
            "isbn": None,
            "retrieved_at": None,
            "retrieved_by": None,
        }
        material = validate_material(raw)
        self.assertEqual(material.material_kind, "ai_generated")

    # -- structural -------------------------------------------------------

    def test_unknown_key_has_a_precise_path(self) -> None:
        raw = local_material()
        raw["rights"]["may_redistribut"] = True
        with self.assertRaises(LedgerError) as ctx:
            validate_material(raw, source="items[0]")
        self.assertIn("may_redistribut", str(ctx.exception))

    def test_non_mapping_rights_values_are_rejected(self) -> None:
        for invalid_rights in (None, "wrong-type", {}):
            with self.subTest(rights=invalid_rights):
                raw = local_material()
                raw["rights"] = invalid_rights
                with self.assertRaises(ValueError):
                    validate_material(raw)

    def test_unknown_subject_is_rejected(self) -> None:
        raw = local_material()
        raw["subjects"] = ["cs409"]
        with self.assertRaises(LedgerError) as ctx:
            validate_material(raw)
        self.assertIn("subjects[0]", str(ctx.exception.path))

    def test_duplicate_resource_id_in_a_ledger_is_rejected(self) -> None:
        with self.assertRaises(LedgerError) as ctx:
            validate_ledger([local_material(), local_material()])
        self.assertIn("duplicate resource_id", str(ctx.exception))

    def test_unsupported_ledger_schema_version_is_rejected(self) -> None:
        with self.assertRaises(LedgerError) as ctx:
            validate_ledger({"schema_version": 99, "items": []})
        self.assertIn("schema_version", str(ctx.exception.path))

    def test_ledger_round_trips_through_yaml(self) -> None:
        import yaml

        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "ledger.yaml"
            payload = {"schema_version": 1, "items": [local_material(), remote_material()]}
            path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
            materials = load_ledger(path)
        self.assertEqual([m.resource_id for m in materials], ["cs408-outline-structure-2026", "cs408-textbook-toc-link"])
        structurable = structurable_materials(materials)
        self.assertEqual([m.resource_id for m in structurable], ["cs408-outline-structure-2026"])


class LedgerFileReadingTest(unittest.TestCase):
    """WP-R3 (round 152 S1 / S2): everyday editing accidents in the ledger file itself."""

    def _load(self, data: bytes):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "ledger.yaml"
            path.write_bytes(data)
            subjects = frozenset(local_material()["subjects"])
            try:
                return load_ledger(path, subject_ids=subjects), path.as_posix()
            except LedgerError as exc:
                return exc, path.as_posix()

    def test_a_ledger_saved_as_gbk_is_a_ledger_error_with_the_path(self) -> None:
        import yaml

        text = yaml.safe_dump([local_material()], allow_unicode=True, sort_keys=False)
        outcome, path = self._load(text.encode("gbk"))
        self.assertIsInstance(outcome, LedgerError)
        self.assertEqual(outcome.path, path)
        self.assertIn("cannot read YAML", str(outcome))

    def test_a_key_written_twice_is_rejected_not_last_wins(self) -> None:
        import yaml

        text = yaml.safe_dump([local_material()], allow_unicode=True, sort_keys=False)
        duplicated = text.replace("  review_index: true\n", "  review_index: true\n" * 2, 1)
        self.assertNotEqual(duplicated, text)
        outcome, path = self._load(duplicated.encode("utf-8"))
        self.assertIsInstance(outcome, LedgerError)
        self.assertEqual(outcome.path, path)
        self.assertIn("duplicate field 'review_index'", str(outcome))

    def test_yaml_merge_accepts_an_override_but_rejects_explicit_duplicates(self) -> None:
        import yaml

        text = yaml.safe_dump([local_material()], allow_unicode=True, sort_keys=False)
        self.assertIn("- schema_version: 1\n", text)
        anchored = text.replace("- schema_version: 1\n", "- &base\n  schema_version: 1\n", 1)
        merged = anchored + (
            "- <<: *base\n"
            "  resource_id: cs408-outline-structure-2026-copy\n"
            "  title: copied title\n"
        )
        expected = yaml.safe_load(merged)
        outcome, _ = self._load(merged.encode("utf-8"))
        self.assertIsInstance(outcome, tuple)
        self.assertEqual([item.resource_id for item in outcome], [
            item["resource_id"] for item in expected
        ])

        duplicated = merged + "  review_index: true\n  review_index: false\n"
        outcome, path = self._load(duplicated.encode("utf-8"))
        self.assertIsInstance(outcome, LedgerError)
        self.assertEqual(outcome.path, path)
        self.assertIn("duplicate field 'review_index'", str(outcome))

        duplicated_merge = merged.replace(
            "- <<: *base\n", "- <<: *base\n  <<: *base\n", 1
        )
        outcome, path = self._load(duplicated_merge.encode("utf-8"))
        self.assertIsInstance(outcome, LedgerError)
        self.assertEqual(outcome.path, path)
        self.assertIn("duplicate field '<<'", str(outcome))


class ExamPhaseRightsTest(unittest.TestCase):
    """The three exam phases are legal facts, not author preferences.

    Added after the 2026-09-12 material reconnaissance corrected the project's
    earlier assumption that the official papers carry no answers. They do, so
    "official publication" and "scoring rubric" have to be modelled apart.
    """

    def test_exam_period_material_cannot_be_held_at_all(self) -> None:
        raw = remote_material()
        raw["rights"]["status"] = "state_secret_exam_period"
        raw["rights"]["may_store"] = True
        with self.assertRaises(LedgerError) as ctx:
            validate_material(raw)
        self.assertIn("state_secret_exam_period", str(ctx.exception))

    def test_scoring_rubric_cannot_be_published_even_after_the_exam(self) -> None:
        """The regulation forbids publishing the rubric after the exam too."""
        raw = local_material()
        raw["rights"]["status"] = "scoring_rubric_restricted"
        with self.assertRaises(LedgerError) as ctx:
            validate_material(raw)
        self.assertIn("scoring_rubric_restricted", str(ctx.exception))

    def test_scoring_rubric_may_be_registered_as_a_forbidden_record(self) -> None:
        """Registering *that* a rubric exists and is off-limits is useful.

        Note the distinction the model draws: this right is **clear** (there is
        no ambiguity about what is allowed) but **prohibitive**. ``is_clear``
        answers "do we know?", ``permits_evidence`` answers "may we?". Only the
        second decides whether a claim can be built on it.
        """
        raw = remote_material()
        raw["resource_id"] = "cs408-2022-rubric-notice"
        raw["rights"]["status"] = "scoring_rubric_restricted"
        material = validate_material(raw)
        self.assertTrue(material.rights.is_clear(), "the position is known, not unclear")
        self.assertFalse(material.rights.permits_evidence(), "but it permits nothing")
        self.assertFalse(material.may_be_structured())
        self.assertFalse(material.can_back_evidence())

    def test_officially_published_papers_with_answers_are_structurable(self) -> None:
        """An officially published paper (which includes its answers) is usable."""
        raw = local_material()
        raw["resource_id"] = "cs408-paper-2022-official"
        raw["material_kind"] = "past_exam_paper"
        raw["rights"]["status"] = "officially_published"
        material = validate_material(raw)
        self.assertTrue(material.rights.is_clear())
        self.assertTrue(material.may_be_structured())


class SourceTierTest(unittest.TestCase):
    """Rights and trust are independent axes.

    Added after a real misattribution: a set of 408 papers hosted on a private
    undergraduate college's advice page was registered as if a graduate
    programme had published it. The papers themselves are officially published
    material, so `rights` was not wrong -- what was missing was a separate
    record of how far the *held bytes* can be trusted.
    """

    def test_an_unstated_tier_defaults_to_the_weakest(self) -> None:
        """An absent trust level is not a high one."""
        material = validate_material(local_material())
        self.assertEqual(material.provenance.source_tier, "community_archive")

    def test_an_unknown_tier_is_rejected(self) -> None:
        raw = local_material()
        raw["provenance"]["source_tier"] = "pretty_reliable_i_think"
        with self.assertRaises(LedgerError) as ctx:
            validate_material(raw)
        self.assertIn("source_tier", str(ctx.exception.path))

    def test_only_strong_tiers_may_define_the_syllabus(self) -> None:
        for tier, allowed in (
            ("official", True),
            ("official_publisher", True),
            ("university", True),
            ("trusted_reprint", False),
            ("community_archive", False),
        ):
            raw = local_material()
            raw["provenance"]["source_tier"] = tier
            material = validate_material(raw)
            with self.subTest(tier=tier):
                self.assertEqual(material.provenance.may_define_syllabus(), allowed)

    def test_rights_and_trust_are_independent(self) -> None:
        """A perfectly permitted material can still be an untrustworthy copy."""
        raw = local_material()
        raw["provenance"]["source_tier"] = "trusted_reprint"
        material = validate_material(raw)
        # Permitted to derive claims from...
        self.assertTrue(material.may_be_structured())
        # ...but not allowed to decide what the syllabus contains.
        self.assertFalse(material.provenance.may_define_syllabus())

    def test_the_reprint_archive_url_is_recorded(self) -> None:
        raw = local_material()
        raw["provenance"]["source_tier"] = "trusted_reprint"
        raw["provenance"]["archive_url"] = "https://example.invalid/archive/list.htm"
        material = validate_material(raw)
        self.assertEqual(material.provenance.archive_url, "https://example.invalid/archive/list.htm")


class LedgerIntegrityTest(unittest.TestCase):
    def test_verify_bytes_detects_a_changed_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "data" / "syllabus" / "outline.txt"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"original bytes")
            raw = local_material()
            raw["storage"]["path"] = "data/syllabus/outline.txt"
            raw["storage"]["sha256"] = sha256_bytes(b"original bytes")
            raw["storage"]["byte_size"] = len(b"original bytes")
            material = validate_material(raw)
            self.assertTrue(material.verify_bytes(root))
            self.assertEqual(integrity_report([material], root=root), ((material.resource_id, True),))

            target.write_bytes(b"tampered bytes")
            self.assertFalse(material.verify_bytes(root))
            self.assertEqual(integrity_report([material], root=root), ((material.resource_id, False),))

    def test_verify_bytes_is_false_when_the_file_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            material = validate_material(local_material())
            self.assertFalse(material.verify_bytes(temp))

    def test_sha256_file_matches_sha256_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "blob.bin"
            payload = b"x" * 100_000
            path.write_bytes(payload)
            from ky.ledger import sha256_file

            self.assertEqual(sha256_file(path), sha256_bytes(payload))


class LedgerSummaryTest(unittest.TestCase):
    def test_summary_separates_the_three_gates(self) -> None:
        materials = [validate_material(local_material()), validate_material(remote_material())]
        summary = ledger_summary(materials)
        self.assertEqual(summary["total"], 2)
        # A link-only material is evidence-incapable even if it is a fine index entry.
        self.assertEqual(summary["evidence_capable"], ["cs408-outline-structure-2026"])
        self.assertEqual(summary["structurable"], ["cs408-outline-structure-2026"])
        self.assertEqual(summary["unclear_rights"], ["cs408-textbook-toc-link"])
        self.assertEqual(summary["by_rights_status"], {"official_public": 1, "unknown": 1})


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
