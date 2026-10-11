# 任务：独立对抗审查 —— 第三方资料索引文档能否作为本项目证据

你是一个独立审查者。**你的结论由你自己从字节里得出，不得采信本文档中的任何"已完成/已验证"字样。**
你被明确授权、并被要求：**设法推翻下面的结论**。

## 0. 硬性边界（违反即本轮作废）

- **你只能创建/修改一个文件**：`F:\workspace\kaoyan-ai-system\review\rounds\attach-audit-OUTSLOT.md`
  （实际文件名见本文件末尾「输出」一节）。**其它任何文件一律不得创建、修改、删除。**
- **禁止运行任何会写文件的命令**（禁止 `tools/fetch_evidence.py`、禁止 `tools/audit_attachment.py`、
  禁止 curl/wget 下载、禁止 git 操作）。你可以使用 Read / Glob / Grep，以及只读的 shell 命令
  （读取文件、计算哈希、运行 python 做纯粹的计算）。
- **禁止联网**获取新页面。你手上的证据就是本节列出的本地文件。
- 如果你认为某个现有文件必须修改，**不要改**，在报告里写出最小 diff 建议。
- 输出用中文。

## 1. 背景

用户提供了一份第三方整理的资料索引文档（下称**附件**），要求"先审查可靠性，可以则作为证据纳入使用"。
项目位于 `F:\workspace\kaoyan-ai-system`，其宪法是 `docs/评审结论与实施契约.md`，
资料规则实现在 `ky/ledger/material.py`。

**先读这三份**（按顺序）：

1. `F:\workspace\kaoyan-ai-system\review\attach-audit\context.md` —— 共享事实基线（主控已核实项 + 证据哈希 + 项目规则摘录）
2. `F:\workspace\kaoyan-ai-system\docs\评审结论与实施契约.md` —— 项目宪法（特别是 §4.2、§4.3）
3. `C:\Users\Lenovo\.dsh\attachments\v1\files\c9\c99635318bb22179351edc6bb07d1f0883aa8403b73c9d14f3e9896ca6d072a0\2024-2026考研数学一英语一真题答案及考试大纲.md` —— **被审对象（原文，595 行）**

然后读项目的资料规则源码，确认 `source_tier` 五档与 `may_define_syllabus()` 的确切语义：

4. `F:\workspace\kaoyan-ai-system\ky\ledger\material.py`（约第 55–105 行、第 430–460 行）
5. `F:\workspace\kaoyan-ai-system\data\materials.yaml`（现有台账 18 条，看它们怎么填 `source_tier` 与 `rights`）

## 2. 证据文件（位于 `F:\workspace\kaoyan-ai-system\cache\evidence\attach\`）

这些是从附件所列 URL **实际抓取**下来的页面（已解码为 UTF-8）。文件名与哈希见 `context.md` §1.2。
`index.json` 里有每条抓取的 HTTP 状态、最终 URL、Content-Type、字节数、sha256。

**你必须自己打开这些 HTML 文件，而不是相信 context.md 的摘要。** 建议每读一个文件先确认字节数/哈希与
`index.json` 一致，不一致要报告。

## 3. 你要回答的问题（四个交付项，缺一不可）

### (1) 可靠性裁定（核心）
按项目规则，这份附件落到 `source_tier` 的哪一档？**它能否 `may_define_syllabus()`？**
必须给出：档位 → 依据某条规则 → 后果。不要给模糊结论（"基本可信"不算结论）。

### (2) 逐条证伪（20 条主张，一条不许跳）
附件原文里成文的事实主张共 20 条，列在下面。每条你要：

- 从证据 HTML 的**字节**里找支持或反证（给出文件名 + 行号 + 你实际看到的原文片段）；
- 给出你自己的判定：`SUPPORTED` / `PARTIAL` / `NOT_FOUND` / `UNREACHABLE` / `CONTRADICTED`；
- **寻找反例**：有没有哪条主张在页面上其实说的是别的事？（例如"下载中心页"其实只是一个列表壳页；
  "PDF 附件"其实不存在；"答案"其实只是考生回忆版）

