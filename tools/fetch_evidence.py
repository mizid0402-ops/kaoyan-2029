"""Fetch remote pages into an evidence vault, recording honest provenance.

Usage:
    py -3.12 tools/fetch_evidence.py <urls.txt> [--out <dir>]

Each URL produces:
    <out>/<slug>.html          decoded body (if the response is textual)
    <out>/<slug>.json          status, final URL, HTTP headers, sha256, byte size, charset

Design notes (project rules):
  * We record what we actually got. A non-200, a challenge page, or a binary
    payload is an honest result, never silently upgraded to "verified".
  * HTML is decoded with <meta charset> / Content-Type sniffing, falling back to
    gb18030 then utf-8 with replacement, because many CN book sites are GBK.
  * Nothing here interprets page content as instructions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

import requests

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

TEXTUAL = re.compile(r"text/|json|xml|javascript", re.I)


def slugify(url: str) -> str:
    s = re.sub(r"^https?://", "", url)
    s = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "_", s)
    return s.strip("_")[:120]


def sniff_charset(raw: bytes, content_type: str) -> str:
    m = re.search(r"charset=([\w-]+)", content_type or "", re.I)
    if m:
        return m.group(1)
    head = raw[:4096].decode("ascii", "ignore")
    m = re.search(r'charset=["\']?([\w-]+)', head, re.I)
    if m:
        return m.group(1)
    return ""


def decode(raw: bytes, content_type: str) -> tuple[str, str]:
    declared = sniff_charset(raw, content_type)
    for enc in [declared, "utf-8", "gb18030"]:
        if not enc:
            continue
        try:
            return raw.decode(enc), enc
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", "replace"), "utf-8/replace"


def fetch(url: str, out: Path, timeout: int = 45) -> dict:
    rec: dict = {"url": url, "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
    except Exception as exc:  # network-level failure is a result, not a crash
        rec.update({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
        return rec

    raw = r.content
    ctype = r.headers.get("Content-Type", "")
    rec.update(
        {
            "ok": True,
            "http_status": r.status_code,
            "final_url": r.url,
            "content_type": ctype,
            "byte_size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "redirected": r.url != url,
        }
    )
    slug = slugify(url)
    if TEXTUAL.search(ctype) or not ctype:
        text, enc = decode(raw, ctype)
        rec["encoding"] = enc
        rec["title"] = (re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S) or [None, ""])[1]
        rec["title"] = re.sub(r"\s+", " ", rec["title"]).strip()[:200]
        (out / f"{slug}.html").write_text(text, encoding="utf-8")
        rec["saved_as"] = f"{slug}.html"
    else:
        (out / f"{slug}.bin").write_bytes(raw)
        rec["saved_as"] = f"{slug}.bin"
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("url_file", type=Path)
    ap.add_argument("--out", type=Path, default=Path("cache/evidence"))
    ap.add_argument("--index", type=Path, default=None)
    args = ap.parse_args()

    urls = [
        line.strip()
        for line in args.url_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    args.out.mkdir(parents=True, exist_ok=True)

    records = []
    for i, url in enumerate(urls, 1):
        rec = fetch(url, args.out)
        records.append(rec)
        status = rec.get("http_status", rec.get("error", "?"))
        print(f"[{i}/{len(urls)}] {status} {rec.get('byte_size', '-')} {url}", flush=True)
        if rec.get("title"):
            print(f"        title: {rec['title'][:110]}", flush=True)

    index = args.index or (args.out / "index.json")
    index.write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nindex -> {index}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
