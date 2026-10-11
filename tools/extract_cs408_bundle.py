"""M21 registered 408 tree-and-question bundle exporter.

See ``contracts/workspace.md``. Public interface: ``build_bundle(workspace, output)`` and CLI
``main()``. Supplementary data remains visibly separate from the effective tree (D1).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from ky.knowledge import load_knowledge_points  # noqa: E402
from ky.models import ContractError, load_yaml_text  # noqa: E402
from ky.workspace import SupplementaryView, Workspace, load_workspace  # noqa: E402


def _yaml_file(path: Path) -> Any:
    return load_yaml_text(path.read_text(encoding="utf-8"), source=path.as_posix())


def _items(document: Any, path: Path) -> list[dict[str, Any]]:
    if isinstance(document, dict):
        document = document.get("items")
    if not isinstance(document, list):
        raise ContractError("expected a list of tree nodes", path.as_posix())
    return document


def _parent_lookup(nodes: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {node["knowledge_point_id"]: node for node in nodes}


def _parent_of(point_id: str, by_id: dict[str, dict[str, Any]]) -> str | None:
    parts = point_id.split(".")
    while len(parts) > 2:
        parts = parts[:-1]
        parent = ".".join(parts)
        if parent in by_id:
            return parent
    return None


def _flat_rows(
    nodes: list[dict[str, Any]],
    agreement: dict[str, dict[str, Any]],
    effective_ids: set[str],
    view_name: str,
) -> list[dict[str, Any]]:
    by_id = _parent_lookup(nodes)
    order_by_parent: defaultdict[str | None, int] = defaultdict(int)
    rows = []
    for node in nodes:
        point_id = node["knowledge_point_id"]
        parent = _parent_of(point_id, by_id)
        order_by_parent[parent] += 1
        attrs = agreement.get(point_id, {})
        rows.append({
            "knowledge_point_id": point_id,
            "scope": node["scope"],
            "title": node.get("title", ""),
            "parent_id": parent or "",
            "depth": len(point_id.split(".")) - 1,
            "order": order_by_parent[parent],
            "source_support": attrs.get("source_support", ""),
            "source_count": attrs.get("source_count", ""),
            "evidence_tag": attrs.get("evidence_tag", ""),
            "match_kind": attrs.get("match_kind", ""),
            "status": node.get("status", ""),
            "source_kind": node.get("source_kind", ""),
            "is_effective": point_id in effective_ids,
            "view_name": view_name,
        })

    children: defaultdict[str, list[str]] = defaultdict(list)
    for row in rows:
        if row["parent_id"]:
            children[row["parent_id"]].append(row["knowledge_point_id"])
    for row in rows:
        row["child_ids"] = ";".join(children.get(row["knowledge_point_id"], []))
    return rows


def _question_rows(index_paths: tuple[Path, ...]) -> list[dict[str, Any]]:
    rows = []
    for path in index_paths:
        document = json.loads(path.read_text(encoding="utf-8"))
        for entry in document["entries"]:
            weights = entry.get("knowledge_point_weights") or {}
            locator = entry.get("locator") or {}
            rows.append({
                "question_id": entry["question_id"],
                "exam_year": entry["exam_year"],
                "number": entry["number"],
                "question_type": entry["question_type"],
                "marks": "" if entry.get("marks") is None else entry["marks"],
                "subject_id": entry["subject_id"],
                "knowledge_point_id": entry.get("knowledge_point_id", ""),
                "knowledge_point_status": entry.get("knowledge_point_status", ""),
                "n_knowledge_points": len(weights),
                "knowledge_point_weights": json.dumps(weights, ensure_ascii=False),
                "answer_confidence": entry.get("answer_confidence", ""),
                "locator_page": locator.get("page", 0),
                "locator_paper_sha256": locator.get("paper_sha256", ""),
            })
    return rows


def _question_map(rows: list[dict[str, Any]]) -> defaultdict[str, list[tuple[dict, Any]]]:
    mapped: defaultdict[str, list[tuple[dict, Any]]] = defaultdict(list)
    for row in rows:
        weights = json.loads(row["knowledge_point_weights"] or "{}")
        if weights:
            for point_id, weight in weights.items():
                mapped[point_id].append((row, weight))
        elif row["knowledge_point_id"]:
            mapped[row["knowledge_point_id"]].append((row, 1.0))
    return mapped


def _coverage_rows(
    tree_rows: list[dict[str, Any]],
    question_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    mapped = _question_map(question_rows)
    rows = []
    for node in tree_rows:
        hits = mapped.get(node["knowledge_point_id"], [])
        years = sorted({question["exam_year"] for question, _ in hits})
        rows.append({
            "knowledge_point_id": node["knowledge_point_id"],
            "scope": node["scope"],
            "title": node["title"],
            "times_mapped": len(hits),
            "years_seen": ";".join(str(year) for year in years),
            "year_count": len(years),
            "question_ids": ";".join(
                f"{question['question_id']}@{weight}" for question, weight in hits
            ),
        })
    return rows, [row for row in rows if row["times_mapped"]]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ContractError("cannot export an empty table", path.as_posix())
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=list(rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_tree_outputs(
    output: Path,
    rows: list[dict[str, Any]],
) -> None:
    (output / "tree_flat.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1),
        encoding="utf-8",
        newline="\n",
    )
    _write_csv(output / "tree_flat.csv", rows)
    lines = [
        "# 408 知识点树（结构大纲）",
        "",
        f"节点总数 {len(rows)} ｜ 节点标题取自 2026 版大纲，本文件只含标题与层级，不含考纲正文。",
        "",
    ]
    for row in rows:
        label = "【补充：非当年考纲，legacy_only_pending】" if not row["is_effective"] else ""
        lines.append(
            "  " * row["depth"]
            + f"- `{row['knowledge_point_id']}` {row['title']}{label}"
        )
    (output / "tree_outline.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )


def _year_span(question_rows: list[dict[str, Any]]) -> str:
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


def _write_coverage(
    output: Path,
    rows: list[dict[str, Any]],
    hits: list[dict[str, Any]],
    question_rows: list[dict[str, Any]],
    index_count: int,
) -> None:
    misses = [row for row in rows if not row["times_mapped"]]
    lines = [
        "# 408 知识点覆盖报告",
        "",
        f"- 树节点总数：**{len(rows)}**",
        f"- 有真题命中的节点：**{len(hits)}**",
        f"- 无真题命中的节点：**{len(misses)}**",
        "- 覆盖口径：题目索引里的 `knowledge_point_weights`（归一化分布）与 `knowledge_point_id` 联合计数；",
        "  一道题命中多个知识点时各计一次。",
        "",
        "## 命中次数最多的 40 个知识点",
        "",
        "| 知识点 | 层级 | 命中次数 | 出现年份 | 标题 |",
        "|---|---|---:|---|---|",
    ]
    for row in sorted(hits, key=lambda item: -item["times_mapped"])[:40]:
        lines.append(
            f"| `{row['knowledge_point_id']}` | {row['scope']} | "
            f"{row['times_mapped']} | {row['years_seen']} | {row['title']} |"
        )
    lines.extend([
        "",
        "## 层级分布（有命中 / 无命中）",
        "",
        "| 层级 | 总数 | 有命中 | 无命中 |",
        "|---|---:|---:|---:|",
    ])
    by_scope: defaultdict[str, list[int]] = defaultdict(lambda: [0, 0])
    for row in rows:
        by_scope[row["scope"]][0] += 1
        if row["times_mapped"]:
            by_scope[row["scope"]][1] += 1
    for scope, (total, tested) in sorted(by_scope.items()):
        lines.append(f"| {scope} | {total} | {tested} | {total - tested} |")
    lines.extend([
        "",
        "## 无真题命中的节点（前 60，全部见 CSV）",
        "",
        f"> 无命中 **不等于** 不考：只说明在 {_year_span(question_rows)} 这"
        f"{_chinese_count(index_count)}套卷子的映射里没出现。",
        "",
        "| 知识点 | 层级 | 标题 |",
        "|---|---|---|",
    ])
    for row in [item for item in rows if not item["times_mapped"]][:60]:
        lines.append(f"| `{row['knowledge_point_id']}` | {row['scope']} | {row['title']} |")
    (output / "coverage.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )


def _generated_from(
    root: Path,
    tree_path: Path,
    agreement_path: Path,
    index_paths: tuple[Path, ...],
) -> dict[str, Any]:
    return {
        "tree": tree_path.relative_to(root).as_posix(),
        "agreement": agreement_path.relative_to(root).as_posix(),
        "exam_indexes": [path.relative_to(root).as_posix()
                         for path in index_paths],
    }


def _manifest_counts(
    rows: list[dict[str, Any]],
    questions: list[dict[str, Any]],
    kp_rows: list[dict[str, Any]],
    hits: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "tree_nodes": len(rows),
        "by_scope": dict(Counter(row["scope"] for row in rows)),
        "questions": len(questions),
        "kp_with_hits": len(hits),
        "kp_without_hits": len(kp_rows) - len(hits),
    }


def _write_manifest(
    output: Path,
    generated_from: dict[str, Any],
    view: SupplementaryView,
    counts: dict[str, Any],
) -> None:
    # Key order is the file layout; the G3e baseline test compares manifest.json byte for byte.
    manifest = {
        "generated_from": generated_from,
        "supplementary_view": {
            "view_name": view.name,
            "kind": view.kind,
            "description": view.description,
        },
        "counts": counts,
        "does_not_contain": [
            "question stems", "options", "answers", "explanations",
            "syllabus body text", "any teaching content",
        ],
        "note": (
            "Titles are short node headings from the official outline. Everything about a "
            "question is referenced by question_id and remains in data/exam_questions."
        ),
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )


def build_bundle(workspace: Workspace, output: Path | None = None) -> dict[str, Any]:
    """Export the registered supplementary tree and its registered question indexes."""
    view = workspace.supplementary["cs408_multisource"]
    tree_path = workspace.require("supplementary.cs408_multisource.files.tree")
    agreement_path = workspace.require("supplementary.cs408_multisource.files.agreement")
    effective_path = workspace.require("reference.knowledge_trees.cs408")
    index_paths = workspace.require_all("reference.exam_indexes.cs408")
    target = output or workspace.require("products.cs408_lecture_workspace")
    target.mkdir(parents=True, exist_ok=True)

    tree_nodes = _items(_yaml_file(tree_path), tree_path)
    agreement_items = _items(_yaml_file(agreement_path), agreement_path)
    agreement = {item["knowledge_point_id"]: item for item in agreement_items}
    effective_ids = {
        point.knowledge_point_id
        for point in load_knowledge_points(
            effective_path,
        )
    }
    rows = _flat_rows(tree_nodes, agreement, effective_ids, view.name)
    questions = _question_rows(index_paths)
    _write_tree_outputs(target, rows)
    _write_csv(target / "question_index.csv", questions)
    kp_rows, hits = _coverage_rows(rows, questions)
    _write_csv(target / "kp_to_questions.csv", kp_rows)
    _write_coverage(target, kp_rows, hits, questions, len(index_paths))
    _write_manifest(
        target,
        _generated_from(workspace.root, tree_path, agreement_path, index_paths),
        view,
        _manifest_counts(rows, questions, kp_rows, hits),
    )
    return {"output": target, "tree_nodes": len(rows), "questions": len(questions)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path)
    args = parser.parse_args()
    workspace = load_workspace(args.workspace)
    result = build_bundle(workspace)
    print("nodes", result["tree_nodes"], "questions", result["questions"])
    print("output:", result["output"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
