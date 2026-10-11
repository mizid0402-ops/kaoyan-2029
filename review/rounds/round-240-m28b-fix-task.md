# 第 240 轮任务书：WP-M28b 返工（gpt-6-luna，续 luna-b，同一 worktree `F:\workspace\kaoyan-wt-m28b`）

sol 第 239 轮评审 FAIL，报告：`F:\workspace\kaoyan-ai-system\review\rounds\round-239-m28b-review-sol61.md`。决策者已核实三条必须改都成立。
决策者在你交付后做过两处格式修正（拆出 `ky/schedule/planning.py` 的 `_check_phase_base`、`budget.py` 折行），保留它们。

## 要改的

1. **B1**：`ky/planner/port.py` 的 `_availability_mapping` 在登记参数为真时输出 `DayBudget` 的实际 `base_minutes` 与 `base_source`（基数 0、`pacing_initial`、`config` 都照实）；
   为参数补 `DayBudget` 类型。修正对应测试断言，并把 `contracts/planner_port.md`、`contracts/route_plan.md` 里"nullable"的措辞改成"登记时为解析出的实际值"。
2. **B2**：`ky timetable show` 不读当前时间；读一次当前路线（`state.routes` 已登记时），`--date` 按该日、`--week` 按周一至周日逐日调用 M8 `daily_base_minutes`
   解析基数，再传给 `timetable.day`；复盘设置仍传 `None`。不改 M18、M26。
3. **B3**：补任务书已点名、报告第一节列出的验收：
   - preflight 与 M19 在 `total_source=base` 时走 override + `drop_when_short`，冻结仍优先（误删 base 分支会让测试失败）；
   - `ky resume` 跨两个阶段、基数不同时逐日取基数（例如 180 / 240），把首日基数套到后续日期会让测试失败；
   - 路线有效但课表当日返回 `None` → 基数 210、来源 `base`；
   - 固定基线的旧版身份断言改为检查**确有差异**的旧文件：旧 `ky/schedule/budget.py` 的 `daily_base_minutes` 只有一个参数、旧 `ky/schedule/planning.py` 的 `Phase` 没有 `base_daily_minutes`，
     并与 `git archive` 取出的源码是同一提交。
   - B1、B2 各补一例。
4. 建议改里便宜的一并做：规格里仍写"固定 v2""不从路线读取总分钟"的旧句直接改掉或写明覆盖关系；`timetable.md` 里"M26 fallback reports total_source: base"改为"M8 改写"；
   `PacingInitial` 列入 `budget` 的公开接口说明、用只读属性声明；`daily_base_minutes` 对新参数先校验（日期类型、非负整数、排除布尔）再运算。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_route_plan_port tests.contract.test_day_budget_port tests.contract.test_availability_port tests.contract.test_planner_port tests.contract.test_resume_port tests.test_planning tests.test_cli
```

报告追加到同一 worktree 的 `review/rounds/round-235-m28b-base-luna.md` 末尾一节"第 240 轮返工"：逐条做法、测试输出原文、"全量：未跑"。不提交。
