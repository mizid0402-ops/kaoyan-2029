"""M31 question selection from loaded sources; see ``contracts/question_bank.md`` and M33.

Public interfaces: ``load_review_question_sources`` and ``review_question_records``.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from ky.knowledge import learnable_tree, load_knowledge_points
from ky.models import ContractError
from ky.mastery import item_level
from ky.question_bank import (
    adapted_question_group_all_retired, question_id_from_ref, question_ref,
    select_adapted_question,
)
from ky.review.check_questions import (
    candidate_check_questions_loaded, load_check_question_sources,
)
from ky.workspace import Workspace


def load_review_question_sources(workspace: Workspace, items, completions) -> dict[str, Any]:
    """Load the trees and M24 references needed by the selected M31 items once."""
    outlines = {}
    for item in items:
        subject = item.subject_id
        if subject in outlines:
            continue
        points = load_knowledge_points(
            workspace.require(f"reference.knowledge_trees.{subject}")
        )
        grammar = workspace.subject_profiles[subject].tree_grammar
        if grammar is None:
            raise ContractError("tree grammar is not registered", f"subjects.{subject}")
        outlines[subject] = learnable_tree(points, grammar)
    passed = {
        review.review_id
        for event in completions
        for review in event.reviews
        if review.check == "past_question" and review.outcome == "correct"
    }
    subjects = {
        item.subject_id for item in items
        if item_level(item, item.review_id in passed) != "learned"
    }
    check_sources = (
        load_check_question_sources(workspace, tuple(sorted(subjects)))
        if subjects else {"per_question": {}, "indexes": {}}
    )
    check_sources["outlines"] = outlines
    return check_sources


def review_question_records(items, bank_path: Path | None, bank: tuple,
                            completions, check_sources,
                            outlines) -> list[dict[str, Any]]:
    past_passed: set[str] = set()
    references: dict[str, date] = {}
    past_used: dict[str, set[str]] = {}
    for event in completions:
        for review in event.reviews:
            if review.check == "past_question" and review.outcome == "correct":
                past_passed.add(review.review_id)
            if not review.question_ref:
                continue
            adapted_id = question_id_from_ref(review.question_ref)
            if adapted_id is not None:
                prior = references.get(adapted_id)
                if prior is None or event.day > prior:
                    references[adapted_id] = event.day
            elif review.check == "past_question":
                past_used.setdefault(review.review_id, set()).add(review.question_ref)
    ancestors = _ancestor_map(items, outlines)
    return [
        _question_record(item, bank_path, bank, references, past_used,
                         past_passed, ancestors.get(item.knowledge_point_id, ()),
                         check_sources)
        for item in items
    ]


def _question_record(item, bank_path, bank, references,
                     past_used, past_passed, ancestors, check_sources) -> dict[str, Any]:
    level = item_level(item, item.review_id in past_passed)
    record: dict[str, Any] = {
        "review_id": item.review_id, "knowledge_point_id": item.knowledge_point_id,
        "title": item.title, "level": level,
    }
    if level != "learned":
        subject = item.subject_id
        past = candidate_check_questions_loaded(
            subject, item.knowledge_point_id,
            check_sources["indexes"][subject], check_sources["per_question"],
            outline=check_sources["outlines"][subject],
            exclude=past_used.get(item.review_id, ()), ancestor_fallback=True,
        )
        if past["candidates"]:
            candidate = past["candidates"][0]
            record.update(question_level="past_question", check="past_question",
                          question_ref=candidate["question_id"], question=candidate)
            return record
        if bank_path is None:
            record["status"] = "未登记题库"
            return record
    elif bank_path is None:
        record.update(status="未登记题库",
                      generation_command=_adapted_question_command(item.knowledge_point_id))
        return record
    question = select_adapted_question(bank, item.knowledge_point_id, ancestors, references)
    if question is None:
        retired = adapted_question_group_all_retired(bank, item.knowledge_point_id, ancestors)
        if level == "learned":
            status = "缺改编题：先生成"
            if retired:
                status += "（该点改编题已全部停用）"
            record.update(status=status,
                          generation_command=_adapted_question_command(item.knowledge_point_id))
        else:
            # sol 282 M3: progressing needs a generation command when its adapted bank is retired.
            if retired and level == "progressing":
                record.update(
                    status="缺改编题：先生成（该点改编题已全部停用）",
                    generation_command=_adapted_question_command(item.knowledge_point_id),
                )
                return record
            record["status"] = "缺题（该点改编题已全部停用）" if retired else "缺题"
        return record
    record.update(question_level="adapted", check="exercise",
                  question_ref=question_ref(question["id"]), question=dict(question))
    return record


def _ancestor_map(items, by_subject) -> dict[str, tuple[str, ...]]:
    result = {}
    for item in items:
        outline = by_subject[item.subject_id]
        if item.knowledge_point_id not in outline.parents:
            raise ContractError("knowledge point is not in the effective tree",
                                item.knowledge_point_id)
        chain = []
        parent = outline.parents[item.knowledge_point_id]
        while parent is not None:
            chain.append(parent)
            parent = outline.parents[parent]
        result[item.knowledge_point_id] = tuple(chain)
    return result


def _adapted_question_command(point_id: str) -> str:
    return f"py -3.12 -m ky planner-input --kind adapted-questions --knowledge-point {point_id}"
