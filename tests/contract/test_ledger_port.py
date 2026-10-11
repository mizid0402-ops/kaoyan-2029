"""M2 material-ledger port: ``contracts/ledger.md``.

Pins what the spec states and ``tests/test_ledger.py`` / ``tests/test_ledger_cli.py`` do not:
the enumerations, document forms, defaults, the complete subject set, exact error paths of
the rights guards, storage and provenance rules, the three gates, and the ``ky ledger`` exit
codes, JSON shape, ``--subject`` filter and read-only behaviour. Every ledger is built here in
a temporary directory; nothing reads the repository's own ledger (D5/D6).
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from ky.__main__ import main as cli_main
from ky.ledger import (
    FORBIDDEN_RIGHTS_STATUS,
    LEDGER_SUBJECT_CATEGORIES,
    SYLLABUS_AUTHORITATIVE_TIERS,
    VALID_ACQUISITION,
    VALID_HISTORY_ACTIONS,
    VALID_MATERIAL_KINDS,
    VALID_REVIEW_STATUS,
    VALID_RIGHTS_STATUS,
    VALID_SOURCE_TIERS,
    VALID_STORAGE_MODES,
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
from ky.models import ContractError
from ky.workspace import WORKSPACE_ENV, WORKSPACE_FILENAME

# Fixture subject ids of a temporary registry, not the repository's subjects.
SUBJECT_A = "alpha"
SUBJECT_B = "beta"
SUBJECTS = frozenset({SUBJECT_A, SUBJECT_B})
ALLOWED = SUBJECTS | LEDGER_SUBJECT_CATEGORIES
PAYLOAD = b"chapter list\n"
STORE_PATH = "data/raw/outline.txt"


def local_material(resource_id: str = "res-local", **overrides) -> dict:
    """A locally stored material whose rights permit structuring."""
    raw = {
        "resource_id": resource_id,
        "title": "outline",
        "material_kind": "outline_structure",
        "subjects": [SUBJECT_A],
        "acquisition": "public_download",
        "rights": {
            "status": "official_public", "licence": None, "licence_url": None,
            "may_store": True, "may_display": True, "may_redistribute": False,
            "may_be_structured": True,
        },
        "storage": {
            "mode": "local_file", "path": STORE_PATH, "sha256": sha256_bytes(PAYLOAD),
            "byte_size": len(PAYLOAD), "url": None, "retrieved_on": "2026-09-12",
        },
        "provenance": {"source_url": "https://example.invalid/outline"},
    }
    raw.update(overrides)
    return raw


def remote_material(resource_id: str = "res-remote", **overrides) -> dict:
    """A link-only material with no local bytes."""
    raw = local_material(resource_id, **overrides)
    raw["rights"] = {
        "status": "unknown", "licence": None, "licence_url": None, "may_store": False,
        "may_display": False, "may_redistribute": False, "may_be_structured": False,
    }
    raw["storage"] = {"mode": "remote_reference", "url": "https://example.invalid/remote"}
    return raw


def validate(raw: dict, subject_ids: frozenset[str] = ALLOWED):
    return validate_material(raw, source="m", subject_ids=subject_ids)


class LedgerPortTestCase(unittest.TestCase):
    def assert_path(self, raw: dict, expected: str, subject_ids: frozenset[str] = ALLOWED
                    ) -> None:
        with self.assertRaises(LedgerError) as ctx:
            validate(raw, subject_ids)
        self.assertEqual(ctx.exception.path, expected)


class EnumerationTest(unittest.TestCase):
    def test_enumerations_equal_the_spec(self) -> None:
        self.assertEqual(VALID_MATERIAL_KINDS, {
            "official_syllabus", "outline_structure", "official_exam_notice", "textbook",
            "past_exam_paper", "reference_notes", "ai_generated",
        })
        self.assertEqual(VALID_ACQUISITION, {
            "public_download", "user_provided", "licensed", "purchased", "generated", "unknown",
        })
        self.assertEqual(VALID_RIGHTS_STATUS, {
            "public_domain", "official_public", "licensed", "personal_use", "unknown",
            "restricted", "state_secret_exam_period", "officially_published",
            "scoring_rubric_restricted",
        })
        self.assertEqual(FORBIDDEN_RIGHTS_STATUS,
                         {"state_secret_exam_period", "scoring_rubric_restricted"})
        self.assertEqual(VALID_STORAGE_MODES, {"local_file", "remote_reference"})
        self.assertEqual(VALID_SOURCE_TIERS, {
            "official", "official_publisher", "university", "trusted_reprint",
            "community_archive",
        })
        self.assertEqual(SYLLABUS_AUTHORITATIVE_TIERS,
                         {"official", "official_publisher", "university"})
        self.assertEqual(VALID_REVIEW_STATUS, {"unreviewed", "verified", "withdrawn"})
        self.assertEqual(VALID_HISTORY_ACTIONS, {
            "registered", "rights_changed", "path_changed", "verified", "withdrawn",
            "superseded",
        })
        self.assertEqual(LEDGER_SUBJECT_CATEGORIES, {"general"})


class DocumentShapeTest(unittest.TestCase):
    def test_a_list_and_an_items_mapping_are_the_same_ledger(self) -> None:
        entries = [local_material(), remote_material()]
        as_list = validate_ledger(copy.deepcopy(entries), subject_ids=ALLOWED)
        as_mapping = validate_ledger({"items": copy.deepcopy(entries)}, subject_ids=ALLOWED)
        self.assertEqual(as_list, as_mapping)

    def test_the_items_mapping_rejects_other_top_level_keys(self) -> None:
        with self.assertRaises(LedgerError) as ctx:
            validate_ledger({"items": [], "owner": "x"}, source="L", subject_ids=ALLOWED)
        self.assertEqual(ctx.exception.path, "L.owner")

    def test_a_mapping_without_items_or_an_empty_document_is_not_a_list(self) -> None:
        for raw in ({"materials": []}, None, "text"):
            with self.subTest(raw=raw), self.assertRaises(LedgerError) as ctx:
                validate_ledger(raw, source="L", subject_ids=ALLOWED)
            self.assertEqual(ctx.exception.path, "L.items")

    def test_duplicate_resource_id_is_reported_at_its_second_occurrence(self) -> None:
        entries = [local_material(), remote_material(), local_material()]
        with self.assertRaises(LedgerError) as ctx:
            validate_ledger(entries, source="L", subject_ids=ALLOWED)
        self.assertEqual(ctx.exception.path, "L.items[2].resource_id")

    def test_optional_fields_take_their_documented_defaults(self) -> None:
        material = validate(local_material())
        self.assertEqual(material.schema_version, 1)
        self.assertEqual(material.review_status, "unreviewed")
        self.assertIs(material.review_index, False)
        self.assertIsNone(material.notes)
        self.assertEqual(material.history, ())
        self.assertEqual(material.provenance.source_tier, "community_archive")


class SubjectSetTest(LedgerPortTestCase):
    def test_explicit_subject_ids_are_the_complete_allowed_set(self) -> None:
        general = local_material(subjects=["general"])
        self.assert_path(general, "m.subjects[0]", subject_ids=SUBJECTS)
        self.assertEqual(validate(general).subjects, ("general",))

    def test_subjects_must_be_a_non_empty_list_without_duplicates(self) -> None:
        self.assert_path(local_material(subjects=[]), "m.subjects")
        self.assert_path(local_material(subjects=[SUBJECT_A, SUBJECT_A]), "m.subjects")

    def test_without_subject_ids_the_registry_plus_general_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            registry = write_registry(Path(temp), subjects=[SUBJECT_B])
            with mock.patch.dict(os.environ, {WORKSPACE_ENV: str(registry)}):
                for subject in (SUBJECT_B, "general"):
                    raw = local_material(subjects=[subject])
                    self.assertEqual(validate_material(raw).subjects, (subject,))
                with self.assertRaises(LedgerError) as ctx:
                    validate_material(local_material(subjects=[SUBJECT_A]), source="m")
                self.assertEqual(ctx.exception.path, "m.subjects[0]")

    def test_registry_discovery_failure_is_a_contract_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            missing = Path(temp) / "missing.yaml"
            with mock.patch.dict(os.environ, {WORKSPACE_ENV: str(missing)}):
                with self.assertRaises(ContractError):
                    validate_material(local_material())


class RightsGuardTest(LedgerPortTestCase):
    def rights(self, **flags) -> dict:
        raw = local_material()
        raw["rights"].update(flags)
        return raw

    def test_each_guard_reports_its_documented_path(self) -> None:
        none = {"may_store": False, "may_display": False, "may_redistribute": False,
                "may_be_structured": False}
        cases = (
            ({**none, "status": "scoring_rubric_restricted", "may_store": True}, "status"),
            ({**none, "status": "unknown", "may_store": True, "may_display": True}, "status"),
            ({**none, "status": "restricted", "may_store": True, "may_display": True},
             "status"),
            ({**none, "may_store": True, "may_redistribute": True}, "may_redistribute"),
            ({**none, "may_display": True}, "may_display"),
            ({**none, "may_be_structured": True}, "may_be_structured"),
        )
        for flags, field in cases:
            with self.subTest(flags=flags):
                self.assert_path(self.rights(**flags), f"m.rights.{field}")

    def test_remote_reference_may_not_store(self) -> None:
        raw = remote_material()
        raw["rights"]["may_store"] = True
        self.assert_path(raw, "m.rights.may_store")

    def test_permission_flags_must_be_booleans(self) -> None:
        for value in ("yes", 1, None):
            with self.subTest(value=value):
                self.assert_path(self.rights(may_display=value), "m.rights.may_display")

    def test_unknown_status_with_structuring_flags_loads_but_stays_closed(self) -> None:
        material = validate(self.rights(status="unknown", may_display=False))
        self.assertTrue(material.rights.may_be_structured)
        self.assertFalse(material.rights.is_clear())
        self.assertFalse(material.rights.permits_evidence())
        self.assertFalse(material.may_be_structured())
        self.assertTrue(material.can_back_evidence())

    def test_every_status_but_unknown_is_clear(self) -> None:
        none = {"may_store": False, "may_display": False, "may_redistribute": False,
                "may_be_structured": False}
        for status in sorted(VALID_RIGHTS_STATUS):
            with self.subTest(status=status):
                material = validate(self.rights(**none, status=status))
                self.assertEqual(material.rights.is_clear(), status != "unknown")


class StorageTest(LedgerPortTestCase):
    def storage(self, raw: dict, **fields) -> dict:
        raw["storage"].update(fields)
        return raw

    def test_local_sha256_is_stored_lowercase(self) -> None:
        digest = sha256_bytes(PAYLOAD)
        material = validate(self.storage(local_material(), sha256=digest.upper()))
        self.assertEqual(material.storage.sha256, digest)

    def test_local_file_field_rules(self) -> None:
        cases = (
            ({"sha256": "a" * 63}, "sha256"),
            ({"sha256": "g" * 64}, "sha256"),
            ({"byte_size": -1}, "byte_size"),
            ({"path": ""}, "path"),
        )
        for fields, field in cases:
            with self.subTest(fields=fields):
                self.assert_path(self.storage(local_material(), **fields), f"m.storage.{field}")

    def test_remote_reference_holds_no_local_facts(self) -> None:
        cases = (
            ({"path": STORE_PATH}, "path"),
            ({"sha256": "a" * 64}, "sha256"),
            ({"byte_size": 0}, "byte_size"),
            ({"url": None}, "url"),
        )
        for fields, field in cases:
            with self.subTest(fields=fields):
                self.assert_path(self.storage(remote_material(), **fields), f"m.storage.{field}")

    def test_storage_is_checked_before_rights(self) -> None:
        raw = remote_material()
        raw["storage"] = {"mode": "remote_reference"}
        raw["rights"]["may_display"] = True
        self.assert_path(raw, "m.storage.url")


class ProvenanceTest(LedgerPortTestCase):
    def test_a_missing_provenance_block_is_untraceable(self) -> None:
        raw = local_material()
        del raw["provenance"]
        self.assert_path(raw, "m.provenance")

    def test_any_one_of_url_publisher_isbn_is_enough(self) -> None:
        for key, value in (("source_url", "https://example.invalid/x"),
                           ("publisher", "press"), ("isbn", 9787107404603)):
            with self.subTest(key=key):
                material = validate(local_material(provenance={key: value}))
                self.assertEqual(getattr(material.provenance, key), str(value))

    def test_tier_does_not_move_any_gate(self) -> None:
        for tier in sorted(VALID_SOURCE_TIERS):
            provenance = {"source_url": "https://example.invalid/x", "source_tier": tier}
            material = validate(local_material(provenance=provenance))
            with self.subTest(tier=tier):
                self.assertTrue(material.may_be_structured())
                self.assertTrue(material.can_back_evidence())


class ReviewAndHistoryTest(LedgerPortTestCase):
    def test_withdrawn_loads_but_closes_both_gates(self) -> None:
        material = validate(local_material(review_status="withdrawn"))
        self.assertFalse(material.may_be_structured())
        self.assertFalse(material.can_back_evidence())
        self.assertEqual(structurable_materials([material]), ())
        self.assertEqual(evidence_capable_materials([material]), ())

    def test_verified_and_unreviewed_open_the_same_gates(self) -> None:
        for status in ("verified", "unreviewed"):
            material = validate(local_material(review_status=status))
            with self.subTest(status=status):
                self.assertTrue(material.may_be_structured())
                self.assertTrue(material.can_back_evidence())

    def test_history_entries_are_validated_with_indexed_paths(self) -> None:
        good = {"action": "registered", "actor": "me"}
        self.assert_path(local_material(history=[good, {"action": "edited", "actor": "me"}]),
                         "m.history[1].action")
        self.assert_path(local_material(history=[{"action": "registered"}]),
                         "m.history[0].actor")
        self.assert_path(local_material(history="registered"), "m.history")


class GateAndIntegrityTest(unittest.TestCase):
    def test_evidence_capable_is_wider_than_structurable(self) -> None:
        raw = local_material()
        raw["rights"].update(may_be_structured=False)
        material = validate(raw)
        self.assertEqual(evidence_capable_materials([material]), (material,))
        self.assertEqual(structurable_materials([material]), ())

    def test_verify_bytes_resolves_relative_paths_under_root_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / STORE_PATH
            target.parent.mkdir(parents=True)
            target.write_bytes(PAYLOAD)
            relative = validate(local_material())
            absolute = validate(local_material(storage={
                **local_material()["storage"], "path": str(target)}))
            elsewhere = root / "elsewhere"
            elsewhere.mkdir()
            self.assertTrue(relative.verify_bytes(root))
            self.assertFalse(relative.verify_bytes(elsewhere))
            self.assertTrue(absolute.verify_bytes(elsewhere))

    def test_integrity_report_covers_remote_references_as_false(self) -> None:
        materials = (validate(remote_material()), validate(local_material()))
        with tempfile.TemporaryDirectory() as temp:
            report = integrity_report(materials, root=temp)
        self.assertEqual(report, (("res-remote", False), ("res-local", False)))

    def test_summary_has_exactly_the_documented_keys(self) -> None:
        summary = ledger_summary([validate(local_material()), validate(remote_material())])
        self.assertEqual(set(summary), {
            "total", "by_kind", "by_rights_status", "by_review_status", "structurable",
            "evidence_capable", "unclear_rights",
        })
        self.assertEqual(summary["by_review_status"], {"unreviewed": 2})


class LoadLedgerTest(unittest.TestCase):
    def test_file_errors_are_ledger_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaises(LedgerError) as ctx:
                load_ledger(root / "absent.yaml", subject_ids=ALLOWED)
            self.assertEqual(ctx.exception.path, "")
            with self.assertRaises(LedgerError) as ctx:
                load_ledger(root, subject_ids=ALLOWED)
            self.assertEqual(ctx.exception.path, "")
            broken = root / "broken.yaml"
            broken.write_text("items: [\n", encoding="utf-8")
            with self.assertRaises(LedgerError) as ctx:
                load_ledger(broken, subject_ids=ALLOWED)
            self.assertEqual(ctx.exception.path, broken.as_posix())

    def test_item_paths_are_prefixed_with_the_file_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = write_ledger(Path(temp), [local_material(subjects=["gamma"])])
            with self.assertRaises(LedgerError) as ctx:
                load_ledger(path, subject_ids=ALLOWED)
        self.assertEqual(ctx.exception.path, f"{path.as_posix()}.items[0].subjects[0]")


# --------------------------------------------------------------------------
# ky ledger
# --------------------------------------------------------------------------


def write_ledger(root: Path, entries: list[dict]) -> Path:
    path = root / "data" / "ledger.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    document = {"schema_version": 1, "items": entries}
    path.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False),
                    encoding="utf-8")
    return path


def write_registry(root: Path, *, subjects: list[str]) -> Path:
    document = {
        "schema_version": 2,
        "subjects": {subject: {"name": subject} for subject in subjects},
        "reference": {
            "knowledge_trees": {}, "exam_indexes": {}, "topic_weights": "data/weights.json",
            "vocabulary_db": "data/vocabulary.sqlite", "ledger": "data/ledger.yaml",
        },
        "materials": {"raw_root": "data/raw"},
        "state": {"review_queue": "data/review_queue", "plans": "data/plans"},
        "staging": "staging", "projection": "data/projection.sqlite",
    }
    path = root / WORKSPACE_FILENAME
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    return path


def run_cli(*args: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        with mock.patch.dict(os.environ):
            os.environ.pop(WORKSPACE_ENV, None)
            code = cli_main(["ledger", *args])
    return code, out.getvalue(), err.getvalue()


def tree_bytes(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


class LedgerCliTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def standalone(self, entries: list[dict], *extra: str) -> tuple[int, str, str]:
        ledger = write_ledger(self.root, entries)
        return run_cli("--ledger", str(ledger), "--root", str(self.root),
                       "--subjects", ",".join(sorted(SUBJECTS)), *extra)

    def test_byte_mismatch_is_reported_with_exit_zero(self) -> None:
        target = self.root / STORE_PATH
        target.parent.mkdir(parents=True)
        target.write_bytes(b"tampered " + PAYLOAD)
        code, out, _ = self.standalone([local_material()], "--json")
        self.assertEqual(code, 0)
        [row] = json.loads(out)["materials"]
        self.assertIs(row["bytes_verified"], False)
        self.assertIs(row["may_be_structured"], True)

    def test_json_has_exactly_the_documented_keys(self) -> None:
        code, out, _ = self.standalone([local_material(), remote_material()], "--json")
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(set(payload), {"ledger", "root", "summary", "materials"})
        self.assertEqual(payload["root"], self.root.as_posix())
        for row in payload["materials"]:
            self.assertEqual(set(row), {
                "resource_id", "title", "material_kind", "subjects", "acquisition",
                "rights_status", "rights_clear", "storage_mode", "review_status",
                "bytes_verified", "can_back_evidence", "may_be_structured", "source_url",
                "publisher",
            })

    def test_subject_filter_applies_after_full_validation(self) -> None:
        entries = [
            local_material("only-a"),
            local_material("a-and-b", subjects=[SUBJECT_A, SUBJECT_B]),
            local_material("only-b", subjects=[SUBJECT_B]),
        ]
        code, out, _ = self.standalone(entries, "--subject", SUBJECT_B, "--json")
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual([m["resource_id"] for m in payload["materials"]], ["a-and-b", "only-b"])
        self.assertEqual(payload["summary"]["total"], 2)
        code, out, _ = self.standalone(entries, "--subject", "absent", "--json")
        self.assertEqual((code, json.loads(out)["materials"]), (0, []))
        invalid = [*entries, local_material("bad", subjects=["gamma"])]
        self.assertEqual(self.standalone(invalid, "--subject", SUBJECT_B)[0], 2)

    def test_invalid_ledger_exits_two_with_a_prefixed_message(self) -> None:
        code, out, err = self.standalone([local_material(), local_material()])
        self.assertEqual((code, out), (2, ""))
        self.assertTrue(err.startswith("ledger violation: "), err)

    def test_usage_error_exits_two(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as ctx:
            run_cli("--no-such-flag")
        self.assertEqual(ctx.exception.code, 2)

    def test_registry_mode_defaults_and_subject_override(self) -> None:
        registry = write_registry(self.root, subjects=[SUBJECT_A, SUBJECT_B])
        write_ledger(self.root, [local_material("b", subjects=[SUBJECT_B])])
        code, out, err = run_cli("--workspace", str(registry), "--json")
        self.assertEqual(code, 0, err)
        payload = json.loads(out)
        self.assertEqual(payload["root"], self.root.as_posix())
        self.assertEqual(payload["ledger"], (self.root / "data" / "ledger.yaml").as_posix())
        code, _, err = run_cli("--workspace", str(registry), "--subjects", SUBJECT_A)
        self.assertEqual(code, 2)
        self.assertIn("subjects[0]", err)

    def test_missing_registered_ledger_exits_two(self) -> None:
        registry = write_registry(self.root, subjects=[SUBJECT_A])
        code, out, err = run_cli("--workspace", str(registry))
        self.assertEqual((code, out), (2, ""))
        self.assertTrue(err.startswith("ledger violation: "), err)

    def test_the_command_writes_nothing(self) -> None:
        target = self.root / STORE_PATH
        target.parent.mkdir(parents=True)
        target.write_bytes(PAYLOAD)
        registry = write_registry(self.root, subjects=[SUBJECT_A])
        write_ledger(self.root, [local_material(), remote_material()])
        before = tree_bytes(self.root)
        for extra in ((), ("--json",)):
            code, _, err = run_cli("--workspace", str(registry), *extra)
            self.assertEqual(code, 0, err)
        self.assertEqual(tree_bytes(self.root), before)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
