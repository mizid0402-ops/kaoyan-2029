# 第 235 轮任务书：WP-M28b 路线 v3 基础时长 + M8 基数解析（gpt-6-luna，窗口 luna-b，新会话，独立 worktree）

## 背景

规格 `contracts/pacing_review.md`（sol 第 233 轮 PASS；**以它为准**）。你在独立 worktree 里工作；主仓库另有人在改 `ky/timetable*`，另一个 worktree 在做 M28a（`ky/pacing/`、完成事件、M0）。
本包只做 §5（当日基数解析与裁剪 / 分配参数）与 §8 的"路线 v3"，以及 M19 日输入包的两个可选字段。**不建 `ky/pacing/`，不改完成事件，不改 `ky/workspace.py`。**

先读：`AGENTS.md`；`contracts/pacing_review.md` §5、§8、§9；`contracts/route_plan.md`；`contracts/timetable.md` §4 第 7 条、§6；`contracts/availability.md`；`contracts/planner_port.md`；
代码 `ky/schedule/planning.py`、`ky/schedule/budget.py`、`ky/availability/port.py`、`ky/__main__.py`（preflight）、`ky/planner/port.py`、`ky/freeze/resume.py`。

## 要做的

1. **路线 v3**（`ky/schedule/planning.py`、`contracts/route_plan.md`）：阶段可选 `base_daily_minutes`（非负整数，排除布尔）。
   `route_plan_to_mapping` 在**没有任何阶段**带该字段时输出 v2 形状（`schema_version: 2`，阶段无此键），有则 v3（只在带值的阶段写此键）；0 是带值。
   解析接受 v2、v3；v2 中出现此键 → 违约。存储（`RoutePlanStore`）照旧。
2. **M8 基数解析**（`ky/schedule/budget.py`）：`daily_base_minutes` 改为按 §5 三级（路线阶段 `base_daily_minutes` > `settings.pacing` 的 `initial`（`d >= start`）> 配置），
   返回基数与 `base_source ∈ {route, pacing_initial, config}`。设置对象由调用方传入：本包定义一个最小的只读协议 / 数据类
   （`start: date`、`initial: int`），**不读文件**。本包里所有调用方（preflight、M19、resume）一律传 `None`；
   读取 `settings.pacing` 并把真实设置传进来是 M28c 的事。参数位要有名字、有类型，方便 M28c 接上。
   `DayBudget` 增加 `base_source`；`total_source` 加 `base`：M26 回落为 `config` 且 `base_source` 为 `route` / `pacing_initial` 时由 M8 改写为 `base`；手填、课表来源不被改写。
   M26 与 M18 **不改**。
3. **调用方**（preflight、M19 日输入包、`ky resume`）：裁剪 / 分配按 §5 扩展的三步——冻结 → override 0 + `drop_when_short`；
   `total_source ∈ {availability, timetable, base}` → override = total + `drop_when_short`；`config` → 旧路径。逐日调用 M8（resume 跨日搜索每天各自解析），不用首日基数套整段。
   M19 日输入包 `availability` 对象：在 `settings.pacing` 登记时多 `base_minutes`、`base_source` 两键（本包的装配层里设置恒为 `None`，所以这条只需按参数实现并用单元测试覆盖）。
4. 同步 `contracts/availability.md`、`contracts/route_plan.md`、`contracts/timetable.md` §6.1 / §6.2 的来源措辞（以 `contracts/pacing_review.md` §5 为准）。

## 逐字节不变（`AGENTS.md` 11–12a）

路线无 `base_daily_minutes`、设置为 `None` 时：`ky preflight`（文本与 `--json`）、`ky planner-input --kind day` 与 `--kind route`、`ky resume --dry-run`、`ky route show`（如有）
与固定提交 **`dcbb5b6`** 逐字节相同，覆盖"无路线 / 路线已登记未开始 / 路线进行中"三种工作区（用 `tests/_baseline_harness.py`，断言取到旧版；只用主注册表登记）。

## 测试（只写这些，全部合成数据）

- 路线：v2 读写不变；带值写 v3、0 也写 v3；v2 带此键拒绝；往返。
- M8：三级优先与 `base_source`；`total_source=base` 的改写只在回落时发生；sol 第 230 轮报告 §三构造例（路线基数 210 → 课表日 165；无路线 initial 180 → 135；同日手填 90 → 90；学期外 210 / 180，来源 base）。
- 调用方：`base` 来源走 override + `drop_when_short`；冻结优先；resume 跨阶段逐日基数不同。
- 上一节的逐字节对照。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_route_plan_port tests.contract.test_day_budget_port tests.contract.test_availability_port tests.contract.test_planner_port tests.contract.test_resume_port tests.test_planning tests.test_cli
```

写完含中文的文件查 `rg -n '\?\?\?' <文件>`。报告 `review/rounds/round-235-m28b-base-luna.md`（写在 worktree 里）：改动、做法、测试输出原文、
"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"、歧义与选择。不提交。
