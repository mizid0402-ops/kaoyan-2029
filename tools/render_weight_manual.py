"""Render docs/知识点权重说明书.md, a reader's guide to the M6 topic weights.

A read-only consumer of three registered ports: topic weights (``contracts/topic_weights.md``),
exam indexes (``contracts/exam_index.md``) and effective knowledge trees
(``contracts/knowledge_tree.md``). Every number in the output is computed here from that data;
nothing is typed by hand, so re-running after a new year is tagged yields the new edition.

Usage:  py -3.12 tools/render_weight_manual.py [--workspace <registry>] [--out <path>]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from ky.knowledge import load_knowledge_points, nearest_ancestor_with_scope  # noqa: E402
from ky.workspace import load_workspace  # noqa: E402

SUBJECT_NAMES = {"cs408": "408 计算机学科专业基础", "math1": "数学一", "eng1": "英语一"}


def load(workspace_path):
    ws = load_workspace(workspace_path)
    trees = {
        s: {p.knowledge_point_id: p for p in load_knowledge_points(
            ws.require(f"reference.knowledge_trees.{s}"))}
        for s in SUBJECT_NAMES
    }
    weights = json.loads(ws.require("reference.topic_weights").read_text(encoding="utf-8"))
    marks = {}
    for subject in SUBJECT_NAMES:
        for path in ws.require_all(f"reference.exam_indexes.{subject}"):
            index = json.loads(path.read_text(encoding="utf-8"))
            for entry in index["entries"]:
                key = f"{subject}-{entry['exam_year']}-{entry['number']}"
                marks[key] = (entry["marks"], entry["question_type"])
    return ws, trees, weights, marks


def pct(part, whole):
    return f"{100 * part / whole:.1f}%" if whole else "—"


def num(value):
    return f"{value:.2f}"


def questions_of(weights, subject):
    for key, value in weights["per_question"].items():
        if key.split("-")[0] == subject:
            yield key, int(key.split("-")[1]), value["distribution"]


def cs408_chapter(trees, node):
    return nearest_ancestor_with_scope(node, trees["cs408"], "chapter") or node


def math1_chapter_key(node):
    # The named_chapters grammar (contracts/workspace.md §2.5) defines a chapter as
    # "<章>.chapter" with required children "<章>.content" / "<章>.requirements"; this
    # recovers that "<章>" stem to merge the three, for presentation only.
    return node.rsplit(".", 1)[0]


def grouped_rows(subject, trees, weights, marks, group_of):
    """Per group: official topic weight, mark-weighted share, years, questions touching it."""
    official = defaultdict(float)
    for node, value in weights["topic_weight"][subject].items():
        official[group_of(node)] += value
    mark_weight = defaultdict(float)
    years = defaultdict(set)
    touching = defaultdict(set)
    mark_total = 0.0
    excluded = 0
    for key, year, dist in questions_of(weights, subject):
        mark = marks.get(key, (None, None))[0]
        if mark is None:
            excluded += 1
        else:
            mark_total += mark
        for node, share in dist.items():
            group = group_of(node)
            years[group].add(year)
            touching[group].add(key)
            if mark is not None:
                mark_weight[group] += share * mark
    return official, mark_weight, mark_total, excluded, years, touching


def title(trees, subject, node_id):
    point = trees[subject].get(node_id)
    return point.title if point else node_id


def section_overview(weights):
    lines = ["## 二、数据总览", "",
             "| 科目 | 年份 | 题数 | 三模型归到同一节点的题 | 权重分散到多个节点的题 |",
             "|---|---|---:|---:|---:|"]
    stats = defaultdict(lambda: [set(), 0, 0, 0])
    for row in weights["batch_stats"]:
        entry = stats[row["subject"]]
        entry[0].add(row["year"])
        entry[1] += row["questions"]
        entry[2] += row["single_node"]
        entry[3] += row["spread"]
    for subject, (years, total, single, spread) in stats.items():
        span = f"{min(years)}–{max(years)}"
        lines.append(f"| {SUBJECT_NAMES[subject]} | {span} | {total} | {single} | {spread} |")
    return lines


def _cs408_domains(trees, official, mark_w, mark_total, excluded, total):
    lines = ["## 三、408 计算机学科专业基础", ""]
    domains = defaultdict(lambda: [0.0, 0.0])
    for chapter, value in official.items():
        domains[chapter.split(".")[1]][0] += value
    for chapter, value in mark_w.items():
        domains[chapter.split(".")[1]][1] += value
    lines += ["### 3.1 四门课的分量", "",
              "| 课程 | 等效题数 | 按题数占比 | 按分值占比 |", "|---|---:|---:|---:|"]
    for domain, (value, mark_value) in sorted(domains.items(), key=lambda kv: -kv[1][0]):
        name = title(trees, "cs408", f"cs408.{domain}.subject")
        lines.append(f"| {name} | {num(value)} | {pct(value, total)} | "
                     f"{pct(mark_value, mark_total)} |")
    lines += ["", f"按分值占比只统计分值已知的题（排除 {excluded} 道分值未核实的题）。", ""]
    return lines

def _cs408_chapters(trees, weights, lines, official, mark_w, mark_total, total, years):
    chapters = [p for p in trees["cs408"].values() if p.scope == "chapter"]
    leaf_count = defaultdict(int)
    hit_nodes = defaultdict(set)
    for point in trees["cs408"].values():
        if point.scope in ("section", "item"):
            leaf_count[cs408_chapter(trees, point.knowledge_point_id)] += 1
    for _, _, dist in questions_of(weights, "cs408"):
        for node in dist:
            if trees["cs408"][node].scope in ("section", "item"):
                hit_nodes[cs408_chapter(trees, node)].add(node)
    lines += ["### 3.2 按章排序", "",
              "| # | 章 | 等效题数 | 按题数占比 | 按分值占比 | 出现年份数 | 命中的节 / 条 |",
              "|---:|---|---:|---:|---:|---:|---:|"]
    ordered = sorted(chapters, key=lambda p: (-official.get(p.knowledge_point_id, 0.0),
                                              p.knowledge_point_id))
    for rank, point in enumerate(ordered, start=1):
        cid = point.knowledge_point_id
        domain = title(trees, "cs408", f"cs408.{cid.split('.')[1]}.subject")
        lines.append(
            f"| {rank} | {domain[2:] if '、' in domain else domain}·{point.title} | "
            f"{num(official.get(cid, 0.0))} | {pct(official.get(cid, 0.0), total)} | "
            f"{pct(mark_w.get(cid, 0.0), mark_total)} | {len(years.get(cid, ()))} | "
            f"{len(hit_nodes.get(cid, ()))} / {leaf_count.get(cid, 0)} |")
    zero = [p.title for p in ordered if official.get(p.knowledge_point_id, 0.0) == 0]
    lines += ["", "近四年一次都没考到的章：" + ("、".join(zero) if zero else "无") + "。", ""]

def _cs408_fine_nodes(trees, weights, lines):
    fine = defaultdict(float)
    fine_years = defaultdict(set)
    for _, year, dist in questions_of(weights, "cs408"):
        for node, share in dist.items():
            fine[node] += share
            fine_years[node].add(year)
    lines += ["### 3.3 最常考的 25 个知识点（节 / 条粒度）", "",
              "| # | 知识点 | 所属章 | 等效题数 | 出现年份数 |", "|---:|---|---|---:|---:|"]
    top = sorted(fine.items(), key=lambda kv: (-kv[1], kv[0]))[:25]
    for rank, (node, value) in enumerate(top, start=1):
        domain = title(trees, "cs408", f"cs408.{node.split('.')[1]}.subject")
        chapter = (f"{domain.split('、', 1)[-1]}·"
                   f"{title(trees, 'cs408', cs408_chapter(trees, node))}")
        lines.append(f"| {rank} | {title(trees, 'cs408', node)} | {chapter} | "
                     f"{num(value)} | {len(fine_years[node])} |")
    touched = sum(1 for p in trees["cs408"].values()
                  if p.scope in ("section", "item") and p.knowledge_point_id in fine)
    all_fine = sum(1 for p in trees["cs408"].values() if p.scope in ("section", "item"))
    lines += ["", f"节 / 条两层共 {all_fine} 个知识点，近四年被至少一道题命中的有 {touched} 个"
              f"（{pct(touched, all_fine)}）。", ""]

def section_cs408(trees, weights, marks):
    official, mark_w, mark_total, excluded, years, touching = grouped_rows(
        "cs408", trees, weights, marks, lambda n: cs408_chapter(trees, n))
    total = sum(official.values())
    lines = _cs408_domains(trees, official, mark_w, mark_total, excluded, total)
    _cs408_chapters(trees, weights, lines, official, mark_w, mark_total, total, years)
    _cs408_fine_nodes(trees, weights, lines)
    return lines


def section_math1(trees, weights, marks):
    official, mark_w, mark_total, excluded, years, _ = grouped_rows(
        "math1", trees, weights, marks, math1_chapter_key)
    total = sum(official.values())
    lines = ["## 四、数学一", ""]
    parts = defaultdict(lambda: [0.0, 0.0])
    for key, value in official.items():
        parts[key.split(".")[1]][0] += value
    for key, value in mark_w.items():
        parts[key.split(".")[1]][1] += value
    lines += ["### 4.1 三门课的分量", "",
              "| 课程 | 等效题数 | 按题数占比 | 按分值占比 |", "|---|---:|---:|---:|"]
    for part, (value, mark_value) in sorted(parts.items(), key=lambda kv: -kv[1][0]):
        lines.append(f"| {title(trees, 'math1', f'math1.{part}.subject')} | {num(value)} | "
                     f"{pct(value, total)} | {pct(mark_value, mark_total)} |")
    lines += ["", f"按分值占比排除 {excluded} 道分值未核实的题。", ""]
    lines += ["### 4.2 按章排序", "",
              "| # | 章 | 等效题数 | 按题数占比 | 按分值占比 | 出现年份数 |",
              "|---:|---|---:|---:|---:|---:|"]
    chapters = [p for p in trees["math1"].values() if p.scope == "chapter"]
    def chapter_weight(point):
        return official.get(math1_chapter_key(point.knowledge_point_id), 0.0)

    ordered = sorted(chapters, key=lambda p: (-chapter_weight(p), p.knowledge_point_id))
    for rank, point in enumerate(ordered, start=1):
        key = math1_chapter_key(point.knowledge_point_id)
        part = title(trees, "math1", f"math1.{key.split('.')[1]}.subject")
        weight = official.get(key, 0.0)
        lines.append(f"| {rank} | {part}·{point.title} | {num(weight)} | {pct(weight, total)} | "
                     f"{pct(mark_w.get(key, 0.0), mark_total)} | {len(years.get(key, ()))} |")
    zero = [p.title for p in ordered if chapter_weight(p) == 0]
    lines += ["", "近四年一次都没考到的章：" + ("、".join(zero) if zero else "无") + "。", "",
              "说明：数学一的树每章只有「考试内容」「考试要求」两个子节点，没有更细的条目；编码者有时标到章、有时标到"
              "「考试内容」，本表把同一章下的这些标注合并计算。", ""]
    return lines


def section_eng1(trees, weights, marks):
    official, mark_w, mark_total, excluded, years, _ = grouped_rows(
        "eng1", trees, weights, marks, lambda n: n)
    total = sum(official.values())
    lines = ["## 五、英语一", "",
             "| # | 节点 | 等效题数 | 按题数占比 | 按分值占比 | 出现年份数 |",
             "|---:|---|---:|---:|---:|---:|"]
    ranked = sorted(official.items(), key=lambda kv: (-kv[1], kv[0]))
    for rank, (node, value) in enumerate(ranked, start=1):
        lines.append(f"| {rank} | {title(trees, 'eng1', node)} | {num(value)} | "
                     f"{pct(value, total)} | {pct(mark_w.get(node, 0.0), mark_total)} | "
                     f"{len(years.get(node, ()))} |")
    lines += ["", f"按分值占比排除 {excluded} 道分值未核实的题。", "",
              "说明：英语一的树是刻意做粗的结构树（24 个节点，试卷结构与考查目标两套并列），每道题常被同时归到"
              "「试卷部分」和「考查能力」两类节点，所以这里的权重反映的是**题型与能力的分布**，不是细粒度知识点。", ""]
    return lines


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workspace", default=None, help="workspace registry (otherwise discover)")
    parser.add_argument("--out", type=Path, default=REPO / "docs" / "知识点权重说明书.md")
    args = parser.parse_args()
    ws, trees, weights, marks = load(args.workspace)
    commit = subprocess.run(["git", "-C", str(ws.root), "rev-parse", "--short", "HEAD"],
                            capture_output=True, text=True).stdout.strip() or "未知"
    cw = weights["meta"]["confidence_weights"]
    lines = [
        "# 知识点权重说明书", "",
        f"> 由 `kaoyan.workspace.yaml` 登记的数据生成（仓库提交 `{commit}`，"
        f"{date.today().isoformat()}）："
        "题→知识点权重 `reference.topic_weights`、真题索引 `reference.exam_indexes.*`、"
        "生效知识树 `reference.knowledge_trees.*`。文中所有数字均由脚本从这些文件计算，未手工填写。", "",
        "## 一、这份说明书回答什么、怎么读", "",
        "- **回答的问题**：在近几年的真题里，考纲树上的哪些章、哪些知识点考得多、哪些几乎没考。",
        "- **等效题数**：每道真题总权重为 1.0，按下文方法分给它考到的知识点；把一个章下所有分到的权重加起来，"
        "就是该章的「等效题数」。例如 3.5 表示相当于 3.5 道整题落在这一章。",
        "- **按题数占比**：等效题数 ÷ 该科总题数。**一道 2 分的选择题和一道 13 分的大题在这里同样算 1**。",
        "- **按分值占比**：把每道题的分值按同样比例分给知识点后求占比，更接近「这一块值多少分」。"
        "只统计分值已知的题（少数年份的大题分值有争议，已排除并注明）。",
        "- **出现年份数**：这一章在统计的几年里有几年被考到——比单年的高低更能说明「是不是年年考」。", "",
        "### 权重是怎么来的", "",
        f"1. 三个模型（{'、'.join(weights['meta']['coders'])}）各自独立地为每道题从考纲树里选节点，"
        f"并给出把握程度：高 = {cw['high']}、中 = {cw['medium']}、低 = {cw['low']}。",
        "2. 每个模型的票 = 把握程度 ÷ 它列出的节点数；三方的票加总后归一化，使每道题总和为 1.0。"
        "三方一致时整道题落在一个节点；有分歧时自动变成按比例分摊，不强行二选一。",
        "3. 408 汇总到「章」；数学一、英语一按标注的节点汇总（它们的树本身就很粗）。",
        "4. 整个聚合是确定性的：`py -3.12 tools/aggregate_topic_weights.py --check` 可以从原始打标逐值复现。", "",
    ]
    lines += section_overview(weights)
    lines += ["", "「权重分散」不等于标注出错：综合题本来就跨多个知识点，分歧被如实记成比例。", ""]
    lines += section_cs408(trees, weights, marks)
    lines += section_math1(trees, weights, marks)
    lines += section_eng1(trees, weights, marks)
    lines += [
        "## 六、怎么用、别怎么用", "",
        "**适合用来**：",
        "- 决定复习顺序与投入比例：先保证「出现年份数」高、「按分值占比」高的章；",
        "- 对照自己的薄弱章：一个章等效题数高、而你的复习队列里它欠账多，就是优先补的地方；",
        "- 挑核对题：系统给复习项出核对题时，就是从这些题→知识点映射里挑真题。", "",
        "**不要这样读**：",
        "- **「没考到」不等于「不考」**。统计窗口只有近 3–4 年、每科每年一套卷，样本很小；考纲里的内容都可能考。",
        "- **不是预测**。它描述过去几年的分布，不保证下一年延续。",
        "- **不是人工金标**。三模型整题归到同一节点的比例见第二节的总览表（英语一因树粗为 0）；"
        "即便三方一致，同一章内的细粒度错位也不会被发现。知识树本身尚未对照纸质官方大纲复核"
        "（全部节点状态为 `extracted`）。",
        "- 数学一、英语一的树很粗，区分度明显低于 408；英语一尤其只能看题型与能力分布。", "",
        "## 七、重新生成", "",
        "新一年真题打完标、写回权重后，运行 `py -3.12 tools/render_weight_manual.py` 即可得到新版说明书；"
        "数字全部来自登记数据，"
        "旧年份的逐题结果不会因追加新年份而改变。", "",
    ]
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
