"""M0/M2/M4/M15 contract drill for data-only subject onboarding."""

from __future__ import annotations

import copy
import hashlib
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from datetime import date
from pathlib import Path

import yaml

from ky.ledger import load_ledger
from ky.models import load_config
from ky.projection import build_projection
from ky.schedule.state_snapshot import build_snapshot
from ky.workspace import load_workspace

ROOT = Path(__file__).resolve().parents[2]


def _copy_registry_sources(workspace_root: Path) -> dict:
    source_path = ROOT / "kaoyan.workspace.yaml"
    document = yaml.safe_load(source_path.read_text(encoding="utf-8"))
    original_effective = dict(document["reference"]["knowledge_trees"])
    copied_effective: dict[str, str] = {}
    for subject, relative in document["reference"]["knowledge_trees"].items():
        destination = workspace_root / "inputs" / "trees" / f"{subject}.yaml"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
        document["reference"]["knowledge_trees"][subject] = destination.relative_to(
            workspace_root
        ).as_posix()
        copied_effective[subject] = document["reference"]["knowledge_trees"][subject]
    for subject, record in document["reference"].get("syllabus_versions", {}).items():
        for version, relative in list(record["versions"].items()):
            if relative == original_effective.get(subject):
                record["versions"][version] = copied_effective[subject]
                continue
            destination = workspace_root / "inputs" / "trees" / f"{subject}-{version}.yaml"
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, destination)
            record["versions"][version] = destination.relative_to(workspace_root).as_posix()
    for subject, paths in document["reference"]["exam_indexes"].items():
        copied = []
        for index, relative in enumerate(paths):
            destination = workspace_root / "inputs" / "indexes" / f"{subject}-{index}.json"
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, destination)
            copied.append(destination.relative_to(workspace_root).as_posix())
        document["reference"]["exam_indexes"][subject] = copied
    for name, view in document.get("supplementary", {}).items():
        for role, relative in view["files"].items():
            destination = workspace_root / "inputs" / "supplementary" / f"{name}-{role}.yaml"
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, destination)
            view["files"][role] = destination.relative_to(workspace_root).as_posix()
    for key in ("topic_weights", "vocabulary_db"):
        relative = document["reference"][key]
        destination = workspace_root / "inputs" / Path(relative).name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
        document["reference"][key] = destination.relative_to(workspace_root).as_posix()
    ledger = workspace_root / "data" / "materials.yaml"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / document["reference"]["ledger"], ledger)
    document["reference"]["ledger"] = ledger.relative_to(workspace_root).as_posix()
    document["projection"] = "out/projection.sqlite"
    return document


def _write_tree(root: Path, *, subject: str, mismatch: bool = False) -> Path:
    source = root / "outline.txt"
    source.write_text("Crop Science\n", encoding="utf-8")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    chapter_id = f"{subject}.agronomy.chapter"
    if mismatch:
        chapter_id = f"{subject}.agronomy.chapter-01"
    items = []
    for point_id, title, scope in (
        (chapter_id, "Agronomy", "chapter"),
        (f"{subject}.agronomy.content", "Content", "section"),
        (f"{subject}.agronomy.requirements", "Requirements", "section"),
    ):
        items.append(
            {
                "schema_version": 1,
                "knowledge_point_id": point_id,
                "title": title,
                "status": "raw",
                "source_kind": "official_outline",
                "sources": [
                    {
                        "path": "outline.txt",
                        "sha256": digest,
                        "locator": {"quote_ref": "Crop Science"},
                    }
                ],
                "scope": scope,
            }
        )
    tree = root / "trees" / f"{subject}.yaml"
    tree.parent.mkdir(parents=True, exist_ok=True)
    tree.write_text(yaml.safe_dump(items, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return tree


class SubjectOnboardingContractTest(unittest.TestCase):
    def test_new_subject_is_data_only_across_consumers(self) -> None:
        subject = "agri314"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "workspace"
            root.mkdir()
            registry_doc = _copy_registry_sources(root)
            tree = _write_tree(root, subject=subject)
            registry_doc["subjects"][subject] = {
                "name": "Agronomy",
                "tree_grammar": "named_chapters",
            }
            registry_doc["reference"]["knowledge_trees"][subject] = (
                tree.relative_to(root).as_posix()
            )
            registry = root / "kaoyan.workspace.yaml"
            registry.write_text(
                yaml.safe_dump(registry_doc, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )

            workspace = load_workspace(registry)
            self.assertIn(subject, workspace.subjects)
            self.assertEqual(workspace.subject_profiles[subject].tree_grammar, "named_chapters")
            checked = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools/verify_tree.py"),
                    str(tree),
                    "--workspace",
                    str(registry),
                    "--root",
                    str(root),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)

            ledger_doc = yaml.safe_load(workspace.ledger.read_text(encoding="utf-8"))
            ledger_entry = copy.deepcopy(ledger_doc["items"][0])
            ledger_entry["resource_id"] = "agri314-onboarding-source"
            ledger_entry["subjects"] = [subject]
            ledger_doc["items"] = [ledger_entry]
            workspace.ledger.write_text(
                yaml.safe_dump(ledger_doc, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            materials = load_ledger(
                workspace.ledger,
                subject_ids=frozenset(workspace.subjects) | {"general"},
            )
            self.assertEqual(materials[0].subjects, (subject,))

            config_path = root / "agri-config.yaml"
            config_path.write_text(
                yaml.safe_dump(
                    {
                        "schema_version": 1,
                        "project_id": "onboarding",
                        "default_daily_minutes": 60,
                        "review_reserve_ratio": 0.4,
                        "hard_max_ratio": 0.6,
                        "subjects": [
                            {
                                "subject_id": subject,
                                "display_name": "Agronomy",
                                "weight": 1.0,
                                "active": True,
                                "min_daily_minutes": 0,
                            }
                        ],
                    },
                    allow_unicode=True,
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            snapshot = build_snapshot(
                load_config(config_path),
                (),
                today=date(2026, 9, 25),
                workspace=workspace,
            )
            self.assertIsNotNone(snapshot.subject(subject).tree_total)

            output = root / "projection.sqlite"
            build_projection(workspace, output)
            with closing(sqlite3.connect(output)) as connection:
                row = connection.execute(
                    "SELECT domain FROM knowledge_points WHERE subject_id=? LIMIT 1",
                    (subject,),
                ).fetchone()
                self.assertIsNotNone(row)
                self.assertIsNone(row[0])
                point_ids = {
                    record[0]
                    for record in connection.execute(
                        "SELECT knowledge_point_id FROM knowledge_points WHERE subject_id=?",
                        (subject,),
                    )
                }
                self.assertIn(f"{subject}.agronomy.chapter", point_ids)

            bad_tree = _write_tree(root, subject=subject, mismatch=True)
            registry_doc["reference"]["knowledge_trees"][subject] = (
                bad_tree.relative_to(root).as_posix()
            )
            registry.write_text(
                yaml.safe_dump(registry_doc, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            rejected = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools/verify_tree.py"),
                    str(bad_tree),
                    "--workspace",
                    str(registry),
                    "--root",
                    str(root),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(rejected.returncode, 1, rejected.stdout + rejected.stderr)
            self.assertIn("conflicts with numbered_chapters id syntax", rejected.stdout)


if __name__ == "__main__":
    unittest.main()
