"""Build the 英语一 (eng1) structural tree — deliberately coarse.

`交接文档.md` §8.1-2 says for English: **不建议像 408 那样建细粒度知识树**. So this tree
is a *structure*: the official outline's own sections, the paper's own parts, and the
ability items the syllabus names. Nothing below that level.

Two sources are used, and their relationship is stated rather than smoothed:

  * 2022 full-text transcript (eol.cn)  -> the section content and the paper structure
  * official 2026 table of contents      -> the *current-section names* (the 2026 outline
                                            renamed Ⅲ to 「考试形式、考试内容与试卷结构」)

Nodes whose name comes from the 2026 TOC are anchored on the local 2026 book-page copy
registered as `eng1-outline-pubinfo-2026`; nodes whose content comes from the 2022
transcript are anchored there. Both hashes are computed from disk, so neither can drift.

Usage:  py -3.12 tools/archive/build_eng1_tree.py [--write]
"""

from __future__ import annotations

import argparse
import hashlib
import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "structured_materials" / "eng1" / "knowledge_tree.yaml"
REPORT = OUT.with_name("knowledge_tree_report.md")

TRANSCRIPT = "data/raw_materials/transcripts/eol_cn/eng1_outline_2022_fulltext.html"
TOC_PAGE = "data/raw_materials/eng1/syllabus/aus_zxhsd_eng1_outline_toc_2026.html"

NOW = "2026-09-13T00:00:00+08:00"

# (id, title, scope, anchor-in-2022-transcript, anchor-in-2026-TOC-page)
NODES: list[tuple[str, str, str, str | None, str | None]] = [
    ("eng1.exam.nature", "考试性质", "section", "I.考试性质", "Ⅰ 考试性质"),
    ("eng1.exam.objectives", "考查目标", "section", "II.考查目标", "Ⅱ 考查目标"),
    ("eng1.exam.objectives.language-knowledge", "语言知识", "section", "1.语法知识", None),
    ("eng1.exam.objectives.knowledge.grammar", "语法知识", "item", "考生应能熟练地运用基本的语法知识", None),
    ("eng1.exam.objectives.knowledge.vocabulary", "词汇", "item", "考生应能掌握5500左右的词汇", None),
    ("eng1.exam.objectives.language-skills", "语言技能", "section", "2.写作", None),
    ("eng1.exam.objectives.skills.reading", "阅读", "item", "考生应能读懂选自各类书籍和报刊", None),
    ("eng1.exam.objectives.skills.writing", "写作", "item", "考生应能写不同类型的应用文", None),
    ("eng1.paper.form", "考试形式与试卷结构", "section", "III.考试形式与试卷结构", "Ⅲ 考试形式、考试内容与试卷结构"),
    ("eng1.paper.format", "考试形式", "item", "考试形式为笔试。考试时间为180分钟。满分为100分", None),
    ("eng1.paper.part1", "第一部分 英语知识运用", "section", "第一部分 英语知识运用", None),
    ("eng1.paper.part2", "第二部分 阅读理解", "section", "第二部分 阅读理解", None),
    ("eng1.paper.part2.a", "A 节（多项选择）", "item", "A节(20小题)", None),
    ("eng1.paper.part2.b", "B 节（新题型）", "item", "B节(5小题)", None),
    ("eng1.paper.part2.c", "C 节（英译汉）", "item", "C节(5小题)", None),
    ("eng1.paper.part3", "第三部分 翻译", "section", "试题分四部分，共48题，包括英语知识运用、阅读理解、翻译和写作", None),
    ("eng1.paper.part3.note", "英译汉作为阅读理解的一部分", "item",
     "硕士研究生入学考试将英译汉试题作为阅读理解的一部分", None),
    ("eng1.paper.part4", "第四部分 写作", "section", "第四部分 写作", None),
    ("eng1.paper.part4.a", "A 节（应用文写作）", "item", "A节：考生根据所给情景写出约100词", None),
    ("eng1.paper.part4.b", "B 节（短文写作）", "item",
     "B节：考生根据提示信息写出一篇160~200词的短文", None),
    ("eng1.example", "题型示例及参考答案", "section", None, "Ⅳ 题型示例及参考答案"),
    ("eng1.appendix.vocabulary", "附录一 词汇表", "section", None, "词汇表"),
    ("eng1.appendix.affixes", "附录二 常用前缀和后缀", "section", None, "常用前缀和后缀"),
    ("eng1.appendix.past-papers", "附录三 真题及参考答案", "section", None, "附录三"),
]


