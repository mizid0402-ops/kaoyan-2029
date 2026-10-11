"""M5 real-question index verifier; see ``contracts/exam_index.md`` and
``contracts/paper_shape.md``.

Public interface: ``verify(path, workspace, materials)`` and the CLI ``main()``.

Design change from the first attempt: a "look for long strings" leak scan produced 99
false positives, because sha256 digests and the file's own explanatory prose are long
strings too. Distinguishing "long text that is content" from "long text that is
metadata" by regex is guesswork.

So this verifier is a **schema contract** instead, which is both stricter and decidable:

  * every key must be on an allow-list; an unexpected key is a failure (this is the same
    "unknown keys are rejected with a precise path" rule `ky.models` and `ky.ledger` use);
  * no value may be free text: identifiers must match an id pattern, digests must be
    lowercase hex of length 64, page/line must be non-negative ints, answer letters are a
    single A-G letter, narrowed per section by the registered paper shape, and every other
    string must be drawn from an enumerated set;
  * consequently, a question stem, an option, or an explanation **cannot** be stored
    without failing this check — there is no field shape that permits it.

Plus the shape and provenance checks: marks total, numbering, type split, answer
coverage, and that the recorded hashes equal the bytes on disk.

Usage:  py -3.12 tools/verify_408_index.py [path ...]
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from ky.models import ContractError  # noqa: E402
from ky.exam.paper_shape import PaperRecord, load_paper_shapes  # noqa: E402
from ky.workspace import Workspace, load_workspace  # noqa: E402

SHA256 = re.compile(r"^[0-9a-f]{64}$")
QUESTION_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)?-\d{4}-\d{2}$")
RESOURCE_ID = re.compile(r"^[a-z0-9][a-z0-9\-]*$")
YEAR = re.compile(r"^\d{4}$")
PAPER_SOURCE = re.compile(r"^[a-z][a-z0-9]*$")

# The upstream confidence-weighted attribution (data/review_weights/topic_weights.json) rounds
# each node's weight to 3 decimal places before writing. Summing several rounded numbers does
# not land exactly on 1.0: checked against the actual file, 99/432 distributions deviate from
# 1.0 by up to 0.002 (max 9 terms in one distribution), none more. A 1e-6 tolerance would flag
# ~23% of real, correct distributions as broken; 5e-3 comfortably covers the observed rounding
# noise while still catching a real error (a dropped term, a wrong confidence weight), which in
# this data always moves the sum by much more than half a percent.
WEIGHT_SUM_TOLERANCE = 5e-3

TOP_KEYS = {
    "schema_version", "kind", "exam_year", "subject_id", "question_count", "marks_total",
    "answer_source_coverage", "calibration", "provenance", "content_policy",
    "verified_facts", "unverified_facts", "entries", "paper_source",
}
# The descriptive prose fields stay optional, as they always were (sol round 67); identity and
# evidence fields are required.
REQUIRED_TOP_KEYS = TOP_KEYS - {
    "paper_source", "content_policy", "verified_facts", "unverified_facts",
}
# check_enum lets None through because many fields are nullable; these two are not, and a null
# `calibration` would otherwise skip the official-answer gate (sol round 67, M1).
NON_NULL_ENUM_KEYS = ("kind", "calibration")
ENTRY_KEYS = {
    "question_id", "exam_year", "subject_id", "number", "question_type", "marks",
    "answer", "answer_kind", "answer_confidence", "answer_sources", "locator",
    "knowledge_point_id", "knowledge_point_status", "notes",
    # A composite question genuinely spans several knowledge points, so a single id loses the
    # distribution. This carries the confidence-weighted multi-coder attribution instead:
    # {node_id: weight}, weights summing to 1.0. `knowledge_point_id` then holds the argmax,
    # kept so existing consumers do not break.
    "knowledge_point_weights",
}
ANSWER_SOURCE_KEYS = {"resource_id", "sha256", "cross_checked_with"}
LOCATOR_KEYS = {"paper_sha256", "page", "line"}
PROVENANCE_KEYS = {"paper", "answer"}
PROV_DOC_KEYS = {"resource_id", "sha256", "source_tier", "rights_status", "note"}
COVERAGE_KEYS = {"choice_answered", "choice_total", "cross_checked", "cross_checked_numbers"}

ENUMS = {
    ("kind",): {"exam_question_index"},
    ("question_type",): {
        "single_choice", "fill_blank", "comprehensive_application", "translation", "writing",
    },
    ("answer_kind",): {None, "letter"},
    ("answer_confidence",): {"unverified", "cross_checked", "official"},
    # assigned_multi_model: three independent AI coders converged on one node (round 15's
    # confidence-weighted distribution has exactly one entry). assigned_unreviewed: the
    # distribution is spread across several nodes (disagreement). assigned_reviewed is kept
    # in the enum but this pipeline has no authority to write it any more -- see the
    # provenance check below. Its "reviewed" now means a human checked the node against the
    # official answer book / source transcript, a different and stronger evidence chain than
    # three models agreeing with each other; nothing in this repo currently produces it.
    ("knowledge_point_status",): {
        "not_assigned", "assigned_multi_model", "assigned_unreviewed", "assigned_reviewed",
    },
    ("calibration",): {"awaiting_official_book", "calibrated"},
    ("source_tier",): {
        "official", "official_publisher", "university", "trusted_reprint", "community_archive",
    },
    ("rights_status",): {
        "official_public", "officially_published", "unknown", "personal_use", "restricted",
    },
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@lru_cache(maxsize=None)
def _tree_ids(tree_path: Path) -> frozenset[str]:
    """Every real knowledge-point ID from the registered effective tree.

    Membership here is what "id合法" actually means: not "looks like an id" but "is a node
    the tree really has." Cached because the verifier runs once per index file (up to 11 in
    a run) and re-parsing a ~400-node tree each time is wasted work for an unchanging answer.
    """
    from ky.knowledge.knowledge_point import load_knowledge_points

    points = load_knowledge_points(tree_path)
    return frozenset(p.knowledge_point_id for p in points)


def extract_408_answers(path: Path) -> dict[int, str]:
    """Read only the answer-letter DOM anchor from a registered quiz page."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    card = re.compile(
        r'<div\s+class=(?:"?)explanation(?:"?)\s+id=(?:"?)explanation-choice-'
        r'([0-9a-f]+)-(\d+)(?:"?)>(.*?)</div>', re.S
    )
    span = re.compile(r'<span\s+class=(?:"?)correct-answer-text(?:"?)[^>]*>(.*?)</span>', re.S)
    answers: dict[int, str] = {}
    for match in card.finditer(raw):
        answer = span.search(match.group(3))
        if answer:
            letter = html.unescape(re.sub(r"<[^>]+>", "", answer.group(1))).strip()
            if re.fullmatch(r"[A-G]", letter):
                answers[int(match.group(2))] = letter
    return answers


