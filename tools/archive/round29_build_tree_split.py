"""Build the CS408 multi-source tree as two artifacts instead of one.

Round 24 produced a single ``knowledge_tree_weighted.yaml`` that failed
``tools/verify_tree.py`` at the document level: it carries six node-level
fields (`aliases`, `source_count`, `weight`, `evidence_tag`,
`baseline_relation`, `match_kind`) outside `ky.knowledge.knowledge_point`'s
whitelist, is missing the contract-required `source_kind`, and stores
`sources` as bare tag labels (`["A", "B"]`) instead of real
`{path, sha256, locator}` records.

This script keeps round24_build_weighted_tree.py's alignment engine and
evidence-tag classification (`main()`, `evidence_for()`) completely unchanged
and reused via import -- that logic decides *whether* a node matches across
the two syllabus sources and is out of scope for this round. What this
script adds:

  1. Real per-node `sources` records for the B side, with a `locator` whose
     `quote_ref` is guaranteed to be verbatim-locatable in a real file (see
     round29_quote_locate.py) -- not just fuzzy-matched.
  2. A source_support value (tools/tree_source_support.py) computed
     independently of the historical `weight`, then asserted equal to it for
     every single node (the round-29 task's hard gate).
  3. Two output files instead of one:
       - knowledge_tree_multisource.yaml: contract-verifiable main tree,
         structurally identical to knowledge_tree.yaml (plain list of
         knowledge points), a superset of it (403 kept + 7 new).
       - knowledge_tree_agreement.yaml: the non-contract annotation layer
         (source_support/source_count/evidence_tag/match_kind/
         baseline_relation/aliases), keyed by knowledge_point_id.

Usage:
    py -3.12 tools/round29_build_tree_split.py
"""
from __future__ import annotations

import copy
import hashlib
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from archive import round24_build_weighted_tree as rb  # noqa: E402
from cs408_quote_locate import build_keymap, locate_quote  # noqa: E402
from tree_source_support import derive_source_support  # noqa: E402

MAIN_TREE_PATH = ROOT / "data/structured_materials/cs408/knowledge_tree_multisource.yaml"
AGREEMENT_PATH = ROOT / "data/structured_materials/cs408/knowledge_tree_agreement.yaml"

SOURCE_A_PATH = rb.SOURCE_A_PATH
SOURCE_B_RAW_PATH = rb.SOURCE_B_PATH
SOURCE_B_TEXT_PATH = ROOT / "data/raw_materials/cs408/syllabus/408_syllabus_2022.extracted.txt"
SOURCE_C_PATH = ROOT / "data/raw_materials/cs408/exam_banks/408q_full.json"

