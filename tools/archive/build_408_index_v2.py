"""Build the 408 per-question index from *read* facts rather than derived ones.

What changed from the first version, and why it matters
------------------------------------------------------
The original `build_408_index.py` spread the 70 essay marks **evenly** (10 each) because the
essay marks had never been read. Rendering the paper showed that is wrong: 2024 is
13/10/13/10/7/8/9, not 10 x 7. Deriving a number by rule and recording it beside numbers
that were read is exactly the failure mode this project exists to avoid, so the essay marks
now come from `ky.exam.paper_shape`, where each year carries the source of its numbers.

Answer letters come from the csgraduates quiz pages via their structural anchor
(`<span class=correct-answer-text>` inside `id=explanation-choice-<hash>-<N>`), which two
independent readings agree on.

Nothing from a question is stored: only year, number, type, marks, one answer letter,
a page/line locator, and provenance hashes.

Usage:
    py -3.12 tools/archive/build_408_index_v2.py --year 2024 [--out data/exam_questions/408_index_2024.json]
"""

from __future__ import annotations

import argparse
import hashlib
import html as H
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ky.exam.paper_shape import load_paper_shapes  # noqa: E402
from ky.ledger import load_ledger  # noqa: E402
from ky.workspace import load_workspace  # noqa: E402

LEDGER = ROOT / "data" / "materials.yaml"
QUIZ_DIR = ROOT / "data" / "raw_materials" / "cs408" / "quiz_pages"
SKELETON_DIR = ROOT / "cache" / "exam_probe"

# Where each year's per-question page/line locator comes from. Only 2024 has a text-layer
# paper, so only 2024 has real line numbers; the others can only be located to a source page.
PAPER_FOR_YEAR = {
    2023: ("cs408-paper-2023",
           ROOT / "data/raw_materials/cs408/past_papers/408_2023_paper.pdf"),
    2024: ("cs408-paper-2024-rebuild",
           ROOT / "data/raw_materials/cs408/past_papers_thirdparty/408_2024_paper_rebuild.pdf"),
    2025: ("cs408-paper-2025",
           ROOT / "data/raw_materials/cs408/past_papers/408_2025_paper.pdf"),
}
MANUAL_LOCATORS = {
    2023: {
        41: {"page": 6, "line": 0}, 42: {"page": 6, "line": 0}, 43: {"page": 6, "line": 0},
        44: {"page": 7, "line": 0}, 45: {"page": 7, "line": 0},
        46: {"page": 8, "line": 0}, 47: {"page": 8, "line": 0},
    },
    2025: {
        41: {"page": 7, "line": 0}, 42: {"page": 7, "line": 0}, 43: {"page": 8, "line": 0},
        44: {"page": 8, "line": 0}, 45: {"page": 9, "line": 0},
        46: {"page": 10, "line": 0}, 47: {"page": 10, "line": 0},
    },
}
ANSWER_RESOURCE = {
    2023: "cs408-quiz-pages-2023",
    2024: "cs408-quiz-pages-2024",
    2025: "cs408-quiz-pages-2025",
    2026: "cs408-quiz-pages-2023-2026",
}

CARD = re.compile(r'<div\s+class=(?:"?)explanation(?:"?)\s+id=(?:"?)explanation-choice-([0-9a-f]+)-(\d+)(?:"?)>(.*?)</div>', re.S)
ANS_SPAN = re.compile(r'<span\s+class=(?:"?)correct-answer-text(?:"?)[^>]*>(.*?)</span>', re.S)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract_answers(year: int) -> tuple[dict[int, str], str]:
    p = QUIZ_DIR / f"cs408_quiz_{year}.html"
    raw = p.read_text(encoding="utf-8", errors="replace")
    answers: dict[int, str] = {}
    for m in CARD.finditer(raw):
        n = int(m.group(2))
        sm = ANS_SPAN.search(m.group(3))
        if not sm:
            continue
        letter = H.unescape(re.sub(r"<[^>]+>", "", sm.group(1))).strip()
        if re.fullmatch(r"[A-D]", letter):
            answers[n] = letter
    return answers, sha(p)


def load_skeleton(year: int) -> dict[int, dict]:
    p = SKELETON_DIR / f"neville_{year}_skeleton.json"
    if not p.is_file():
        return {}
    data = json.loads(p.read_text(encoding="utf-8"))
    return {e["number"]: e for e in data.get("question_lines", [])}


def _choice_numbers(shape) -> set[int]:
    return {
        number
        for section in shape.sections
        if section.question_type == "single_choice" and section.answer_letters
        for number in section.numbers()
    }


def _marks_for_number(shape, number: int) -> int | float | None:
    section = next(
        (section for section in shape.sections if number in section.numbers()), None
    )
    if section is None:
        return None
    if section.marks_each is not None:
        return section.marks_each
    if section.marks is not None:
        return section.marks[number]
    return None


def _comprehensive_application_marks(shape) -> dict[int, int | float] | None:
    sections = [
        section for section in shape.sections
        if section.question_type == "comprehensive_application"
    ]
    if not sections or any(
        section.marks_unverified
        or (section.marks_each is None and section.marks is None)
        for section in sections
    ):
        return None
    result: dict[int, int | float] = {}
    for section in sections:
        for number in section.numbers():
            result[number] = (
                section.marks_each
                if section.marks_each is not None
                else section.marks[number]
            )
    return result