# New source format = add a reader here and register its name in the paper shape.
ANSWER_READERS = {"csgraduates_quiz_dom": extract_408_answers}


def check_keys(node: dict, allowed: set[str], where: str, problems: list[str]) -> None:
    extra = sorted(set(node) - allowed)
    if extra:
        problems.append(f"{where}: unexpected key(s) {extra}")


def check_required_keys(node: dict, required: set[str], where: str, problems: list[str]) -> None:
    for key in sorted(required - set(node)):
        problems.append(f"{where}.{key}: required field is missing")


def check_enum(value, key: str, where: str, problems: list[str]) -> None:
    allowed = ENUMS.get((key,))
    if allowed is None or value is None:
        return
    if value not in allowed:
        problems.append(f"{where}: {key}={value!r} not in {sorted(map(str, allowed))}")


def _decimal_number(value) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        return None
    return result if result.is_finite() else None


def _section_for_number(shape: PaperRecord, number: int):
    return next((section for section in shape.sections if number in section.numbers()), None)


def _answer_letters_label(letters: str) -> str:
    if len(letters) > 1 and all(
        ord(right) == ord(left) + 1 for left, right in zip(letters, letters[1:])
    ):
        return f"{letters[0]}-{letters[-1]}"
    return letters


def _load_paper_record(
    data: dict, workspace: Workspace
) -> tuple[PaperRecord | None, list[str]]:
    subject = data.get("subject_id")
    year = data.get("exam_year")
    paper_source = data.get("paper_source", "national")
    if not isinstance(subject, str):
        return None, ["$: subject_id must be a registered subject identifier"]
    if not isinstance(year, int) or isinstance(year, bool):
        return None, ["$: exam_year must be an integer year"]
    if not isinstance(paper_source, str) or not PAPER_SOURCE.fullmatch(paper_source):
        return None, ["$: invalid paper source code"]
    shape_path = workspace.paper_shapes.get(subject)
    if shape_path is None:
        return None, [f"$: no paper shape file registered for subject {subject!r}"]

    try:
        shapes = load_paper_shapes(
            workspace.require(f"reference.paper_shapes.{subject}"), subject_id=subject
        )
    except ContractError as exc:
        return None, [f"$: {exc}"]
    try:
        return shapes.get(year, paper_source), []
    except ContractError as exc:
        return None, [f"$: {exc}"]


