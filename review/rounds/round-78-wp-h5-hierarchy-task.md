# 任务书：WP-H5 续——树层级接口的决定（续你第 76 轮）

你停下来问是对的。决策者的决定：**路径 1 的轻量版**——把现有的层级约定写进 M4 规格并提供公开接口，M6 只用这个接口。

## 事实与理由

本项目知识树的层级**本来就由 ID 的点分命名空间表达**：`ky/knowledge/tree_grammar.py` 的 `_parent_id()` 与各树语法校验都依赖它，
投影也按它找父节点。这是一个存在但没写进规格、也没有公开接口的端口约定，不是"从文本倒推结构"。缺的是把它定型。

## 要做的（在第 74 / 76 轮任务书之上）

1. `contracts/knowledge_tree.md` 加一节"层级"：节点的父节点 = 其 ID 的**最长真前缀**（按 `.` 分段）且该前缀本身是同一棵树里的节点；没有这样的前缀即为根。
   祖先 = 沿父节点逐级向上。说明这正是现有树语法校验所依赖的约定。
2. 在 M4 提供公开接口（放 `ky/knowledge/` 里最合适的模块，模块头更新"对外接口"）：
   - `parent_id(point_id, tree_ids) -> str | None`；
   - `nearest_ancestor_with_scope(point_id, points_by_id, scope) -> str | None`（含自身：自身 scope 即为所求时返回自身）。
   `tree_grammar.py` 里需要"直接父段"的地方改用公开函数或保持其私有辅助——**不改变任何树语法校验的行为**（`tests.test_verify_tree_shapes`、`tests.contract.test_knowledge_tree_port` 须照旧通过）。
   契约测试补这两个函数的正反例（`tests/contract/test_knowledge_tree_port.py`）。
3. M6 的 cs408 上卷用 `nearest_ancestor_with_scope(..., "chapter")`；找不到 chapter 祖先 → `ContractError`（列出节点）。
4. 然后完成第 74 / 76 轮的全部内容：批次清单、注册表键、规格、聚合器、`--check` / `--write` 工具、复现（逐位相等）、增量、负例、模块地图、方法文档 §1.3 更正。

## 验收（只跑这些；缺 `data/raw_materials/` 导致的既有失败如实记录）

```
py -3.12 -m unittest tests.contract.test_topic_weights_port tests.contract.test_workspace tests.contract.test_knowledge_tree_port tests.test_verify_tree_shapes
py -3.12 tools/aggregate_topic_weights.py --check
```

## 报告

`review/rounds/round-78-wp-h5-luna.md`：合并第 74 / 76 轮已有结论，逐条落点、复现比较结果、增量测试结果、验收输出、建议。
全量：未跑。不提交。含中文文件查 `???`。
