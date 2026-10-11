"""M21 question-extraction verifier; see ``contracts/workspace.md``.

Public interface: CLI ``main()``. Registered indexes define expected records; inline source paths
resolve from ``Workspace.root`` and source papers must be under the registered raw-material root.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

from bs4 import BeautifulSoup, Tag

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from ky.workspace import load_workspace  # noqa: E402

REQUIRED_FIELDS = {
    "question_id",
    "exam_year",
    "number",
    "question_type",
    "marks",
    "stem",
    "options",
    "answer",
    "source_html",
    "source_html_sha256",
    "extraction_method",
    "confidence",
}
QUESTION_ID = re.compile(r"cs408-\d{4}-\d{2}")


def clean(text: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        text.replace("\u00a0", " ").replace("\u202f", " "),
    ).strip()


def first_source_text(heading: Tag, boundary: Tag) -> str:
    node = heading.next_sibling
    while node is not None and node is not boundary:
        if isinstance(node, Tag):
            text = clean(node.get_text(" ", strip=True))
            if text:
                return text
        node = node.next_sibling
    return ""


def _read_registered_indexes(paths: tuple[Path, ...]) -> dict[int, dict]:
    result = {}
    for path in paths:
        document = json.loads(path.read_text(encoding="utf-8"))
        result[int(document["exam_year"])] = document
    return result


def _verify_year(
    year: int,
    expected: dict,
    records: list[dict],
    sample_ids: set[str],
    question_dir: Path,
    workspace_root: Path,
    raw_root: Path,
) -> tuple[int, int, set[str]]:
    assert all(entry["exam_year"] == year for entry in expected["entries"])
    assert all(record["exam_year"] == year for record in records)
    expected_by_id = {entry["question_id"]: entry for entry in expected["entries"]}
    records_by_id = {record["question_id"]: record for record in records}
    assert records_by_id.keys() == expected_by_id.keys()
    assert all(REQUIRED_FIELDS <= record.keys() for record in records)
    assert {record["number"] for record in records} == {
        entry["number"] for entry in expected["entries"]
    }
    expected_choices = {
        entry["question_id"]
        for entry in expected["entries"]
        if entry["question_type"] == "single_choice"
    }
    choice_records = [
        record for record in records if record["question_id"] in expected_choices
    ]
    assert all(len(record["options"]) == 4 for record in choice_records)
    assert all(
        not record["options"] for record in records if record not in choice_records
    )

    source_path = workspace_root / records[0]["source_html"]
    assert source_path.is_relative_to(raw_root)
    source_digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
    assert all(record["source_html"] == records[0]["source_html"] for record in records)
    assert all(record["source_html_sha256"] == source_digest for record in records)
    soup = BeautifulSoup(source_path.read_text(encoding="utf-8"), "lxml")
    main = soup.select_one(".td-content")
    assert main is not None
    headings = {
        int(heading["id"]): heading
        for heading in main.find_all("h5", id=re.compile(r"^\d+$"))
    }
    expected_numbers = {int(entry["number"]) for entry in expected["entries"]}
    assert set(headings) == expected_numbers
    assert len(main.select("div.choice-container")) == len(expected_choices)
    assert len(main.select("div.answer-container")) == (
        len(records) - len(expected_choices)
    )

    answer_matches = 0
    for record in records:
        answer_matches += _verify_record(
            record,
            expected_by_id[record["question_id"]],
            headings[int(record["number"])],
            question_dir,
            record["question_id"] in sample_ids,
        )
    return len(expected_choices), answer_matches, sample_ids


def _verify_record(
    record: dict,
    expected: dict,
    heading: Tag,
    question_dir: Path,
    is_sample: bool,
) -> int:
    assert record["question_id"] == expected["question_id"]
    assert record["number"] == expected["number"]
    assert record["exam_year"] == expected["exam_year"]
    assert record["question_type"] == expected["question_type"]
    assert record["marks"] == expected.get("marks")
    is_choice = expected["question_type"] == "single_choice"
    boundary_class = "choice-container" if is_choice else "answer-container"
    node = heading.next_sibling
    boundary = None
    while node is not None:
        if isinstance(node, Tag):
            if node.name in {"h3", "h4", "h5"}:
                break
            if boundary_class in (node.get("class") or []):
                boundary = node
                break
        node = node.next_sibling
    assert boundary is not None
    answer_matches = 0
    if is_choice:
        labels = [
            clean(item.get_text(" ", strip=True)).rstrip(".．、")
            for item in boundary.select(".choice-label")
        ]
        assert labels == list("ABCD")
        answer_node = boundary.select_one(".correct-answer-text")
        assert answer_node is not None
        answer_match = re.search(
            r"([ABCD])\s*$", clean(answer_node.get_text(" ", strip=True))
        )
        assert answer_match is not None
        assert answer_match.group(1) == record["answer"] == expected.get("answer")
        answer_matches = 1
    if is_sample:
        excerpt = first_source_text(heading, boundary)
        assert excerpt
        assert excerpt[:80] in clean(record["stem"])
    body = record["stem"]
    if record["options"]:
        body += "\n\n" + "\n".join(
            f"{label}. {option}"
            for label, option in zip("ABCD", record["options"], strict=True)
        )
    text_path = question_dir / f"{record['question_id']}.txt"
    assert text_path.read_text(encoding="utf-8") == body + "\n"
    return answer_matches


def _verify_year_records(
    records: list[dict], expected_by_year: dict[int, dict], question_dir: Path,
    workspace_root: Path, raw_root: Path,
):
    records_by_year: dict[int, list[dict]] = {}
    for record in records:
        records_by_year.setdefault(record["exam_year"], []).append(record)
    assert set(records_by_year) == set(expected_by_year)
    samples_by_year = {
        year: {
            min(entry["question_id"] for entry in expected["entries"])
        }
        for year, expected in expected_by_year.items()
    }
    final_year = max(expected_by_year)
    final_ids = [
        entry["question_id"]
        for entry in expected_by_year[final_year]["entries"]
    ]
    samples_by_year[final_year].add(max(final_ids))
    answer_total = 0
    answer_matches = 0
    sample_ids: set[str] = set()
    for year, expected in expected_by_year.items():
        year_total, year_matches, year_samples = _verify_year(
            year,
            expected,
            records_by_year[year],
            samples_by_year[year],
            question_dir,
            workspace_root,
            raw_root,
        )
        answer_total += year_total
        answer_matches += year_matches
        sample_ids.update(year_samples)
        confidence = Counter(
            record["confidence"] for record in records_by_year[year]
        )
        print(
            f"{year}: {len(records_by_year[year])}/{len(expected['entries'])} "
            f"confidence={dict(confidence)}"
        )
    return sample_ids, answer_total, answer_matches


def _verify_record_summary(
    records: list[dict], report: dict, sample_ids: set[str],
    answer_total: int, answer_matches: int, question_dir: Path,
):
    record_ids = {record["question_id"] for record in records}
    assert len(records) == len(record_ids)
    text_files = list(question_dir.glob("cs408-*.txt"))
    assert len(text_files) == len(records)
    summary = report["summary"]
    assert summary["expected"] == len(records)
    assert summary["extracted"] == len(records)
    assert summary["missing"] == []
    assert summary["years_complete"] is True
    suspicious = sum(
        item["status"] == "suspicious"
        for year_report in report["years"].values()
        for item in year_report["questions"]
    )
    assert summary["suspicious"] == suspicious
    report_questions = sum(
        len(year_report["questions"])
        for year_report in report["years"].values()
    )
    assert report_questions == len(records)
    assert sample_ids
    return record_ids, len(text_files), answer_total, answer_matches, len(sample_ids)


def _verify_records(
    records: list[dict],
    report: dict,
    expected_by_year: dict[int, dict],
    question_dir: Path,
    workspace_root: Path,
    raw_root: Path,
) -> tuple[set[str], int, int, int, int]:
    sample_ids, answer_total, answer_matches = _verify_year_records(
        records, expected_by_year, question_dir, workspace_root, raw_root,
    )
    return _verify_record_summary(
        records, report, sample_ids, answer_total, answer_matches, question_dir,
    )


def _verify_deck_map(
    product_root: Path,
    workspace_root: Path,
    record_ids: set[str],
) -> int:
    deck_map = json.loads(
        (product_root / "deck_question_map.json").read_text(encoding="utf-8")
    )
    assert deck_map["unit_count"] == len(deck_map["units"])
    assert all(
        len(question["stem_excerpt_120"]) <= 120
        for unit in deck_map["units"]
        for question in unit["questions"]
    )
    assert all(
        question["question_id"] in record_ids
        for unit in deck_map["units"]
        for question in unit["questions"]
    )
    for unit in deck_map["units"]:
        deck_path = workspace_root / unit["deck_file"]
        content = deck_path.read_text(encoding="utf-8")
        location = re.search(
            r"^## 真题定位[^\n]*\n(?P<body>.*?)(?=^## |\Z)",
            content,
            flags=re.MULTILINE | re.DOTALL,
        )
        assert location is not None
        listed = list(dict.fromkeys(QUESTION_ID.findall(location.group("body"))))
        actual = [question["question_id"] for question in unit["questions"]]
        assert actual == listed
    return len(deck_map["units"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path)
    args = parser.parse_args()
    workspace = load_workspace(args.workspace)
    product_root = workspace.require("products.cs408_lecture_workspace")
    question_dir = product_root / "questions"
    records = json.loads(
        (question_dir / "questions_index.json").read_text(encoding="utf-8")
    )
    report = json.loads(
        (question_dir / "extraction_report.json").read_text(encoding="utf-8")
    )
    expected = _read_registered_indexes(
        workspace.require_all("reference.exam_indexes.cs408")
    )
    raw_root = workspace.require("materials.raw_root")
    (
        record_ids,
        text_count,
        answer_total,
        answer_matches,
        sample_count,
    ) = _verify_records(
        records,
        report,
        expected,
        question_dir,
        workspace.root,
        raw_root,
    )
    deck_units = _verify_deck_map(product_root, workspace.root, record_ids)
    per_year = {year: len(data["entries"]) for year, data in expected.items()}
    per_year_count = (
        next(iter(per_year.values()))
        if len(set(per_year.values())) == 1
        else per_year
    )
    print(
        f"PASS: records={len(records)} txt={text_count} per_year={per_year_count} "
        f"choice_answers={answer_matches}/{answer_total} samples={sample_count} "
        f"deck_units={deck_units}"
    )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
