"""Workspace port contract for the projection consumer."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from contextlib import closing
from datetime import date
from pathlib import Path
from unittest.mock import patch

import yaml

from ky.knowledge import load_knowledge_points
from ky.models import ContractError, load_config
from ky.projection import build_projection
from ky.schedule.state_snapshot import build_snapshot
from ky.workspace import load_workspace

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY = REPO_ROOT / "kaoyan.workspace.yaml"
CONFIG = REPO_ROOT / "tests/fixtures/config/config-minimal.yaml"
# Last commit whose builder is schema 4; pinned, never HEAD.
SCHEMA4_COMMIT = "f2b3669"
CUSTOM_SOURCE = "probe"


def _clone_workspace(directory: Path) -> Path:
    """Copy registered projection sources under new relative paths and emit a temp registry."""
    source = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    root = directory / "clone"
    root.mkdir()
    # Trees move to new paths; version registration (WP-H4a) is not what this port tests.
    source["reference"].pop("syllabus_versions", None)
    for subject, path in list(source["reference"]["knowledge_trees"].items()):
        rel = f"copied/trees/{subject}.yaml"
        destination = root / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REGISTRY.parent / path, destination)
        source["reference"]["knowledge_trees"][subject] = rel
    for subject, paths in list(source["reference"]["exam_indexes"].items()):
        updated = []
        for index, path in enumerate(paths):
            rel = f"copied/indexes/{subject}-{index}.json"
            destination = root / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REGISTRY.parent / path, destination)
            updated.append(rel)
        source["reference"]["exam_indexes"][subject] = updated
    for name, view in source.get("supplementary", {}).items():
        for role, path in list(view["files"].items()):
            rel = f"copied/supplementary/{name}-{role}.yaml"
            destination = root / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REGISTRY.parent / path, destination)
            view["files"][role] = rel
    for key, rel in (("topic_weights", "copied/weights/topic_weights.json"),
                     ("vocabulary_db", "copied/vocab/vocabulary.sqlite")):
        destination = root / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REGISTRY.parent / source["reference"][key], destination)
        source["reference"][key] = rel
    source["projection"] = "out/projection.sqlite"
    registry = root / "kaoyan.workspace.yaml"
    rendered = yaml.safe_dump(source, allow_unicode=True, sort_keys=False)
    registry.write_text(rendered, encoding="utf-8", newline="\n")
    return registry


def _meta(con: sqlite3.Connection, key: str) -> str:
    return con.execute("SELECT value FROM projection_meta WHERE key=?", (key,)).fetchone()[0]


def _add_missing_prefix_nodes(tree_path: Path) -> None:
    tree = yaml.safe_load(tree_path.read_text(encoding="utf-8"))
    chapter = deepcopy(next(node for node in tree if node["scope"] == "chapter"))
    item = deepcopy(next(node for node in tree if node["scope"] == "item"))
    chapter["knowledge_point_id"] = "cs408.probe.chapter-99"
    chapter["title"] = "Hierarchy contract probe chapter"
    item["knowledge_point_id"] = (
        "cs408.probe.chapter-99.section-01.item-01"
    )
    item["title"] = "Hierarchy contract probe item"
    tree.extend((chapter, item))
    tree_path.write_text(
        yaml.safe_dump(tree, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
        newline="\n",
    )


def _add_missing_prefix_agreement(agreement_path: Path) -> None:
    agreement = yaml.safe_load(agreement_path.read_text(encoding="utf-8"))
    chapter = deepcopy(next(
        node for node in agreement["items"]
        if node["knowledge_point_id"].endswith("chapter-01")
    ))
    item = deepcopy(agreement["items"][0])
    chapter["knowledge_point_id"] = "cs408.probe.chapter-99"
    item["knowledge_point_id"] = (
        "cs408.probe.chapter-99.section-01.item-01"
    )
    agreement["items"].extend((chapter, item))
    agreement_path.write_text(
        yaml.safe_dump(agreement, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
        newline="\n",
    )


class ProjectionPortContractTest(unittest.TestCase):
    def test_projection_parent_uses_port_across_missing_intermediate_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            registry = _clone_workspace(Path(td))
            document = yaml.safe_load(registry.read_text(encoding="utf-8"))
            effective_path = registry.parent / document["reference"]["knowledge_trees"]["cs408"]
            _add_missing_prefix_nodes(effective_path)
            view = next(
                view for view in document["supplementary"].values()
                if view["subject"] == "cs408" and view["kind"] == "cross_year_tree"
            )
            tree_path = registry.parent / view["files"]["tree"]
            agreement_path = registry.parent / view["files"]["agreement"]
            _add_missing_prefix_nodes(tree_path)
            _add_missing_prefix_agreement(agreement_path)
            workspace = load_workspace(registry)
            output = Path(td) / "projection.sqlite"
            build_projection(workspace, output)

            point_id = "cs408.probe.chapter-99.section-01.item-01"
            expected_parent = "cs408.probe.chapter-99"
            with closing(sqlite3.connect(output)) as connection:
                effective_parent = connection.execute(
                    "SELECT parent_id FROM knowledge_points WHERE knowledge_point_id=?",
                    (point_id,),
                ).fetchone()[0]
                supplementary_parent = connection.execute(
                    "SELECT parent_id FROM supplementary_knowledge_points "
                    "WHERE knowledge_point_id=?",
                    (point_id,),
                ).fetchone()[0]
            self.assertEqual(effective_parent, expected_parent)
            self.assertEqual(supplementary_parent, expected_parent)

    def test_projection_cli_uses_explicit_workspace_and_out(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            registry = _clone_workspace(Path(td))
            out = Path(td) / "cli.sqlite"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ky.projection",
                    "--workspace",
                    str(registry),
                    "--out",
                    str(out),
                ],
                cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(out.is_file())

    def test_projection_cli_bad_explicit_workspace_does_not_fall_back(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "must-not-exist.sqlite"
            missing_registry = Path(td) / "missing.yaml"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ky.projection",
                    "--workspace",
                    str(missing_registry),
                    "--out",
                    str(out),
                ],
                cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", check=False,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("contract violation:", result.stderr)
            self.assertFalse(out.exists())

    def test_repository_effective_and_supplementary_separation(self) -> None:
        ws = load_workspace(REGISTRY)
        view = next(
            item for item in ws.supplementary.values()
            if item.kind == "cross_year_tree"
        )
        subject = view.subject
        effective_ids = {
            node.knowledge_point_id
            for node in load_knowledge_points(
                ws.require(f"reference.knowledge_trees.{subject}")
            )
        }
        supplementary_ids = {
            node.knowledge_point_id
            for node in load_knowledge_points(view.files["tree"])
        }
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "projection.sqlite"
            build_projection(ws, out)
            with closing(sqlite3.connect(out)) as con:
                effective = con.execute(
                    "SELECT COUNT(*) FROM knowledge_points WHERE subject_id=?",
                    (subject,),
                ).fetchone()[0]
                self.assertEqual(effective, len(effective_ids))
                supplement_count = con.execute(
                    "SELECT COUNT(*) FROM supplementary_knowledge_points "
                    "WHERE subject_id=?",
                    (subject,),
                ).fetchone()[0]
                self.assertEqual(supplement_count, len(supplementary_ids))
                effective_supplement_count = con.execute(
                    "SELECT COUNT(*) FROM supplementary_knowledge_points "
                    "WHERE subject_id=? AND is_effective=1",
                    (subject,),
                ).fetchone()[0]
                self.assertEqual(
                    effective_supplement_count,
                    len(effective_ids & supplementary_ids),
                )
                legacy_ids = supplementary_ids - effective_ids
                projected_legacy_ids = {
                    row[0] for row in con.execute(
                        "SELECT knowledge_point_id FROM supplementary_knowledge_points "
                        "WHERE view_name=? AND is_effective=0",
                        (view.name,),
                    )
                }
                self.assertEqual(projected_legacy_ids, legacy_ids)
                columns = {
                    row[1]
                    for row in con.execute("PRAGMA table_info(knowledge_points)")
                }
                self.assertTrue(
                    {"source_support", "source_count", "evidence_tag"}.isdisjoint(columns)
                )
                sources = dict(con.execute(
                    "SELECT subject_id, tree_source FROM knowledge_points "
                    "GROUP BY subject_id, tree_source"
                ))
                self.assertEqual(
                    sources,
                    {
                        subject: f"reference.knowledge_trees.{subject}"
                        for subject in ws.knowledge_trees
                    },
                )

    def test_snapshot_counts_match_effective_projection_counts(self) -> None:
        ws = load_workspace(REGISTRY)
        config = load_config(CONFIG)
        snapshot = build_snapshot(config, (), today=date(2026, 9, 25), workspace=ws)
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "projection.sqlite"
            build_projection(ws, out)
            with closing(sqlite3.connect(out)) as con:
                for subject in snapshot.subjects:
                    projected = con.execute(
                        "SELECT COUNT(*) FROM knowledge_points WHERE subject_id=?",
                        (subject.subject_id,),
                    ).fetchone()[0]
                    snapshot_count = subject.tree_total.count if subject.tree_total else None
                    projected_count = (
                        projected if subject.subject_id in ws.knowledge_trees else None
                    )
                    self.assertEqual(snapshot_count, projected_count)

    def test_replacement_uses_new_registered_relative_paths_and_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            registry = _clone_workspace(root)
            doc = yaml.safe_load(registry.read_text(encoding="utf-8"))
            subject = next(iter(doc["reference"]["knowledge_trees"]))
            old_tree = doc["reference"]["knowledge_trees"][subject]
            new_tree = f"replacement/syllabus/{subject}-effective.yaml"
            (registry.parent / new_tree).parent.mkdir(parents=True)
            shutil.copyfile(registry.parent / old_tree, registry.parent / new_tree)
            tree_doc = yaml.safe_load((registry.parent / new_tree).read_text(encoding="utf-8"))
            tree_items = tree_doc["items"] if isinstance(tree_doc, dict) else tree_doc
            changed_point_id = tree_items[0]["knowledge_point_id"]
            tree_items[0]["title"] = "replacement title marker"
            (registry.parent / new_tree).write_text(
                yaml.safe_dump(tree_doc, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
                newline="\n",
            )
            doc["reference"]["knowledge_trees"][subject] = new_tree
            paths = doc["reference"]["exam_indexes"][subject]
            old_index = paths[0]
            new_index = f"replacement/indexes/{subject}-index.json"
            (registry.parent / new_index).parent.mkdir(parents=True)
            shutil.copyfile(registry.parent / old_index, registry.parent / new_index)
            paths[0] = new_index
            old_weights = doc["reference"]["topic_weights"]
            new_weights = "replacement/weights/weights.json"
            (registry.parent / new_weights).parent.mkdir(parents=True)
            shutil.copyfile(registry.parent / old_weights, registry.parent / new_weights)
            doc["reference"]["topic_weights"] = new_weights
            old_vocab = doc["reference"]["vocabulary_db"]
            new_vocab = "replacement/vocab/eng.sqlite"
            (registry.parent / new_vocab).parent.mkdir(parents=True)
            shutil.copyfile(registry.parent / old_vocab, registry.parent / new_vocab)
            doc["reference"]["vocabulary_db"] = new_vocab
            rendered = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)
            registry.write_text(rendered, encoding="utf-8", newline="\n")
            ws = load_workspace(registry)
            out = root / "projection.sqlite"
            build_projection(ws, out)
            with closing(sqlite3.connect(out)) as con:
                ids = {
                    row[0]
                    for row in con.execute(
                        "SELECT knowledge_point_id FROM knowledge_points "
                "WHERE subject_id=?",
                (subject,),
                    )
                }
                inputs = json.loads(_meta(con, "inputs"))
                registered_tree = ws.require(f"reference.knowledge_trees.{subject}")
                self.assertEqual(len(ids), len(load_knowledge_points(registered_tree)))
                self.assertEqual(
                    con.execute(
                        "SELECT title FROM knowledge_points WHERE knowledge_point_id=?",
                        (changed_point_id,),
                    ).fetchone()[0],
                    "replacement title marker",
                )
                for moved in (new_tree, new_index, new_weights, new_vocab):
                    self.assertIn(moved, inputs)
                    digest = hashlib.sha256((ws.root / moved).read_bytes()).hexdigest()
                    self.assertEqual(inputs[moved], digest)

    def test_hash_and_projection_content_use_the_same_read_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            registry = _clone_workspace(Path(td))
            ws = load_workspace(registry)
            subject = next(iter(ws.knowledge_trees))
            tree = ws.require(f"reference.knowledge_trees.{subject}")
            original_content = tree.read_bytes()
            original_doc = yaml.safe_load(original_content.decode("utf-8"))
            original_items = (
                original_doc["items"]
                if isinstance(original_doc, dict)
                else original_doc
            )
            first_id = original_items[0]["knowledge_point_id"]
            original_title = original_items[0]["title"]
            changed_doc = yaml.safe_load(original_content.decode("utf-8"))
            changed_items = changed_doc["items"] if isinstance(changed_doc, dict) else changed_doc
            changed_items[0]["title"] = "written after first read"
            changed_content = yaml.safe_dump(
                changed_doc,
                allow_unicode=True,
                sort_keys=False,
            ).encode("utf-8")
            read_bytes = Path.read_bytes
            changed = False

            def read_then_change(path: Path) -> bytes:
                nonlocal changed
                content = read_bytes(path)
                if path == tree and not changed:
                    path.write_bytes(changed_content)
                    changed = True
                return content

            out = Path(td) / "same-read.sqlite"
            with patch.object(Path, "read_bytes", read_then_change):
                build_projection(ws, out)
            with closing(sqlite3.connect(out)) as con:
                title = con.execute(
                    "SELECT title FROM knowledge_points WHERE knowledge_point_id=?",
                    (first_id,),
                ).fetchone()[0]
                recorded = json.loads(_meta(con, "inputs"))
            rel = tree.relative_to(ws.root).as_posix()
            self.assertEqual(title, original_title)
            self.assertEqual(recorded[rel], hashlib.sha256(original_content).hexdigest())
            self.assertNotEqual(recorded[rel], hashlib.sha256(changed_content).hexdigest())

    def test_malformed_locator_is_a_contract_error_and_cli_exit_two(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            registry = _clone_workspace(Path(td))
            ws = load_workspace(registry)
            subject = next(iter(ws.exam_indexes))
            index = ws.require_all(f"reference.exam_indexes.{subject}")[0]
            original_document = json.loads(index.read_text(encoding="utf-8"))
            document = json.loads(json.dumps(original_document))
            document["entries"][0]["locator"] = [1]
            index.write_text(json.dumps(document), encoding="utf-8", newline="\n")
            with self.assertRaises(ContractError) as caught:
                build_projection(ws, Path(td) / "bad.sqlite")
            self.assertIn(
                f"reference.exam_indexes.{subject}.entries[0].locator",
                caught.exception.path,
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ky.projection",
                    "--workspace",
                    str(registry),
                    "--out",
                    str(Path(td) / "cli-bad.sqlite"),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("contract violation:", result.stderr)

            invalid_fields = (
                ("exam_year", "bad", "exam_year"),
                ("marks", [], "marks"),
            )
            for name, value, path_part in invalid_fields:
                with self.subTest(field=name):
                    bad_document = json.loads(json.dumps(original_document))
                    bad_document["entries"][0][name] = value
                    index.write_text(
                        json.dumps(bad_document),
                        encoding="utf-8",
                        newline="\n",
                    )
                    with self.assertRaises(ContractError) as field_error:
                        build_projection(ws, Path(td) / f"bad-{name}.sqlite")
                    self.assertIn(path_part, field_error.exception.path)

    def test_supplementary_node_must_match_registered_view_subject(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            registry = _clone_workspace(Path(td))
            ws = load_workspace(registry)
            view = next(
                item for item in ws.supplementary.values()
                if item.kind == "cross_year_tree"
            )
            tree_doc = yaml.safe_load(view.files["tree"].read_text(encoding="utf-8"))
            tree_items = tree_doc["items"] if isinstance(tree_doc, dict) else tree_doc
            extra = dict(tree_items[0])
            extra_id = "outside.synthetic.extra"
            extra["knowledge_point_id"] = extra_id
            tree_items.append(extra)
            view.files["tree"].write_text(
                yaml.safe_dump(tree_doc, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
                newline="\n",
            )
            agreement_doc = yaml.safe_load(
                view.files["agreement"].read_text(encoding="utf-8")
            )
            agreement_item = dict(agreement_doc["items"][0])
            agreement_item["knowledge_point_id"] = extra_id
            agreement_doc["items"].append(agreement_item)
            view.files["agreement"].write_text(
                yaml.safe_dump(agreement_doc, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
                newline="\n",
            )
            with self.assertRaises(ContractError) as caught:
                build_projection(ws, Path(td) / "wrong-subject.sqlite")
            self.assertIn(
                f"supplementary.{view.name}.files.tree",
                caught.exception.path,
            )

    def test_missing_registered_index_preserves_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            registry = _clone_workspace(Path(td))
            ws = load_workspace(registry)
            out = Path(td) / "prior.sqlite"
            original = b"pre-existing projection bytes"
            out.write_bytes(original)
            next(iter(ws.exam_indexes.values()))[0].unlink()
            with self.assertRaises(ContractError):
                build_projection(ws, out)
            self.assertEqual(out.read_bytes(), original)

    def _assert_invalid_supplement(self, mutation) -> None:
        with tempfile.TemporaryDirectory() as td:
            registry = _clone_workspace(Path(td))
            ws = load_workspace(registry)
            view = next(
                item for item in ws.supplementary.values()
                if item.kind == "cross_year_tree"
            )
            agreement = view.files["agreement"]
            tree = view.files["tree"]
            if mutation == "agreement_missing":
                doc = yaml.safe_load(agreement.read_text(encoding="utf-8"))
                doc["items"].pop()
                agreement.write_text(
                    yaml.safe_dump(doc, allow_unicode=True, sort_keys=False),
                    encoding="utf-8",
                )
            elif mutation == "agreement_extra":
                doc = yaml.safe_load(agreement.read_text(encoding="utf-8"))
                extra = dict(doc["items"][0])
                extra["knowledge_point_id"] = f"{view.subject}.synthetic.extra"
                doc["items"].append(extra)
                agreement.write_text(
                    yaml.safe_dump(doc, allow_unicode=True, sort_keys=False),
                    encoding="utf-8",
                )
            else:
                doc = yaml.safe_load(tree.read_text(encoding="utf-8"))
                entries = doc["items"] if isinstance(doc, dict) else doc
                registered_tree = ws.require(
                    f"reference.knowledge_trees.{view.subject}"
                )
                effective_id = next(iter(load_knowledge_points(registered_tree)))
                entries[:] = [
                    entry
                    for entry in entries
                    if entry["knowledge_point_id"] != effective_id.knowledge_point_id
                ]
                tree.write_text(
                    yaml.safe_dump(doc, allow_unicode=True, sort_keys=False),
                    encoding="utf-8",
                )
            with self.assertRaises(ContractError):
                build_projection(ws, Path(td) / "out.sqlite")

    def test_agreement_missing_row_is_rejected(self) -> None:
        self._assert_invalid_supplement("agreement_missing")

    def test_agreement_extra_row_is_rejected(self) -> None:
        self._assert_invalid_supplement("agreement_extra")

    def test_effective_id_missing_from_supplement_is_rejected(self) -> None:
        self._assert_invalid_supplement("effective_missing")

    def test_projection_content_and_inputs_are_deterministic_and_exact(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            registry = _clone_workspace(Path(td))
            ws = load_workspace(registry)
            first, second = Path(td) / "first.sqlite", Path(td) / "second.sqlite"
            build_projection(ws, first)
            build_projection(ws, second)
            with closing(sqlite3.connect(first)) as left, closing(sqlite3.connect(second)) as right:
                self.assertEqual(_meta(left, "inputs"), _meta(right, "inputs"))
                left_meta = left.execute(
                    "SELECT * FROM projection_meta ORDER BY key"
                ).fetchall()
                right_meta = right.execute(
                    "SELECT * FROM projection_meta ORDER BY key"
                ).fetchall()
                self.assertEqual(left_meta, right_meta)
                recorded = json.loads(_meta(left, "inputs"))
                registered_paths = list(ws.knowledge_trees.values())
                registered_paths.extend(
                    path for group in ws.exam_indexes.values() for path in group
                )
                registered_paths.extend((ws.topic_weights, ws.vocabulary_db))
                registered_paths.extend(
                    path
                    for view in ws.supplementary.values()
                    for path in view.files.values()
                )
                expected = {
                    path.relative_to(ws.root).as_posix() for path in registered_paths
                }
                self.assertEqual(set(recorded), expected)
                self.assertEqual(_meta(left, "workspace_registry_sha256"), ws.sha256)


def _register_custom_source_index(registry: Path) -> tuple[str, dict]:
    """Register a copy of the first index under ``CUSTOM_SOURCE`` (contracts/exam_index.md §1)."""
    doc = yaml.safe_load(registry.read_text(encoding="utf-8"))
    subject, paths = next(iter(doc["reference"]["exam_indexes"].items()))
    index = json.loads((registry.parent / paths[0]).read_text(encoding="utf-8"))
    index["paper_source"] = CUSTOM_SOURCE
    for entry in index["entries"]:
        entry["question_id"] = (
            f"{subject}-{CUSTOM_SOURCE}-{index['exam_year']}-{entry['number']:02d}"
        )
    rel = f"copied/indexes/{subject}-{CUSTOM_SOURCE}.json"
    (registry.parent / rel).write_text(json.dumps(index), encoding="utf-8", newline="\n")
    paths.append(rel)
    rendered = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)
    registry.write_text(rendered, encoding="utf-8", newline="\n")
    return rel, index


def _load_schema4_builder(directory: Path):
    """Import schema 4 code and source port from a fixed commit, never from HEAD."""
    sources = {}
    for relative in ("ky/projection/__init__.py", "ky/projection/learning_state.py"):
        shown = subprocess.run(
            ["git", "show", f"{SCHEMA4_COMMIT}:{relative}"],
            cwd=REPO_ROOT, capture_output=True, check=False,
        )
        if shown.returncode != 0:
            raise AssertionError(shown.stderr.decode("utf-8", errors="replace"))
        sources[relative] = shown.stdout

    source_name = "ky.projection.learning_state"
    source_path = directory / "learning_state_schema4.py"
    source_path.write_bytes(sources["ky/projection/learning_state.py"])
    source_spec = importlib.util.spec_from_file_location(source_name, source_path)
    source_module = importlib.util.module_from_spec(source_spec)
    previous_source = sys.modules.get(source_name)
    sys.modules[source_name] = source_module
    try:
        source_spec.loader.exec_module(source_module)
        builder_path = directory / "projection_schema4.py"
        builder_path.write_bytes(sources["ky/projection/__init__.py"])
        builder_spec = importlib.util.spec_from_file_location(
            "projection_schema4_baseline", builder_path
        )
        builder = importlib.util.module_from_spec(builder_spec)
        sys.modules[builder_spec.name] = builder
        try:
            builder_spec.loader.exec_module(builder)
        finally:
            sys.modules.pop(builder_spec.name, None)
        return builder
    finally:
        if previous_source is None:
            sys.modules.pop(source_name, None)
        else:
            sys.modules[source_name] = previous_source


def _columns(con: sqlite3.Connection, table: str) -> list[tuple]:
    return con.execute(f"PRAGMA table_info({table})").fetchall()


def _sorted_rows(con: sqlite3.Connection, name: str, columns: list[str]) -> list[tuple]:
    selected = ", ".join(columns)
    order = ", ".join(str(position) for position in range(1, len(columns) + 1))
    return con.execute(f"SELECT {selected} FROM {name} ORDER BY {order}").fetchall()


class ProjectionPaperSourceTest(unittest.TestCase):
    """Schema 4's paper source contract remains covered after the schema 5 bump."""

    def test_paper_source_column_records_default_and_custom_sources(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            registry = _clone_workspace(Path(td))
            _, custom = _register_custom_source_index(registry)
            ws = load_workspace(registry)
            expected = {}
            for group in ws.exam_indexes.values():
                for path in group:
                    document = json.loads(path.read_text(encoding="utf-8"))
                    source = document.get("paper_source", "national")
                    expected.update(
                        (entry["question_id"], source) for entry in document["entries"]
                    )
            out = Path(td) / "projection.sqlite"
            build_projection(ws, out)
            with closing(sqlite3.connect(out)) as con:
                projected = dict(con.execute(
                    "SELECT question_id, paper_source FROM exam_questions"
                ))
                column = next(
                    row for row in _columns(con, "exam_questions") if row[1] == "paper_source"
                )
        self.assertEqual(projected, expected)
        custom_ids = {entry["question_id"] for entry in custom["entries"]}
        self.assertEqual(
            {question_id for question_id, source in projected.items()
             if source == CUSTOM_SOURCE},
            custom_ids,
        )
        self.assertIn("national", set(projected.values()))
        self.assertEqual((column[2], column[3]), ("TEXT", 1))

    def test_duplicate_question_id_names_both_files_and_keeps_projection(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            registry = _clone_workspace(Path(td))
            out = Path(td) / "projection.sqlite"
            build_projection(load_workspace(registry), out)
            original = out.read_bytes()
            doc = yaml.safe_load(registry.read_text(encoding="utf-8"))
            subject, paths = next(iter(doc["reference"]["exam_indexes"].items()))
            first = paths[0]
            second = f"copied/indexes/{subject}-duplicate.json"
            shutil.copyfile(registry.parent / first, registry.parent / second)
            paths.append(second)
            rendered = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)
            registry.write_text(rendered, encoding="utf-8", newline="\n")
            index = json.loads((registry.parent / first).read_text(encoding="utf-8"))
            colliding = index["entries"][0]["question_id"]
            with self.assertRaises(ContractError) as caught:
                build_projection(load_workspace(registry), out)
            message = str(caught.exception)
            self.assertIn(first, message)
            self.assertIn(second, message)
            self.assertIn(colliding, message)
            self.assertEqual(
                caught.exception.path,
                f"reference.exam_indexes.{subject}.entries[0].question_id",
            )
            self.assertEqual(out.read_bytes(), original)

    def test_schema5_adds_only_the_three_fsrs_columns_to_pinned_schema4(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            baseline = _load_schema4_builder(Path(td))
            self.assertEqual(baseline.PROJECTION_SCHEMA_VERSION, 4)
            registry = _clone_workspace(Path(td))
            _register_custom_source_index(registry)
            ws = load_workspace(registry)
            old_db, new_db = Path(td) / "schema4.sqlite", Path(td) / "schema5.sqlite"
            baseline.build_projection(ws, old_db)
            build_projection(ws, new_db)
            with closing(sqlite3.connect(old_db)) as old, closing(sqlite3.connect(new_db)) as new:
                self._assert_same_except_fsrs_columns(old, new)

    def _assert_same_except_fsrs_columns(
        self,
        old: sqlite3.Connection,
        new: sqlite3.Connection,
    ) -> None:
        schema = "SELECT type, name, sql FROM sqlite_master ORDER BY type, name"
        old_schema, new_schema = old.execute(schema).fetchall(), new.execute(schema).fetchall()
        self.assertEqual(
            [row for row in old_schema if row[1] not in {"exam_questions", "review_items"}],
            [row for row in new_schema if row[1] not in {"exam_questions", "review_items"}],
        )
        old_columns = _columns(old, "exam_questions")
        new_columns = _columns(new, "exam_questions")
        self.assertEqual(new_columns, old_columns)
        old_review = _columns(old, "review_items")
        new_review = _columns(new, "review_items")
        self.assertEqual(new_review[:17], old_review[:17])
        self.assertEqual(
            [row[1:4] for row in new_review[17:20]],
            [("stability", "REAL", 0), ("difficulty", "REAL", 0),
             ("fsrs_reviewed_on", "TEXT", 0)],
        )
        self.assertEqual(
            [row[1:] for row in new_review[20:]],
            [row[1:] for row in old_review[17:]],
        )
        self.assertTrue(old.execute("SELECT COUNT(*) FROM exam_questions").fetchone()[0])
        for kind, name, _ in old_schema:
            if kind not in ("table", "view") or name == "projection_meta":
                continue
            columns = [row[1] for row in _columns(old, name)]
            with self.subTest(name=name):
                self.assertEqual(
                    _sorted_rows(old, name, columns),
                    _sorted_rows(new, name, columns),
                )
        old_meta = dict(old.execute("SELECT key, value FROM projection_meta"))
        new_meta = dict(new.execute("SELECT key, value FROM projection_meta"))
        self.assertEqual(old_meta.pop("projection_schema_version"), "4")
        self.assertEqual(new_meta.pop("projection_schema_version"), "5")
        self.assertEqual(old_meta, new_meta)


if __name__ == "__main__":
    unittest.main()
