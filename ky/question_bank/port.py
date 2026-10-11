"""M31 adapted-question bank (``contracts/question_bank.md``).

Public interfaces validate, read, append, and select one-question YAML files;
they also create adapted-question input packages and apply staged submissions.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Iterable, Mapping
from datetime import date
from pathlib import Path
from typing import Any

from ky.knowledge import KnowledgePointError, learnable_tree, load_knowledge_points
from ky.models import ContractError, load_yaml_text
from ky.planner.port import canonical_json_bytes
from ky.review.check_questions import candidate_check_questions
from ky.storage.atomic import replace_bytes
from ky.workspace import Workspace, load_workspace

_FIELDS = frozenset({
    "schema_version", "id", "knowledge_point_id", "difficulty", "basis", "based_on",
    "stem", "choices", "answer", "explanation", "validation", "created_by", "created_on",
})
_REQUIRED_FIELDS = _FIELDS - {"choices", "explanation"}
_ACTOR = re.compile(r"^ai:[a-z0-9][a-z0-9._-]*$")
_HASH = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^qb-(?P<point>[a-z][a-z0-9]*(?:\.[a-z0-9-]+)+)-(?P<seq>(?:0[1-9]|[1-9][0-9]))$")
_TEMP_NAME = re.compile(r"^\.(?P<target>qb-.+)\.(?P<random>[a-z0-9_]{8})\.tmp$")


def validate_question(raw: object, *, source: str = "<question>") -> dict[str, Any]:
    """Validate one stored M31 question mapping and return a plain copy."""
    if not isinstance(source, str) or not source:
        raise ContractError("source must be a non-empty string", "source")
    if not isinstance(raw, Mapping):
        raise ContractError("expected a mapping", source)
    if any(not isinstance(key, str) for key in raw):
        raise ContractError("question keys must be strings", source)
    unknown = set(raw) - _FIELDS
    missing = _REQUIRED_FIELDS - set(raw)
    if unknown:
        key = sorted(unknown)[0]
        raise ContractError("unknown field", f"{source}.{key}")
    if missing:
        key = sorted(missing)[0]
        raise ContractError("required field is missing", f"{source}.{key}")
    if type(raw["schema_version"]) is not int or raw["schema_version"] != 1:
        raise ContractError("schema_version must be integer 1", f"{source}.schema_version")
    point_id = _text(raw["knowledge_point_id"], f"{source}.knowledge_point_id")
    match = _ID.fullmatch(raw["id"]) if isinstance(raw["id"], str) else None
    if match is None or match.group("point") != point_id:
        raise ContractError("id must be qb-<knowledge point>-<two digit sequence>",
                            f"{source}.id")
    if raw["difficulty"] != "basic":
        raise ContractError("difficulty must be basic", f"{source}.difficulty")
    if not isinstance(raw["basis"], str) or raw["basis"] not in {
        "past_questions", "syllabus",
    }:
        raise ContractError("basis must be past_questions or syllabus", f"{source}.basis")
    based_on = raw["based_on"]
    if (not isinstance(based_on, list) or any(not isinstance(item, str) or not item
                                               for item in based_on)):
        raise ContractError("based_on must be a list of question IDs", f"{source}.based_on")
    if raw["basis"] == "past_questions" and not based_on:
        raise ContractError("past_questions requires based_on", f"{source}.based_on")
    if raw["basis"] == "syllabus" and based_on:
        raise ContractError("syllabus requires an empty based_on list", f"{source}.based_on")
    _text(raw["stem"], f"{source}.stem")
    if "choices" in raw and (not isinstance(raw["choices"], list) or any(
        not isinstance(choice, str) or not choice for choice in raw["choices"]
    )):
        raise ContractError("choices must be a list of non-empty strings", f"{source}.choices")
    _text(raw["answer"], f"{source}.answer")
    if "explanation" in raw:
        _text(raw["explanation"], f"{source}.explanation")
    if raw["validation"] != "guided":
        raise ContractError("validation must be guided", f"{source}.validation")
    actor = _text(raw["created_by"], f"{source}.created_by")
    if not _ACTOR.fullmatch(actor):
        raise ContractError("created_by must match the M19 AI actor rule", f"{source}.created_by")
    created_on = _date(raw["created_on"], f"{source}.created_on")
    # AI drafts write unquoted YAML dates (sol 268 F2); store one ISO-string form.
    return {**raw, "created_on": created_on.isoformat()}


def _text(value: object, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError("expected a non-empty string", path)
    return value


def _date(value: object, path: str) -> date:
    if type(value) is date:
        return value
    if not isinstance(value, str):
        raise ContractError("expected an ISO date (YYYY-MM-DD)", path)
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ContractError("expected an ISO date (YYYY-MM-DD)", path) from exc
    if parsed.isoformat() != value:
        raise ContractError("expected an ISO date (YYYY-MM-DD)", path)
    return parsed


def _read_yaml(path: Path) -> object:
    try:
        return load_yaml_text(path.read_text(encoding="utf-8"), source=path.as_posix())
    except (OSError, UnicodeError, ContractError) as exc:
        raise ContractError(f"cannot read question: {exc}", path.as_posix()) from exc


QUESTION_REF_PREFIX = "qb:"


def question_ref(question_id: str) -> str:
    """Return the completion-event ``question_ref`` for an adapted question (§1)."""
    if not isinstance(question_id, str) or not _ID.fullmatch(question_id):
        raise ContractError("expected an adapted question id", "question_id")
    return QUESTION_REF_PREFIX + question_id


def question_id_from_ref(ref: str) -> str | None:
    """Return the adapted question id named by a ``qb:`` reference, else ``None``."""
    if not isinstance(ref, str) or not ref.startswith(QUESTION_REF_PREFIX):
        return None
    question_id = ref[len(QUESTION_REF_PREFIX):]
    return question_id if _ID.fullmatch(question_id) else None


def load_question_bank(root: str | Path) -> tuple[dict[str, Any], ...]:
    """Read and validate each question file in a bank directory."""
    try:
        bank = Path(root)
    except TypeError as exc:
        raise ContractError("root must be a path", "root") from exc
    if not bank.is_dir():
        if bank.exists():
            raise ContractError("expected a directory", bank.as_posix())
        return ()
    questions = []
    seen: set[str] = set()
    paths = []
    retired_paths = []
    for path in sorted(bank.rglob("*")):
        if path.is_dir():
            if len(path.relative_to(bank).parts) != 1:
                raise ContractError("question bank directories must be one level deep",
                                    path.as_posix())
            continue
        if len(path.relative_to(bank).parts) != 2:
            raise ContractError("unexpected file in question bank", path.as_posix())
        if _is_question_temp(path):
            continue
        if path.suffix != ".yaml":
            raise ContractError("unexpected file in question bank", path.as_posix())
        if path.name.endswith(".retired.yaml"):
            retired_paths.append(path)
        else:
            paths.append(path)
    for path in paths:
        question = validate_question(_read_yaml(path), source=path.as_posix())
        if path.stem != question["id"]:
            raise ContractError("filename must match id", path.as_posix())
        if path.parent.name != question["knowledge_point_id"]:
            raise ContractError("directory must match knowledge_point_id", path.as_posix())
        if question["id"] in seen:
            raise ContractError("duplicate question id", f"{path}.id")
        seen.add(question["id"])
        questions.append(question)
    by_id = {question["id"]: question for question in questions}
    for path in retired_paths:
        retirement = _validate_retirement(_read_yaml(path), path)
        question = by_id.get(retirement["id"])
        if question is None:
            raise ContractError("retirement has no matching question", path.as_posix())
        expected_name = f"{retirement['id']}.retired.yaml"
        if path.name != expected_name or path.parent.name != question["knowledge_point_id"]:
            raise ContractError("retirement filename must match question id", path.as_posix())
        if "retired" in question:
            raise ContractError("duplicate retirement record", path.as_posix())
        question["retired"] = True
        question["retirement"] = retirement
    return tuple(questions)


def _is_question_temp(path: Path) -> bool:
    """Skip only M31 writer temp names (sol 282 M4), including retire records."""
    match = _TEMP_NAME.fullmatch(path.name)
    if match is None:
        return False
    target = match.group("target")
    if target.endswith(".retired.yaml"):
        question_id = target[:-len(".retired.yaml")]
    elif target.endswith(".yaml"):
        question_id = target[:-len(".yaml")]
    else:
        return False
    question_match = _ID.fullmatch(question_id)
    return question_match is not None and path.parent.name == question_match.group("point")


def append_question(root: str | Path, raw: object) -> Path:
    """Publish one immutable question using a same-directory hard link."""
    question = validate_question(raw)
    try:
        bank = Path(root)
    except TypeError as exc:
        raise ContractError("root must be a path", "root") from exc
    target = _preflight_question(bank, question)
    folder = target.parent
    folder.mkdir(parents=True, exist_ok=True)
    _ensure_child(folder, bank, "knowledge point directory")
    expected = target.stem
    _ensure_child(target, folder, "question target")
    data = _yaml_bytes(question)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=folder
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
        reread = validate_question(_read_yaml(temporary), source=temporary.as_posix())
        if reread != question:
            raise ContractError("question changed during serialization", temporary.as_posix())
        try:
            os.link(temporary, target)
        except FileExistsError as exc:
            raise ContractError("question file already exists", target.as_posix()) from exc
        return target
    finally:
        temporary.unlink(missing_ok=True)


def _preflight_question(bank: Path, question: Mapping[str, Any]) -> Path:
    """Check sequence and capacity from one parsed M31 bank snapshot (sol 282 M5/M6)."""
    questions = load_question_bank(bank)
    point_id = question["knowledge_point_id"]
    prior_sequences = [
        int(_ID.fullmatch(item["id"]).group("seq"))
        for item in questions
        if item["knowledge_point_id"] == point_id
    ]
    active_count = sum(
        1 for item in questions
        if item["knowledge_point_id"] == point_id and not item.get("retired", False)
    )
    if active_count >= 9:
        raise ContractError(
            "knowledge point already has nine questions", (bank / point_id).as_posix(),
        )
    expected = f"qb-{point_id}-{max(prior_sequences, default=0) + 1:02d}"
    if question["id"] != expected:
        raise ContractError(f"expected next question id {expected}", "id")
    return bank / point_id / f"{expected}.yaml"


def _yaml_bytes(value: Mapping[str, Any]) -> bytes:
    import yaml

    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False).encode("utf-8")


def _validate_retirement(raw: object, path: Path) -> dict[str, Any]:
    fields = {"schema_version", "id", "reason", "retired_on"}
    if not isinstance(raw, Mapping) or set(raw) != fields:
        raise ContractError("retirement must contain the required fields", path.as_posix())
    if type(raw["schema_version"]) is not int or raw["schema_version"] != 1:
        raise ContractError("schema_version must be integer 1", f"{path}.schema_version")
    question_id = _text(raw["id"], f"{path}.id")
    if not _ID.fullmatch(question_id):
        raise ContractError("expected an adapted question id", f"{path}.id")
    reason = _text(raw["reason"], f"{path}.reason")
    retired_on = _date(raw["retired_on"], f"{path}.retired_on").isoformat()
    return {"schema_version": 1, "id": question_id, "reason": reason,
            "retired_on": retired_on}


def retire_question(
    root: str | Path, question_id: str, reason: str, retired_on: date | str,
    *, dry_run: bool = False,
) -> Path:
    """Write a validated retirement record once, preserving the question file."""
    if not isinstance(question_id, str) or not _ID.fullmatch(question_id):
        raise ContractError("expected an adapted question id", "question")
    reason = _text(reason, "reason")
    retired_on = _date(retired_on, "date").isoformat()
    if type(dry_run) is not bool:
        raise ContractError("dry_run must be a boolean", "dry_run")
    try:
        bank = Path(root)
    except TypeError as exc:
        raise ContractError("root must be a path", "root") from exc
    questions = load_question_bank(bank)
    question = next((item for item in questions if item["id"] == question_id), None)
    if question is None:
        raise ContractError("question does not exist", "question")
    folder = bank / question["knowledge_point_id"]
    target = folder / f"{question_id}.retired.yaml"
    if question.get("retired", False):
        raise ContractError("question is already retired", target.as_posix())
    _ensure_child(folder, bank, "knowledge point directory")
    _ensure_child(target, folder, "retirement target")
    record = {"schema_version": 1, "id": question_id, "reason": reason,
              "retired_on": retired_on}
    if dry_run:
        return target
    data = _yaml_bytes(record)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=folder
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
        reread = _validate_retirement(_read_yaml(temporary), temporary)
        if reread != record:
            raise ContractError("retirement changed during serialization", temporary.as_posix())
        try:
            os.link(temporary, target)
        except FileExistsError as exc:
            raise ContractError("question is already retired", target.as_posix()) from exc
        return target
    finally:
        temporary.unlink(missing_ok=True)


def _ensure_child(path: Path, parent: Path, label: str) -> None:
    try:
        resolved_parent = parent.resolve(strict=False)
        resolved_path = path.resolve(strict=False)
        resolved_path.relative_to(resolved_parent)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ContractError(f"{label} resolves outside its parent", path.as_posix()) from exc


def select_adapted_question(
    questions: Iterable[Mapping[str, Any]], point_id: str,
    ancestors: Iterable[str], uses: Mapping[str, date],
) -> Mapping[str, Any] | None:
    """Choose the nearest-node unused question, then the least recently used."""
    if not isinstance(point_id, str) or not point_id:
        raise ContractError("point_id must be a non-empty string", "point_id")
    if isinstance(ancestors, str):
        raise ContractError("ancestors must be an iterable of IDs", "ancestors")
    if not isinstance(ancestors, Iterable):
        raise ContractError("ancestors must be an iterable of IDs", "ancestors")
    if not isinstance(uses, Mapping):
        raise ContractError("uses must map question IDs to dates", "uses")
    if any(
        not isinstance(question_id, str) or not isinstance(used_on, date)
        for question_id, used_on in uses.items()
    ):
        raise ContractError("uses must map question IDs to dates", "uses")
    ancestors = tuple(ancestors)
    if any(not isinstance(ancestor, str) or not ancestor for ancestor in ancestors):
        raise ContractError("ancestors must be non-empty IDs", "ancestors")
    by_point: dict[str, list[Mapping[str, Any]]] = {}
    for question in questions:
        if not isinstance(question, Mapping):
            raise ContractError("questions must be mappings", "questions")
        if not isinstance(question.get("knowledge_point_id"), str) or not isinstance(
            question.get("id"), str
        ):
            raise ContractError("question requires id and knowledge_point_id", "questions")
        by_point.setdefault(question["knowledge_point_id"], []).append(question)
    for candidate_point in (point_id, *ancestors):
        populated = by_point.get(candidate_point, ())
        if not populated:
            continue
        # The nearest populated group decides (§5 / §6a, sol 272 F1): when all of its
        # questions are retired the point needs new questions, not an ancestor's.
        group = sorted(
            (item for item in populated if not item.get("retired", False)),
            key=lambda item: item["id"],
        )
        if not group:
            return None
        unused = [item for item in group if item["id"] not in uses]
        if unused:
            return unused[0]
        return min(group, key=lambda item: (uses[item["id"]], item["id"]))
    return None


def adapted_question_group_all_retired(
    questions: Iterable[Mapping[str, Any]], point_id: str, ancestors: Iterable[str],
) -> bool:
    """Return whether the nearest populated own/ancestor group is entirely retired."""
    by_point: dict[str, list[Mapping[str, Any]]] = {}
    for question in questions:
        if not isinstance(question, Mapping):
            raise ContractError("questions must be mappings", "questions")
        point = question.get("knowledge_point_id")
        if not isinstance(point, str):
            raise ContractError("question requires knowledge_point_id", "questions")
        by_point.setdefault(point, []).append(question)
    for point in (point_id, *tuple(ancestors)):
        group = by_point.get(point, ())
        if group:
            return all(item.get("retired", False) for item in group)
    return False


def adapted_question_input_data(
    workspace: Workspace, knowledge_point_id: str,
) -> tuple[dict[str, Any], str]:
    """Build the deterministic M31 AI input package without writing it."""
    if not isinstance(workspace, Workspace):
        raise ContractError("expected Workspace", "workspace")
    point = _text(knowledge_point_id, "knowledge_point_id")
    subject = point.split(".", 1)[0]
    try:
        tree = load_knowledge_points(workspace.require(f"reference.knowledge_trees.{subject}"))
        grammar = workspace.subject_profiles[subject].tree_grammar
        if grammar is None:
            raise ContractError("tree grammar is not registered", f"subjects.{subject}")
        outline = learnable_tree(tree, grammar)
    except (ValueError, KeyError, KnowledgePointError) as exc:
        raise ContractError(str(exc), f"reference.knowledge_trees.{subject}") from exc
    if point not in outline.points_by_id or point in outline.trackers:
        raise ContractError("knowledge point must be learnable", "knowledge_point_id")
    chain = []
    current: str | None = point
    while current is not None:
        record = outline.points_by_id[current]
        chain.append({"id": current, "title": record.title})
        current = outline.parents[current]
    past = candidate_check_questions(
        workspace, point, ancestor_fallback=True, include_details=True,
    )
    basis = "past_questions" if past["candidates"] else "syllabus"
    descendants = _point_descendants(point, outline.children)
    syllabus = [
        {"id": item_id, "title": outline.points_by_id[item_id].title}
        for item_id in (point, *sorted(descendants))
    ]
    package = {
        "schema_version": 1,
        "kind": "adapted_questions_input",
        "knowledge_point": {"id": point, "title": outline.points_by_id[point].title,
                            "tree_path": list(reversed(chain))},
        "syllabus": syllabus,
        "basis": basis,
        "candidates": past["candidates"],
    }
    return package, hashlib.sha256(canonical_json_bytes(package)).hexdigest()


def _point_descendants(point_id: str, children: Mapping[str, tuple[str, ...]]) -> tuple[str, ...]:
    found: list[str] = []
    pending = list(children.get(point_id, ()))
    while pending:
        current = pending.pop(0)
        found.append(current)
        pending.extend(children.get(current, ()))
    return tuple(found)


def create_adapted_question_input(
    knowledge_point_id: str, *, workspace_path: str | Path | None = None,
) -> tuple[Path, str]:
    """Write the M31 input package to the registered staging inputs folder."""
    workspace = load_workspace(workspace_path)
    package, digest = adapted_question_input_data(workspace, knowledge_point_id)
    staging = workspace.write_target("staging")
    target = staging / "inputs" / f"adapted--{knowledge_point_id}--{digest[:12]}.json"
    _ensure_child(staging / "inputs", staging, "inputs directory")
    _ensure_child(target, staging / "inputs", "input package")
    target.parent.mkdir(parents=True, exist_ok=True)
    replace_bytes(target, canonical_json_bytes(package))
    return target, digest


def submit_staged_question(
    path: str | Path, *, dry_run: bool = False,
    workspace_path: str | Path | None = None,
) -> tuple[Path | None, dict[str, Any]]:
    """Validate freshness, provenance and learnable target before appending."""
    if not isinstance(dry_run, bool):
        raise ContractError("dry_run must be a boolean", "dry_run")
    workspace = load_workspace(workspace_path)
    try:
        bank_root = workspace.write_target("state.question_bank")
        staging = workspace.write_target("staging")
    except ContractError as exc:
        raise ContractError(str(exc), "state.question_bank") from exc
    proposal_path = Path(path)
    try:
        resolved = proposal_path.resolve(strict=True)
        staging_root = staging.resolve(strict=False)
        category_root = (staging / "question_bank").resolve(strict=False)
        category_root.relative_to(staging_root)
        resolved.relative_to(category_root)
    except (OSError, ValueError, RuntimeError) as exc:
        raise ContractError(
            "proposal must be under staging/question_bank", proposal_path.as_posix()
        ) from exc
    raw = _read_yaml(resolved)
    if not isinstance(raw, Mapping):
        raise ContractError("expected a mapping", resolved.as_posix())
    if not (_REQUIRED_FIELDS | {"input_hash"}) <= set(raw) or set(raw) - {
        *_FIELDS, "input_hash",
    }:
        raise ContractError("proposal fields do not match question schema", resolved.as_posix())
    digest = raw["input_hash"]
    if not isinstance(digest, str) or not _HASH.fullmatch(digest):
        raise ContractError("input_hash must be a 64-character SHA-256", "input_hash")
    payload = {key: value for key, value in raw.items() if key != "input_hash"}
    question = validate_question(payload, source=resolved.as_posix())
    input_path = _matching_input(staging, question["knowledge_point_id"], digest)
    try:
        package = json.loads(input_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot read input package: {exc}", input_path.as_posix()) from exc
    actual = hashlib.sha256(canonical_json_bytes(package)).hexdigest()
    if actual != digest:
        raise ContractError("input package hash does not match", "input_hash")
    current_package, current_hash = adapted_question_input_data(
        workspace, question["knowledge_point_id"]
    )
    if current_hash != digest or current_package != package:
        raise ContractError("输入已变化，请基于新输入包重新提案", "input_hash")
    expected_basis = package["basis"]
    if question["basis"] != expected_basis:
        raise ContractError("basis does not match the input package", "basis")
    candidates = {item["question_id"] for item in package["candidates"]}
    if any(item not in candidates for item in question["based_on"]):
        raise ContractError("based_on must come from the input candidates", "based_on")
    if dry_run:
        _preflight_question(bank_root, question)
        return None, question
    return append_question(bank_root, question), question


def _matching_input(staging: Path, point_id: str, digest: str) -> Path:
    inputs = staging / "inputs"
    try:
        staging_root = staging.resolve(strict=False)
        input_root = inputs.resolve(strict=False)
        input_root.relative_to(staging_root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ContractError("inputs path resolves outside staging", inputs.as_posix()) from exc
    candidates = sorted(inputs.glob(f"adapted--{point_id}--*.json"))
    for candidate in candidates:
        if candidate.name == f"adapted--{point_id}--{digest[:12]}.json":
            try:
                candidate.resolve(strict=True).relative_to(input_root)
            except (OSError, RuntimeError, ValueError) as exc:
                raise ContractError(
                    "input package resolves outside staging/inputs", candidate.as_posix()
                ) from exc
            return candidate
    raise ContractError("matching adapted-question input package not found", "input_hash")
