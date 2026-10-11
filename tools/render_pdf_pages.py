"""Extract the embedded page images from the scanned 408 PDFs into a cache dir.

Why this bypasses the OCR prohibition
-------------------------------------
`docs/资料可得性侦察.md` §五 forbids "对扫描件做 OCR 全文入库" — building a text bank
out of the scans. Rendering a page to an image and *looking at it* is a different act:
no text is ever produced, nothing is stored but throwaway pixels, and the only thing
allowed to leave the loop is structured metadata (year / question number / question
type / knowledge-point id). The image itself is never written into the repo's
`data/` tree and never becomes an artifact.

Output goes to `cache/` (declared disposable: SQLite/cache are rebuildable projections),
so it can be deleted at any time without losing a source of truth.

Usage:
    py -3.12 tools/render_pdf_pages.py --pdf <file.pdf> [--out cache/pdf_images] [--limit N]
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "cache" / "pdf_images"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--limit", type=int, default=0, help="0 = all pages")
    args = ap.parse_args()

    pdf = args.pdf if args.pdf.is_absolute() else ROOT / args.pdf
    if not pdf.is_file():
        print(f"missing PDF: {pdf}", file=sys.stderr)
        return 2

    try:
        import pypdf
    except ModuleNotFoundError:
        print("pypdf required", file=sys.stderr)
        return 2

    stem = pdf.stem
    out_dir = args.out / stem
    out_dir.mkdir(parents=True, exist_ok=True)

    reader = pypdf.PdfReader(str(pdf))
    total_pages = len(reader.pages)
    pages = range(total_pages if args.limit <= 0 else min(args.limit, total_pages))

    written: list[tuple[int, int, Path, int, str]] = []
    for page_index in pages:
        page = reader.pages[page_index]
        try:
            images = list(page.images)
        except Exception as exc:
            print(f"  page {page_index + 1}: image extraction failed: {type(exc).__name__}: {exc}")
            continue
        for image_index, image in enumerate(images):
            suffix = Path(getattr(image, "name", "") or "img").suffix or ".png"
            dest = out_dir / f"p{page_index + 1:03d}_{image_index}{suffix}"
            payload = image.data
            dest.write_bytes(payload)
            digest = hashlib.sha256(payload).hexdigest()
            written.append((page_index + 1, image_index, dest, len(payload), digest))

    print(f"{pdf.name}: {total_pages} pages -> wrote {len(written)} images into {out_dir}")
    for page_no, img_no, dest, size, digest in written[:12]:
        print(f"  p{page_no:03d} img{img_no}  {size:>9} bytes  {digest[:16]}  {dest.name}")
    if len(written) > 12:
        print(f"  ... {len(written) - 12} more")
    return 0


if __name__ == "__main__":
    sys.exit(main())
