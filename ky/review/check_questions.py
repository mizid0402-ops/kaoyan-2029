"""M24 check-question selection (``contracts/check_questions.md``).

Public interfaces: :func:`candidate_check_questions`,
:func:`load_check_question_sources`, and :func:`candidate_check_questions_loaded`.
The loaded entry calculates from caller-supplied indexes, weights, and tree.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from ky.models import ContractError
from ky.knowledge import load_knowledge_points, learnable_tree
from ky.workspace import Workspace


def _read_json(path: Path, key: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot read registered JSON: {exc}", key) from exc


def _subject_for(workspace: Workspace, knowledge_point_id: str) -> str:
    if not isinstance(knowledge_point_id, str) or not knowledge_point_id:
        raise ContractError("expected a non-empty knowledge point ID", "knowledge_point_id")
    subject = knowledge_point_id.split(".", 1)[0]
    if subject not in workspace.subject_profiles:
        raise ContractError("knowledge point subject is not registered", "knowledge_point_id")
    return subject


def _read_topic_weights(workspace: Workspace) -> Mapping[str, Any]:
    key = "reference.topic_weights"
    document = _read_json(workspace.require(key), key)
    if not isinstance(document, Mapping):
        raise ContractError("expected an object", key)
    per_question = document.get("per_question", {})
    if per_question is None:
        per_question = {}
    if not isinstance(per_question, Mapping):
        raise ContractError("expected a mapping", f"{key}.per_question")
    return per_question


def _candidate_weight(
    weights: Mapping[str, Any],
    direct: bool,
    per_question: Mapping[str, Any],
    subject_id: str,
    exam_year: int,
    number: int,
    knowledge_point_id: str,
    field: str,
) -> float | None:
    if knowledge_point_id in weights:
        value = weights[knowledge_point_id]
        weight_field = f"{field}.knowledge_point_weights.{knowledge_point_id}"
    elif direct:
        topic_key = f"{subject_id}-{exam_year}-{number}"
        topic_entry = per_question.get(topic_key)
        if topic_entry is None:
            return 1.0
        if not isinstance(topic_entry, Mapping):
            raise ContractError(
                "expected a mapping", f"reference.topic_weights.per_question.{topic_key}"
            )
        distribution = topic_entry.get("distribution", {})
        if not isinstance(distribution, Mapping):
            raise ContractError(
                "expected a mapping",
                f"reference.topic_weights.per_question.{topic_key}.distribution",
            )
        value = distribution.get(knowledge_point_id, 1.0)
        weight_field = (
            f"reference.topic_weights.per_question.{topic_key}.distribution."
            f"{knowledge_point_id}"
        )
    else:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ContractError("expected a finite numeric weight", weight_field)
    return float(value)


def _entry_candidate(
    entry: object,
    field: str,
    indexed_subject: str,
    knowledge_point_id: str,
    per_question: Mapping[str, Any],
    *,
    include_details: bool = False,
) -> dict[str, Any] | None:
    if not isinstance(entry, Mapping):
        raise ContractError("expected an object", field)
    weights = entry.get("knowledge_point_weights", {})
    if weights is None:
        weights = {}
    if not isinstance(weights, Mapping):
        raise ContractError("expected a mapping", f"{field}.knowledge_point_weights")
    question_id = entry.get("question_id")
    subject_id = entry.get("subject_id")
    exam_year = entry.get("exam_year")
    number = entry.get("number")
    if not isinstance(question_id, str) or not question_id:
        raise ContractError("expected a non-empty string", f"{field}.question_id")
    if not isinstance(subject_id, str) or not subject_id:
        raise ContractError("expected a non-empty string", f"{field}.subject_id")
    if subject_id != indexed_subject:
        raise ContractError("subject_id does not match the registered index subject",
                            f"{field}.subject_id")
    if isinstance(exam_year, bool) or not isinstance(exam_year, int):
        raise ContractError("expected an integer", f"{field}.exam_year")
    if isinstance(number, bool) or not isinstance(number, int):
        raise ContractError("expected an integer", f"{field}.number")
    locator = entry.get("locator")
    if not isinstance(locator, Mapping):
        raise ContractError("expected a mapping", f"{field}.locator")
    resolved = _candidate_weight(
        weights,
        entry.get("knowledge_point_id") == knowledge_point_id,
        per_question,
        subject_id,
        exam_year,
        number,
        knowledge_point_id,
        field,
    )
    if resolved is None:
        return None
    weight = resolved
    result = {
        "question_id": question_id,
        "subject_id": subject_id,
        "exam_year": exam_year,
        "number": number,
        "weight": float(weight),
        "locator": locator,
        "source": "past_question",
    }
    if include_details:
        for key in ("question_type", "marks"):
            if key in entry:
                result[key] = entry[key]
        if entry.get("answer_kind") == "letter":
            result["answer_kind"] = "letter"
            if "answer" in entry:
                result["answer"] = entry["answer"]
    return result


def _read_candidates_for_point(
    subject: str,
    entries: list[tuple[object, str]],
    knowledge_point_id: str,
    per_question: Mapping[str, Any],
    *,
    include_details: bool = False,
) -> list[dict[str, Any]]:
    candidates = []
    seen_question_ids: set[str] = set()
    for entry, field in entries:
        if not isinstance(entry, Mapping):
            raise ContractError("expected an object", field)
        question_id = entry.get("question_id")
        if isinstance(question_id, str) and question_id in seen_question_ids:
            raise ContractError("duplicate question_id in registered index",
                                f"{field}.question_id")
        candidate = _entry_candidate(
            entry, field, subject, knowledge_point_id, per_question,
            include_details=include_details,
        )
        if isinstance(question_id, str):
            seen_question_ids.add(question_id)
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def candidate_check_questions(
    workspace: Workspace,
    knowledge_point_id: str,
    *,
    exclude: Iterable[str] = (),
    limit: int | None = None,
    ancestor_fallback: bool = False,
    include_details: bool = False,
) -> dict[str, Any]:
    """Return deterministic linked past questions, without their question text."""
    if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit < 0):
        raise ContractError("expected a non-negative integer or null", "limit")
    if isinstance(exclude, str):
        raise ContractError("expected an iterable of question IDs", "exclude")
    if not isinstance(ancestor_fallback, bool):
        raise ContractError("expected a boolean", "ancestor_fallback")
    if not isinstance(include_details, bool):
        raise ContractError("expected a boolean", "include_details")
    excluded_items = tuple(exclude)
    if any(not isinstance(item, str) or not item for item in excluded_items):
        raise ContractError("expected non-empty question IDs", "exclude")

    subject = _subject_for(workspace, knowledge_point_id)
    sources = load_check_question_sources(workspace, (subject,))
    outline = None
    if ancestor_fallback and not _read_candidates_for_point(
            subject, sources["indexes"][subject], knowledge_point_id,
            sources["per_question"]):
        outline = _load_outline(workspace, subject)
    return candidate_check_questions_loaded(
        subject, knowledge_point_id, sources["indexes"][subject],
        sources["per_question"], outline=outline, exclude=excluded_items,
        limit=limit, ancestor_fallback=ancestor_fallback,
        include_details=include_details,
    )


def load_check_question_sources(workspace: Workspace, subjects) -> dict[str, Any]:
    """Read M24's shared weights and each requested subject index once."""
    per_question = _read_topic_weights(workspace)
    indexes = {subject: _read_index_entries(workspace, subject) for subject in subjects}
    return {"per_question": per_question, "indexes": indexes}