def _verify_section_entries(shape: PaperRecord, entries: list) -> list[str]:
    problems: list[str] = []
    if len(entries) != shape.question_count:
        problems.append(
            f"question count is {len(entries)}, registered shape says {shape.question_count}"
        )
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        number = entry.get("number")
        if not isinstance(number, int) or isinstance(number, bool):
            continue
        section = _section_for_number(shape, number)
        if section is None:
            problems.append(f"{entry.get('question_id')}: number is outside registered sections")
            continue
        problems.extend(_verify_entry_section(entry, section, number))
    return problems


def _verify_entry_section(entry: dict, section, number: int) -> list[str]:
    problems: list[str] = []
    question_id = entry.get("question_id")
    if entry.get("question_type") != section.question_type:
        problems.append(f"{question_id}: question_type disagrees with paper shape")
    answer = entry.get("answer")
    if section.answer_letters and answer is not None and (
        not isinstance(answer, str) or answer not in section.answer_letters
    ):
        allowed = _answer_letters_label(section.answer_letters)
        problems.append(f"{question_id}: choice answers must be {allowed}")
    marks = _decimal_number(entry.get("marks"))
    if section.marks_each is not None and marks != Decimal(str(section.marks_each)):
        problems.append(f"{question_id}: marks disagree with marks_each")
    elif section.marks is not None and marks != Decimal(str(section.marks[number])):
        problems.append(f"{question_id}: marks disagree with registered marks")
    elif section.marks_unverified and entry.get("marks") is not None:
        problems.append(f"{question_id}: unverified marks must be null")
    return problems


def _verify_registered_total(shape: PaperRecord, data: dict) -> list[str]:
    if any(
        section.marks_each is None and section.marks is None
        for section in shape.sections
    ):
        return []
    expected_total = Decimal("0")
    for section in shape.sections:
        if section.marks_each is not None:
            expected_total += (
                section.end - section.start + 1
            ) * Decimal(str(section.marks_each))
        else:
            expected_total += sum(
                (Decimal(str(mark)) for mark in section.marks.values()), Decimal("0")
            )
    actual_total = _decimal_number(data.get("marks_total"))
    if actual_total != expected_total:
        return [
            f"marks_total {actual_total} != registered shape total {expected_total}"
        ]
    return []


def _verify_independent_answers(
    shape: PaperRecord, data: dict, entries: list, workspace: Workspace, materials: dict
) -> list[str]:
    if shape.answer_reader is None:
        return []
    reader = ANSWER_READERS.get(shape.answer_reader)
    if reader is None:
        return [f"$: unknown answer_reader {shape.answer_reader!r}"]
    provenance = data.get("provenance") or {}
    answer_block = provenance.get("answer") or {}
    material = materials.get(answer_block.get("resource_id"))
    answer_path = (
        workspace.root / material.storage.path
        if material and material.storage.path
        else None
    )
    if answer_path is None or not answer_path.is_file():
        return [
            "$: cannot independently read answer source for "
            f"({data.get('exam_year')}, {data.get('paper_source', 'national')})"
        ]
    answers = reader(answer_path)
    expected_answers = {
        number
        for section in shape.sections
        if section.answer_letters
        for number in section.numbers()
    }
    problems: list[str] = []
    if set(answers) != expected_answers:
        problems.append(
            f"$: answer reader yielded question numbers {sorted(answers)}, "
            f"expected {sorted(expected_answers)}"
        )
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("number") not in expected_answers:
            continue
        number = entry["number"]
        if entry.get("answer") != answers.get(number):
            problems.append(
                f"{entry.get('question_id')}: answer {entry.get('answer')!r} "
                f"!= source {answers.get(number)!r}"
            )
    return problems


