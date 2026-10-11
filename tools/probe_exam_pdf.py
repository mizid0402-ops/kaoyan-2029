"""Download a candidate exam PDF and report what it actually is.

`docs/资料可得性侦察.md` §2.4(4) requires classifying any exam material by *content*,
not by filename: "已按实际内容标注，未按文件名标注". So this fetches the bytes, then
reports the facts a human needs to judge it (page count, text layer, embedded-image
geometry, and whether the identifier strings one would expect are present) — and
refuses to print any question text.

Download target is a *staging* path under cache/, never data/raw_materials: nothing
becomes a registered source until the user accepts its provenance.

Usage:
    py -3.12 tools/probe_exam_pdf.py --url <url> [--name probe.pdf] [--render-page N]
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "cache" / "exam_probe"

# Content-shape probes. These are structural markers, not question text: the header
# band of a 408 paper states the exam identity and the section headings.
MARKERS = [
    "全国硕士研究生", "计算机学科专业基础", "408", "单项选择题", "综合应用题",
    "数据结构", "计算机组成原理", "操作系统", "计算机网络", "绝密", "参考答案",
]


class _DownloadFailure(Exception):
    def __init__(self, exception_name: str):
        super().__init__(exception_name)
        self.exception_name = exception_name


def _download_pdf(url: str, name: str):
    import requests

    STAGE.mkdir(parents=True, exist_ok=True)
    dest = STAGE / name
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        response = requests.get(url, headers=headers, timeout=90, allow_redirects=True)
    except requests.RequestException as exc:
        raise _DownloadFailure(type(exc).__name__) from None
    dest.write_bytes(response.content)
    digest = hashlib.sha256(response.content).hexdigest()
    return response, dest, digest


def _inspect_pdf(reader) -> tuple[int, int]:
    pages = len(reader.pages)
    chars = 0
    for page in reader.pages[: min(5, pages)]:
        chars += len((page.extract_text() or "").strip())
    return pages, chars


def _print_download_summary(url, response, dest, digest) -> None:
    print(f"url         : {url}")
    print(f"final_url   : {response.url}")
    print(
        f"http        : {response.status_code}  "
        f"content-type: {response.headers.get('Content-Type')}"
    )
    print(f"bytes       : {len(response.content)}")
    print(f"sha256      : {digest}")
    print(f"magic       : {response.content[:8].decode('latin-1')!r}")
    print(f"staged at   : {dest.relative_to(ROOT).as_posix()}  (staging only, not registered)")
    print()


def _print_pdf_metadata(reader) -> None:
    try:
        meta = reader.metadata or {}
        for key in ("/Title", "/Author", "/Producer", "/Creator", "/CreationDate"):
            if meta.get(key):
                print(f"meta {key:14}: {str(meta[key])[:120]}")
    except Exception:
        pass


def _print_marker_scan(reader) -> None:
    print("\nmarker scan (structure only, no question text printed):")
    try:
        head = "".join(
            reader.pages[i].extract_text() or ""
            for i in range(min(2, len(reader.pages)))
        )
    except Exception:
        head = ""
    hits = [marker for marker in MARKERS if marker in head]
    print(f"  text layer empty -> markers unavailable" if not head.strip()
          else f"  found in first 2 pages: {hits}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--name", default="probe.pdf")
    ap.add_argument("--render-page", type=int, default=0)
    args = ap.parse_args()

    try:
        r, dest, digest = _download_pdf(args.url, args.name)
    except _DownloadFailure as exc:
        print(
            f"download failed: {args.url} ({exc.exception_name})",
            file=sys.stderr,
        )
        return 1

    _print_download_summary(args.url, r, dest, digest)

    if not r.content[:5].startswith(b"%PDF"):
        print("NOT a PDF payload — stopping here")
        return 1

    import pypdf

    reader = pypdf.PdfReader(str(dest))
    pages, chars = _inspect_pdf(reader)
    print(f"pages       : {pages}")
    print(f"text layer  : {chars} chars in first {min(5, pages)} pages "
          f"({'HAS TEXT' if chars > 200 else 'SCANNED IMAGE ONLY'})")

    # structural markers on the rendered first pages, via embedded image count
    try:
        page = reader.pages[0]
        images = list(page.images)
        print(f"page 1 media: {len(images)} embedded image(s)")
        for image in images[:3]:
            print(f"              name={getattr(image, 'name', '?')} bytes={len(image.data)}")
    except Exception as exc:
        print(f"page 1 media: could not enumerate ({type(exc).__name__})")

    _print_pdf_metadata(reader)

    if args.render_page:
        out_dir = STAGE / (dest.stem + "_pages")
        out_dir.mkdir(parents=True, exist_ok=True)
        idx = args.render_page - 1
        if 0 <= idx < pages:
            target = out_dir / f"p{args.render_page:03d}.jpg"
            for i, image in enumerate(reader.pages[idx].images):
                target = out_dir / f"p{args.render_page:03d}_{i}.jpg"
                target.write_bytes(image.data)
                print(f"rendered    : {target.relative_to(ROOT).as_posix()}")
        else:
            print(f"render-page {args.render_page} out of range (1..{pages})")

    _print_marker_scan(reader)
    return 0


if __name__ == "__main__":
    sys.exit(main())
