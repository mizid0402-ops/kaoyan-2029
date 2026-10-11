# WP-F-a 返工报告

## 改动落点

1. `ky/storage/day_plan_store.py`
   - `_read_freeze_event()` 与 `_read_freeze_sources` 共用 `_parse_freeze_event_bytes()`；该函数接收
     已读字节，完成解析、字段与存储路径校验。冻结/恢复事件错误路径和消息沿用原规则。
   - `_load_day_plans_manifest()` 只负责读文件字节，随后与 `_read_current_plans()` 共用
     `_parse_day_plans_manifest()` 做条目规整，manifest 每次读取一次。
   - manifest 候选只接受 `<root>/<YYYY-MM>/day_plans_manifest.yaml`。扫描发现其他位置的同名文件时，
     抛 `StorageError` 并指出错位路径。完成事件仍递归发现后按 `_completion_event_path(day)` 校验。
2. `ky/storage/route_store.py`
   - `_read_manifest()` 和 `read_state_sources()` 共用 `_parse_manifest_bytes()`。
   - `_load_entry()` 与 `read_state_sources()` 共用 `_load_entry_from_bytes()` 校验原始 SHA-256、
     revision、route_id 并解析；版本字节由 `_read_entry_bytes()` 读取一次。原错误消息与路径保留。
3. `ky/storage/review_shards.py`
   - `load()` 与 `read_state_sources()` 共用 `_load_items()`，队列级重复 `review_id` 检查只有一份。
     `load()` 仍走原 manifest loader，因此缺 manifest 仍报原 `StorageError`；新来源端口缺 manifest
     仍返回空队列、空来源。
4. `tests/contract/test_state_sources_port.py`
   - `_assert_each_source_read_once()` 同时计数 `Path.read_bytes` 与 `Path.read_text`。队列、路线、计划
     和 availability 测试均断言来源文件总计恰好读取一次，且没有通过 `read_text` 再读一次；计划测试
     还锁住每月 manifest 的单次读取。
   - 增加任意位置的 `day_plans_manifest.yaml` 必须报错测试。

## 共用私有函数

- 日计划：`_parse_freeze_event_bytes()`、`_parse_day_plans_manifest()`；位置判断使用
  `_is_day_plan_manifest_path()`。
- RoutePlan：`_parse_manifest_bytes()`、`_read_entry_bytes()`、`_load_entry_from_bytes()`。
- ReviewShardStore：`_load_items()`。

## 定点变异结果

每次均用 `apply_patch` 暂时改一个实现点，运行单个对应测试，记录失败后立即用 `apply_patch` 还原；
最终实现没有保留变异代码。

1. 在 `_read_current_plans()` 对同一 manifest 再调用一次 `read_bytes()`。运行
   `DayPlanSourcesTests.test_each_month_manifest_is_read_once`：退出码 1，1 项失败；计数断言实际值
   为 2、期望为 1。
2. 暂时跳过 `_is_day_plan_manifest_path()` 判断。运行
   `DayPlanSourcesTests.test_misplaced_day_plan_manifest_is_rejected`：退出码 1，1 项失败；测试报告
   `StorageError not raised`。
3. 在共享 `_load_entry_from_bytes()` 暂时关闭摘要不匹配判断。运行
   `TestRoutePlanStore.test_tampered_revision_is_rejected`：退出码 1，1 项失败；测试报告
   `StorageError not raised`。

## 验收输出

运行任务书指定命令：

```text
py -3.12 -m unittest tests.contract.test_state_sources_port tests.test_day_plan_store tests.test_storage tests.contract.test_route_plan_port tests.contract.test_availability_port tests.contract.test_freeze_port
```

结果：`Ran 76 tests in 48.138s`，`OK`。

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。未提交。
