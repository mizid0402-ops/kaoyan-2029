"""M24 check-question selection port contract."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml

from ky.models import ContractError
from ky.review.check_questions import candidate_check_questions
from ky.workspace import load_workspace


REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY = REPO_ROOT / "kaoyan.workspace.yaml"


def _temporary_workspace(
    directory: Path,
    entries: list[dict],
    *,
    missing: bool = False,
    topic_weights: dict | None = None,
) -> Path:
    source = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    subject = "math1"
    root = directory / "workspace"
    root.mkdir()
    source["subjects"] = {subject: source["subjects"][subject]}
    source["subjects"][subject]["tree_grammar"] = "named_chapters"
    source["reference"]["knowledge_trees"] = {
        subject: source["reference"]["knowledge_trees"][subject]
    }
    source["reference"]["exam_indexes"] = {subject: ["indexes/questions.json"]}
    source["reference"].pop("paper_shapes", None)
    source["reference"].pop("syllabus_versions", None)
    source["reference"]["topic_weights"] = "weights/topic_weights.json"
    tree_path = root / "trees/knowledge.yaml"
    tree_path.parent.mkdir()
    points = [
        ("math1.demo.chapter", "chapter"),
        ("math1.demo.content", "content"),
        ("math1.demo.requirements", "requirements"),
        ("math1.demo.requirements.item-01", "item"),
    ]
    tree_path.write_text(yaml.safe_dump([
        {"schema_version": 1, "knowledge_point_id": point_id, "title": title,
         "scope": "chapter" if title == "chapter" else "item", "status": "raw",
         "source_kind": "manual", "sources": [{"path": "synthetic.pdf", "sha256": "0" * 64,
                                                   "locator": {"page": 1}}]}
        for point_id, title in points
    ], allow_unicode=True), encoding="utf-8")
    source["supplementary"] = {}
    if not missing:
        index_path = root / "indexes/questions.json"
        index_path.parent.mkdir()
        index_path.write_text(json.dumps({"entries": entries}), encoding="utf-8")
    weights_path = root / "weights/topic_weights.json"
    weights_path.parent.mkdir()
    topic_document = {"topic_weight": {subject: {}}}
    if topic_weights is not None:
        topic_document["per_question"] = topic_weights
    weights_path.write_text(json.dumps(topic_document), encoding="utf-8")
    registry = root / "kaoyan.workspace.yaml"
    source["reference"]["knowledge_trees"] = {subject: "trees/knowledge.yaml"}
    registry.write_text(yaml.safe_dump(source, allow_unicode=True), encoding="utf-8")
    return registry


def _entry(question_id: str, year: int, number: int, weight: float) -> dict:
    return {
        "question_id": question_id,
        "subject_id": "math1",
        "exam_year": year,
        "number": number,
        "knowledge_point_weights": {"math1.demo.item": weight},
        "locator": {"page": year - 2000, "line": number},
    }


class CheckQuestionsPortContractTest(unittest.TestCase):
    def test_duplicate_question_id_in_one_index_is_rejected_at_second_entry(self) -> None:
        entry = _entry("q1", 2024, 1, 0.8)
        with tempfile.TemporaryDirectory() as temporary:
            registry = _temporary_workspace(Path(temporary), [entry, entry])
            with self.assertRaises(ContractError) as ctx:
                candidate_check_questions(load_workspace(registry), "math1.demo.item")
        self.assertEqual(
            ctx.exception.path,
            "reference.exam_indexes.math1.entries[1].question_id",
        )

    def test_missing_locator_is_rejected(self) -> None:
        entry = _entry("q1", 2024, 1, 0.8)
        entry.pop("locator")
        with tempfile.TemporaryDirectory() as temporary:
            registry = _temporary_workspace(Path(temporary), [entry])
            with self.assertRaises(ContractError) as ctx:
                candidate_check_questions(load_workspace(registry), "math1.demo.item")
        self.assertEqual(ctx.exception.path, "reference.exam_indexes.math1.entries[0].locator")

    def test_subject_must_match_registered_index(self) -> None:
        entry = _entry("q1", 2024, 1, 0.8)
        entry["subject_id"] = "eng1"
        with tempfile.TemporaryDirectory() as temporary:
            registry = _temporary_workspace(Path(temporary), [entry])
            with self.assertRaises(ContractError) as ctx:
                candidate_check_questions(load_workspace(registry), "math1.demo.item")
        self.assertEqual(
            ctx.exception.path,
            "reference.exam_indexes.math1.entries[0].subject_id",
        )

    def test_sort_exclude_and_limit(self) -> None:
        entries = [
            _entry("older-heavy", 2023, 8, 0.8),
            _entry("newer-light", 2025, 2, 0.4),
            _entry("same-weight-later", 2025, 4, 0.8),
            _entry("same-weight-earlier-number", 2025, 1, 0.8),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            registry = _temporary_workspace(Path(temporary), entries)
            workspace = load_workspace(registry)
            result = candidate_check_questions(
                workspace,
                "math1.demo.item",
                exclude={"same-weight-earlier-number"},
                limit=2,
            )
            explicit_default = candidate_check_questions(
                workspace, "math1.demo.item", exclude={"same-weight-earlier-number"},
                limit=2, ancestor_fallback=False,
            )
        self.assertEqual(
            [item["question_id"] for item in result["candidates"]],
            ["same-weight-later", "older-heavy"],
        )
        self.assertIsNone(result["fallback"])
        self.assertEqual(result["candidates"][0]["source"], "past_question")
        self.assertEqual(
            json.dumps(result, ensure_ascii=False, separators=(",", ":")),
            json.dumps(explicit_default, ensure_ascii=False, separators=(",", ":")),
        )

    def test_direct_knowledge_point_id_uses_unit_weight(self) -> None:
        entry = _entry("direct", 2024, 1, 0.3)
        entry["knowledge_point_id"] = "math1.demo.item"
        entry["knowledge_point_weights"] = {}
        with tempfile.TemporaryDirectory() as temporary:
            registry = _temporary_workspace(Path(temporary), [entry])
            result = candidate_check_questions(load_workspace(registry), "math1.demo.item")
        self.assertEqual(result["candidates"][0]["weight"], 1.0)

    def test_direct_mapping_uses_registered_per_question_weight(self) -> None:
        entry = _entry("direct", 2024, 1, 0.3)
        entry["knowledge_point_id"] = "math1.demo.item"
        entry["knowledge_point_weights"] = {}
        with tempfile.TemporaryDirectory() as temporary:
            registry = _temporary_workspace(
                Path(temporary),
                [entry],
                topic_weights={
                    "math1-2024-1": {
                        "distribution": {"math1.demo.item": 0.65}
                    }
                },
            )
            result = candidate_check_questions(load_workspace(registry), "math1.demo.item")
        self.assertEqual(result["candidates"][0]["weight"], 0.65)

    def test_no_linked_past_question_allows_ai_fallback(self) -> None:
        unrelated = _entry("other", 2024, 1, 1.0)
        unrelated["knowledge_point_weights"] = {"math1.other.item": 1.0}
        with tempfile.TemporaryDirectory() as temporary:
            registry = _temporary_workspace(Path(temporary), [unrelated])
            result = candidate_check_questions(load_workspace(registry), "math1.demo.item")
        self.assertEqual(result, {"candidates": [], "fallback": "ai_generated_allowed"})

    def test_ancestor_fallback_aggregates_descendant_weights_and_marks_node(self) -> None:
        target = "math1.demo.requirements.item-01"
        entry = _entry("chapter-content", 2025, 3, 0)
        entry["knowledge_point_weights"] = {
            "math1.demo.chapter": 0.25,
            "math1.demo.content": 0.35,
        }
        with tempfile.TemporaryDirectory() as temporary:
            registry = _temporary_workspace(Path(temporary), [entry])
            workspace = load_workspace(registry)
            default = candidate_check_questions(workspace, target)
            recovered = candidate_check_questions(workspace, target, ancestor_fallback=True)
        self.assertEqual(default, {"candidates": [], "fallback": "ai_generated_allowed"})
        self.assertEqual(recovered["matched_ancestor"], "math1.demo.chapter")
        self.assertEqual(recovered["candidates"][0]["weight"], 0.6)

    def test_ancestor_fallback_reaches_root_then_keeps_original_fallback(self) -> None:
        unrelated = _entry("unrelated", 2024, 1, 1.0)
        unrelated["knowledge_point_weights"] = {"math1.other.item": 1.0}
        with tempfile.TemporaryDirectory() as temporary:
            registry = _temporary_workspace(Path(temporary), [unrelated])
            result = candidate_check_questions(
                load_workspace(registry), "math1.demo.requirements.item-01",
                ancestor_fallback=True,
            )
        self.assertEqual(result, {"candidates": [], "fallback": "ai_generated_allowed"})

    def test_all_linked_questions_excluded_does_not_claim_no_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            registry = _temporary_workspace(Path(temporary), [_entry("done", 2024, 1, 1.0)])
            result = candidate_check_questions(
                load_workspace(registry), "math1.demo.item", exclude={"done"}
            )
        self.assertEqual(result, {"candidates": [], "fallback": None})

    def test_missing_registered_index_raises_contract_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            registry = _temporary_workspace(Path(temporary), [], missing=True)
            with self.assertRaises(ContractError):
                candidate_check_questions(load_workspace(registry), "math1.demo.item")

    def test_repository_registry_returns_sorted_linked_question(self) -> None:
        workspace = load_workspace(REGISTRY)
        point_id = None
        subject = None
        for candidate_subject in sorted(workspace.exam_indexes):
            for path in workspace.require_all(f"reference.exam_indexes.{candidate_subject}"):
                document = json.loads(path.read_text(encoding="utf-8"))
                for entry in document["entries"]:
                    mapped = entry.get("knowledge_point_weights", {}) or {}
                    direct = entry.get("knowledge_point_id")
                    if mapped:
                        point_id = next(iter(mapped))
                    elif direct:
                        point_id = direct
                    if point_id:
                        subject = candidate_subject
                        break
                if point_id:
                    break
            if point_id:
                break
        self.assertIsNotNone(point_id)
        result = candidate_check_questions(workspace, point_id)
        self.assertTrue(result["candidates"])
        order = [
            (-item["weight"], -item["exam_year"], item["number"], item["question_id"])
            for item in result["candidates"]
        ]
        self.assertEqual(order, sorted(order))
        self.assertTrue(all(item["subject_id"] == subject for item in result["candidates"]))


if __name__ == "__main__":
    unittest.main()
