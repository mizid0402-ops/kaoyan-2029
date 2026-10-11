"""M6 question-to-knowledge-point classifier; see ``contracts/workspace.md``.

Public interface: ``classify(text, valid_ids)`` and the CLI ``main()``.

Method (deliberately mechanical and auditable):

  1. Re-read the staged paper PDF in memory and locate each question's line span.
  2. Score every candidate *section* node of the 408 tree against that question's text
     using a hand-written pattern bank (term -> section id).
  3. Emit ONLY: year, question number, matched node id, matched term, match count,
     and a confidence band. No question text, no options, no answers, ever.

Why patterns rather than a model's judgement: the tree's node set comes from the
official outline, so the mapping target is authoritative; the *assignment* is the
fallible step, and a term-based assignment can be re-run, diffed, inspected and
reviewed. A model's judgement cannot. Disagreements with the official answer book,
when it arrives, will therefore point at a specific pattern to fix.

The pattern bank encodes 408 terminology that is already in the outline's own
vocabulary (链表/二叉树/散列/页表/流水线…). It is a lookup key, not exam content.

Usage:
    py -3.12 tools/classify_questions.py --pdf <paper.pdf> --year 2024 \
        --out cache/exam_probe/2024_question_map.json [--show 47]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ky.knowledge.knowledge_point import load_knowledge_points  # noqa: E402
from ky.workspace import load_workspace  # noqa: E402

# term -> section knowledge_point_id. Ordered longest-term-first at match time so
# "二叉排序树" does not lose to "二叉树".
PATTERNS: list[tuple[str, str]] = [
    # ---------------- 数据结构 ----------------
    ("邻接多重表", "cs408.ds.chapter-05.section-02"),
    ("邻接表", "cs408.ds.chapter-05.section-02"),
    ("邻接矩阵", "cs408.ds.chapter-05.section-02"),
    ("广度优先", "cs408.ds.chapter-05.section-03"),
    ("深度优先", "cs408.ds.chapter-05.section-03"),
    ("拓扑排序", "cs408.ds.chapter-05.section-04"),
    ("关键路径", "cs408.ds.chapter-05.section-04"),
    ("最短路径", "cs408.ds.chapter-05.section-04"),
    ("最小生成树", "cs408.ds.chapter-05.section-04"),
    ("Prim", "cs408.ds.chapter-05.section-04"),
    ("Kruskal", "cs408.ds.chapter-05.section-04"),
    ("Dijkstra", "cs408.ds.chapter-05.section-04"),
    ("哈夫曼", "cs408.ds.chapter-04.section-04"),
    ("并查集", "cs408.ds.chapter-04.section-04"),
    ("二叉排序树", "cs408.ds.chapter-06.section-05"),
    ("平衡二叉树", "cs408.ds.chapter-06.section-05"),
    ("红黑树", "cs408.ds.chapter-06.section-05"),
    ("B+树", "cs408.ds.chapter-06.section-06"),
    ("B+ 树", "cs408.ds.chapter-06.section-06"),
    ("B树", "cs408.ds.chapter-06.section-06"),
    ("B 树", "cs408.ds.chapter-06.section-06"),
    ("散列", "cs408.ds.chapter-06.section-07"),
    ("哈希", "cs408.ds.chapter-06.section-07"),
    ("装填因子", "cs408.ds.chapter-06.section-07"),
    ("模式匹配", "cs408.ds.chapter-06.section-08"),
    ("KMP", "cs408.ds.chapter-06.section-08"),
    ("next数组", "cs408.ds.chapter-06.section-08"),
    ("折半查找", "cs408.ds.chapter-06.section-04"),
    ("二分查找", "cs408.ds.chapter-06.section-04"),
    ("分块查找", "cs408.ds.chapter-06.section-03"),
    ("顺序查找", "cs408.ds.chapter-06.section-02"),
    ("快速排序", "cs408.ds.chapter-07.section-07"),
    ("堆排序", "cs408.ds.chapter-07.section-08"),
    ("归并排序", "cs408.ds.chapter-07.section-09"),
    ("基数排序", "cs408.ds.chapter-07.section-10"),
    ("希尔排序", "cs408.ds.chapter-07.section-06"),
    ("起泡排序", "cs408.ds.chapter-07.section-04"),
    ("冒泡排序", "cs408.ds.chapter-07.section-04"),
    ("直接插入排序", "cs408.ds.chapter-07.section-02"),
    ("折半插入排序", "cs408.ds.chapter-07.section-03"),
    ("简单选择排序", "cs408.ds.chapter-07.section-05"),
    ("外部排序", "cs408.ds.chapter-07.section-11"),
    ("排序", "cs408.ds.chapter-07.section-12"),
    ("中序遍历", "cs408.ds.chapter-04.section-02"),
    ("后序遍历", "cs408.ds.chapter-04.section-02"),
    ("前序遍历", "cs408.ds.chapter-04.section-02"),
    ("先序遍历", "cs408.ds.chapter-04.section-02"),
    ("层序遍历", "cs408.ds.chapter-04.section-02"),
    ("遍历", "cs408.ds.chapter-04.section-02"),
    ("二叉树", "cs408.ds.chapter-04.section-02"),
    ("完全二叉树", "cs408.ds.chapter-04.section-02"),
    ("树", "cs408.ds.chapter-04.section-01"),
    ("栈", "cs408.ds.chapter-03.section-06"),
    ("队列", "cs408.ds.chapter-03.section-06"),
    ("循环队列", "cs408.ds.chapter-03.section-02"),
    ("数组", "cs408.ds.chapter-03.section-04"),
    ("压缩存储", "cs408.ds.chapter-03.section-05"),
    ("对称矩阵", "cs408.ds.chapter-03.section-05"),
    ("三对角", "cs408.ds.chapter-03.section-05"),
    ("链表", "cs408.ds.chapter-02.section-02"),
    ("顺序表", "cs408.ds.chapter-02.section-02"),
    ("线性表", "cs408.ds.chapter-02.section-01"),
    ("时间复杂度", "cs408.ds.chapter-01.section-02"),
    ("空间复杂度", "cs408.ds.chapter-01.section-02"),
    # ---------------- 计算机组成原理 ----------------
    ("浮点数", "cs408.co.chapter-02.section-01"),
    ("IEEE", "cs408.co.chapter-02.section-01"),
    ("补码", "cs408.co.chapter-02.section-01"),
    ("移码", "cs408.co.chapter-02.section-01"),
    ("海明", "cs408.co.chapter-02.section-01"),
    ("校验码", "cs408.co.chapter-02.section-01"),
    ("CRC", "cs408.co.chapter-02.section-01"),
    ("乘法", "cs408.co.chapter-02.section-02"),
    ("除法", "cs408.co.chapter-02.section-02"),
    ("加法器", "cs408.co.chapter-02.section-02"),
    ("Cache", "cs408.co.chapter-03.section-01"),
    ("cache", "cs408.co.chapter-03.section-01"),
    ("虚拟存储", "cs408.co.chapter-03.section-01"),
    ("页表", "cs408.co.chapter-03.section-01"),
    ("TLB", "cs408.co.chapter-03.section-01"),
    ("存储器", "cs408.co.chapter-03.section-01"),
    ("DRAM", "cs408.co.chapter-03.section-01"),
    ("SRAM", "cs408.co.chapter-03.section-01"),
    ("寻址方式", "cs408.co.chapter-04.section-01"),
    ("指令格式", "cs408.co.chapter-04.section-01"),
    ("CISC", "cs408.co.chapter-04.section-01"),
    ("RISC", "cs408.co.chapter-04.section-01"),
    ("流水线", "cs408.co.chapter-05.section-01"),
    ("数据通路", "cs408.co.chapter-05.section-01"),
    ("控制器", "cs408.co.chapter-05.section-01"),
    ("中断", "cs408.co.chapter-05.section-01"),
    ("总线", "cs408.co.chapter-06.section-01"),
    ("I/O", "cs408.co.chapter-06.section-02"),
    ("DMA", "cs408.co.chapter-06.section-02"),
    ("磁盘", "cs408.co.chapter-06.section-02"),
    ("RAID", "cs408.co.chapter-06.section-02"),
    # ---------------- 操作系统 ----------------
    ("进程", "cs408.os.chapter-02.section-01"),
    ("线程", "cs408.os.chapter-02.section-01"),
    ("调度", "cs408.os.chapter-02.section-02"),
    ("同步", "cs408.os.chapter-02.section-03"),
    ("互斥", "cs408.os.chapter-02.section-03"),
    ("信号量", "cs408.os.chapter-02.section-03"),
    ("死锁", "cs408.os.chapter-02.section-04"),
    ("银行家", "cs408.os.chapter-02.section-04"),
    ("页面置换", "cs408.os.chapter-03.section-02"),
    ("缺页", "cs408.os.chapter-03.section-02"),
    ("分页", "cs408.os.chapter-03.section-02"),
    ("分段", "cs408.os.chapter-03.section-02"),
    ("文件", "cs408.os.chapter-04.section-01"),
    ("目录", "cs408.os.chapter-04.section-01"),
    ("磁盘调度", "cs408.os.chapter-05.section-01"),
    # ---------------- 计算机网络 ----------------
    ("子网", "cs408.cn.chapter-03.section-01"),
    ("CIDR", "cs408.cn.chapter-03.section-01"),
    ("IP", "cs408.cn.chapter-03.section-01"),
    ("ARP", "cs408.cn.chapter-03.section-01"),
    ("DHCP", "cs408.cn.chapter-03.section-01"),
    ("路由", "cs408.cn.chapter-03.section-01"),
    ("TCP", "cs408.cn.chapter-04.section-01"),
    ("UDP", "cs408.cn.chapter-04.section-01"),
    ("拥塞", "cs408.cn.chapter-04.section-01"),
    ("滑动窗口", "cs408.cn.chapter-04.section-01"),
    ("三次握手", "cs408.cn.chapter-04.section-01"),
    ("DNS", "cs408.cn.chapter-05.section-01"),
    ("HTTP", "cs408.cn.chapter-05.section-01"),
    ("以太网", "cs408.cn.chapter-02.section-01"),
    ("CSMA", "cs408.cn.chapter-02.section-01"),
    ("交换机", "cs408.cn.chapter-02.section-01"),
]

Q_START = re.compile(r"^\s*(\d{1,2})\s*[.、．]\s*(.*)$")


def question_spans(pdf: Path) -> dict[int, str]:
    """number -> the question's own text (kept in memory only, returned not stored)."""
    import pypdf

    reader = pypdf.PdfReader(str(pdf))
    current: int | None = None
    buffer: list[str] = []
    spans: dict[int, str] = {}
    for page in reader.pages:
        for raw in (page.extract_text() or "").splitlines():
            match = Q_START.match(raw)
            # a real question start: number followed by text, and not an option line
            if match and not re.match(r"^\s*[A-D][.、．]", raw):
                number = int(match.group(1))
                if number not in spans and (current is None or number == current + 1):
                    if current is not None:
                        spans[current] = "\n".join(buffer)
                    current = number
                    buffer = [match.group(2)]
                    continue
            if current is not None:
                buffer.append(raw)
    if current is not None:
        spans[current] = "\n".join(buffer)
    return spans


