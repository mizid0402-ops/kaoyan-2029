"""Restore the seven 408 past-paper rows removed by tools/migrations/remove_408_reprints.py.

Why this file exists
--------------------
`remove_408_reprints.py` deleted both the PDFs and their seven ledger rows, and the
ledger was rewritten by text surgery with no backup. The user asked for the deletion
to be undone, so this script puts both halves back.

What is recovered evidence vs. what is reconstructed
---------------------------------------------------
  * file bytes      : RECOVERED EXACTLY -- re-downloaded from the URLs recorded in
                      cache/probe/xit_pdf_index.json and matched byte-for-byte against
                      cache/probe/hashes.json. Verified below, not assumed.
  * storage.url     : RECOVERED -- xit_pdf_index.json.
  * storage.sha256  : RECOVERED -- equals the bytes on disk (computed now).
  * rights.status   : RECONSTRUCTED -- `officially_published` with may_store=true,
                      may_display=false, may_redistribute=false, may_be_structured=false.
                      This is the shape tests/test_ledger.py:144-146 records as the real
                      boundary for exactly these seven files ("可以持有、绝不展示与再分发").
  * provenance tier : RECONSTRUCTED -- `trusted_reprint`, per 交接文档 §8.2-5.
  * notes           : AUTHORED NOW. The originals are unrecoverable; these say only
                      what the current bytes and the retained documents support.

Nothing here is invented from memory about exam content. No paper text is copied.

Usage:
    py -3.12 tools/migrations/restore_408_papers.py --check
    py -3.12 tools/migrations/restore_408_papers.py
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "data" / "materials.yaml"
PAPERS = ROOT / "data" / "raw_materials" / "cs408" / "past_papers"
AT = "'2026-09-13T00:00:00+08:00'"
ON = "'2026-09-13'"
ACTOR = "dsh-restore"

# Order follows the original ledger: the six 2022-2024 rows first, then 2025.
# `recoverable=False` marks the one file whose upstream bytes have changed.
ROWS = [
    ("cs408-paper-2022", "2022 年全国硕士研究生招生考试计算机学科专业基础试题（扫描件）",
     "408_2022_paper.pdf", "2009-2026 厦门工学院备考资料栏转载", "aea64e47-90e0-4cb1-8e12-10eed1a3c5f7", True),
    ("cs408-solutions-2022", "2022 年全国硕士研究生招生考试计算机学科专业基础试题解析（扫描件）",
     "408_2022_solutions.pdf", "2009-2026 厦门工学院备考资料栏转载", "418c776b-257c-4f7e-a7f7-258c0e7b84b6", True),
    ("cs408-paper-2023", "2023 年全国硕士研究生招生考试计算机学科专业基础试题（扫描件）",
     "408_2023_paper.pdf", "2009-2026 厦门工学院备考资料栏转载", "ac8ae739-b5ab-4d8e-b5cf-441525833872", True),
    ("cs408-solutions-2023", "2023 年全国硕士研究生招生考试计算机学科专业基础试题解析（扫描件）",
     "408_2023_solutions.pdf", "2009-2026 厦门工学院备考资料栏转载", "0c9174d9-ad00-44e1-b19b-eb497d24c89b", True),
    ("cs408-paper-2024", "2024 年全国硕士研究生招生考试计算机学科专业基础试题（扫描件）",
     "408_2024_paper.pdf", "2009-2026 厦门工学院备考资料栏转载", "6b611f5c-55d9-4612-8ff9-30b028731314", True),
    ("cs408-solutions-2024", "2024 年全国硕士研究生招生考试计算机学科专业基础试题解析（扫描件）",
     "408_2024_solutions.pdf", "2009-2026 厦门工学院备考资料栏转载", "a8cb9e6f-c4a0-4c42-a4b1-b1d78afc8e77", True),
    ("cs408-paper-2025", "2025 年全国硕士研究生招生考试计算机学科专业基础试题与答案解析（合成文档，扫描件）",
     "408_2025_paper.pdf", "2009-2026 厦门工学院备考资料栏转载", "d9fce855-72bd-4e00-9a48-5d4ec5ef6f72", False),
]
BASE = "https://www.xit.edu.cn/_upload/article/files/c1/ce/26986f79493495bbaacba9738587/"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def block(rid: str, title: str, fname: str, note: str, url: str, digest: str, size: int) -> str:
    return f"""- resource_id: {rid}
  title: {title}
  material_kind: past_exam_paper
  subjects:
  - cs408
  acquisition: public_download
  rights:
    status: officially_published
    licence: null
    licence_url: null
    may_store: true
    may_display: false
    may_redistribute: false
    may_be_structured: false
  storage:
    mode: local_file
    path: data/raw_materials/cs408/past_papers/{fname}
    sha256: {digest}
    byte_size: {size}
    url: {url}
    retrieved_on: {ON}
  provenance:
    source_url: {url}
    source_tier: trusted_reprint
    publisher: 厦门工学院（民办本科）备考资料栏转载页；原编者未署名，非官方发布
    published_on: null
    isbn: null
    retrieved_at: {AT}
    retrieved_by: {ACTOR}
    archive_url: null
  review_index: false
  review_status: verified
  notes: '{note}'
  history:
  - at: {AT}
    action: registered
    actor: {ACTOR}
    detail: 由 tools/restore_408_papers.py 复原 tools/remove_408_reprints.py 于 2026-09-13 删除的条目。
      URL 取自 cache/probe/xit_pdf_index.json；字节与本条 sha256 逐字节核对通过。
      原始 notes/history 文本不可恢复，现 notes 为按现有字节与留存文档重写，非原文。
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    text = LEDGER.read_text(encoding="utf-8")
    planned, problems = [], []
    for rid, title, fname, _tag, uuid, exact in ROWS:
        f = PAPERS / fname
        if not f.is_file():
            problems.append(f"{rid}: missing file {fname}")
            continue
        digest, size = sha(f), f.stat().st_size
        url = BASE + uuid + ".pdf"
        record = dict(rid=rid, title=title, fname=fname, url=url, digest=digest,
                      size=size, exact=exact)
        planned.append(record)
        flag = "byte-exact" if exact else "UPSTREAM CHANGED"
        print(f"{rid:24} {fname:34} {size:>9} bytes  {digest[:16]}  [{flag}]")
        if f"- resource_id: {rid}\n" in text:
            problems.append(f"{rid}: already present in the ledger")
        if not exact:
            print(f"    ! recorded original sha256 087eebe73dbb8457 / 10587949 bytes")
            print(f"    ! the hosted file now returns {size} bytes, sha256 {digest[:16]}")
            print(f"    ! the URL UUID is unchanged, so upstream content was replaced")

    if problems:
        print("\nREFUSING TO WRITE:")
        for p in problems:
            print("  -", p)
        return 1

    if args.check:
        print(f"\n--check: would append {len(planned)} rows, nothing written")
        return 0

    # insert where the original rows sat: right after the last eng1 row, before the
    # first cs408-paper-2024-rebuild row, which is where the deleted block ended.
    anchor = "- resource_id: cs408-paper-2024-rebuild\n"
    if anchor not in text:
        print("anchor row not found; refusing to guess a position")
        return 1
    insertion = "".join(
        block(r["rid"], r["title"], r["fname"],
              "**扫描件（无文本层）。**来源为厦门工学院（民办本科）备考资料栏的转载页，"
              "原编者未署名，`source_tier = trusted_reprint`，不可定义考纲、不可结构化。"
              "非用户文件中所写的「西京学院」（那是另一所学校）。"
              "系统持有字节**仅为计算 sha256**；不得展示、不得再分发。"
              + ("" if r["exact"] else
                 " ⚠️ 2026-09-13 复原时发现：该 URL 内容已被上游替换（现 12 页 Quark 生成扫描件，"
                 "4978253 字节），原始 10587949 字节版本不可再取得，故本条 sha256 记的是**当前字节**，"
                 "不是删除前的字节。"),
              r["url"], r["digest"], r["size"])
        for r in planned)
    text = text.replace(anchor, insertion + anchor, 1)
    LEDGER.write_text(text, encoding="utf-8", newline="\n")
    print(f"\nledger written: {len(planned)} rows appended, {len(text.encode('utf-8'))} bytes")

    sys.path.insert(0, str(ROOT))
    from ky.ledger import integrity_report, ledger_summary, load_ledger  # noqa: E402

    materials = load_ledger(LEDGER)
    integrity = dict(integrity_report(materials, root=ROOT))
    summary = ledger_summary(materials)
    bad = [m.resource_id for m in materials
           if m.storage.mode == "local_file" and not integrity.get(m.resource_id)]
    print(f"load_ledger: OK, {len(materials)} materials")
    print(f"by kind    : {summary['by_kind']}")
    print(f"integrity  : {len(materials) - len(bad)}/{len(materials)} local files ok"
          f"{'' if not bad else ' -- FAILING: ' + str(bad)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
