# 第 250 轮任务书：WP-M28c 实现评审（gpt-6.1-sol，续 sol61-m28）

## 范围

worktree `F:\workspace\kaoyan-wt-m28c`（分支 `wip/m28c`，含 M28a + M28b，基于 master `8eca5be`）里未提交的改动：复盘设置接线、`ky/pacing/input.py`（输入包）、
`ky/pacing/submit.py`（提交、意图、恢复、`--dry-run`）、`apply_pacing`、`RoutePlanStore.read_revision_context()`、`ky pacing status`、preflight 提醒。
实现者报告在该 worktree 的 `review/rounds/round-247-m28c-luna.md`；任务书 `F:\workspace\kaoyan-ai-system\review\rounds\round-247-m28c-task.md`。

## 已知、不在本轮

- master 已含 IO2（`1a7a4a7`，`ky/timetable_io.base_resolver` 等）；合并时由决策者把复盘设置接到 `base_resolver`。
- `ky/pacing/port.py` 的 `apply_pacing` 64 行，决策者合并时拆分。

## 请判断

1. 是否符合 `contracts/pacing_review.md` §4–§7、§9 与你第 233 轮列出的 6 条细节：先分流再校验、七条护栏、意图字段与一致性校验、两类摘要不混用、
   恢复三状态与 `--dry-run` 文案 / 退出码、路线转换五种情形、manifest 一次读、复盘设置在所有调用方接通、未登记设置时逐字节不变。
2. 实现者自选四处：`submit` 无 `--config` 而用登记的 `settings.exam_config`；缺 manifest 视为修订 0；JSON 模式的提醒写 stderr；未另造 resolver。是否合理。
3. `AGENTS.md` 已知缺陷（尤其第 1 条只写一次、第 2 条同一数据只读一次、中断可恢复）与 D7。
4. 测试是否有实质断言，覆盖任务书点名的用例。

只跑相关单个模块或单项（在该 worktree 里），不跑全量。

## 输出

`F:\workspace\kaoyan-ai-system\review\rounds\round-250-m28c-review-sol61.md`：PASS / FAIL；必须改（附可复现输入）/ 建议改 / 不改；安全登记单列。

## 禁止

不联网；只写这一份报告；不修改其他文件；不读仓库外文件；不写个人数据。
