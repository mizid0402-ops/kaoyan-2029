# 2024 年英语一试题节点映射报告（sol）

## 结论

- 已独立完成 1—52 题映射，共 52 条，无缺号、无重号。
- 置信度：high 45 条，medium 7 条，low 0 条。
- `primary_node` 为 `null`：0 条；`nodes` 中的 `null`：0 个。
- 所有节点 ID 均来自指定节点表，未自创节点。

## 输入与完整性

- 节点表：`mapping/tasks/eng1_2024_nodes.tsv`，共 24 个节点。
- 任务书给出的 SHA-256 `86b908b2d0bc5331bf0771de29790e69e31fa7efed361e9f09d8da28889f472d` 与把节点表换行统一为 LF 后的实测值一致。
- 当前磁盘文件使用 CRLF 换行，原始字节 SHA-256 为 `ba119084615d2f04288a4a2e45efedaa9954247e63fb104189851cfa054b025a`；两者差异仅由换行编码造成。JSON 的 `node_table_sha256` 记录任务书采用的 LF 规范化哈希。
- 两份指定 PDF 均有可用文本层：`bv_e1_2024.pdf` 14 页，`lazy_e1_2024.pdf` 12 页。两份来源对题号和板块归属相互印证。

## 映射口径

| 题号 | 主节点 | 附加能力或知识节点 | 说明 |
|---|---|---|---|
| 1—20 | `eng1.paper.part1` | 逐题选择 `eng1.exam.objectives.knowledge.grammar` 或 `eng1.exam.objectives.knowledge.vocabulary` | 完形填空兼有句法结构、固定搭配和语境词义判断。 |
| 21—40 | `eng1.paper.part2.a` | `eng1.exam.objectives.skills.reading` | 四篇常规阅读多项选择。 |
| 41—45 | `eng1.paper.part2.b` | `eng1.exam.objectives.skills.reading` | 评论与概括句匹配的新题型。 |
| 46—50 | `eng1.paper.part2.c` | `eng1.exam.objectives.skills.reading` | 题源明确置于阅读理解 Part C 的英译汉。 |
| 51 | `eng1.paper.part4.a` | `eng1.exam.objectives.skills.writing` | 回复邮件的应用文写作。 |
| 52 | `eng1.paper.part4.b` | `eng1.exam.objectives.skills.writing` | 图画与统计图结合的短文写作。 |

## 边界判断

1. 未给 46—50 题附加 `eng1.paper.part3` 或 `eng1.paper.part3.note`。题源将这五题明确列在 Section II Reading Comprehension 的 Part C，已有更精确的 `eng1.paper.part2.c` 可用，继续叠加另一部分节点会制造归属冲突。
2. 51—52 题题源标为 Section III Writing，而节点表把对应细项命名为第四部分 A/B 节。因为节点表中只有 `eng1.paper.part4.a` 与 `eng1.paper.part4.b` 能精确表达应用文和短文写作，故采用这两个节点，并将置信度降为 medium 以显式保留编号差异。
3. 1—20 题中第 6、8、15、16、19 题的词义判断同时受句法或篇章语境影响，因此标为 medium；其余题型归属或考点指向明确，标为 high。
4. 没有题目需要标记为“疑似考纲外”，所以不存在 `null` 映射。

## 最小范围验证标准

- JSON 可被 Python 3.12 解析。
- `entries` 长度恰为 52。
- `number` 排序后严格等于 1—52，且无重复。
- 每条均包含 `number`、`nodes`、`primary_node`、`confidence`、`reason`。
- `confidence` 仅取 high、medium、low。
- 每个非空节点均存在于指定 TSV。
- `primary_node` 为非空时必在该条 `nodes` 中。
- `reason` 非空，且不是题干原文复制。

