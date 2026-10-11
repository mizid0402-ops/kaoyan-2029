# 第 222 轮任务书：WP-T2 课表接入 M26 / M8 / preflight / 输入包 / resume + `ky timetable` CLI（gpt-6-luna，续 luna-c）

## 背景

你上一轮（第 219 轮）做的 `ky/timetable/` 已由决策者按规格修订：`timetable_for_workspace(workspace)` 不再收配置，
`day` / `minutes_for` / `minutes_between` 的 `base_minutes` 改为**必填**（当日基数由 M8 传入，见 `contracts/timetable.md` §4 第 7 条）。
先 `git diff` 看一眼 `ky/timetable/calendar.py` 与 `tests/contract/test_timetable_port.py` 的变化，不要改回去。

规格以 `contracts/timetable.md` 为准（§6、§8 是本包范围）。`contracts/pacing_review.md` 是**以后**的 M28，本包**不实现**它，
只需保证本包的接口能让它将来接上（M8 先解析基数、再调 M26）。

## 要做的

1. **M26**（`ky/availability/port.py`、`contracts/availability.md`）：定义协议 `DerivedDailyMinutes`（`minutes_for(day, base_minutes) -> int | None`）；
   `resolve_daily_minutes(day, base_minutes, availability, timetable=None)`，优先级与 `source` 枚举按 `contracts/timetable.md` §6.1。
   M26 不 import M18。调用方全部跟着改签名（不留旧签名的兼容别名，`AGENTS.md`）。
2. **M8**（`ky/schedule/budget.py`、`contracts/route_plan.md` 的来源说明）：`resolve_day_budget(day, config, availability, route, timetable=None)`；
   基数 = `config.default_daily_minutes`（写成一个有名字的小函数，注释说明 M28 会在这里加路线与设置两级）；`DayBudget.total_source` 加 `timetable`。
3. **调用方**（`contracts/timetable.md` §6.2 的三步优先顺序，**冻结优先**）：
   - `ky/__main__.py` preflight：注册表里加载**一次**课表，同一对象传给预算解析；来源为 `timetable` 时在 `daily budget` 行后多打印一行
     （学期、第几周、星期；`follow` 时写"按 X 日的课"；大节数；空闲分钟；用到 `unconfirmed` 节次时加标记）。
   - `ky/planner/port.py` 日输入包：同一次加载；`availability` 字段在 `state.availability` 或 `state.timetable` 任一登记时给出对象；
     同步 `contracts/planner_port.md`（写明 `source` 为 `timetable` / `config` 时是参考基数，只有 `availability` 对应 M13 硬上限）。
   - `ky/freeze/resume.py` 与 `ky resume`：`plan_resume(..., timetable=None)` 把同一对象一路传到每个候选日的 `resolve_day_budget`。
   - **不改**：M13 `DayPlanStore` 的可用时间上限（只看手填）、M27 冻结阈值、M15 投影。
4. **CLI `ky timetable`**（`contracts/timetable.md` §8，全部行为照写）：`show --week N [--semester L]`、`show --date D`、`check`、`check --school FILE`；
   退出码：契约违约 2、用法错误 3（与现有子命令一致）。`show` 的基数用第 2 条的同一个函数取得。
   函数照 `AGENTS.md`：一个函数一件事，≤ 约 60 行，行宽 ≤ 100；网格打印拆成有名字的辅助函数。
5. **逐字节对照测试**（`AGENTS.md` 11–12a）：**未登记 `state.timetable`** 时，下面三条命令在同一份临时工作区上的 stdout / stderr / 退出码 / 写出的文件，
   与固定提交 **`e381792`** 逐字节相同：`ky preflight`（文本与 `--json`）、`ky planner-input --kind day`、`ky resume --dry-run`。
   用 `tests/_baseline_harness.py`（`fixed_source` 带身份断言、`compare_runs`）；旧版整个 `ky/` 取自该提交
   （例如 `git archive e381792 ky` 解到临时目录，用 `PYTHONPATH` 指向它运行 `py -3.12 -m ky`），并断言取到的确实是旧版
   （例如旧版 `ky/availability/port.py` 里 `resolve_daily_minutes` 的签名含 `config`）。
6. **新增测试**（只写这些）：
   - M26：三级优先（手填 0 也优先；课表给 0 也不是 None；课表 None 回落基数）。
   - M8：`total_source=timetable` 时总分钟与阶段配额缩放（sol 第 217 轮报告 §四示例：课表 75、hard 0.6 → 硬上限 45，两科各 30 → 23/22）。
   - preflight：课表来源时走 override + `drop_when_short`；冻结时仍 override 0 + `drop_when_short`；课表登记但当日在学期外 → `strict` 旧路径（sol 第 218 轮 R3 的三种情形）；多出的那一行文字。
   - M19：只登记课表时 `availability` 对象为 `{"minutes": 75, "source": "timetable"}`；学期外为 `config` 来源对象。
   - resume：同一课表对象跨多天使用、只加载一次。
   - M13：课表 75、日计划声明 200 → 允许；同日手填 90 时 200 → 拒绝。
   - CLI：§8 每条行为各一例（含多学期省略 `--semester` 退出 3、未登记课表 `show --date` 退出 0、`check --school` 不读注册表）。

## 不做

- 不实现 M28（设置文件、复盘报告、路线 v3、完成事件 v3、`base` 来源）。
- 不改 `kaoyan.workspace.yaml`、真实数据文件、`docs/模块地图.md`、README（决策者做）。
- 不改投影。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_timetable_port tests.contract.test_availability_port tests.contract.test_day_budget_port tests.contract.test_planner_port tests.contract.test_resume_port tests.contract.test_freeze_port tests.contract.test_route_plan_port tests.contract.test_day_plan_store_port tests.test_cli
```

写完含中文的文件查 `rg -n '\?\?\?' <文件>`。怀疑影响了其他模块时，在报告里列出模块名，不要自己跑全量。

## 报告

`review/rounds/round-222-m18-wiring-luna.md`：改动文件、每条要求的做法、测试输出原文、"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"、
你做了选择的歧义点（不要改规格）。
