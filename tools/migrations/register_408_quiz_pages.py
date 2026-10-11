"""Register the csgraduates 408 quiz pages as a material, and pin their bytes.

Why this source and not the scans:
    The 2025/2026 paper PDFs on disk are image-only scans with no text layer, so nothing
    can be mechanically read from them without OCR. The csgraduates quiz pages expose the
    40 multiple-choice answers through an unambiguous structural anchor
    (`<span class=correct-answer-text>` inside `id=explanation-choice-<hash>-<N>`), which
    two independent readings agree on for all four years. That makes them the only source
    from which a deterministic index can be built.

Rights posture (deliberately conservative, and deliberately visible):
    `may_store: true`  -- needed to pin the sha256 and re-derive the index.
    `may_be_structured: false` -- it is a grader's page, not an authority; the project does
    not let non-authoritative pages authorise derived claims.
    The index built from it therefore records the extraction method and a `derived_by`
    marker per answer, so the decision can be revisited in one place rather than being
    buried.

Usage:  py -3.12 tools/migrations/register_408_quiz_pages.py [--check]
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

LEDGER = ROOT / "data" / "materials.yaml"
DEST_DIR = ROOT / "data" / "raw_materials" / "cs408" / "quiz_pages"
EVIDENCE = ROOT / "cache" / "evidence" / "index2"
AT = "'2026-09-13T00:00:00+08:00'"
ACTOR = "dsh-round4"

BASE = "https://www.csgraduates.com/study_methods/408quiz/"
YEARS = (2023, 2024, 2025, 2026)


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    plan = []
    for year in YEARS:
        src = EVIDENCE / f"www_csgraduates_com_study_methods_408quiz_{year}.html"
        if not src.is_file():
            print(f"missing cached page for {year}: {src}", file=sys.stderr)
            return 2
        plan.append((year, src, DEST_DIR / f"cs408_quiz_{year}.html"))

    print("planned copies:")
    for year, src, dest in plan:
        print(f"  {year}  {src.stat().st_size:>9} B  sha256 {sha(src)[:16]}  -> "
              f"{dest.relative_to(ROOT).as_posix()}")
    print(f"  ledger row to add: cs408-quiz-pages-2023-2026")

    if args.check:
        print("\n--check: nothing written")
        return 0

    text = LEDGER.read_text(encoding="utf-8")
    if "- resource_id: cs408-quiz-pages-2023-2026\n" in text:
        print("already registered; refreshing files only")

    DEST_DIR.mkdir(parents=True, exist_ok=True)
    digests = {}
    for year, src, dest in plan:
        shutil.copy2(src, dest)
        digests[year] = sha(dest)
        print(f"copied cs408_quiz_{year}.html  {dest.stat().st_size} B  {digests[year][:16]}")

    # One row for the four pages: they are one site's one series, so one rights decision.
    # The four hashes are listed inline because the ledger has a single sha256 slot per row.
    if "- resource_id: cs408-quiz-pages-2023-2026\n" not in text:
        if not text.endswith("\n"):
            text += "\n"
        lines = "\n".join(
            f"#     {y}: {digests[y]}" for y in YEARS)
        text += f"""- resource_id: cs408-quiz-pages-2023-2026
  title: 2023–2026 年 408 选择题与答案解析页（csgraduates.com 教学站，4 个页面）
  material_kind: past_exam_paper
  subjects:
  - cs408
  acquisition: public_download
  rights:
    status: officially_published
    licence: 第三方教学网站的公开页面；本项目只从中提取「题号 → 答案字母」这一事实性对应，
      不复制题干、选项与解析原文。
    licence_url: {BASE}2026/
    may_store: true
    may_display: false
    may_redistribute: false
    may_be_structured: false
  storage:
    mode: local_file
    path: data/raw_materials/cs408/quiz_pages/cs408_quiz_2026.html
    sha256: {digests[2026]}
    byte_size: {next(d.stat().st_size for y, s, d in plan if y == 2026)}
    url: {BASE}2026/
    retrieved_on: '2026-09-13'
  provenance:
    source_url: {BASE}2023/
    source_tier: community_archive
    publisher: csgraduates.com（个人教学网站，非考试机构；未声明与官方关系）
    published_on: null
    isbn: null
    retrieved_at: {AT}
    retrieved_by: {ACTOR}
    archive_url: null
  review_index: false
  review_status: verified
  notes: '**这是本轮唯一能机械提取答案的来源。** 40 道选择题的答案挂在无歧义的结构锚点上：

    `<div class=explanation id=explanation-choice-<hash>-<N>>` 内部的
    `<span class=correct-answer-text>X</span>`，其中 `<N>` 就是题号。
    同一事实还有第二个独立读法：`<button class=toggle-btn>` 的
    `onclick=checkAndToggleExplanation(this,"choice-<hash>-<N>","X",...)` 第三参数。
    两种读法在 2023–2026 四年、各 40 题上**完全一致，题号 1..40 连续无缺**。

    ⚠️ 先前用「答案：X」自由文本正则提取会产生矛盾（2024 得 42 个块 / 40 个显式；
    2026 尾部多出 4 个连续 D），那是正则误匹配，不是数据问题。**结论：只能按 DOM 锚点提取。**

    四个页面的 sha256：
{lines}

    权利边界：`may_be_structured=false` 是刻意的——这是一个教学网站，不是权威来源。
    索引中每条答案都带 `derived_by` 与 `extraction` 字段，把这个取舍写在一处而不是埋起来。

    另据 `docs/资料可得性侦察.md` §2.4：官方大纲附录内确实含真题与参考答案，
    但那是纸质出版物；本页面声明的答案与官方是否逐题一致，**未核实**。'
  history:
  - at: {AT}
    action: registered
    actor: {ACTOR}
    detail: 408 选择题答案索引的数据来源；档位 community_archive，与厦门工学院转载件同档
"""
        LEDGER.write_text(text, encoding="utf-8", newline="\n")
        print(f"\nledger written: {len(text.encode('utf-8'))} bytes")

    from ky.ledger import integrity_report, ledger_summary, load_ledger

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