主张清单（编号与 `tools/audit_attachment.py` 一致；该脚本的自动化判定仅供参考，**不得作为你的结论**）：

| # | 主张 | 对应 URL | 证据文件 |
|---|---|---|---|
| A1 | 管理规定页：2026 初试 2025-12-20—21；数学一/英语一为全国统一命题科目 | moe.gov.cn `.../t20250918_1413836.html` | `www_moe_gov_cn_...html` |
| A2 | 数学大纲 ISBN 9787107404689 / 157 页 / 29 元 / 官方目录 | `www.zxhsd.com/kgsm/ts/2025/10/17/6704598.shtml` | `www_zxhsd_com_...html` |
| A3 | 台湾大书城数学大纲核验页 | `www.megbook.com.tw/mall/detail.jsp?proID=4159518` | `www_megbook_com_tw_..._4159518.html`（103 字节） |
| A4 | 英语一大纲 ISBN 9787107404603 / 236 页 / 附录三含 2024-2025 真题及参考答案 / 附录一词汇表 | `aus.zxhsd.com/.../6694606.shtml` | `aus_zxhsd_com_...html` |
| A5 | 台湾大书城英语一大纲页 | `search.megbook.com.tw/mall/detail.jsp?proID=4159208` | `search_megbook_com_tw_...html` |
| B1 | 中国考研网 2024 数学一真题及答案（网络整理 PDF） | `chinakaoyan.com/info/article/id/527517.shtml` | `www_chinakaoyan_com_..._527517_...html` |
| B2 | 同站下载中心提供该 PDF | `download.chinakaoyan.com/list-show-218527.html` | `download_chinakaoyan_com_...html` |
| B3 | 天津仁爱学院数学教学部提供 2025 数学一真题及答案解析 PDF | `tjrac.edu.cn/sxjxb/info/1340/3002.htm` | `www_tjrac_edu_cn_...html` |
| B4 | 聚创考研 2025 数学一解析页 | `m.juyingonline.com/news/356469.html` | `m_juyingonline_com_news_356469_html.html` |
| B5 | 启航数学真题索引 | `m-jixun.iqihang.com/kyzt/shuxue/` | `m_jixun_iqihang_com_kyzt_shuxue.html` |
| B6 | 启航 2026 数学一完整卷 + 解析 | `m-jixun.iqihang.com/kyzt/shuxue/shuxue1/2025703715.html` | `m_jixun_iqihang_com_..._2025703715_html.html` |
| B7 | 聚创考研 2026 数学一手写版 PDF | `m.juyingonline.com/news/357790.html` | `m_juyingonline_com_news_357790_html.html` |
| C1 | 懒笔记 2024 英语一整卷 + PDF/Word/解析 | `english-exam.lazynote.cn/kaoyan/paper/2024-english-one/` | `english_exam_..._2024_...html` |
| C2 | 中国考研网 2024 英语一各题型答案索引 | `chinakaoyan.com/info/article/id/526859.shtml` | `www_chinakaoyan_com_..._526859_...html` |
| C3 | 懒笔记 2025 英语一整卷 | `english-exam.lazynote.cn/kaoyan/paper/2025-english-one/` | `english_exam_..._2025_...html` |
| C4 | 新东方 2025 英语一试题及答案 | `kaoyan.xdf.cn/202501/14059107.html` | `kaoyan_xdf_cn_...html` |
| C5 | 考研之家标注《2025 英语一试题参考答案.pdf》 | `www.yanbbs.com/nd.jsp?id=47` | **无**（抓取失败，SSL 自签证书） |
| C6 | 懒笔记 2026 英语一整卷 + 分模块解析 | `english-exam.lazynote.cn/kaoyan/paper/2026-english-one/` | `english_exam_..._2026_...html` |
| C7 | kaoyan.cn 静态 PDF 含 2026 英语一试题及答案 | `static.kaoyan.cn/file/question/2025/12/27/4644ae5c...pdf` | `static_kaoyan_cn_..._pdf.bin`（903877 字节） |
| C8 | 懒笔记 2010—2026 英语一总库 | `english-exam.lazynote.cn/kaoyan/english-one/` | `english_exam_..._english_one.html` |

