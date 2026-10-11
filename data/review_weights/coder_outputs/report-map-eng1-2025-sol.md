# 2025 年英语一试题节点映射报告（sol）

## 结论

- 已独立完成 1—52 题映射，共 52 条，无缺号、重号或自创节点。
- confidence 统计：high 45，medium 7，low 0。
- `primary_node` 为 `null` 的题目：0；未发现“疑似考纲外”题目。
- 两份题源 PDF 均有可用文本层，题型、编号与题干信息相互印证。

## 映射原则

1. 优先使用能直接对应试卷题型的细分节点作为 `primary_node`。
2. `nodes` 补充与作答能力直接相关的阅读、写作、词汇或语法节点，不加入仅有弱关联的泛化节点。
3. 第 46—50 题在节点表中同时对应“阅读理解 C 节”和“英译汉作为阅读理解的一部分”两个表述，因此保留两者，并将 confidence 标为 medium；其余题型在卷面上有明确分节，标为 high。
4. 第 5、19 题分别同时涉及介词搭配与非谓语结构，难以仅归入词汇或语法单一类别，故保留两个知识节点并标为 medium。

## 分段结果

| 题号 | 题型 | primary_node | confidence |
|---|---|---|---|
| 1—4 | 英语知识运用 | `eng1.paper.part1` | high |
| 5 | 英语知识运用 | `eng1.paper.part1` | medium |
| 6—18 | 英语知识运用 | `eng1.paper.part1` | high |
| 19 | 英语知识运用 | `eng1.paper.part1` | medium |
| 20 | 英语知识运用 | `eng1.paper.part1` | high |
| 21—40 | 阅读理解 A 节 | `eng1.paper.part2.a` | high |
| 41—45 | 阅读理解 B 节 | `eng1.paper.part2.b` | high |
| 46—50 | 阅读理解 C 节（英译汉） | `eng1.paper.part2.c` | medium |
| 51 | 应用文写作 | `eng1.paper.part4.a` | high |
| 52 | 短文写作 | `eng1.paper.part4.b` | high |

## 节点表校验说明

任务书给出的 SHA-256 为 `86b908b2d0bc5331bf0771de29790e69e31fa7efed361e9f09d8da28889f472d`，该值与节点表按 UTF-8 解码并统一为 LF 换行后的哈希一致，已写入 JSON 的 `meta.node_table_sha256`。当前磁盘文件采用 CRLF 换行，其原始字节哈希为 `ba119084615d2f04288a4a2e45efedaa9954247e63fb104189851cfa054b025a`；差异来自换行编码，不是节点内容变化。

## 校验项

- `entries` 条数必须为 52。
- `number` 必须严格覆盖 1—52。
- `nodes` 与 `primary_node` 必须全部来自指定 TSV，或显式为 `null`。
- `confidence` 必须属于 high / medium / low。
- 每条 `reason` 必须非空，且以判断依据而非题干复制描述。
