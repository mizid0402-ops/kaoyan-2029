from __future__ import annotations

import copy
import hashlib
import os
import tempfile
import unittest
from dataclasses import fields
from pathlib import Path
from unittest.mock import patch

import yaml

from tests._resources import require_path
from tests._fixtures import set_nested_value

from ky.models import ContractError
from ky.workspace import (
    WORKSPACE_ENV,
    WORKSPACE_FILENAME,
    find_workspace,
    load_workspace,
)

ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_FILE = ROOT / WORKSPACE_FILENAME

# Replacement implementations can register here and will run through the same
# language-independent acceptance contract.
LOADERS = [load_workspace]

BASE_DOCUMENT = {
    "schema_version": 2,
    "subjects": {
        "alpha": {"name": "Alpha", "tree_grammar": "named_chapters"},
        "beta": {"name": "Beta"},
    },
    "reference": {
        "knowledge_trees": {"alpha": "data/tree.yaml"},
        "exam_indexes": {"alpha": ["data/index.json"]},
        "paper_shapes": {},
        "topic_weights": "data/weights.json",
        "weight_batches": "data/batches.yaml",
        "vocabulary_db": "data/vocabulary.sqlite",
        "ledger": "data/materials.yaml",
    },
    "supplementary": {
        "alpha_supplement": {
            "kind": "cross_year_tree",
            "subject": "alpha",
            "description": "supplementary tree",
            "files": {"tree": "data/tree-all.yaml", "agreement": "data/agreement.yaml"},
        }
    },
    "materials": {"raw_root": "data/raw"},
    "products": {"lecture": "review/lecture"},
    "settings": {},
    "state": {"review_queue": "data/queue", "plans": "data/plans"},
    "staging": "staging",
    "projection": "data/projection.sqlite",
}


def _write_doc(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _write_local_doc(root: Path, doc: dict) -> Path:
    path = root / "kaoyan.workspace.local.yaml"
    _write_doc(path, doc)
    return path


def _path_snapshot(root: Path) -> dict[str, bytes | None]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes() if path.is_file() else None
        for path in root.rglob("*")
    }


def _registry_variants(seed: dict) -> list[tuple[str, dict, bool]]:
    """Generate the former registry matrix as current workspace inputs."""
    variants: list[tuple[str, dict, bool]] = []

    def add(name: str, path: tuple[str, ...], value: object) -> None:
        document = copy.deepcopy(seed)
        set_nested_value(document, path, value)
        variants.append((name, document, False))

    for key in seed:
        document = copy.deepcopy(seed)
        del document[key]
        variants.append((f"missing-top-level-{key}", document,
                         key in {"supplementary", "products", "settings"}))
    add("schema-version-type", ("schema_version",), "2")
    add("subjects-type", ("subjects",), [])
    add("reference-type", ("reference",), [])
    unknown = copy.deepcopy(seed)
    unknown["unexpected"] = "value"
    variants.append(("unknown-root-key", unknown, False))
    subjects = seed["subjects"]
    subject = next(iter(subjects))
    profile = copy.deepcopy(subjects[subject])
    invalid_subjects = copy.deepcopy(subjects)
    del invalid_subjects[subject]
    invalid_subjects[f"{subject}-bad"] = profile
    add("invalid-subject-id", ("subjects",), invalid_subjects)
    add("subject-profile-type", ("subjects", subject), "profile")

    for name, value in (
        ("path-parent-segment", "../outside.yaml"),
        ("path-backslash", r"data\outside.yaml"),
        ("path-absolute", "/outside/workspace.yaml"),
    ):
        add(name, ("reference", "topic_weights"), value)

    reference = seed["reference"]
    add("syllabus-versions-type", ("reference", "syllabus_versions"), [])
    syllabus_subject = next(iter(reference.get("syllabus_versions", subjects)))
    for name, path, value in (
        ("syllabus-unknown-subject", ("reference", "syllabus_versions", "unknownsubject"),
         {"versions": {"2026": "data/tree.yaml"}, "mappings": []}),
        ("syllabus-record-type", ("reference", "syllabus_versions", syllabus_subject), "record"),
        ("syllabus-versions-empty", ("reference", "syllabus_versions", syllabus_subject,
                                      "versions"), {}),
        ("syllabus-invalid-label", ("reference", "syllabus_versions", syllabus_subject,
                                     "versions"), {"bad": "data/tree.yaml"}),
        ("syllabus-mappings-type", ("reference", "syllabus_versions", syllabus_subject,
                                    "mappings"), "mapping.yaml"),
        ("syllabus-effective-tree-mismatch", ("reference", "syllabus_versions",
                                                syllabus_subject, "versions"),
         {"2099": "data/another-tree.yaml"}),
    ):
        add(name, path, value)
    existing_path = next(iter(reference["syllabus_versions"][syllabus_subject]["versions"].values()))
    add("syllabus-duplicate-path", ("reference", "syllabus_versions", syllabus_subject,
                                     "versions"), {"2026": existing_path, "2027": existing_path})
    add("paper-shapes-type", ("reference", "paper_shapes"), [])
    add("paper-shapes-unknown-subject", ("reference", "paper_shapes"),
        {"unknownsubject": "data/paper.yaml"})
    add("paper-shapes-invalid-path", ("reference", "paper_shapes"),
        {subject: "../paper.yaml"})
    add("weight-batches-invalid-path", ("reference", "weight_batches"), "../batches.yaml")
    add("weight-batches-type", ("reference", "weight_batches"), [])
    add("exam-index-unknown-subject-before-value-type", ("reference", "exam_indexes"),
        {"unknownsubject": "not-a-list"})

    for key in seed:
        document = copy.deepcopy(seed)
        del document[key]
        if key == "schema_version":
            document["subjects"] = []
        else:
            document["schema_version"] = "2"
        variants.append((f"double-error-schema-before-{key}", document, False))

    def paired(
        name: str,
        first: tuple[str, ...],
        first_value: object,
        second: tuple[str, ...],
        second_value: object,
    ) -> None:
        document = copy.deepcopy(seed)
        set_nested_value(document, first, first_value)
        set_nested_value(document, second, second_value)
        variants.append((name, document, False))

    paired("subject-before-reference", ("subjects", subject), "profile",
           ("reference", "topic_weights"), "../bad")
    paired("knowledge-before-syllabus", ("reference", "knowledge_trees"), [],
           ("reference", "syllabus_versions"), [])
    paired("syllabus-before-exam-indexes", ("reference", "syllabus_versions"), [],
           ("reference", "exam_indexes"), [])
    paired("exam-indexes-before-paper-shapes", ("reference", "exam_indexes"), [],
           ("reference", "paper_shapes"), [])
    paired("paper-shapes-before-weight-path", ("reference", "paper_shapes"), [],
           ("reference", "topic_weights"), "../bad")
    paired("reference-before-supplementary", ("reference", "topic_weights"), "../bad",
           ("supplementary",), [])
    paired("supplementary-before-materials", ("supplementary",), [], ("materials",), [])
    paired("materials-before-products", ("materials",), [], ("products",), [])
    paired("products-before-settings", ("products",), [], ("settings",), [])
    paired("settings-before-state", ("settings",), [], ("state",), [])
    paired("state-before-staging", ("state",), [], ("staging",), "../bad")
    paired("staging-before-projection", ("staging",), "../bad",
           ("projection",), "../bad")
    return variants


