# Round 47 评审：WP-B′2 投影（已提交 341200b）

请审 `git show 341200b`（`ky/projection/`、`contracts/projection.md`、`tests/contract/test_projection_port.py`）。遵守仓库根 `AGENTS.md`：不跑全量，只跑与结论直接相关的单个模块。
Claude 已看出、请你给出判断的两点：

1. **输入哈希与解析分两次读文件**（`inputs` 先 `read_bytes` 算哈希，之后再解析）——与 WP-B 的 M3 同类。参考数据是冻结的；你认为这里必须改还是记为已知限制？
2. **`load_knowledge_points(..., writer="deterministic_script")`**：投影是读者，却用了"有权写 frequency"的身份；快照用 `writer="state_snapshot"`。今天所有树 `frequency: null` 没差别，但一旦确定性脚本写入频率，快照会拒绝加载、投影不会。这是本包的问题，还是知识点契约"读者身份与写权限混用"的既有设计问题？给出最小修法建议（本轮不一定修）。

另外逐条对照 `contracts/projection.md` 与实现，找"规格写了、实现没做"或"测试断言太弱"的地方。
产物：`review/rounds/round-47-wp-b2-review-sol-out.md`，每条 "必须改 / 建议改 / 不改"，给 PASS / FAIL。
