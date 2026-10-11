"""M6 topic-weight aggregation and incremental-growth contract."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from ky.exam.topic_weights import aggregate_topic_weights
from ky.knowledge import KnowledgePoint, load_knowledge_points, nearest_ancestor_with_scope
from ky.models import ContractError
from ky.workspace import load_workspace
import tools.apply_knowledge_weights as apply_weights


ROOT = Path(__file__).resolve().parents[2]


def _inputs() -> tuple[dict, dict, dict, dict]:
    workspace = load_workspace(ROOT / "kaoyan.workspace.yaml")
    manifest_path = workspace.require("reference.weight_batches")
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    coder_outputs: dict[str, dict] = {}
    for batch in manifest["batches"]:
        for relative in batch["coders"].values():
            coder_outputs.setdefault(
                relative,
                json.loads((ROOT / relative).read_text(encoding="utf-8")),
            )
    subjects = {batch["subject_id"] for batch in manifest["batches"]}
    trees: dict[str, dict[str, KnowledgePoint]] = {}
    for subject in subjects:
        path = workspace.require(f"reference.knowledge_trees.{subject}")
        points = load_knowledge_points(path)
        trees[subject] = {point.knowledge_point_id: point for point in points}
    current = json.loads(
        workspace.require("reference.topic_weights").read_text(encoding="utf-8")
    )
    return manifest, coder_outputs, trees, current


def _assert_contract_error(
    test: unittest.TestCase,
    manifest: dict,
    coder_outputs: dict,
    trees: dict,
    expected: str,
) -> None:
    with test.assertRaises(ContractError) as caught:
        aggregate_topic_weights(manifest, coder_outputs, trees)
    test.assertIn(expected, str(caught.exception))


def _copy_aggregation_workspace(temp_root: Path, *, copy_artifact: bool) -> Path:
    workspace = load_workspace(ROOT / "kaoyan.workspace.yaml")
    registry = temp_root / "kaoyan.workspace.yaml"
    shutil.copyfile(workspace.source, registry)
    manifest_path = workspace.require("reference.weight_batches")
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    registered_files = {manifest_path}
    for batch in manifest["batches"]:
        for relative in batch["coders"].values():
            registered_files.add(workspace.root / relative)
    for subject in {batch["subject_id"] for batch in manifest["batches"]}:
        registered_files.add(workspace.require(f"reference.knowledge_trees.{subject}"))
    if copy_artifact:
        registered_files.add(workspace.topic_weights)
    for source in registered_files:
        relative = source.relative_to(workspace.root)
        target = temp_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    return registry


def _run_aggregator(registry: Path, mode: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "aggregate_topic_weights.py"),
            mode,
            "--workspace",
            str(registry),
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
        encoding="utf-8",
    )


def _run_apply_weights(root: Path, weights_path: Path) -> int:
    with (
        patch.object(apply_weights, "ROOT", root),
        patch.object(apply_weights, "TOPIC_WEIGHTS", weights_path),
        patch.object(sys, "argv", ["apply_knowledge_weights.py"]),
    ):
        return apply_weights.main()


def _copy_weight_tool_fixture(clone: Path, source: str) -> Path:
    tools_dir = clone / "tools"
    tools_dir.mkdir(parents=True)
    tool_path = tools_dir / "apply_knowledge_weights.py"
    tool_path.write_text(source, encoding="utf-8")
    shutil.copyfile(ROOT / "tools" / "verify_408_index.py", tools_dir / "verify_408_index.py")
    shutil.copyfile(ROOT / "kaoyan.workspace.yaml", clone / "kaoyan.workspace.yaml")
    weights_target = clone / "data" / "review_weights" / "topic_weights.json"
    weights_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "data" / "review_weights" / "topic_weights.json", weights_target)
    shutil.copytree(ROOT / "data" / "exam_questions", clone / "data" / "exam_questions")
    return tool_path


def _run_apply_tool(tool_path: Path, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(tool_path)],
        cwd=cwd,
        capture_output=True,
        check=False,
        env={
            **os.environ,
            "PYTHONPATH": os.pathsep.join(
                filter(None, [str(ROOT), os.environ.get("PYTHONPATH", "")])
            ),
        },
        text=True,
        encoding="utf-8",
    )


def _index_bytes(root: Path) -> dict[Path, bytes]:
    index_dir = root / "data" / "exam_questions"
    return {
        path.relative_to(index_dir): path.read_bytes()
        for path in index_dir.glob("*.json")
    }


def _write_source_index(path: Path, paper_source: str) -> None:
    question_id = (
        "cs408-2023-01" if paper_source == "national" else "cs408-xidian-2023-01"
    )
    document = {
        "subject_id": "cs408",
        "exam_year": 2023,
        "paper_source": paper_source,
        "entries": [
            {
                "number": 1,
                "question_id": question_id,
                "knowledge_point_id": None,
                "knowledge_point_weights": None,
                "knowledge_point_status": "not_assigned",
            }
        ],
    }
    path.write_text(json.dumps(document), encoding="utf-8")


class TopicWeightsPortContractTests(unittest.TestCase):
    def test_registered_batches_reproduce_the_current_artifact(self) -> None:
        manifest, coder_outputs, trees, current = _inputs()
        self.assertEqual(
            aggregate_topic_weights(manifest, coder_outputs, trees), current
        )

    def test_adding_a_batch_preserves_old_questions_and_adds_only_its_weight(self) -> None:
        manifest, coder_outputs, trees, current = _inputs()
        before = aggregate_topic_weights(manifest, coder_outputs, trees)
        subject = next(
            subject
            for subject, policy in manifest["topic_rollup"].items()
            if policy == "chapter"
        )
        tree = trees[subject]
        chapter_id, coded_nodes = self._chapter_nodes(subject, tree)
        coders = manifest["coders"]
        max_confidence = max(
            manifest["confidence_weights"],
            key=manifest["confidence_weights"].__getitem__,
        )
        min_confidence = min(
            manifest["confidence_weights"],
            key=manifest["confidence_weights"].__getitem__,
        )

        with tempfile.TemporaryDirectory() as temporary:
            temp_root = Path(temporary)
            copied_manifest = copy.deepcopy(manifest)
            copied_outputs: dict[str, dict] = {}
            for batch in copied_manifest["batches"]:
                for coder, relative in batch["coders"].items():
                    destination = temp_root / relative
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(ROOT / relative, destination)
                    copied_outputs[relative] = json.loads(
                        destination.read_text(encoding="utf-8")
                    )

            years = [batch["exam_year"] for batch in copied_manifest["batches"]]
            new_year = max(years) + 1
            new_batch_paths: dict[str, str] = {}
            for coder_index, coder in enumerate(coders):
                relative = f"synthetic/{subject}-{new_year}-{coder}.json"
                new_batch_paths[coder] = relative
                entries = [
                    {"number": 1, "nodes": [coded_nodes[0]], "confidence": max_confidence},
                    {
                        "number": 2,
                        "nodes": [coded_nodes[0] if coder_index < 2 else coded_nodes[1]],
                        "confidence": max_confidence,
                    },
                    {
                        "number": 3,
                        "nodes": [coded_nodes[0] if coder_index == 0 else coded_nodes[1]],
                        "confidence": (
                            min_confidence if coder_index == 0 else max_confidence
                        ),
                    },
                ]
                document = {
                    "meta": {
                        "coder": coder,
                        "subject": subject,
                        "year": new_year,
                        "node_table_sha256": f"source-{coder_index}",
                    },
                    "entries": entries,
                }
                output_path = temp_root / relative
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(
                    json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                copied_outputs[relative] = document

            copied_manifest["batches"].append(
                {
                    "subject_id": subject,
                    "exam_year": new_year,
                    "coders": new_batch_paths,
                }
            )
            manifest_file = temp_root / "batches.yaml"
            manifest_file.write_text(
                yaml.safe_dump(
                    copied_manifest, allow_unicode=True, sort_keys=False
                ),
                encoding="utf-8",
            )
            copied_manifest = yaml.safe_load(
                manifest_file.read_text(encoding="utf-8")
            )
            after = aggregate_topic_weights(copied_manifest, copied_outputs, trees)

        old_keys = set(before["per_question"])
        self.assertEqual(old_keys, set(current["per_question"]))
        for key in old_keys:
            old_json = json.dumps(
                before["per_question"][key], ensure_ascii=False, separators=(",", ":")
            )
            new_json = json.dumps(
                after["per_question"][key], ensure_ascii=False, separators=(",", ":")
            )
            self.assertEqual(old_json, new_json, key)

        before_weights = before["topic_weight"][subject]
        after_weights = after["topic_weight"][subject]
        self.assertEqual(after_weights[chapter_id] - before_weights[chapter_id], 3.0)
        for node_id, value in before_weights.items():
            if node_id != chapter_id:
                self.assertEqual(after_weights[node_id], value, node_id)

    def test_unregistered_node_reports_coder_question_and_node(self) -> None:
        manifest, outputs, trees, _ = _inputs()
        manifest = copy.deepcopy(manifest)
        outputs = copy.deepcopy(outputs)
        batch = manifest["batches"][0]
        coder = manifest["coders"][0]
        path = batch["coders"][coder]
        outputs[path]["entries"][0]["nodes"] = ["not.a.registered.node"]
        _assert_contract_error(
            self,
            manifest,
            outputs,
            trees,
            f"coder {coder}, question 1: node 'not.a.registered.node' is not in the active tree",
        )

    def test_missing_question_number_is_rejected(self) -> None:
        manifest, outputs, trees, _ = _inputs()
        manifest = copy.deepcopy(manifest)
        outputs = copy.deepcopy(outputs)
        batch = manifest["batches"][0]
        coder = manifest["coders"][1]
        path = batch["coders"][coder]
        outputs[path]["entries"].pop()
        _assert_contract_error(
            self, manifest, outputs, trees, "question numbers missing="
        )

    def test_duplicate_question_number_is_rejected(self) -> None:
        manifest, outputs, trees, _ = _inputs()
        manifest = copy.deepcopy(manifest)
        outputs = copy.deepcopy(outputs)
        batch = manifest["batches"][0]
        coder = manifest["coders"][0]
        path = batch["coders"][coder]
        outputs[path]["entries"].append(copy.deepcopy(outputs[path]["entries"][0]))
        _assert_contract_error(self, manifest, outputs, trees, "duplicate question number")

    def test_duplicate_batch_is_rejected(self) -> None:
        manifest, outputs, trees, _ = _inputs()
        manifest = copy.deepcopy(manifest)
        manifest["batches"].append(copy.deepcopy(manifest["batches"][0]))
        _assert_contract_error(self, manifest, outputs, trees, "duplicate batch")

    def test_batch_year_must_be_four_digits(self) -> None:
        manifest, outputs, trees, _ = _inputs()
        manifest = copy.deepcopy(manifest)
        outputs = copy.deepcopy(outputs)
        for path in manifest["batches"][0]["coders"].values():
            outputs[path]["meta"]["year"] = 1
        manifest["batches"][0]["exam_year"] = 1
        _assert_contract_error(
            self, manifest, outputs, trees, "expected a four-digit year"
        )

    def test_invalid_paper_source_code_is_rejected(self) -> None:
        manifest, outputs, trees, _ = _inputs()
        manifest = copy.deepcopy(manifest)
        manifest["batches"][0]["paper_source"] = "school-x"
        _assert_contract_error(
            self, manifest, outputs, trees, "invalid paper source code"
        )

    def test_xidian_paper_source_is_accepted(self) -> None:
        manifest, outputs, trees, _ = _inputs()
        manifest = copy.deepcopy(manifest)
        batch = manifest["batches"][0]
        batch["paper_source"] = "xidian"
        result = aggregate_topic_weights(manifest, outputs, trees)
        self.assertIn(
            f"{batch['subject_id']}-xidian-{batch['exam_year']}-1",
            result["per_question"],
        )

    def test_write_rebuilds_corrupt_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temp_root = Path(temporary)
            registry = _copy_aggregation_workspace(temp_root, copy_artifact=True)
            workspace = load_workspace(registry)
            workspace.topic_weights.write_text("not-json", encoding="utf-8")
            written = _run_aggregator(registry, "--write")
            self.assertEqual(written.returncode, 0, written.stderr)
            checked = _run_aggregator(registry, "--check")
            self.assertEqual(checked.returncode, 0, checked.stderr)
            self.assertIn("numeric equality, no tolerance", checked.stdout)

    def test_write_rebuilds_missing_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temp_root = Path(temporary)
            registry = _copy_aggregation_workspace(temp_root, copy_artifact=False)
            workspace = load_workspace(registry)
            self.assertFalse(workspace.topic_weights.exists())
            written = _run_aggregator(registry, "--write")
            self.assertEqual(written.returncode, 0, written.stderr)
            checked = _run_aggregator(registry, "--check")
            self.assertEqual(checked.returncode, 0, checked.stderr)

    def test_write_does_not_rewrite_a_hard_linked_outside_file(self) -> None:
        # sol round 83, W2: the registered name may be a hard link to a file outside the
        # workspace; --write must replace the name, not write through the link.
        with tempfile.TemporaryDirectory() as temporary, \
                tempfile.TemporaryDirectory() as elsewhere:
            temp_root = Path(temporary)
            registry = _copy_aggregation_workspace(temp_root, copy_artifact=False)
            workspace = load_workspace(registry)
            outside = Path(elsewhere) / "outside.json"
            outside.write_text("outside sentinel", encoding="utf-8")
            workspace.topic_weights.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.link(outside, workspace.topic_weights)
            except OSError as exc:
                self.skipTest(f"hard links unavailable: {exc}")
            written = _run_aggregator(registry, "--write")
            self.assertEqual(written.returncode, 0, written.stderr)
            self.assertEqual(outside.read_text(encoding="utf-8"), "outside sentinel")
            self.assertEqual(_run_aggregator(registry, "--check").returncode, 0)

    def test_write_bytes_match_fixed_baseline(self) -> None:
        # sol round 96: --check compares numbers only, so a newline change in --write went
        # unnoticed. Compare raw bytes against the tool as of 8f31a05 (pinned, not HEAD).
        baseline = subprocess.run(
            ["git", "show", "8f31a05:tools/aggregate_topic_weights.py"],
            cwd=ROOT, capture_output=True, check=True, text=True, encoding="utf-8",
        ).stdout
        self.assertIn("def _replace_file(target: Path, text: str)", baseline)
        current = (ROOT / "tools" / "aggregate_topic_weights.py").read_text(encoding="utf-8")
        environment = {
            **os.environ,
            "PYTHONPATH": os.pathsep.join(
                filter(None, [str(ROOT), os.environ.get("PYTHONPATH", "")])
            ),
        }
        with tempfile.TemporaryDirectory() as temporary:
            written_bytes = []
            for label, source in (("baseline", baseline), ("current", current)):
                clone = Path(temporary) / label
                clone.mkdir()
                registry = _copy_aggregation_workspace(clone, copy_artifact=False)
                tool_path = clone / "tools" / "aggregate_topic_weights.py"
                tool_path.parent.mkdir(parents=True)
                tool_path.write_text(source, encoding="utf-8")
                completed = subprocess.run(
                    [sys.executable, str(tool_path), "--write", "--workspace", str(registry)],
                    cwd=clone, capture_output=True, check=False, env=environment,
                    text=True, encoding="utf-8",
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                written_bytes.append(load_workspace(registry).topic_weights.read_bytes())
            self.assertNotIn(b"\r", written_bytes[1])
            self.assertEqual(
                written_bytes[0].replace(b"\r\n", b"\n"),
                written_bytes[1].replace(b"\r\n", b"\n"),
            )

    def test_school_paper_key_writes_to_matching_index(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temp_root = Path(temporary)
            registry = yaml.safe_load(
                (ROOT / "kaoyan.workspace.yaml").read_text(encoding="utf-8")
            )
            registry["reference"]["exam_indexes"] = {
                "cs408": [
                    "data/exam_questions/national.json",
                    "data/exam_questions/school.json",
                ]
            }
            registry_path = temp_root / "kaoyan.workspace.yaml"
            registry_path.write_text(
                yaml.safe_dump(registry, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            weights_path = temp_root / "topic_weights.json"
            weights_path.write_text(
                json.dumps(
                    {
                        "per_question": {
                            "cs408-xidian-2023-1": {
                                "distribution": {"cs408.os.chapter-01": 1.0}
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            index_dir = temp_root / "data" / "exam_questions"
            index_dir.mkdir(parents=True)
            national_path = index_dir / "national.json"
            school_path = index_dir / "school.json"
            _write_source_index(national_path, "national")
            _write_source_index(school_path, "xidian")
            # An unregistered file with the same identity must stay untouched: only
            # registered indexes are written (sol round 83, W8).
            decoy_path = index_dir / "stray.json"
            _write_source_index(decoy_path, "xidian")
            decoy_before = decoy_path.read_bytes()
            self.assertEqual(_run_apply_weights(temp_root, weights_path), 0)
            self.assertEqual(decoy_path.read_bytes(), decoy_before)
            result = json.loads(school_path.read_text(encoding="utf-8"))
            entry = result["entries"][0]
            self.assertEqual(entry["knowledge_point_id"], "cs408.os.chapter-01")
            self.assertEqual(entry["knowledge_point_status"], "assigned_multi_model")
            national_entry = json.loads(national_path.read_text(encoding="utf-8"))[
                "entries"
            ][0]
            self.assertIsNone(national_entry["knowledge_point_id"])

    def test_national_index_bytes_match_fixed_baseline(self) -> None:
        baseline = subprocess.run(
            ["git", "show", "11cda18:tools/apply_knowledge_weights.py"],
            cwd=ROOT,
            capture_output=True,
            check=True,
            text=True,
            encoding="utf-8",
        ).stdout
        self.assertIn(
            'QUESTION_KEY = re.compile(r"^([a-z0-9]+)-(\\d{4})-(\\d+)$")',
            baseline,
        )
        current = (ROOT / "tools" / "apply_knowledge_weights.py").read_text(
            encoding="utf-8"
        )
        with tempfile.TemporaryDirectory() as temporary:
            temp_root = Path(temporary)
            result_bytes = []
            for label, source in (("baseline", baseline), ("current", current)):
                clone = temp_root / label
                tool_path = _copy_weight_tool_fixture(clone, source)
                completed = _run_apply_tool(tool_path, clone)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                result_bytes.append(_index_bytes(clone))
            self.assertTrue(all(b"\r" not in data for data in result_bytes[1].values()))
            self.assertEqual(
                {
                    path: data.replace(b"\r\n", b"\n")
                    for path, data in result_bytes[0].items()
                },
                {
                    path: data.replace(b"\r\n", b"\n")
                    for path, data in result_bytes[1].items()
                },
            )

    @staticmethod
    def _chapter_nodes(
        subject: str,
        tree: dict[str, KnowledgePoint],
    ) -> tuple[str, tuple[str, str]]:
        chapters = [
            point_id for point_id, point in tree.items() if point.scope == "chapter"
        ]
        for chapter_id in chapters:
            descendants = [
                point_id
                for point_id in tree
                if nearest_ancestor_with_scope(point_id, tree, "chapter") == chapter_id
            ]
            candidates = [chapter_id, *descendants]
            unique: list[str] = []
            for point_id in candidates:
                if point_id not in unique:
                    unique.append(point_id)
                if len(unique) == 2:
                    return chapter_id, (unique[0], unique[1])
        raise AssertionError(f"subject {subject!r} has no chapter with two usable nodes")


if __name__ == "__main__":
    unittest.main()
