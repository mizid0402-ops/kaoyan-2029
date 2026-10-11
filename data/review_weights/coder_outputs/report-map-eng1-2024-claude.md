# 2024 年英语一 52 题 → 考纲节点映射报告（coder: claude）

## 数据来源

- 题干 PDF：`claude2\dl\bv_e1_2024.pdf`（14 页，pypdf 直接抽取文本层，34235 字符）、`claude2\dl\lazy_e1_2024.pdf`（12 页，同法抽取，28099 字符）。两份 PDF 均带完整文本层，无需渲染读图。
- 节点表：`mapping\tasks\eng1_2024_nodes.tsv`，24 个节点。
- 节点表 sha256（按 LF 换行归一化计算，与任务书给定值一致）：
  `86b908b2d0bc5331bf0771de29790e69e31fa7efed361e9f09d8da28889f472d`
  （注：文件本身为 CRLF 换行，对原始字节直接算得 `ba119084…` 与任务书不符；替换 `\r\n`→`\n` 后重算即得到任务书给定的哈希，说明内容一致，仅换行符表示不同，已在 JSON `meta.node_table_sha256` 中记录任务书给定值。）

## 结构核对

两份 PDF 内容一致，试卷结构与官方英语一标准格式完全吻合：

| 题号范围 | 试卷位置 | 节点 |
|---|---|---|
| 1–20 | Section I Use of English（单篇完形填空，20空） | `eng1.paper.part1` |
| 21–40 | Section II Reading Comprehension Part A（四篇短文，每篇5题单选） | `eng1.paper.part2.a` |
| 41–45 | Part B（新题型：多人评论 + 7选5配对陈述句） | `eng1.paper.part2.b` |
| 46–50 | Part C（英译汉，5句划线句子汉译） | `eng1.paper.part2.c`（+ `eng1.paper.part3.note`） |
| 51 | Section III Writing Part A（应用文：回复留学生邮件） | `eng1.paper.part4.a` |
| 52 | Section III Writing Part B（图文/图表大作文） | `eng1.paper.part4.b` |

依据均来自 PDF 中明确标注的 Section/Part 小标题（如 "Section I Use of English"、"Part A"、"Part B"、"Part C"、"Section III Writing"、"Part A"、"Part B"），以及题目形式特征（字数要求、题型说明），未依赖题干具体内容语义猜测。

## 特殊说明：46–50 的双节点

节点表中除 `eng1.paper.part2.c`（阅读理解 C 节 英译汉）外，还单列了 `eng1.paper.part3`（第三部分 翻译）及其子项 `eng1.paper.part3.note`（"英译汉作为阅读理解的一部分"）。英语一的翻译题在试卷上实际位置是 Section II Part C，并非独立成"第三部分"；`part3.note` 的文字正是在解释这一点。因此我将 46–50 的 `primary_node` 定为更细、更贴合试卷实际位置的 `eng1.paper.part2.c`，同时把 `eng1.paper.part3.note` 作为次要节点一并列出，避免遗漏节点表中专门为此设置的说明性条目。

## 置信度分布

本次映射任务的节点表本质是"试卷结构/考纲目录"节点（Section/Part 层级），并非语法词汇等内容知识点；52 题在 PDF 中均有清晰的 Section/Part 标题分隔，题号范围与官方标准格式（20+20+5+5+1+1=52）严丝合缝，无歧义或超纲情况，因此 52 题全部判定为 `confidence: high`，无 `medium`/`low`，无 `null`。

## 输出文件

- JSON：`mapping\map-eng1-2024-claude.json`
- 报告：`mapping\report-map-eng1-2024-claude.md`（本文件）
