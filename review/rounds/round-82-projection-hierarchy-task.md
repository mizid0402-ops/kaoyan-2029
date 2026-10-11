# 任务书：投影的父节点改用 M4 层级端口（M15，sol 第 80 轮 B4）

先读 `review/rounds/round-80-review-sol-out.md` 的 B4、`contracts/knowledge_tree.md` 的"层级"一节、`ky/knowledge/hierarchy.py`、`contracts/projection.md`、`ky/projection/__init__.py`。
遵守 `AGENTS.md`。你在主工作区改，不提交。
**另一个 luna 同时在改 `ky/exam/topic_weights.py`、`tools/aggregate_topic_weights.py`、`tools/apply_knowledge_weights.py`、`contracts/topic_weights.md`、`tests/contract/test_topic_weights_port.py`——不要碰这些文件。**

## 为什么

WP-H5 把知识树层级写进了 M4 规格：父节点 = ID 的**最长真前缀**且该前缀本身是同一棵树里的节点；并提供公开函数 `ky.knowledge.parent_id`。
投影仍只看"去掉最后一段"的紧邻前缀，找不到就写 `NULL`（`ky/projection/__init__.py` 生效表与补充表两处）。
sol 实测：cs408 有 38 个节点、eng1 有 4 个节点两边给出的父节点不同（例如 `cs408.co.chapter-01.section-01.detail-04.note-01`）。同一概念两套算法，就是拼图的咬合面不一致。

## 要做的

1. 投影生效表 `knowledge_points.parent_id` 与补充表 `supplementary_knowledge_points.parent_id` 都改用 `ky.knowledge.parent_id(point_id, 同一棵树的 ID 集合)`。
   **先核对**：现有投影对"只有两段的 ID"（如 `cs408.ds`）一律写 `NULL`，即使 `cs408` 这样的一段 ID 是树中节点。新定义下会不会出现一段的父节点？各树里有没有一段 ID 的节点？把核对结果写进报告；若新定义会让某些节点的父节点变成一段 ID，照新定义做（规格优先），并在报告里列出。
   `depth` 列的含义不改（仍是 ID 段数 − 1），在报告里说明它与层级父子的区别是否需要另议。
2. `contracts/projection.md` 的 `parent_id` 列说明改为"按 `contracts/knowledge_tree.md` 层级定义"。
3. 投影的 `schema_version` 是否需要升级：`parent_id` 取值变化但列不变。按 `contracts/projection.md` 自己的版本规则判断，写进报告；规则没说清就不升级、在报告里提出。
4. 重建仓库里的投影 `data/projections/kaoyan_projection.sqlite`（`ky` 的投影重建命令，先在代码里找到正确入口），报告里给出重建前后 `parent_id` 不同的行数（按科目）——期望与 sol 的 38 / 4 一致，不一致就解释。
5. 测试：
   - `tests/contract/test_knowledge_tree_port.py`：`parent_id` / `nearest_ancestor_with_scope` 加"缺中间前缀"的用例（例如树里有 `x.a.chapter-01` 与 `x.a.chapter-01.section-01.item-01`，没有 `…section-01`）；sol 指出现有测试在"只认紧邻父段"的实现下也能通过，新用例必须能让那种实现变红（临时改实现验证）。
   - `tests/contract/test_projection_port.py`：同样的缺中间前缀输入，投影的 `parent_id` 等于端口结果（生效表与补充表各一条）。

## 不做的

不改 `ky/knowledge/hierarchy.py` 的行为、不改树语法校验、不改树数据。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_projection_port tests.contract.test_knowledge_tree_port tests.test_projection tests.test_projection_service
```

## 报告

`review/rounds/round-82-projection-hierarchy-luna.md`：落点、第 1 / 3 / 4 条的核对结果、撤实现验证、验收输出。全量：未跑。不提交。含中文文件查 `???`。
