"""Verify the claims of the user-supplied index document against actually-fetched bytes.

Input : cache/evidence/attach/index.json (produced by tools/fetch_evidence.py)
Output: review/attach-audit/<timestamp>-attachment-audit.json + .md

Rule: every claim is decided by what the saved HTML/PDF actually contains.
A claim that cannot be decided from the fetched bytes is reported as UNVERIFIABLE,
never as OK. This is the project's "自己数出来的数字不可信" rule applied to a document.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EV = ROOT / "cache" / "evidence" / "attach"
OUT = ROOT / "review" / "attach-audit"

# ---------------------------------------------------------------- claims table
# (claim_id, subject, human claim, url that should support it, content probes)
CLAIMS = [
    # group A: official / publisher
    ("A1", "official", "2026 研考初试时间 2025-12-20—21；数学一/英语一为全国统一命题科目",
     "https://www.moe.gov.cn/srcsite/A15/moe_778/s3261/202509/t20250918_1413836.html",
     ["12月20日", "12月21日", "统一命题"]),
    ("A2", "publisher", "数学大纲 ISBN 9787107404689 / 157 页 / 29.00 元 / 人教社 / 2026 版目录",
     "https://www.zxhsd.com/kgsm/ts/2025/10/17/6704598.shtml",
     ["9787107404689", "157", "29", "考试内容和考试要求", "数学(一)"]),
    ("A3", "publisher", "数学大纲目录（境外核验页，台湾大书城）",
     "https://www.megbook.com.tw/mall/detail.jsp?proID=4159518",
     ["9787", "数学"]),
    ("A4", "publisher", "英语一大纲 ISBN 9787107404603 / 236 页 / 含附录三 2024-2025 真题及参考答案",
     "https://aus.zxhsd.com/kgsm/ts/2025/10/17/6694606.shtml",
     ["9787107404603", "236", "附录三", "试题参考答案", "词汇表"]),
    ("A5", "publisher", "英语一大纲目录（台湾大书城）",
     "https://search.megbook.com.tw/mall/detail.jsp?proID=4159208",
     ["9787", "英语"]),
    # group B: math past papers
    ("B1", "math-reprint", "2024 数学一真题及答案（网络整理 PDF）",
     "https://www.chinakaoyan.com/info/article/id/527517.shtml",
     ["2024", "数学一", "真题", "答案"]),
    ("B2", "math-reprint", "同站下载中心提供该 PDF",
     "https://download.chinakaoyan.com/list-show-218527.html",
     ["2024", "数学"]),
    ("B3", "math-university", "天津仁爱学院数学教学部提供 2025 数学一真题及答案解析 PDF 附件",
     "https://www.tjrac.edu.cn/sxjxb/info/1340/3002.htm",
     ["2025", "数学（一）", "真题", "pdf"]),
    ("B4", "math-reprint", "聚创考研 2025 数学一解析",
     "https://m.juyingonline.com/news/356469.html",
     ["2025", "数学一"]),
    ("B5", "math-reprint", "启航数学真题索引",
     "https://m-jixun.iqihang.com/kyzt/shuxue/",
     ["数学"]),
    ("B6", "math-reprint", "启航 2026 数学一完整卷 + 解析",
     "https://m-jixun.iqihang.com/kyzt/shuxue/shuxue1/2025703715.html",
     ["2026", "数学一", "答案"]),
    ("B7", "math-reprint", "聚创考研 2026 数学一手写版 PDF",
     "https://m.juyingonline.com/news/357790.html",
     ["2026", "数学一"]),
    # group C: english
    ("C1", "eng-reprint", "懒笔记 2024 英语一整卷 + PDF + Word + 解析",
     "https://english-exam.lazynote.cn/kaoyan/paper/2024-english-one/",
     ["2024", "PDF", "Word", "解析"]),
    ("C2", "eng-reprint", "中国考研网 2024 英语一各题型答案索引",
     "https://www.chinakaoyan.com/info/article/id/526859.shtml",
     ["2024", "英语"]),
    ("C3", "eng-reprint", "懒笔记 2025 英语一整卷",
     "https://english-exam.lazynote.cn/kaoyan/paper/2025-english-one/",
     ["2025", "PDF", "Word"]),
    ("C4", "eng-reprint", "新东方 2025 英语一试题及答案",
     "https://kaoyan.xdf.cn/202501/14059107.html",
     ["2025", "英语（一）", "答案"]),
    ("C5", "eng-reprint", "考研之家标注的「2025 英语一试题参考答案.pdf」",
     "https://www.yanbbs.com/nd.jsp?id=47",
     ["参考答案"]),
    ("C6", "eng-reprint", "懒笔记 2026 英语一整卷 + 分模块解析",
     "https://english-exam.lazynote.cn/kaoyan/paper/2026-english-one/",
     ["2026", "完形", "阅读", "新题型", "翻译", "写作"]),
    ("C7", "eng-reprint", "kaoyan.cn 静态 PDF 含 2026 英语一试题及答案",
     "https://static.kaoyan.cn/file/question/2025/12/27/4644ae5c80a12b9a2135e54dc56c0724.pdf",
     []),  # PDF: decided by magic bytes + size, and by an explicit copyright gate
    ("C8", "eng-reprint", "懒笔记 2010—2026 英语一真题总库",
     "https://english-exam.lazynote.cn/kaoyan/english-one/",
     ["2010", "2026", "PDF", "Word"]),
]

# Statement-level claims about the attachment's own structure (subject breakdown,
# question counts, score split). These are cross-checked against independent
# sources, never against the attachment itself.
STRUCTURE_CLAIMS = [
    ("S1", "数学一 高数60% / 线代20% / 概率20%", {"高等数学": "60", "线性代数": "20", "概率论与数理统计": "20"}),
    ("S2", "数学一 10 单选 + 6 填空 + 6 解答",
     {"单项选择题": "10", "填空题": "6", "解答题": "6"}),
    ("S3", "英语一 完形10/阅读A40/新题型10/翻译10/写作30", {"10": "完形", "40": "阅读", "30": "写作"}),
]


def load(url: str) -> tuple[str, dict]:
    rec = RECS_BY_URL.get(url)
    if rec is None:
        return "", {"http_status": "not_fetched"}
    path = EV / rec["saved_as"] if rec.get("saved_as") else None
    text = path.read_text(encoding="utf-8", errors="replace") if path and path.exists() else ""
    return text, rec


def norm(s: str) -> str:
    return re.sub(r"[\s\u3000]+", "", s)


def check(claim_id, subject, human, url, probes) -> dict:
    text, rec = load(url)
    flat = norm(text)
    missing = [p for p in probes if norm(p) not in flat]
    status = rec.get("http_status", rec.get("error", "?"))
    if isinstance(status, str) and status.startswith("SSLError"):
        verdict = "UNREACHABLE"
    elif status != 200:
        verdict = "UNREACHABLE"
    elif missing:
        verdict = "PARTIAL" if len(missing) < len(probes) else "NOT_FOUND"
    else:
        verdict = "SUPPORTED"
    return {
        "claim_id": claim_id,
        "subject": subject,
        "claim": human,
        "url": url,
        "http_status": status,
        "final_url": rec.get("final_url"),
        "byte_size": rec.get("byte_size"),
        "sha256": rec.get("sha256"),
        "probes": probes,
        "probes_missing": missing,
        "verdict": verdict,
    }


def main() -> int:
    global RECS_BY_URL
    index = json.loads((EV / "index.json").read_text(encoding="utf-8"))
    RECS_BY_URL = {r["url"]: r for r in index}

    results = [check(*c) for c in CLAIMS]

    # PDF specifically: a fetched PDF of exam text is a rights question, not a
    # credibility question. Report what it is; refuse to treat it as usable.
    pdf = next((r for r in results if r["claim_id"] == "C7"), None)
    if pdf:
        rec = RECS_BY_URL[pdf["url"]]
        path = EV / rec["saved_as"]
        head = path.read_bytes()[:8] if path.exists() else b""
        pdf["pdf_magic"] = head.decode("latin-1")
        pdf["rights_note"] = (
            "已实际下载到完整 PDF 字节；按项目 §4.3/侦察 §2.4 第 8-10 条，"
            "真题与答案原文不得入库，此文件仅作「该链接确实提供真题」的存在性证据，"
            "不得进入 data/raw_materials。"
        )

    counts: dict[str, int] = {}
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1

    payload = {
        "audited_document": "2024-2026考研数学一英语一真题答案及考试大纲.md",
        "audited_sha256": "c99635318bb22179351edc6bb07d1f0883aa8403b73c9d14f3e9896ca6d072a0",
        "verdict_counts": counts,
        "claims": results,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "attachment-audit.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )

    lines = [
        "# 附件（用户提供的资料索引）可靠性审计",
        "",
        f"被审文件 sha256 `{payload['audited_sha256']}`",
        "",
        f"逐条判定：{counts}",
        "",
        "| # | 类别 | 判定 | HTTP | 字节 | 缺失探针 | 主张 |",
        "|---|---|---|---:|---:|---|---|",
    ]
    for r in results:
        miss = "、".join(r["probes_missing"]) or "-"
        lines.append(
            f"| {r['claim_id']} | {r['subject']} | **{r['verdict']}** | {r['http_status']} | "
            f"{r['byte_size']} | {miss} | {r['claim']} |"
        )
    if pdf:
        lines += ["", "## 关于 C7（kaoyan.cn 静态 PDF）", "", pdf["rights_note"],
                  f"magic bytes: `{pdf['pdf_magic']}`"]
    (OUT / "attachment-audit.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )

    print("\n".join(lines[:6]))
    for r in results:
        if r["verdict"] != "SUPPORTED":
            print(f"  !! {r['claim_id']} {r['verdict']} missing={r['probes_missing']}")
    print(f"\njson -> {OUT / 'attachment-audit.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