def classify(text: str, valid_ids: set[str]) -> list[tuple[str, str, int]]:
    """Score sections by number of distinct pattern hits, longest terms first."""
    normalised = text.replace(" ", "")
    hits: dict[str, list[str]] = {}
    used_spans: list[tuple[int, int]] = []
    for term, section in sorted(PATTERNS, key=lambda t: -len(t[0])):
        if section not in valid_ids:
            continue
        needle = term.replace(" ", "")
        idx = normalised.find(needle)
        if idx < 0:
            continue
        hits.setdefault(section, []).append(term)
    return sorted(
        ((section, "、".join(terms), len(terms)) for section, terms in hits.items()),
        key=lambda t: (-t[2], t[0]),
    )


def _map_questions(
    spans: dict[int, str],
    year: int,
    valid_ids: set[str],
    titles: dict[str, str],
) -> list[dict]:
    rows = []
    for number in sorted(spans):
        ranked = classify(spans[number], valid_ids)
        best = ranked[0] if ranked else None
        runner = ranked[1] if len(ranked) > 1 else None
        if best is None:
            band = "unmapped"
        elif best[2] >= 2 and (runner is None or best[2] > runner[2]):
            band = "high"
        else:
            band = "low"
        rows.append({
            "year": year,
            "number": number,
            "section_id": best[0] if best else None,
            "section_title": titles.get(best[0]) if best else None,
            "matched_terms": best[1] if best else None,
            "hit_count": best[2] if best else 0,
            "confidence": band,
            "alternatives": [
                {"section_id": section, "matched_terms": terms, "hit_count": count}
                for section, terms, count in ranked[1:4]
            ],
        })
    return rows