class WorkspaceContractTests(unittest.TestCase):
    def test_weighted_mastery_is_a_registered_subject_feature(self) -> None:
        document = copy.deepcopy(BASE_DOCUMENT)
        document["subjects"]["alpha"]["features"] = ["weighted_mastery"]
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / WORKSPACE_FILENAME
            _write_doc(source, document)
            workspace = load_workspace(source)
            self.assertEqual(workspace.subject_profiles["alpha"].features,
                             ("weighted_mastery",))

            document["subjects"]["alpha"]["features"] = ["unrecognized"]
            _write_doc(source, document)
            with self.assertRaises(ContractError) as caught:
                load_workspace(source)
        self.assertEqual(caught.exception.path, "subjects.alpha.features[0]")

    def test_single_error_variant_table(self) -> None:
        seed = yaml.safe_load(WORKSPACE_FILE.read_text(encoding="utf-8"))
        variants = _registry_variants(seed)
        retired = {
            "double-error-schema-before-schema_version",
            "double-error-schema-before-subjects",
            "double-error-schema-before-reference",
            "double-error-schema-before-materials",
            "double-error-schema-before-state",
            "double-error-schema-before-staging",
            "double-error-schema-before-projection",
            "subject-before-reference", "knowledge-before-syllabus",
            "syllabus-before-exam-indexes", "exam-indexes-before-paper-shapes",
            "paper-shapes-before-weight-path", "reference-before-supplementary",
            "supplementary-before-materials", "materials-before-products",
            "products-before-settings", "settings-before-state", "state-before-staging",
            "staging-before-projection",
        }
        cases = [row for row in variants if row[0] not in retired]
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / WORKSPACE_FILENAME
            for name, document, expected_success in cases:
                with self.subTest(variant=name):
                    _write_doc(source, document)
                    if expected_success:
                        load_workspace(source)
                    else:
                        with self.assertRaises(ContractError):
                            load_workspace(source)

    def test_syllabus_versions_effective_pointer_and_labels(self) -> None:
        document = copy.deepcopy(BASE_DOCUMENT)
        document["reference"]["syllabus_versions"] = {
            "alpha": {"versions": {"2026": "data/tree.yaml"}, "mappings": []}
        }
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / WORKSPACE_FILENAME
            _write_doc(source, document)
            workspace = load_workspace(source)
            self.assertEqual(
                workspace.syllabus_versions["alpha"].versions["2026"],
                source.parent / "data/tree.yaml",
            )
            self.assertEqual(workspace.effective_version("alpha"), "2026")
            self.assertIsNone(workspace.effective_version("beta"))
            self.assertEqual(
                workspace.require_all("reference.syllabus_versions.alpha.mappings"), ()
            )

            altered = copy.deepcopy(document)
            altered["reference"]["syllabus_versions"]["alpha"]["versions"] = {
                "2026": "data/other-tree.yaml"
            }
            _write_doc(source, altered)
            with self.assertRaisesRegex(ContractError, "reference.knowledge_trees.alpha"):
                load_workspace(source)

            altered["reference"]["syllabus_versions"]["alpha"]["versions"] = {
                2026: "data/tree.yaml"
            }
            _write_doc(source, altered)
            with self.assertRaisesRegex(ContractError, "four-digit string"):
                load_workspace(source)

            altered["reference"]["syllabus_versions"]["alpha"]["versions"] = {
                "2026": "data/tree.yaml"
            }
            altered["reference"]["syllabus_versions"]["ghost"] = {
                "versions": {"2026": "data/tree.yaml"}, "mappings": []
            }
            _write_doc(source, altered)
            with self.assertRaisesRegex(ContractError, "subject is not declared"):
                load_workspace(source)

    def test_syllabus_versions_reject_duplicate_tree_path(self) -> None:
        document = copy.deepcopy(BASE_DOCUMENT)
        document["reference"]["syllabus_versions"] = {
            "alpha": {
                "versions": {
                    "2026": "data/tree.yaml",
                    "2027": "data/tree.yaml",
                },
                "mappings": [],
            }
        }
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / WORKSPACE_FILENAME
            _write_doc(source, document)
            with self.assertRaises(ContractError) as context:
                load_workspace(source)
            self.assertEqual(
                context.exception.path,
                "reference.syllabus_versions.alpha.versions.2027",
            )
            self.assertIn("already registered", str(context.exception))

    def test_effective_version_is_independent_of_version_mapping_order(self) -> None:
        document = copy.deepcopy(BASE_DOCUMENT)
        document["reference"]["syllabus_versions"] = {
            "alpha": {
                "versions": {
                    "2026": "data/tree.yaml",
                    "2027": "data/other-tree.yaml",
                },
                "mappings": [],
            }
        }
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / WORKSPACE_FILENAME
            _write_doc(source, document)
            self.assertEqual(load_workspace(source).effective_version("alpha"), "2026")

            document["reference"]["syllabus_versions"]["alpha"]["versions"] = {
                "2027": "data/other-tree.yaml",
                "2026": "data/tree.yaml",
            }
            _write_doc(source, document)
            self.assertEqual(load_workspace(source).effective_version("alpha"), "2026")

    def test_require_mapping_list_error_depends_on_registration(self) -> None:
        document = copy.deepcopy(BASE_DOCUMENT)
        document["reference"]["syllabus_versions"] = {
            "alpha": {"versions": {"2026": "data/tree.yaml"}, "mappings": []}
        }
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / WORKSPACE_FILENAME
            _write_doc(source, document)
            workspace = load_workspace(source)
            with self.assertRaises(ContractError) as registered:
                workspace.require("reference.syllabus_versions.alpha.mappings")
            self.assertEqual(
                registered.exception.path,
                "reference.syllabus_versions.alpha.mappings",
            )
            self.assertIn("use require_all", str(registered.exception))

            with self.assertRaises(ContractError) as missing:
                workspace.require("reference.syllabus_versions.ghost.mappings")
            self.assertEqual(
                missing.exception.path,
                "reference.syllabus_versions.ghost.mappings",
            )
            self.assertIn("not registered", str(missing.exception))

    def test_1_repository_registry(self) -> None:
        repo = Path(__file__).resolve().parents[2]
        expected_indexes = {path.relative_to(repo).as_posix() for path in (repo / "data/exam_questions").glob("*.json")}

        for loader in LOADERS:
            with self.subTest(loader=loader.__name__):
                workspace = loader(repo / WORKSPACE_FILENAME)
                self.assertEqual(workspace.subjects, tuple(workspace.subject_profiles))
                actual_indexes = {path.relative_to(repo).as_posix() for paths in workspace.exam_indexes.values() for path in paths}
                self.assertEqual(actual_indexes, expected_indexes)
                self.assertEqual(
                    sum(map(len, workspace.exam_indexes.values())),
                    len(expected_indexes),
                )
                single_keys = [
                    "reference.topic_weights",
                    "reference.vocabulary_db",
                    "reference.ledger",
                    "materials.raw_root",
                ]
                if workspace.weight_batches is not None:
                    single_keys.append("reference.weight_batches")
                single_keys.extend(f"reference.knowledge_trees.{key}" for key in workspace.knowledge_trees)
                single_keys.extend(
                    f"reference.paper_shapes.{key}" for key in workspace.paper_shapes
                )
                single_keys.extend(
                    f"reference.timetable_schools.{key}"
                    for key in workspace.timetable_schools
                )
                single_keys.extend(
                    f"supplementary.{name}.files.{role}"
                    for name, view in workspace.supplementary.items()
                    for role in view.files
                )
                single_keys.extend(f"products.{key}" for key in workspace.products)
                if workspace.exam_config is not None:
                    single_keys.append("settings.exam_config")
                # Raw materials and product workspaces are gitignored; a clean clone lacks them
                # (C1, WP-G1). Every tracked registration is still required to exist.
                ignored = {
                    "materials.raw_root": (workspace.raw_root, "按 data/materials.yaml 重取原始资料"),
                }
                ignored.update(
                    (f"products.{key}", (path, "本机产品工作区，由对应生产线工具生成或从备份恢复"))
                    for key, path in workspace.products.items()
                )
                for key in single_keys:
                    if key in ignored and not ignored[key][0].exists():
                        with self.subTest(missing_resource=key):
                            require_path(self, *ignored[key])
                        continue
                    workspace.require(key)
                for subject in workspace.exam_indexes:
                    workspace.require_all(f"reference.exam_indexes.{subject}")

    def test_2_paths_are_relative_to_registry_even_from_child_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "copied" / WORKSPACE_FILENAME
            _write_doc(source, BASE_DOCUMENT)
            child = source.parent / "deep" / "inside"
            child.mkdir(parents=True)
            for loader in LOADERS:
                with self.subTest(loader=loader.__name__):
                    loaded = loader(source)
                    self.assertEqual(loaded.root, source.parent.absolute())
                    self.assertEqual(loaded.topic_weights, source.parent / "data/weights.json")
                    self.assertEqual(
                        loaded.weight_batches, source.parent / "data/batches.yaml"
                    )
                    with patch("pathlib.Path.cwd", return_value=child):
                        found = find_workspace()
                    self.assertEqual(found, source.absolute())

    def test_3_structure_rejections_report_contract_paths(self) -> None:
        cases: list[tuple[str, str]] = []

        def altered(label: str, path: str, value: object = None, *, remove: bool = False, expected: str | None = None) -> None:
            doc = copy.deepcopy(BASE_DOCUMENT)
            node = doc
            bits = path.split(".")
            for part in bits[:-1]:
                node = node[part]
            if remove:
                del node[bits[-1]]
            else:
                node[bits[-1]] = value
            cases.append((label, expected if expected is not None else path, yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)))

        cases.append(("top-level list", "", "- one\n"))
        altered("unknown top-level", "mystery", "x")
        altered("unknown reference", "reference.mystery", "x")
        altered("paper shape undeclared subject", "reference.paper_shapes.gamma", "data/gamma.yaml")
        altered("unknown view", "supplementary.alpha_supplement.mystery", "x")
        altered("schema version 1", "schema_version", 1)
        altered("boolean version", "schema_version", True)
        altered("missing version", "schema_version", remove=True)
        altered("empty subjects", "subjects", {})
        altered("subjects list", "subjects", ["alpha"])
        altered(
            "invalid subject id",
            "subjects",
            {"CS408": {"name": "Alpha"}},
            expected="subjects.CS408",
        )
        altered(
            "missing profile name",
            "subjects.alpha",
            {"tree_grammar": "named_chapters"},
            expected="subjects.alpha.name",
        )
        altered(
            "unknown profile field",
            "subjects.alpha.extra",
            "x",
            expected="subjects.alpha.extra",
        )
        altered(
            "unknown tree grammar",
            "subjects.alpha.tree_grammar",
            "nested",
            expected="subjects.alpha.tree_grammar",
        )
        altered(
            "wrong feature type",
            "subjects.alpha.features",
            "vocabulary",
            expected="subjects.alpha.features",
        )
        altered(
            "unknown feature",
            "subjects.alpha.features",
            ["unknown"],
            expected="subjects.alpha.features[0]",
        )
        altered(
            "tree without grammar",
            "subjects.alpha.tree_grammar",
            remove=True,
            expected="subjects.alpha.tree_grammar",
        )
        altered(
            "unknown tree subject",
            "reference.knowledge_trees",
            {"unknown": "tree.yaml"},
            expected="reference.knowledge_trees.unknown",
        )
        altered(
            "unknown index subject",
            "reference.exam_indexes",
            {"unknown": ["index.json"]},
            expected="reference.exam_indexes.unknown",
        )
        altered("empty index list", "reference.exam_indexes.alpha", [])
        altered(
            "duplicate index path",
            "reference.exam_indexes",
            {"alpha": ["same.json"], "beta": ["same.json"]},
            expected="reference.exam_indexes.beta[0]",
        )
        altered("unknown kind", "supplementary.alpha_supplement.kind", "unknown")
        altered("unknown view subject", "supplementary.alpha_supplement.subject", "unknown")
        altered(
            "missing agreement role",
            "supplementary.alpha_supplement.files",
            {"tree": "tree.yaml"},
            expected="supplementary.alpha_supplement.files.agreement",
        )
        altered(
            "extra view role",
            "supplementary.alpha_supplement.files",
            {"tree": "tree.yaml", "agreement": "agreement.yaml", "other": "other.yaml"},
            expected="supplementary.alpha_supplement.files.other",
        )
        altered("numeric path", "reference.topic_weights", 42)
        raw_duplicates = [
            ("top duplicate", "schema_version", "schema_version: 2\nschema_version: 2\n"),
            ("nested duplicate", "reference.topic_weights", yaml.safe_dump(BASE_DOCUMENT, allow_unicode=True, sort_keys=False).replace("reference:\n", "reference:\n  topic_weights: data/other.json\n", 1)),
            # Round-45 review M1: a quoted parent key and a flow mapping must still report the
            # real duplicated field, not a neighbour left over from text re-parsing.
            ("quoted parent duplicate", "reference.topic_weights", yaml.safe_dump(BASE_DOCUMENT, allow_unicode=True, sort_keys=False).replace("reference:\n", '"reference":\n  topic_weights: data/other.json\n', 1)),
            ("flow mapping duplicate", "materials.raw_root", yaml.safe_dump(BASE_DOCUMENT, allow_unicode=True, sort_keys=False).replace("materials:\n  raw_root: data/raw\n", "materials: {raw_root: data/raw, raw_root: data/other}\n", 1)),
        ]

        for loader in LOADERS:
            for label, expected_field, content in cases:
                with self.subTest(loader=loader.__name__, case=label), tempfile.TemporaryDirectory() as temporary:
                    source = Path(temporary) / WORKSPACE_FILENAME
                    source.write_text(content, encoding="utf-8")
                    with self.assertRaises(ContractError) as caught:
                        loader(source)
                    self.assertEqual(caught.exception.path, expected_field, msg=label)
            for label, expected_field, content in raw_duplicates:
                with self.subTest(loader=loader.__name__, case=label), tempfile.TemporaryDirectory() as temporary:
                    source = Path(temporary) / WORKSPACE_FILENAME
                    source.write_text(content, encoding="utf-8")
                    with self.assertRaises(ContractError) as caught:
                        loader(source)
                    self.assertEqual(caught.exception.path, expected_field, msg=label)

    def test_3b_cyclic_alias_is_a_contract_violation_not_a_crash(self) -> None:
        # Round-45 re-review M4: a self-referencing alias must be rejected, not recurse forever.
        content = (
            "schema_version: 2\n"
            "subjects: {alpha: {name: Alpha, tree_grammar: named_chapters}}\n"
            "reference: &x\n  self: *x\n"
        )
        for loader in LOADERS:
            with self.subTest(loader=loader.__name__), tempfile.TemporaryDirectory() as temporary:
                source = Path(temporary) / WORKSPACE_FILENAME
                source.write_text(content, encoding="utf-8")
                with self.assertRaises(ContractError) as caught:
                    loader(source)
                self.assertEqual(caught.exception.path, "reference.self")

    def test_4_registered_path_syntax_is_rejected(self) -> None:
        bad_paths = ["/abs", "C:/x", "C:x", "\\\\server\\share", "a\\b", "a/../b", "./a", "a//b", "a/", ""]
        for loader in LOADERS:
            for value in bad_paths:
                with self.subTest(loader=loader.__name__, path=value), tempfile.TemporaryDirectory() as temporary:
                    doc = copy.deepcopy(BASE_DOCUMENT)
                    doc["reference"]["topic_weights"] = value
                    source = Path(temporary) / WORKSPACE_FILENAME
                    _write_doc(source, doc)
                    with self.assertRaises(ContractError) as caught:
                        loader(source)
                    self.assertEqual(caught.exception.path, "reference.topic_weights")

            with tempfile.TemporaryDirectory() as temporary:
                doc = copy.deepcopy(BASE_DOCUMENT)
                doc["reference"]["weight_batches"] = "../outside.yaml"
                source = Path(temporary) / WORKSPACE_FILENAME
                _write_doc(source, doc)
                with self.assertRaises(ContractError) as caught:
                    loader(source)
                self.assertEqual(caught.exception.path, "reference.weight_batches")

    def test_4b_weight_batches_registration_is_optional(self) -> None:
        for loader in LOADERS:
            with self.subTest(loader=loader.__name__), tempfile.TemporaryDirectory() as temporary:
                doc = copy.deepcopy(BASE_DOCUMENT)
                doc["reference"].pop("weight_batches")
                source = Path(temporary) / WORKSPACE_FILENAME
                _write_doc(source, doc)
                workspace = loader(source)
                self.assertIsNone(workspace.weight_batches)
                with self.assertRaises(ContractError) as caught:
                    workspace.require("reference.weight_batches")
                self.assertEqual(caught.exception.path, "reference.weight_batches")

    def test_5_lazy_existence_type_and_symlink_checks(self) -> None:
        for loader in LOADERS:
            with self.subTest(loader=loader.__name__), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "workspace"
                root.mkdir()
                source = root / WORKSPACE_FILENAME
                doc = copy.deepcopy(BASE_DOCUMENT)
                doc["reference"]["topic_weights"] = "missing.json"
                doc["materials"]["raw_root"] = "raw-file"
                doc["reference"]["vocabulary_db"] = "as-directory"
                doc["products"]["lecture"] = "raw-file"
                _write_doc(source, doc)
                (root / "raw-file").write_text("x", encoding="utf-8")
                (root / "as-directory").mkdir()
                workspace = loader(source)  # Registered paths need not exist at load time.
                with self.assertRaises(ContractError) as caught:
                    workspace.require("reference.knowledge_trees.unknown")
                self.assertEqual(caught.exception.path, "reference.knowledge_trees.unknown")
                with self.assertRaises(ContractError) as caught:
                    workspace.require("reference.topic_weights")
                self.assertEqual(caught.exception.path, "reference.topic_weights")
                with self.assertRaises(ContractError) as caught:
                    workspace.require("reference.vocabulary_db")
                self.assertEqual(caught.exception.path, "reference.vocabulary_db")
                with self.assertRaises(ContractError) as caught:
                    workspace.require("materials.raw_root")
                self.assertEqual(caught.exception.path, "materials.raw_root")
                with self.assertRaises(ContractError) as caught:
                    workspace.require("products.lecture")
                self.assertEqual(caught.exception.path, "products.lecture")
                with self.assertRaises(ContractError) as caught:
                    workspace.require_all("reference.exam_indexes.alpha")
                self.assertEqual(caught.exception.path, "reference.exam_indexes.alpha")
                with self.assertRaises(ContractError) as caught:
                    workspace.require("reference.exam_indexes.alpha")
                self.assertEqual(caught.exception.path, "reference.exam_indexes.alpha")
                self.assertIn("use require_all", str(caught.exception))
                # Write targets are never require()-able, even when registered (spec section 4).
                for write_target in (
                    "state.review_queue", "state.plans", "staging", "projection",
                ):
                    with self.assertRaises(ContractError) as caught:
                        workspace.require(write_target)
                    self.assertEqual(caught.exception.path, write_target)

                # A directory junction needs no special privilege on Windows, so the
                # escapes-the-workspace check is exercised even where symlinks are refused.
                if os.name == "nt":
                    import _winapi

                    outside_dir = Path(temporary) / "outside-dir"
                    outside_dir.mkdir()
                    junction_doc = copy.deepcopy(doc)
                    junction_doc["products"]["lecture"] = "junction-dir"
                    _write_doc(source, junction_doc)
                    _winapi.CreateJunction(str(outside_dir), str(root / "junction-dir"))
                    junction_workspace = loader(source)
                    with self.assertRaises(ContractError) as caught:
                        junction_workspace.require("products.lecture")
                    self.assertEqual(caught.exception.path, "products.lecture")
                    self.assertIn("outside the workspace", str(caught.exception))
                    _write_doc(source, doc)
                with self.assertRaises(ContractError) as caught:
                    workspace.require_all("reference.topic_weights")
                self.assertEqual(caught.exception.path, "reference.topic_weights")

    def test_write_target_registered_path_does_not_require_or_create_target(self) -> None:
        for loader in LOADERS:
            with self.subTest(loader=loader.__name__), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "workspace"
                root.mkdir()
                source = root / WORKSPACE_FILENAME
                _write_doc(source, BASE_DOCUMENT)
                workspace = loader(source)

                target = workspace.write_target("state.plans")

                self.assertEqual(target, root / "data" / "plans")
                self.assertFalse(target.exists())

    def test_write_target_rejects_existing_targets_with_wrong_type(self) -> None:
        targets = (
            ("state.review_queue", ("state", "review_queue"), "data/queue", False),
            ("state.plans", ("state", "plans"), "data/plans", False),
            ("state.routes", ("state", "routes"), "data/routes", False),
            ("state.timetable", ("state", "timetable"), "data/timetable.yaml", True),
            ("staging", ("staging",), "data/staging", False),
            ("state.availability", ("state", "availability"), "data/availability", True),
            ("projection", ("projection",), "data/projection.sqlite", True),
        )
        for key, document_path, relative, wrong_is_directory in targets:
            with self.subTest(key=key), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "workspace"
                root.mkdir()
                doc = copy.deepcopy(BASE_DOCUMENT)
                if document_path[0] == "state":
                    doc["state"][document_path[1]] = relative
                else:
                    doc[document_path[0]] = relative
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                if wrong_is_directory:
                    target.mkdir()
                    expected = "expected a file"
                else:
                    target.write_text("occupied", encoding="utf-8")
                    expected = "expected a directory"
                source = root / WORKSPACE_FILENAME
                _write_doc(source, doc)

                with self.assertRaises(ContractError) as caught:
                    load_workspace(source).write_target(key)

                self.assertEqual(caught.exception.path, key)
                self.assertIn(expected, str(caught.exception))

    def test_write_target_accepts_exactly_the_write_destinations(self) -> None:
        # sol round 90, W2: the allowed-key set was only sampled; pin all of it.
        doc = copy.deepcopy(BASE_DOCUMENT)
        doc["state"] = {**doc["state"], "availability": "data/availability.yaml",
                        "routes": "data/routes", "timetable": "data/timetable.yaml"}
        # Each key must map to its own registered value, not merely to somewhere inside the
        # workspace (sol round 92: "staging" mapped to plans would still have passed).
        expected = {
            "state.review_queue": doc["state"]["review_queue"],
            "state.plans": doc["state"]["plans"],
            "state.availability": doc["state"]["availability"],
            "state.routes": doc["state"]["routes"],
            "state.timetable": doc["state"]["timetable"],
            "staging": doc["staging"],
            "projection": doc["projection"],
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "workspace"
            root.mkdir()
            source = root / WORKSPACE_FILENAME
            _write_doc(source, doc)
            workspace = load_workspace(source)
            for key, relative in expected.items():
                with self.subTest(key=key):
                    self.assertEqual(workspace.write_target(key), root / relative)
            for key in (
                "reference.ledger", "materials.raw_root",
                "reference.timetable_schools.sample",
            ):
                with self.subTest(key=key), self.assertRaises(ContractError) as caught:
                    workspace.write_target(key)
                self.assertEqual(caught.exception.path, key)

    def test_write_target_rejects_unregistered_key(self) -> None:
        for loader in LOADERS:
            with self.subTest(loader=loader.__name__), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "workspace"
                root.mkdir()
                source = root / WORKSPACE_FILENAME
                doc = copy.deepcopy(BASE_DOCUMENT)
                _write_doc(source, doc)

                with self.assertRaises(ContractError) as caught:
                    loader(source).write_target("state.availability")

                self.assertEqual(caught.exception.path, "state.availability")
                self.assertIn("not registered", str(caught.exception))

    def test_timetable_school_registry_keys_paths_and_require(self) -> None:
        cases = (
            ([], "reference.timetable_schools"),
            ({"Sample": "data/sample.yaml"}, "reference.timetable_schools.Sample"),
            ({"sample": "../sample.yaml"}, "reference.timetable_schools.sample"),
            ({"sample": "data\\sample.yaml"}, "reference.timetable_schools.sample"),
        )
        for schools, expected_path in cases:
            with self.subTest(schools=schools), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "workspace"
                root.mkdir()
                document = copy.deepcopy(BASE_DOCUMENT)
                document["reference"]["timetable_schools"] = schools
                source = root / WORKSPACE_FILENAME
                _write_doc(source, document)

                with self.assertRaises(ContractError) as caught:
                    load_workspace(source)

                self.assertEqual(caught.exception.path, expected_path)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "workspace"
            root.mkdir()
            document = copy.deepcopy(BASE_DOCUMENT)
            document["reference"]["timetable_schools"] = {"sample": "data/sample.yaml"}
            source = root / WORKSPACE_FILENAME
            _write_doc(source, document)
            workspace = load_workspace(source)
            self.assertEqual(
                workspace.timetable_schools,
                {"sample": root / "data" / "sample.yaml"},
            )
            with self.assertRaises(TypeError):
                workspace.timetable_schools["other"] = root / "other.yaml"
            with self.assertRaises(ContractError) as missing:
                workspace.require("reference.timetable_schools.unknown")
            self.assertEqual(
                missing.exception.path, "reference.timetable_schools.unknown"
            )
            with self.assertRaises(ContractError) as absent:
                workspace.require("reference.timetable_schools.sample")
            self.assertEqual(absent.exception.path, "reference.timetable_schools.sample")

    def test_timetable_write_target_path_and_registration(self) -> None:
        for bad_value in ("../outside.yaml", "data\\outside.yaml"):
            with self.subTest(bad_value=bad_value), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "workspace"
                root.mkdir()
                document = copy.deepcopy(BASE_DOCUMENT)
                document["state"]["timetable"] = bad_value
                source = root / WORKSPACE_FILENAME
                _write_doc(source, document)

                with self.assertRaises(ContractError) as caught:
                    load_workspace(source)

                self.assertEqual(caught.exception.path, "state.timetable")

        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / WORKSPACE_FILENAME
            _write_doc(source, BASE_DOCUMENT)
            with self.assertRaises(ContractError) as caught:
                load_workspace(source).write_target("state.timetable")
            self.assertEqual(caught.exception.path, "state.timetable")

    @unittest.skipUnless(os.name == "nt", "directory junctions are available on Windows")
    def test_write_target_rejects_junction_that_resolves_outside_workspace(self) -> None:
        import _winapi

        for loader in LOADERS:
            with self.subTest(loader=loader.__name__), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                root = base / "workspace"
                root.mkdir()
                outside = base / "outside"
                outside.mkdir()
                source = root / WORKSPACE_FILENAME
                doc = copy.deepcopy(BASE_DOCUMENT)
                doc["state"]["plans"] = "linked-plans"
                _write_doc(source, doc)
                try:
                    _winapi.CreateJunction(str(outside), str(root / "linked-plans"))
                except OSError as exc:
                    self.skipTest(f"directory junction unavailable on this account: {exc}")

                with self.assertRaises(ContractError) as caught:
                    loader(source).write_target("state.plans")

                self.assertEqual(caught.exception.path, "state.plans")
                self.assertIn("resolves outside the workspace", str(caught.exception))


    def test_5b_symlink_escaping_the_workspace_is_rejected(self) -> None:
        for loader in LOADERS:
            with self.subTest(loader=loader.__name__), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "workspace"
                root.mkdir()
                source = root / WORKSPACE_FILENAME
                outside = Path(temporary) / "outside.json"
                outside.write_text("outside", encoding="utf-8")
                link = root / "linked.json"
                try:
                    link.symlink_to(outside)
                except (OSError, NotImplementedError) as exc:
                    self.skipTest(f"symbolic link unavailable on this account (the junction case in test_5 still ran): {exc}")
                doc = copy.deepcopy(BASE_DOCUMENT)
                doc["reference"]["topic_weights"] = "linked.json"
                _write_doc(source, doc)
                with self.assertRaises(ContractError) as caught:
                    loader(source).require("reference.topic_weights")
                self.assertEqual(caught.exception.path, "reference.topic_weights")
                self.assertIn("outside the workspace", str(caught.exception))

    @unittest.skipUnless(os.name == "nt", "case aliases are one file only on case-insensitive Windows file systems")
    def test_5c_case_aliased_index_paths_are_one_registration(self) -> None:
        # Round-45 review M2.
        for loader in LOADERS:
            cases = [
                (
                    "same subject",
                    {"alpha": ["data/index.json", "data/INDEX.json"]},
                    "reference.exam_indexes.alpha[1]",
                ),
                (
                    "across subjects",
                    {"alpha": ["data/index.json"], "beta": ["Data/Index.JSON"]},
                    "reference.exam_indexes.beta[0]",
                ),
            ]
            for label, indexes, expected in cases:
                with self.subTest(loader=loader.__name__, case=label), tempfile.TemporaryDirectory() as temporary:
                    source = Path(temporary) / WORKSPACE_FILENAME
                    doc = copy.deepcopy(BASE_DOCUMENT)
                    doc["reference"]["exam_indexes"] = indexes
                    _write_doc(source, doc)
                    with self.assertRaises(ContractError) as caught:
                        loader(source)
                    self.assertEqual(caught.exception.path, expected)

    def test_5d_hash_and_parsed_content_come_from_the_same_read(self) -> None:
        # Round-45 review M3: the registry changing on disk right after it is read must not
        # yield paths from one version and a sha256 of another.
        for loader in LOADERS:
            with self.subTest(loader=loader.__name__), tempfile.TemporaryDirectory() as temporary:
                source = Path(temporary) / WORKSPACE_FILENAME
                first = copy.deepcopy(BASE_DOCUMENT)
                first["reference"]["topic_weights"] = "data/first.json"
                second = copy.deepcopy(BASE_DOCUMENT)
                second["reference"]["topic_weights"] = "data/second.json"
                _write_doc(source, first)
                first_bytes = source.read_bytes()
                real_read_bytes = Path.read_bytes

                def read_then_replace(path: Path) -> bytes:
                    data = real_read_bytes(path)
                    if path == source:
                        _write_doc(source, second)  # a concurrent writer lands mid-load
                    return data

                with patch.object(Path, "read_bytes", read_then_replace):
                    loaded = loader(source)
                self.assertEqual(loaded.topic_weights.name, "first.json")
                self.assertEqual(loaded.sha256, hashlib.sha256(first_bytes).hexdigest())

    def test_6_discovery_precedence_no_fallback_and_cwd_resolution(self) -> None:
        for loader in LOADERS:
            with self.subTest(loader=loader.__name__), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                root = base / "root"
                nested = root / "nested"
                nested.mkdir(parents=True)
                outer = root / WORKSPACE_FILENAME
                inner = nested / WORKSPACE_FILENAME
                _write_doc(outer, BASE_DOCUMENT)
                inner_doc = copy.deepcopy(BASE_DOCUMENT)
                inner_doc["reference"]["topic_weights"] = "inside.json"
                _write_doc(inner, inner_doc)
                explicit = base / "explicit.yaml"
                _write_doc(explicit, BASE_DOCUMENT)
                env_source = base / "env.yaml"
                _write_doc(env_source, BASE_DOCUMENT)
                cwd = base / "cwd"
                cwd.mkdir()
                with patch("pathlib.Path.cwd", return_value=cwd), patch.dict(os.environ, {WORKSPACE_ENV: str(env_source)}):
                    self.assertEqual(find_workspace(explicit=explicit), explicit.absolute())
                    self.assertEqual(loader(explicit).source, explicit.absolute())
                    self.assertEqual(find_workspace(), env_source.absolute())
                    self.assertEqual(loader().source, env_source.absolute())
                with patch("pathlib.Path.cwd", return_value=nested), patch.dict(os.environ, {}, clear=True):
                    self.assertEqual(find_workspace(), inner.absolute())
                relative_explicit = os.path.relpath(explicit, cwd)
                relative_env = os.path.relpath(env_source, cwd)
                with patch("pathlib.Path.cwd", return_value=cwd), patch.dict(os.environ, {WORKSPACE_ENV: relative_env}):
                    self.assertEqual(find_workspace(explicit=relative_explicit), explicit.absolute())
                    self.assertEqual(find_workspace(), env_source.absolute())
                with patch("pathlib.Path.cwd", return_value=cwd), patch.dict(os.environ, {}, clear=True):
                    with self.assertRaises(ContractError):
                        loader(base / "missing-explicit.yaml")
                with patch("pathlib.Path.cwd", return_value=cwd), patch.dict(os.environ, {WORKSPACE_ENV: "missing-env.yaml"}):
                    with self.assertRaises(ContractError) as caught:
                        loader()
                    self.assertIn(WORKSPACE_ENV, str(caught.exception))
                with patch("pathlib.Path.cwd", return_value=nested), patch.dict(os.environ, {WORKSPACE_ENV: ""}):
                    self.assertEqual(find_workspace(), inner.absolute())
                no_registry = base / "no-registry"
                no_registry.mkdir()
                with patch("pathlib.Path.cwd", return_value=no_registry), patch.dict(os.environ, {}, clear=True):
                    with self.assertRaises(ContractError):
                        find_workspace()

    def test_6b_error_selected_explicitly_names_its_source_once(self) -> None:
        for loader in LOADERS:
            with self.subTest(loader=loader.__name__), tempfile.TemporaryDirectory() as temporary:
                source = Path(temporary) / WORKSPACE_FILENAME
                doc = copy.deepcopy(BASE_DOCUMENT)
                doc["schema_version"] = 1
                _write_doc(source, doc)
                with self.assertRaises(ContractError) as caught:
                    loader(source)
                self.assertEqual(caught.exception.path, "schema_version")
                message = str(caught.exception)
                self.assertEqual(message.count("schema_version:"), 1, message)
                self.assertIn("selected via --workspace", message)

    def test_7_sha256_tracks_original_bytes_including_line_endings(self) -> None:
        lf = yaml.safe_dump(BASE_DOCUMENT, allow_unicode=True, sort_keys=False).encode("utf-8")
        crlf = lf.replace(b"\n", b"\r\n")
        for loader in LOADERS:
            with tempfile.TemporaryDirectory() as temporary:
                source = Path(temporary) / WORKSPACE_FILENAME
                source.write_bytes(lf)
                self.assertEqual(loader(source).sha256, hashlib.sha256(lf).hexdigest())
                source.write_bytes(crlf)
                self.assertEqual(loader(source).sha256, hashlib.sha256(crlf).hexdigest())
                self.assertNotEqual(loader(source).sha256, hashlib.sha256(lf).hexdigest())

    def test_8_loading_is_pure_read_and_mappings_are_immutable(self) -> None:
        for loader in LOADERS:
            with self.subTest(loader=loader.__name__), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source = root / WORKSPACE_FILENAME
                _write_doc(source, BASE_DOCUMENT)
                before = _path_snapshot(root)
                workspace = loader(source)
                after = _path_snapshot(root)
                self.assertEqual(before, after)
                self.assertFalse((root / "state").exists())
                self.assertFalse((root / "staging").exists())
                with self.assertRaises(TypeError):
                    workspace.knowledge_trees["unknown"] = root / "tree.yaml"
                with self.assertRaises(TypeError):
                    workspace.subject_profiles["unknown"] = workspace.subject_profiles["alpha"]
                with self.assertRaises(TypeError):
                    workspace.exam_indexes["alpha"] = ()
                with self.assertRaises(TypeError):
                    workspace.supplementary["alpha_supplement"].files["tree"] = root / "other.yaml"
                with self.assertRaises(TypeError):
                    workspace.products["new"] = root / "other"

    def test_local_overlay_absence_matches_main_registry_and_has_no_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / WORKSPACE_FILENAME
            _write_doc(source, BASE_DOCUMENT)
            without_overlay = load_workspace(source)
            self.assertIsNone(without_overlay.local_sha256)

            local_path = root / "kaoyan.workspace.local.yaml"
            self.assertFalse(local_path.exists())
            same_registry = load_workspace(source)
            for field in fields(without_overlay):
                self.assertEqual(
                    getattr(without_overlay, field.name),
                    getattr(same_registry, field.name),
                    field.name,
                )

    def test_local_overlay_registers_each_allowed_key(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / WORKSPACE_FILENAME
            _write_doc(source, BASE_DOCUMENT)
            local = {
                "schema_version": 1,
                "reference": {"timetable_schools": {"sample": "personal/school.yaml"}},
                "settings": {"exam_config": "personal/config.yaml"},
                "state": {
                    "availability": "personal/availability.yaml",
                    "timetable": "personal/timetable.yaml",
                    "question_bank": "data/personal/question_bank",
                },
            }
            overlay_path = _write_local_doc(root, local)
            for relative in (
                "personal/school.yaml",
                "personal/config.yaml",
                "personal/availability.yaml",
            ):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture", encoding="utf-8")
            workspace = load_workspace(source)

            self.assertEqual(
                workspace.timetable_schools,
                {"sample": root / "personal" / "school.yaml"},
            )
            self.assertEqual(
                workspace.require("settings.exam_config"),
                root / "personal" / "config.yaml",
            )
            self.assertEqual(
                workspace.availability, root / "personal" / "availability.yaml"
            )
            self.assertEqual(
                workspace.write_target("state.timetable"),
                root / "personal" / "timetable.yaml",
            )
            self.assertEqual(
                workspace.write_target("state.question_bank"),
                root / "data" / "personal" / "question_bank",
            )
            with self.assertRaises(ContractError) as caught:
                workspace.require("state.question_bank")
            self.assertEqual(caught.exception.path, "state.question_bank")
            self.assertEqual(
                workspace.local_sha256,
                hashlib.sha256(overlay_path.read_bytes()).hexdigest(),
            )

    def test_local_overlay_rejects_each_registered_duplicate(self) -> None:
        duplicates = (
            ({"reference": {"timetable_schools": {"sample": "personal/school.yaml"}}},
             "local.reference.timetable_schools"),
            ({"settings": {"exam_config": "personal/config.yaml"}},
             "local.settings.exam_config"),
            ({"state": {"availability": "personal/availability.yaml"}},
             "local.state.availability"),
            ({"state": {"timetable": "personal/timetable.yaml"}},
             "local.state.timetable"),
        )
        for addition, expected in duplicates:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source = root / WORKSPACE_FILENAME
                main = copy.deepcopy(BASE_DOCUMENT)
                if "reference" in addition:
                    main["reference"]["timetable_schools"] = {"main": "data/main.yaml"}
                elif "settings" in addition:
                    main["settings"]["exam_config"] = "data/config.yaml"
                else:
                    key = next(iter(addition["state"]))
                    main["state"][key] = "data/main.yaml"
                _write_doc(source, main)
                local = {"schema_version": 1, **addition}
                _write_local_doc(root, local)

                with self.assertRaises(ContractError) as caught:
                    load_workspace(source)

                self.assertEqual(caught.exception.path, expected)

    def test_local_overlay_rejects_unknown_schema_paths_and_invalid_yaml(self) -> None:
        cases = (
            ("schema_version: 2\n", "local.schema_version"),
            ("schema_version: 1\nunknown: value\n", "local.unknown"),
            ("schema_version: 1\nstate:\n  unknown: value\n", "local.state.unknown"),
            ("schema_version: 1\nstate:\n  timetable: ../private.yaml\n",
             "local.state.timetable"),
            ("schema_version: [\n", "local"),
            ("schema_version: 1\nvalue: !unsupported payload\n", "local"),
        )
        for rendered, expected in cases:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source = root / WORKSPACE_FILENAME
                _write_doc(source, BASE_DOCUMENT)
                (root / "kaoyan.workspace.local.yaml").write_text(
                    rendered, encoding="utf-8"
                )

                with self.assertRaises(ContractError) as caught:
                    load_workspace(source)

                self.assertEqual(caught.exception.path, expected)

    def test_explicit_workspace_uses_its_own_local_overlay(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            selected = root / "selected"
            elsewhere = root / "elsewhere"
            selected.mkdir()
            elsewhere.mkdir()
            selected_registry = selected / WORKSPACE_FILENAME
            elsewhere_registry = elsewhere / WORKSPACE_FILENAME
            _write_doc(selected_registry, BASE_DOCUMENT)
            _write_doc(elsewhere_registry, BASE_DOCUMENT)
            selected_local = _write_local_doc(selected, {
                "schema_version": 1,
                "state": {"timetable": "personal/selected.yaml"},
            })
            _write_local_doc(elsewhere, {
                "schema_version": 1,
                "state": {"timetable": "personal/elsewhere.yaml"},
            })

            workspace = load_workspace(selected_registry)

            self.assertEqual(workspace.timetable, selected / "personal" / "selected.yaml")
            self.assertEqual(
                workspace.local_sha256,
                hashlib.sha256(selected_local.read_bytes()).hexdigest(),
            )


if __name__ == "__main__":
    unittest.main()
