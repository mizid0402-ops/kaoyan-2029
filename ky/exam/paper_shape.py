"""M5′ paper shape data loader (``contracts/paper_shape.md``).

Public interfaces: :func:`load_paper_shapes`, :class:`PaperShapes`,
:class:`PaperRecord`, and :class:`PaperSection`.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from ky.models import ContractError, load_yaml_text

_ROOT_KEYS = frozenset({"schema_version", "kind", "subject_id", "papers"})
_PAPER_KEYS = frozenset(
    {"exam_year", "paper_source", "question_count", "sections", "answer_reader", "basis"}
)
_SECTION_KEYS = frozenset(
    {"numbers", "question_type", "marks_each", "marks", "answer_letters"}
)
_QUESTION_TYPES = frozenset(
    {"single_choice", "fill_blank", "comprehensive_application", "translation", "writing"}
)
_CODE = re.compile(r"^[a-z][a-z0-9]*$")


@dataclass(frozen=True)
class PaperSection:
    start: int
    end: int
    question_type: str
    marks_each: int | float | None
    marks: Mapping[int, int | float] | None
    marks_unverified: bool
    answer_letters: str | None

    def numbers(self) -> range:
        return range(self.start, self.end + 1)


@dataclass(frozen=True)
class PaperRecord:
    exam_year: int
    paper_source: str
    question_count: int
    sections: tuple[PaperSection, ...]
    answer_reader: str | None
    basis: str


@dataclass(frozen=True)
class PaperShapes:
    subject_id: str
    papers: Mapping[tuple[int, str], PaperRecord]

    def get(self, exam_year: int, paper_source: str = "national") -> PaperRecord:
        record = self.papers.get((exam_year, paper_source))
        if record is None:
            raise ContractError(
                f"no paper shape recorded for ({exam_year}, {paper_source})",
                "papers",
            )
        return record


def _mapping(value: object, path: str) -> dict:
    if not isinstance(value, dict):
        raise ContractError("expected a mapping", path)
    return value


def _unknown(node: dict, allowed: frozenset[str], path: str) -> None:
    unknown = sorted(set(node) - allowed, key=str)
    if unknown:
        key = unknown[0]
        raise ContractError(f"unknown field {key!r}", f"{path}.{key}")


def _required(node: dict, key: str, path: str) -> object:
    if key not in node:
        raise ContractError("required field is missing", f"{path}.{key}".strip("."))
    return node[key]


def _integer(value: object, path: str, *, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ContractError("expected an integer", path)
    if value < minimum:
        raise ContractError(f"must be >= {minimum}", path)
    return value


def _positive_number(value: object, path: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractError("expected a finite positive number", path)
    if (isinstance(value, float) and not math.isfinite(value)) or value <= 0:
        raise ContractError("expected a finite positive number", path)
    return value


def _parse_marks(
    node: dict, path: str, start: int, end: int
) -> tuple[int | float | None, Mapping[int, int | float] | None, bool]:
    mark_keys = {key for key in ("marks_each", "marks") if key in node}
    if len(mark_keys) > 1:
        raise ContractError("only one marks form is allowed", path)
    if "marks_each" in node:
        value = _positive_number(node["marks_each"], f"{path}.marks_each")
        return value, None, False
    if "marks" not in node:
        return None, None, False
    raw_marks = node["marks"]
    if raw_marks == "unverified":
        return None, None, True
    mark_map = _mapping(raw_marks, f"{path}.marks")
    expected = set(range(start, end + 1))
    valid_keys = all(
        isinstance(number, int) and not isinstance(number, bool)
        for number in mark_map
    )
    if not valid_keys or set(mark_map) != expected:
        raise ContractError("marks keys must match section question numbers", f"{path}.marks")
    marks = MappingProxyType(
        {
            number: _positive_number(mark_map[number], f"{path}.marks.{number}")
            for number in range(start, end + 1)
        }
    )
    return None, marks, False


def _parse_section(raw: object, path: str, expected_start: int) -> PaperSection:
    node = _mapping(raw, path)
    _unknown(node, _SECTION_KEYS, path)
    numbers = _required(node, "numbers", path)
    if not isinstance(numbers, list) or len(numbers) != 2:
        raise ContractError("expected [start, end]", f"{path}.numbers")
    start = _integer(numbers[0], f"{path}.numbers[0]")
    end = _integer(numbers[1], f"{path}.numbers[1]")
    if start != expected_start:
        raise ContractError("sections must continuously cover question numbers", f"{path}.numbers")
    if end < start:
        raise ContractError("range end must be >= start", f"{path}.numbers[1]")

    question_type = _required(node, "question_type", path)
    if not isinstance(question_type, str) or question_type not in _QUESTION_TYPES:
        raise ContractError("unknown question type", f"{path}.question_type")

    marks_each, marks, marks_unverified = _parse_marks(node, path, start, end)

    answer_letters = node.get("answer_letters")
    if answer_letters is not None:
        if (
            not isinstance(answer_letters, str)
            or not answer_letters
            or len(set(answer_letters)) != len(answer_letters)
            or any(letter not in "ABCDEFG" for letter in answer_letters)
        ):
            raise ContractError("expected unique answer letters A-G", f"{path}.answer_letters")
        if question_type != "single_choice":
            raise ContractError("answer_letters requires single_choice", f"{path}.answer_letters")

    return PaperSection(
        start, end, question_type, marks_each, marks, marks_unverified, answer_letters
    )


def _parse_paper(raw: object, index: int) -> PaperRecord:
    path = f"papers[{index}]"
    node = _mapping(raw, path)
    _unknown(node, _PAPER_KEYS, path)
    year = _integer(_required(node, "exam_year", path), f"{path}.exam_year", minimum=1000)
    paper_source = _required(node, "paper_source", path)
    if not isinstance(paper_source, str) or not _CODE.fullmatch(paper_source):
        raise ContractError("invalid paper source code", f"{path}.paper_source")
    count = _integer(_required(node, "question_count", path), f"{path}.question_count")
    if count > 99:
        raise ContractError("question_count must be <= 99", f"{path}.question_count")
    raw_sections = _required(node, "sections", path)
    if not isinstance(raw_sections, list) or not raw_sections:
        raise ContractError("expected a non-empty list", f"{path}.sections")
    sections = []
    next_number = 1
    for section_index, raw_section in enumerate(raw_sections):
        section = _parse_section(
            raw_section, f"{path}.sections[{section_index}]", next_number
        )
        sections.append(section)
        next_number = section.end + 1
    if next_number != count + 1:
        raise ContractError("sections must cover 1..question_count", f"{path}.sections")
    reader = node.get("answer_reader")
    if reader is not None and (not isinstance(reader, str) or not reader):
        raise ContractError("expected a non-empty string", f"{path}.answer_reader")
    basis = _required(node, "basis", path)
    if not isinstance(basis, str) or not basis.strip():
        raise ContractError("expected a non-empty string", f"{path}.basis")
    return PaperRecord(year, paper_source, count, tuple(sections), reader, basis)


def load_paper_shapes(path: str | Path, *, subject_id: str) -> PaperShapes:
    """Load a strict paper shape registry for the declared subject."""
    source = Path(path)
    try:
        raw_text = source.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ContractError(f"cannot read paper shapes: {exc}", "") from exc
    data = _mapping(load_yaml_text(raw_text, source=source.as_posix()), "")
    _unknown(data, _ROOT_KEYS, "$")
    version = _integer(_required(data, "schema_version", ""), "schema_version")
    if version != 1:
        raise ContractError("unsupported schema_version", "schema_version")
    kind = _required(data, "kind", "")
    if kind != "paper_shapes":
        raise ContractError("expected kind paper_shapes", "kind")
    recorded_subject = _required(data, "subject_id", "")
    if not isinstance(recorded_subject, str) or recorded_subject != subject_id:
        raise ContractError("subject_id does not match registered subject", "subject_id")
    raw_papers = _required(data, "papers", "")
    if not isinstance(raw_papers, list) or not raw_papers:
        raise ContractError("expected a non-empty list", "papers")
    records: dict[tuple[int, str], PaperRecord] = {}
    for index, raw_paper in enumerate(raw_papers):
        record = _parse_paper(raw_paper, index)
        key = (record.exam_year, record.paper_source)
        if key in records:
            raise ContractError("duplicate (exam_year, paper_source)", f"papers[{index}]")
        records[key] = record
    return PaperShapes(subject_id, MappingProxyType(records))
