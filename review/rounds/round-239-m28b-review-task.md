# 第 239 轮任务书：WP-M28b 实现评审（gpt-6.1-sol，续 sol61-m28）

## 范围

worktree `F:\workspace\kaoyan-wt-m28b`（分支 `wip/m28b`，基于 `dcbb5b6`）里未提交的改动：路线 v3 `base_daily_minutes`、M8 基数三级解析与 `base` 来源、
preflight / M19 / resume 的调用方、四份规格的来源措辞。实现者报告在该 worktree 的 `review/rounds/round-235-m28b-base-luna.md`；
决策者另做了两处格式修正（拆出 `_check_phase_base`、折行）。任务书 `F:\workspace\kaoyan-ai-system\review\rounds\round-235-m28b-base-task.md`。
在该 worktree 里用 `git diff` 看改动。

## 请判断

1. 是否符合 `contracts/pacing_review.md` §5、§8（路线 v3 部分）、§9 与第 233 轮你列出的端口细节（尤其 `total_source=base` 只在回落时改写、手填与课表来源不被覆盖、逐日解析）。
2. 逐字节对照：是否固定 `dcbb5b6`、断言取到旧版、覆盖三种路线状态与所列命令；有没有漏掉的日常路径。
3. 与 M18 / M26 的接缝（不改 M18、M26）；`ky timetable show` 仍用配置基数（实现者说明的选择）是否与规格冲突。
4. `AGENTS.md` 已知缺陷清单与 D7。

## 可以运行

只跑与结论直接相关的单个模块或单条命令（在该 worktree 里）；不跑全量。

## 输出

`F:\workspace\kaoyan-ai-system\review\rounds\round-239-m28b-review-sol61.md`（写在主仓库）：PASS / FAIL；必须改 / 建议改 / 不改；安全登记单列。

## 禁止

不联网；只写这一份报告；不修改其他文件；不读仓库外文件；不写个人数据。