# Fixed (not datetime.now()) so the main tree's transition_history for the 7
# legacy-only nodes is byte-reproducible across runs, matching the style of
# the existing hand-authored timestamps in knowledge_tree.yaml.
LEGACY_NODE_TIMESTAMP = "2026-09-15T00:00:00+08:00"


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def build():
    ctx = rb.main()
    baseline = ctx["baseline"]
    node_events = ctx["node_events"]

    source_b_text = SOURCE_B_TEXT_PATH.read_text(encoding="utf-8")
    keymap = build_keymap(source_b_text)
    sha_b_text = sha256_of(SOURCE_B_TEXT_PATH)
    b_path_rel = rel(SOURCE_B_TEXT_PATH)

    main_items: list[dict] = []
    agreement_items: list[dict] = []
    unresolved: list[str] = []
    mismatches: list[tuple[str, float, float]] = []

    def b_source_record(quote: str) -> dict:
        return {"path": b_path_rel, "sha256": sha_b_text, "locator": {"quote_ref": quote}}

    for n in baseline:
        pid = n["knowledge_point_id"]
        ev = node_events[pid]
        scope = n.get("scope", "item")
        raw_2022 = ev.get("raw_2022")
        kind = ev["kind"]
        tag, old_support = rb.evidence_for(scope, kind, raw_2022, n["title"])

        main_node = copy.deepcopy(n)
        if raw_2022:
            quote = locate_quote(raw_2022, source_b_text, keymap)
            if quote is None:
                unresolved.append(pid)
                continue
            main_node["sources"].append(b_source_record(quote))
        main_items.append(main_node)

        source_count = len(main_node["sources"])
        new_support = derive_source_support(tag, source_count, kind)
        if new_support != old_support:
            mismatches.append((pid, old_support, new_support))

        aliases = []
        if raw_2022 and raw_2022 != n["title"]:
            alias_note = "text_layer_ocr_risk_raw" if rb.is_ocr_risk(raw_2022) else "2022_wording"
            aliases.append({"text": raw_2022, "source": "B", "note": alias_note})

        agreement_items.append({
            "knowledge_point_id": pid,
            "source_support": new_support,
            "source_count": source_count,
            "evidence_tag": tag,
            "match_kind": kind,
            "baseline_relation": "kept",
            "aliases": aliases,
        })

    legacy_counter: Counter = Counter()
    for n in ctx["new_nodes"]:
        parent = n["section_id"] or n["chapter_id"]
        legacy_counter[parent] += 1
        pid = f"{parent}.legacy-item-{legacy_counter[parent]:02d}"
        raw_2022 = n["raw_2022"]
        quote = locate_quote(raw_2022, source_b_text, keymap)
        if quote is None:
            unresolved.append(pid)
            continue
        b_source = b_source_record(quote)

        main_items.append({
            "schema_version": 1,
            "knowledge_point_id": pid,
            "title": raw_2022,
            "scope": "item",
            "status": "extracted",
            "source_kind": "official_outline",
            "sources": [b_source],
            "frequency": None,
            "evidence": [],
            "transition_history": [{
                "from": "raw", "to": "extracted", "actor": "ai",
                "source": b_source, "at": LEGACY_NODE_TIMESTAMP,
            }],
            "supersedes": None,
            "revision": 1,
        })

        tag, old_support = "legacy_only_pending", 0.5
        new_support = derive_source_support(tag, 1, "only_a")
        if new_support != old_support:
            mismatches.append((pid, old_support, new_support))

        aliases = []
        if rb.is_ocr_risk(raw_2022):
            aliases.append({"text": raw_2022, "source": "B", "note": "text_layer_ocr_risk_raw"})

        agreement_items.append({
            "knowledge_point_id": pid,
            "source_support": new_support,
            "source_count": 1,
            "evidence_tag": tag,
            "match_kind": "only_a",
            "baseline_relation": "new_vs_baseline",
            "aliases": aliases,
            "review_note": n.get(
                "not_merged_reason",
                f"仅 2022 显式出现；所属节『{n['parent_section_title']}』在 2026 仍存在，2026 未见对应编号条目",
            ),
        })

    if unresolved:
        raise RuntimeError(f"{len(unresolved)} node(s) got no locatable B quote_ref: {unresolved}")
    if mismatches:
        raise AssertionError(
            f"{len(mismatches)} node(s): derived source_support != historical weight: {mismatches[:10]}"
        )

    return main_items, agreement_items


def build_c_registry_entry() -> dict:
    return {
        "path": rel(SOURCE_C_PATH),
        "sha256": sha256_of(SOURCE_C_PATH),
        "role": "kaichan-kc/408-questions 题库元数据（第三方独立视角，用于印证，非考纲来源，不计入节点 sources）",
    }


def main() -> None:
    main_items, agreement_items = build()

    MAIN_TREE_PATH.write_text(
        yaml.safe_dump(main_items, allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8",
        newline="\n",
    )

    agreement_doc = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator": "tools/round29_build_tree_split.py",
        "concept_name": "source_support",
        "concept_note": (
            "重命名自 round-24 的 weight 字段，避免与 ky/schedule/review_clip.py 的学科级时间预算权重、"
            "tools/apply_knowledge_weights.py 的题目->知识点分布置信度混淆；数值与含义均未改变，"
            "仅为“来源支持度”起一个不冲突的名字。"
        ),
        "source_registry": {
            "A": {
                "path": rel(SOURCE_A_PATH),
                "sha256": sha256_of(SOURCE_A_PATH),
                "role": "2026 官方大纲 HTML（权威基线，knowledge_tree.yaml 与本树主表的唯一 A 来源）",
            },
            "B_raw": {
                "path": rel(SOURCE_B_RAW_PATH),
                "sha256": sha256_of(SOURCE_B_RAW_PATH),
                "role": "2022 大纲 PDF 原件（独立第二源，20 页；归档用，不直接作为节点 sources 引用）",
            },
            "B_text": {
                "path": rel(SOURCE_B_TEXT_PATH),
                "sha256": sha256_of(SOURCE_B_TEXT_PATH),
                "role": (
                    "对 B_raw 用 round22_extract.extract_2022() 确定性抽取的纯文本副本；"
                    "主表节点的 B 源 sources[].path 均指向此文件，因为 verify_tree.py 按 UTF-8 文本"
                    "读取并做 quote_ref 定位，无法直接处理 PDF 二进制内容"
                ),
            },
            "C": build_c_registry_entry(),
        },
        "baseline_relation_counts": dict(Counter(a["baseline_relation"] for a in agreement_items)),
        "items": agreement_items,
    }
    AGREEMENT_PATH.write_text(
        yaml.safe_dump(agreement_doc, allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8",
        newline="\n",
    )
    print(f"main table  : {len(main_items)} nodes -> {MAIN_TREE_PATH.relative_to(ROOT)}")
    print(f"agreement   : {len(agreement_items)} nodes -> {AGREEMENT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
