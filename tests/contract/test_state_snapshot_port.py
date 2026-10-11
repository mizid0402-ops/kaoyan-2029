from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path
from unittest.mock import patch

import yaml

from ky.models import ContractError, load_config
from ky.knowledge import load_knowledge_points
from ky.schedule.completion import CompletionEvent, VocabProgress
from ky.schedule.state_snapshot import build_snapshot
from ky.schedule.vocab_channel import remaining_pool
from ky.storage.day_plan_store import DayPlanStore
from ky.workspace import WORKSPACE_ENV, WORKSPACE_FILENAME, load_workspace

REPO_ROOT = Path(__file__).resolve().parents[2]
TODAY = date(2026, 9, 25)
CONFIG_PATH = REPO_ROOT / "tests/fixtures/config/config-minimal.yaml"
ITEMS_PATH = REPO_ROOT / "tests/fixtures/reviews/reviews-normal.yaml"
REPOSITORY_WORKSPACE = load_workspace(REPO_ROOT / WORKSPACE_FILENAME)
SUPPLEMENTARY_VIEW = next(
    view for view in REPOSITORY_WORKSPACE.supplementary.values()
    if view.kind == "cross_year_tree"
)
TREE_SUBJECT = SUPPLEMENTARY_VIEW.subject
EFFECTIVE_TREE = REPOSITORY_WORKSPACE.require(
    f"reference.knowledge_trees.{TREE_SUBJECT}"
)
SUPPLEMENTARY_TREE = REPOSITORY_WORKSPACE.require(
    f"supplementary.{SUPPLEMENTARY_VIEW.name}.files.tree"
)


def _tree_count(path: Path) -> int:
    return len(load_knowledge_points(path))


def _registry_doc() -> dict:
    doc = yaml.safe_load((REPO_ROOT / WORKSPACE_FILENAME).read_text(encoding="utf-8"))
    doc["reference"]["knowledge_trees"] = {}
    doc["reference"].pop("syllabus_versions", None)
    doc["reference"]["vocabulary_db"] = "data/missing-vocabulary.sqlite"
    return doc


def _write_registry(root: Path, doc: dict) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    source = root / WORKSPACE_FILENAME
    source.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return source


def _copy_tree(source: Path, root: Path, relative: str) -> str:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return relative


def _snapshot(workspace_path: Path, *, tree_paths=None, vocab_db: Path | None = None):
    config = load_config(CONFIG_PATH)
    return build_snapshot(
        config,
        (),
        today=TODAY,
        tree_paths=tree_paths,
        vocab_db=vocab_db,
        workspace=load_workspace(workspace_path),
    )