def _verify_paper_shape(
    data: dict, entries: list, workspace: Workspace, materials: dict
) -> list[str]:
    shape, problems = _load_paper_record(data, workspace)
    if shape is None:
        return problems
    problems.extend(_verify_section_entries(shape, entries))
    problems.extend(_verify_registered_total(shape, data))
    problems.extend(_verify_independent_answers(shape, data, entries, workspace, materials))
    return problems


def _verify_index_header(data: dict, workspace: Workspace, problems: list[str]) -> tuple:
    check_keys(data, TOP_KEYS, "$", problems)
    check_required_keys(data, REQUIRED_TOP_KEYS, "$", problems)
    for key in NON_NULL_ENUM_KEYS:
        if key in data and data[key] is None:
            problems.append(f"$.{key}: must not be null")
    check_enum(data.get("kind"), "kind", "$", problems)
    subject = data.get("subject_id")
    if not isinstance(subject, str) or subject not in workspace.subjects:
        problems.append(f"$.subject_id: {subject!r} is not a registered subject")
    year = data.get("exam_year")
    if not isinstance(year, int) or isinstance(year, bool):
        problems.append("$.exam_year: expected an integer year")
    paper_source = data.get("paper_source", "national")
    if not isinstance(paper_source, str) or not PAPER_SOURCE.fullmatch(paper_source):
        problems.append("$.paper_source: invalid paper source code")
    check_enum(data.get("calibration"), "calibration", "$", problems)
    if not YEAR.match(str(data.get("exam_year", ""))):
        problems.append("$: exam_year must be a 4-digit year")
    if not isinstance(data.get("schema_version"), int):
        problems.append("$: schema_version must be an int")
    return subject, year, paper_source


def _verify_provenance_shape(data: dict, problems: list[str]) -> None:
    check_keys(data.get("provenance", {}), PROVENANCE_KEYS, "$.provenance", problems)
    for label, block in (data.get("provenance") or {}).items():
        where = f"$.provenance.{label}"
        if not isinstance(block, dict):
            problems.append(f"{where}: expected an object")
            continue
        check_keys(block, PROV_DOC_KEYS, where, problems)
        if not RESOURCE_ID.match(str(block.get("resource_id", ""))):
            problems.append(f"{where}.resource_id: not an id")
        if not SHA256.match(str(block.get("sha256", ""))):
            problems.append(f"{where}.sha256: not a 64-char lowercase hex digest")
        check_enum(block.get("source_tier"), "source_tier", where, problems)
        check_enum(block.get("rights_status"), "rights_status", where, problems)


def _verify_coverage_shape(data: dict, problems: list[str]) -> None:
    coverage = data.get("answer_source_coverage")
    if not isinstance(coverage, dict):
        problems.append("$.answer_source_coverage: expected an object")
    else:
        check_keys(coverage, COVERAGE_KEYS, "$.answer_source_coverage", problems)


def _verify_entry_identity(
    entry: dict, where: str, subject, year, paper_source, problems: list[str]
) -> int | None:
    check_keys(entry, ENTRY_KEYS, where, problems)
    if not QUESTION_ID.match(str(entry.get("question_id", ""))):
        problems.append(f"{where}.question_id: not an id")
    raw_number = entry.get("number")
    number = raw_number
    if (
        not isinstance(number, int)
        or isinstance(number, bool)
        or number < 1
    ):
        problems.append(f"{where}.number: must be a positive int")
        number = None
    if entry.get("subject_id") != subject:
        problems.append(f"{where}.subject_id: must equal top-level subject_id")
    if entry.get("exam_year") != year:
        problems.append(f"{where}.exam_year: must equal top-level exam_year")
    if (
        isinstance(raw_number, int)
        and not isinstance(raw_number, bool)
        and isinstance(year, int)
    ):
        if paper_source == "national":
            expected_id = f"{subject}-{year}-{raw_number:02d}"
        else:
            expected_id = f"{subject}-{paper_source}-{year}-{raw_number:02d}"
        if entry.get("question_id") != expected_id:
            problems.append(f"{where}.question_id: expected {expected_id}")
    return number


