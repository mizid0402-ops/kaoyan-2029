# WP-H5 收尾：拆分过长函数

将批次登记校验、逐题聚合、上卷累加和权重排序拆到 `_registered_batch`、`_aggregate_questions`、`_accumulate_topic_weights` 与 `_ordered_topic_weights`；`_read_entries` 的产出读取和题号覆盖校验拆为 `_read_coder_entries`、`_validate_question_coverage`。`aggregate_topic_weights` 现负责编排。批次、题目、编码者、节点的遍历和浮点 `+=` 顺序保持不变。

验收：

- `py -3.12 tools/aggregate_topic_weights.py --check`：`topic_weights.json matches registered batches`。
- `py -3.12 -m unittest tests.contract.test_topic_weights_port`：6 tests，`OK`。

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。未提交。
