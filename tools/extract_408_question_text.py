"""M21 408 paper-text extractor; see ``contracts/workspace.md``.

Public interface: ``paper_for(year, papers_root)`` and CLI ``main()``. Inputs come from the
registered raw-material and exam-index paths; outputs stay in the registered product directory.

Why this exists
---------------
The deck scaffold referenced questions by id, year and page but carried no text, on the
assumption that whoever authored the slides would paste an excerpt. In practice that meant the
slides showed no question at all -- which defeats the point of quoting one for credibility.

So the text is extracted here, once, with provenance, into a side directory. The deck files stay
metadata-only and the author copies in the specific excerpt they need, under QUOTATION_POLICY.md.

Provenance is mandatory: every extracted item records the paper file, its SHA-256, the page, and
the question number, so any excerpt in a slide can be traced back to a page of a known file.

Output: questions/<question_id>.txt  plus  questions_index.json
"""

from __future__ import annotations

import hashlib
import argparse
import json
import re
import sys
from pathlib import Path

import pypdf

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from ky.workspace import load_workspace  # noqa: E402

# Question numbering in the collected 408 papers uses several styles; accept all of them.
NUM_PATTERNS = [
    r"^\s*(\d{1,2})[.、．]\s*",
    r"^\s*[（(](\d{1,2})[)）]\s*",
    r"^\s*【(\d{1,2})】\s*",
]
NUM_RE = re.compile("|".join(f"(?:{p})" for p in NUM_PATTERNS), re.M)


def paper_for(year: int, papers_root: Path) -> Path | None:
    for cand in sorted(papers_root.glob(f"*{year}*paper*.pdf")):
        return cand
    return None


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def page_texts(pdf: Path) -> list[str]:
    return [(pg.extract_text() or "") for pg in pypdf.PdfReader(str(pdf)).pages]


def extract_registered_questions(index_paths: tuple[Path, ...], papers_root: Path,
                                 output_dir: Path) -> tuple[list[dict], list[str]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    index: list[dict] = []
    missing: list[str] = []
    for idx_file in index_paths:
        data = json.loads(idx_file.read_text(encoding="utf-8"))
        year = int(data["exam_year"])
        pdf = paper_for(year, papers_root)
        if pdf is None:
            missing.append(f"{year}: no paper file")
            continue
        digest = sha256(pdf)
        pages = page_texts(pdf)
        for entry in data["entries"]:
            record = _extract_entry(entry, year, pdf, digest, pages)
            if record is None:
                missing.append(entry["question_id"])
                continue
            (output_dir / f"{record['question_id']}.txt").write_text(
                record["text"] + "\n",
                encoding="utf-8",
                newline="\n",
            )
            index.append(record)
    (output_dir / "questions_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=1),
        encoding="utf-8",
        newline="\n",
    )
    return index, missing


def _extract_entry(entry: dict, year: int, pdf: Path, digest: str,
                   pages: list[str]) -> dict | None:
    number = int(entry["number"])
    page = int((entry.get("locator") or {}).get("page") or 0)
    order = ([page - 1] if page else []) + [
        index for index in range(len(pages)) if page == 0 or index != page - 1
    ]
    found_page, found_text = None, ""
    for page_index in order:
        if not 0 <= page_index < len(pages):
            continue
        text = pages[page_index]
        for match in re.finditer(rf"(?m)^\s*(?:{number})[.、．)）】]\s*", text):
            segment = text[match.start(): match.start() + 1400]
            following = re.search(
                r"(?m)^\s*(?:1?\d|2\d|3\d|4\d|5\d)[.、．)）】]\s+",
                segment[4:],
            )
            if following:
                segment = segment[: 4 + following.start()]
            if len(segment.strip()) > 25:
                found_page, found_text = page_index + 1, segment.strip()
                break
        if found_text:
            break
    if not found_text:
        return None
    return {
        "question_id": entry["question_id"],
        "exam_year": year,
        "number": number,
        "question_type": entry["question_type"],
        "marks": entry.get("marks"),
        "paper_file": pdf.name,
        "paper_sha256": digest,
        "page": found_page,
        "text": found_text,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path)
    args = parser.parse_args()
    workspace = load_workspace(args.workspace)
    raw_root = workspace.require("materials.raw_root")
    output_dir = workspace.require("products.cs408_lecture_workspace") / "questions"
    indexes = workspace.require_all("reference.exam_indexes.cs408")
    records, missing = extract_registered_questions(
        indexes,
        raw_root / "cs408" / "past_papers",
        output_dir,
    )
    papers = sorted((raw_root / "cs408" / "past_papers").glob("*.pdf"))
    print(f"papers found : {[path.name for path in papers]}")
    print(f"questions extracted: {len(records)}")
    print(f"not extracted     : {len(missing)} -> {missing[:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
