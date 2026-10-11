"""Dump the embedded images of a staged PDF page so a human (or a vision pass) can read it.

Staging only: output goes to `cache/`, nothing is registered, nothing is committed.
Question text is never printed to stdout — only file paths and sizes.

Usage:  py -3.12 tools/render_staged_page.py --pdf <staged.pdf> --page 1
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--page", type=int, default=1, help="1-based")
    args = ap.parse_args()

    pdf = Path(args.pdf)
    if not pdf.is_absolute():
        pdf = ROOT / pdf
    if not pdf.is_file():
        print(f"missing: {pdf}", file=sys.stderr)
        return 2

    import pypdf

    reader = pypdf.PdfReader(str(pdf))
    pages = len(reader.pages)
    idx = args.page - 1
    if not 0 <= idx < pages:
        print(f"page {args.page} out of range 1..{pages}", file=sys.stderr)
        return 2

    out_dir = pdf.parent / f"{pdf.stem}_pages"
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for i, image in enumerate(reader.pages[idx].images):
        suffix = Path(getattr(image, "name", "") or "img.png").suffix or ".png"
        dest = out_dir / f"p{args.page:03d}_{i}{suffix}"
        dest.write_bytes(image.data)
        written.append((dest, len(image.data)))

    print(f"{pdf.name} page {args.page}/{pages}: {len(written)} image(s)")
    for dest, size in written:
        print(f"  {dest.relative_to(ROOT).as_posix()}  {size} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
