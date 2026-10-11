# 2026 年英语一题目映射报告（luna）

## 结论

- 已编码题号：52 题，严格覆盖 1–52，无缺号、重号。
- confidence：high 49，medium 3，low 0。
- `primary_node` 为 null：0 题；所有题均能在允许节点表中找到明确的试卷结构或能力节点，因此没有标为“疑似考纲外”。

## 输入与独立性

- 题干来源：`claude2/dl/bv_e1_2026.pdf`、`claude2/dl/lazy_e1_2026.pdf`。
- 节点表：`mapping/tasks/eng1_2026_nodes.tsv`。
- 本次只读取任务书、上述两份题干 PDF 和上述节点表；未读取或参考其他 coder 产出。
- 两份 PDF 均存在文本层；未使用其他 coder 的答案或映射结果。

## 节点表校验

- 实际读取节点表 SHA-256：`ba119084615d2f04288a4a2e45efedaa9954247e63fb104189851cfa054b025a`。
- 任务书声明 SHA-256：`86b908b2d0bc5331bf0771de29790e69e31fa7efed361e9f09d8da28889f472d`。
- 两者不一致；本文件的 `meta.node_table_sha256` 记录实际读取文件的哈希，节点 ID 也只取自该文件。

## 映射分段

| 题号 | 试卷节点 | 能力/知识节点 |
|---|---|---|
| 1–20 | `eng1.paper.part1` | `grammar` 或 `vocabulary` |
| 21–40 | `eng1.paper.part2.a` | `eng1.exam.objectives.skills.reading` |
| 41–45 | `eng1.paper.part2.b` | `eng1.exam.objectives.skills.reading` |
| 46–50 | `eng1.paper.part2.c` | `eng1.paper.part3.note` |
| 51 | `eng1.paper.part4.a` | `eng1.exam.objectives.skills.writing` |
| 52 | `eng1.paper.part4.b` | `eng1.exam.objectives.skills.writing` |

## 最小范围验证

- JSON 可按 UTF-8 回读并解析。
- `entries` 数量为 52，题号集合为 1–52。
- 每条都有 `number`、`nodes`、`primary_node`、`confidence`、`reason`。
- 所有 `nodes` 和非空 `primary_node` 均存在于节点表；未自创节点 ID。
- 未执行 Git，也未修改 `F:\workspace\kaoyan-ai-system`。