def candidate_check_questions_loaded(
    subject: str,
    knowledge_point_id: str,
    entries: list[tuple[object, str]],
    per_question: Mapping[str, Any],
    *,
    outline=None,
    exclude: Iterable[str] = (),
    limit: int | None = None,
    ancestor_fallback: bool = False,
    include_details: bool = False,
) -> dict[str, Any]:
    """Select M24 candidates using already loaded source documents (M33 §3)."""
    if not isinstance(subject, str) or not subject:
        raise ContractError("expected a subject ID", "subject")
    if not isinstance(knowledge_point_id, str) or not knowledge_point_id:
        raise ContractError("expected a non-empty knowledge point ID", "knowledge_point_id")
    if knowledge_point_id.split(".", 1)[0] != subject:
        raise ContractError("knowledge point subject does not match", "knowledge_point_id")
    if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit < 0):
        raise ContractError("expected a non-negative integer or null", "limit")
    if isinstance(exclude, str):
        raise ContractError("expected an iterable of question IDs", "exclude")
    if not isinstance(ancestor_fallback, bool):
        raise ContractError("expected a boolean", "ancestor_fallback")
    if not isinstance(include_details, bool):
        raise ContractError("expected a boolean", "include_details")
    excluded_items = tuple(exclude)
    if any(not isinstance(item, str) or not item for item in excluded_items):
        raise ContractError("expected non-empty question IDs", "exclude")
    excluded = set(excluded_items)

    candidates = _read_candidates_for_point(
        subject, entries, knowledge_point_id, per_question,
        include_details=include_details,
    )
    matched_ancestor = None
    has_linked_questions = bool(candidates)
    if ancestor_fallback and not candidates:
        if outline is None:
            raise ContractError("ancestor fallback requires a loaded tree", "outline")
        candidates, matched_ancestor = _read_ancestor_candidates_loaded(
            subject, knowledge_point_id, per_question, entries, outline,
            include_details=include_details,
        )
        has_linked_questions = bool(candidates)
    candidates = [item for item in candidates if item["question_id"] not in excluded]
    candidates.sort(
        key=lambda item: (
            -item["weight"], -item["exam_year"], item["number"], item["question_id"]
        )
    )
    if limit is not None:
        candidates = candidates[:limit]
    result: dict[str, Any] = {"candidates": candidates, "fallback": None}
    if matched_ancestor is not None:
        result["matched_ancestor"] = matched_ancestor
    if not has_linked_questions:
        result["fallback"] = "ai_generated_allowed"
    return result


