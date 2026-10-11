"""Probe a third-party 408 quiz page and report which cross-checkable facts it exposes.

Goal: find out whether csgraduates.com's per-year pages can serve as an *independent*
source for (a) the 40 multiple-choice answer letters and (b) the per-question topic.
That would let two-or-more-source agreement stand in for the official book.

Only structured facts are reported: option-key counts, whether answer letters appear,
whether per-question topic labels appear, and how many questions the page covers.
Question text is never printed — this prints counts and marker words only.

Usage:  py -3.12 tools/archive/probe_quiz_page.py --dir cache/evidence/index2 [--json out.json]
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

TARGETS = [
    ("2023", "www_csgraduates_com_study_methods_408quiz_2023.html"),
    ("2024", "www_csgraduates_com_study_methods_408quiz_2024.html"),
    ("2025", "www_csgraduates_com_study_methods_408quiz_2025.html"),
    ("2026", "www_csgraduates_com_study_methods_408quiz_2026.html"),
]

# markers that indicate a *structured* answer key rather than prose
ANSWER_MARKERS = ["正确答案", "参考答案", "答案", "解析"]
TOPIC_MARKERS = ["考点", "知识点", "本题考查", "所属章节", "章节"]
SECTION_MARKERS = ["数据结构", "计算机组成原理", "操作系统", "计算机网络"]


def text_of(path: Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="replace")
    raw = re.sub(r"<!--.*?-->", " ", raw, flags=re.S)
    raw = re.sub(r"<script.*?</script>", " ", raw, flags=re.I | re.S)
    raw = re.sub(r"<style.*?</style>", " ", raw, flags=re.I | re.S)
    return html.unescape(re.sub(r"<[^>]+>", "\n", raw))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, default=ROOT / "cache" / "evidence" / "index2")
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args()

    report = []
    for year, filename in TARGETS:
        path = args.dir / filename
        if not path.is_file():
            print(f"{year}: MISSING {filename}")
            continue
        text = text_of(path)
        lines = [re.sub(r"[\s\u3000\xa0]+", " ", ln).strip() for ln in text.splitlines()]
        lines = [ln for ln in lines if ln]

        # question numbering 1..N
        numbers = {int(m.group(1)) for m in re.finditer(r"^\s*(\d{1,2})\s*[.、．]", text, re.M)}
        contiguous = sorted(n for n in numbers if 1 <= n <= 47)

        # answer letters: patterns like "1. A" / "1．A" inside an answer-table region
        letter_rows = re.findall(r"(\d{1,2})\s*[.、．:：]\s*([ABCD])\b", text)
        option_lines = len(re.findall(r"^\s*[ABCD]\s*[.、．]", text, re.M))

        counts = {marker: text.count(marker) for marker in ANSWER_MARKERS + TOPIC_MARKERS}
        sections = {marker: text.count(marker) for marker in SECTION_MARKERS}
        patterns = re.findall(r"pattern|genome|nucleotide", text, re.I)

        entry = {
            "year": year,
            "file": filename,
            "bytes": path.stat().st_size,
            "numbered_lines": len(contiguous),
            "number_range": [contiguous[0], contiguous[-1]] if contiguous else None,
            "missing_1_to_47": [n for n in range(1, 48) if n not in numbers],
            "answer_letter_pairs": len(letter_rows),
            "option_lines": option_lines,
            "markers": counts,
            "section_words": sections,
        }
        report.append(entry)

        print(f"--- {year}  ({entry['bytes']} bytes)")
        print(f"    numbered lines 1..47 present : {len(contiguous)}  range {entry['number_range']}")
        print(f"    missing numbers              : {entry['missing_1_to_47'][:12]}"
              f"{' ...' if len(entry['missing_1_to_47']) > 12 else ''}")
        print(f"    answer-letter pairs (N. X)   : {len(letter_rows)}")
        print(f"    option lines (A. B. C. D.)   : {option_lines}")
        print(f"    markers                      : {counts}")
        print(f"    section words                : {sections}")

    if args.json:
        out = args.json if args.json.is_absolute() else ROOT / args.json
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nwrote {out.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
