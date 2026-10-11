"""Register the round-2 sources into the material ledger, honestly and atomically.

What this does (and deliberately does not do):

  1. Copies the *transcript* pages the audit relies on into `data/raw_materials/`
     so their bytes are pinned locally, and records the real SHA-256.
  2. Appends ledger entries for: the user-supplied attachment (as an index, NOT as
     an authority), two independent math-outline transcripts, one English-outline
     transcript, and three link-only exam-material references.
  3. Amends the two existing 2026 outline entries' notes with what this round
     actually verified.
  4. Refuses to mark anything `may_define_syllabus`-capable that is not official.

Why transcripts are registered as `trusted_reprint` and not `official`:
    They are third-party transcriptions of an official publication. A transcription
    error changes what the syllabus says, which is precisely the failure mode the
    tier system exists to catch. So the tree built from them inherits a stated
    "must be re-checked against the printed 2028 outline" caveat.

Existing entries are preserved byte-for-byte except for the `notes:` line of the
two entries named in AMEND, whose text is replaced wholesale.

Usage:
    py -3.12 tools/migrations/register_round2_sources.py [--check]
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "data" / "materials.yaml"
TRANSCRIPT_DIR = ROOT / "data" / "raw_materials" / "transcripts"
RETRIEVED_ON = "'2026-09-13'"
RETRIEVED_AT = "'2026-09-13T00:00:00+08:00'"
ACTOR = "dsh-round2"

# (source file from cache, destination filename inside transcripts/)
COPIES: list[tuple[str, str, str]] = [
    ("cache/evidence/cand2/kaoyan_eol_cn_kao_shi_da_gang_shuxue_202109_t20210916_2155978_shtml.html",
     "eol_cn/math_outline_2022_fulltext.html",
     "data/raw_materials/transcripts/eol_cn/math_outline_2022_fulltext.html"),
    ("cache/evidence/cand4/edu_newdu_com_Master_Math_Guide_202511_4818166_html.html",
     "newdu_com/math1_outline_2026_fulltext.html",
     "data/raw_materials/transcripts/newdu_com/math1_outline_2026_fulltext.html"),
    ("cache/evidence/cand/kaoyan_eol_cn_kao_shi_da_gang_yingyu_202109_t20210916_2155864_shtml.html",
     "eol_cn/eng1_outline_2022_fulltext.html",
     "data/raw_materials/transcripts/eol_cn/eng1_outline_2022_fulltext.html"),
]

NEW_ENTRIES: list[str] = [
    # ------------------------------------------------------------------ attachment
    """- resource_id: user-index-math1-eng1-2026
  title: 2024-2026 考研数学一英语一真题答案及考试大纲（用户提供的第三方资料索引）
  material_kind: reference_notes
  subjects:
  - math1
  - eng1
  acquisition: user_provided
  rights:
    status: unknown
    licence: null
    licence_url: null
    may_store: true
    may_display: false
    may_redistribute: false
    may_be_structured: false
  storage:
    mode: local_file
    path: review/attach-audit/attachment-copy.md
    sha256: {attach_sha}
    byte_size: {attach_size}
    url: null
    retrieved_on: {on}
  provenance:
    source_url: null
    source_tier: trusted_reprint
    publisher: 未署名（用户提供的第三方整理稿；整理者与原始出处均未标注）
    published_on: null
    isbn: null
    retrieved_at: {at}
    retrieved_by: {actor}
    archive_url: null
  review_index: false
  review_status: verified
  notes: '**这是目录，不是考纲。** source_tier=trusted_reprint，may_define_syllabus 为 false：
    它既非官方发布也非官方出版社出品，是一份二手整理。可用途：资料获取线索、链接白名单、
    与官方书目页交叉核对。**不得作为任何知识树节点的来源**，也不得据它登记试卷结构
    （其数学一题型写"解答题 6 题"，而 2022 版官方大纲原文为 7 题，已发现错误）。

    本轮实测：20 条 URL 中 18 条有字节支持；1 条为 102 字节空壳（台湾大书城数学页）；
    1 条 SSL 自签证书不可达（yanbbs.com）。明细见 review/attach-audit/可靠性审查结论.md
    与 review/attach-audit/attachment-audit.json。

    rights.status=unknown 是刻意的：这份整理稿本身的权利状态无从判定，而"没说"不等于"可以用"。
    may_store=true 因为它不是出版物正文，且必须留存才能核对 sha256。'
  history:
  - at: {at}
    action: registered
    actor: {actor}
    detail: 用户提供；经主控字节级审计 + 两个外部模型独立审查后登记为线索级来源，明确不可定义考纲
