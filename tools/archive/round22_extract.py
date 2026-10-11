"""Replay the fixed round-22 outline comparison with historical paths."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from cs408_outline_extract import (
    SUBJECTS,
    compare,
    extract_2022,
    extract_2026,
    flatten,
    tree_reverse_check,
)

PDF = ROOT / "data/raw_materials/cs408/syllabus/408_syllabus_2022.pdf"
HTML = ROOT / "data/raw_materials/cs408/syllabus/archive408_408_outline_2026.html"
TREE = ROOT / "data/structured_materials/cs408/knowledge_tree.yaml"
OUT = Path(r"C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\round22_results.json")


def main() -> None:
    d22 = extract_2022(PDF)
    d26 = extract_2026(HTML)
    f22 = flatten(d22)
    f26 = flatten(d26)
    result = {
        "2022": d22,
        "2026": d26,
        "flat_2022": f22,
        "flat_2026": f26,
        "compare": compare(f22, f26),
        "tree_reverse": tree_reverse_check(d22, TREE),
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