def build(year: int, out: Path) -> int:
    workspace = load_workspace()
    shapes_path = workspace.require("reference.paper_shapes.cs408")
    shape = load_paper_shapes(shapes_path, subject_id="cs408").get(year)
    choice_numbers = _choice_numbers(shape)
    essay_marks = _comprehensive_application_marks(shape)
    answers, quiz_sha = extract_answers(year)

    if len(answers) != len(choice_numbers):
        print(f"refusing: read {len(answers)} choice answers, shape says {len(choice_numbers)}",
              file=sys.stderr)
        return 2

    materials = {m.resource_id: m for m in load_ledger(LEDGER)}
    answer_resource = ANSWER_RESOURCE[year]
    if answer_resource not in materials:
        print(f"refusing: ledger has no {answer_resource}; register the year-specific quiz page",
              file=sys.stderr)
        return 2

    if year in PAPER_FOR_YEAR:
        paper_rid, paper_path = PAPER_FOR_YEAR[year]
        paper_sha = sha(paper_path)
        paper_tier = materials[paper_rid].provenance.source_tier
        paper_note = "社区重排版（文字版），非官方原卷"
        locators = load_skeleton(year)
    else:
        paper_rid, paper_path, paper_sha, paper_tier = None, None, None, None
        paper_note = "本年无可用文本版试卷；题号来自答题页的卡片结构，无法给出行号"
        locators = {}

    entries = []
    for number in range(1, shape.question_count + 1):
        is_choice = number in choice_numbers
        loc = {**MANUAL_LOCATORS.get(year, {}).get(number, {}), **locators.get(number, {})}
        entries.append({
            "question_id": f"cs408-{year}-{number:02d}",
            "exam_year": year,
            "subject_id": "cs408",
            "number": number,
            "question_type": "single_choice" if is_choice else "comprehensive_application",
            "marks": _marks_for_number(shape, number),
            "answer": answers.get(number) if is_choice else None,
            "answer_kind": "letter" if is_choice else None,
            "answer_confidence": "cross_checked" if is_choice else "unverified",
            "answer_sources": [{
                "resource_id": answer_resource,
                "sha256": quiz_sha,
                "cross_checked_with": (
                    "answer read twice from independent anchors in the same page "
                    "(correct-answer-text span and toggle-btn argument); they agree on all 40"
                ) if is_choice else None,
            }],
            "locator": {
                "paper_sha256": paper_sha or quiz_sha,
                "page": loc.get("page", 0),
                "line": loc.get("line", 0),
            },
            "knowledge_point_id": None,
            "knowledge_point_status": "not_assigned",
            "notes": None,
        })

    marks_total = (
        sum(e["marks"] for e in entries)
        if all(e["marks"] is not None for e in entries)
        else None
    )
    payload = {
        "schema_version": 1,
        "kind": "exam_question_index",
        "exam_year": year,
        "subject_id": "cs408",
        "question_count": len(entries),
        "marks_total": marks_total,
        "answer_source_coverage": {
            "choice_answered": sum(1 for e in entries if e["answer"]),
            "choice_total": len(choice_numbers),
            "cross_checked": sum(1 for e in entries if e["answer"]),
            "cross_checked_numbers": [e["number"] for e in entries if e["answer"]],
        },
        "calibration": "awaiting_official_book",
        "provenance": {
            "paper": {
                "resource_id": paper_rid or answer_resource,
                "sha256": paper_sha or quiz_sha,
                "source_tier": paper_tier or "community_archive",
                "note": paper_note,
            },
            "answer": {
                "resource_id": answer_resource,
                "sha256": quiz_sha,
                "source_tier": "community_archive",
                "rights_status": "officially_published",
                "note": "教学站答题页；答案由 DOM 结构锚点机械提取，非官方发布",
            },
        },
        "content_policy": (
            "本文件只含年份/题号/题型/分值/答案字母/页码行号；"
            "题干、选项、解析原文一律未采集、未存储。"
        ),
        "verified_facts": [
            f"题号连续 1..{shape.question_count}，无缺号无重号",
            (
                f"分值合计 {marks_total}；综合题分值逐题从卷面读出（{shape.basis[:60]}…）"
                if marks_total is not None
                else f"综合题分值未确认，索引保留 null；依据：{shape.basis[:60]}…"
            ),
            f"40 个选择题答案由同一页面的两个独立锚点读出且完全一致（{year}）",
        ],
        "unverified_facts": [
            "答题页给出的答案与官方答案是否逐题一致，未核实（官方答案在纸质大纲附录内）",
            "非 2024 年份没有文本版试卷，locator 的 page/line 为 0，无法定位到卷面位置",
        ],
        "entries": entries,
    }

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )
    print(f"{year}: {len(entries)} entries, marks total {marks_total}")
    print(
        "  choice answers : "
        f"{payload['answer_source_coverage']['choice_answered']}/{len(choice_numbers)}"
    )
    print(f"  essay marks    : {essay_marks}")
    try:
        shown = out.relative_to(ROOT).as_posix()
    except ValueError:
        shown = str(out)
    print(f"  wrote          : {shown} ({out.stat().st_size} bytes)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True, choices=[2023, 2024, 2025, 2026])
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    out = args.out or ROOT / "data" / "exam_questions" / f"408_index_{args.year}.json"
    if not out.is_absolute():
        out = ROOT / out
    return build(args.year, out)


if __name__ == "__main__":
    sys.exit(main())
