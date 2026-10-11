# Round 47 修复任务书：WP-B′2 投影三处 MAJOR（gpt-6-sol 判 FAIL）

你是实现者（续同一会话）。依据：`review/rounds/round-47-wp-b2-review-sol-out.md`（sol 已给出精确触发输入）。遵守仓库根 `AGENTS.md`（只跑点名模块，不跑全量）。

1. **M1 哈希与解析同源**：每个登记输入只读一次原始字节，哈希与解析共用这份字节。
   `ky.knowledge` 增加从文本/字节加载知识点的入口（例如 `load_knowledge_points_from_text(text, *, source, writer)`），现有 `load_knowledge_points(path)` 改为读字节后调用它；附表、索引、权重同理（严格 YAML 读取也要能从文本入口进入，复用 `ky.models` 的加载器，不要复制）。
   回归：沿用 sol 的做法——首次读取后改写文件，断言表内容与 `inputs` 哈希属于同一版本。
2. **M2 畸形索引条目**：`locator` 不是映射（以及其他字段类型不符）时，以该条目字段路径抛 `ContractError`；CLI exit 2。回归：sol 的 `locator: [1]` 输入。
3. **M3 补充树外科目节点**：补充树每个节点 ID 的科目必须等于 `view.subject`，否则在 `supplementary.<name>.files.tree` 拒绝。回归：sol 的 `math1.synthetic.extra` 输入。
4. 顺手按 sol 建议加强两处断言：仓库测试核对 7 个 legacy 节点的**完整 ID 集**与 `tree_source` 精确登记键；替换演练里把被替换文件的**内容也改掉**，断言表内容来自新文件。

不做：`writer` 身份问题（知识点接口的读写权限拆分另开工作包）；不改 `data/`。

验收：`py -3.12 -m unittest tests.contract.test_projection_port tests.test_projection tests.test_knowledge_contract tests.test_state_snapshot` 全绿。全量不跑。
产物：追加到 `review/rounds/round-47-wp-b2-projection-luna.md` 末尾（"## 修复（sol FAIL 后）"），不提交。
