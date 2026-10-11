# WP-H4b / sol 第 73 轮意见修复报告

## 逐项落点

- **M1 同版本图校验**：`resolve_mapping_chain` 现在先拒绝重复边、再检测全图环，之后才对
  `from_version == to_version` 返回空链。新增同版本请求遇重复边、成环的两个负例。
- **M2 缺省队列位置**：`review-queue` 省略 `--store` 时直接使用 `workspace.review_queue`，
  不再对写入目标调用 `require()`。新增 check 与 migrate 不传 `--store` 的成功用例。
- **合并择优**：先按 `state == "queued"` 排序，再按到期日、`review_id` 排序。新增
  suspended 早到期对 queued 晚到期，以及过期 scheduled 对 queued 两个精确例；均断言 queued
  保留，另一个被退役。
- **路径搜索**：`_find_paths` 收集到第二条路径后立即停止继续递归，公开端口不变。
- **空链 apply**：打印“无需迁移（from == to）”，退出 0，不调用写入；测试前后比较队列
  manifest、分片、目录及空目录条目，内容和目录树均不变。
- **分类说明**：CLI 计划摘要说明分类可重叠；规格同步说明一项可同时属于 `renamed`、
  `merged` 和 `retired`。
- **多步迁移**：补充断言拆分子项经过下一步改名后的 `review_id` 与 revision。

修改文件：`ky/review/syllabus_migration.py`、`ky/__main__.py`、
`tests/contract/test_syllabus_migration_port.py`、`contracts/syllabus_migration.md`、
本报告。未改 `ky/knowledge/syllabus_mapping.py`、`ky/storage/` 或 `ky/workspace.py`。

## 撤改验证记录

- **M1**：临时将同版本空链判断移回图校验之前，运行
  `tests.contract.test_syllabus_migration_port.SyllabusMigrationPortTests.test_chain_rejects_missing_multiple_duplicate_edges_and_cycles`。
  结果 `FF`：同版本重复边和同版本成环两个 subtest 均因未抛 `ContractError` 失败；随后恢复
  校验顺序。
- **M2**：临时把缺省路径恢复为 `workspace.require("state.review_queue")`，运行
  `test_check_uses_registered_default_store` 与 `test_migrate_uses_registered_default_store`。
  结果 `FF`：两者均退出 2，报 `state.review_queue: not registered`；随后恢复为
  `workspace.review_queue`。
- **合并优先级**：临时恢复仅按 `(due_date, review_id)` 排序，运行两个 queued 优先用例。
  结果 `FF`：两例中 queued 项都被退役；随后恢复 queued 状态优先排序。

## 验收

按任务书运行：

```text
py -3.12 -m unittest tests.contract.test_syllabus_migration_port tests.test_cli
```

结果：`Ran 51 tests ... OK`。全量：未跑。

本报告与本轮新增/修改文件已完成连续问号占位符扫描，未发现匹配项。

未提交；`../kaoyan-wt-h5` 未触碰。
