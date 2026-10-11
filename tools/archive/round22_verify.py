from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from archive.round22_extract import HTML, PDF
from cs408_outline_extract import extract_2022, extract_2026, key


OUT = Path(r"C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\round22_verify.txt")


def flatten_counts(data):
    return {
        n: (
            sum(len(x["chapters"]) for x in s["subjects"].values()),
            sum(len(c["sections"]) for s in data["subjects"].values() for c in s["chapters"]),
            sum(len(sec["items"]) for s in data["subjects"].values() for c in s["chapters"] for sec in c["sections"]),
        )
        for n, data in [("2022", data)]
    }


def main():
    a = extract_2022(PDF)
    b = extract_2022(PDF)
    c = extract_2026(HTML)
    deterministic = json.dumps(a, ensure_ascii=False, sort_keys=True) == json.dumps(b, ensure_ascii=False, sort_keys=True)
    section_re = re.compile(r"(?<![A-Za-z0-9])[(（]\s*([一二三四五六七八九十—-]{1,3})\s*[)）〕\]]\s*[.]?")
    item_re = re.compile(r"(?<![A-Za-z0-9])(?:\d{1,2}\s*[.]|\d{1,2}(?=\s+[\u3400-\u9fff])|[⒈⒉⒊⒋⒌⒍⒎⒏⒐]|(?<!\w)-(?=[\u3400-\u9fffA-Za-z]))")
    marker_fixture = "(一)甲\n1.乙\n（四）丙\n⒉丁\n(六).戊\n2 己\n（—）庚\n-辛"
    marker_ok = len(section_re.findall(marker_fixture)) == 4 and len(item_re.findall(marker_fixture)) == 4
    all_items = [x for s in a["subjects"].values() for ch in s["chapters"] for sec in ch["sections"] for x in sec["items"]]
    sample_titles = ["顺序存储", "二叉树的遍历", "基本运算部件:加法器、算术逻辑部件(ALu)", "页椎分配", "HTTP 协议"]
    sample_ok = all(key(t) in key(a["normalized_source_text"]) for t in sample_titles)
    counts = {name: (len(s["chapters"]), sum(len(c["sections"]) for c in s["chapters"]), sum(len(sec["items"]) for c in s["chapters"] for sec in c["sections"])) for name, s in a["subjects"].items()}
    out = [
        "sha=" + a["metadata"]["sha256"],
        "deterministic=" + str(deterministic),
        "marker_variants=" + str(marker_ok),
        "line_wrap_sample=" + str(key("计算机系统的工作原理:\n存储程序、工作方式") in key(a["normalized_source_text"])),
        "source_anchor_samples=" + str(sample_ok),
        "item_count=" + str(len(all_items)),
        "counts=" + str(counts),
        "2026_subjects=" + str(sorted(c["subjects"])),
    ]
    OUT.write_text("\n".join(out), encoding="utf-8")


if __name__ == "__main__":
    main()
