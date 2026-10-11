"""Print the 408 tree's item-level vocabulary so classification patterns can be built.

The classifier must map a question to a node that *already exists* in the tree (which
comes from the official outline). So the pattern bank has to be derived from node
titles, not from a model's idea of what 408 covers.

Prints: subject, chapter, section and item titles with their ids, filtered/grouped.
No exam content is involved.

Usage:  py -3.12 tools/list_tree_vocab.py [--subject ds] [--scope item]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ky.knowledge.knowledge_point import load_knowledge_points  # noqa: E402

TREE = ROOT / "data" / "structured_materials" / "cs408" / "knowledge_tree.yaml"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", default="item")
    ap.add_argument("--prefix", default="")
    args = ap.parse_args()

    points = load_knowledge_points(TREE)
    for point in points:
        if point.scope != args.scope:
            continue
        if args.prefix and not point.knowledge_point_id.startswith(args.prefix):
            continue
        print(f"{point.knowledge_point_id:<46} {point.title}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
