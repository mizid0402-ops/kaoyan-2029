"""Register the 408 exam-paper source and pin its bytes, with hashes re-verified.

Scope discipline (why this is safe to do while the *mapping* method is undecided):

  * It records **where the paper came from** and pins the exact bytes. That is needed
    by every mapping method, so it is not wasted whichever method is chosen.
  * Tier is `community_archive`, NOT `trusted_reprint`: the file is a community
    *rebuild* by an individual (its own README says the author holds no copyright and
    the text was regenerated from images). The tier enum's definition of
    `community_archive` is 个人整理, which is exactly what this is.
  * `may_be_structured: false` — a re-typed paper may not authorise derived claims.
    But `may_store: true`: the project needs the bytes to verify hashes and to let the
    题号 be located, and the content is already public.

The answer scan is registered as `unknown` rights with `may_store: true`: it was
fetched from a public repo, but its own provenance chains back to an anonymous WeChat
account watermark, so its licence cannot be established. Unknown is not permission —
hence nothing may be structured from it.

Usage:  py -3.12 tools/migrations/register_408_source.py [--check]
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

LEDGER = ROOT / "data" / "materials.yaml"
DEST_DIR = ROOT / "data" / "raw_materials" / "cs408" / "past_papers_thirdparty"
AT = "'2026-09-13T00:00:00+08:00'"
ACTOR = "dsh-round3"

# expected sha256 recorded from the probe run — re-verified after download
SOURCES = [
    {
        "resource_id": "cs408-paper-2024-rebuild",
        "url": "https://raw.githubusercontent.com/neville-studio/408-exam-paper/main/papers-rebuild/2024.pdf",
        "filename": "408_2024_paper_rebuild.pdf",
        "expected_sha": "baae7ba96588d55117a31c297304927d3791d0f3576bf0c70f32fd8a9fe1766c",
        "title": "2024 年全国硕士研究生招生考试计算机学科专业基础试题（社区重排版，文字版）",
        "kind": "past_exam_paper",
        "rights_status": "officially_published",
        "may_be_structured": False,
        "publisher": "GitHub 社区仓库 neville-studio/408-exam-paper（个人重排版，MIT 协议声明；作者自述不持有试卷内容版权）",
        "notes": (
            "**社区重排版**，非官方原卷、非扫描件。仓库 README 自述：基于图片重新生成文字版，"
            "错误率约 1 处/100KB，并明确可信度排序为「大纲内真题 > 第三方原题 > 第三方回忆版」，"
            "同时要求贡献者不要提供回忆版。\n\n"
            "**source_tier 定级理由（刻意不用 trusted_reprint）**：这是个人整理件，"
            "符合 community_archive 释义（「个人整理：只能用于查漏与线索」）；"
            "且 may_be_structured=false —— 重排版可能含转写错误，不得据其定义任何内容。\n\n"
            "本文件仅用于：①定位题号边界；②在官方 2026 版大纲到货后做逐题比对、量化重排错误率。"
        ),
        "may_store": True,
        "may_display": False,
        "may_redistribute": False,
    },
    {
        "resource_id": "cs408-answer-2024-scan",
        "url": "https://raw.githubusercontent.com/neville-studio/408-exam-paper/main/answers/2024-answer.pdf",
        "filename": "408_2024_answer_scan.pdf",
        "expected_sha": "83146d04e95bdf2e7a58b6157a2ba00029c7b4268f1937bedd740ae7f1868523",
        "title": "2024 年计算机学科专业基础试题参考答案（扫描件，来源不明）",
        "kind": "past_exam_paper",
        "rights_status": "unknown",
        "may_be_structured": False,
        "publisher": None,
        "notes": (
            "扫描件（无文本层，6 页）。页面带微信公众号水印（`xlxj985211`），"
            "**原始发布者与授权状态无法确认**，故 rights.status=unknown。\n\n"
            "未知不等于可用：不得据此定义任何内容，不得展示、不得再分发。"
            "本轮仅用其首页的答案速查表（01–40 题号与字母），且已与另一个已删除的独立来源交叉验证。"
        ),
        "may_store": True,
        "may_display": False,
        "may_redistribute": False,
    },
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    import requests

    DEST_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    for spec in SOURCES:
        if f"- resource_id: {spec['resource_id']}\n" in LEDGER.read_text(encoding="utf-8"):
            print(f"{spec['resource_id']}: already registered (no-op)")
            continue
        dest = DEST_DIR / spec["filename"]
        if dest.is_file():
            got = sha(dest)
            print(f"{spec['filename']}: already present on disk, sha256 {got[:16]}")
        else:
            print(f"fetching {spec['url']}")
            response = requests.get(
                spec["url"], timeout=120,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            )
            response.raise_for_status()
            dest.write_bytes(response.content)
            got = sha(dest)
            print(f"  {len(response.content)} bytes -> {dest.name}, sha256 {got[:16]}")
        if got != spec["expected_sha"]:
            print(f"  *** SHA MISMATCH: expected {spec['expected_sha'][:16]}, got {got[:16]}")
            print("  *** the upstream file changed; refusing to register with a stale hash")
            return 1
        results.append((spec, dest, got))

    if not results:
        print("nothing to register")
        return 0

    if args.check:
        print("\n--check: nothing written to the ledger")
        return 0

    text = LEDGER.read_text(encoding="utf-8")
    if not text.endswith("\n"):
        text += "\n"
    for spec, dest, got in results:
        url = spec["url"]
        if spec["publisher"]:
            provenance_publisher = spec["publisher"]
            source_url = url
        else:
            # provenance must carry at least one of source_url/publisher/isbn
            provenance_publisher = "（未署名；原始发布者无法确认）"
            source_url = url
        rights_url = None if spec["rights_status"] == "unknown" else url
        text += f"""- resource_id: {spec['resource_id']}
  title: {spec['title']}
  material_kind: {spec['kind']}
  subjects:
  - cs408
  acquisition: public_download
  rights:
    status: {spec['rights_status']}
    licence: null
    licence_url: {rights_url if rights_url else 'null'}
    may_store: {'true' if spec['may_store'] else 'false'}
    may_display: {'true' if spec['may_display'] else 'false'}
    may_redistribute: {'true' if spec['may_redistribute'] else 'false'}
    may_be_structured: {'true' if spec['may_be_structured'] else 'false'}
  storage:
    mode: local_file
    path: {dest.relative_to(ROOT).as_posix()}
    sha256: {got}
    byte_size: {dest.stat().st_size}
    url: {url}
    retrieved_on: '2026-09-13'
  provenance:
    source_url: {source_url}
    source_tier: community_archive
    publisher: {provenance_publisher}
    published_on: null
    isbn: null
    retrieved_at: {AT}
    retrieved_by: {ACTOR}
    archive_url: null
  review_index: false
  review_status: verified
  notes: '{spec['notes']}'
  history:
  - at: {AT}
    action: registered
    actor: {ACTOR}
    detail: 408 题号索引的数据来源；档位 community_archive，不可定义考纲、不可结构化
"""
    LEDGER.write_text(text, encoding="utf-8", newline="\n")
    print(f"\nledger written: {len(text.encode('utf-8'))} bytes")

    from ky.ledger import integrity_report, load_ledger, ledger_summary

    materials = load_ledger(LEDGER)
    integrity = dict(integrity_report(materials, root=ROOT))
    summary = ledger_summary(materials)
    bad = [m.resource_id for m in materials
           if m.storage.mode == "local_file" and not integrity.get(m.resource_id)]
    print(f"load_ledger: OK, {len(materials)} materials | by kind {summary['by_kind']}")
    print(f"local files failing integrity: {bad if bad else 'none'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
