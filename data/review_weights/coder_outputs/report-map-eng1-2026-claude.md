# 2026 年英语一（52题）知识树映射报告 — coder: claude

## 结论摘要

- entries：52 条，number 1..52 无缺无重（已用脚本 assert 校验）。
- confidence 分布：high 52 / medium 0 / low 0。
- null（疑似考纲外）：0 条。
- 输出文件：`map-eng1-2026-claude.json`

## 数据来源

- 题干来源（只读）：
  - `claude2\dl\bv_e1_2026.pdf`（对应文本层 `bv_e1_2026.txt`）
  - `claude2\dl\lazy_e1_2026.pdf`（对应文本层 `lazy_e1_2026.txt`）
- 两份文本层内容互相印证（题目、选项、段落顺序一致），均含可直接提取的文本层，未使用 `pypdfium2` 渲染目视识别。
- 节点表：`mapping\tasks\eng1_2026_nodes.tsv`，24 个节点。

## 节点表 SHA256 核对异常（需人工关注）

任务书声明的节点表 sha256 为：
`86b908b2d0bc5331bf0771de29790e69e31fa7efed361e9f09d8da28889f472d`

但用 `py -3.12` 对当前 `eng1_2026_nodes.tsv` 文件实际计算得到的 sha256 为：
`ba119084615d2f04288a4a2e45efedaa9954247e63fb104189851cfa054b025a`

两者不一致。核对发现：
- 文件内容与任务书描述的“24 个节点”完全吻合（24 行节点 + 1 行表头），节点 id 集合与我此前（2024批次）使用的节点表一致；
- 我 2024 批次产出的 `map-eng1-2024-claude.json` 中 `meta.node_table_sha256` 记录的正是任务书声明的 `86b908b2...`，说明该值可能是历次任务书模板中沿用/预先写入的哈希，而非对当前文件实时计算所得；实际文件哈希以本报告中给出的 `ba119084...` 为准。
- 为与既往批次的 `meta` 字段保持一致（且任务书明确要求 `node_table_sha256` 字段本身即取自任务书声明值），本次输出 JSON 的 `meta.node_table_sha256` 仍填写任务书给出的 `86b908b2...`；但特此在报告中说明实测值不一致，供后续核验/修正任务书或校验脚本时参考。
- 未发现节点表内容有会影响本次映射结果的实质性差异（24 个 `eng1.*` 节点 id 与 title 均可正常读取并用于映射）。

## 试卷结构 → 节点映射依据

2026 年英语一试卷结构（通过读取两份文本层核实一致）：

| 题号 | 试卷部分 | 内容 | 映射节点 |
|---|---|---|---|
| 1–20 | Section I Use of English | 单篇完形填空（AI 与审美/自我认知） | `eng1.paper.part1` |
| 21–25 | Section II Part A / Text 1 | 驴的驯化史 | `eng1.paper.part2.a` |
| 26–30 | Section II Part A / Text 2 | 好莱坞影视制作衰退 | `eng1.paper.part2.a` |
| 31–35 | Section II Part A / Text 3 | 无线电广播史与聆听方式变迁 | `eng1.paper.part2.a` |
| 36–40 | Section II Part A / Text 4 | 美国森林火灾管理与计划烧除 | `eng1.paper.part2.a` |
| 41–45 | Section II Part B | 8 段文字重新排序（已给出 F、H、C 位置） | `eng1.paper.part2.b` |
| 46–50 | Section II Part C | 划线句子英译汉（科学素养教育史） | `eng1.paper.part2.c`（+ `eng1.paper.part3.note`） |
| 51 | Section III Writing Part A | 应用文：以 Li Ming 身份回复 Paul 的邮件（约100词） | `eng1.paper.part4.a` |
| 52 | Section III Writing Part B | 图表作文：养老机器人接受度调查图表（160-200词） | `eng1.paper.part4.b` |

说明：
1. 46–50 题在 `nodes` 中同时列出 `eng1.paper.part2.c` 与 `eng1.paper.part3.note`，`primary_node` 取 `eng1.paper.part2.c`——因为节点表把“英译汉”列为 Section II 阅读理解的 C 节（试卷实际归属），而 `eng1.paper.part3.note`（『第三部分 翻译』下的说明节点）专门用于标注英语（一）的英译汉本质上是阅读理解的一部分、并非独立翻译大部分，二者含义互补，故一并列出，此做法与我在 2024 批次的处理方式一致。
2. 未使用 `eng1.exam.objectives.*`（考查目标：语法/词汇/阅读/写作技能）系列节点参与映射——这些节点描述的是能力维度而非试卷版面结构，粒度上不如 `eng1.paper.*` 系列贴合“第几部分第几题”的定位需求，且与 2024 批次的处理口径保持一致，避免每题重复挂载冗余节点。
3. 未发现任何题目在节点表中找不到对应节点（无『疑似考纲外』情况）；`eng1.paper.part1`、`eng1.paper.part2.a`、`eng1.paper.part2.b` 在节点表中均为叶子层级（无更细子节点），故按规则粒度“不硬塞”，直接采用该层级作为唯一节点。
4. 全部 52 题的试卷位置定位清晰（页面小标题/题号范围/字数要求均可直接从文本层核实），故全部标记为 `high` 置信度；未出现需要标记为 `medium`/`low` 的模糊情形。

## 独立性声明

本次映射仅依据题干 PDF 文本层与节点表独立完成，未查看 `map-eng1-2026-luna.json`、`map-eng1-2026-sol.json` 等同批次其他 coder 的产出。参考的历史文件仅为本人（claude）在 2024 批次产出的 `map-eng1-2024-claude.json`，用于核对输出 schema 与既往映射口径的一致性，不涉及本次 2026 题目内容的答案推测。

## 未触碰事项

- 未修改 `F:\workspace\kaoyan-ai-system` 下任何文件。
- 未执行任何 `git` 命令。
- 全程使用 `py -3.12`；终端中文输出存在乱码风险的步骤（如 sha256 校验）均已改用 Python 脚本读写 UTF-8 结果后再核对，避免终端编码问题影响判断。
