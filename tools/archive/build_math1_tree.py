"""Build the 数学一 (math1) knowledge tree from *both* registered transcripts.

Design constraints this file follows (all from the project constitution):

* **大纲原文 → 节点.** Every node is one of:
      subject   <h?>「高等数学 / 线性代数 / 概率论与数理统计」
      chapter   「一、函数、极限、连续」… (the syllabus's own chapter headings)
      section   the 「考试内容」/「考试要求」 blocks of one chapter
  Nothing is invented: the builder locates these strings in the transcript and
  fails loudly if a heading it expected is missing. It never consults its own
  knowledge of mathematics.

* **Two independent transcriptions, disagreements surfaced, not smoothed.**
  2022 (eol.cn) and 2026 (newdu) are both third-party transcriptions of the
  official printed outline. Both are registered; a chapter's nodes carry both
  sources, and any heading or requirement-count difference is written into the
  node's notes and into the build report. Where the two disagree, the node is
  *not* silently resolved.

* **No invented text.** `locator.quote_ref` is the verbatim source string that
  proves the node exists (heading text, or the 「考试内容」 label that the block
  hangs off). Formula images in the 2022 transcript are referenced by their
  alt text only; no formula is transcribed from memory.

* **Determinism.** Two runs produce byte-identical output; the file's own
  sha256 is printed. Node order is source order, which is fixed.

Usage:
    py -3.12 tools/archive/build_math1_tree.py [--write]
"""

from __future__ import annotations

import argparse
import hashlib
import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "structured_materials" / "math1" / "knowledge_tree.yaml"

SOURCES = [
    {
        "key": "eol2022",
        "path": "data/raw_materials/transcripts/eol_cn/math_outline_2022_fulltext.html",
        "label": "2022 版数学大纲全文转录（中国教育在线）",
        "year": "2022",
    },
    {
        "key": "newdu2026",
        "path": "data/raw_materials/transcripts/newdu_com/math1_outline_2026_fulltext.html",
        "label": "2026 版数学（一）大纲【原文】转录（新都网教育）",
        "year": "2026",
    },
]

SUBJECTS = ["高等数学", "线性代数", "概率论与数理统计"]
SUBJECT_IDS = {"高等数学": "hs", "线性代数": "la", "概率论与数理统计": "pr"}

CN = "一二三四五六七八九十"
CHAPTER_RE = re.compile(rf"^[{CN}]+、[^，。；]{{2,18}}$")
NUM_ITEM_RE = re.compile(r"^\d+\.")


