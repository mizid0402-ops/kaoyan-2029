"""M15 read-only projection builder; see ``contracts/projection.md`` and
``contracts/learning_state_projection.md``.

Public interface: ``build_projection(workspace, out=None)`` and
``ProjectionInUseError``. The builder reads registered inputs and atomically replaces its output.
Learning state is read through ``ky.projection.learning_state`` source ports.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ky.knowledge import (
    KnowledgePointError,
    KnowledgePoint,
    load_knowledge_points_from_text,
    parent_id,
)
from ky.models import ContractError, _require_mapping, load_yaml_text
from ky.projection.learning_state import LearningState, read_learning_state, write_learning_state
from ky.workspace import Workspace

__all__ = ["build_projection", "PROJECTION_SCHEMA_VERSION", "ProjectionInUseError"]

PROJECTION_SCHEMA_VERSION = 5

# Schema 4 stores each index's ``paper_source`` (contracts/exam_index.md §1); schema 5 adds
# FSRS memory columns to the learning-state projection.
_DEFAULT_PAPER_SOURCE = "national"
_PAPER_SOURCE_RE = re.compile(r"^[a-z][a-z0-9]*$")


class ProjectionInUseError(RuntimeError):
    """The existing projection could not be replaced, usually because it is being served."""


@dataclass(frozen=True)
class _RegisteredInput:
    path: Path
    content: bytes
    sha256: str


@dataclass(frozen=True)
class _SupplementaryInput:
    subject: str
    kind: str
    description: str
    tree: _RegisteredInput
    agreement: _RegisteredInput


@dataclass(frozen=True)
class _ProjectionInputs:
    effective: dict[str, _RegisteredInput]
    indexes: dict[str, tuple[_RegisteredInput, ...]]
    weights: _RegisteredInput
    vocabulary: _RegisteredInput
    supplementary: dict[str, _SupplementaryInput]
    hashes: dict[str, str]


@dataclass(frozen=True)
class _ProjectionRows:
    effective: list[tuple[Any, ...]]
    views: list[tuple[Any, ...]]
    supplementary: list[tuple[Any, ...]]
    questions: list[tuple[Any, ...]]
    question_weights: list[tuple[Any, ...]]
    topic_weights: list[tuple[Any, ...]]


def _subject_of(knowledge_point_id: str) -> str:
    return knowledge_point_id.split(".", 1)[0]


def _domain_of(workspace: Workspace, knowledge_point_id: str) -> str | None:
    parts = knowledge_point_id.split(".")
    profile = workspace.subject_profiles.get(_subject_of(knowledge_point_id))
    return parts[1] if len(parts) > 1 and profile and profile.domain_segment else None


def _read_registered_file(path: Path) -> _RegisteredInput:
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise ContractError(f"cannot read registered input: {exc}") from exc
    return _RegisteredInput(path, content, hashlib.sha256(content).hexdigest())


def _read_projection_inputs(workspace: Workspace) -> _ProjectionInputs:
    """Resolve every registered dependency, then read each unique file once."""
    effective_paths = {
        subject: workspace.require(f"reference.knowledge_trees.{subject}")
        for subject in sorted(workspace.knowledge_trees)
    }
    index_paths = {
        subject: workspace.require_all(f"reference.exam_indexes.{subject}")
        for subject in sorted(workspace.exam_indexes)
    }
    weights_path = workspace.require("reference.topic_weights")
    vocabulary_path = workspace.require("reference.vocabulary_db")
    supplementary_paths: dict[str, tuple[Path, Path]] = {}
    for name, view in sorted(workspace.supplementary.items()):
        if view.kind == "cross_year_tree":
            supplementary_paths[name] = (
                workspace.require(f"supplementary.{name}.files.tree"),
                workspace.require(f"supplementary.{name}.files.agreement"),
            )

    paths = set(effective_paths.values())
    paths.update(path for group in index_paths.values() for path in group)
    paths.update((weights_path, vocabulary_path))
    paths.update(path for pair in supplementary_paths.values() for path in pair)
    loaded: dict[Path, _RegisteredInput] = {}
    for path in sorted(paths, key=lambda item: item.relative_to(workspace.root).as_posix()):
        loaded[path] = _read_registered_file(path)

    effective = {subject: loaded[path] for subject, path in effective_paths.items()}
    indexes = {
        subject: tuple(loaded[path] for path in group)
        for subject, group in index_paths.items()
    }
    supplementary = {}
    for name, (tree_path, agreement_path) in supplementary_paths.items():
        view = workspace.supplementary[name]
        supplementary[name] = _SupplementaryInput(
            view.subject,
            view.kind,
            view.description,
            loaded[tree_path],
            loaded[agreement_path],
        )
    hashes = {
        path.relative_to(workspace.root).as_posix(): loaded[path].sha256
        for path in sorted(paths, key=lambda item: item.relative_to(workspace.root).as_posix())
    }
    return _ProjectionInputs(
        effective,
        indexes,
        loaded[weights_path],
        loaded[vocabulary_path],
        supplementary,
        hashes,
    )


def _input_text(source: _RegisteredInput, key: str) -> str:
    try:
        return source.content.decode("utf-8")
    except UnicodeError as exc:
        raise ContractError(f"registered input is not UTF-8: {exc}", key) from exc


def _read_tree(source: _RegisteredInput, key: str) -> tuple[KnowledgePoint, ...]:
    nodes = load_knowledge_points_from_text(
        _input_text(source, key),
        source=source.path.as_posix(),
    )
    ids = [node.knowledge_point_id for node in nodes]
    if len(ids) != len(set(ids)):
        raise ContractError("duplicate knowledge_point_id", key)
    return nodes


def _read_agreement(
    source: _RegisteredInput,
    key: str,
) -> dict[str, dict[str, Any]]:
    raw = load_yaml_text(_input_text(source, key), source=source.path.as_posix())
    doc = _require_mapping(raw, key)
    items = doc.get("items")
    if not isinstance(items, list):
        raise ContractError("expected a list", f"{key}.items")
    result: dict[str, dict[str, Any]] = {}
    for index, raw_item in enumerate(items):
        field = f"{key}.items[{index}]"
        item = _require_mapping(raw_item, field)
        point_id = item.get("knowledge_point_id")
        if not isinstance(point_id, str) or not point_id:
            raise ContractError("expected a non-empty string", f"{field}.knowledge_point_id")
        if point_id in result:
            raise ContractError("duplicate knowledge_point_id", f"{field}.knowledge_point_id")
        support = item.get("source_support")
        count = item.get("source_count")
        tag = item.get("evidence_tag")
        if support is not None and (
            isinstance(support, bool) or not isinstance(support, (int, float))
        ):
            raise ContractError("expected a number or null", f"{field}.source_support")
        if count is not None and (isinstance(count, bool) or not isinstance(count, int)):
            raise ContractError("expected an integer or null", f"{field}.source_count")
        if tag is not None and not isinstance(tag, str):
            raise ContractError("expected a string or null", f"{field}.evidence_tag")
        result[point_id] = {
            "source_support": support,
            "source_count": count,
            "evidence_tag": tag,
        }
    return result


def _json_document(source: _RegisteredInput, key: str) -> Any:
    try:
        return json.loads(_input_text(source, key))
    except (ContractError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot read valid JSON: {exc}", key) from exc


def _build_effective_rows(
    workspace: Workspace,
    sources: Mapping[str, _RegisteredInput],
) -> tuple[list[tuple[Any, ...]], dict[str, set[str]]]:
    rows: list[tuple[Any, ...]] = []
    subject_ids: dict[str, set[str]] = {}
    for subject, source in sources.items():
        key = f"reference.knowledge_trees.{subject}"
        nodes = _read_tree(source, key)
        ids = {node.knowledge_point_id for node in nodes}
        subject_ids[subject] = ids
        for node in nodes:
            point_id = node.knowledge_point_id
            if _subject_of(point_id) != subject:
                raise ContractError("knowledge point belongs to a different subject", key)
            parts = point_id.split(".")
            parent = parent_id(point_id, ids)
            rows.append((
                point_id,
                subject,
                _domain_of(workspace, point_id),
                node.scope,
                node.title,
                parent,
                len(parts) - 1,
                node.status,
                key,
            ))
    rows.sort(key=lambda row: row[0])
    return rows, subject_ids


def _build_supplementary_rows(
    workspace: Workspace,
    sources: Mapping[str, _SupplementaryInput],
    effective_ids: Mapping[str, set[str]],
) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]]]:
    view_rows: list[tuple[Any, ...]] = []
    rows: list[tuple[Any, ...]] = []
    for name, source in sources.items():
        tree_key = f"supplementary.{name}.files.tree"
        agreement_key = f"supplementary.{name}.files.agreement"
        nodes = _read_tree(source.tree, tree_key)
        supp_ids = {node.knowledge_point_id for node in nodes}
        if source.subject not in effective_ids:
            raise ContractError("supplementary subject has no registered effective tree", tree_key)
        for index, node in enumerate(nodes):
            if _subject_of(node.knowledge_point_id) != source.subject:
                path = f"{tree_key}.items[{index}].knowledge_point_id"
                raise ContractError("knowledge point belongs to a different subject", path)
        if not effective_ids[source.subject].issubset(supp_ids):
            raise ContractError(
                "effective tree IDs must be a subset of supplementary tree IDs",
                tree_key,
            )
        agreement = _read_agreement(source.agreement, agreement_key)
        if set(agreement) != supp_ids:
            raise ContractError(
                "agreement IDs must exactly match supplementary tree IDs",
                f"{agreement_key}.items",
            )
        view_rows.append((name, source.kind, source.subject, source.description))
        for node in nodes:
            point_id = node.knowledge_point_id
            parts = point_id.split(".")
            parent = parent_id(point_id, supp_ids)
            attrs = agreement[point_id]
            rows.append((
                name,
                point_id,
                source.subject,
                _domain_of(workspace, point_id),
                node.scope,
                node.title,
                parent,
                len(parts) - 1,
                node.status,
                int(point_id in effective_ids[source.subject]),
                attrs["source_support"],
                attrs["source_count"],
                attrs["evidence_tag"],
            ))
    view_rows.sort()
    rows.sort(key=lambda row: (row[0], row[1]))
    return view_rows, rows


def _optional_string(entry: Mapping[str, Any], name: str, field: str) -> str | None:
    value = entry.get(name)
    if value is not None and not isinstance(value, str):
        raise ContractError("expected a string or null", f"{field}.{name}")
    return value


def _optional_number(entry: Mapping[str, Any], name: str, field: str) -> int | float | None:
    value = entry.get(name)
    if value is not None and (
        isinstance(value, bool) or not isinstance(value, (int, float))
    ):
        raise ContractError("expected a number or null", f"{field}.{name}")
    if isinstance(value, float) and not math.isfinite(value):
        raise ContractError("expected a finite number", f"{field}.{name}")
    return value


def _knowledge_point_weight_rows(
    question_id: str,
    entry: Mapping[str, Any],
    field: str,
) -> list[tuple[Any, ...]]:
    weights = entry.get("knowledge_point_weights", {})
    if weights is None:
        weights = {}
    if not isinstance(weights, Mapping):
        raise ContractError("expected a mapping", f"{field}.knowledge_point_weights")
    rows = []
    for point_id, weight in weights.items():
        if not isinstance(point_id, str) or not point_id:
            raise ContractError(
                "expected a non-empty knowledge point ID",
                f"{field}.knowledge_point_weights",
            )
        if isinstance(weight, bool) or not isinstance(weight, (int, float)):
            raise ContractError(
                "expected a numeric weight",
                f"{field}.knowledge_point_weights.{point_id}",
            )
        value = float(weight)
        if not math.isfinite(value):
            raise ContractError(
                "expected a finite weight",
                f"{field}.knowledge_point_weights.{point_id}",
            )
        rows.append((question_id, point_id, value))
    return rows


def _exam_locator(
    entry: Mapping[str, Any],
    field: str,
) -> tuple[int | None, str | None]:
    locator = entry.get("locator", {})
    if locator is None:
        locator = {}
    if not isinstance(locator, Mapping):
        raise ContractError("expected a mapping", f"{field}.locator")
    page = locator.get("page")
    line = locator.get("line")
    for name, value in (("page", page), ("line", line)):
        if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
            raise ContractError("expected an integer or null", f"{field}.locator.{name}")
    paper_hash = locator.get("paper_sha256")
    if paper_hash is not None and not isinstance(paper_hash, str):
        raise ContractError("expected a string or null", f"{field}.locator.paper_sha256")
    return page, paper_hash


def _index_paper_source(document: Mapping[str, Any], key: str) -> str:
    source = document.get("paper_source", _DEFAULT_PAPER_SOURCE)
    if not isinstance(source, str) or not _PAPER_SOURCE_RE.fullmatch(source):
        raise ContractError("invalid paper source code", f"{key}.paper_source")
    return source


def _exam_entry_rows(
    entry: Mapping[str, Any],
    paper_source: str,
    field: str,
) -> tuple[tuple[Any, ...], list[tuple[Any, ...]]]:
    for name in ("question_id", "subject_id", "question_type"):
        value = entry.get(name)
        if not isinstance(value, str) or not value:
            raise ContractError("expected a non-empty string", f"{field}.{name}")
    for name in ("exam_year", "number"):
        value = entry.get(name)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ContractError("expected an integer", f"{field}.{name}")
    question_id = entry["question_id"]
    weight_rows = _knowledge_point_weight_rows(question_id, entry, field)
    page, paper_hash = _exam_locator(entry, field)
    row = (
        question_id,
        entry["exam_year"],
        entry["number"],
        entry["subject_id"],
        entry["question_type"],
        _optional_number(entry, "marks", field),
        _optional_string(entry, "answer", field),
        _optional_string(entry, "answer_confidence", field),
        _optional_string(entry, "knowledge_point_id", field),
        _optional_string(entry, "knowledge_point_status", field),
        len(weight_rows),
        page,
        paper_hash,
        paper_source,
    )
    return row, weight_rows


def _exam_document_rows(
    source: _RegisteredInput,
    key: str,
) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]]]:
    document = _json_document(source, key)
    if not isinstance(document, Mapping) or not isinstance(document.get("entries"), list):
        raise ContractError("expected an object with an entries list", key)
    paper_source = _index_paper_source(document, key)
    question_rows: list[tuple[Any, ...]] = []
    weight_rows: list[tuple[Any, ...]] = []
    for index, raw_entry in enumerate(document["entries"]):
        field = f"{key}.entries[{index}]"
        entry = _require_mapping(raw_entry, field)
        row, weights = _exam_entry_rows(entry, paper_source, field)
        question_rows.append(row)
        weight_rows.extend(weights)
    return question_rows, weight_rows


def _claim_question_ids(
    claimed: dict[str, str],
    question_rows: list[tuple[Any, ...]],
    origin: str,
    key: str,
) -> None:
    """Record which index file produced each ID; a repeat names both files.

    Without this check a repeated ID would surface as a SQLite primary-key error during the
    write instead of a contract error that says which registered files collide.
    """
    for index, row in enumerate(question_rows):
        question_id = row[0]
        first = claimed.get(question_id)
        if first is not None:
            raise ContractError(
                f"question_id {question_id!r} is produced by both {first} and {origin}",
                f"{key}.entries[{index}].question_id",
            )
        claimed[question_id] = origin


def _build_exam_rows(
    root: Path,
    indexes: Mapping[str, tuple[_RegisteredInput, ...]],
) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]]]:
    question_rows: list[tuple[Any, ...]] = []
    weight_rows: list[tuple[Any, ...]] = []
    claimed: dict[str, str] = {}
    for subject, sources in indexes.items():
        key = f"reference.exam_indexes.{subject}"
        for source in sources:
            rows, weights = _exam_document_rows(source, key)
            origin = source.path.relative_to(root).as_posix()
            _claim_question_ids(claimed, rows, origin, key)
            question_rows.extend(rows)
            weight_rows.extend(weights)
    question_rows.sort(key=lambda row: (row[1], row[2], row[0]))
    weight_rows.sort(key=lambda row: (row[0], row[1]))
    return question_rows, weight_rows


def _build_topic_weight_rows(source: _RegisteredInput) -> list[tuple[str, str, float]]:
    key = "reference.topic_weights"
    document = _json_document(source, key)
    if not isinstance(document, Mapping):
        raise ContractError("expected a mapping", key)
    blocks = document.get("topic_weight", {})
    if blocks is None:
        blocks = {}
    if not isinstance(blocks, Mapping):
        raise ContractError("expected a mapping", f"{key}.topic_weight")
    rows = []
    for subject, block in blocks.items():
        if not isinstance(subject, str) or not isinstance(block, Mapping):
            raise ContractError("expected a subject mapping", f"{key}.topic_weight.{subject}")
        for point_id, weight in block.items():
            if not isinstance(point_id, str) or isinstance(weight, bool):
                raise ContractError(
                    "expected a numeric weight",
                    f"{key}.topic_weight.{subject}.{point_id}",
                )
            try:
                value = float(weight)
            except (TypeError, ValueError) as exc:
                raise ContractError(
                    "expected a numeric weight",
                    f"{key}.topic_weight.{subject}.{point_id}",
                ) from exc
            if not math.isfinite(value):
                raise ContractError(
                    "expected a finite weight",
                    f"{key}.topic_weight.{subject}.{point_id}",
                )
            rows.append((subject, point_id, value))
    rows.sort()
    return rows


def _create_projection_tables(con: sqlite3.Connection) -> None:
    con.execute("""CREATE TABLE knowledge_points (
        knowledge_point_id TEXT PRIMARY KEY, subject_id TEXT NOT NULL, domain TEXT,
        scope TEXT NOT NULL, title TEXT, parent_id TEXT, depth INTEGER NOT NULL,
        tree_status TEXT NOT NULL, tree_source TEXT NOT NULL)""")
    con.execute("""CREATE TABLE supplementary_views (
        view_name TEXT PRIMARY KEY, kind TEXT NOT NULL, subject_id TEXT NOT NULL,
        description TEXT NOT NULL)""")
    con.execute("""CREATE TABLE supplementary_knowledge_points (
        view_name TEXT NOT NULL, knowledge_point_id TEXT NOT NULL, subject_id TEXT NOT NULL,
        domain TEXT, scope TEXT NOT NULL, title TEXT, parent_id TEXT, depth INTEGER NOT NULL,
        tree_status TEXT NOT NULL, is_effective INTEGER NOT NULL CHECK(is_effective IN (0,1)),
        source_support REAL, source_count INTEGER, evidence_tag TEXT,
        PRIMARY KEY (view_name, knowledge_point_id))""")
    con.execute("""CREATE TABLE exam_questions (
        question_id TEXT PRIMARY KEY, exam_year INTEGER NOT NULL, number INTEGER NOT NULL,
        subject_id TEXT NOT NULL, question_type TEXT NOT NULL, marks INTEGER, answer TEXT,
        answer_confidence TEXT, knowledge_point_id TEXT, knowledge_point_status TEXT,
        n_knowledge_points INTEGER NOT NULL, locator_page INTEGER, paper_sha256 TEXT,
        paper_source TEXT NOT NULL)""")
    con.execute("""CREATE TABLE question_knowledge_weights (
        question_id TEXT NOT NULL, knowledge_point_id TEXT NOT NULL, weight REAL NOT NULL,
        PRIMARY KEY (question_id, knowledge_point_id))""")
    con.execute("""CREATE TABLE topic_weights (
        subject_id TEXT NOT NULL, knowledge_point_id TEXT NOT NULL, topic_weight REAL NOT NULL,
        PRIMARY KEY (subject_id, knowledge_point_id))""")
    con.execute("CREATE TABLE projection_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")


def _insert_projection_rows(
    con: sqlite3.Connection,
    rows: _ProjectionRows,
) -> None:
    con.executemany("INSERT INTO knowledge_points VALUES (?,?,?,?,?,?,?,?,?)", rows.effective)
    con.executemany("INSERT INTO supplementary_views VALUES (?,?,?,?)", rows.views)
    con.executemany(
        "INSERT INTO supplementary_knowledge_points VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        rows.supplementary,
    )
    con.executemany(
        "INSERT INTO exam_questions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        rows.questions,
    )
    con.executemany(
        "INSERT INTO question_knowledge_weights VALUES (?,?,?)",
        rows.question_weights,
    )
    con.executemany("INSERT INTO topic_weights VALUES (?,?,?)", rows.topic_weights)


def _write_meta_and_views(
    con: sqlite3.Connection,
    workspace: Workspace,
    inputs: _ProjectionInputs,
    rows: _ProjectionRows,
    learning_state: LearningState,
) -> None:
    effective_by_subject = dict(
        sorted(Counter(row[1] for row in rows.effective).items())
    )
    meta = {
        "projection_schema_version": str(PROJECTION_SCHEMA_VERSION),
        "knowledge_points": str(len(rows.effective)),
        "supplementary_knowledge_points": str(len(rows.supplementary)),
        "exam_questions": str(len(rows.questions)),
        "question_knowledge_weights": str(len(rows.question_weights)),
        "topic_weights": str(len(rows.topic_weights)),
        "kp_by_scope": json.dumps(
            dict(sorted(Counter(row[3] for row in rows.effective).items())),
            sort_keys=True,
        ),
        "kp_by_subject": json.dumps(effective_by_subject, sort_keys=True),
        "kp_effective_by_subject": json.dumps(effective_by_subject, sort_keys=True),
        "kp_by_tree_status": json.dumps(
            dict(sorted(Counter(row[7] for row in rows.effective).items())),
            sort_keys=True,
        ),
        "q_by_year": json.dumps(
            dict(sorted(Counter(row[1] for row in rows.questions).items())),
            sort_keys=True,
        ),
        "inputs": json.dumps(inputs.hashes, sort_keys=True),
        "state_inputs": json.dumps(dict(learning_state.state_inputs), sort_keys=True),
        "freeze_events_latched": "1" if learning_state.freeze_events_latched else "0",
        "workspace_registry_sha256": workspace.sha256,
        "supplementary_views": json.dumps([row[0] for row in rows.views]),
        "content_notice": (
            "Read-only projection rebuilt from the structured materials. Knowledge-point counts "
            "carry tree_status; extracted trees must not be used for coverage or capability "
            "metrics. "
            "Supplementary-view nodes and agreement attributes record cross-year source support "
            "and are outside the effective scope for the current year."
        ),
    }
    con.executemany("INSERT INTO projection_meta VALUES (?,?)", sorted(meta.items()))
    con.execute("""CREATE VIEW v_knowledge_points_by_subject AS
        SELECT subject_id, scope, tree_status, COUNT(*) AS n FROM knowledge_points
        GROUP BY subject_id, scope, tree_status""")
    con.execute("""CREATE VIEW v_supplementary_not_effective AS
        SELECT * FROM supplementary_knowledge_points WHERE is_effective = 0""")
    con.execute("""CREATE VIEW v_question_coverage AS
        SELECT w.knowledge_point_id AS knowledge_point_id, COUNT(*) AS times_asked,
               COUNT(DISTINCT q.exam_year) AS years_seen
        FROM question_knowledge_weights w JOIN exam_questions q ON q.question_id = w.question_id
        GROUP BY w.knowledge_point_id""")


def _write_projection_database(
    output: Path,
    workspace: Workspace,
    inputs: _ProjectionInputs,
    rows: _ProjectionRows,
    learning_state: LearningState,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(output.suffix + ".building")
    tmp.unlink(missing_ok=True)
    con = sqlite3.connect(tmp)
    try:
        con.execute("PRAGMA foreign_keys = ON")
        _create_projection_tables(con)
        _insert_projection_rows(con, rows)
        write_learning_state(con, learning_state)
        _write_meta_and_views(con, workspace, inputs, rows, learning_state)
        con.commit()
    except Exception:
        con.close()
        tmp.unlink(missing_ok=True)
        raise
    else:
        con.close()
    try:
        os.replace(tmp, output)
    except PermissionError as exc:
        tmp.unlink(missing_ok=True)
        raise ProjectionInUseError(
            f"Cannot replace projection {output}. Stop the Datasette projection service "
            "before rebuilding; Windows keeps the served SQLite file open."
        ) from exc


def build_projection(workspace: Workspace, out: Path | None = None) -> dict:
    """Build and atomically replace the read-only projection.

    All required registered inputs are read once and parsed from the same bytes used for their
    SHA-256 values. Validation finishes before output creation, so a failed build preserves any
    existing projection. The vocabulary database is fingerprinted as a dependency but not queried.
    """
    inputs = _read_projection_inputs(workspace)
    effective_rows, effective_ids = _build_effective_rows(workspace, inputs.effective)
    view_rows, supplement_rows = _build_supplementary_rows(
        workspace,
        inputs.supplementary,
        effective_ids,
    )
    question_rows, question_weight_rows = _build_exam_rows(workspace.root, inputs.indexes)
    topic_weight_rows = _build_topic_weight_rows(inputs.weights)
    learning_state = read_learning_state(workspace)
    rows = _ProjectionRows(
        effective_rows,
        view_rows,
        supplement_rows,
        question_rows,
        question_weight_rows,
        topic_weight_rows,
    )
    output = Path(out) if out is not None else workspace.projection
    _write_projection_database(
        output,
        workspace,
        inputs,
        rows,
        learning_state,
    )
    return {
        "output": str(output),
        "bytes": output.stat().st_size,
        "knowledge_points": len(effective_rows),
        "supplementary_knowledge_points": len(supplement_rows),
        "exam_questions": len(question_rows),
        "question_knowledge_weights": len(question_weight_rows),
        "topic_weights": len(topic_weight_rows),
        "inputs": len(inputs.hashes),
    }
