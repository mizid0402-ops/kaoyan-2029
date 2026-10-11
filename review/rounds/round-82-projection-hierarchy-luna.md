# Round 82 投影层级端口收口

## 落点

- `ky/projection/__init__.py`：生效树按该科目 ID 集合、补充树按该补充树 ID 集合调用
  `ky.knowledge.parent_id`；两处投影共用 M4 的最长真前缀规则。
- `contracts/projection.md`：两张知识点表的 `parent_id` 均指向
  `contracts/knowledge_tree.md` 的层级定义。
- `tests/contract/test_knowledge_tree_port.py`：为 `parent_id` 和
  `nearest_ancestor_with_scope` 加入缺中间前缀例子。
- `tests/contract/test_projection_port.py`：用克隆工作区在有效表和补充表各验证一条缺中间
  前缀节点的 `parent_id`。
- 重建产物：`data/projections/kaoyan_projection.sqlite`。

## 核对结果

### 父节点和单段 ID

对注册树中所有 ID 检查段数：cs408 生效树 403 个、eng1 24 个、math1 69 个、cs408 补充树
410 个；没有单段 ID 节点。因此当前数据里没有节点会以单段 ID 为父节点。两段 ID（例如
`cs408.ds`）即使存在，也只有在同树中确有 `cs408` 节点时才会得到一段父节点；当前各树都
没有这样的根 ID。规则按新端口实现，没有特例。

`depth` 继续等于 ID 段数减一。它表示 ID 的段数，不是沿实际存在父节点边走到根的边数；当
中间前缀缺失时，两者可能不同。当前没有证据表明需要改变 `depth` 的列义；若消费者把它当
成父子边数，需另行讨论并统一契约。

### Schema 版本

`contracts/projection.md` 只声明当前 `projection_schema_version` 为 2，没有说明版本递增的
判据。此次列名、类型和表结构均未变化，仅 `parent_id` 的值依照 M4 改变，因此保留 v2；
建议后续在契约中明确版本号按结构变化还是语义变化递增。

### 重建前后父节点差异

先用 `build_projection` 写入临时数据库，与仓库原投影按 ID 比较，再通过仓库命令重建。按
科目统计的不同 `parent_id` 行数：

| 表 | 科目 | 不同的行数 |
|---|---:|---:|
| `knowledge_points` | cs408 | 38 |
| `knowledge_points` | eng1 | 4 |
| `knowledge_points` | math1 | 0 |
| `supplementary_knowledge_points` | cs408 | 38 |

生效表计数与 sol 的 38 / 4 一致；补充树中的相同 cs408 节点也更新了 38 行。正式重建命令：
`py -3.12 -m ky.projection --json`。命令成功，输出路径为
`data/projections/kaoyan_projection.sqlite`，投影含 496 个生效节点和 410 个补充节点。

## 回归验证

临时把 `ky.knowledge.hierarchy.parent_id` 改为只检查紧邻前缀后，以下三个新用例均失败，父节点
实际为 `None`：

- `test_parent_id_skips_missing_intermediate_prefix`
- `test_nearest_ancestor_with_scope_skips_missing_intermediate_prefix`
- `test_projection_parent_uses_port_across_missing_intermediate_prefix`

临时改动已还原；`ky/knowledge/hierarchy.py` 行为未改。

## 验收

执行任务书指定命令：

```text
py -3.12 -m unittest tests.contract.test_projection_port tests.contract.test_knowledge_tree_port tests.test_projection tests.test_projection_service
Ran 39 tests in 16.999s
OK
```

全量测试：未跑（按 `AGENTS.md`）。未提交。
