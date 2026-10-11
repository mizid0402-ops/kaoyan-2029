"""Build the 408 per-question index: question numbers, types, marks and answer letters.

Deliberately narrow, for two reasons:

  1. **The mapping method is not decided yet** (the user paused it), so this tool emits
     no knowledge-point assignment at all. Structure + answers are needed by every
     candidate method, so this work cannot be wasted.
  2. **Nothing from a question may be stored.** The only per-question fields written are
     the year, the number, the type, the marks, and a single answer letter. The question
     text, its options and any explanation are read, used positionally, and dropped.

Where the facts come from:

  * numbers/pages      : `cache/exam_probe/neville_2024_skeleton.json`, itself produced by
                         reading the registered paper PDF; the PDF's sha256 is checked here.
  * type and marks     : the 408 paper's own fixed structure (单项选择题 1-40, 2 marks each;
                         综合应用题 41-47, 70 marks split across them) — recorded as
                         derived-by-rule, not as something read off a page.
  * answer letters     : the registered answer scan's first page. **Read by a vision pass,
                         hand-transcribed into this file, and NOT independently verified** —
                         so every row is stamped `answer_confidence: unverified`, and the
                         whole file carries `calibration: awaiting_official_book`.

Usage:  py -3.12 tools/archive/build_408_index.py [--out data/exam_questions/408_index_2024.json]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKELETON = ROOT / "cache" / "exam_probe" / "neville_2024_skeleton.json"
PAPER = ROOT / "data" / "raw_materials" / "cs408" / "past_papers_thirdparty" / "408_2024_paper_rebuild.pdf"
ANSWER = ROOT / "data" / "raw_materials" / "cs408" / "past_papers_thirdparty" / "408_2024_answer_scan.pdf"

EXPECTED_PAPER_SHA = "baae7ba96588d55117a31c297304927d3791d0f3576bf0c70f32fd8a9fe1766c"
EXPECTED_ANSWER_SHA = "83146d04e95bdf2e7a58b6157a2ba00029c7b4268f1937bedd740ae7f1868523"

# 408 paper structure — rules, not readings. 40 单选 x 2 分 = 80; 综合应用 70 分 (题量随年份变化).
CHOICE_COUNT = 40
CHOICE_MARKS_EACH = 2
ESSAY_TOTAL_MARKS = 70

# Hand-transcribed from the answer scan's page-1 quick-answer table (01-40).
# This is the ONLY reason every row is marked unverified.
ANSWERS_2024 = {
    1: "D", 2: "A", 3: "A", 4: "B", 5: "D", 6: "A", 7: "D", 8: "A", 9: "B", 10: "C",
    11: "D", 12: "B", 13: "B", 14: "C", 15: "D", 16: "D", 17: "C", 18: "B", 19: "C", 20: "B",
    21: "A", 22: "C", 23: "A", 24: "A", 25: "D", 26: "A", 27: "A", 28: "B", 29: "A", 30: "C",
    31: "C", 32: "C", 33: "B", 34: "C", 35: "D", 36: "B", 37: "D", 38: "D", 39: "C", 40: "D",
}

# Cross-check performed 2026-09-13 against a second, independent transcription of the same
# answer table (a rehost that has since been deleted at the user's instruction). Only the
# questions actually compared are listed, so the claim stays as narrow as the evidence.
CROSSCHECKED = list(range(1, 16))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "exam_questions" / "408_index_2024.json")
    args = ap.parse_args()

    if not PAPER.is_file() or not ANSWER.is_file():
        print("registered source files missing; run tools/migrations/register_408_source.py first", file=sys.stderr)
        return 2
    paper_sha, answer_sha = sha(PAPER), sha(ANSWER)
    if paper_sha != EXPECTED_PAPER_SHA or answer_sha != EXPECTED_ANSWER_SHA:
        print(f"source sha256 changed: paper={paper_sha[:16]} answer={answer_sha[:16]}", file=sys.stderr)
        return 1
    if not SKELETON.is_file():
        print(f"missing skeleton: {SKELETON}", file=sys.stderr)
        return 2

    skeleton = json.loads(SKELETON.read_text(encoding="utf-8"))
    located = {entry["number"]: entry for entry in skeleton["question_lines"]}
    numbers = sorted(located)
    if numbers != list(range(1, len(numbers) + 1)):
        print(f"skeleton numbering is not contiguous: {len(numbers)} entries", file=sys.stderr)
        return 1

    essay_numbers = [n for n in numbers if n > CHOICE_COUNT]
    # spread the 70 essay marks as evenly as the paper does (first questions get the extra mark)
    base, extra = divmod(ESSAY_TOTAL_MARKS, len(essay_numbers))
    essay_marks = {n: base + (1 if i < extra else 0) for i, n in enumerate(essay_numbers)}

    entries = []
    for number in numbers:
        is_choice = number <= CHOICE_COUNT
        entries.append({
            "question_id": f"cs408-2024-{number:02d}",
            "exam_year": 2024,
            "subject_id": "cs408",
            "number": number,
            "question_type": "single_choice" if is_choice else "comprehensive_application",
            "marks": CHOICE_MARKS_EACH if is_choice else essay_marks[number],
            "answer": ANSWERS_2024.get(number) if is_choice else None,
            "answer_kind": "letter" if is_choice else None,
            "answer_confidence": "unverified",
            "answer_sources": [
                {
                    "resource_id": "cs408-answer-2024-scan",
                    "sha256": answer_sha,
                    "cross_checked_with": "独立转录来源（已于 2026-09-13 按用户指示删除，故仅存记录）"
                    if number in CROSSCHECKED else None,
                }
            ],
            "locator": {
                "paper_sha256": paper_sha,
                "page": located[number]["page"],
                "line": located[number]["line"],
            },
            "knowledge_point_id": None,
            "knowledge_point_status": "not_assigned",
            "notes": None,
        })

    payload = {
        "schema_version": 1,
        "kind": "exam_question_index",
        "exam_year": 2024,
        "subject_id": "cs408",
        "question_count": len(entries),
        "marks_total": sum(e["marks"] for e in entries),
        "answer_source_coverage": {
            "choice_answered": sum(1 for e in entries if e["answer"]),
            "choice_total": CHOICE_COUNT,
            "cross_checked": len(CROSSCHECKED),
            "cross_checked_numbers": CROSSCHECKED,
        },
        "calibration": "awaiting_official_book",
        "provenance": {
            "paper": {
                "resource_id": "cs408-paper-2024-rebuild",
                "sha256": paper_sha,
                "source_tier": "community_archive",
                "note": "社区重排版（文字版），非官方原卷",
            },
            "answer": {
                "resource_id": "cs408-answer-2024-scan",
                "sha256": answer_sha,
                "source_tier": "community_archive",
                "rights_status": "unknown",
                "note": "扫描件，原始发布者不明；仅可本地自用",
            },
        },
        "content_policy": (
            "本文件只含年份/题号/题型/分值/答案字母/页码行号；"
            "题干、选项、解析原文一律未采集、未存储。"
        ),
        "verified_facts": [
            "47 道题号连续 1..47，无缺号无重号（由 paper 的文本层机械抽取）",
            "分值合计 150（40*2 + 70）",
        ],
        "unverified_facts": [
            "全部 40 个答案字母未经独立复核（仅据答案扫描件首页人工转录）",
            "重排版的题目文字与官方原卷是否逐字一致，未知；待官方 2026 版大纲到货后比对",
            "41-47 题的分值分布是按总分的规则摊派，不是从卷面读到的",
        ],
        "entries": entries,
    }
    out = args.out if args.out.is_absolute() else ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )

    print(f"entries      : {len(entries)}  (单选 {CHOICE_COUNT} + 综合 {len(essay_numbers)})")
    print(f"marks total  : {payload['marks_total']}")
    print(f"answers      : {payload['answer_source_coverage']['choice_answered']}/40, "
          f"cross-checked {len(CROSSCHECKED)}")
    print(f"knowledge pt : all null ({payload['entries'][0]['knowledge_point_status']})")
    print(f"wrote        : {out.relative_to(ROOT).as_posix()}  ({out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
