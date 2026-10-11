# 第 220 轮任务书：M28 周期复盘与调整规格——只审细则（gpt-6.1-sol，续 sol61-m18 会话）

## 背景

用户 2026-09-30 追加：基础学习时长 180–240 分钟只是基础，要一个模块让 AI 按"学 + 复习"模型，
依据每半月 / 每月的实际情况调整复习时间和方案。决策者起草了 `contracts/pacing_review.md`（§9 是用户原选项与决策者拟定项）。
同时 `contracts/timetable.md` 因此改了一处：课表上限缺省从"配置值"改为"M8 传入的当日基数"（见其 §4 第 7 条、§6.1、§7、§11 末段）。

本轮**只审规则本身**，还没有实现。

## 必读

`AGENTS.md`；`contracts/pacing_review.md`；`contracts/timetable.md`（改动处）；`contracts/route_plan.md`；`contracts/planner_port.md`；
`contracts/freeze.md`；`contracts/day_plan_store.md`；`contracts/review_progress.md`；`contracts/state_snapshot.md`（积压口径）；
代码 `ky/schedule/budget.py`、`ky/schedule/planning.py`（路线解析与 `validate_route_plan`）、`ky/schedule/completion.py`（完成事件版本）、
`ky/schedule/monthly_close.py`（现有月结，判断与本模块是否重复）、`ky/storage/route_store.py`。

## 请逐条判断

1. 与用户选项一致性（§9）；有没有把用户没选的东西塞进来；决策者拟定项是否合理。
2. 周期划分（§2）：给出具体设置与日期，检查边界（`until` 与 kind 的合法起点、月末、闰年 2 月、`start` 不在起点）。
3. 报告（§3）：每个字段是否都能**由现有数据确定性算出**；"队列没有历史快照"的处理是否够用；只写一次与重复运行语义。
4. 护栏（§5）：给出能绕过或误拒的具体方案；切开阶段的做法在"effective_from 恰是阶段起点 / 恰在最后一天 / 没有路线 / 路线尚未开始"时的结果；
   与 D10（用户自定义时间线）、D11（冻结与手动重启）是否冲突。
5. 接缝（§6）：路线 v3、完成事件 v3、M8 基数解析与 M18 课表基数的顺序；未登记设置时逐字节不变是否可达成；
   与现有月结（M11 `monthly_close`）是否重复、是否应复用。
6. 可维护性（D7）：模块边界、有没有更简单的等价设计。

## 输出

写到 `review/rounds/round-220-m28-pacing-spec-review-sol61.md`：PASS / FAIL；必须改（附具体输入、草案结果、应有结果）/ 建议改 / 不改；安全登记单列。

## 禁止

不联网；只写这一份报告；不跑测试；不读仓库外文件。