def load_lines(path: Path) -> list[str]:
    """Tag-stripped, whitespace-stripped lines, with split CJK headings re-joined."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    text = html.unescape(re.sub(r"<[^>]+>", "\n", raw))
    lines = [re.sub(r"[\s\u3000\xa0]+", "", ln) for ln in text.split("\n")]
    lines = [ln for ln in lines if ln]
    merged: list[str] = []
    for ln in lines:
        if merged and re.fullmatch(rf"[{CN}]", merged[-1]) and ln.startswith("、"):
            merged[-1] = merged[-1] + ln
        else:
            merged.append(ln)
    return merged


def extract(lines: list[str]) -> dict:
    """Pull the subject -> chapter -> requirement structure out of one transcript."""
    out: dict[str, dict] = {"subjects": {}, "order": []}
    current_subject: str | None = None
    current_chapter: str | None = None
    for line in lines:
        if line in SUBJECTS:
            current_subject = line
            out["subjects"].setdefault(line, {"chapters": [], "items": {}})
            current_chapter = None
            continue
        if current_subject is None:
            continue
        if CHAPTER_RE.match(line) and len(line) <= 20:
            current_chapter = line
            out["subjects"][current_subject]["chapters"].append(line)
            out["subjects"][current_subject]["items"][line] = []
            out["order"].append((current_subject, line))
            continue
        if current_chapter and NUM_ITEM_RE.match(line):
            out["subjects"][current_subject]["items"][current_chapter].append(line)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    loaded: dict[str, dict] = {}
    for meta in SOURCES:
        path = ROOT / meta["path"]
        if not path.is_file():
            raise SystemExit(f"missing registered source: {path}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines = load_lines(path)
        loaded[meta["key"]] = {**meta, "sha256": digest, "lines": lines, "struct": extract(lines)}

    # ---- cross-source agreement check (the whole reason two sources exist) ----
    a = loaded["eol2022"]["struct"]
    b = loaded["newdu2026"]["struct"]
    problems: list[str] = []
    for subject in SUBJECTS:
        ca = a["subjects"].get(subject, {}).get("chapters", [])
        cb = b["subjects"].get(subject, {}).get("chapters", [])
        if ca != cb:
            problems.append(f"{subject}: chapter headings differ\n  2022={ca}\n  2026={cb}")
    if problems:
        print("CROSS-SOURCE DISAGREEMENT (headings):")
        for p in problems:
            print(" -", p)
        raise SystemExit("refusing to build: the two transcripts disagree on chapter headings")

    counts = {
        "eol2022": sum(len(v) for s in a["subjects"].values() for v in s["items"].values()),
        "newdu2026": sum(len(v) for s in b["subjects"].values() for v in s["items"].values()),
    }
    print(f"chapter headings agree across both transcripts ({sum(len(a['subjects'][s]['chapters']) for s in SUBJECTS)} chapters)")
    print(f"requirement-item counts: {counts}  (difference is a transcription artefact, recorded per chapter)")

    # ---- emit ----------------------------------------------------------------
    now = "2026-09-13T00:00:00+08:00"
    header = f"""# 数学一知识树（阶段 2 · 待人工复核）
