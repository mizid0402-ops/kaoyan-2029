from __future__ import annotations

import copy
import hashlib
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from ky.knowledge.syllabus_mapping import load_syllabus_mapping
from ky.models import ContractError
from ky.workspace import WORKSPACE_FILENAME, load_workspace
from tests.contract.test_workspace import BASE_DOCUMENT, _write_doc


class SyllabusMappingPortTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        source_file = self.root / "data/source.txt"
        source_file.parent.mkdir(parents=True)
        source_file.write_text("outline", encoding="utf-8")
        digest = hashlib.sha256(source_file.read_bytes()).hexdigest()
        self.old_ids = (
            "alpha.ds.chapter-01.section-01",
            "alpha.ds.chapter-01.section-02",
            "alpha.ds.chapter-01.section-03",
            "alpha.ds.chapter-01.section-04",
            "alpha.ds.chapter-01.section-05",
        )
        self.new_ids = (
            self.old_ids[0],
            "alpha.ds.chapter-01.section-06",
            "alpha.ds.chapter-01.section-07",
            "alpha.ds.chapter-01.section-08",
            "alpha.ds.chapter-01.section-09",
        )
        self.old_tree = self._write_tree("old.yaml", self.old_ids, digest)
        self.new_tree = self._write_tree("new.yaml", self.new_ids, digest)
        document = copy.deepcopy(BASE_DOCUMENT)
        document["reference"]["knowledge_trees"] = {"alpha": "data/old.yaml"}
        document["reference"]["syllabus_versions"] = {
            "alpha": {
                "versions": {"2026": "data/old.yaml", "2027": "data/new.yaml"},
                "mappings": ["data/map.yaml"],
            }
        }
        self.registry_path = self.root / WORKSPACE_FILENAME
        _write_doc(self.registry_path, document)
        self.workspace = load_workspace(self.registry_path)
        self.mapping_path = self.root / "data/map.yaml"
        self.base_mapping = {
            "schema_version": 1,
            "kind": "syllabus_mapping",
            "subject_id": "alpha",
            "from_version": "2026",
            "to_version": "2027",
            "basis": "Compare both outline versions chapter by chapter.",
            "changes": [
                {"from": self.old_ids[1], "to": [self.new_ids[1], self.new_ids[2]]},
                {"from": self.old_ids[2], "to": [self.new_ids[3]]},
                {"from": self.old_ids[3], "to": [self.new_ids[3]]},
                {"from": self.old_ids[4], "to": []},
            ],
            "added": [self.new_ids[4]],
        }
        self._write_mapping(self.base_mapping)

    def _write_tree(self, name: str, ids: tuple[str, ...], digest: str) -> Path:
        path = self.root / "data" / name
        nodes = [
            {
                "schema_version": 1,
                "knowledge_point_id": point_id,
                "title": point_id,
                "status": "raw",
                "source_kind": "official_outline",
                "sources": [{"path": "source.txt", "sha256": digest,
                             "locator": {"quote_ref": "outline"}}],
                "scope": "section",
            }
            for point_id in ids
        ]
        path.write_text(yaml.safe_dump(nodes, sort_keys=False), encoding="utf-8")
        return path

    def _write_mapping(self, document: dict) -> None:
        self.mapping_path.write_text(
            yaml.safe_dump(document, sort_keys=False), encoding="utf-8"
        )

    def _assert_invalid(self, document: dict, message: str) -> None:
        self._write_mapping(document)
        with self.assertRaisesRegex(ContractError, message):
            load_syllabus_mapping(
                self.mapping_path, self.workspace, subject_id="alpha"
            )

    def test_preserve_split_merge_delete_and_add(self) -> None:
        mapping = load_syllabus_mapping(
            self.mapping_path, self.workspace, subject_id="alpha"
        )
        self.assertEqual(mapping.targets(self.old_ids[0]), (self.old_ids[0],))
        self.assertEqual(mapping.targets(self.old_ids[1]), (self.new_ids[1], self.new_ids[2]))
        self.assertEqual(mapping.targets(self.old_ids[2]), (self.new_ids[3],))
        self.assertEqual(mapping.targets(self.old_ids[3]), (self.new_ids[3],))
        self.assertEqual(mapping.targets(self.old_ids[4]), ())

    def test_explicit_self_target_preserves_common_id(self) -> None:
        document = copy.deepcopy(self.base_mapping)
        document["changes"].append(
            {"from": self.old_ids[0], "to": [self.old_ids[0]]}
        )
        self._write_mapping(document)
        mapping = load_syllabus_mapping(
            self.mapping_path, self.workspace, subject_id="alpha"
        )
        self.assertEqual(mapping.targets(self.old_ids[0]), (self.old_ids[0],))

    def test_rejects_undeclared_deletion(self) -> None:
        document = copy.deepcopy(self.base_mapping)
        document["changes"].pop()
        self._assert_invalid(document, "undeclared deletion or rename")

    def test_rejects_new_id_without_source_or_added(self) -> None:
        document = copy.deepcopy(self.base_mapping)
        document["added"] = []
        self._assert_invalid(document, "new ID has no source and is not added")

    def test_rejects_common_id_explicitly_removed(self) -> None:
        document = copy.deepcopy(self.base_mapping)
        document["changes"].append({"from": self.old_ids[0], "to": []})
        self._assert_invalid(document, "new ID has no source and is not added")

    def test_rejects_common_id_redirect_without_self_target(self) -> None:
        document = copy.deepcopy(self.base_mapping)
        document["changes"].append(
            {"from": self.old_ids[0], "to": [self.new_ids[1]]}
        )
        self._assert_invalid(document, "new ID has no source and is not added")

    def test_rejects_implicit_self_with_another_explicit_source(self) -> None:
        document = copy.deepcopy(self.base_mapping)
        document["changes"][1]["to"].append(self.new_ids[0])
        self._assert_invalid(document, "new ID has multiple sources")

    def test_rejects_added_and_change_target_duplicate(self) -> None:
        document = copy.deepcopy(self.base_mapping)
        document["changes"].append({"from": self.old_ids[0], "to": [self.new_ids[4]]})
        document["changes"][0]["to"].append(self.new_ids[4])
        self._assert_invalid(document, "also appears in changes.to")

    def test_rejects_duplicate_from(self) -> None:
        document = copy.deepcopy(self.base_mapping)
        document["changes"].append(copy.deepcopy(document["changes"][0]))
        self._assert_invalid(document, "from ID appears more than once")

    def test_rejects_duplicate_target_in_one_change(self) -> None:
        document = copy.deepcopy(self.base_mapping)
        document["changes"][0]["to"].append(document["changes"][0]["to"][0])
        self._write_mapping(document)
        with self.assertRaises(ContractError) as context:
            load_syllabus_mapping(
                self.mapping_path, self.workspace, subject_id="alpha"
            )
        self.assertEqual(context.exception.path, "changes[0].to[2]")

    def test_rejects_to_outside_new_tree(self) -> None:
        document = copy.deepcopy(self.base_mapping)
        document["changes"][0]["to"] = ["alpha.ds.chapter-01.section-99"]
        self._assert_invalid(document, "to ID is not in new tree")

    def test_rejects_unregistered_version(self) -> None:
        document = copy.deepcopy(self.base_mapping)
        document["to_version"] = "2028"
        self._assert_invalid(document, "version is not registered")

    def test_rejects_equal_versions(self) -> None:
        document = copy.deepcopy(self.base_mapping)
        document["to_version"] = "2026"
        self._assert_invalid(document, "from_version must differ")

    def test_rejects_unknown_key(self) -> None:
        document = copy.deepcopy(self.base_mapping)
        document["unexpected"] = True
        self._assert_invalid(document, "unknown field")

    def test_rejects_mapping_loaded_for_another_subject(self) -> None:
        document = copy.deepcopy(self.base_mapping)
        document["subject_id"] = "cs408"
        self._write_mapping(document)
        with self.assertRaises(ContractError) as context:
            load_syllabus_mapping(
                self.mapping_path, self.workspace, subject_id="alpha"
            )
        self.assertEqual(context.exception.path, "subject_id")

    def test_rejects_unregistered_mapping_path(self) -> None:
        unregistered = self.root / "data/unregistered.yaml"
        unregistered.write_bytes(self.mapping_path.read_bytes())
        with self.assertRaises(ContractError) as context:
            load_syllabus_mapping(
                unregistered, self.workspace, subject_id="alpha"
            )
        self.assertEqual(context.exception.path, "path")
        self.assertIn("mapping file is not registered", str(context.exception))

    def test_rejects_mapping_tree_through_escaping_junction(self) -> None:
        if os.name != "nt":
            self.skipTest("directory junction probe requires Windows")
        import _winapi

        outside = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        shutil.copyfile(self.new_tree, outside / "new.yaml")
        junction = self.root / "data" / "outside-tree"
        try:
            _winapi.CreateJunction(str(outside), str(junction))
        except OSError as exc:
            self.skipTest(f"directory junction unavailable in this environment: {exc}")

        registry_doc = yaml.safe_load(self.registry_path.read_text(encoding="utf-8"))
        registry_doc["reference"]["syllabus_versions"]["alpha"]["versions"][
            "2027"
        ] = "data/outside-tree/new.yaml"
        _write_doc(self.registry_path, registry_doc)
        workspace = load_workspace(self.registry_path)
        with self.assertRaises(ContractError) as context:
            load_syllabus_mapping(
                self.mapping_path, workspace, subject_id="alpha"
            )
        self.assertEqual(
            context.exception.path,
            "reference.syllabus_versions.alpha.versions.2027",
        )
        self.assertIn("outside the workspace", str(context.exception))

    def test_targets_rejects_id_outside_source_tree(self) -> None:
        mapping = load_syllabus_mapping(
            self.mapping_path, self.workspace, subject_id="alpha"
        )
        with self.assertRaises(ContractError) as context:
            mapping.targets("alpha.ds.chapter-99.section-99")
        self.assertEqual(context.exception.path, "old_id")

    def test_root_unknown_mixed_keys_raise_contract_error(self) -> None:
        document = copy.deepcopy(self.base_mapping)
        document[7] = "unexpected numeric key"
        document["zzz"] = "unexpected string key"
        self._write_mapping(document)
        with self.assertRaises(ContractError) as context:
            load_syllabus_mapping(
                self.mapping_path, self.workspace, subject_id="alpha"
            )
        self.assertEqual(context.exception.path, "7")
        self.assertIn("unknown field", str(context.exception))

    def test_change_unknown_mixed_keys_raise_contract_error(self) -> None:
        document = copy.deepcopy(self.base_mapping)
        document["changes"][0][7] = "unexpected numeric key"
        document["changes"][0]["zzz"] = "unexpected string key"
        self._write_mapping(document)
        with self.assertRaises(ContractError) as context:
            load_syllabus_mapping(
                self.mapping_path, self.workspace, subject_id="alpha"
            )
        self.assertEqual(context.exception.path, "changes[0].7")
        self.assertIn("unknown field", str(context.exception))


if __name__ == "__main__":
    unittest.main()
