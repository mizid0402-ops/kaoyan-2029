# 2025 英语一 52 题 -> 考纲节点映射报告 (coder: claude)

- 节点表: `C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\mapping\tasks\eng1_2025_nodes.tsv`
- 节点表实际 sha256: `ba119084615d2f04288a4a2e45efedaa9954247e63fb104189851cfa054b025a`
- 任务书中给出的 sha256: `86b908b2d0bc5331bf0771de29790e69e31fa7efed361e9f09d8da28889f472d`
- **哈希不一致警告**：当前节点表文件的 sha256 与任务书中声明的值不一致。已核对文件行数(24 个节点)与任务描述吻合，且路径为任务书指定的唯一节点表路径，推测任务书文档中的哈希值与当前文件版本不同步(例如文件在任务下发后被重新生成)。本次映射仍以任务书指定路径的当前文件内容为准，未做任何猜测性替换。

- entries 总数: 52（应为 52）
- number 覆盖: 1..52 连续无缺无重（已在脚本中断言校验）
- confidence 分布: high=52, medium=0, low=0
- primary_node 为 null 的题数: 0

## 试卷结构核对依据

通过 `bv_e1_2025.txt` 与 `lazy_e1_2025.txt`（对应 PDF 的已提取文本）核对，2025 年英语一试卷结构与题号区间为：

| 题号区间 | 试卷位置 | 映射主节点 |
|---|---|---|
| 1-20 | Section I Use of English（完形填空） | `eng1.paper.part1` |
| 21-40 | Section II Reading Comprehension Part A（4篇阅读×5题） | `eng1.paper.part2.a` |
| 41-45 | Section II Part B（新题型，段落排序） | `eng1.paper.part2.b` |
| 46-50 | Section II Part C（英译汉） | `eng1.paper.part2.c` |
| 51 | Section III Writing Part A（应用文，回复邮件） | `eng1.paper.part4.a` |
| 52 | Section III Writing Part B（短文写作，图表作文） | `eng1.paper.part4.b` |

该结构（完形20 + 阅读A20 + 阅读B5 + 阅读C(翻译)5 + 写作A1 + 写作B1 = 52）与考研英语一多年来的固定题型/分值结构一致，且与本次两份题干文本的 Section/Part 标题、题号编号完全对应，故全部 52 题均标记为 `high` 置信度。

## 未使用/疑似考纲外说明

本次 52 题全部可在节点表中找到对应节点，无需填 null。节点表中以下节点本次未被用作 primary_node（均为宏观说明性/附录类节点，不对应具体题目，符合预期）：`eng1.appendix.*`、`eng1.exam.nature`、`eng1.exam.objectives`(顶层)、`eng1.exam.objectives.language-knowledge`(顶层)、`eng1.exam.objectives.language-skills`(顶层)、`eng1.example`、`eng1.paper.form`、`eng1.paper.format`、`eng1.paper.part2`(顶层)、`eng1.paper.part3`(顶层)、`eng1.paper.part4`(顶层)。

## 独立完成声明

本次映射独立完成，未查看或参考其他 coder 的产出文件。