class StateSnapshotWorkspacePortTests(unittest.TestCase):
    def test_vocabulary_delivery_count_comes_from_completion_events(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            db = root / "vocabulary.sqlite"
            shutil.copyfile(REPOSITORY_WORKSPACE.require("reference.vocabulary_db"), db)
            plans = root / "state" / "plans"
            store = DayPlanStore(plans)
            words = ("abate", "abdicate")
            store.write_completion_event(CompletionEvent(
                day=TODAY,
                vocab=VocabProgress(delivered_words=words),
            ))
            workspace = replace(REPOSITORY_WORKSPACE, plans=plans)
            snapshot = build_snapshot(
                load_config(CONFIG_PATH), (), today=TODAY, vocab_db=db, workspace=workspace
            )
            self.assertEqual(snapshot.vocab.delivered, len(words))
            self.assertEqual(snapshot.vocab.remaining, remaining_pool(db, delivered=set(words)))

    def test_replacement_exercise_reads_a_tree_at_its_new_relative_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "workspace"
            doc = _registry_doc()
            doc["reference"]["knowledge_trees"][TREE_SUBJECT] = _copy_tree(
                EFFECTIVE_TREE, root,
                f"relocated/trees/{TREE_SUBJECT}.yaml",
            )
            source = _write_registry(root, doc)
            override_vocab = root / "explicit-missing-vocab.sqlite"

            effective = _snapshot(source, vocab_db=override_vocab)
            self.assertEqual(
                effective.subject(TREE_SUBJECT).tree_total.count,
                _tree_count(EFFECTIVE_TREE),
            )
            self.assertIsNone(effective.vocab)

            # Changing only the registry path selects the supplementary tree.
            doc["reference"]["knowledge_trees"][TREE_SUBJECT] = _copy_tree(
                SUPPLEMENTARY_TREE, root,
                f"another/place/{TREE_SUBJECT}.yaml",
            )
            _write_registry(root, doc)
            supplementary = _snapshot(source, vocab_db=override_vocab)
            self.assertEqual(
                supplementary.subject(TREE_SUBJECT).tree_total.count,
                _tree_count(SUPPLEMENTARY_TREE),
            )

    def test_registered_but_missing_tree_is_a_contract_violation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "workspace"
            doc = _registry_doc()
            doc["reference"]["knowledge_trees"][TREE_SUBJECT] = "not-present/tree.yaml"
            source = _write_registry(root, doc)
            with self.assertRaises(ContractError) as caught:
                _snapshot(source, vocab_db=root / "missing-vocab.sqlite")
            self.assertEqual(
                caught.exception.path,
                f"reference.knowledge_trees.{TREE_SUBJECT}",
            )

    def test_subject_without_registered_tree_has_no_total(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "workspace"
            doc = _registry_doc()
            doc["reference"]["knowledge_trees"][TREE_SUBJECT] = _copy_tree(
                EFFECTIVE_TREE, root, "trees/current.yaml"
            )
            source = _write_registry(root, doc)
            result = _snapshot(source, vocab_db=root / "missing-vocab.sqlite")
            config_subjects = load_config(CONFIG_PATH).subjects
            unregistered_tree_subject = next(
                subject.subject_id
                for subject in config_subjects
                if subject.subject_id not in load_workspace(source).knowledge_trees
            )
            self.assertIsNone(result.subject(unregistered_tree_subject).tree_total)

    def test_config_subject_must_be_declared_by_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "workspace"
            doc = _registry_doc()
            removed_subject = load_config(CONFIG_PATH).subjects[-1].subject_id
            del doc["subjects"][removed_subject]
            source = _write_registry(root, doc)
            config = load_config(CONFIG_PATH)
            subjects = tuple(
                replace(subject, subject_id="outside-workspace")
                if subject.subject_id == removed_subject else subject
                for subject in config.subjects
            )
            with self.assertRaises(ContractError) as caught:
                build_snapshot(
                    replace(config, subjects=subjects),
                    (),
                    today=TODAY,
                    vocab_db=root / "missing-vocab.sqlite",
                    workspace=load_workspace(source),
                )
            expected_index = next(
                index for index, subject in enumerate(subjects)
                if subject.subject_id == "outside-workspace"
            )
            self.assertEqual(
                caught.exception.path,
                f"subjects[{expected_index}].subject_id",
            )

    def test_explicit_tree_and_vocab_override_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "workspace"
            doc = _registry_doc()
            doc["reference"]["knowledge_trees"][TREE_SUBJECT] = _copy_tree(
                SUPPLEMENTARY_TREE, root, f"registry/{TREE_SUBJECT}.yaml"
            )
            source = _write_registry(root, doc)
            explicit_relative = f"override/{TREE_SUBJECT}.yaml"
            explicit_tree = root / explicit_relative
            _copy_tree(EFFECTIVE_TREE, root, explicit_relative)
            workspace = load_workspace(source)
            result = build_snapshot(
                load_config(CONFIG_PATH),
                (),
                today=TODAY,
                tree_paths={TREE_SUBJECT: explicit_tree},
                vocab_db=root / "explicit-missing.sqlite",
                workspace=workspace,
            )
            self.assertEqual(
                result.subject(TREE_SUBJECT).tree_total.count,
                _tree_count(EFFECTIVE_TREE),
            )
            # If the registry's missing vocabulary path had been used this would raise.
            self.assertIsNone(result.vocab)

    def test_no_registry_or_explicit_sources_is_an_error(self) -> None:
        with self.assertRaises(ContractError) as caught:
            build_snapshot(load_config(CONFIG_PATH), (), today=TODAY)
        self.assertEqual(caught.exception.path, "workspace")


class StateSnapshotWorkspaceCliTests(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "ky", "snapshot", *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

    def test_snapshot_discovers_repository_registry_without_flag(self) -> None:
        with patch.dict(os.environ, {WORKSPACE_ENV: ""}):
            result = self._run(
                "--config", str(CONFIG_PATH), "--items", str(ITEMS_PATH),
                "--date", "2026-09-25", "--json",
            )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        subject = next(
            item for item in payload["subjects"]
            if item["subject_id"] == TREE_SUBJECT
        )
        self.assertEqual(subject["tree_total"]["count"], _tree_count(EFFECTIVE_TREE))

    def test_corrupt_completion_event_is_a_contract_violation(self) -> None:
        # sol round 86, M2: the delivered-word read raised CompletionError past the CLI.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "workspace"
            doc = _registry_doc()
            source = _write_registry(root, doc)
            workspace = load_workspace(source)
            event = workspace.plans / "2026-09" / "completion--2026-09-10.yaml"
            event.parent.mkdir(parents=True)
            event.write_text("not: a completion event\n", encoding="utf-8")
            vocab_db = Path(temporary) / "vocabulary.sqlite"
            shutil.copyfile(REPOSITORY_WORKSPACE.require("reference.vocabulary_db"), vocab_db)
            result = self._run(
                "--config", str(CONFIG_PATH), "--items", str(ITEMS_PATH),
                "--workspace", str(source), "--vocab-db", str(vocab_db),
                "--date", "2026-09-25", "--json",
            )
        self.assertEqual(result.returncode, 2, msg=result.stdout)
        self.assertIn("contract violation:", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_bad_explicit_workspace_does_not_fall_back_to_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {WORKSPACE_ENV: ""}):
            missing = Path(temporary) / "missing.yaml"
            result = self._run(
                "--config", str(CONFIG_PATH), "--items", str(ITEMS_PATH),
                "--workspace", str(missing), "--json",
            )
        self.assertEqual(result.returncode, 2)
        self.assertIn("contract violation:", result.stderr)
        self.assertIn("--workspace", result.stderr)

    def test_ky_workspace_environment_selects_alternate_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "workspace"
            doc = _registry_doc()
            doc["reference"]["knowledge_trees"][TREE_SUBJECT] = _copy_tree(
                SUPPLEMENTARY_TREE, root,
                f"relocated/{TREE_SUBJECT}.yaml",
            )
            source = _write_registry(root, doc)
            with patch.dict(os.environ, {WORKSPACE_ENV: str(source)}):
                result = self._run(
                    "--config", str(CONFIG_PATH), "--items", str(ITEMS_PATH),
                    "--vocab-db", str(root / "explicit-missing.sqlite"),
                    "--date", "2026-09-25", "--json",
                )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        subject = next(
            item for item in payload["subjects"]
            if item["subject_id"] == TREE_SUBJECT
        )
        self.assertEqual(subject["tree_total"]["count"], _tree_count(SUPPLEMENTARY_TREE))
        self.assertIsNone(payload["vocab"])


if __name__ == "__main__":
    unittest.main()