def _load_outline(workspace: Workspace, subject: str):
    tree_path = workspace.require(f"reference.knowledge_trees.{subject}")
    try:
        points = load_knowledge_points(tree_path)
        grammar = workspace.subject_profiles[subject].tree_grammar
        if grammar is None:
            raise ContractError("tree grammar is not registered", f"subjects.{subject}")
        return learnable_tree(points, grammar)
    except (ValueError, KeyError) as exc:
        raise ContractError(str(exc), f"reference.knowledge_trees.{subject}") from exc


def _read_ancestor_candidates_loaded(
    subject: str,
    knowledge_point_id: str,
    per_question: Mapping[str, Any],
    entries: list[tuple[object, str]],
    outline,
    *,
    include_details: bool = False,
) -> tuple[list[dict[str, Any]], str | None]:
    if knowledge_point_id not in outline.points_by_id:
        raise ContractError("knowledge point is not in the effective tree", "knowledge_point_id")

    current = outline.parents[knowledge_point_id]
    while current is not None:
        descendants = _descendants(current, outline.children)
        candidates = _read_candidates_for_ids(
            subject, entries, frozenset({current, *descendants}), per_question,
            include_details=include_details,
        )
        if candidates:
            return candidates, current
        current = outline.parents[current]
    return [], None


def _descendants(point_id: str, children: Mapping[str, tuple[str, ...]]) -> set[str]:
    found: set[str] = set()
    pending = list(children.get(point_id, ()))
    while pending:
        child = pending.pop()
        if child in found:
            continue
        found.add(child)
        pending.extend(children.get(child, ()))
    return found


def _read_candidates_for_ids(
    subject: str,
    entries: list[tuple[Mapping[str, Any], str]],
    point_ids: frozenset[str],
    per_question: Mapping[str, Any],
    *,
    include_details: bool = False,
) -> list[dict[str, Any]]:
    candidates = []
    for entry, field in entries:
        candidate = _aggregate_entry_candidate(
            entry, field, subject, point_ids, per_question,
            include_details=include_details,
        )
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def _read_index_entries(
    workspace: Workspace, subject: str,
) -> list[tuple[object, str]]:
    key = f"reference.exam_indexes.{subject}"
    result = []
    for path in workspace.require_all(key):
        document = _read_json(path, key)
        if not isinstance(document, Mapping) or not isinstance(document.get("entries"), list):
            raise ContractError("expected an object with an entries list", key)
        for index, entry in enumerate(document["entries"]):
            field = f"{key}.entries[{index}]"
            result.append((entry, field))
    return result


def _aggregate_entry_candidate(
    entry: Mapping[str, Any],
    field: str,
    subject: str,
    point_ids: frozenset[str],
    per_question: Mapping[str, Any],
    *,
    include_details: bool = False,
) -> dict[str, Any] | None:
    weights = entry.get("knowledge_point_weights", {})
    if weights is None:
        weights = {}
    if not isinstance(weights, Mapping):
        raise ContractError("expected a mapping", f"{field}.knowledge_point_weights")
    question_id = entry.get("question_id")
    entry_subject = entry.get("subject_id")
    exam_year = entry.get("exam_year")
    number = entry.get("number")
    if not isinstance(question_id, str) or not question_id:
        raise ContractError("expected a non-empty string", f"{field}.question_id")
    if entry_subject != subject:
        raise ContractError("subject_id does not match the registered index subject",
                            f"{field}.subject_id")
    if isinstance(exam_year, bool) or not isinstance(exam_year, int):
        raise ContractError("expected an integer", f"{field}.exam_year")
    if isinstance(number, bool) or not isinstance(number, int):
        raise ContractError("expected an integer", f"{field}.number")
    locator = entry.get("locator")
    if not isinstance(locator, Mapping):
        raise ContractError("expected a mapping", f"{field}.locator")
    total = 0.0
    found = False
    for point_id in sorted(point_ids):
        resolved = _candidate_weight(
            weights, entry.get("knowledge_point_id") == point_id, per_question,
            subject, exam_year, number, point_id, field,
        )
        if resolved is not None:
            found = True
            total += resolved
    if not found:
        return None
    if not math.isfinite(total):
        raise ContractError("aggregated weight must be finite", f"{field}.knowledge_point_weights")
    result = {
        "question_id": question_id,
        "subject_id": subject,
        "exam_year": exam_year,
        "number": number,
        "weight": total,
        "locator": locator,
        "source": "past_question",
    }
    if include_details:
        for key in ("question_type", "marks"):
            if key in entry:
                result[key] = entry[key]
        if entry.get("answer_kind") == "letter":
            result["answer_kind"] = "letter"
            if "answer" in entry:
                result["answer"] = entry["answer"]
    return result
