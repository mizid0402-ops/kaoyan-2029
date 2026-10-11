# 第 267 轮：掌握度第二版（A 真题门槛 + B 阶段目标）

## 改动

- M30：`item_level(item, past_question_passed)` 在稳定度 / 间隔达到 30 天时，只有真题答对过才给 `consolidated`；`subject_mastery` 接受已答对真题的复习项 ID 集合，并增加加权 `covered` 输出。`unknown_refs` / `tracker_refs` 保持知识点 ID，`excluded_refs` 保持复习项 ID。
- M30：`mastery_gap(subjects, today, route)` 改按路线阶段末的覆盖与巩固目标插值；早于起点为 0，晚于最后目标点取末值，无路线 / 无阶段目标分别返回 `missing_route` / `no_targets`。能力页不再读取复盘设置作为目标日期来源。
- M11 路线格式增加 schema v4 阶段 `targets`，验证精确整数范围、巩固不高于覆盖以及跨目标阶段不下降。无目标路线继续输出 v2 / v3。M28 pacing 原地替换保留目标，切段时目标跟随原阶段末端留在后半段。
- M17 能力页从一次读取的完成事件中筛选 `check == past_question` 且 `outcome == correct` 的复习项 ID；目标卡片改为覆盖和巩固两行，并分别说明缺少路线、路线尚无阶段目标。
- 更新对应的四个契约测试模块。未修改 README、模块地图、M10、M24、题库、`ky/__main__.py` 或 `ky/workspace.py`；并行工作区中的文件未触碰。

## 做法

档位门槛只由调用方给入的复习项 ID 集合判定，M30 不读取完成事件文件，也不推测检查类型。调用层读取 `state.plans` 一次并构造集合后传给 M30。覆盖值与能力值共用叶子权重分布，按未舍入的 `Fraction` 汇总。

路线阶段目标作为 `Phase.targets` 的可选映射进入 M11：只有存在目标时使用 schema v4；`base_daily_minutes` 仍按 v3 可选字段保留。阶段目标日期采用该阶段 `end_exclusive`，从 `(route.start_date, 0, 0)` 逐段线性插值。

在 `prompts/` 下搜索路线/阶段目标指引时，只找到 `pacing_review.md` 与题库提示文件，没有路线规划提示文件；因此没有把路线目标要求写入不相关的 M28 复盘提示。

## 测试

执行命令：

```text
py -3.12 -m unittest tests.contract.test_mastery_port tests.contract.test_route_plan_port tests.contract.test_pacing_port tests.contract.test_charts_port
```

测试输出原文：

```text
..........................课表不覆盖此日
............没有需要重排的积压
正在恢复提交
effective_from: 2026-10-16
base: 180 -> 180
review_minutes.cs408: - -> 20
review_minutes.eng1: - -> 20
review_minutes.math1: - -> 20
调整在 2028-12-23 日阶段结束后失效
生效日上限：2028-12-23（取自设置 exam_date）
有课表的日子，M8 仍会按当日容量缩放复习配额
rationale: adjust
evidence: report.cycle.end = "2026-10-15"
已完成上次中断的提交
......
----------------------------------------------------------------------
Ran 44 tests in 23.413s

OK
```

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）

## 歧义与选择

- 真题门槛由调用方预先给出 `past_question_passed` 集合，M30 仅检查复习项 ID 是否在集合中；只有 `past_question` 且结果为 `correct` 的事件会进入集合，exercise 等类型不会提升档位。
- v4 的阶段目标表示该阶段 `end_exclusive` 当天的目标值，边界日即采用前一段末目标；相邻两目标之间按日期线性插值。
- 当前 `prompts/` 没有路线规划提示文件，故无法按要求为该提示补句；发现的 `pacing_review.md` 是独立 M28 指引，没有改动。

未读取 `data/personal/`。未提交。
