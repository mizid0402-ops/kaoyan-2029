"""Fix the eng1 provenance rows and register the page that actually carries the 2026 TOC.

Why this is a separate, small, auditable step:

  * `eng1-outline-pubinfo-2026` declared `sha256 140f5346… / byte_size 8057`, but the file
    on disk is `0e833aac… / 8131`. The recorded hash never matched the bytes. The ledger's
    own integrity report would have flagged this as MISMATCH — it only looked "verified"
    because the previous phase never re-ran it after the file was replaced.
  * The official 2026 English TOC that the tree needs lives on the 人教社体系
    `aus.zxhsd.com` page (already fetched and hash-pinned), not on the megbook page.
    So it gets registered as its own material instead of being attributed to the wrong URL.

Nothing here changes any tier or permission: both rows stay `trusted_reprint` and
`may_be_structured: false`, because both are bookseller pages.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

LEDGER = ROOT / "data" / "materials.yaml"
AT = "'2026-09-13T00:00:00+08:00'"
ACTOR = "dsh-round2"

AUS_SRC = ROOT / "cache" / "evidence" / "attach" / "aus_zxhsd_com_kgsm_ts_2025_10_17_6694606_shtml.html"
AUS_DST = ROOT / "data" / "raw_materials" / "eng1" / "syllabus" / "aus_zxhsd_eng1_outline_toc_2026.html"
MEGBOOK = ROOT / "data" / "raw_materials" / "eng1" / "syllabus" / "megbook_eng1_outline_pubinfo_2026.html"

NEW_RESOURCE_ID = "eng1-outline-toc-aus-zxhsd-2026"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def bounds(text: str, rid: str) -> tuple[int, int]:
    start = text.index(f"- resource_id: {rid}\n")
    nxt = text.find("\n- resource_id: ", start + 1)
    return start, (nxt + 1 if nxt != -1 else len(text))


def main() -> int:
    text = LEDGER.read_text(encoding="utf-8")
    changed: list[str] = []

    # ---- 1. correct the megbook row so its hash matches its bytes ------------
    start, end = bounds(text, "eng1-outline-pubinfo-2026")
    block = text[start:end]
    real_sha = sha(MEGBOOK)
    real_size = MEGBOOK.stat().st_size
    old_sha_line = [ln for ln in block.splitlines() if ln.strip().startswith("sha256:")][0].strip()
    if real_sha not in block:
        block = block.replace(old_sha_line, f"sha256: {real_sha}", 1)
        block = block.replace(
            [ln for ln in block.splitlines() if ln.strip().startswith("byte_size:")][0].strip(),
            f"byte_size: {real_size}",
            1,
        )
        marker = "  history:\n"
        idx = block.index(marker) + len(marker)
        block = block[:idx] + (
            f"  - at: {AT}\n"
            "    action: verified\n"
            f"    actor: {ACTOR}\n"
            "    detail: 修正 storage 哈希：原记录的 sha256/byte_size 与磁盘字节不符"
            f"（这是台账完整性问题，不是抓取问题）。现按磁盘现算：{real_sha[:16]} / {real_size} 字节。\n"
        ) + block[idx:]
        changed.append(f"eng1-outline-pubinfo-2026: storage hash corrected -> {real_sha[:16]}")
        text = text[:start] + block + text[end:]
    else:
        print("megbook row already matches its bytes (no-op)")

    # ---- 2. register the page that really carries the 2026 TOC ---------------
    if f"- resource_id: {NEW_RESOURCE_ID}\n" in text:
        print("aus.zxhsd TOC row already registered (no-op)")
    else:
        if not AUS_SRC.is_file():
            raise SystemExit(f"missing fetched page: {AUS_SRC}")
        AUS_DST.parent.mkdir(parents=True, exist_ok=True)
        AUS_DST.write_bytes(AUS_SRC.read_bytes())
        aus_sha = sha(AUS_DST)
        aus_size = AUS_DST.stat().st_size
        entry = f"""- resource_id: {NEW_RESOURCE_ID}
  title: 2026 年全国硕士研究生招生考试英语（一）考试大纲（人教社体系书目页，载有完整官方目录）
  material_kind: official_syllabus
  subjects:
  - eng1
  acquisition: public_download
  rights:
    status: official_public
    licence: 澳大利亚新华书店（人教社体系发行渠道）商品页；页面公布的是官方目录层级，属事实性公开信息。
      系统只保存该公开页面，不持有书籍正文。
    licence_url: https://aus.zxhsd.com/kgsm/ts/2025/10/17/6694606.shtml
    may_store: true
    may_display: true
    may_redistribute: false
    may_be_structured: false
  storage:
    mode: local_file
    path: data/raw_materials/eng1/syllabus/aus_zxhsd_eng1_outline_toc_2026.html
    sha256: {aus_sha}
    byte_size: {aus_size}
    url: https://aus.zxhsd.com/kgsm/ts/2025/10/17/6694606.shtml
    retrieved_on: '2026-09-13'
  provenance:
    source_url: https://aus.zxhsd.com/kgsm/ts/2025/10/17/6694606.shtml
    source_tier: trusted_reprint
    publisher: 人民教育出版社（教育部教育考试院 编）；本条字节取自澳大利亚新华书店书目页
    published_on: '2025-09-01'
    isbn: 978-7-107-40460-3
    retrieved_at: {AT}
    retrieved_by: {ACTOR}
    archive_url: null
  review_index: false
  review_status: verified
  notes: '**这是本轮唯一逐字载有官方目录的英语（一）大纲页面。** 页面给出：
    ISBN 9787107404603、236 页、出版 2025/09/01、出版社人民教育；目录为
    「Ⅰ 考试性质 / Ⅱ 考查目标 / Ⅲ 考试形式、考试内容与试卷结构 / Ⅳ 题型示例及参考答案 /
    附录一 词汇表（含部分国家地区名称、大洲名大洋名）/ 附录二 常用前缀和后缀、常见缩写词 /
    附录三 2024 与 2025 英语（一）试题及试题参考答案」。

    ⚠️ source_tier=trusted_reprint（**书店书目页，不是官方出版社产品页**），
    因此 may_define_syllabus 为 false：它可作结构锚点，不能作为“考纲是否包含某内容”的判据。
    定价仍未核实（该页 price 字段为空）。

    对照：另一条 `eng1-outline-pubinfo-2026`（megbook 台湾页）**不含目录**，
    本轮据此拆分为两条，避免把「目录」这一事实挂到没有该内容的 URL 上。'
  history:
  - at: {AT}
    action: registered
    actor: {ACTOR}
    detail: 英语一结构树的目录锚点来源；与 megbook 页拆分登记，因后者不含目录
"""
        if not text.endswith("\n"):
            text += "\n"
        text += entry
        changed.append(f"registered {NEW_RESOURCE_ID} ({aus_sha[:16]} / {aus_size} bytes)")

    LEDGER.write_text(text, encoding="utf-8", newline="\n")
    for c in changed:
        print("  -", c)

    from ky.ledger import load_ledger, integrity_report

    materials = load_ledger(LEDGER)
    integrity = dict(integrity_report(materials, root=ROOT))
    bad = [m.resource_id for m in materials if m.storage.mode == "local_file" and not integrity.get(m.resource_id)]
    print(f"\nload_ledger: OK, {len(materials)} materials")
    print(f"local files failing integrity: {bad if bad else 'none'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
