# Round 55 WP-C2 实现报告

## 变更

- D8′：完成记录新增显式或按 `event.day#index` 派生的 `completion_id`。同一 review item 在同日可推进多次；已提交 ID 报告为 replayed 并跳过；较早补录仍推进，报告为 late，且 `last_reviewed_on` 不倒退。
- 分片 manifest 升至 schema v2，队列和已计算 ID 集由同一次 manifest 替换提交。schema v1 manifest 按空 ID 集读取。
- `day-plan record --review-store` 预检只拒绝队列里未知的 `review_id` 和事件内重复的 `completion_id`。
- D9：`KaoyanConfig.review_policy.self_rating_mode` 缺省为 strict，只接受 strict / lenient；`day-plan record` 将策略传入 `LadderSm2Algorithm`。lenient 对 unchecked unknown 缩为 1 天、vague 缩为半间隔（至少 1 天），保持 phase / ease / repetitions / lapses；basic / fluent / 无自评不拉长间隔，并通过推进报告标记 needs_check。
- 更新 `contracts/review_progress.md`，移除 D8 日期 / 质量去重和冲突规则，记录 D8′ 与 D9 行为矩阵。

## 验证

- 首次运行任务书指定的 8 个测试模块共 191 项，暴露 5 项失败。修正配置传递、unchecked 间隔更新、自动 ID 往返和旧迟到拒绝断言后，按仓库规则只重跑受影响模块。
- 最终 `tests.test_storage tests.test_review_queue_advance tests.test_cli tests.contract.test_review_progress_port`：55 项通过。
- 最终 `tests.test_day_plan_store`：16 项通过。
- 首次 191 项运行中，其他未受后续改动影响的指定模块通过，包括 `tests.test_completion`、`tests.test_contracts`、`tests.test_review_scheduler`。
- `py_compile` 对本轮 Python 实现文件通过；`git diff --check` 通过；本轮变更文件未发现连续问号乱码。
- 全量测试未跑（按仓库 AGENTS.md，由决策者提交前统一运行）。

## 范围与限制

- 未修改主工作区另行处理的 `ky/knowledge/`、`ky/projection/`、`ky/schedule/state_snapshot.py` 或 `tools/`。
- `needs_check` 作为 `ReviewQueueAdvanceReport.needs_check_review_ids` 输出，本轮没有接入 M24 出题流程。
- 未提交。
