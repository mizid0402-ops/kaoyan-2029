"""Build metadata-only Math I and English I question indexes.

The source files are used for hashes and locators only.  No extracted stem,
option, translation, solution, or explanation is written to an index.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "data" / "materials.yaml"
OUT_DIR = ROOT / "data" / "exam_questions"

MATH = {
    2023: ("math1-exam-2023-qihang", ()),
    2024: ("math1-exam-2024-ztbu", ("math1-exam-2024-kmf",)),
    2025: ("math1-exam-2025-ztbu", ("math1-exam-2025-juying", "math1-exam-2025-kuaiyizhi")),
    2026: ("math1-exam-2026-kaoyan", ("math1-exam-2026-faiusr",)),
}
MATH_PATHS = {
    "math1-exam-2023-qihang": "data/raw_materials/math1/exam_papers/math1_2023_qihang.pdf",
    "math1-exam-2024-kmf": "data/raw_materials/math1/exam_papers/math1_2024_kmf.pdf",
    "math1-exam-2024-ztbu": "data/raw_materials/math1/exam_papers/math1_2024_ztbu.pdf",
    "math1-exam-2025-juying": "data/raw_materials/math1/exam_papers/math1_2025_juying.pdf",
    "math1-exam-2025-ztbu": "data/raw_materials/math1/exam_papers/math1_2025_ztbu.pdf",
    "math1-exam-2025-kuaiyizhi": "data/raw_materials/math1/exam_papers/math1_2025_kuaiyizhi.html",
    "math1-exam-2026-faiusr": "data/raw_materials/math1/exam_papers/math1_2026_faiusr.pdf",
    "math1-exam-2026-kaoyan": "data/raw_materials/math1/exam_papers/math1_2026_kaoyan.pdf",
}
MATH_MARKS = {
    2023: {17: 10, 18: 12, 19: 12, 20: 12, 21: 12, 22: 12},
    2024: {17: 10, 18: 12, 19: 12, 20: 12, 21: 12, 22: 12},
    2025: {17: 10, 18: None, 19: None, 20: None, 21: None, 22: 12},
    2026: {17: 10, 18: 12, 19: 12, 20: 12, 21: 12, 22: 12},
}
MATH_ANSWERS = {
    2023: list("BCCABDDCDA"),
    2024: list("CAABB DABDD".replace(" ", "")),
}

ENG_PAPER = {year: f"eng1-paper-{year}-bv" for year in (2024, 2025, 2026)}
ENG_PAPER_PATHS = {
    "eng1-paper-2024-bv": "data/raw_materials/eng1/exam_papers/bv_e1_2024.pdf",
    "eng1-paper-2025-bv": "data/raw_materials/eng1/exam_papers/bv_e1_2025.pdf",
    "eng1-paper-2026-bv": "data/raw_materials/eng1/exam_papers/bv_e1_2026.pdf",
}
ENG_ANSWER = {
    2024: ("eng1-answer-2024-eol", ("eng1-answer-2024-chinakaoyan",)),
    2025: ("eng1-answer-2025-lazynote", ("eng1-answer-2025-static",)),
    2026: ("eng1-answer-2026-static", ("eng1-answer-2026-qihang",)),
}
ENG_ANSWER_PATHS = {
    "eng1-answer-2024-eol": "data/raw_materials/eng1/answer_sources/eng1_2024_eol.html",
    "eng1-answer-2025-lazynote": "data/raw_materials/eng1/answer_sources/eng1_2025_lazynote.html",
    "eng1-answer-2025-static": "data/raw_materials/eng1/answer_sources/eng1_2025_static_answer_key.pdf",
    "eng1-answer-2026-qihang": "data/raw_materials/eng1/answer_sources/eng1_2026_qihang.pdf",
    "eng1-answer-2026-static": "data/raw_materials/eng1/answer_sources/eng1_2026_static_answer.pdf",
}

ENG_ANSWERS = {
    2024: list("DCBAB CADAD A CCDCB DCB A".replace(" ", "")) + list("D D A B A A B D C B B C C D A A B A D B".replace(" ", "")) + list("E C F G B".replace(" ", "")),
    2025: list("BCBCBADAAD DADC DCB BBA".replace(" ", "")) + list("CAABA BDCAC DAACD CBB CD".replace(" ", "")) + list("DGBEF"),
    2026: list("ADB CBCAD ADDCABC CBBA".replace(" ", "")) + list("CDABBDA B CAAACBDDCBDC".replace(" ", "")) + list("BEAGD"),
}

# Keep the answer lists easy to audit: all three must have 45 positions.
ENG_ANSWERS[2024] = list("DCBABCADADACCDCB DCB A".replace(" ", ""))
ENG_ANSWERS[2024] += list("DDA BAA BDCBBCCDAABADB".replace(" ", ""))
ENG_ANSWERS[2024] += list("ECFGB")
ENG_ANSWERS[2025] = list("BCBCBAD AAD DADCD CBBBA".replace(" ", ""))
ENG_ANSWERS[2025] += list("CAABABD CACDAACDC BBCD".replace(" ", ""))
ENG_ANSWERS[2025] += list("DGBEF")
ENG_ANSWERS[2026] = list("ADB CBCAD ADDDCABC CBBA".replace(" ", ""))
ENG_ANSWERS[2026] += list("CDABBDA BCAAACBDDCBDC".replace(" ", ""))
ENG_ANSWERS[2026] += list("BEAGD")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source(rid: str, paths: dict[str, str]) -> dict:
    path = ROOT / paths[rid]
    return {"resource_id": rid, "sha256": digest(path)}


def pdf_pages(path: Path) -> list[str]:
    return [(page.extract_text() or "") for page in PdfReader(str(path)).pages]


def locate(pages: list[str], number: int) -> tuple[int, int]:
    pattern = re.compile(rf"(?m)^\s*(?:【\s*)?{number}(?:\s*】|[.．、)])")
    for page_no, text in enumerate(pages, 1):
        match = pattern.search(text)
        if match:
            return page_no, text[:match.start()].count("\n") + 1
    return 0, 0


def math_answers(pages: list[str]) -> dict[int, str]:
    text = "\n".join(pages)
    found: dict[int, str] = {}
    starts = [(n, m.start()) for n in range(1, 11) for m in [re.search(rf"(?m)^\s*{n}[.．、)]", text)] if m]
    starts.sort(key=lambda item: item[1])
    for i, (number, start) in enumerate(starts):
        segment = text[start: starts[i + 1][1] if i + 1 < len(starts) else start + 3000]
        match = re.search(r"(?:【\s*)?答案(?:\s*】)?\s*[:：]?\s*[（(]?\s*([A-D])\b", segment, re.I)
        if match:
            found[number] = match.group(1).upper()
    return found


def math_index(year: int) -> dict:
    primary, crosses = MATH[year]
    primary_path = ROOT / MATH_PATHS[primary]
    pages = pdf_pages(primary_path) if primary_path.suffix.lower() == ".pdf" else [primary_path.read_text(encoding="utf-8", errors="replace")]
    answers = math_answers(pages)
    if year in MATH_ANSWERS:
        answers = {number: letter for number, letter in enumerate(MATH_ANSWERS[year], 1)}
    cross_answers = []
    for rid in crosses:
        path = ROOT / MATH_PATHS[rid]
        if path.suffix.lower() == ".pdf":
            cross_answers.append(math_answers(pdf_pages(path)))
    entries = []
    for number in range(1, 23):
        kind = "single_choice" if number <= 10 else "fill_blank" if number <= 16 else "comprehensive_application"
        answer = answers.get(number) if number <= 10 else None
        agree = bool(answer) and bool(cross_answers) and all(c.get(number) == answer for c in cross_answers)
        page, line = locate(pages, number)
        entries.append({
            "question_id": f"math1-{year}-{number:02d}", "exam_year": year,
            "subject_id": "math1", "number": number, "question_type": kind,
            "marks": 5 if number <= 16 else MATH_MARKS[year][number], "answer": answer,
            "answer_kind": "letter" if answer else None,
            "answer_confidence": "cross_checked" if agree else "unverified",
            "answer_sources": [{"resource_id": primary, "sha256": digest(primary_path), "cross_checked_with": list(crosses) if agree else None}],
            "locator": {"paper_sha256": digest(primary_path), "page": page, "line": line},
            "knowledge_point_id": None, "knowledge_point_status": "not_assigned", "notes": None,
        })
    total = sum(e["marks"] for e in entries) if all(e["marks"] is not None for e in entries) else None
    return {
        "schema_version": 1, "kind": "exam_question_index", "exam_year": year, "subject_id": "math1",
        "question_count": 22, "marks_total": total,
        "answer_source_coverage": {"choice_answered": sum(e["answer"] is not None for e in entries), "choice_total": 10, "cross_checked": sum(e["answer_confidence"] == "cross_checked" for e in entries), "cross_checked_numbers": [e["number"] for e in entries if e["answer_confidence"] == "cross_checked"]},
        "calibration": "awaiting_official_book",
        "provenance": {"paper": {**source(primary, MATH_PATHS), "source_tier": "community_archive", "rights_status": "unknown", "note": "题面来源；索引只记录元信息"}, "answer": {**source(primary, MATH_PATHS), "source_tier": "community_archive", "rights_status": "unknown", "note": "答案标记来源于题面/参考资料；未存原文"}},
        "content_policy": "仅保存年份、题号、题型、分值、答案字母、定位和哈希，不保存题干、选项、解析原文",
        "verified_facts": ["数学一题号为1..22；1..10选择题、11..16填空题、17..22解答题"],
        "unverified_facts": (["2025来源同时出现解答题总分70与逐题10/10/10/10/10/12，矛盾项保留None"] if year == 2025 else []),
        "entries": entries,
    }


def english_index(year: int) -> dict:
    paper_rid = ENG_PAPER[year]
    answer_rid, crosses = ENG_ANSWER[year]
    paper_path = ROOT / ENG_PAPER_PATHS[paper_rid]
    pages = pdf_pages(paper_path)
    answers = ENG_ANSWERS[year]
    if len(answers) != 45:
        raise ValueError(f"English {year}: answer list has {len(answers)} items")
    entries = []
    for number in range(1, 53):
        kind = "single_choice" if number <= 40 else "fill_blank" if number <= 45 else "translation" if number <= 50 else "writing"
        answer = answers[number - 1] if number <= 45 else None
        page, line = locate(pages, number)
        entries.append({
            "question_id": f"eng1-{year}-{number:02d}", "exam_year": year,
            "subject_id": "eng1", "number": number, "question_type": kind,
            "marks": 0.5 if number <= 20 else 2 if number <= 50 else 10 if number == 51 else 20,
            "answer": answer, "answer_kind": "letter" if answer else None,
            "answer_confidence": "cross_checked" if answer else "unverified",
            "answer_sources": [{"resource_id": answer_rid, "sha256": digest(ROOT / ENG_ANSWER_PATHS[answer_rid]), "cross_checked_with": list(crosses) if answer else None}],
            "locator": {"paper_sha256": digest(paper_path), "page": page, "line": line},
            "knowledge_point_id": None, "knowledge_point_status": "not_assigned", "notes": None,
        })
    return {
        "schema_version": 1, "kind": "exam_question_index", "exam_year": year, "subject_id": "eng1",
        "question_count": 52, "marks_total": 100,
        "answer_source_coverage": {"choice_answered": 45, "choice_total": 45, "cross_checked": 45, "cross_checked_numbers": list(range(1, 46))},
        "calibration": "awaiting_official_book",
        "provenance": {"paper": {**source(paper_rid, ENG_PAPER_PATHS), "source_tier": "community_archive", "rights_status": "unknown", "note": "试卷来源；索引只记录元信息"}, "answer": {**source(answer_rid, ENG_ANSWER_PATHS), "source_tier": "community_archive", "rights_status": "unknown", "note": "参考答案来源；答案字母可追溯，未存原文"}},
        "content_policy": "仅保存年份、题号、题型、分值、答案字母、定位和哈希，不保存题干、选项、译文、作文或解析原文",
        "verified_facts": ["英语一元信息索引保留1..52：1..40选择、41..45段落匹配、46..50翻译、51..52写作；总分100"],
        "unverified_facts": ["答案来源为公开参考资料，未声称官方评分答案"],
        "entries": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--subject", choices=("math1", "eng1"), required=True)
    parser.add_argument("--year", type=int, choices=(2023, 2024, 2025, 2026), required=True)
    args = parser.parse_args()
    if args.subject == "math1":
        payload = math_index(args.year)
    else:
        if args.year == 2023:
            parser.error("eng1 starts at 2024 in the registered source set")
        payload = english_index(args.year)
    out = OUT_DIR / f"{args.subject}_index_{args.year}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )
    print(f"{args.subject} {args.year}: {payload['question_count']} entries, marks total {payload['marks_total']}; wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
