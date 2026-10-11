"""Apply the round-2 review's findings to the ledger. Idempotent and hash-guarded.

Findings applied (from review/rounds/attach-audit-opus.md):

  F1  `user-index-math1-eng1-2026` must NOT be in the ledger. It is an unattributed
      third-party index: it has no source_url/publisher/isbn, so the ledger's own rule
      (`provenance must record at least one of source_url / publisher / isbn`) rejects it
      outright, and inventing a publisher to satisfy that rule would be fabricating
      provenance. It is a *lead list*, so it belongs in `review/`, not in `data/`.
  F2  `math1-outline-pubinfo-2026` and `eng1-outline-pubinfo-2026` were registered as
      `official_publisher` with `may_be_structured: true`. They are *bookseller* product
      pages transcribing the publisher's table of contents, not the publisher.
      `official_publisher` also sits in `SYLLABUS_AUTHORITATIVE_TIERS`, so those two rows
      currently grant bookstore pages the right to define the syllabus. Downgrade to
      `trusted_reprint`, `may_be_structured: false`, and name the actual site.
  F3  `eng1-exam-analysis-2026`'s "ISBN conflict" note can be resolved: 978-7-107-40461-0
      is the 考试分析, 978-7-107-40460-3 is the 考试大纲. Two books, not a conflict.

Guards: every changed file's sha256 before/after is printed, the ledger is re-loaded
through `load_ledger` after writing, and the whole thing is a no-op on a second run.
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

LEDGER = ROOT / "data" / "materials.yaml"
TODAY = "'2026-09-13T00:00:00+08:00'"
ACTOR = "dsh-round2-fix"

DOWNGRADES = {
    "math1-outline-pubinfo-2026": (
        "source_tier: official_publisher",
        "source_tier: trusted_reprint",
        "publisher: null",
        "publisher: 台湾大书城 search.megbook.com.tw（书店商品页，转录人教社目录）",
    ),
    "eng1-outline-pubinfo-2026": (
        "source_tier: official_publisher",
        "source_tier: trusted_reprint",
        "publisher: null",
        "publisher: 台湾大书城 search.megbook.com.tw（书店商品页，转录人教社目录）",
    ),
    # Same defect as F2, found by applying the reviewer's rule consistently rather
    # than only to the rows it named: this row's bytes come from yuntaigo (a
    # bookseller), so it may not hold a syllabus-authoritative tier either.
    "eng1-exam-analysis-2026": (
        "source_tier: official_publisher",
        "source_tier: trusted_reprint",
        "publisher: 人民教育出版社",
        "publisher: 人民教育出版社（官方编写）；本条字节取自 www.yuntaigo.com 书店书目页",
    ),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def block_bounds(text: str, resource_id: str) -> tuple[int, int]:
    start = text.index(f"- resource_id: {resource_id}\n")
    nxt = text.find("\n- resource_id: ", start + 1)
    return start, (nxt + 1 if nxt != -1 else len(text))


def re_sub_sha(block: str, old_sha: str, new_sha: str, new_size: int) -> str:
    """Point a storage block at the corrected bytes, in place."""
    if old_sha and old_sha in block:
        block = block.replace(old_sha, new_sha, 1)
    else:
        block = re.sub(r"(?m)^    sha256: .*$", f"    sha256: {new_sha}", block, count=1)
    block = re.sub(r"(?m)^    byte_size: .*$", f"    byte_size: {new_size}", block, count=1)
    return block


def main() -> int:
    before = sha(LEDGER)
    text = LEDGER.read_text(encoding="utf-8")
    changed: list[str] = []

    # ---- F4: eng1-outline-pubinfo-2026 holds the WRONG page bytes ------------
    # Its registered local copy has no table of contents and is not the page whose
    # URL it declares (`search.megbook.com.tw`, 8045 bytes on the wire / 8131 as
    # stored). The registered file is a different, TOC-less capture. The tree
    # builder anchors on that TOC, so the byte/hash pair must be corrected, not
    # worked around.
    good = ROOT / "cache" / "evidence" / "attach" / "search_megbook_com_tw_mall_detail_jsp_proID_4159208.html"
    target = ROOT / "data" / "raw_materials" / "eng1" / "syllabus" / "megbook_eng1_outline_pubinfo_2026.html"
    if good.is_file():
        good_sha = sha(good)
        cur_sha = sha(target) if target.is_file() else ""
        if cur_sha != good_sha:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(good.read_bytes())
            start, end = block_bounds(text, "eng1-outline-pubinfo-2026")
            block = text[start:end]
            block = re_sub_sha(block, cur_sha, good_sha, good.stat().st_size)
            text = text[:start] + block + text[end:]
            changed.append(
                f"eng1-outline-pubinfo-2026: stored bytes replaced "
                f"({cur_sha[:16] or 'missing'} -> {good_sha[:16]}); it now carries the TOC"
            )
        else:
            print("F4: eng1 TOC page already correct (no-op)")
    else:
        print(f"F4: source page for the fix not found at {good}")


    # ---- F1: drop the attachment entry -------------------------------------
    if "- resource_id: user-index-math1-eng1-2026\n" in text:
        start, end = block_bounds(text, "user-index-math1-eng1-2026")
        text = text[:start] + text[end:]
        changed.append("removed ledger entry user-index-math1-eng1-2026 (not registrable: no provenance)")
    else:
        print("F1: user-index entry already absent (no-op)")

    # ---- F2: downgrade the two bookseller pages ----------------------------
    for resource_id, (old_tier, new_tier, old_pub, new_pub) in DOWNGRADES.items():
        start, end = block_bounds(text, resource_id)
        block = text[start:end]
        if old_tier not in block:
            print(f"F2: {resource_id}: {old_tier!r} not present (already fixed?)")
        else:
            block = block.replace(old_tier, new_tier, 1)
            changed.append(f"{resource_id}: source_tier official_publisher -> trusted_reprint")
        if old_pub in block:
            block = block.replace(old_pub, new_pub, 1)
        # rights: a bookseller page may hold the bytes but may not authorise structure
        if "    may_be_structured: true" in block:
            block = block.replace("    may_be_structured: true", "    may_be_structured: false", 1)
            changed.append(f"{resource_id}: may_be_structured true -> false")
        # append an audit event so the downgrade is explainable later
        marker = "  history:\n"
        idx = block.index(marker) + len(marker)
        event = (
            f"  - at: {TODAY}\n"
            "    action: rights_changed\n"
            f"    actor: {ACTOR}\n"
            "    detail: 独立审查发现档位虚高：这是书店商品页（转录人教社目录），不是官方出版社；"
            "official_publisher 属于 SYLLABUS_AUTHORITATIVE_TIERS，等于把“定义考纲”的权限给了一家书店。"
            "降为 trusted_reprint 并关闭 may_be_structured。目录事实性内容仍可引用。\n"
        )
        if ACTOR not in block:
            block = block[:idx] + event + block[idx:]
            changed.append(f"{resource_id}: history event appended")
        text = text[:start] + block + text[end:]

    # ---- F3: resolve the exam-analysis ISBN note ---------------------------
    start, end = block_bounds(text, "eng1-exam-analysis-2026")
    block = text[start:end]
    if "未能确证" in block:
        block = block.replace(
            "在取得权威来源（人教社或教育考试院）确认前，本条目的\n    ISBN 不作为事实使用。",
            "2026-09-13 已解决：`978-7-107-40461-0` 是**本条目（考试分析）**，"
            "`978-7-107-40460-3` 是《2026 年…英语（一）考试大纲》，两者是**两本不同的书**，"
            "从来不是冲突。本条目 ISBN 可作为事实使用。",
        )
        changed.append("eng1-exam-analysis-2026: ISBN note resolved")
        text = text[:start] + block + text[end:]
    else:
        print("F3: exam-analysis ISBN note already resolved (no-op)")

    if not changed:
        print("nothing to do")
        return 0

    LEDGER.write_text(text, encoding="utf-8", newline="\n")
    after = sha(LEDGER)
    print(f"ledger sha256 {before[:16]} -> {after[:16]}")
    for c in changed:
        print("  -", c)

    # ---- re-validate through the real loader -------------------------------
    from ky.ledger import load_ledger

    materials = load_ledger(LEDGER)
    print(f"\nload_ledger: OK, {len(materials)} materials")
    authoritative = [m.resource_id for m in materials if m.provenance.may_define_syllabus()]
    print(f"materials that may_define_syllabus: {authoritative}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
