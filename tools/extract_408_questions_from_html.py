"""M21 HTML question extractor; see ``contracts/workspace.md``.

Public interface: ``extract_year(year)`` and CLI ``main()``. It reads registered CS408 indexes
and materials and writes only under ``products.cs408_lecture_workspace``.

The extractor handles the collected CS408 papers from explicit numbered HTML anchors.

The quiz pages contain one ``h5`` element whose ``id`` is the question number for
each indexed question. Each choice question ends at a
``div.choice-container`` and each comprehensive question ends at a
``div.answer-container``. Those DOM boundaries are the extraction anchors; the
script never aligns anonymous blocks to index entries by position and never fills
missing text from model knowledge.

Outputs:
  * review/408知识点树与真题/questions/<question_id>.txt
  * review/408知识点树与真题/questions/questions_index.json
  * review/408知识点树与真题/questions/extraction_report.json
  * review/408知识点树与真题/deck_question_map.json
"""

from __future__ import annotations

import hashlib
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, NavigableString, Tag


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from ky.workspace import Workspace, load_workspace  # noqa: E402

WORKSPACE: Workspace | None = None
QUIZ_DIR: Path | None = None
QUESTION_DIR: Path | None = None
DECK_DIR: Path | None = None
DECK_MAP: Path | None = None
REGISTERED_INDEXES: dict[int, dict[str, Any]] = {}

