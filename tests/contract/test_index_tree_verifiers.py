"""Current behavior contract tests for registered exam-index and knowledge-tree verifiers."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any, NamedTuple

import yaml

from ky.exam.paper_shape import load_paper_shapes
from ky.knowledge.knowledge_point import load_knowledge_points
from ky.ledger import load_ledger
from ky.workspace import load_workspace
from tools.verify_408_index import verify
from tests._resources import require_path


ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_PATH = ROOT / "kaoyan.workspace.yaml"

Change = tuple[tuple[Any, ...], Any]


class IndexEdit(NamedTuple):
    """One index error aimed at one check of ``verify``.

    ``marker`` is a substring of the problem that check reports. ``stage`` says where the
    check runs relative to the empty-entries early return: ``head`` before it, ``return`` is
    the early return itself, ``body`` after it (hidden when entries are empty).
    """

    name: str
    changes: tuple[Change, ...]
    marker: str
    stage: str


class TreeVariant(NamedTuple):
    """One ``verify_tree.py`` input with the exit code and report lines it must produce."""

    name: str
    document: Any
    extra_args: tuple[str, ...]
    exit_code: int
    markers: tuple[str, ...]


def _with_value(document: Any, path: tuple[Any, ...], value: Any) -> None:
    node = document
    for key in path[:-1]:
        # Only mappings get missing intermediate keys; a list index must already exist.
        if isinstance(node, dict) and key not in node:
            node[key] = {}
        node = node[key]
    node[path[-1]] = value


def _capture_verify(function, path: Path, workspace, materials) -> tuple[Any, bytes, bytes]:
    stdout = StringIO()
    stderr = StringIO()
    try:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = function(path, workspace, materials)
        value = ("return", json.dumps(result, ensure_ascii=False).encode("utf-8"))
    except Exception as exc:  # Match exception type and message as part of the observable result.
        value = (
            "exception", type(exc).__module__, type(exc).__qualname__,
            str(exc).encode("utf-8"),
        )
    return value, stdout.getvalue().encode("utf-8"), stderr.getvalue().encode("utf-8")


def _shape_answer_edit(entries: list[Any]) -> IndexEdit:
    """A letter that is legal for its section but disagrees with the registered answer source.

    Taken from another answered entry, so no answer letter is written into the test. The last
    answered entry is edited so the entry-level errors on ``entries[0]`` (e.g. a bad number,
    which takes that entry out of the answer comparison) cannot hide this one in a pair.
    """
    answered = [
        index for index, entry in enumerate(entries)
        if isinstance(entry, dict) and entry.get("answer")
    ]
    target = answered[-1]
    other = next(
        entries[index]["answer"] for index in answered
        if entries[index]["answer"] != entries[target]["answer"]
    )
    return IndexEdit(
        "paper-shape", ((("entries", target, "answer"), other),),
        f"answer {other!r} != source", "body",
    )


def _index_edits(seed: dict[str, Any]) -> list[IndexEdit]:
    """One error per check of ``verify``, each chosen so that check itself reports it.

    Values follow sol round 150 G3d-M1: ``schema_version=999`` or the seed's own calibration
    produce no problem, and a well-formed but wrong digest only fails the later ledger check.
    """
    first = ("entries", 0)
    return [
        IndexEdit("header", ((("schema_version",), None),),
                  "$: schema_version must be an int", "head"),
        IndexEdit("provenance-shape", ((("provenance", "paper", "sha256"), "bad"),),
                  "$.provenance.paper.sha256: not a 64-char", "head"),
        IndexEdit("coverage-shape", ((("answer_source_coverage",), []),),
                  "$.answer_source_coverage: expected an object", "head"),
        IndexEdit("entries-empty", ((("entries",), []),),
                  "$.entries: expected a non-empty list", "return"),
        IndexEdit("identity", (((*first, "number"), -1),),
                  "$.entries[0].number: must be a positive int", "body"),
        IndexEdit("values", (((*first, "marks"), -1),),
                  "$.entries[0].marks: must be null or a positive number", "body"),
        IndexEdit("weights", (((*first, "knowledge_point_weights"), []),),
                  "$.entries[0].knowledge_point_weights: expected an object", "body"),
        IndexEdit("assignment", (((*first, "knowledge_point_status"), "not_assigned"),),
                  "$.entries[0]: knowledge_point_status=not_assigned", "body"),
        IndexEdit("notes", (((*first, "notes"), "probe"),),
                  "$.entries[0].notes: must be null", "body"),
        IndexEdit("sources", (((*first, "answer_sources"), "invalid"),),
                  "$.entries[0].answer_sources: expected a list", "body"),
        IndexEdit("locator", (((*first, "locator", "page"), -1),),
                  "$.entries[0].locator.page: must be a non-negative int", "body"),
        IndexEdit("free-text", ((("content_policy",), 12),),
                  "$.content_policy: expected a string", "body"),
        IndexEdit("totals", ((("question_count",), seed.get("question_count", 0) + 1),),
                  "question_count disagrees with entries length", "body"),
        IndexEdit("answer-coverage", ((("answer_source_coverage", "choice_total"), -1),),
                  "!= answer_source_coverage.choice_total -1", "body"),
        IndexEdit("registered-provenance", ((("provenance", "paper", "sha256"), "0" * 64),),
                  "$.provenance.paper: disk hash != index hash", "body"),
        _shape_answer_edit(seed["entries"]),
        IndexEdit("calibration", (
            (("calibration",), "awaiting_official_book"),
            ((*first, "answer_confidence"), "official"),
        ), "claims official answer while uncalibrated", "body"),
    ]


def _paths_overlap(first: IndexEdit, second: IndexEdit) -> bool:
    """True when one edit writes the same field as, or a field inside, the other's field.

    Such a pair would overwrite (or fail to reach) the first error instead of adding a second.
    """
    for left, _ in first.changes:
        for right, _ in second.changes:
            shorter = min(len(left), len(right))
            if left[:shorter] == right[:shorter]:
                return True
    return False


def _expected_markers(edits: tuple[IndexEdit, ...]) -> list[str]:
    if any(edit.stage == "return" for edit in edits):
        return [edit.marker for edit in edits if edit.stage != "body"]
    return [edit.marker for edit in edits]


def _index_variants(seed: dict[str, Any]) -> list[tuple[str, Any, list[str]]]:
    """The valid seed, every single error, and every pair of errors on different fields."""
    edits = _index_edits(seed)
    groups: list[tuple[IndexEdit, ...]] = [(edit,) for edit in edits]
    for first in range(len(edits)):
        for second in range(first + 1, len(edits)):
            if not _paths_overlap(edits[first], edits[second]):
                groups.append((edits[first], edits[second]))
    variants: list[tuple[str, Any, list[str]]] = [("valid", copy.deepcopy(seed), [])]
    for group in groups:
        document = copy.deepcopy(seed)
        for edit in group:
            for path, value in edit.changes:
                _with_value(document, path, value)
        name = "+".join(edit.name for edit in group)
        variants.append((name, document, _expected_markers(group)))
    return variants


def _tree_items(document: Any) -> list[dict[str, Any]]:
    return document["items"] if isinstance(document, dict) else document


def _tree_copy(seed: Any, *edits) -> Any:
    document = copy.deepcopy(seed)
    for edit in edits:
        edit(_tree_items(document))
    return document


def _yaml_variants(seed: Any) -> list[TreeVariant]:
    """Tree inputs that each reach one stage of ``verify_tree.main``, plus stage pairs.

    sol round 150 G3d-M2: the provenance stage needs an input of its own, and pairs with the
    structure and required-scope stages fix the order of their failures. The context, empty
    tree and status-note inputs fix the order of the two contract exits, the node-count line
    before the empty-tree exit, and the note lines after the failure exit.
    """
    items = _tree_items(seed)
    sourced = next(index for index, point in enumerate(items) if point.get("sources"))
    missing_scope = "g3d-missing-scope"

    def damage_hash(points: list[dict[str, Any]]) -> None:
        points[sourced]["sources"][0]["sha256"] = "0" * 64

    def damage_quote(points: list[dict[str, Any]]) -> None:
        points[sourced]["sources"][0]["locator"]["quote_ref"] = "g3d-absent-quote-probe"

    def damage_contract(points: list[dict[str, Any]]) -> None:
        points[sourced].pop("title", None)

    def damage_structure(points: list[dict[str, Any]]) -> None:
        points[1]["knowledge_point_id"] = points[0]["knowledge_point_id"]

    def add_evidence(points: list[dict[str, Any]]) -> None:
        # Contract-valid evidence; only the verifier's "extracted nodes carry none" rule fails.
        source = copy.deepcopy(points[sourced]["sources"][0])
        points[sourced]["evidence"] = [{"validation": "guided", "source": source}]

    def empty(points: list[dict[str, Any]]) -> None:
        points.clear()

    def raw_status(points: list[dict[str, Any]]) -> None:
        # A raw node needs no transition history; the verifier prints a note, not a failure.
        points[sourced]["status"] = "raw"
        points[sourced].pop("transition_history", None)

    duplicate = "duplicate knowledge_point_id"
    evidence = "extracted node must not carry evidence"
    note = "status=raw (expected extracted)"
    scope = f"required scope {missing_scope!r} not present"
    require = ("--require-scopes", missing_scope)
    return [
        TreeVariant("valid", _tree_copy(seed), (), 0, ("ALL CHECKS PASSED",)),
        TreeVariant("source-hash", _tree_copy(seed, damage_hash), (), 1, ("sha256 mismatch",)),
        TreeVariant("quote-ref", _tree_copy(seed, damage_quote), (), 1,
                    ("quote_ref       : FAIL",)),
        TreeVariant("contract", _tree_copy(seed, damage_contract), (), 2,
                    ("CONTRACT FAILURE",)),
        TreeVariant("context+contract", _tree_copy(seed, damage_contract),
                    ("--subject", "g3d-unknown-subject"), 2, ("unknown subject",)),
        TreeVariant("empty-tree", _tree_copy(seed, empty), (), 2,
                    ("(0 nodes", "CONTRACT FAILURE: empty tree")),
        TreeVariant("structure", _tree_copy(seed, damage_structure), (), 1, (duplicate,)),
        TreeVariant("provenance", _tree_copy(seed, add_evidence), (), 1, (evidence,)),
        TreeVariant("require-scopes", _tree_copy(seed), require, 1, (scope,)),
        TreeVariant("structure+provenance", _tree_copy(seed, damage_structure, add_evidence),
                    (), 1, (duplicate, evidence)),
        TreeVariant("provenance+require-scopes", _tree_copy(seed, add_evidence), require, 1,
                    (evidence, scope)),
        TreeVariant("status-note", _tree_copy(seed, raw_status), (), 0, (note,)),
        TreeVariant("status-note+require-scopes", _tree_copy(seed, raw_status), require, 1,
                    (scope,)),
    ]


class IndexTreeVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workspace = load_workspace(WORKSPACE_PATH)
        ledger_path = cls.workspace.require("reference.ledger")
        cls.materials = {item.resource_id: item for item in load_ledger(ledger_path)}

    def _index_seed(self) -> tuple[Path, dict[str, Any]]:
        for subject, paths in self.workspace.exam_indexes.items():
            shape_path = self.workspace.paper_shapes.get(subject)
            if shape_path is None:
                continue
            shapes = load_paper_shapes(shape_path, subject_id=subject)
            for path in paths:
                if not path.is_file():
                    continue
                seed = json.loads(path.read_text(encoding="utf-8"))
                shape = shapes.get(seed.get("exam_year"), seed.get("paper_source", "national"))
                if shape is None or not getattr(shape, "answer_reader", None):
                    continue
                for block in (seed.get("provenance") or {}).values():
                    material = self.materials.get((block or {}).get("resource_id"))
                    if material is not None and material.storage.path:
                        require_path(
                            self, self.workspace.root / material.storage.path,
                            "restore the registered raw source from its ledger record",
                        )
                return path, seed
        self.skipTest("no registered index with a registered answer reader is available")

    def _assert_index_markers(self, captured: tuple[Any, bytes, bytes], markers: list[str]):
        value = captured[0]
        self.assertEqual(value[0], "return", value)
        problems = json.loads(value[1].decode("utf-8"))
        if not markers:
            self.assertEqual(problems, [])
        for marker in markers:
            self.assertTrue(
                any(marker in problem for problem in problems),
                f"expected a problem containing {marker!r}, got {problems}",
            )

    def test_registered_index_variants_emit_expected_diagnostics(self) -> None:
        _, seed = self._index_seed()
        variants = _index_variants(seed)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for index, (name, document, markers) in enumerate(variants):
                candidate = root / f"index-{index}.json"
                candidate.write_text(
                    json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                with self.subTest(variant=name):
                    current = _capture_verify(
                        verify, candidate, self.workspace, self.materials
                    )
                    self._assert_index_markers(current, markers)

    def _assert_tree_markers(self, variant: TreeVariant, current) -> None:
        # Markers are ASCII; the console code page of the child process does not matter.
        stdout = current.stdout.decode("utf-8", errors="replace")
        self.assertEqual(current.returncode, variant.exit_code, stdout)
        for marker in variant.markers:
            self.assertIn(marker, stdout)

    def test_registered_trees_and_variants_have_expected_cli_diagnostics(self) -> None:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            trees = list(self.workspace.knowledge_trees.items())
            if not trees:
                self.skipTest("workspace has no registered knowledge trees")
            variant_count = 0
            for subject, tree_path in trees:
                seed = yaml.safe_load(tree_path.read_text(encoding="utf-8"))
                points = load_knowledge_points(tree_path)
                for point in points:
                    for source in point.sources:
                        source_path = Path(source["path"])
                        if not source_path.is_absolute():
                            source_path = self.workspace.root / source_path
                        require_path(
                            self, source_path,
                            "restore the source file recorded by the knowledge tree",
                        )
                for index, variant in enumerate(_yaml_variants(seed)):
                    candidate = root / f"tree-{subject}-{index}.yaml"
                    candidate.write_text(
                        yaml.safe_dump(variant.document, allow_unicode=True, sort_keys=False),
                        encoding="utf-8",
                    )
                    common = [
                        str(candidate), "--workspace", str(WORKSPACE_PATH),
                        "--subject", subject, "--root", str(ROOT), *variant.extra_args,
                    ]
                    current = subprocess.run(
                        [sys.executable, str(ROOT / "tools/verify_tree.py"), *common],
                        cwd=ROOT, env=env, capture_output=True,
                    )
                    with self.subTest(subject=subject, variant=variant.name):
                        self._assert_tree_markers(variant, current)
                    variant_count += 1
            self.assertGreater(variant_count, 0)


if __name__ == "__main__":
    unittest.main()