def _write_result(
    path: Path,
    workspace_root: Path,
    pdf: Path,
    year: int,
    rows: list[dict],
    show: int,
) -> None:
    counts = {}
    for row in rows:
        counts[row["confidence"]] = counts.get(row["confidence"], 0) + 1
    payload = {
        "year": year,
        "paper": pdf.name,
        "questions": len(rows),
        "confidence_counts": counts,
        "method": "term-pattern match against cs408 tree section titles; no question text stored",
        "rows": rows,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )
    print(f"year {year}: {len(rows)} questions mapped")
    print(f"confidence: {counts}")
    print(f"\n{'q':>3}  {'band':<9} {'hits':>4}  section")
    limit = show or len(rows)
    for row in rows[:limit]:
        title = (row["section_title"] or "-")[:38]
        print(f"{row['number']:>3}  {row['confidence']:<9} {row['hit_count']:>4}  {title}")
    print(f"\nwrote {path.relative_to(workspace_root).as_posix()} (no question text)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--show", type=int, default=0)
    ap.add_argument("--workspace", type=Path)
    args = ap.parse_args()

    workspace = load_workspace(args.workspace)
    pdf = Path(args.pdf)
    if not pdf.is_absolute():
        pdf = workspace.root / pdf
    tree_path = workspace.require("reference.knowledge_trees.cs408")
    points = load_knowledge_points(tree_path)
    valid_ids = {p.knowledge_point_id for p in points if p.scope == "section"}
    titles = {p.knowledge_point_id: p.title for p in points}

    out = args.out if args.out.is_absolute() else workspace.root / args.out
    rows = _map_questions(
        question_spans(pdf),
        args.year,
        valid_ids,
        titles,
    )
    _write_result(out, workspace.root, pdf, args.year, rows, args.show)
    return 0


if __name__ == "__main__":
    sys.exit(main())