""",
    # --------------------------------------------------- math transcript (2022)
    """- resource_id: math1-outline-transcript-eol-2022
  title: 2022 年全国硕士研究生招生考试数学（一）考试大纲（第三方全文转录，中国教育在线）
  material_kind: official_syllabus
  subjects:
  - math1
  acquisition: public_download
  rights:
    status: official_public
    licence: 中国教育在线（kaoyan.eol.cn）转载的官方大纲全文；本系统只取"考试形式与试卷结构"与
      "考试内容和考试要求"的**章节标题与要求条目**，不复制书稿正文段落。
    licence_url: https://kaoyan.eol.cn/kao_shi_da_gang/shuxue/202109/t20210916_2155978.shtml
    may_store: true
    may_display: true
    may_redistribute: false
    may_be_structured: true
  storage:
    mode: local_file
    path: data/raw_materials/transcripts/eol_cn/math_outline_2022_fulltext.html
    sha256: {eol_sha}
    byte_size: {eol_size}
    url: https://kaoyan.eol.cn/kao_shi_da_gang/shuxue/202109/t20210916_2155978.shtml
    retrieved_on: {on}
  provenance:
    source_url: https://kaoyan.eol.cn/kao_shi_da_gang/shuxue/202109/t20210916_2155978.shtml
    source_tier: trusted_reprint
    publisher: 中国教育在线（转录教育部教育考试院《2022 年数学考试大纲》）
    published_on: '2021-09-16'
    isbn: 978-7-04-056666-6
    retrieved_at: {at}
    retrieved_by: {actor}
    archive_url: null
  review_index: false
  review_status: verified
  notes: '⚠️ source_tier=trusted_reprint → **may_define_syllabus 为 false**。转录本身可能出错，
    因此由此建立的数学一知识树必须标注"须以纸质官方大纲复核"。

    实测结构：高数 8 章 + 线代 6 章 + 概率论 8 章 = 22 章；「考试要求」编号条目 121 条。
    "考试形式与试卷结构"为：满分 150 / 180 分钟；单选 10 题×5 分、填空 6 题×5 分、
    解答题（含证明题）**7 题**共 70 分 —— 该数字与用户提供的索引文档（写 6 题）冲突，以本文件为准。

    已知转录瑕疵：正文中的数学公式被替换为 zhihu 公式图片链接（<img ... zhihu.com/equation>），
    因此公式本身不在文本层；建节点时不得凭领域知识补写公式。'
  history:
  - at: {at}
    action: registered
    actor: {actor}
    detail: 数学一知识树的结构来源之一（2022 版全文转录），与 2026 版转录交叉验证
