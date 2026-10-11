"""Report whether each registered PDF has an extractable text layer.

The reconnaissance claimed all seven 408 PDFs are scans with no text layer. That
claim decides the whole next work item (OCR vs. plain text extraction), so it gets
measured rather than remembered.

Usage:  py -3.12 tools/probe_pdf_text.py [--dir <path>]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = ROOT / "data" / "raw_materials" / "cs408" / "past_papers"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    ap.add_argument("--sample-pages", type=int, default=3)
    ap.add_argument("--with-images", action="store_true",
                    help="also report the number of embedded images per sampled page")
    args = ap.parse_args()

    try:
        import pypdf
    except ModuleNotFoundError:
        print("pypdf is required: py -3.12 -m pip install pypdf", file=sys.stderr)
        return 2

    pdfs = sorted(args.dir.glob("*.pdf"))
    if not pdfs:
        print(f"no PDFs under {args.dir}")
        return 2

    print(f"{'file':<26}{'pages':>6}{'text(chars)':>13}  verdict")
    scanned = 0
    for path in pdfs:
        try:
            reader = pypdf.PdfReader(str(path))
            pages = len(reader.pages)
            sample = reader.pages[: args.sample_pages]
            chars = sum(len((p.extract_text() or "").strip()) for p in sample)
            images = 0
            if args.with_images:
                for page in sample:
                    try:
                        images += len(list(page.images))
                    except Exception:
                        pass
            verdict = "TEXT LAYER" if chars > 200 else "SCANNED (no text layer)"
            if chars <= 200:
                scanned += 1
            extra = f" images={images}" if args.with_images else ""
            print(f"{path.name:<26}{pages:>6}{chars:>13}  {verdict}{extra}")
        except Exception as exc:  # a broken PDF is a finding, not a crash
            print(f"{path.name:<26}{'?':>6}{'?':>13}  ERROR {type(exc).__name__}: {exc}")

    print(f"\n{scanned}/{len(pdfs)} files have no text layer in the first {args.sample_pages} pages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
