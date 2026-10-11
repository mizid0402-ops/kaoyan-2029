"""M21 registered 408 lecture scaffold builder; see ``contracts/workspace.md``.

Public interface: ``build_scaffold(workspace)`` and CLI ``main()``. Supplementary-only nodes
carry an explicit legacy marker in every generated teaching unit that lists them (D1).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from ky.workspace import Workspace, load_workspace  # noqa: E402

LEGACY_MARKER = "【补充：非当年考纲，legacy_only_pending】"


def _is_effective(row: dict[str, str]) -> bool:
    return row.get("is_effective", "true").strip().lower() == "true"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _node_label(row: dict[str, str]) -> str:
    suffix = "" if _is_effective(row) else LEGACY_MARKER
    return f"{row['title']}{suffix}"


def _year_span(question_rows: list[dict[str, str]]) -> str:
    years = sorted({int(row["exam_year"]) for row in question_rows})
    if not years:
        return "登记索引"
    if len(years) == 1:
        return str(years[0])
    return f"{years[0]}–{years[-1]}"


def _chinese_count(number: int) -> str:
    digits = "零一二三四五六七八九"
    if number < 10:
        return digits[number]
    if number < 20:
        return f"十{digits[number % 10] if number % 10 else ''}"
    if number < 100:
        tens, ones = divmod(number, 10)
        return f"{digits[tens]}十{digits[ones] if ones else ''}"
    raise ValueError("exam index count must be less than 100")


def _has_ancestor(point_id: str, unit_id: str, nodes: dict[str, dict[str, str]]) -> bool:
    # Walks parent_id links, so a node whose id does not share the unit prefix still counts;
    # the visited set stops a cyclic parent chain instead of looping forever.
    current = point_id
    visited: set[str] = set()
    while current and current not in visited:
        visited.add(current)
        if current == unit_id:
            return True
        current = nodes.get(current, {}).get("parent_id", "")
    return False


def _unit_points(
    unit_id: str,
    nodes: dict[str, dict[str, str]],
    kp_questions: dict[str, dict[str, str]],
) -> list[str]:
    # Prefix matches come first, then tree descendants in kp_questions order (row order of
    # the question table depends on it).
    candidates = [
        point_id for point_id in kp_questions
        if point_id == unit_id or point_id.startswith(unit_id + ".")
    ]
    for point_id in kp_questions:
        if _has_ancestor(point_id, unit_id, nodes) and point_id not in candidates:
            candidates.append(point_id)
    return candidates


def _questions_for_unit(
    row: dict[str, str],
    nodes: dict[str, dict[str, str]],
    kp_questions: dict[str, dict[str, str]],
    question_meta: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    candidates = _unit_points(row["knowledge_point_id"], nodes, kp_questions)
    questions = []
    for point_id in candidates:
        row_hits = kp_questions.get(point_id, {})
        if row_hits.get("times_mapped", "0") in ("0", ""):
            continue
        for pair in (row_hits.get("question_ids") or "").split(";"):
            if not pair:
                continue
            question_id = pair.split("@", 1)[0]
            if question_id not in question_meta:
                continue
            if any(question["id"] == question_id for question in questions):
                continue
            source = question_meta[question_id]
            questions.append({
                "id": question_id,
                "year": source["exam_year"],
                "number": source["number"],
                "type": source["question_type"],
                "marks": source["marks"],
                "page": source["locator_page"],
                "paper_sha256": source["locator_paper_sha256"],
                "for_kp": point_id,
            })
    questions.sort(key=lambda item: (item["year"], int(item["number"])))
    return questions


def _unit_header(
    row: dict[str, str],
    nodes: dict[str, dict[str, str]],
    kids: list[str],
    questions: list[dict[str, str]],
    manifest: dict[str, Any],
) -> list[str]:
    """Title, generator note, supplementary-view line and the unit facts table."""
    point_id = row["knowledge_point_id"]
    parent = nodes.get(row.get("parent_id", ""), {})
    view = manifest.get("supplementary_view", {})
    return [
        f"# {_node_label(row)}",
        "",
        "<!-- 由 tools/build_408_deck_scaffold.py 生成；正文由 AI 填写。 -->",
        "",
        f"补充视图：`{view.get('view_name', row.get('view_name', ''))}` — "
        f"{view.get('description', '')}",
        "",
        "| 项 | 值 |",
        "|---|---|",
        f"| 知识单元 | `{point_id}` |",
        f"| 所属章 | {parent.get('title', '')} (`{row.get('parent_id', '')}`) |",
        f"| 来源支持度 | {row.get('source_support', '')} ｜ 来源数 "
        f"{row.get('source_count', '')} ｜ 证据 {row.get('evidence_tag', '')} |",
        f"| 子条目数 | {len(kids)} |",
        f"| 真题命中 | {len(questions)} 题 |",
        "",
    ]


def _unit_children_section(
    nodes: dict[str, dict[str, str]],
    kids: list[str],
    kp_questions: dict[str, dict[str, str]],
) -> list[str]:
    """The child knowledge items of the unit, each with its question-hit count."""
    lines = ["## 本单元覆盖的知识条目", ""]
    for child_id in kids:
        child = nodes[child_id]
        hit_row = kp_questions.get(child_id, {})
        hits = hit_row.get("times_mapped", "0")
        hit_label = f"（真题命中 {hits} 次）" if hits not in (None, "", "0") else ""
        lines.append(f"- `{child_id}` {_node_label(child)}{hit_label}")
    return lines


def _unit_question_section(
    questions: list[dict[str, str]],
    year_span: str,
    index_count: int,
) -> list[str]:
    """The question locator table, or the "no hit is not 'not examined'" note."""
    lines = ["", "## 真题定位（引用请按 QUOTATION_POLICY.md）", ""]
    if questions:
        lines.extend([
            "| 题号 | 年份 | 题型 | 分值 | 卷面页 | 该题映射到的知识点 |",
            "|---|---|---|---:|---:|---|",
        ])
        for question in questions:
            lines.append(
                f"| {question['id']} | {question['year']} | {question['type']} | "
                f"{question['marks']} | {question['page']} | `{question['for_kp']}` |"
            )
    else:
        lines.append(
            f"> 本单元在 {year_span} {_chinese_count(index_count)}套卷的映射中**无真题命中**。"
            f"无命中不等于不考，只说明这{_chinese_count(index_count)}套里没出现。"
        )
    return lines


def _unit_lecture_section(questions: list[dict[str, str]]) -> list[str]:
    """The AI-filled lecture body headings, with one excerpt slot for each of the first three
    questions under 真题印证."""
    lines = [
        "",
        "## 讲解正文（待 AI 填写）",
        "",
        "### 考点提炼",
        "",
        "### 原理与推导",
        "",
        "### 易错点",
        "",
        "### 真题印证（此处插入简短摘录，每题不超过必要长度，并注明题号与年份）",
        "",
    ]
    for question in questions[:3]:
        lines.extend([
            f"#### {question['year']} 年第 {question['number']} 题",
            "",
            f"- 出处：`{question['id']}`，卷面第 {question['page']} 页",
            "- 摘录：（此处填最必要的题干片段）",
            "- 讲解：",
            "",
        ])
    return lines


def _unit_practice_section() -> list[str]:
    """The practice-pointer heading; the user allows it to stay empty."""
    return ["### 练习指向", "", "（本栏按用户要求可省略）", ""]


def _unit_document(
    row: dict[str, str],
    nodes: dict[str, dict[str, str]],
    children: dict[str, list[str]],
    kp_questions: dict[str, dict[str, str]],
    questions: list[dict[str, str]],
    manifest: dict[str, Any],
    year_span: str,
    index_count: int,
) -> str:
    # Section order is the document layout; the G3e baseline test pins it byte for byte.
    kids = children.get(row["knowledge_point_id"], [])
    lines = [
        *_unit_header(row, nodes, kids, questions, manifest),
        *_unit_children_section(nodes, kids, kp_questions),
        *_unit_question_section(questions, year_span, index_count),
        *_unit_lecture_section(questions),
        *_unit_practice_section(),
    ]
    return "\n".join(lines)


def build_scaffold(workspace: Workspace) -> list[Path]:
    """Build teaching-unit markdown files from the registered product workspace."""
    product_root = workspace.require("products.cs408_lecture_workspace")
    deck_root = product_root / "deck"
    deck_root.mkdir(parents=True, exist_ok=True)
    tree_rows = _read_csv(product_root / "tree_flat.csv")
    kp_rows = _read_csv(product_root / "kp_to_questions.csv")
    question_rows = _read_csv(product_root / "question_index.csv")
    manifest = json.loads((product_root / "manifest.json").read_text(encoding="utf-8"))
    nodes = {row["knowledge_point_id"]: row for row in tree_rows}
    kp_questions = {row["knowledge_point_id"]: row for row in kp_rows}
    question_meta = {row["question_id"]: row for row in question_rows}
    year_span = _year_span(question_rows)
    index_count = len(manifest["generated_from"]["exam_indexes"])
    children: defaultdict[str, list[str]] = defaultdict(list)
    for row in tree_rows:
        if row.get("parent_id"):
            children[row["parent_id"]].append(row["knowledge_point_id"])

    written = []
    units = [row for row in tree_rows if row["scope"] == "section"]
    for row in units:
        questions = _questions_for_unit(row, nodes, kp_questions, question_meta)
        path = deck_root / f"{row['knowledge_point_id']}.md"
        path.write_text(
            _unit_document(
                row,
                nodes,
                children,
                kp_questions,
                questions,
                manifest,
                year_span,
                index_count,
            ),
            encoding="utf-8",
        )
        written.append(path)
    return written


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path)
    args = parser.parse_args()
    files = build_scaffold(load_workspace(args.workspace))
    print("deck shells written:", len(files))
    print("example:", files[0].name if files else "-")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
