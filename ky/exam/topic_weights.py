"""M6 topic-weight aggregation from ``contracts/topic_weights.md``.

Public interface: :func:`aggregate_topic_weights`. The function combines a
batch manifest, coder output documents, and registered effective-tree nodes.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from ky.knowledge import KnowledgePoint, nearest_ancestor_with_scope
from ky.models import ContractError


_PAPER_SOURCE_RE = re.compile(r"^[a-z][a-z0-9]*$")


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractError("expected a mapping", path)
    if any(not isinstance(key, str) for key in value):
        raise ContractError("mapping keys must be strings", path)
    return value


def _sequence(value: Any, path: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ContractError("expected a list", path)
    return value


def _positive_weight(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractError("expected a positive number", path)
    weight = float(value)
    if not math.isfinite(weight) or weight <= 0:
        raise ContractError("expected a positive finite number", path)
    return weight


def _load_manifest_settings(
    manifest: Mapping[str, Any],
) -> tuple[list[str], dict[str, float], dict[str, str], Mapping[str, Any]]:
    coders_raw = _sequence(manifest.get("coders"), "coders")
    coders = list(coders_raw)
    if not coders or any(not isinstance(coder, str) or not coder for coder in coders):
        raise ContractError("coders must contain non-empty names", "coders")
    if len(coders) != len(set(coders)):
        raise ContractError("duplicate coder", "coders")

    confidence_raw = _mapping(manifest.get("confidence_weights"), "confidence_weights")
    confidence_weights = {
        name: _positive_weight(value, f"confidence_weights.{name}")
        for name, value in confidence_raw.items()
    }
    if not confidence_weights:
        raise ContractError("confidence weights must not be empty", "confidence_weights")

    rollup_raw = _mapping(manifest.get("topic_rollup"), "topic_rollup")
    topic_rollup: dict[str, str] = {}
    for subject, value in rollup_raw.items():
        if not isinstance(value, str) or value not in {"chapter", "none"}:
            raise ContractError("unknown topic rollup", f"topic_rollup.{subject}")
        topic_rollup[subject] = value
    metadata = _mapping(manifest.get("meta"), "meta")
    for field in ("policy", "caveat"):
        if not isinstance(metadata.get(field), str):
            raise ContractError("expected a string", f"meta.{field}")
    return coders, confidence_weights, topic_rollup, metadata


def _batch_identity(batch: Mapping[str, Any], index: int) -> tuple[str, int, str]:
    path = f"batches[{index}]"
    subject = batch.get("subject_id")
    year = batch.get("exam_year")
    source = batch.get("paper_source", "national")
    if not isinstance(subject, str) or not subject:
        raise ContractError("expected a subject ID", f"{path}.subject_id")
    if isinstance(year, bool) or not isinstance(year, int) or not 1000 <= year <= 9999:
        raise ContractError("expected a four-digit year", f"{path}.exam_year")
    if not isinstance(source, str) or not _PAPER_SOURCE_RE.fullmatch(source):
        raise ContractError("invalid paper source code", f"{path}.paper_source")
    return subject, year, source


def _question_key(subject: str, year: int, source: str, number: int) -> str:
    if source == "national":
        return f"{subject}-{year}-{number}"
    return f"{subject}-{source}-{year}-{number}"


def _read_entries(
    batch: Mapping[str, Any],
    index: int,
    coders: Sequence[str],
    coder_outputs: Mapping[str, Mapping[str, Any]],
) -> tuple[list[int], dict[str, dict[int, Mapping[str, Any]]]]:
    prefix = f"batches[{index}]"
    paths = _mapping(batch.get("coders"), f"{prefix}.coders")
    if set(paths) != set(coders):
        raise ContractError(
            "batch coder names must match manifest coders", f"{prefix}.coders"
        )
    entries_by_coder: dict[str, dict[int, Mapping[str, Any]]] = {}
    order_by_coder: dict[str, list[int]] = {}
    for coder in coders:
        indexed, order = _read_coder_entries(
            paths[coder], coder, batch.get("exam_year"), coder_outputs, prefix
        )
        entries_by_coder[coder] = indexed
        order_by_coder[coder] = order

    numbers = _validate_question_coverage(
        coders, entries_by_coder, order_by_coder, prefix
    )
    return numbers, entries_by_coder


def _read_coder_entries(
    relative_path: Any,
    coder: str,
    batch_year: Any,
    coder_outputs: Mapping[str, Mapping[str, Any]],
    batch_prefix: str,
) -> tuple[dict[int, Mapping[str, Any]], list[int]]:
    if not isinstance(relative_path, str) or not relative_path:
        raise ContractError("expected an output path", f"{batch_prefix}.coders.{coder}")
    document = coder_outputs.get(relative_path)
    if document is None:
        raise ContractError("coder output was not loaded", relative_path)
    document = _mapping(document, relative_path)
    document_meta = _mapping(document.get("meta"), f"{relative_path}.meta")
    if document_meta.get("coder") != coder:
        raise ContractError("coder metadata mismatch", f"{relative_path}.meta.coder")
    if document_meta.get("year") != batch_year:
        raise ContractError("coder year mismatch", f"{relative_path}.meta.year")
    entries = _sequence(document.get("entries"), f"{relative_path}.entries")
    indexed: dict[int, Mapping[str, Any]] = {}
    order: list[int] = []
    for entry_index, raw_entry in enumerate(entries):
        entry_path = f"{relative_path}.entries[{entry_index}]"
        entry = _mapping(raw_entry, entry_path)
        number = entry.get("number")
        if isinstance(number, bool) or not isinstance(number, int) or number < 1:
            raise ContractError(
                "expected a positive question number", f"{entry_path}.number"
            )
        if number in indexed:
            raise ContractError(f"duplicate question number {number}", entry_path)
        indexed[number] = entry
        order.append(number)
    return indexed, order


def _validate_question_coverage(
    coders: Sequence[str],
    entries_by_coder: Mapping[str, Mapping[int, Mapping[str, Any]]],
    order_by_coder: Mapping[str, list[int]],
    batch_prefix: str,
) -> list[int]:
    first = coders[0]
    numbers = order_by_coder[first]
    expected = set(numbers)
    if not numbers or expected != set(range(1, len(numbers) + 1)):
        raise ContractError(
            "question numbers must be contiguous from 1",
            f"{batch_prefix}.coders.{first}",
        )
    for coder in coders[1:]:
        actual = set(entries_by_coder[coder])
        if actual != expected:
            missing = sorted(expected - actual)
            extra = sorted(actual - expected)
            raise ContractError(
                f"question numbers missing={missing} extra={extra}",
                f"{batch_prefix}.coders.{coder}",
            )
    return numbers


def _question_votes(
    number: int,
    entries_by_coder: Mapping[str, Mapping[int, Mapping[str, Any]]],
    coders: Sequence[str],
    confidence_weights: Mapping[str, float],
    tree: Mapping[str, KnowledgePoint],
    batch_index: int,
) -> tuple[dict[str, float], dict[str, float]]:
    votes: dict[str, float] = {}
    for coder in coders:
        entry = entries_by_coder[coder][number]
        if "nodes" not in entry:
            raise ContractError(
                "required field is missing",
                f"batches[{batch_index}].{coder}.{number}.nodes",
            )
        nodes = entry.get("nodes", [])
        if nodes is None:
            nodes = []
        nodes = _sequence(nodes, f"batches[{batch_index}].{coder}.{number}.nodes")
        confidence = entry.get("confidence")
        if nodes and (
            not isinstance(confidence, str) or confidence not in confidence_weights
        ):
            raise ContractError(
                f"unknown confidence {confidence!r}",
                f"batches[{batch_index}].{coder}.{number}.confidence",
            )
        vote = confidence_weights[confidence] / len(nodes) if nodes else 0.0
        for node_id in nodes:
            if not isinstance(node_id, str):
                raise ContractError(
                    "node ID must be a string",
                    f"batches[{batch_index}].{coder}.{number}.nodes",
                )
            if node_id not in tree:
                raise ContractError(
                    f"coder {coder}, question {number}: node {node_id!r} "
                    "is not in the active tree",
                    f"batches[{batch_index}].coders.{coder}",
                )
            votes[node_id] = votes.get(node_id, 0.0) + vote
    total = sum(votes.values())
    if total == 0:
        raise ContractError(
            f"question {number} received no votes", f"batches[{batch_index}]"
        )
    raw_distribution = {node_id: value / total for node_id, value in votes.items()}
    rounded = {node_id: round(value, 3) for node_id, value in raw_distribution.items()}
    return raw_distribution, rounded


def _registered_batch(
    raw_batch: Any,
    index: int,
    identities: set[tuple[str, int, str]],
    topic_rollup: Mapping[str, str],
    knowledge_trees: Mapping[str, Mapping[str, KnowledgePoint]],
) -> tuple[Mapping[str, Any], str, int, str, Mapping[str, KnowledgePoint]]:
    batch = _mapping(raw_batch, f"batches[{index}]")
    subject, year, paper_source = _batch_identity(batch, index)
    identity = (subject, year, paper_source)
    if identity in identities:
        raise ContractError(f"duplicate batch {identity!r}", f"batches[{index}]")
    identities.add(identity)
    if subject not in topic_rollup:
        raise ContractError(
            "subject missing from topic_rollup", f"topic_rollup.{subject}"
        )
    if subject not in knowledge_trees:
        raise ContractError(
            "effective tree is not registered",
            f"reference.knowledge_trees.{subject}",
        )
    return batch, subject, year, paper_source, knowledge_trees[subject]


def _aggregate_questions(
    numbers: Sequence[int],
    subject: str,
    year: int,
    paper_source: str,
    entries_by_coder: Mapping[str, Mapping[int, Mapping[str, Any]]],
    coders: Sequence[str],
    confidence_weights: Mapping[str, float],
    tree: Mapping[str, KnowledgePoint],
    batch_index: int,
    per_question: dict[str, dict[str, dict[str, float]]],
) -> tuple[list[tuple[str, dict[str, float]]], int, int]:
    raw_questions: list[tuple[str, dict[str, float]]] = []
    single_node = 0
    spread = 0
    for number in numbers:
        question_key = _question_key(subject, year, paper_source, number)
        if question_key in per_question:
            raise ContractError(f"duplicate question key {question_key!r}", "batches")
        raw_distribution, rounded_distribution = _question_votes(
            number,
            entries_by_coder,
            coders,
            confidence_weights,
            tree,
            batch_index,
        )
        per_question[question_key] = {"distribution": rounded_distribution}
        raw_questions.append((question_key, raw_distribution))
        if len(rounded_distribution) == 1:
            single_node += 1
        else:
            spread += 1
    return raw_questions, single_node, spread


def _accumulate_topic_weights(
    raw_questions: Sequence[tuple[str, dict[str, float]]],
    subject: str,
    rollup: str,
    tree: Mapping[str, KnowledgePoint],
    batch_index: int,
    topic_weights: dict[str, dict[str, float]],
) -> None:
    subject_weights = topic_weights.setdefault(subject, {})
    for _, raw_distribution in raw_questions:
        for node_id, value in raw_distribution.items():
            summary_id = node_id
            if rollup == "chapter":
                ancestor = nearest_ancestor_with_scope(node_id, tree, "chapter")
                if ancestor is None:
                    raise ContractError(
                        f"node {node_id!r} has no chapter ancestor in subject {subject!r}",
                        f"batches[{batch_index}].coders",
                    )
                summary_id = ancestor
            subject_weights[summary_id] = subject_weights.get(summary_id, 0.0) + value


def _aggregate_batch(
    raw_batch: Any,
    index: int,
    identities: set[tuple[str, int, str]],
    topic_rollup: Mapping[str, str],
    knowledge_trees: Mapping[str, Mapping[str, KnowledgePoint]],
    coders: Sequence[str],
    confidence_weights: Mapping[str, float],
    coder_outputs: Mapping[str, Mapping[str, Any]],
    per_question: dict[str, dict[str, dict[str, float]]],
    topic_weights: dict[str, dict[str, float]],
) -> dict[str, Any]:
    batch, subject, year, paper_source, tree = _registered_batch(
        raw_batch, index, identities, topic_rollup, knowledge_trees
    )
    numbers, entries_by_coder = _read_entries(batch, index, coders, coder_outputs)
    raw_questions, single_node, spread = _aggregate_questions(
        numbers,
        subject,
        year,
        paper_source,
        entries_by_coder,
        coders,
        confidence_weights,
        tree,
        index,
        per_question,
    )
    _accumulate_topic_weights(
        raw_questions, subject, topic_rollup[subject], tree, index, topic_weights
    )
    return {
        "subject": subject,
        "year": year,
        "questions": len(numbers),
        "single_node": single_node,
        "spread": spread,
    }


def _ordered_topic_weights(
    topic_weights: Mapping[str, Mapping[str, float]],
) -> dict[str, dict[str, float]]:
    return {
        subject: dict(sorted(weights.items(), key=lambda item: (-item[1], item[0])))
        for subject, weights in topic_weights.items()
    }


def aggregate_topic_weights(
    manifest: Mapping[str, Any],
    coder_outputs: Mapping[str, Mapping[str, Any]],
    knowledge_trees: Mapping[str, Mapping[str, KnowledgePoint]],
) -> dict[str, Any]:
    """Aggregate registered coder batches without mutating any input."""
    manifest = _mapping(manifest, "$")
    coders, confidence_weights, topic_rollup, metadata = _load_manifest_settings(manifest)
    batches = _sequence(manifest.get("batches"), "batches")
    if not batches:
        raise ContractError("batches must not be empty", "batches")
    required_meta = {"policy", "caveat"}
    if set(metadata) != required_meta:
        raise ContractError("meta must contain policy and caveat", "meta")

    identities: set[tuple[str, int, str]] = set()
    topic_weights: dict[str, dict[str, float]] = {}
    batch_stats: list[dict[str, Any]] = []
    per_question: dict[str, dict[str, dict[str, float]]] = {}

    for index, raw_batch in enumerate(batches):
        batch_stats.append(
            _aggregate_batch(
                raw_batch,
                index,
                identities,
                topic_rollup,
                knowledge_trees,
                coders,
                confidence_weights,
                coder_outputs,
                per_question,
                topic_weights,
            )
        )

    output_meta = {
        "policy": metadata["policy"],
        "confidence_weights": dict(confidence_weights),
        "coders": list(coders),
        "batches": len(batches),
        "caveat": metadata["caveat"],
    }
    return {
        "meta": output_meta,
        "batch_stats": batch_stats,
        "topic_weight": _ordered_topic_weights(topic_weights),
        "per_question": per_question,
    }
