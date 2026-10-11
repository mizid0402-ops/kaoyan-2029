# Round 120：WP-R1 修复 sol 118 B3 / B5 与建议 B2

基线提交：`6f91af13bc5118ef2242797f088df51b6be9935c`（worktree 起点）。未提交。

## 落点

- **B5 / M13：** `ky/storage/day_plan_store.py` 新增 `write_freeze_record(day, status_mapping)`、
  `write_resume_record(day, mapping)`、`freeze_records()`、`resume_records()`。记录写入
  `<store>/freeze/freeze--<D>.yaml` 或 `<store>/freeze/resume--<D>.yaml`，采用一次写入、
  临时文件重读校验后原子替换。读取时校验记录格式、文件位置及文件名日期与内容日期；
  第二次写入同一天记录会拒绝。
- **B5 / M27：** `ky/freeze/port.py` 增加 `latch_active(freeze_days, resume_days)`，并给
  `assess_freeze`、`FreezeStatus`、冻结 payload 增加 `latched`。相同日期恢复即解除；早于
  冻结日期的恢复不解除。
- **冻结记录写入方：** `ky/__main__.py` 中 `day-plan record` 在写完成事件及推进队列前，
  按事件日期检查注册队列；达到阈值且没有活动锁存时先写冻结记录，之后仍照常记录。
  `day-plan submit` 注入 M13 gate；最终计划对象通过不变量和 availability 检查后，gate
  按计划日期读取队列与记录，必要时先写冻结记录，再以 `StorageError` 拒绝提交。没有可用
  注册表时不注入 gate。preflight 与 `ky/planner/port.py` 的 M19 输入生成仅读取记录。
- **B3：** 删除 CLI 对提案路径的单独预读；`DayPlanStore.write_day_plan` 在落盘前及临时文件
  重读后都调用 `freeze_gate`，第二次使用重读计划的日期。
- **B2：** 冻结时 preflight 文本显示 `review soft / hard : 冻结期间不生效`，且省略
  `timeline phase` 行。JSON 的未冻结形状不变。
- **规格和测试：** `contracts/freeze.md` 说明锁存、记录格式、写入时机、只读路径与解除规则；
  回归测试仅新增在 `tests/contract/test_freeze_port.py`。测试基线使用上述完整提交哈希，且
  断言取到的是旧版无锁存实现。

## 撤修复敏感性

以下均做了临时反向修改，观察到对应测试失败后立即恢复：

- 关闭 M27 的 `latched` 判定，
  `test_record_latches_freeze_until_a_resume_record` 因 preflight 无 `freeze` payload 失败。
- 移除 M13 写前与临时文件重读时的 gate 调用，
  `test_freeze_gate_checks_the_final_plan_day_before_writing` 因未抛冻结错误失败。
- 单独恢复旧 soft/hard 行或单独恢复 timeline phase 输出，
  `test_frozen_text_marks_review_limits_inactive_and_hides_timeline_phase` 分别因对应断言失败。
- 把恢复边界从 `R >= F` 改为 `R > F`，
  `test_latch_active_resume_boundaries_and_multiple_cycles` 在 `R == F` 断言失败。
- 移除冻结/恢复记录的一次写入检查或读取路径检查，
  `test_freeze_and_resume_records_are_write_once_and_path_checked` 分别因未拒绝重复写入或
  未拒绝错位记录失败。

未冻结 JSON、文本与 planner 输入的逐字节对照测试固定读取基线提交；旧版入口断言确认其含
冻结阈值功能、但没有 `latch_active`。测试通过时输出保持一致。

## 验收

执行：

```text
py -3.12 -m unittest tests.contract.test_freeze_port tests.test_day_plan_store tests.contract.test_planner_port tests.test_cli
```

结果：`Ran 99 tests ... OK`。

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。

## WP-R2 接口

R2 调用 `DayPlanStore(<registered state.plans>).write_resume_record(day, mapping)`。`day` 是
恢复生效日期；`mapping` 是由 R2 定义的恢复审计信息映射。M13 写入一次：

```yaml
schema_version: 1
day: YYYY-MM-DD
resume:
  # R2 提供的恢复信息
```

文件路径为 `<state.plans>/freeze/resume--<D>.yaml`。同一天再次写入会抛 `StorageError`；
`resume_records()` 返回经过路径与日期校验的日期元组。任一 `R >= F` 的恢复记录解除对应冻结。
