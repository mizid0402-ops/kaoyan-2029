"""Extract the structural skeleton of a text-layer exam PDF without emitting any content.

Purpose: decide whether question boundaries can be found *programmatically*, and give
the user a plan estimate (how many questions, where each section starts) — while
printing no question text at all.

What is printed for each detected question-start line:
    the question number, and a redacted shape of the remainder (ASCII letters, digits
    and punctuation collapsed), e.g.  `12. ______ ( )`  — never the words.

What is printed for section headings: the heading, because 408 section headings are
fixed taxonomy ("一、单项选择题", "数据结构", "综合应用题") already present in the
official outline we already hold, not question content.

Nothing is written to disk except an optional JSON index containing only counts and
line numbers.

Usage:
    py -3.12 tools/extract_exam_skeleton.py --pdf <file.pdf> [--json <out.json>]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CN = "一二三四五六七八九十"
# section headers we expect in a 408 paper (taxonomy, not content)
SECTION_PAT = re.compile(
    rf"^\s*(?:[{CN}]+、)?\s*(单项选择题|综合应用题|数据结构|计算机组成原理|操作系统|计算机网络)\s*$"
)
Q_START = re.compile(r"^\s*(\d{1,2})\s*[.、．]\s*(\S.*)$")


def redact_shape(text: str) -> str:
    """Collapse a line to punctuation/digit shape, dropping all words.

    Latin words become `A`, CJK runs become `汉`, digits stay, everything else stays.
    """
    out = re.sub(r"[A-Za-z]+", "A", text)
    out = re.sub(r"[\u4e00-\u9fff]+", "汉", out)
    out = re.sub(r"\s+", " ", out)
    return out[:60]


def _read_structure(pdf: Path):
    import pypdf

    reader = pypdf.PdfReader(str(pdf))
    starts: list[dict] = []
    sections: list[dict] = []
    for page_index, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        for line_no, raw_line in enumerate(text.splitlines()):
            line = raw_line.strip()
            if not line:
                continue
            if SECTION_PAT.match(line):
                sections.append({"page": page_index + 1, "line": line_no, "heading": line})
                continue
            match = Q_START.match(line)
            if match:
                starts.append({
                    "page": page_index + 1,
                    "line": line_no,
                    "number": int(match.group(1)),
                    "shape": redact_shape(match.group(2)),
                })
    return len(reader.pages), starts, sections


def _print_structure(
    pdf: Path, page_count: int, starts: list[dict], sections: list[dict], head: int,
):
    print(f"pdf        : {pdf.name}")
    print(f"pages      : {page_count}")
    print(f"q-starts   : {len(starts)}")
    print(f"sections   : {len(sections)}")
    print()
    print("section headings (taxonomy only):")
    for entry in sections:
        print(f"  p{entry['page']:>3}  {entry['heading']}")
    print()
    print(f"first {min(head, len(starts))} question starts (number + redacted shape):")
    for entry in starts[:head]:
        print(f"  p{entry['page']:>3}  {entry['number']:>2}. {entry['shape']}")
    if len(starts) > head:
        print(f"  ... {len(starts) - head} more")
    numbers = [entry["number"] for entry in starts]
    seen = sorted(set(numbers))
    gaps = [n for n in range(1, (max(seen) if seen else 0) + 1) if n not in seen]
    dupes = sorted({n for n in numbers if numbers.count(n) > 1})
    print()
    print(f"number range: {min(seen) if seen else '-'}..{max(seen) if seen else '-'}")
    print(f"missing numbers: {gaps if gaps else 'none'}")
    print(f"duplicate numbers: {dupes if dupes else 'none'}")
    return seen, gaps, dupes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--json", type=Path, default=None)
    ap.add_argument("--head", type=int, default=40, help="how many question starts to show")
    args = ap.parse_args()

    pdf = Path(args.pdf)
    if not pdf.is_absolute():
        pdf = ROOT / pdf
    if not pdf.is_file():
        print(f"missing: {pdf}", file=sys.stderr)
        return 2

    page_count, starts, sections = _read_structure(pdf)
    seen, gaps, dupes = _print_structure(pdf, page_count, starts, sections, args.head)

    if args.json:
        payload = {
            "pdf": pdf.relative_to(ROOT).as_posix() if pdf.is_relative_to(ROOT) else str(pdf),
            "pages": page_count,
            "question_start_count": len(starts),
            "number_range": [min(seen), max(seen)] if seen else None,
            "missing_numbers": gaps,
            "duplicate_numbers": dupes,
            "sections": sections,
            # NOTE: only line numbers and counts — no question text is stored anywhere
            "question_lines": [{k: e[k] for k in ("page", "line", "number")} for e in starts],
        }
        out = args.json if args.json.is_absolute() else ROOT / args.json
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
            newline="\n",
        )
        out_label = (
            out.relative_to(ROOT).as_posix()
            if out.is_relative_to(ROOT)
            else str(out)
        )
        print(f"\nindex (structure only, no content) -> {out_label}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