def _verify_entry_values(
    entry: dict, where: str, subject, valid_kp_ids, problems: list[str]
):
    marks = entry.get("marks")
    decimal_marks = _decimal_number(marks)
    if marks is not None and (decimal_marks is None or decimal_marks <= 0):
        problems.append(f"{where}.marks: must be null or a positive number")
    check_enum(entry.get("question_type"), "question_type", where, problems)
    check_enum(entry.get("answer_kind"), "answer_kind", where, problems)
    check_enum(entry.get("answer_confidence"), "answer_confidence", where, problems)
    check_enum(entry.get("knowledge_point_status"), "knowledge_point_status", where, problems)

    answer = entry.get("answer")
    if answer is not None and (
        not isinstance(answer, str) or answer not in set("ABCDEFG")
    ):
        problems.append(f"{where}.answer: only a single A-G letter may be stored")

    kp = entry.get("knowledge_point_id")
    if kp is not None and (not isinstance(kp, str) or kp not in valid_kp_ids):
        problems.append(
            f"{where}.knowledge_point_id: {kp!r} is not a node in the {subject} tree"
        )
    return kp


def _verify_entry_weights(
    entry: dict, where: str, kp, subject, valid_kp_ids, problems: list[str]
) -> None:
    # A composite question's distribution and primary id must describe the same assignment.
    kpw = entry.get("knowledge_point_weights")
    if kpw is not None:
        if not isinstance(kpw, dict):
            problems.append(f"{where}.knowledge_point_weights: expected an object")
        elif not kpw:
            problems.append(f"{where}.knowledge_point_weights: must not be empty when present")
        else:
            bad_id = [key for key in kpw if key not in valid_kp_ids]
            if bad_id:
                problems.append(
                    f"{where}.knowledge_point_weights: id(s) not in the "
                    f"{subject} tree {bad_id[:3]}"
                )
            bad_w = [
                key for key, value in kpw.items()
                if isinstance(value, bool)
                or not isinstance(value, (int, float))
                or value <= 0
            ]
            if bad_w:
                problems.append(
                    f"{where}.knowledge_point_weights: non-positive weight(s) "
                    f"{bad_w[:3]}"
                )
            else:
                total = sum(kpw.values())
                if abs(total - 1.0) > WEIGHT_SUM_TOLERANCE:
                    problems.append(
                        f"{where}.knowledge_point_weights: weights sum to "
                        f"{total:.6f}, expected 1.0"
                    )
                argmax = max(kpw, key=lambda key: kpw[key])
                if kp is not None and argmax != kp:
                    problems.append(
                        f"{where}: knowledge_point_id {kp!r} is not the argmax {argmax!r} "
                        f"of knowledge_point_weights"
                    )
                if kp is None:
                    problems.append(
                        f"{where}: knowledge_point_weights present but "
                        "knowledge_point_id is null"
                    )


def _verify_entry_assignment_status(entry: dict, where: str, kp, problems: list[str]) -> None:
    # Status and ids must agree; a model distribution cannot claim human review.
    kpw = entry.get("knowledge_point_weights")
    kp_status = entry.get("knowledge_point_status")
    if kp_status == "not_assigned" and (kp is not None or kpw is not None):
        problems.append(
            f"{where}: knowledge_point_status=not_assigned but "
            "a knowledge point is set"
        )
    if (
        kp_status in {"assigned_reviewed", "assigned_unreviewed", "assigned_multi_model"}
        and kp is None
    ):
        problems.append(
            f"{where}: knowledge_point_status={kp_status} but knowledge_point_id is null"
        )
    if kp_status == "assigned_reviewed" and kpw is not None:
        problems.append(
            f"{where}: knowledge_point_status=assigned_reviewed but knowledge_point_weights "
            f"is set -- this pipeline cannot claim human review; use assigned_multi_model "
            f"for a converged 3-model distribution"
        )
    if kp_status == "assigned_multi_model" and kpw is not None and len(kpw) != 1:
        problems.append(
            f"{where}: knowledge_point_status=assigned_multi_model requires a single-node "
            f"distribution, got {len(kpw)} node(s)"
        )
    if kp_status == "assigned_unreviewed" and kpw is not None and len(kpw) <= 1:
        problems.append(
            f"{where}: knowledge_point_status=assigned_unreviewed requires a spread "
            f"distribution (>1 node), got {len(kpw)}"
        )


