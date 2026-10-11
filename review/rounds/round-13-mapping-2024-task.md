# 任务：把 408 题目映射到大纲知识树节点（多模型交叉验证，第一批）

## 目标

为 `data/exam_questions/408_index_2024.json` 的 **47 道题**，每题给出它考查的**考纲知识树节点 id**。

## 最高优先级规则

### 规则 1：只能从给定节点表里选，**不得自创节点 id**

节点表在 `%TEMP%\kaoyan-probe\mapping\cs408_nodes.tsv`（每行：节点 id、层级、标题）。
来源是 `data/structured_materials/cs408/knowledge_tree.yaml`（403 节点，从 2026 版官方大纲抽取）。
**如果你认为某题考的内容在节点表里找不到对应节点，必须填 `null` 并说明"疑似考纲外"，不得编造 id。**

### 规则 2：粒度优先级

按 **item > section > chapter** 优先选最细的节点。
但**不要为了凑细粒度硬塞**：若题目只对应到章级内容、section 级没有合适项，就填 chapter 级节点。

### 规则 3：一题可对应多个节点，但要克制

- 选择题通常 1 个节点；若确实跨两个考点，最多列 2 个，并说明主次。
- 综合应用题（41–47）**必然跨多个节点**，请列 1–4 个，并说明该题各部分分别对应哪个节点。

### 规则 4：不确定就说不确定

每题必须给 `confidence`：`high` / `medium` / `low`。
**`low` 不是失败**——它是下游决定"是否需要人工看"的依据。宁可标 low，不要硬猜。

## 你要读的题干

题干在这些文件里（**只读，不要修改**）：

- `F:\workspace\kaoyan-ai-system\data\raw_materials\cs408\past_papers_thirdparty\408_2024_paper_rebuild.pdf`
  （**有文本层**，12 页，47 题齐全；用 `pypdf` 抽取）
- 交叉参考（选择题题干 + 解析）：
  `F:\workspace\kaoyan-ai-system\data\raw_materials\cs408\quiz_pages\cs408_quiz_2024.html`

题号与分值的权威清单（不要自己重新数）：
`F:\workspace\kaoyan-ai-system\data\exam_questions\408_index_2024.json`
（41–47 题的分值已确认为 `13/10/13/10/7/8/9`）

## 输出格式

写入 `%TEMP%\kaoyan-probe\mapping\map-<你的代号>.json`，结构：

```json
{
  "meta": {
    "coder": "<你的代号>",
    "year": 2024,
    "subject": "cs408",
    "node_table_sha256": "<节点表的 sha256，自己算>",
    "started_at": "<ISO 时间>"
  },
  "entries": [
    {
      "number": 1,
      "nodes": ["cs408.ds.chapter-01.section-02.item-03"],
      "primary_node": "cs408.ds.chapter-01.section-02.item-03",
      "confidence": "high",
      "reason": "≤40 字，说明为什么是这些节点。不要抄题干。"
    }
  ]
}
```

**要求**：`entries` 必须**恰好 47 条**，`number` 为 1..47，无缺无重。

`reason` 字段**写判断依据，不要写题干原文**（避免把题目内容复制进产出文件）。

## 纪律

1. **不要为了和别的模型一致而改自己的判断**——你是独立编码者。
2. **不要修改 `F:\workspace\kaoyan-ai-system` 下任何文件。** 不要执行 git。
3. 本机 `py` 启动器不回显输出，**必须用 `py -3.12`**。
4. 终端吞中文：结果写 UTF-8 文件再读。
5. 用 `pypdf` 抽文本；若某题文本层读不全，用 `pypdfium2` 渲染该页目视补读。

## 报告

写入 `%TEMP%\kaoyan-probe\mapping\report-map-<你的代号>.md`，包含：

1. 47 题的映射结果表（题号 / 节点 / 置信度）。
2. **统计**：各置信度条数；填 `null` 的题号及理由。
3. **哪些题你认为考纲树覆盖不到**（这是重要信号，单独列）。
4. **哪些题你标了 low**，以及卡在哪里。
5. 「没有把握的地方」至少 3 条。

最后用一句话回复：47 题是否全部编码 + high/medium/low 条数 + null 条数 + 报告路径。