对 **C7** 额外要求：核对它**是不是真 PDF**（magic bytes）、**是不是真含 2026 英语一试题**（可用
`py -3.12` 加 pypdf 试试能否提取文本；若不能，如实说"无法判定内容"）。然后按项目侦察文档
`docs/资料可得性侦察.md` §2.4 第 8–10 条判定：**这个文件能不能进 `data/raw_materials/`？**
给出规则依据（哪一条、为什么）。

对 **B3** 额外要求：它被附件归为「高校官网」，按规则 `university` 档**可以定义考纲**。
请核对：该页是否真的发布在高校官网域（`.edu.cn`）？它提供的是**真题与答案**，还是**教学部自己的解析**？
如果是后者，"可定义考纲"这个推论是否成立？（提示：`may_define_syllabus()` 管的是"考纲内容"，
不是"任何资料"。）

### (3) 附件自身的逻辑/事实错误清单
逐条挑出附件里**站不住的具体句子**，每条给：原文行号 → 错在哪 → 反证在哪。
特别检查这几处（不限于此）：

- 附件 §1.2 与 §3.2 的试卷结构与分值（数学一 10 单选/6 填空/6 解答/150 分；英语一 完形10/阅读A40/新题型10/翻译10/写作30）
  ——证据 HTML 里**有没有**这些数字？如果没有，附件是从哪来的？这属于什么性质的问题？
- 附件 §6 与 §8 的"推荐下载顺序"里把**官方大纲附录**列为 2024/2025 真题的"最权威"来源，但同时也给出网络整理版；
  这个排序对本项目是否成立（考虑：本项目**不得登记题干与答案原文**）？
- 附件 §9 的「核心来源汇总」是否覆盖了它正文引用的全部 URL？（自己数，给数字和计数方法）
- 附件声明的"整理日期 2026-09-13"与页面内容的时效性是否自洽（例如 2026 年考研初试在 2025-12-21 结束，
  2026 英语一/数学一的"真题"在 2026-09 是否已存在）？

### (4) 显式不确定清单
标题固定为「## 我不确定的地方」。列出你无法从字节里判定的每一件事。
**报告零不确定 = 视为未完成审查。** 诚实报告"我无法核实 X"是有效结果。

## 4. 已知的失败模式（本项目真实踩过，逐条自查）

- **"测试全绿 ≠ 验收通过"**：本项目已有四次"测试/自查全绿但仍有重大缺陷"。
- **"我自己数出来的数字不可信"**：本项目出现过用正则数节点漏掉整层 226 个条目。
  **你的任何计数都必须给方法，并且用第二种独立方法复核。**
- **"结论方向对，不代表引用的数字对"**：本项目出现过三方对同一反例给出三个数字，只有一个对。
  **你引用的任何数字必须现跑或现查，并给命令/行号。**
- 审查者自己改坏文件不还原：**你被禁止修改任何文件**（除你的输出文件）。

## 5. 输出

写入（**仅此一个文件**）：`F:\workspace\kaoyan-ai-system\review\rounds\attach-audit-OUTSLOT.md`

结构：

```markdown
# 附件可靠性独立审查（OUTSLOT）

## 0. 我实际做了什么（命令 + 结果摘要）
## 1. 裁定：source_tier = ?  / may_define_syllabus = ?
## 2. 逐条证伪表（20 条）
## 3. 附件自身的错误清单
## 4. 对项目下一步的直接影响（哪些可以用、哪些不能用、缺什么）
## 5. 我不确定的地方
## 6. 我实际修改过的文件（如果没有，写"无"）
```

报告要**直接、可验证、不客套**。对每条结论写清它是"我验证过的"还是"我认为的"。