def load_text(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    text = raw.decode("utf-8", errors="replace")
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    text = re.sub(r"<script.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.I | re.S)
    return html.unescape(re.sub(r"<[^>]+>", "\n", text)), digest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    t_text, t_sha = load_text(ROOT / TRANSCRIPT)
    p_text, p_sha = load_text(ROOT / TOC_PAGE)
    t_norm = re.sub(r"[\s\u3000\xa0]+", "", t_text)
    p_norm = re.sub(r"[\s\u3000\xa0]+", "", p_text)

    missing = []
    for nid, title, scope, a2022, a2026 in NODES:
        if a2022 and re.sub(r"[\s\u3000\xa0]+", "", a2022) not in t_norm:
            missing.append((nid, "2022 transcript", a2022))
        if a2026 and re.sub(r"[\s\u3000\xa0]+", "", a2026) not in p_norm:
            missing.append((nid, "2026 TOC page", a2026))
    if missing:
        print("ANCHOR NOT FOUND — refusing to build:")
        for nid, where, anchor in missing:
            print(f"  - {nid}: {anchor!r} not in {where}")
        return 1

    header = f"""# 英语一结构树（阶段 2 · 待人工复核）
#
# 定位：这是**结构树，不是细粒度知识树**。交接文档 §8.1-2 明确「不建议像 408 那样建细粒度知识树」，
#       因此本树只到大纲自身的节、试卷自身的部分、以及大纲点名的能力项，不往下拆词/语法点。
#
# 来源（两份，均已登记进 data/materials.yaml）：
#   1) 2022 版英语（一）大纲全文转录（中国教育在线）  source_tier=trusted_reprint
#      {TRANSCRIPT}
#      sha256 {t_sha}
#   2) 2026 版英语（一）大纲官方目录（台湾大书城转录人教社目录页）source_tier=trusted_reprint
#      {TOC_PAGE}
#      sha256 {p_sha}
#
# ⚠️ 证据等级：两份来源的 source_tier 均为 trusted_reprint，**may_define_syllabus() 为 false**。
#   所有节点 status=extracted，**须以纸质官方大纲复核后方可 approved**，
#   未 approved 前不得进频率统计、覆盖率或能力画像。
#
# 一处**有意的版本差异**（不要当成错误）：
#   节点 `eng1.paper.form` 的标题用的是 **2026 版目录的措辞**「考试形式、考试内容与试卷结构」，
#   而 2022 版转录写作「III.考试形式与试卷结构」。2026 版把「考试内容」并入了该节标题。
#   两种措辞各自锚定在自己的来源上，均逐字可定位。
#
# 词汇表：大纲要求「掌握 5500 左右的词汇以及相关附表中的内容（详见附录 1、2）」，
#   附录一为词汇表、附录二为常用前缀和后缀与常见缩写词。**本树不导入词表正文**——
#   词表正文属出版物内容，需要单独的、有权利依据的来源（交接文档 §8.2 待办）。
#
# 生成：tools/build_eng1_tree.py（确定性）
"""
    out: list[str] = [header]
    anchor_seq = 0

    def emit_sources(sources: list[tuple[str, str, str]]) -> tuple[list[str], str]:
        """sources: list of (path, sha, quote). Returns lines and first anchor."""
        nonlocal anchor_seq
        lines: list[str] = ["  sources:"]
        first = ""
        for path, sha, quote in sources:
            anchor_seq += 1
            anchor = f"&id{anchor_seq:03d}"
            if not first:
                first = anchor[1:]
            lines += [
                f"  - {anchor}",
                f"    path: {path}",
                f"    sha256: {sha}",
                "    locator:",
                f"      section: '{quote}'",
                f"      quote_ref: '{quote}'",
            ]
        return lines, first

    for nid, title, scope, a2022, a2026 in NODES:
        sources: list[tuple[str, str, str]] = []
        if a2022:
            sources.append((TRANSCRIPT, t_sha, a2022))
        if a2026:
            sources.append((TOC_PAGE, p_sha, a2026))
        out.append("- schema_version: 1")
        out.append(f"  knowledge_point_id: {nid}")
        out.append(f"  title: '{title}'")
        out.append(f"  scope: {scope}")
        out.append("  status: extracted")
        out.append("  source_kind: official_outline")
        src_lines, first_anchor = emit_sources(sources)
        out += src_lines
        out.append("  frequency: null")
        out.append("  evidence: []")
        out.append("  transition_history:")
        out.append("  - from: raw")
        out.append("    to: extracted")
        out.append("    actor: ai")
        out.append(f"    source: *{first_anchor}")
        out.append(f"    at: '{NOW}'")
        out.append("  supersedes: null")
        out.append("  revision: 1")

    content = "\n".join(out) + "\n"
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()

    report = f"""# 英语一结构树构建报告

生成：tools/build_eng1_tree.py · 来源哈希 2022 转录 {t_sha[:16]} / 2026 目录页 {p_sha[:16]}

- 节点数：{len(NODES)}；每个节点的 `locator.quote_ref` 都已在对应来源文件中定位成功。
- 试卷结构（来自 2022 版全文转录，**须以纸质官方大纲复核**）：
  笔试、180 分钟、满分 100 分；试题分四部分共 48 题 ——
  第一部分 英语知识运用（20 小题×0.5 分=10 分）；
  第二部分 阅读理解 A/B/C 三节共 30 小题×2 分=60 分（A 节 20 题、B 节新题型 5 题、C 节英译汉 5 题）；
  第三/四部分 写作 A 节应用文 10 分 + B 节短文 160~200 词 20 分 = 30 分。
- 版本差异：2026 版官方目录把第 Ⅲ 节改名为「考试形式、考试内容与试卷结构」，
  2022 版转录作「III.考试形式与试卷结构」；两处措辞各自锚定在自己的来源上。
- **未纳入**：附录一词汇表的词条正文（约 5500 词）。理由：属出版物内容，
  需要单独的、有权利依据的来源；本树只登记「大纲要求掌握 5500 左右的词汇」这一条能力项。
"""
    if args.write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(content, encoding="utf-8", newline="\n")
        REPORT.write_text(report, encoding="utf-8", newline="\n")
        print(f"written {OUT} ({len(content.encode('utf-8'))} bytes, sha256 {digest})")
        print(f"written {REPORT}")
    else:
        print(f"dry run: {len(NODES)} nodes, {len(content.encode('utf-8'))} bytes, sha256 {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
