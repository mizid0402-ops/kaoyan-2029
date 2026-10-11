"""Move the superseded section-10 history out of the handoff into the archive.

Run from the repository root with: py -3.12 <this file>
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "交接文档.md"
ARCHIVE = ROOT / "docs" / "archive" / "交接文档-§10历史-至2026-10-08.md"
MARKER = "> **2026-10-01 夜：⑤ 全部提交**"
HEADER = (
    "# 交接文档 §10 历史（2026-10-01 – 2026-10-08，逐字归档）\n"
    "\n"
    "> 从 `交接文档.md` §10 逐字移出（2026-10-09，决策者收口）。内容是当时的进度札记与试运行安排，\n"
    "> 试运行已于 2026-10-08 被用户取消；需要来龙去脉时在这里或 `review/rounds/` 查。\n"
    "\n"
)

with open(DOC, encoding="utf-8", newline="") as handle:
    text = handle.read()
head, marker, tail = text.partition(MARKER)
if not marker:
    raise SystemExit("marker not found; nothing moved")

newline = "\r\n" if "\r\n" in text else "\n"
with open(ARCHIVE, "w", encoding="utf-8", newline="") as handle:
    handle.write(HEADER.replace("\n", newline) + marker + tail)
with open(DOC, "w", encoding="utf-8", newline="") as handle:
    handle.write(head.rstrip(newline) + newline)

print("archived lines:", (marker + tail).count(newline) + 1)
print("handoff now ends at line:", head.count(newline) + 1)