QUESTION_ID_RE = re.compile(r"cs408-\d{4}-\d{2}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean_inline(text: str) -> str:
    """Normalize layout whitespace without rewriting source wording."""
    text = text.replace("\u00a0", " ").replace("\u202f", " ")
    return re.sub(r"\s+", " ", text).strip()


def text_from_table(table: Tag) -> str:
    rows: list[str] = []
    for row in table.find_all("tr"):
        cells = [
            clean_inline(cell.get_text(" ", strip=True))
            for cell in row.find_all(["th", "td"])
        ]
        if cells:
            rows.append(" | ".join(cells))
    return "\n".join(rows) or clean_inline(table.get_text(" ", strip=True))


def block_text(block: Tag) -> tuple[str, list[str]]:
    """Return a text serialization and any fidelity warnings for one DOM block."""
    warnings: list[str] = []
    classes = set(block.get("class") or [])

    if block.name == "table":
        text = text_from_table(block)
    elif block.name in {"pre", "code"} or "highlight" in classes:
        # Syntax highlighters wrap nearly every token in a span.  A separator in
        # get_text() would therefore put each token on its own line; retain only
        # line breaks that are actually present in the source DOM text.
        text = block.get_text("", strip=False).replace("\r\n", "\n")
        text = text.replace("\u00a0", " ").replace("\u202f", " ")
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
    else:
        text = clean_inline(block.get_text(" ", strip=True))

    visual_nodes = block.find_all(["img", "svg", "image"])
    is_visual_wrapper = "svg-wrapper" in classes
    if visual_nodes or is_visual_wrapper:
        warnings.append("visual_content_serialized_as_text")
        alt_texts = [
            clean_inline(node.get("alt", ""))
            for node in block.find_all("img")
            if clean_inline(node.get("alt", ""))
        ]
        if not text and alt_texts:
            text = " ".join(alt_texts)
        if text:
            text = f"[图示文本] {text}"
        else:
            text = "[图像：请查看源 HTML 中的内嵌图形]"
            warnings.append("visual_has_no_accessible_text")
    return text, warnings


def content_between(heading: Tag, boundary: Tag) -> tuple[str, list[str]]:
    blocks: list[str] = []
    warnings: list[str] = []
    node = heading.next_sibling
    reached_boundary = False
    while node is not None:
        if node is boundary:
            reached_boundary = True
            break
        if isinstance(node, Tag):
            if node.name in {"h3", "h4", "h5"}:
                break
            text, block_warnings = block_text(node)
            if text:
                blocks.append(text)
            warnings.extend(block_warnings)
        elif isinstance(node, NavigableString):
            text = clean_inline(str(node))
            if text:
                blocks.append(text)
        node = node.next_sibling
    if not reached_boundary:
        raise ValueError(
            f"boundary {boundary.get('id')} is not after heading {heading.get('id')}"
        )
    return "\n".join(blocks).strip(), sorted(set(warnings))


def direct_boundary(heading: Tag, expected_class: str) -> Tag:
    node = heading.next_sibling
    while node is not None:
        if isinstance(node, Tag):
            if node.name in {"h3", "h4", "h5"}:
                break
            if expected_class in (node.get("class") or []):
                return node
        node = node.next_sibling
    raise ValueError(
        f"question heading {heading.get('id')} has no following {expected_class} boundary"
    )


def parse_options(container: Tag) -> tuple[list[str], list[str], list[str]]:
    labels: list[str] = []
    options: list[str] = []
    warnings: list[str] = []
    for option in container.select("label.choice-option"):
        label_node = option.select_one(".choice-label")
        text_node = option.select_one(".choice-text")
        if label_node is None or text_node is None:
            raise ValueError(f"malformed option in {container.get('id')}")
        labels.append(
            clean_inline(label_node.get_text(" ", strip=True)).rstrip(".．、")
        )
        text, option_warnings = block_text(text_node)
        options.append(text)
        warnings.extend(option_warnings)
    return labels, options, sorted(set(warnings))


def dom_answer(container: Tag) -> str | None:
    node = container.select_one(".correct-answer-text")
    if node is None:
        return None
    match = re.search(r"([ABCD])\s*$", clean_inline(node.get_text(" ", strip=True)))
    return match.group(1) if match else None


def find_numbered_headings(main: Tag) -> dict[int, Tag]:
    found: dict[int, Tag] = {}
    duplicates: list[int] = []
    for heading in main.find_all("h5", id=True):
        ident = str(heading.get("id"))
        if not ident.isdigit():
            continue
        number = int(ident)
        if number in found:
            duplicates.append(number)
        found[number] = heading
    if duplicates:
        raise ValueError(f"duplicate numbered h5 ids: {duplicates}")
    return found


def source_path_for_report(path: Path) -> str:
    if WORKSPACE is None:
        raise RuntimeError("workspace has not been configured")
    return path.relative_to(WORKSPACE.root).as_posix()


def _load_year_inputs(year: int) -> tuple[dict, Path, Tag, dict[int, Tag], dict[int, dict]]:
    if QUIZ_DIR is None:
        raise RuntimeError("workspace has not been configured")
    index_data = REGISTERED_INDEXES[year]
    html_path = QUIZ_DIR / f"cs408_quiz_{year}.html"
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "lxml")
    main = soup.select_one(".td-content")
    if main is None:
        raise ValueError(f"{html_path.name}: missing .td-content")
    headings = find_numbered_headings(main)
    entries = {int(entry["number"]): entry for entry in index_data["entries"]}
    expected_numbers = set(entries)
    if set(headings) != expected_numbers:
        raise ValueError(f"{year}: HTML headings differ from registered index numbers")
    return index_data, html_path, main, headings, entries


def _extract_options(
    year: int,
    number: int,
    entry: dict[str, Any],
    boundary: Tag,
) -> tuple[list[str], list[str], list[str], dict[str, Any] | None]:
    labels, options, warnings = parse_options(boundary)
    if labels != list("ABCD") or len(options) != len(labels) or any(not item for item in options):
        raise ValueError(f"{year} Q{number}: malformed options; labels={labels}")
    observed = dom_answer(boundary)
    indexed = entry.get("answer")
    answer_check = {
        "question_id": entry["question_id"],
        "index_answer": indexed,
        "dom_answer": observed,
        "match": indexed == observed,
    }
    if observed is None or indexed != observed:
        warnings.append("index_answer_does_not_match_dom")
    return labels, options, warnings, answer_check


def _question_content(year: int, number: int, entry: dict[str, Any], heading: Tag):
    is_choice = entry["question_type"] == "single_choice"
    expected_type = "single_choice" if is_choice else "comprehensive_application"
    if entry["question_type"] != expected_type:
        raise ValueError(
            f"{year} Q{number}: unsupported question type {entry['question_type']}"
        )
    boundary_name = "choice-container" if is_choice else "answer-container"
    boundary = direct_boundary(heading, boundary_name)
    stem, warnings = content_between(heading, boundary)
    if not stem:
        raise ValueError(f"{year} Q{number}: empty stem")
    labels: list[str] = []
    options: list[str] = []
    answer_check = None
    if is_choice:
        labels, options, option_warnings, answer_check = _extract_options(
            year,
            number,
            entry,
            boundary,
        )
        warnings.extend(option_warnings)
    warnings = sorted(set(warnings))
    return is_choice, boundary, stem, labels, options, warnings, answer_check