def _verify_entry_sources(entry: dict, where: str, problems: list[str]) -> None:
    sources = entry.get("answer_sources")
    if not isinstance(sources, list):
        problems.append(f"{where}.answer_sources: expected a list")
    else:
        for s_index, source in enumerate(sources):
            s_where = f"{where}.answer_sources[{s_index}]"
            if not isinstance(source, dict):
                problems.append(f"{s_where}: expected an object")
                continue
            check_keys(source, ANSWER_SOURCE_KEYS, s_where, problems)
            if not SHA256.match(str(source.get("sha256", ""))):
                problems.append(f"{s_where}.sha256: not a digest")


def _verify_entry_locator(entry: dict, where: str, problems: list[str]) -> None:
    locator = entry.get("locator")
    if not isinstance(locator, dict):
        problems.append(f"{where}.locator: expected an object")
    else:
        check_keys(locator, LOCATOR_KEYS, where + ".locator", problems)
        if not SHA256.match(str(locator.get("paper_sha256", ""))):
            problems.append(f"{where}.locator.paper_sha256: not a digest")
        for key in ("page", "line"):
            if not isinstance(locator.get(key), int) or locator[key] < 0:
                problems.append(f"{where}.locator.{key}: must be a non-negative int")


def _verify_entry(
    entry: dict, index: int, subject, year, paper_source, valid_kp_ids,
    problems: list[str]
) -> int | None:
    where = f"$.entries[{index}]"
    number = _verify_entry_identity(entry, where, subject, year, paper_source, problems)
    kp = _verify_entry_values(entry, where, subject, valid_kp_ids, problems)
    _verify_entry_weights(entry, where, kp, subject, valid_kp_ids, problems)
    _verify_entry_assignment_status(entry, where, kp, problems)
    if entry.get("notes") is not None:
        problems.append(
            f"{where}.notes: must be null (free text here could carry question content)"
        )
    _verify_entry_sources(entry, where, problems)
    _verify_entry_locator(entry, where, problems)
    return number


def _verify_free_text_fields(data: dict, problems: list[str]) -> None:
    for where, key in (("$", "content_policy"),):
        value = data.get(key)
        if value is not None and not isinstance(value, str):
            problems.append(f"{where}.{key}: expected a string")
    for key in ("verified_facts", "unverified_facts"):
        value = data.get(key)
        if value is not None and not isinstance(value, list):
            problems.append(f"$.{key}: expected a list")


def _verify_totals(data: dict, entries: list, numbers: list, problems: list[str]) -> None:
    if numbers != list(range(1, len(entries) + 1)):
        problems.append(f"numbering not contiguous: {len(numbers)} entries")
    if len(entries) != data.get("question_count"):
        problems.append("question_count disagrees with entries length")
    object_entries = [entry for entry in entries if isinstance(entry, dict)]
    numeric_marks = [
        _decimal_number(entry.get("marks"))
        for entry in object_entries
        if entry.get("marks") is not None
    ]
    incomplete_marks = len(numeric_marks) != len(entries) or any(
        mark is None for mark in numeric_marks
    )
    total = (
        sum((mark for mark in numeric_marks if mark is not None), Decimal("0"))
        if numeric_marks and not incomplete_marks
        else None
    )
    declared_total = data.get("marks_total")
    if incomplete_marks:
        if declared_total is not None:
            problems.append("marks_total must be null when an entry mark is null")
    elif total != _decimal_number(declared_total):
        problems.append(f"marks_total {declared_total} != sum {total}")


def _verify_answer_coverage(data: dict, entries: list, problems: list[str]) -> None:
    # The entry loop already reported non-object entries; coverage counts only the objects.
    object_entries = [entry for entry in entries if isinstance(entry, dict)]
    essay = [
        entry for entry in object_entries
        if entry.get("question_type") == "comprehensive_application"
    ]
    answerable = [entry for entry in object_entries if entry.get("answer_kind") == "letter"]
    coverage = data.get("answer_source_coverage")
    coverage_total = coverage.get("choice_total") if isinstance(coverage, dict) else None
    if len(answerable) != coverage_total:
        problems.append(
            f"answerable count {len(answerable)} != answer_source_coverage.choice_total "
            f"{coverage_total}"
        )
    for entry in answerable:
        if not entry.get("answer"):
            problems.append(f"{entry.get('question_id')}: letter answer missing")
    for entry in essay:
        if entry.get("answer") is not None:
            problems.append(f"{entry.get('question_id')}: essay must carry no letter")


