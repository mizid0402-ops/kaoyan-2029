from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from cs408_outline_extract import key


DATA = Path(r"C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\round22_results.json")
OUT = Path(r"C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\round22_lists.md")


def main():
    d = json.loads(DATA.read_text(encoding="utf-8"))
    lines = []
    for subject, cmp in d["compare"].items():
        lines.append("## " + subject)
        lines.append("2022-only (" + str(len(cmp["only_2022"])) + ")")
        lines.extend("- " + x for x in cmp["only_2022"])
        lines.append("2026-only (" + str(len(cmp["only_2026"])) + ")")
        lines.extend("- " + x for x in cmp["only_2026"])
        lines.append("both (" + str(cmp["both"]) + ")")
        lines.extend("- " + x for x in cmp["both_titles_2022"])
        lines.append("")
    lines.append("section overlaps")
    for subject in d["compare"]:
        a = {key(x) for x in d["flat_2022"][subject]["sections"]}
        b = {key(x) for x in d["flat_2026"][subject]["sections"]}
        lines.append("%s | intersection=%d | union=%d | 2022=%d | 2026=%d" % (subject, len(a & b), len(a | b), len(a), len(b)))
    lines.append("tree reverse by subject")
    lines.append(str(d["tree_reverse"]["by_subject"]))
    OUT.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
