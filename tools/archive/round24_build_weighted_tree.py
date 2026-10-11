"""Build the 408 multi-source *weighted* knowledge tree (round 24).

Inputs (all previously verified by the orchestrator, reused as-is):
  Source A: data/raw_materials/cs408/syllabus/archive408_408_outline_2026.html
  Source B: %TEMP%/kaoyan-probe/ghsurvey/downloads/408_syllabus_2022.pdf
  Source C: %TEMP%/kaoyan-probe/ghsurvey/downloads/408q_full.json (kaichan-kc/408-questions)
  Baseline: data/structured_materials/cs408/knowledge_tree.yaml (single-source, 403 nodes)

This script does NOT re-implement source A/B extraction -- it imports the
already-reviewed extractor from tools/round22_extract.py (see
review/rounds/round-22-408-dual-source-report.md) and only adds:

  1. a reorder-aware, containment-based aligner that maps 2022 (B) structure
     onto the existing 2026-derived (A) baseline tree, node for node;
  2. a small, explicitly-justified manual override list for renames/splits
     that plain string containment cannot resolve (documented inline, each
     with the reason a human would accept it);
  3. weight/evidence_tag assignment per the round-22 report's own table;
  4. an independent, non-authoritative cross-check against source C's
     per-question `knowledgeTagsId` tag, reported honestly as unmappable to
     tree node IDs (no dictionary decoding those tag numbers exists locally).

Output: data/structured_materials/cs408/knowledge_tree_weighted.yaml
Also writes a UTF-8 evidence dump used by the round-24 report generator:
  review/rounds/round24_evidence.json (source data for the markdown report;
  not itself a deliverable data file).
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from cs408_outline_extract import (  # noqa: E402
    SUBJECTS,
    clean_display,
    extract_2022,
    extract_2026,
    key as base_key,
)

SOURCE_A_PATH = ROOT / "data/raw_materials/cs408/syllabus/archive408_408_outline_2026.html"
SOURCE_B_PATH = ROOT / "data/raw_materials/cs408/syllabus/408_syllabus_2022.pdf"
BASELINE_TREE_PATH = ROOT / "data/structured_materials/cs408/knowledge_tree.yaml"
OUT_TREE_PATH = ROOT / "data/structured_materials/cs408/knowledge_tree_weighted.yaml"
# Scratch evidence dump used only while drafting the round-24 report; kept
# outside the repo (review/rounds/ is reserved for the report markdown
# itself) in the same %TEMP%/kaoyan-probe scratch area earlier rounds used.
EVIDENCE_OUT_PATH = Path(r"C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\round24_evidence.json")

SOURCE_C_PATH = Path(
    r"C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\ghsurvey\downloads\408q_full.json"
)
SOURCE_C_EXPECTED_SHA = "451197409bd3471168ccb1754a86e766bf528c8f354ec1866ace82701d03f275"
SOURCE_C_EXPECTED_BYTES = 1056638

SUBJECT_CODE = {"数据结构": "ds", "计算机组成原理": "co", "操作系统": "os", "计算机网络": "cn"}

# ---------------------------------------------------------------------------
# OCR / text-layer-artifact correction (2022 PDF text layer only).
#
# These are narrow, targeted substring fixes applied to a *copy* of the raw
# 2022 title text used only to compute a matching key. The untouched raw text
# is always preserved verbatim in the node's aliases (tagged ocr_risk_raw) --
# this function must never be used to overwrite what gets stored as the
# alias's displayed text.
# ---------------------------------------------------------------------------
OCR_RISK_MARKERS = ("Cach ", "Cach和", "页椎", "软件 次结构", "软件次结构", "磁盘磁盘结构", "宽带、码元", "1/O", "l/o", "1/o")


def ocr_correct_for_matching(s: str) -> str:
    s = s.replace("Cach ", "Cache ").replace("Cach和", "Cache和")
    s = s.replace("页椎", "页框")
    s = s.replace("软件 次结构", "软件层次结构").replace("软件次结构", "软件层次结构")
    s = s.replace("磁盘磁盘结构", "磁盘 磁盘结构")
    s = s.replace("宽带、码元", "带宽、码元")
    return s


def is_ocr_risk(raw_2022_text: str) -> bool:
    return any(m in raw_2022_text for m in OCR_RISK_MARKERS)


def key(s: str) -> str:
    return base_key(ocr_correct_for_matching(s))


def contained(a: str, b: str) -> bool:
    if not a or not b:
        return False
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    if len(short) >= 4 and short in long_:
        return True
    if len(short) >= 2 and long_.startswith(short):
        return True
    return False


# ---------------------------------------------------------------------------
# Generic reorder-aware, containment-fallback aligner.
#
# Phase 1 (SequenceMatcher 'equal' opcodes): exact-key matches in original
#   document order -- this is what round-22 already validated.
# Phase 2 (manual overrides, if given): exact-key match against a small
#   explicit list of (text_a, text_b) pairs that a human confirmed refer to
#   the same concept despite failing key()/containment (synonyms, particles).
# Phase 3: exact-key match pooled *across* every non-equal opcode block
#   (fixes plain reorders that SequenceMatcher splits into insert+delete
#   pairs rather than a single replace).
# Phase 4: containment match (one key is a >=4-char substring of the other,
#   or a >=2-char prefix -- the latter catches the extraction pattern where
#   2022's item text is "<short title><attached explanation>" with no
#   separator).
# Anything left is reported as only_a / only_b.
# ---------------------------------------------------------------------------
def align(items_a, items_b, key_fn=key, extra_pairs=None):
    ka = [key_fn(t) for t in items_a]
    kb = [key_fn(t) for t in items_b]
    sm = SequenceMatcher(None, ka, kb, autojunk=False)
    pairs = []
    pool_a, pool_b = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for oi, oj in zip(range(i1, i2), range(j1, j2)):
                pairs.append((oi, oj, "exact"))
        else:
            pool_a.extend(range(i1, i2))
            pool_b.extend(range(j1, j2))
    used_b = set()

    if extra_pairs:
        override_keys = {(key_fn(a), key_fn(b)) for a, b in extra_pairs}
        still_a = []
        for oi in pool_a:
            match = next((oj for oj in pool_b if oj not in used_b and (ka[oi], kb[oj]) in override_keys), None)
            if match is not None:
                pairs.append((oi, match, "manual_override"))
                used_b.add(match)
            else:
                still_a.append(oi)
        pool_a = still_a

    still_a = []
    for oi in pool_a:
        match = next((oj for oj in pool_b if oj not in used_b and ka[oi] == kb[oj]), None)
        if match is not None:
            pairs.append((oi, match, "reorder_exact"))
            used_b.add(match)
        else:
            still_a.append(oi)
    pool_a = still_a

    still_a = []
    for oi in pool_a:
        match = next((oj for oj in pool_b if oj not in used_b and contained(ka[oi], kb[oj])), None)
        if match is not None:
            pairs.append((oi, match, "fuzzy"))
            used_b.add(match)
        else:
            still_a.append(oi)
    pool_a = still_a

    for oi in pool_a:
        pairs.append((oi, None, "only_a"))
    for oj in pool_b:
        if oj not in used_b:
            pairs.append((None, oj, "only_b"))
    return pairs


# ---------------------------------------------------------------------------
# Manual overrides: each entry below is a case where the 2022 and 2026
# wording differ enough (synonym, dropped/added particle, added
# abbreviation, scope broadened from process to process+thread) that no
# substring relationship exists, but inspecting both full titles side by
# side leaves no reasonable doubt they name the same syllabus concept in the
# same structural position. Every entry is listed and justified in the
# round-24 report; nothing here is inferred silently.
# ---------------------------------------------------------------------------
MANUAL_CHAPTER = {
    "操作系统": [("操作系统概述", "操作系统基础")],
    "计算机网络": [("计算机网络体系结构", "计算机网络概述")],
}
MANUAL_SECTION = {
    ("计算机组成原理", "存储器层次结构"): [("存储器的层次化结构", "层次化存储器的基本结构")],
    ("计算机组成原理", "数据的表示和运算"): [("定点数的表示和运算", "整数的表示和运算")],
    ("计算机网络", "计算机网络概述"): [("计算机网络概述", "计算机网络基本概念")],
    ("操作系统", "操作系统基础"): [
        ("操作系统的概念、特征、功能和提供的服务", "操作系统的基本概念"),
        ("操作系统的发展与分类", "操作系统发展历程"),
    ],
}
MANUAL_ITEM = {
    ("数据结构", "树与二叉树", "二叉树"): [("二叉树的定义及其主要特征", "二叉树的定义及其主要特性")],
    ("计算机组成原理", "总线和输入/输出系统", "总线"): [("总线的事务和定时", "总线事务和定时")],
    ("计算机组成原理", "数据的表示和运算", "数制与编码"): [
        ("进位计数制及其相互转换", "进位计数制及其数据之间的相互转换"),
    ],
    ("计算机组成原理", "存储器层次结构", "高速缓冲存储器(Cache)"): [("Cache 的基本工作原理", "Cache 的基本原理")],
    ("计算机组成原理", "中央处理器(CPU)", "多处理器基本概念"): [
        ("多核处理器(multi-core)的基本概念", "多核(multi-core)处理器的基本概念"),
    ],
    ("操作系统", "进程管理", "进程与线程"): [
        ("进程概念", "进程与线程的基本概念"),
        ("进程的状态与转换", "进程/线程的状态与转换"),
    ],
    ("操作系统", "进程管理", "CPU 调度与上下文切换"): [
        (
            "典型调度算法 先来先服务调度算法。短作业(短进程、短线程)优先调度算法,时间片轮转调度算法,优先级调度 算法,高响应比优先调度算法,多级队列调度算法,多级反馈队列调度算法。",
            "CPU 调度算法",
        ),
    ],
    ("计算机网络", "应用层", "网络应用模型"): [("客户/服务器模型", "客户/服务器(C/S)模型")],
    ("计算机网络", "计算机网络概述", "计算机网络基本概念"): [
        ("计算机网络的概念、组成与功能", "计算机网络的定义、组成与功能"),
        ("计算机网络主要性能指标", "计算机网络的主要性能指标"),
    ],
    ("计算机网络", "计算机网络概述", "计算机网络体系结构"): [
        ("ISO/OSI 参考模型和 TCP/IP 模型", "ISO/OSI 参考模型和 TCP/IP 参考模型"),
    ],
    ("操作系统", "操作系统基础", "程序运行环境"): [
        ("程序运行时内存映像与地址空间", "程序运行时的内存映像与地址空间"),
    ],
}

# Genuine one-2022-item -> many-2026-item splits. These are *not* run through
# align()'s pairwise consumption (which would steal the 2022 index from the
# other, already-correct containment match); instead each target 2026 item
# (identified by its baseline id once built) gets a supplementary evidence
# link recorded after normal alignment finishes.
SPLIT_LINKS = [
    {
        "subject": "计算机网络", "chapter": "传输层", "section": "TCP 协议",
        "source_2022": "TCP 流量控制与拥塞控制", "target_2026": "TCP 拥塞控制",
        "note": "2022 一条『TCP 流量控制与拥塞控制』在 2026 拆为『TCP 流量控制』『TCP 拥塞控制』两条；前者已由包含式匹配覆盖，本条补记后者。",
    },
    {
        "subject": "计算机组成原理", "chapter": "数据的表示和运算", "section": "整数的表示和运算",
        "source_2022": "无符号整数的表示与运算;带符号整数的表示与运算", "target_2026": "无符号整数的表示和运算",
        "note": "2022 一条以分号并列『无符号/带符号整数的表示与运算』，2026 拆为两条独立条目。",
    },
    {
        "subject": "计算机组成原理", "chapter": "数据的表示和运算", "section": "整数的表示和运算",
        "source_2022": "无符号整数的表示与运算;带符号整数的表示与运算", "target_2026": "带符号整数的表示和运算",
        "note": "同上，拆分出的第二条。",
    },
]

# Cross-section moves: same concept, but 2026 moved the item under a
# different section than the one it lived under in 2022.
CROSS_SECTION_LINKS = [
    {
        "subject": "计算机组成原理", "chapter": "数据的表示和运算",
        "source_section": "定点数的表示和运算", "source_2022": "定点数的编码表示:无符号数的表示,带符号整数的表示。",
        "target_section": "数制与编码", "target_2026": "定点数的编码表示",
        "note": "内容从 2022『定点数的表示和运算』节迁移至 2026『数制与编码』节，条目本身对应关系明确。",
    },
]

# Item promoted to section scope between years (2022 numbered item -> 2026
# section heading with no numbered sub-items of its own).
SCOPE_PROMOTIONS = [
    {
        "subject": "数据结构", "chapter": "线性表",
        "source_section": "线性表的实现", "source_2022": "线性表的应用",
        "target_section": "线性表的应用",
        "note": "2022 是『线性表的实现』节下的编号条目，2026 提升为独立小节标题，内容范围不变。",
    },
]

# Items the round-22 report explicitly flagged as *not* to auto-merge despite
# superficial similarity (terminology genuinely differs in scope/emphasis).
# Recorded here purely so the builder's output matches that documented
# decision instead of silently drifting from it.
EXPLICITLY_NOT_MERGED = [
    ("计算机组成原理", "计算机硬件的基本组成", "计算机硬件的基本结构", "组成 vs 结构：不确定是否同一考点范围，未强行合并"),
    ("计算机网络", "路由表与路由转发", "路由表与分组转发", "round-22 报告已判定为术语差异，保持低权重待核，不自动合并"),
]

RECENT_NEW_ITEM_TITLES = {"堆及其应用", "多处理机调度"}


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_baseline():
    raw = yaml.safe_load(BASELINE_TREE_PATH.read_text(encoding="utf-8"))
    return raw if isinstance(raw, list) else raw["items"]


def strip_number_prefix(title: str) -> str:
    return clean_display(title)


def main():
    baseline = load_baseline()
    baseline_by_id = {n["knowledge_point_id"]: n for n in baseline}

    # --- lookups from baseline id -> (subject_code, key) ------------------
    chapter_key_to_id = {}
    section_key_to_id = {}
    item_key_to_id = {}
    detail_note_ids = []
    subject_scope_ids = []
    for n in baseline:
        pid = n["knowledge_point_id"]
        code = pid.split(".")[1]
        scope = n.get("scope")
        last = pid.rsplit(".", 1)[-1]
        if scope == "subject":
            subject_scope_ids.append(pid)
        elif scope == "chapter":
            chapter_key_to_id[(code, key(strip_number_prefix(n["title"])))] = pid
        elif scope == "section":
            # section ids are chapter_id + ".section-NN"; chapter id is the
            # id minus its last segment.
            chapter_id = pid.rsplit(".", 1)[0]
            section_key_to_id[(chapter_id, key(strip_number_prefix(n["title"])))] = pid
        elif scope == "item":
            if re.match(r"^item-\d+", last):
                item_key_to_id[(code, key(n["title"]))] = pid
            else:
                detail_note_ids.append(pid)

    d22 = extract_2022(SOURCE_B_PATH)
    d26 = extract_2026(SOURCE_A_PATH)
    full_2022_key = key(d22["normalized_source_text"])

    node_events = {}  # knowledge_point_id -> dict(match_kind, raw_2022_text_or_None, note)
    new_nodes = []    # 2022-only orphans not present in baseline
    align_log = defaultdict(list)  # subject -> list of row dicts, for the report
    counters = Counter()

    for subject_name in d22["subjects"]:
        code = SUBJECT_CODE[subject_name]
        ch22 = d22["subjects"][subject_name]["chapters"]
        ch26 = d26["subjects"][subject_name]["chapters"]
        chpairs = align([c["title"] for c in ch22], [c["title"] for c in ch26], extra_pairs=MANUAL_CHAPTER.get(subject_name))

        for ci, cj, ckind in chpairs:
            if cj is None:
                # chapter only in 2022 -- did not occur in any of the 4 subjects
                # after manual overrides; log defensively if it ever does.
                align_log[subject_name].append({"level": "chapter", "kind": "only_22", "title": ch22[ci]["title"]})
                counters["chapter_only_22"] += 1
                continue
            c26 = ch26[cj]
            chapter_id = chapter_key_to_id.get((code, key(strip_number_prefix(c26["title"]))))
            if ci is None:
                node_events[chapter_id] = {"kind": "only_26", "raw_2022": None, "note": "2026 新增章，2022 无对应位置或内容"}
                align_log[subject_name].append({"level": "chapter", "kind": "only_26", "ch26": c26["title"]})
                counters["chapter_only_26"] += 1
                sections26_todo = list(enumerate(c26["sections"]))
                for _, s26 in sections26_todo:
                    section_id = section_key_to_id.get((chapter_id, key(strip_number_prefix(s26["title"]))))
                    node_events[section_id] = {"kind": "only_26", "raw_2022": None, "note": "所属章为 2026 新增章"}
                    for it26 in s26["items"]:
                        item_id = item_key_to_id.get((code, key(it26)))
                        node_events[item_id] = {"kind": "only_26_new_structure", "raw_2022": None, "note": "所属章为 2026 新增章"}
                continue
            c22 = ch22[ci]
            align_log[subject_name].append({"level": "chapter", "kind": ckind, "ch22": c22["title"], "ch26": c26["title"]})
            counters["chapter_" + ckind] += 1
            if ckind != "exact":
                node_events[chapter_id] = {"kind": ckind, "raw_2022": c22["title"], "note": "章改名：位置相同、下属小节与条目内容重叠"}
            else:
                node_events[chapter_id] = {"kind": "exact", "raw_2022": c22["title"], "note": None}

            spairs = align(
                [s["title"] for s in c22["sections"]], [s["title"] for s in c26["sections"]],
                extra_pairs=MANUAL_SECTION.get((subject_name, c26["title"])),
            )
            for si, sj, skind in spairs:
                if sj is None:
                    align_log[subject_name].append({"level": "section", "kind": "only_22", "chapter": c26["title"], "s22": c22["sections"][si]["title"]})
                    counters["section_only_22"] += 1
                    # No baseline id exists for a 2022-only section; its items
                    # become new orphan nodes with a synthetic parent tag.
                    for it22 in c22["sections"][si]["items"]:
                        new_nodes.append({
                            "subject": subject_name, "code": code, "chapter_id": chapter_id,
                            "parent_section_title": c22["sections"][si]["title"], "section_id": None,
                            "raw_2022": it22,
                        })
                    continue
                s26 = c26["sections"][sj]
                section_id = section_key_to_id.get((chapter_id, key(strip_number_prefix(s26["title"]))))
                if si is None:
                    node_events[section_id] = {"kind": "only_26", "raw_2022": None, "note": "2026 新增小节，2022 无对应位置或内容"}
                    align_log[subject_name].append({"level": "section", "kind": "only_26", "chapter": c26["title"], "s26": s26["title"]})
                    counters["section_only_26"] += 1
                    for it26 in s26["items"]:
                        item_id = item_key_to_id.get((code, key(it26)))
                        node_events[item_id] = {"kind": "only_26_new_structure", "raw_2022": None, "note": "所属节为 2026 新增小节"}
                    continue
                s22 = c22["sections"][si]
                align_log[subject_name].append({"level": "section", "kind": skind, "chapter": c26["title"], "s22": s22["title"], "s26": s26["title"]})
                counters["section_" + skind] += 1
                if skind != "exact":
                    node_events[section_id] = {"kind": skind, "raw_2022": s22["title"], "note": "小节改名/重排：位置相同、条目内容重叠"}
                else:
                    node_events[section_id] = {"kind": "exact", "raw_2022": s22["title"], "note": None}

                ipairs = align(s22["items"], s26["items"], extra_pairs=MANUAL_ITEM.get((subject_name, c26["title"], s26["title"])))
                for oi, oj, ikind in ipairs:
                    t22 = s22["items"][oi] if oi is not None else None
                    t26 = s26["items"][oj] if oj is not None else None
                    align_log[subject_name].append({"level": "item", "kind": ikind, "chapter": c26["title"], "section": s26["title"], "t22": t22, "t26": t26})
                    counters["item_" + ikind] += 1
                    if t26 is None:
                        new_nodes.append({
                            "subject": subject_name, "code": code, "chapter_id": chapter_id,
                            "parent_section_title": s22["title"], "section_id": section_id,
                            "raw_2022": t22,
                        })
                        continue
                    item_id = item_key_to_id.get((code, key(t26)))
                    if item_id is None:
                        raise RuntimeError(f"unresolved 2026 item id for {t26!r} in {subject_name}")
                    node_events[item_id] = {"kind": ikind, "raw_2022": t22, "note": None}

    # --- split / cross-section / scope-promotion annotations --------------
    for link in SPLIT_LINKS:
        code = SUBJECT_CODE[link["subject"]]
        item_id = item_key_to_id.get((code, key(link["target_2026"])))
        if item_id is None:
            raise RuntimeError("split link target not found: " + link["target_2026"])
        node_events[item_id] = {"kind": "split_from_2022", "raw_2022": link["source_2022"], "note": link["note"]}

    for link in CROSS_SECTION_LINKS:
        code = SUBJECT_CODE[link["subject"]]
        item_id = item_key_to_id.get((code, key(link["target_2026"])))
        if item_id is None:
            raise RuntimeError("cross-section link target not found: " + link["target_2026"])
        node_events[item_id] = {"kind": "cross_section_move", "raw_2022": link["source_2022"], "note": link["note"]}

    scope_promotion_notes = []
    for promo in SCOPE_PROMOTIONS:
        code = SUBJECT_CODE[promo["subject"]]
        chapter_id = next((v for (c, k), v in chapter_key_to_id.items() if c == code and k == key(promo["chapter"])), None)
        section_id = section_key_to_id.get((chapter_id, key(promo["target_section"])))
        if section_id is None:
            raise RuntimeError("scope promotion target section not found: " + promo["target_section"])
        node_events[section_id] = {"kind": "scope_promotion_from_item", "raw_2022": promo["source_2022"], "note": promo["note"]}
        scope_promotion_notes.append(promo)

    # --- subject-scope nodes: containment against 2022 full text ----------
    for pid in subject_scope_ids:
        title = baseline_by_id[pid]["title"]
        title = re.sub(r"^\[[^\]]*\]\s*", "", title)
        title = strip_number_prefix(title)
        found = key(title) in full_2022_key
        node_events[pid] = {
            "kind": "full_text_match" if found else "full_text_no_match",
            "raw_2022": title if found else None,
            "note": None if found else "2022 全文未逐字命中；不排除同义改写，未做语义合并",
        }

    # --- detail/note nodes: containment against 2022 full text ------------
    for pid in detail_note_ids:
        title = baseline_by_id[pid]["title"]
        found = key(title) in full_2022_key
        node_events[pid] = {
            "kind": "full_text_match" if found else "full_text_no_match",
            "raw_2022": title if found else None,
            "note": "无编号说明，按 2022 全文包含关系判定" if found else "无编号说明，2022 全文未命中",
        }

    # --- dedupe new_nodes against split/cross-section/promotion sources ---
    # Those 2022 raw texts are already represented as evidence on a baseline
    # (2026-sourced) node; creating a second, separate orphan node for the
    # same 2022 text would double-count the same source content.
    consumed_2022_texts = {link["source_2022"] for link in SPLIT_LINKS}
    consumed_2022_texts |= {link["source_2022"] for link in CROSS_SECTION_LINKS}
    consumed_2022_texts |= {p["source_2022"] for p in SCOPE_PROMOTIONS}
    new_nodes = [n for n in new_nodes if n["raw_2022"] not in consumed_2022_texts]

    # --- explicitly-not-merged pairs: attach a review note to both sides --
    not_merged_notes = {}
    for subject_name, t22, t26, reason in EXPLICITLY_NOT_MERGED:
        code = SUBJECT_CODE[subject_name]
        item_id = item_key_to_id.get((code, key(t26)))
        if item_id and item_id in node_events:
            node_events[item_id]["note"] = reason
        not_merged_notes[(subject_name, t22)] = reason
    for n in new_nodes:
        note_key = (n["subject"], n["raw_2022"])
        if note_key in not_merged_notes:
            n["not_merged_reason"] = not_merged_notes[note_key]

    # sanity: every baseline node must have an event
    missing = [pid for pid in baseline_by_id if pid not in node_events]
    if missing:
        raise RuntimeError(f"{len(missing)} baseline nodes got no alignment event, e.g. {missing[:5]}")

    return {
        "baseline": baseline,
        "baseline_by_id": baseline_by_id,
        "node_events": node_events,
        "new_nodes": new_nodes,
        "align_log": dict(align_log),
        "counters": dict(counters),
        "d22": d22,
        "d26": d26,
        "full_2022_key": full_2022_key,
        "scope_promotion_notes": scope_promotion_notes,
        "item_key_to_id": item_key_to_id,
        "chapter_key_to_id": chapter_key_to_id,
        "section_key_to_id": section_key_to_id,
    }


def evidence_for(scope: str, kind: str, raw_2022: str | None, title_2026: str | None) -> tuple[str, float]:
    ocr = raw_2022 is not None and is_ocr_risk(raw_2022)
    if kind in ("exact", "reorder_exact", "full_text_match"):
        tag, weight = "dual_source_exact", 1.00
    elif kind in ("manual_override", "fuzzy", "split_from_2022", "cross_section_move", "scope_promotion_from_item"):
        tag, weight = "structural_equivalent", 0.75
    elif kind == "full_text_no_match":
        tag, weight = ("structural_equivalent", 0.75) if scope == "subject" else ("single_source_unverified", 0.50)
    elif kind in ("only_26", "only_26_new_structure"):
        tag, weight = "candidate_recent_new", 0.75
    elif kind == "only_b":
        if title_2026 in RECENT_NEW_ITEM_TITLES:
            tag, weight = "candidate_recent_new", 0.75
        else:
            tag, weight = "single_source_unverified", 0.50
    else:
        raise ValueError(f"unhandled match kind {kind!r}")
    if ocr:
        tag = "text_layer_ocr_risk"
    return tag, weight


def build_c_stats():
    if not SOURCE_C_PATH.is_file():
        return {"available": False}
    raw_bytes = SOURCE_C_PATH.read_bytes()
    sha = hashlib.sha256(raw_bytes).hexdigest()
    data = json.loads(raw_bytes.decode("utf-8"))
    total_questions = 0
    knowledge_point_ids_nonnull = 0
    tag_year_counts: dict[str, Counter] = defaultdict(Counter)
    tag_total = Counter()
    for year, questions in data.items():
        for q in questions:
            qq = q.get("question", {})
            total_questions += 1
            if qq.get("knowledgePointIds") is not None:
                knowledge_point_ids_nonnull += 1
            tag = qq.get("knowledgeTagsId")
            if tag is not None:
                tag_year_counts[tag][year] += 1
                tag_total[tag] += 1
    return {
        "available": True,
        "path": str(SOURCE_C_PATH),
        "bytes": len(raw_bytes),
        "sha256": sha,
        "sha256_matches_task_brief": sha == SOURCE_C_EXPECTED_SHA and len(raw_bytes) == SOURCE_C_EXPECTED_BYTES,
        "years": sorted(data.keys()),
        "total_questions": total_questions,
        "knowledge_point_ids_field_nonnull_count": knowledge_point_ids_nonnull,
        "distinct_knowledge_tags_id": len(tag_total),
        "tag_total_counts": dict(tag_total),
        "tag_year_coverage": {tag: dict(years) for tag, years in tag_year_counts.items()},
        "mappable_to_tree_node_ids": False,
        "mapping_gap_reason": (
            "字段 knowledgePointIds 在全部 799 条题目记录中恒为 null；实际含值字段是 "
            "knowledgeTagsId（单个数字字符串，无附带名称/词典文件)。本仓库/本机范围内未发现"
            "任何将 knowledgeTagsId 数字解码为知识点名称或本树 knowledge_point_id 的映射表。"
            "因此无法把源 C 的标签统计对应到本树具体节点，只能报告标签本身的年份/次数分布。"
        ),
    }


def build_yaml(ctx, c_stats):
    baseline = ctx["baseline"]
    baseline_by_id = ctx["baseline_by_id"]
    node_events = ctx["node_events"]

    sha_a = sha256_of(SOURCE_A_PATH)
    sha_b = sha256_of(SOURCE_B_PATH)

    out_items = []
    baseline_relation_counts = Counter()
    for n in baseline:
        pid = n["knowledge_point_id"]
        ev = node_events[pid]
        scope = n.get("scope", "item")
        raw_2022 = ev.get("raw_2022")
        tag, weight = evidence_for(scope, ev["kind"], raw_2022, n["title"])
        sources = ["A"] + (["B"] if raw_2022 else [])
        aliases = []
        if raw_2022 and raw_2022 != n["title"]:
            alias_note = "text_layer_ocr_risk_raw" if is_ocr_risk(raw_2022) else "2022_wording"
            aliases.append({"text": raw_2022, "source": "B", "note": alias_note})
        node = {
            "knowledge_point_id": pid,
            "title": n["title"],
            "aliases": aliases,
            "scope": scope,
            "status": "extracted",
            "sources": sources,
            "source_count": len(sources),
            "weight": weight,
            "evidence_tag": tag,
            "baseline_relation": "kept",
            "match_kind": ev["kind"],
        }
        if ev.get("note"):
            node["review_note"] = ev["note"]
        out_items.append(node)
        baseline_relation_counts["kept"] += 1

    legacy_counter = Counter()
    for n in ctx["new_nodes"]:
        legacy_counter[n["section_id"] or n["chapter_id"]] += 1
        seq = legacy_counter[n["section_id"] or n["chapter_id"]]
        parent = n["section_id"] or n["chapter_id"]
        pid = f"{parent}.legacy-item-{seq:02d}"
        alias_note = "text_layer_ocr_risk_raw" if is_ocr_risk(n["raw_2022"]) else None
        tag, weight = "legacy_only_pending", 0.50
        node = {
            "knowledge_point_id": pid,
            "title": n["raw_2022"],
            "aliases": [],
            "scope": "item",
            "status": "extracted",
            "sources": ["B"],
            "source_count": 1,
            "weight": weight,
            "evidence_tag": tag,
            "baseline_relation": "new_vs_baseline",
            "match_kind": "only_a",
            "review_note": n.get(
                "not_merged_reason",
                f"仅 2022 显式出现；所属节『{n['parent_section_title']}』在 2026 仍存在，2026 未见对应编号条目",
            ),
        }
        if alias_note:
            node["aliases"].append({"text": n["raw_2022"], "source": "B", "note": alias_note})
        out_items.append(node)
        baseline_relation_counts["new_vs_baseline"] += 1

    doc = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator": "tools/round24_build_weighted_tree.py",
        "notice": (
            "本树为多源加权基线，非人工核准；权重反映来源支持度，不反映正确性。"
            "status 字段一律使用 extracted（不使用 approved，因其要求 actor=human，"
            "本流程无权产生该状态）。"
        ),
        "sources_registry": {
            "A": {
                "path": str(SOURCE_A_PATH.relative_to(ROOT)).replace("\\", "/"),
                "sha256": sha_a,
                "role": "2026 官方大纲 HTML（权威基线，单源树 knowledge_tree.yaml 的唯一来源）",
            },
            "B": {
                "path": str(SOURCE_B_PATH).replace("\\", "/"),
                "sha256": sha_b,
                "role": "2022 大纲 PDF（独立第二源，文本层，20 页）",
            },
            "C": {
                "path": str(SOURCE_C_PATH).replace("\\", "/"),
                "sha256": c_stats.get("sha256"),
                "role": "kaichan-kc/408-questions 题库元数据（第三方独立视角，用于印证，非考纲来源，不计入节点 sources）",
            },
        },
        "source_c_verification": c_stats,
        "baseline_relation_counts": dict(baseline_relation_counts),
        "items": out_items,
    }
    return doc


def main_build():
    ctx = main()
    c_stats = build_c_stats()
    doc = build_yaml(ctx, c_stats)
    OUT_TREE_PATH.write_text(
        yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8",
        newline="\n",
    )

    evidence = {
        "counters": ctx["counters"],
        "align_log": ctx["align_log"],
        "new_nodes": ctx["new_nodes"],
        "scope_promotion_notes": ctx["scope_promotion_notes"],
        "manual_chapter": MANUAL_CHAPTER,
        "manual_section": {" / ".join(k): v for k, v in MANUAL_SECTION.items()},
        "manual_item": {" / ".join(k): v for k, v in MANUAL_ITEM.items()},
        "split_links": SPLIT_LINKS,
        "cross_section_links": CROSS_SECTION_LINKS,
        "explicitly_not_merged": EXPLICITLY_NOT_MERGED,
        "c_stats": c_stats,
        "total_nodes": len(doc["items"]),
        "baseline_relation_counts": doc["baseline_relation_counts"],
        "evidence_tag_counts": dict(Counter(n["evidence_tag"] for n in doc["items"])),
        "weight_counts": dict(Counter(n["weight"] for n in doc["items"])),
    }
    EVIDENCE_OUT_PATH.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )
    return doc, evidence


if __name__ == "__main__":
    doc, evidence = main_build()
    print("total nodes:", len(doc["items"]))
    print("baseline_relation_counts:", doc["baseline_relation_counts"])
    print("evidence_tag_counts:", evidence["evidence_tag_counts"])
    print("weight_counts:", evidence["weight_counts"])
