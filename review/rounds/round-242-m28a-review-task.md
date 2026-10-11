# 第 242 轮任务书：WP-M28a 实现评审（gpt-6.1-sol，续 sol61-m28）

## 范围

worktree `F:\workspace\kaoyan-wt-m28a`（分支 `wip/m28a`，基于 `dcbb5b6`）里未提交的改动：M0 `settings.pacing`、完成事件 v3 `study_minutes`、`ky/pacing/`（设置、周期、报告、存储）、
`ky pacing report` CLI。实现者报告在该 worktree 的 `review/rounds/round-234-m28a-report-luna.md`；任务书 `F:\workspace\kaoyan-ai-system\review\rounds\round-234-m28a-report-task.md`。
在该 worktree 里用 `git diff` / `git status` 看改动。

## 决策者已发现、将随本轮一并返工的问题（请确认或补充，不必重复论证）

1. `ky/pacing/port.py` 的 `build_report` 107 行、`ky/pacing/storage.py` 的 `_validate_report` 79 行，超过 `AGENTS.md` 约 60 行的要求。
2. CLI 在既无 `--config` 也未登记 `settings.exam_config` 时回退到工作区根的 `kaoyan_config.yaml`：这是约定路径拼接，违反 `contracts/workspace.md` §1，应为契约错误。

## 请判断

1. 是否符合 `contracts/pacing_review.md` §2、§3、§8（完成事件 v3、M0）与第 233 轮你列出的细节：报告每个字段的口径（`reviews` 按 `completed_on`、重复 `completion_id`、
   `reviews_unattributed`、`recorded_event_days`、`backlog_observed`、`latched_at_end`、`due_next`、`previous` 只取紧邻周期、`report_hash`）、只写一次与重复运行语义。
2. 实现者自选的三处歧义（`source_note` 字段名、`sources` 含上一份报告、只列出现过的科目行）是否合理。
3. 逐字节对照：是否固定 `dcbb5b6`、断言取到旧版、覆盖所列命令；无 `study_minutes` 时完成事件文件是否逐字节不变。
4. `AGENTS.md` 已知缺陷清单（同一数据只读一次、只写一次文件、参数先校验等）与 D7。

## 可以运行

只跑与结论直接相关的单个模块或单条命令（在该 worktree 里）；不跑全量。

## 输出

`F:\workspace\kaoyan-ai-system\review\rounds\round-242-m28a-review-sol61.md`：PASS / FAIL；必须改（附可复现输入）/ 建议改 / 不改；安全登记单列。

## 禁止

不联网；只写这一份报告；不修改其他文件；不读仓库外文件；不写个人数据。