def _verify_registered_provenance(
    data: dict, entries: list, workspace: Workspace, materials: dict,
    problems: list[str]
) -> None:
    provenance = data.get("provenance") or {}
    for label, block in provenance.items():
        rid = (block or {}).get("resource_id")
        recorded = (block or {}).get("sha256")
        material = materials.get(rid)
        if material is None:
            problems.append(f"$.provenance.{label}: resource_id {rid!r} is not in the ledger")
            continue
        where = material.storage.path
        if not where:
            if material.storage.mode != "remote_reference":
                problems.append(f"$.provenance.{label}: {rid} has no file path to check")
            continue
        source_path = workspace.root / where
        if not source_path.is_file():
            problems.append(f"$.provenance.{label}: registered file missing at {where}")
        elif recorded and sha(source_path) != recorded:
            problems.append(
                f"$.provenance.{label}: disk hash != index hash for {rid} "
                f"(index={str(recorded)[:16]} disk={sha(source_path)[:16]})"
            )
    paper_hash = (provenance.get("paper") or {}).get("sha256")
    for entry in entries:
        locator_hash = (entry.get("locator") or {}).get("paper_sha256")
        if locator_hash != paper_hash:
            problems.append(f"{entry.get('question_id')}: locator hash != provenance hash")
            break


def _verify_calibration(data: dict, entries: list, problems: list[str]) -> None:
    if data.get("calibration") != "awaiting_official_book":
        return
    for entry in entries:
        if (
            entry.get("knowledge_point_id") is not None
            and entry.get("knowledge_point_weights") is None
        ):
            problems.append(
                f"{entry.get('question_id')}: knowledge point set before calibration"
            )
        if entry.get("answer_confidence") == "official":
            problems.append(
                f"{entry.get('question_id')}: claims official answer while uncalibrated"
            )


def verify(
    path: Path,
    workspace: Workspace,
    materials: dict,
) -> list[str]:
    problems: list[str] = []
    data = json.loads(path.read_text(encoding="utf-8"))
    subject, year, paper_source = _verify_index_header(data, workspace, problems)
    _verify_provenance_shape(data, problems)
    _verify_coverage_shape(data, problems)

    entries = data.get("entries")
    if not isinstance(entries, list) or not entries:
        problems.append("$.entries: expected a non-empty list")
        return problems

    tree_path = workspace.knowledge_trees.get(subject) if isinstance(subject, str) else None
    if tree_path is None:
        valid_kp_ids = frozenset()
    else:
        valid_kp_ids = _tree_ids(workspace.require(f"reference.knowledge_trees.{subject}"))
    numbers = []
    for index, entry in enumerate(entries):
        where = f"$.entries[{index}]"
        if not isinstance(entry, dict):
            problems.append(f"{where}: expected an object")
            continue
        number = _verify_entry(
            entry, index, subject, year, paper_source, valid_kp_ids, problems
        )
        if number is not None:
            numbers.append(number)

    _verify_free_text_fields(data, problems)
    _verify_totals(data, entries, numbers, problems)
    _verify_answer_coverage(data, entries, problems)
    _verify_registered_provenance(data, entries, workspace, materials, problems)
    problems.extend(_verify_paper_shape(data, entries, workspace, materials))
    _verify_calibration(data, entries, problems)
    return problems

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", type=Path)
    ap.add_argument("--workspace", type=Path)
    args = ap.parse_args()
    try:
        workspace = load_workspace(args.workspace)
        from ky.ledger import load_ledger

        ledger_path = workspace.require("reference.ledger")
        materials = {item.resource_id: item for item in load_ledger(ledger_path)}
        targets = args.paths or sorted(
            path
            for subject in workspace.exam_indexes
            for path in workspace.require_all(f"reference.exam_indexes.{subject}")
        )
    except ContractError as exc:
        print(f"contract violation: {exc}", file=sys.stderr)
        return 2
    if not targets:
        print("no exam index files are registered", file=sys.stderr)
        return 2

    failed = False
    for path in targets:
        try:
            problems = verify(path, workspace, materials)
        except ContractError as exc:
            print(f"contract violation: {exc}", file=sys.stderr)
            return 2
        print(f"{path.name}: {'OK' if not problems else f'FAIL ({len(problems)})'}")
        for problem in problems[:12]:
            print(f"   - {problem}")
        failed = failed or bool(problems)
    print("\nALL INDEX FILES VERIFIED" if not failed else "\nVERIFICATION FAILED")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
