# 任务：把 408 题目映射到大纲知识树节点（**第三方独立编码**）

## 你的角色与独立性要求

你是本轮的**第三方**编码者，模型家族与前两方**不同**（前两方是 Codex 系的 gpt-5.6-sol 与 gpt-5.6-luna）。

**你的价值恰恰在于独立性**：
- **不要**试图推测前两方会怎么答
- **不要**为了"看起来合理"而选一个中庸的节点
- 前两方的产出**不在你的工作目录里**，也不要去找

三方交叉的意义：若三方一致 → 共享偏见的可能性大幅降低；
若你与两方都不同 → 那正是最需要人工看的题。

## 目标

为 2024 年 408 的 **47 道题**，每题给出它考查的**考纲知识树节点 id**。

## 最高优先级规则

### 规则 1：只能从给定节点表里选，**不得自创节点 id**

节点表：`%TEMP%\kaoyan-probe\mapping\cs408_nodes.tsv`（每行：`node_id` / `scope` / `title`，383 个）。
来源是 2026 版官方大纲抽取的 403 节点树。

**若你认为某题考的内容在节点表里找不到对应节点，必须填 `null` 并说明"疑似考纲外"，不得编造 id。**
**填 `null` 不是失败——它是"考纲树可能缺节点"的重要信号。**

### 规则 2：粒度优先级

按 **item > section > chapter** 优先选最细的节点。
但**不要为了凑细粒度硬塞**：若题目只对应到章级内容、section 级没有合适项，就填 chapter 级节点。

### 规则 3：一题可对应多个节点，但要克制

- 选择题通常 1 个；若确实跨两个考点，最多 2 个并说明主次。
- **综合应用题（41–47）必然跨多个节点**，列 1–4 个，并说明各部分分别对应哪个节点。

### 规则 4：不确定就说不确定

每题必须给 `confidence`：`high` / `medium` / `low`。
**宁可标 low，不要硬猜。** 置信度是你的自我报告，不是给别人看的门面。

## 你要读的题干

**只读，不要修改**：

- 主来源：`F:\workspace\kaoyan-ai-system\data\raw_materials\cs408\past_papers_thirdparty\408_2024_paper_rebuild.pdf`
  （**有文本层**，12 页，47 题齐全，用 `pypdf` 抽取）
- 交叉参考（选择题题干 + 解析）：`F:\workspace\kaoyan-ai-system\data\raw_materials\cs408\quiz_pages\cs408_quiz_2024.html`

题号与分值的权威清单（不要自己重新数）：
`F:\workspace\kaoyan-ai-system\data\exam_questions\408_index_2024.json`
（41–47 分值已确认为 `13/10/13/10/7/8/9`）

## 输出格式

写入 `%TEMP%\kaoyan-probe\mapping\map-claude.json`：

```json
{
  "meta": {
    "coder": "claude",
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
      "reason": "≤40 字，判断依据。**不要抄题干原文。**"
    }
  ]
}
```

`entries` 必须**恰好 47 条**，`number` 为 1..47，无缺无重。

## 纪律

1. **不要修改 `F:\workspace\kaoyan-ai-system` 下任何文件。** 不要执行 git。
2. 本机 `py` 启动器不回显输出，**必须用 `py -3.12`**。
3. 终端吞中文：结果写 UTF-8 文件再读。
4. 用 `pypdf` 抽文本；若某题文本层读不全，用 `pypdfium2` 渲染该页目视补读。
5. **reason 字段写判断依据，不要复制题干原文**（避免把题目内容写进产出文件）。

## 报告

写入 `%TEMP%\kaoyan-probe\mapping\report-map-claude.md`：

1. 47 题的映射结果表（题号 / 节点 / 置信度）。
2. **统计**：各置信度条数；填 `null` 的题号及理由。
3. **哪些题你判断考纲树覆盖不到**（单独列）。
4. **哪些题你标了 low**，卡在哪里。
5. 「没有把握的地方」至少 3 条。

最后用一句话回复：47 题是否全部编码 + high/medium/low 条数 + null 条数 + 报告路径。