""",
    # --------------------------------------------------- math transcript (2026)
    """- resource_id: math1-outline-transcript-newdu-2026
  title: 2026 年考研数学（一）考试大纲【原文】（第三方全文转录，新都网教育）
  material_kind: official_syllabus
  subjects:
  - math1
  acquisition: public_download
  rights:
    status: official_public
    licence: 同 math1-outline-transcript-eol-2022：只取章节标题与要求条目。
    licence_url: http://edu.newdu.com/Master/Math/Guide/202511/4818166.html
    may_store: true
    may_display: true
    may_redistribute: false
    may_be_structured: true
  storage:
    mode: local_file
    path: data/raw_materials/transcripts/newdu_com/math1_outline_2026_fulltext.html
    sha256: {newdu_sha}
    byte_size: {newdu_size}
    url: http://edu.newdu.com/Master/Math/Guide/202511/4818166.html
    retrieved_on: {on}
  provenance:
    source_url: http://edu.newdu.com/Master/Math/Guide/202511/4818166.html
    source_tier: trusted_reprint
    publisher: 新都网教育（转录教育部教育考试院《2026 年数学考试大纲》）
    published_on: '2025-11-01'
    isbn: 978-7-107-40468-9
    retrieved_at: {at}
    retrieved_by: {actor}
    archive_url: null
  review_index: false
  review_status: verified
  notes: '⚠️ source_tier=trusted_reprint → **may_define_syllabus 为 false**。

    实测结构与 2022 版转录**章节层级一致**（高数 8 + 线代 6 + 概率论 8 = 22 章），
    但「考试要求」编号条目为 120 条（2022 版 121 条）—— 差异属转录编号断裂（例如
    "五、大数定律和中心极限定理"被 HTML 断成 "五" + "、大数定律和中心极限定理"），
    不足以证明考纲内容变化，但**足以证明"任何单一转录都不可单独采信"**。

    已知转录瑕疵（比 2022 版更差）："相合性"误作"柑合性"；"伯努利"误作"伯努"；
    "列维-林德伯格定理"括号缺失。这些是转录/OCR 错误，建节点时须与另一来源比对，
    不一致处不得擅自择一。'
  history:
  - at: {at}
    action: registered
    actor: {actor}
    detail: 数学一知识树的结构来源之一（2026 版全文转录），与 2022 版交叉验证
""",
    # --------------------------------------------------- eng1 transcript (2022)
    """- resource_id: eng1-outline-transcript-eol-2022
  title: 2022 年全国硕士研究生招生考试英语（一）考试大纲（第三方全文转录，中国教育在线）
  material_kind: official_syllabus
  subjects:
  - eng1
  acquisition: public_download
  rights:
    status: official_public
    licence: 中国教育在线转载的官方大纲全文；只取考试形式、试卷结构与考查目标条目的标题级信息。
    licence_url: https://kaoyan.eol.cn/kao_shi_da_gang/yingyu/202109/t20210916_2155864.shtml
    may_store: true
    may_display: true
    may_redistribute: false
    may_be_structured: true
  storage:
    mode: local_file
    path: data/raw_materials/transcripts/eol_cn/eng1_outline_2022_fulltext.html
    sha256: {engeol_sha}
    byte_size: {engeol_size}
    url: https://kaoyan.eol.cn/kao_shi_da_gang/yingyu/202109/t20210916_2155864.shtml
    retrieved_on: {on}
  provenance:
    source_url: https://kaoyan.eol.cn/kao_shi_da_gang/yingyu/202109/t20210916_2155864.shtml
    source_tier: trusted_reprint
    publisher: 中国教育在线（转录教育部教育考试院《2022 年英语（一）考试大纲》）
    published_on: '2021-09-16'
    isbn: null
    retrieved_at: {at}
    retrieved_by: {actor}
    archive_url: null
  review_index: false
  review_status: verified
  notes: '⚠️ source_tier=trusted_reprint → **may_define_syllabus 为 false**。

    实测内容：I 考试性质 / II 考查目标（语言知识：语法、词汇 5500 左右；语言技能：阅读、写作）/
    III 考试形式与试卷结构（笔试、180 分钟、满分 100）/ IV 题型示例与参考答案。
    试卷结构实测为四部分共 48 题：英语知识运用（20 小题×0.5 分=10 分）、阅读理解
    （A 节 20 题×2 分=40 分；B 节新题型 5 小题；C 节英译汉 5 小题）共 60 分、
    写作（A 应用文 10 分 + B 短文 160-200 词 20 分）共 30 分。

    与用户索引文档的差异：索引文档写"阅读理解 A 40 / 新题型 10 / 翻译 10"，
    与本转录一致；但索引文档未说明其数字来源，故仍按本文件登记。'
  history:
  - at: {at}
    action: registered
    actor: {actor}
    detail: 英语一结构树的来源（2022 版全文转录）
