# 第 263 轮任务书：M30 掌握度 + 能力画像页 实现**初检**（gpt-6.1-sol，续 sol61-m17）

## 只做初检（用户 2026-10-01）

- 只核对实现是否落实 `contracts/mastery.md` 与 `contracts/charts.md` §8，以及你第 259 / 261 轮提过、已写进规格的点（M1 权重开关、M2 目标差距边界、M3 遗忘次数输出、FSRS 稳定度分档）。
- 每项最多 1 个合成探针；不通读全部代码、不找新测试缺口、不评视觉。日常会算错 / 崩溃的写"必须改"（附输入），其他一行进"留给最终大检查"。报告约 50 行。

## 范围

主仓库未提交改动：`ky/mastery/`、`ky/knowledge/hierarchy.py`（新增 `learnable_tree`）、`ky/charts/`（`ability_chart_data`、`render_ability`、`ky chart ability`）、`ky/workspace.py`（`weighted_mastery`）、
`kaoyan.workspace.yaml`、相关测试与文档。任务书 `review/rounds/round-260-m30-task.md`；实现者报告 `review/rounds/round-260-m30-luna.md`。
决策者改过（不必复查）：能力页四张卡片的口径说明合并为页首一句，各卡片换成各自的短说明。

## 验证

只跑 `py -3.12 -m unittest tests.contract.test_mastery_port tests.contract.test_charts_port`，外加探针（系统临时目录，`PYTHONDONTWRITEBYTECODE=1`）。不跑全量。

## 输出

`F:\workspace\kaoyan-ai-system\review\rounds\round-263-m30-review-sol61.md`：PASS / FAIL；必须改；留给最终大检查。

## 禁止

不联网；只写这一份报告；不改其他文件；不读 `data/personal/`、`outputs/` 与 gitignore 的学习状态。
