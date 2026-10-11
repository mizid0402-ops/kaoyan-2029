# 第 253 轮任务书：M17 可视化规格**初检**（gpt-6.1-sol，新窗口 sol61-m17）

## 这一轮只做初检（用户 2026-10-01）

用户要求每包只做初检，彻底的大检查等全部工作做完后统一做。本轮：

- 只审规格 `contracts/charts.md` 本身（`AGENTS.md`"决策者细则先审再实现"），**不写代码、不跑测试**。
- 重点只看 §7 末尾列出的四条决策者自拟细则，以及规格是否与用户 §7 决议表一致、引用的现有接口名是否真实存在。
- 会让实现者做错或日常使用出错的写进"必须改"（附反例）；其他一律一行写进"留给最终大检查"，不展开、不判 FAIL。
- 报告约 40 行以内。

## 背景

- 需求 `review/requirements.md` §8.1、§8.2；前端范围 `docs/前端设计-范围与待定.md`；轮子调研 `review/rounds/artifacts/report-github-adoption.md`（plotly）。
- 现有接口：`contracts/timetable.md` §7（`TimetableCalendar.day`、`DaySchedule`）、`ky/timetable_io/preview.py` 的 `base_resolver`、
  `ky/schedule/budget.py` 的 `resolve_day_budget`、`contracts/review_progress.md`（完成事件 v3 `study_minutes`）、
  `contracts/state_sources.md`、`contracts/workspace.md`（`products` 映射）、`ky/knowledge/hierarchy.py`、`contracts/pacing_review.md` §3。

## 输出

`F:\workspace\kaoyan-ai-system\review\rounds\round-253-m17-spec-review-sol61.md`：PASS / FAIL；"必须改"（若有，附反例）；"留给最终大检查"。

## 禁止

不联网；只写这一份报告；不修改其他文件；不读仓库外文件；不写个人数据（`data/personal/` 与 gitignore 的学习状态都不读）。