def _extract_question(
    year: int,
    number: int,
    entry: dict[str, Any],
    heading: Tag,
    html_path: Path,
    digest: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    is_choice, boundary, stem, labels, options, warnings, answer_check = _question_content(
        year, number, entry, heading,
    )
    unreadable_visual = "visual_has_no_accessible_text" in warnings
    confidence = "low" if unreadable_visual else ("medium" if warnings else "high")
    status = "suspicious" if unreadable_visual else "extracted"
    question_id = entry["question_id"]
    record = {
        "question_id": question_id,
        "exam_year": year,
        "number": number,
        "question_type": entry["question_type"],
        "marks": entry.get("marks"),
        "stem": stem,
        "options": options,
        "answer": entry.get("answer"),
        "source_html": source_path_for_report(html_path),
        "source_html_sha256": digest,
        "extraction_method": (
            "number-keyed DOM extraction from h5[id] to typed question boundary"
        ),
        "confidence": confidence,
    }
    question_status = {
        "question_id": question_id,
        "number": number,
        "status": status,
        "heading_id": str(heading.get("id")),
        "boundary_id": boundary.get("id"),
        "option_labels": labels,
        "confidence": confidence,
        "warnings": warnings,
    }
    return record, question_status, answer_check


def _year_report(
    index_data: dict,
    html_path: Path,
    main: Tag,
    headings: dict[int, Tag],
    digest: str,
    statuses: list[dict[str, Any]],
    answer_checks: list[dict[str, Any]],
) -> dict[str, Any]:
    provenance_sha = index_data.get("provenance", {}).get("answer", {}).get("sha256")
    mismatches = [check for check in answer_checks if not check["match"]]
    if mismatches:
        raise ValueError(f"index/DOM answer mismatches: {mismatches}")
    return {
        "source_html": source_path_for_report(html_path),
        "source_html_sha256": digest,
        "index_provenance_sha256": provenance_sha,
        "index_provenance_sha256_matches": provenance_sha == digest,
        "expected": len(statuses),
        "extracted": len(statuses),
        "suspicious": sum(item["status"] == "suspicious" for item in statuses),
        "missing": [],
        "numbered_heading_ids": sorted(headings),
        "choice_container_count": len(main.select("div.choice-container")),
        "comprehensive_answer_container_count": len(
            main.select("div.answer-container")
        ),
        "choice_answer_cross_check": {
            "compared": len(answer_checks),
            "matched": len(answer_checks) - len(mismatches),
            "mismatches": mismatches,
        },
        "questions": statuses,
    }


def extract_year(year: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    index_data, html_path, main, headings, entries = _load_year_inputs(year)
    digest = sha256(html_path)
    records = []
    statuses = []
    answer_checks = []
    for number, entry in sorted(entries.items()):
        record, status, answer_check = _extract_question(
            year,
            number,
            entry,
            headings[number],
            html_path,
            digest,
        )
        records.append(record)
        statuses.append(status)
        if answer_check is not None:
            answer_checks.append(answer_check)
    report = _year_report(
        index_data,
        html_path,
        main,
        headings,
        digest,
        statuses,
        answer_checks,
    )
    return records, report


def excerpt(text: str, limit: int = 120) -> str:
    return clean_inline(text)[:limit]


def build_deck_map(records_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    units: list[dict[str, Any]] = []
    if DECK_DIR is None or WORKSPACE is None:
        raise RuntimeError("workspace has not been configured")
    deck_files = sorted(DECK_DIR.glob("*.md"))
    indexes = {
        year: {entry["question_id"]: entry for entry in data["entries"]}
        for year, data in REGISTERED_INDEXES.items()
    }

    for deck_file in deck_files:
        content = deck_file.read_text(encoding="utf-8")
        location_section = re.search(
            r"^## 真题定位[^\n]*\n(?P<body>.*?)(?=^## |\Z)",
            content,
            flags=re.MULTILINE | re.DOTALL,
        )
        if location_section is None:
            raise ValueError(f"{deck_file.name}: missing 真题定位 section")
        qids = list(
            dict.fromkeys(QUESTION_ID_RE.findall(location_section.group("body")))
        )
        unknown = [qid for qid in qids if qid not in records_by_id]
        if unknown:
            raise ValueError(f"{deck_file.name}: unknown question ids: {unknown}")
        questions = []
        for qid in qids:
            record = records_by_id[qid]
            index_entry = indexes[record["exam_year"]][qid]
            questions.append(
                {
                    "question_id": qid,
                    "exam_year": record["exam_year"],
                    "number": record["number"],
                    "marks": record["marks"],
                    "locator_page": index_entry.get("locator", {}).get("page"),
                    "stem_excerpt_120": excerpt(record["stem"]),
                }
            )
        units.append(
            {
                "knowledge_unit_id": deck_file.stem,
                "deck_file": deck_file.relative_to(WORKSPACE.root).as_posix(),
                "question_count": len(questions),
                "questions": questions,
            }
        )
    return {
        "schema_version": 1,
        "quotation_limit_chars": 120,
        "unit_count": len(units),
        "units": units,
    }


def write_outputs(records: list[dict[str, Any]], report: dict[str, Any]) -> None:
    if QUESTION_DIR is None or DECK_MAP is None:
        raise RuntimeError("workspace has not been configured")
    QUESTION_DIR.mkdir(parents=True, exist_ok=True)
    expected_txt_names = {f"{record['question_id']}.txt" for record in records}
    unexpected_txt = sorted(
        path.name
        for path in QUESTION_DIR.glob("cs408-*.txt")
        if path.name not in expected_txt_names
    )
    if unexpected_txt:
        raise ValueError(f"unexpected existing question text files: {unexpected_txt}")

    for record in records:
        body = record["stem"]
        if record["options"]:
            body += "\n\n" + "\n".join(
                f"{label}. {text}"
                for label, text in zip("ABCD", record["options"], strict=True)
            )
        (QUESTION_DIR / f"{record['question_id']}.txt").write_text(
            body + "\n", encoding="utf-8", newline="\n"
        )

    (QUESTION_DIR / "questions_index.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (QUESTION_DIR / "extraction_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    deck_map = build_deck_map(
        {record["question_id"]: record for record in records}
    )
    DECK_MAP.write_text(
        json.dumps(deck_map, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _configure_workspace(workspace: Workspace) -> None:
    global WORKSPACE, QUIZ_DIR, QUESTION_DIR, DECK_DIR, DECK_MAP
    WORKSPACE = workspace
    raw_root = workspace.require("materials.raw_root")
    product_root = workspace.require("products.cs408_lecture_workspace")
    QUIZ_DIR = raw_root / "cs408" / "quiz_pages"
    QUESTION_DIR = product_root / "questions"
    DECK_DIR = product_root / "deck"
    DECK_MAP = product_root / "deck_question_map.json"
    for path in workspace.require_all("reference.exam_indexes.cs408"):
        document = json.loads(path.read_text(encoding="utf-8"))
        REGISTERED_INDEXES[int(document["exam_year"])] = document


def _extract_registered_years() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records = []
    reports = {}
    for year in sorted(REGISTERED_INDEXES):
        year_records, report = extract_year(year)
        records.extend(year_records)
        reports[str(year)] = report
    return records, reports


def _sample_rows(
    records: list[dict[str, Any]],
    reports: dict[str, Any],
) -> list[dict[str, Any]]:
    samples = []
    records_by_year: dict[int, list[dict[str, Any]]] = {}
    for record in records:
        records_by_year.setdefault(record["exam_year"], []).append(record)
    ordered_years = sorted(records_by_year)
    sample_records = []
    first_year_records = sorted(
        records_by_year[ordered_years[0]], key=lambda item: item["number"]
    )
    first_choice = next(
        record for record in first_year_records
        if record["question_type"] == "single_choice"
    )
    first_other = next(
        (record for record in first_year_records
         if record["question_type"] != "single_choice"),
        first_year_records[-1],
    )
    sample_records.extend((first_choice, first_other))
    for year in ordered_years[1:]:
        sample_records.append(
            max(records_by_year[year], key=lambda item: item["number"])
        )
    for record in sample_records:
        year = record["exam_year"]
        status = next(
            question
            for question in reports[str(year)]["questions"]
            if question["question_id"] == record["question_id"]
        )
        samples.append(
            {
                "question_id": record["question_id"],
                "number": record["number"],
                "html_heading_id": status["heading_id"],
                "typed_boundary_id": status["boundary_id"],
                "option_labels": status["option_labels"],
                "stem_excerpt_120": excerpt(record["stem"]),
                "number_matches_heading": str(record["number"])
                == status["heading_id"],
            }
        )
    return samples


def _report_alignment(records: list[dict[str, Any]], reports: dict[str, Any]):
    expected = sum(len(document["entries"]) for document in REGISTERED_INDEXES.values())
    samples = _sample_rows(records, reports)
    choice_questions = sum(
        entry["question_type"] == "single_choice"
        for document in REGISTERED_INDEXES.values()
        for entry in document["entries"]
    )
    matched_answers = sum(
        year["choice_answer_cross_check"]["matched"] for year in reports.values()
    )
    all_numbers_match = all(
        report["numbered_heading_ids"]
        == sorted(int(entry["number"]) for entry in REGISTERED_INDEXES[int(year)]["entries"])
        for year, report in reports.items()
    )
    all_option_labels_match = all(
        status["option_labels"] == list("ABCD")
        for year_report in reports.values()
        for status in year_report["questions"]
        if status["option_labels"]
    )
    return (
        expected,
        samples,
        choice_questions,
        matched_answers,
        all_numbers_match,
        all_option_labels_match,
    )


def _build_extraction_report(
    records: list[dict[str, Any]],
    reports: dict[str, Any],
) -> dict[str, Any]:
    (expected, samples, choice_questions, matched_answers, all_numbers_match,
     all_option_labels_match) = _report_alignment(records, reports)
    return {
        "schema_version": 2,
        "method": "explicit-number DOM extraction; no positional zip alignment",
        "summary": {
            "expected": expected,
            "extracted": len(records),
            "suspicious": sum(year["suspicious"] for year in reports.values()),
            "missing": [],
            "years_complete": all(
                year["expected"] == year["extracted"] for year in reports.values()
            ),
        },
        "html_comprehensive_body_finding": {
            "present": True,
            "evidence": (
                "Each .td-content has registered non-choice headings followed by stem blocks "
                "and one answer-container before the next numbered heading."
            ),
        },
        "alignment_validation": {
            "all_index_numbers_equal_html_heading_ids": all_numbers_match,
            "all_choice_option_labels_are_abcd": all_option_labels_match,
            "all_index_answers_match_dom_answers": matched_answers == choice_questions,
            "choice_answers_matched": matched_answers,
            "choice_questions": choice_questions,
            "sample_count": len(samples),
            "samples": samples,
        },
        "failures": [],
        "limitations": [
            (
                "Text fields serialize tables, code, and inline SVG text. A source visual "
                "with no accessible text is marked explicitly and receives low confidence."
            )
        ],
        "years": reports,
    }


def _print_summary(records: list[dict[str, Any]], reports: dict[str, Any]) -> None:
    if DECK_MAP is None:
        raise RuntimeError("workspace has not been configured")
    deck_map = json.loads(DECK_MAP.read_text(encoding="utf-8"))
    print(f"records={len(records)} deck_units={deck_map['unit_count']}")
    for year, item in sorted(reports.items()):
        print(
            f"{year}: expected={item['expected']} extracted={item['extracted']} "
            f"suspicious={item['suspicious']} answers="
            f"{item['choice_answer_cross_check']['matched']}/"
            f"{item['choice_answer_cross_check']['compared']}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path)
    args = parser.parse_args()
    _configure_workspace(load_workspace(args.workspace))
    records, reports = _extract_registered_years()
    question_ids = [record["question_id"] for record in records]
    if len(question_ids) != len(set(question_ids)):
        raise ValueError("duplicate question ids in extracted records")
    write_outputs(records, _build_extraction_report(records, reports))
    _print_summary(records, reports)


if __name__ == "__main__":
    main()
