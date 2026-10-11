# 2025 英语一题目节点映射报告（luna）

## 输入与边界

- 任务书：`mapping/tasks/task_eng1_2025.md`
- 节点表：`mapping/tasks/eng1_2025_nodes.tsv`
- 题干来源：`claude2/dl/bv_e1_2025.pdf`、`claude2/dl/lazy_e1_2025.pdf`
- 节点 ID 只取自节点表；未发现需要标记为“疑似考纲外”的题目。
- 节点表按 LF 规范化后的 SHA-256 为 `86b908b2d0bc5331bf0771de29790e69e31fa7efed361e9f09d8da28889f472d`，与任务书给定值一致。

## 映射判断

1. 1–20：两份 PDF 均将其置于 Section I Use of English，按空格主要考查词义搭配或句法连接，分别补充词汇/语法知识节点。
2. 21–40：均位于 Section II Part A，分别来自四篇阅读材料，统一映射到 A 节和阅读技能节点。
3. 41–45：位于 Section II Part B，是段落排序的新题型，映射到 B 节和阅读技能节点。
4. 46–50：位于 Section II Part C，是五处英译汉分段；同时保留 Part C 节点及“英译汉作为阅读理解的一部分”注释节点。
5. 51：位于 Section III Writing Part A，属于应用文写作；52 位于 Part B，属于短文写作。

## 完整性与置信度

- `entries`：52 条，题号 1–52 无缺失、无重复。
- `confidence`：high 52 条，medium 0 条，low 0 条。
- `null`：0 条。
- 结论：所有题目均能依据 PDF 中明确的试卷分区与节点表中的对应节点编码；没有把题干外推为节点表不存在的细分 ID。
