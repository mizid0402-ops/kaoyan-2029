# WP-H5 实施报告

## 复现门槛结论

**暂停实现，等待决策者确认汇总规则。** 按任务书先对现有 11 批做只读复现：

- 按 high=1.0、medium=0.6、low=0.3 逐题投票，并将分布舍入到三位小数后，432 条
  `per_question` 全部与现有文件一致。
- 11 条 `batch_stats` 全部一致；批次题号无缺失、无重复。
- 现有 `meta` 记录 11 批、三个 coder 和上述置信度权重。
- 但 `topic_weight` 的输出粒度无法按方法文档确定性复现，因此整份文件不能判为完全一致。

## 2024 CS408 产出核对

已打开三份未带科目年份的产出核对 `meta`：

| 文件 | coder | subject | year | node_table_sha256 |
|---|---|---|---:|---|
| `map-sol.json` | sol | cs408 | 2024 | `447b9f6280be38868ac18a8adec60895cdaca247b13246b1b46cdc6b8b1ad386` |
| `map-luna.json` | luna | cs408 | 2024 | `447b9f6280be38868ac18a8adec60895cdaca247b13246b1b46cdc6b8b1ad386` |
| `map-claude.json` | claude | cs408 | 2024 | `447b9f6280be38868ac18a8adec60895cdaca247b13246b1b46cdc6b8b1ad386` |

三份 `meta` 均确认属于 cs408 2024，摘要值相同。

## 阻塞证据

方法文档 §1.2 说明逐题的置信度加权投票，但没有给出 `topic_weight` 从题目节点分布汇总
到主题节点的映射规则。§1.3 只说明 CS408 按 chapter、数学一按 chapter、英语一因没有
chapter 层而退到 section。当前产物与该粒度描述不一致：按登记知识树的 `scope` 字段，
`topic_weight` 中 CS408 有 24 个 chapter；数学一有 19 个 chapter 和 20 个 section；英语一
有 10 个 item 和 6 个 section。文档没有说明何时保留较细层级、如何处理没有相应父节点的
投票，或如何在混合层级间归并。因此无法据文档算出应与现有节点逐项比较的
`topic_weight`，也无法报告可信的节点差值。

方法文档只说节点表从知识树的 chapter/section/item 节点导出，没有定义导出后的字节格式、
排序或哈希步骤。故无法独立重算 `node_table_sha256`，也未猜测其算法。2024 三份输出中的
摘要相互一致，但这不能单独证明它们与当前注册树相符。

## 变更与验证

仅新增本报告。未改权重 JSON、编码者产出、索引、注册表或实现文件。复现为只读探针，未
写入仓库。按复现门槛未开始实现，故验收命令未运行：

- `py -3.12 -m unittest tests.contract.test_topic_weights_port tests.contract.test_workspace`：未跑
- `py -3.12 tools/aggregate_topic_weights.py --check`：未跑（工具尚未实现）
- 全量：未跑（按 AGENTS.md，由决策者提交前统一跑）

## 建议

请决策者先明确 `topic_weight` 的节点归并规则，并补充节点表的确定性序列化与 SHA-256
算法。之后可继续实现聚合、重算全部字段并编写对应契约测试；在这两项规则明确前，不应
用特判拟合当前汇总值。