""",
    # --------------------------------------------------- link-only references
    """- resource_id: ref-exam-material-links-2026
  title: 2024-2026 数学一 / 英语一 真题与解析的公开链接集合（仅链接，不持有正文）
  material_kind: past_exam_paper
  subjects:
  - math1
  - eng1
  acquisition: public_download
  rights:
    status: officially_published
    licence: null
    licence_url: null
    may_store: false
    may_display: false
    may_redistribute: false
    may_be_structured: false
  storage:
    mode: remote_reference
    path: null
    sha256: null
    byte_size: null
    url: https://static.kaoyan.cn/file/question/2025/12/27/4644ae5c80a12b9a2135e54dc56c0724.pdf
    retrieved_on: {on}
  provenance:
    source_url: https://static.kaoyan.cn/file/question/2025/12/27/4644ae5c80a12b9a2135e54dc56c0724.pdf
    source_tier: trusted_reprint
    publisher: null
    published_on: null
    isbn: null
    retrieved_at: {at}
    retrieved_by: {actor}
    archive_url: null
  review_index: false
  review_status: verified
  notes: '**只登记链接与元信息，不持有任何试卷/答案正文。** 依据 docs/资料可得性侦察.md §2.4 第 8-10 条：
    不登记真题题干原文、不登记参考答案原文、不批量抓取。

    已实测：URL 返回 HTTP 200、Content-Type application/pdf、903877 字节、
    sha256 d33c331413174826c333437b46e6819ab8b6da2435da1300d670d701fbac84c4。
    该 PDF 据页面标注含 2026 英语（一）试题及答案。**实测过程中一个外部审查 agent 曾自行下载并
    解析了它，把试题与答案原文写进了日志；该日志已被删除。** 这是本轮明确的边界事故，记录在此。

    同类链接（懒笔记 2010-2026 共 17 套、启航/聚创 2026 数学一等）见
    review/attach-audit/attachment-audit.json，一律只作链接，不入库。'
  history:
  - at: {at}
    action: registered
    actor: {actor}
    detail: 附件所引真题链接的存在性证据；按权利边界不持有正文
""",
]

AMEND_NOTE_ANCHORS = {
    "eng1-outline-pubinfo-2026": (
        "review_status: verified\n  notes: ",
        """review_status: verified
  notes: '仅含出版元信息与目录层级。**ISBN 冲突已于 2026-09-13 解决**：
    978-7-107-40460-3 = 《2026 年…英语（一）考试大纲（非英语专业）》（本条目所指，236 页，人教社）；
    978-7-107-40461-0 = 《英语（一）（二）考试分析（非英语专业）2026 年版》（另一册，见 eng1-exam-analysis-2026）。
    两者不是同一本书，侦察文档第 3 项未核实可关闭。

    目录（来自人教社体系书目页，2 个独立书商页一致）：Ⅰ 考试性质 / Ⅱ 考查目标 /
    Ⅲ 考试形式、考试内容与试卷结构 / Ⅳ 题型示例及参考答案 / 附录一 词汇表（含部分国家地区名称、
    大洲名大洋名）/ 附录二 常用前缀和后缀、常见缩写词 / 附录三 2024 与 2025 英语（一）试题及试题参考答案。
    → 侦察文档第 4 项未核实（"附录是否含真题"）可关闭：**含**。

    仍未核实：定价；以及"英语一是否有独立公开的官方标准答案文件"（倾向无）。'
