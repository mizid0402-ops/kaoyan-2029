# WP-E5a 实现报告

## 修改文件

- `ky/schedule/planning.py`：M11 改为 D10 可变时间线。新增 `Phase`，`RoutePlan.phases`
  覆盖 `[start_date, target_exam_date)`；验证阶段序号、起止日期闭合、标签与各科非负整数分钟。
  映射和解析使用严格 `schema_version: 2` 与新字段；schema 1 明确报错，提示旧 24 月格式已作废。
- `ky/storage/route_store.py`：未改存储事务实现。M13 读写仍统一调用 M11 的解析、映射和校验接口，
  因而比较并交换、锁、manifest、发布和回滚语义保持不变。
- `ky/__main__.py`：M14 文本展示逐段输出右开区间、标签和按科目 ID 排序的每日复习分钟；JSON
  继续使用唯一映射接口。
- `ky/planner/port.py`：M19 当前路线使用新映射；日输入包命中阶段时使用 `phase` 字段，区间仍为
  `[start, end_exclusive)`，考试日当天返回 `null`。无路线的代码路径未变。
- `contracts/route_plan.md`：重写格式与校验规则；存储、CLI、恢复规则保留并更新展示描述。
- `contracts/planner_port.md`：将日输入包路线命中字段从 `envelope` 更新为 `phase`。
- `docs/模块地图.md`：M11 职责改为“可变时间线（阶段起止 + 各科复习分钟）”。
- `tests/test_planning.py`：用时间线闭合、空阶段和复习分钟类型验证替代固定 24 月验证。
- `tests/contract/test_route_plan_port.py`：改为时间线构造，覆盖新映射、schema 1 的 D10 拒绝信息及文本展示。
- `tests/contract/test_planner_port.py`：辅助构造按起止日期和边界推导阶段；覆盖阶段边界选择和考试日 `null`。

## 公开名与用户可见格式调整

按 D10 和任务书的“不留兼容别名”要求，移除以下旧公开名：

- `ROUTE_PLAN_MONTHS`：固定月份数与可变阶段数冲突。
- `MonthEnvelope`：由新值类型 `Phase` 取代。
- `envelope_bounds`：按日历月推导边界的接口不再适用于任意日期区间。
- `RoutePlan.months`：改为 `RoutePlan.phases`。

旧序列化字段 `months`、`phase_label`、`projected_capacity_minutes`、`subject_weights`、
`channel_capacity_minutes`、`target_vocab_words` 一并从路线格式移除；阶段改用 `label` 与
`review_minutes`。schema 1 不迁移，解析时按 D10 返回可操作的重写提示。该删除是任务书明确要求，
也符合 AGENTS.md 的 D7：不保留兼容别名；D10 明确仓库没有已存路线且旧格式作废。

## 验收与撤实现验证

指定命令：

```text
py -3.12 -m unittest tests.test_planning tests.contract.test_route_plan_port tests.contract.test_planner_port tests.test_cli
Ran 98 tests in 19.881s
OK
```

- 撤去末段结束日期检查后，`test_last_phase_must_end_at_exam_date` 失败（未抛出 `RoutePlanError`）。
- 撤去相邻阶段起点检查后，`test_adjacent_phases_must_be_contiguous_and_non_overlapping` 中的间隙与重叠两例均失败。
- 恢复实现后重跑了上述全部指定模块，结果通过。
- `git diff --check` 通过；变更文件的乱码占位符扫描无命中。
- 全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。

## 给 E5b 的建议

- 从当天命中的 `[start, end_exclusive)` 阶段读取 `review_minutes`，使用当天实际在考科目集合检查缺项，
  缺少任何在考科目时显式报契约错误；格式层不要把配置科目 ID 写死。
- 复习分钟表示各科当天常规复习配额。若配额总和超过当天硬上限，按 D10 使用最大余数法按比例缩放；
  紧急项沿用现行超本科配额规则，但全天仍不突破硬上限。
- 保留优先级：单日手填可用时间控制总时长，阶段控制科目分配，配置仅在前两者缺失时回落。
- 没有路线或当天在路线外时，维持原行为的逐字节一致性；不要在本包提前改动
  `review_clip.py`、`budget.py` 或 preflight 裁剪逻辑。
