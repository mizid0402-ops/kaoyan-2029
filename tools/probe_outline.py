"""Feature-count probe for an outline transcription.

Purpose: produce an HONEST count of what a candidate source file actually contains,
using two independent methods (HTML heading tags vs. plain-text numbered lines), and
print the headings themselves so a human can eyeball whether a whole tier was missed.

This is the project's "自己数出来的数字不可信" guard turned into a tool: never trust a
single counting method, and always show the items, not just the total.

Usage:
    py -3.12 tools/probe_outline.py <file.html> [--anchor <string>]
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

CN_NUM = "一二三四五六七八九十"
SEC_RE = re.compile(rf"^\s*(?:[（(]\s*[{CN_NUM}0-9]+\s*[)）]|[{CN_NUM}]+、)")


def strip_tags(fragment: str) -> str:
    fragment = re.sub(r"<script.*?</script>", " ", fragment, flags=re.I | re.S)
    fragment = re.sub(r"<style.*?</style>", " ", fragment, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", "\n", fragment)
    text = html.unescape(text)
    lines = [re.sub(r"[\s\u3000\xa0]+", "", ln) for ln in text.split("\n")]
    return "\n".join([ln for ln in lines if ln])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", type=Path)
    ap.add_argument("--anchor", default=None, help="start scanning after this literal")
    args = ap.parse_args()

    raw = args.path.read_text(encoding="utf-8", errors="replace")
    if args.anchor and args.anchor in raw:
        raw = raw.split(args.anchor, 1)[1]

    text = strip_tags(raw)
    lines = text.split("\n")

    # method 1: plain-text numbered headings
    numbered = [ln for ln in lines if SEC_RE.match(ln) and 2 <= len(ln) <= 40]
    # method 2: HTML tags that usually carry headings
    tagged = re.findall(r"<(h[2-5]|strong|b)[^>]*>\s*([^<]{2,40}?)\s*</\1>", raw, re.I)

    print(f"file: {args.path}")
    print(f"method 1 (plain-text 编号行): {len(numbered)}")
    for ln in numbered:
        print(f"    {ln}")
    print(f"\nmethod 2 (HTML 粗体/标题标签): {len(tagged)}")
    seen: list[str] = []
    for _tag, body in tagged:
        body = html.unescape(re.sub(r"\s+", "", body))
        if body and body not in seen:
            seen.append(body)
    for s in seen:
        print(f"    {s}")
    print(f"method 2 去重后: {len(seen)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