"""
    ),
    "math1-outline-pubinfo-2026": (
        "review_status: verified\n  notes: ",
        """review_status: verified
  notes: '仅含出版元信息与目录层级描述，**不含大纲正文与章节目录正文**。
    2026-09-13 由浙江省新华书店书目页独立复核：ISBN 9787107404689、157 页、定价 29.00 元、
    出版 2025-09-01 第 1 版，且**官方目录逐字一致**：Ⅰ 考试性质 / Ⅱ 考查目标 /
    Ⅲ 试卷分类及使用专业 / Ⅳ 考试形式和试卷结构 / Ⅴ 考试内容和考试要求（数学一/二/三）/
    Ⅵ 题型示例及参考答案；附录含 2024、2025 试题及参考答案。

    ⚠️ 该官方目录**只到「数学(一)」这一级**，不含高等数学/线性代数/概率论之下的章节标题。
    因此它只能作**分卷与结构锚点**，不足以构建知识树。'
"""
    ),
}


def sha256_of(path: Path) -> tuple[str, int]:
    raw = path.read_bytes()
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="report planned changes only")
    args = ap.parse_args()

    values: dict[str, str] = {}
    for src_rel, _dst_rel, dest_rel in COPIES:
        src = ROOT / src_rel
        if not src.is_file():
            raise SystemExit(f"missing cache file: {src}")
        digest, size = sha256_of(src)
        key = {
            "math_outline_2022_fulltext.html": "eol",
            "math1_outline_2026_fulltext.html": "newdu",
            "eng1_outline_2022_fulltext.html": "engeol",
        }[Path(dest_rel).name]
        values[f"{key}_sha"] = digest
        values[f"{key}_size"] = str(size)

    # attachment copy: pin the user's document inside the repo so its hash is checkable
    attach_src = Path(
        r"C:\Users\Lenovo\.dsh\attachments\v1\files\c9"
        r"\c99635318bb22179351edc6bb07d1f0883aa8403b73c9d14f3e9896ca6d072a0"
        r"\2024-2026考研数学一英语一真题答案及考试大纲.md"
    )
    attach_dst = ROOT / "review" / "attach-audit" / "attachment-copy.md"
    if not attach_src.is_file():
        raise SystemExit(f"attachment not readable: {attach_src}")
    digest, size = sha256_of(attach_src)
    if digest != "c99635318bb22179351edc6bb07d1f0883aa8403b73c9d14f3e9896ca6d072a0":
        raise SystemExit(f"attachment sha256 changed: {digest}")
    values["attach_sha"] = digest
    values["attach_size"] = str(size)

    values.update({"on": RETRIEVED_ON, "at": RETRIEVED_AT, "actor": ACTOR})

    print("planned values:")
    for k in sorted(values):
        print(f"  {k} = {values[k]}")

    if args.check:
        print("\n--check: no files written")
        return 0

    # 1) copy transcripts + attachment
    for src_rel, _dst_rel, dest_rel in COPIES:
        dest = ROOT / dest_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / src_rel, dest)
        d, s = sha256_of(dest)
        print(f"copied {dest_rel} ({s} bytes, {d[:16]})")
    attach_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(attach_src, attach_dst)
    d, s = sha256_of(attach_dst)
    print(f"copied review/attach-audit/attachment-copy.md ({s} bytes, {d[:16]})")

    # 2) append new entries
    text = LEDGER.read_text(encoding="utf-8")
    if "user-index-math1-eng1-2026" in text:
        raise SystemExit("ledger already contains the new entries; refusing to double-register")
    if not text.endswith("\n"):
        text += "\n"
    for template in NEW_ENTRIES:
        text += template.format(**values)

    # 3) amend the two existing notes
    for resource_id, (anchor, replacement) in AMEND_NOTE_ANCHORS.items():
        start = text.index(f"- resource_id: {resource_id}\n")
        nxt = text.find("\n- resource_id: ", start + 1)
        end = nxt + 1 if nxt != -1 else len(text)
        block = text[start:end]
        if anchor not in block:
            raise SystemExit(f"anchor not found inside {resource_id}")
        head = block[: block.index(anchor)]
        tail = block[block.index("  history:"):]
        text = text[:start] + head + replacement + tail + text[end:]

    LEDGER.write_text(text, encoding="utf-8", newline="\n")
    print(f"\nledger written: {LEDGER} ({LEDGER.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
