"""Remove the 厦门工学院-rehosted 408 papers from the project.

Decision (user, 2026-09-13): 这些是民办本科转载页挂的、无署名编者的真题扫描件，
不作为本项目的 408 真题来源。

What this does, in order, so nothing dangles:
  1. rewrites data/materials.yaml without the six cs408 paper/solutions rows;
  2. deletes the PDFs under data/raw_materials/cs408/past_papers/
     (the whole directory — it exists only for those files);
  3. deletes the page images rendered from them under cache/pdf_images/
     (derived, disposable; rendering them was a feasibility probe, not an artifact);
  4. re-loads the ledger and re-checks byte integrity;
  5. prints every file it removed with its sha256, so the removal itself is auditable.

The ledger is rewritten by text surgery, not by dumping parsed YAML: re-serialising
would reformat all remaining 17 entries and bury this change in noise.

Usage:
    py -3.12 tools/migrations/remove_408_reprints.py --check     # dry run
    py -3.12 tools/migrations/remove_408_reprints.py             # execute
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
PAPERS_DIR = ROOT / "data" / "raw_materials" / "cs408" / "past_papers"
IMAGE_DIR = ROOT / "cache" / "pdf_images"

# The six rows created for that source. `ref-exam-material-links-2026` is NOT in this
# list: it is a link-only row for a different, still-undecided source.
REMOVE = [
    "cs408-paper-2022",
    "cs408-paper-2023",
    "cs408-paper-2024",
    "cs408-paper-2025",
    "cs408-solutions-2022",
    "cs408-solutions-2023",
    "cs408-solutions-2024",
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bounds(text: str, rid: str) -> tuple[int, int]:
    start = text.index(f"- resource_id: {rid}\n")
    nxt = text.find("\n- resource_id: ", start + 1)
    return start, (nxt + 1 if nxt != -1 else len(text))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    text = LEDGER.read_text(encoding="utf-8")
    plan_ledger: list[str] = []
    for rid in REMOVE:
        if f"- resource_id: {rid}\n" in text:
            plan_ledger.append(rid)
        else:
            print(f"note: {rid} already absent from the ledger")
    plan_files = sorted(p for p in PAPERS_DIR.glob("*") if p.is_file()) if PAPERS_DIR.is_dir() else []
    plan_images = IMAGE_DIR.is_dir() and any(IMAGE_DIR.iterdir())

    print(f"ledger rows to remove      : {len(plan_ledger)}")
    for rid in plan_ledger:
        print(f"    - {rid}")
    print(f"files to delete            : {len(plan_files)}")
    for p in plan_files:
        print(f"    - {p.relative_to(ROOT).as_posix()}  {p.stat().st_size} bytes  {sha(p)[:16]}")
    print(f"derived image dir to delete: {IMAGE_DIR.relative_to(ROOT).as_posix()}"
          f"  ({plan_images and sum(1 for _ in IMAGE_DIR.rglob('*') if _.is_file()) or 0} files)")

    if args.check:
        print("\n--check: nothing written")
        return 0

    removed_rows = 0
    for rid in plan_ledger:
        start, end = bounds(text, rid)
        text = text[:start] + text[end:]
        removed_rows += 1
    LEDGER.write_text(text, encoding="utf-8", newline="\n")
    print(f"\nledger rewritten: {removed_rows} rows removed, {len(text.encode('utf-8'))} bytes")

    for p in plan_files:
        p.unlink()
    if PAPERS_DIR.is_dir() and not any(PAPERS_DIR.iterdir()):
        PAPERS_DIR.rmdir()
        parent = PAPERS_DIR.parent
        if parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()
    print(f"deleted {len(plan_files)} PDFs and the now-empty past_papers directory")

    if IMAGE_DIR.is_dir():
        shutil.rmtree(IMAGE_DIR)
        print(f"deleted derived images: {IMAGE_DIR.relative_to(ROOT).as_posix()}")

    from ky.ledger import integrity_report, load_ledger, ledger_summary

    materials = load_ledger(LEDGER)
    integrity = dict(integrity_report(materials, root=ROOT))
    summary = ledger_summary(materials)
    bad = [m.resource_id for m in materials if m.storage.mode == "local_file" and not integrity.get(m.resource_id)]
    print(f"\nload_ledger: OK, {len(materials)} materials (was {len(materials) + removed_rows})")
    print(f"by kind    : {summary['by_kind']}")
    print(f"integrity  : {len(materials) - len(bad)}/{len(materials)} local files ok"
          f"{'' if not bad else ' -- FAILING: ' + str(bad)}")
    leftover = [m.resource_id for m in materials if "xit.edu.cn" in (m.provenance.source_url or "")]
    print(f"rows still citing xit.edu.cn: {leftover if leftover else 'none'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