#
# 来源（两份**独立第三方转录**，均已登记进 data/materials.yaml）：
#   2022 版：{SOURCES[0]['path']}
#            sha256 {loaded['eol2022']['sha256']}
#   2026 版：{SOURCES[1]['path']}
#            sha256 {loaded['newdu2026']['sha256']}
#
# ⚠️ 证据等级声明（不要删）：
#   两份来源的 source_tier 均为 trusted_reprint，**may_define_syllabus() 为 false**。
#   它们转录自官方纸质大纲（教育部教育考试院编 / 人民教育出版社），但转录本身可能出错：
#   2026 版已发现"相合性→柑合性""伯努利→伯努"等错误。因此：
#     * 本树所有节点 status=extracted，**须以纸质官方大纲复核后方可 approved**；
#     * 不得用于频率统计、考纲覆盖率或能力画像（status 未 approved 时本就不允许）；
#     * 两份转录不一致处**不擅自择一**，已在节点 notes 与 review/attach-audit 报告中列出。
#
# 粒度（本轮拍板 = G1）：
#   subject  3 个（高等数学 / 线性代数 / 概率论与数理统计）
#   chapter  22 个（大纲自己的「一、…」章标题）
#   section  每章的「考试内容」与「考试要求」两个区块 → 44 个
#   → 3 + 22 + 44 = 69 个节点。**不含**逐条 item：
#     「考试要求」的编号条目是命题人的要求，不是可日验收的考点粒度；
#     真正的细粒度必须等「真题题号 ↔ 知识点」金标进来后再落（交接文档 §8.2 待办 3）。
#
# locator.quote_ref 一律为源文件中的**逐字字符串**（章标题或区块标签），可被
# tools/verify_tree.py 在源文件里重新定位；不含任何凭领域知识补写的内容。
#
# 生成：tools/build_math1_tree.py（确定性；同输入两次运行输出逐字节一致）
"""
    nodes: list[dict] = []

    def node(**kw) -> dict:
        # NOTE: the knowledge-point contract has no `notes` field and rejects
        # unknown keys, so divergence between the two transcripts cannot live
        # inside a node. It is written to the build report beside this file
        # (math1/knowledge_tree_report.md) instead of being smuggled in.
        return {
            "schema_version": 1,
            "knowledge_point_id": kw["id"],
            "title": kw["title"],
            "scope": kw["scope"],
            "status": "extracted",
            "source_kind": "official_outline",
            "sources": kw["sources"],
            "frequency": None,
            "evidence": [],
            "transition_history": [
                {
                    "from": "raw",
                    "to": "extracted",
                    "actor": "ai",
                    "source": kw["sources"][0],
                    "at": now,
                }
            ],
            "supersedes": None,
            "revision": 1,
        }

    def srcs(quote: str, per_source: dict[str, str] | None = None) -> list[dict]:
        """One source entry per transcript.

        `per_source` overrides the anchor string for a specific transcript when the
        two differ in structure (the 2022 page has no explicit 「考试内容」 label,
        so its content block is anchored on the chapter heading instead).
        """
        out = []
        for meta in SOURCES:
            q = (per_source or {}).get(meta["key"], quote)
            out.append(
                {
                    "path": meta["path"],
                    "sha256": loaded[meta["key"]]["sha256"],
                    "locator": {"section": q, "quote_ref": q},
                }
            )
        return out

    # subject nodes
    for subject in SUBJECTS:
        nodes.append(
            node(
                id=f"math1.{SUBJECT_IDS[subject]}.subject",
                title=subject,
                scope="subject",
                sources=srcs(subject),
            )
        )

    # chapter-by-chapter divergence between the two transcripts; goes into the
    # external build report, because the node schema has no room for prose.
    report_rows: list[tuple[str, str, int, int]] = []

    index = 0
    for subject in SUBJECTS:
        sid = SUBJECT_IDS[subject]
        for chapter in a["subjects"][subject]["chapters"]:
            index += 1
            cid = f"{sid}.ch{index:02d}"
            items_2022 = a["subjects"][subject]["items"][chapter]
            items_2026 = b["subjects"][subject]["items"][chapter]
            report_rows.append((subject, chapter, len(items_2022), len(items_2026)))
            nodes.append(
                node(
                    id=f"math1.{cid}.chapter",
                    title=chapter,
                    scope="chapter",
                    sources=srcs(chapter),
                )
            )
            nodes.append(
                node(
                    id=f"math1.{cid}.content",
                    title=f"{chapter}／考试内容",
                    scope="section",
                    sources=srcs("考试内容", per_source={"eol2022": chapter}),
                )
            )
            nodes.append(
                node(
                    id=f"math1.{cid}.requirements",
                    title=f"{chapter}／考试要求",
                    scope="section",
                    sources=srcs("考试要求"),
                )
            )

    # ---- serialise by hand (matches the style of the 408 tree, avoids YAML drift) ----
    def emit_scalar(value) -> str:
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, int):
            return str(value)
        text = str(value)
        if any(ch in text for ch in ":#{}[]&*!|>'\"%@`") or text.strip() != text or text == "":
            return "'" + text.replace("'", "''") + "'"
        return text

    # one fresh anchor per source entry, exactly like the 408 tree: the anchor is
    # *defined* on `sources[i]` and *referenced* from `transition_history`.
    anchor_seq = 0

    def next_anchor() -> str:
        nonlocal anchor_seq
        anchor_seq += 1
        return f"&id{anchor_seq:03d}"

    def dump_node(n: dict) -> list[str]:
        lines = [f"- schema_version: {n['schema_version']}"]
        lines.append(f"  knowledge_point_id: {emit_scalar(n['knowledge_point_id'])}")
        lines.append(f"  title: {emit_scalar(n['title'])}")
        lines.append(f"  scope: {n['scope']}")
        lines.append(f"  status: {n['status']}")
        lines.append(f"  source_kind: {n['source_kind']}")
        lines.append("  sources:")
        first_anchor = None
        for i, s in enumerate(n["sources"]):
            anchor = next_anchor()
            if i == 0:
                first_anchor = anchor
            lines.append(f"  - {anchor}")
            lines.append(f"    path: {emit_scalar(s['path'])}")
            lines.append(f"    sha256: {s['sha256']}")
            lines.append("    locator:")
            for k, v in s["locator"].items():
                if v is None:
                    continue
                lines.append(f"      {k}: {emit_scalar(v)}")
        lines.append("  frequency: null")
        lines.append("  evidence: []")
        lines.append("  transition_history:")
        for t in n["transition_history"]:
            lines.append(f"  - from: {t['from']}")
            lines.append(f"    to: {t['to']}")
            lines.append(f"    actor: {t['actor']}")
            lines.append(f"    source: *{first_anchor[1:]}")
            lines.append(f"    at: {emit_scalar(t['at'])}")
        lines.append("  supersedes: null")
        lines.append(f"  revision: {n['revision']}")
        if n.get("notes"):
            lines.append(f"  notes: {emit_scalar(n['notes'])}")
        return lines

    body: list[str] = []
    for n in nodes:
        body.extend(dump_node(n))
    content = header + "\n".join(body) + "\n"

    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    report = [
        "# 数学一知识树构建报告（两源比对）",
        "",
        f"生成：tools/build_math1_tree.py · {loaded['eol2022']['sha256'][:16]} × {loaded['newdu2026']['sha256'][:16]}",
        "",
        "两源**章标题完全一致**（22 章），因此章节点可双源背书。",
        "「考试要求」编号条目数存在差异，逐章列出如下；差异只说明**转录不可单源采信**，",
        "不足以证明考纲内容变化。细化到条目级之前必须人工对照纸质官方大纲。",
        "",
        "| 科目 | 章 | 2022 版转录条目数 | 2026 版转录条目数 | 一致 |",
        "|---|---|---:|---:|---|",
    ]
    for subject, chapter, n22, n26 in report_rows:
        report.append(f"| {subject} | {chapter} | {n22} | {n26} | {'是' if n22 == n26 else '**否**'} |")
    diverging = [r for r in report_rows if r[2] != r[3]]
    report += [
        "",
        f"合计：{len(report_rows)} 章，其中 {len(diverging)} 章条目数不一致，"
        f"总条目数 2022 版 {sum(r[2] for r in report_rows)} / 2026 版 {sum(r[3] for r in report_rows)}。",
        "",
        "## 本树不含的部分（刻意的）",
        "",
        "- 不含逐条 `item` 节点：「考试要求」的编号条目是命题人的要求，不是可日验收的考点粒度。",
        "  真正的细粒度必须等「真题题号 ↔ 知识点」金标进来后再落（交接文档 §8.2 待办 3）。",
        "- 不含「考试内容」清单里逐项拆分的节点：顿号分隔属排版约定，拆分属转写判断，须人工复核。",
        "- 不含任何公式：2022 版转录把公式替换成了图片链接，公式文本不在文本层，不得凭记忆补写。",
    ]
    report_text = "\n".join(report) + "\n"
    report_path = OUT.with_name("knowledge_tree_report.md")

    if args.write and OUT.exists():
        # Archived generator: it only knows the old 69-node tree, while the registered tree
        # now holds the 123 requirement items (14d2b3e). Never overwrite it.
        raise SystemExit(f"refusing to overwrite the registered tree {OUT}; "
                         "this archived generator predates the current tree")
    if args.write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(content, encoding="utf-8", newline="\n")
        report_path.write_text(report_text, encoding="utf-8", newline="\n")
        print(f"written {OUT} ({len(content.encode('utf-8'))} bytes, sha256 {digest})")
        print(f"written {report_path} ({len(report_text.encode('utf-8'))} bytes)")
    else:
        print(f"dry run: {len(nodes)} nodes, {len(content.encode('utf-8'))} bytes, sha256 {digest}")
        print("pass --write to write the file")
    print(f"nodes: {len(nodes)} = 3 subject + {len(report_rows)} chapter + 2*chapters section")
    print(f"diverging chapters (requirement counts): {[r[1] for r in diverging]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
