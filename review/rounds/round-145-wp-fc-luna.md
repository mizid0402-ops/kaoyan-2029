# Round 145 — WP-F-c implementation report (`luna-c`)

## F-b 验收补强

### 改动

- `tests/contract/test_learning_state_projection.py`：补充投影 `review_items` 与写后队列对象
  的逐列核对，包含 `state`、revision、到期日、上次复习日、全部 `schedule_*` 字段、
  defer 与反馈字段。`day-plan record --review-store` 和 `ky resume` 各自保存写前对象，
 并断言写后推进字段确实改变；resume 同时继续核对投影恢复事件。
- 辅助断言直接按 `review_id` 从投影查询，避免只凭队列重读断言重建结果。

### 定点变异

临时将 `ky/projection/learning_state.py` 的投影 `due_date` 写值替换为常量
`"1900-01-01"`，执行：

```text
$env:PYTHONDONTWRITEBYTECODE='1'; py -3.12 -m unittest tests.contract.test_learning_state_projection.LearningStateProjectionTests.test_real_cli_writes_are_visible_after_rebuild
```

实际结果：失败，`_assert_projected_review_item` 在 `record` 之后发现投影日期为
`1900-01-01`，而写后队列为 `2026-10-01`。变异已撤销。

### 本节验收

第一部分包含在最终验收命令中；该命令通过，共 `Ran 25 tests in 9.753s / OK`，完整输出见
F-c 的最终验收小节。

## F-c 按日期查询端口

### 改动落点与接口

- `ky/schedule/state_snapshot.py`：新增冻结数据类 `ReviewCounts` 和纯函数
  `count_review_items_by_subject(items: Sequence[ReviewItem], day: date) -> Mapping[str, ReviewCounts]`。
  `queued`、`scheduled` 计入队列数；今日到期与积压分钟只计 `queued`，边界沿用原规则。
  `build_snapshot` 调用该函数，继续按配置科目顺序保留零值行。
- `ky/projection/status.py`：新增
  `status_as_of(projection_path, day, config, policy=FreezePolicy()) -> StatusAsOf`，只读打开
  schema 3 数据库。逐列重建 ReviewItem 并经 `validate_review_item`、
  `validate_items_against_config` 校验；调用 M12 计数与 M27 `latch_active` / `assess_freeze`。
  读取当天计划、完成事件存在标志、可用分钟与匹配路线阶段。
- `status_to_mapping(status: StatusAsOf) -> dict[str, object]` 是唯一 JSON 映射接口。
  顶层为 `as_of`、`subjects`、`freeze`、`day_plan`、`completion_event_exists`、
  `availability_minutes`、`route_phase`。冻结对象始终有 `frozen` 布尔；只有冻结时才含
  `resume`。缺日计划 / 阶段 / 可用分钟为 `null`，无完成事件为 `false`。
- `ky/projection/__main__.py`：新增
  `py -3.12 -m ky.projection status --date D [--config PATH] [--workspace W] [--json]`。
  显式 `--config` 优先；否则读 `settings.exam_config`。都缺失时返回契约错误，提示传入
  `--config` 或登记该键。原重建参数与输出路径保留。
- 规格与目录：`contracts/state_snapshot.md` 补 M12 计数接口；新增
  `contracts/projection_status.md`；`docs/模块地图.md` 仅更新 M12、M15 两行。
- 测试：新增 `tests/contract/test_state_snapshot_counts_baseline.py` 与
  `tests/contract/test_projection_status.py`；F-b 补强留在原投影契约测试中。

### `as_of` 与缺失语义

`as_of` 表示按日期 D 评估**最近一次成功重建**的投影事实，不是历史回放，也不承诺刚才的
写入已经反映到投影。冻结锁存根据投影中当前冻结事件序列计算，即使查询过去日期也使用当前
锁存；冻结阈值按本次传入的配置计算。文件缺失、schema 版本不是 3、查询所需表 / 列缺失或
数据库不可读时抛出带投影路径且要求重建的 `ContractError`，不会创建空库。配置外队列科目
经模型校验器拒绝。接口只读，不写状态，也不触发重建。

### 定点变异

- M12 变异：暂时将队列数条件从 `queued` 或 `scheduled` 改为仅 `queued`，用
  `PYTHONDONTWRITEBYTECODE=1 py -3.12 -m unittest tests.contract.test_state_snapshot_counts_baseline.StateSnapshotCountsBaselineTests.test_snapshot_json_matches_pinned_m12_with_date_boundaries`
  执行。实际失败：固定提交 `b867ae7` 的快照与新快照不等，`in_review_queue` 从 4 变为 3。
  变异已撤销。
- 冻结变异：暂时令 M15 `latched = False`，执行
  `PYTHONDONTWRITEBYTECODE=1 py -3.12 -m unittest tests.contract.test_projection_status.ProjectionStatusTests.test_counts_freeze_sequence_read_only_and_past_as_of`。
  实际失败：返回的 `FreezeStatus` 为 `frozen=False, latched=False`，与按三条序列事件计算的
  `frozen=True, latched=True` 不同。变异已撤销。
- schema 变异：暂时把 `_SCHEMA_VERSION` 改成 `"2"`，执行
  `PYTHONDONTWRITEBYTECODE=1 py -3.12 -m unittest tests.contract.test_projection_status.ProjectionStatusTests.test_missing_schema_and_out_of_config_queue_are_contract_errors`。
  实际失败：schema 2 fixture 未被 schema 检查拒绝，错误落到了后续“缺少表”，与测试要求的
  schema 版本错误不符。变异已撤销。
- 两个基线测试还会固定检查 `b867ae7` 的旧 M12 / 旧投影 CLI 源码确实来自该提交；旧、新
  M12 快照 JSON 字节相同，重建 CLI JSON 输出字节相同。最终验收通过。

### CLI 与输出形状

`--json` 输出 `status_to_mapping()` 的字段形状；不带 `--json` 输出日期、科目队列 / 到期 /
积压计数和冻结布尔。缺少配置时错误指明 `settings.exam_config` 并解释可用设置方式。
重建命令调用原有 `build_projection`，固定 `b867ae7` 输出对照通过。

### 最终验收

执行任务书指定命令：

```text
py -3.12 -m unittest tests.contract.test_learning_state_projection tests.contract.test_projection_status tests.contract.test_state_snapshot_counts_baseline tests.test_projection_service tests.contract.test_state_snapshot_port
```

```text
Ran 25 tests in 9.753s
OK
```

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。

### 留给后续工作的注意事项与建议

- 前端应把 `as_of` 展示为投影评估日期，并通过明确的重建 / 刷新流程获得新写入；运行中的
  `serve --immutable` 不会自动切换到新数据库，W2 刷新流程需另行约定。
- 显式 `--store` / `--items` 指向注册表外路径的写入不会进入该工作区投影；调用方需确保
  状态写入路径与注册表输入一致。
- 冻结字段描述当前投影事件锁存与按查询日、当前配置计算的阈值结果；不要把它解释成历史日
  的冻结回放。查询不包含建议、优先级或下一步任务。
