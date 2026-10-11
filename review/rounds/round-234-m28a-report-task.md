# 第 234 轮任务书：WP-M28a 设置 / 周期 / 完成事件 v3 / 复盘报告（gpt-6-luna，窗口 luna-a，新会话，独立 worktree）

## 背景

规格 `contracts/pacing_review.md`（sol 第 220/221/230/233 轮审过，第 233 轮 PASS；**以它为准**，不改业务规则）。
你在独立 worktree 里工作（路径见派发命令的工作目录），分支已建好。主仓库另有人在改 `ky/timetable*`，与你无关。
本包做规格 §2（设置与周期）、§3（复盘报告与其存储、`ky pacing report`）、§8 中"完成事件 v3"与"M0 `settings.pacing`"两项。
**路线 v3、M8 基数解析（M28b）与输入包 / 护栏 / 提交（M28c）不做。**

先读：`AGENTS.md`；`contracts/pacing_review.md`；`contracts/workspace.md`（尤其 §2.6）；`contracts/state_sources.md`；`contracts/review_progress.md`；
`contracts/state_snapshot.md`（积压口径）；代码 `ky/workspace.py`、`ky/schedule/completion.py`、`ky/storage/day_plan_store.py`、`ky/storage/route_store.py`（只写一次发布）、
`ky/schedule/state_snapshot.py`、`ky/freeze/port.py`、`ky/planner/port.py`（`canonical_json_bytes`）。

## 要做的

1. **M0**（`ky/workspace.py`、`contracts/workspace.md`）：`settings.pacing` 为可选 F 键，`Workspace.pacing: Path | None`；本地补充文件 §2.6 允许键加入 `settings.pacing`
   （只增不改、未知 / 重复键拒绝、`local.` 错误路径、`local_sha256` 照旧）。
2. **完成事件 v3**（`ky/schedule/completion.py` 与写读完成事件的存储，`contracts/review_progress.md` 或其所在规格同步）：
   可选 `study_minutes`（非负整数，排除布尔）。**没有该值时仍写 v2（逐字节与现在相同）**，有值写 v3；v1 / v2 / v3 都可读，v1 / v2 读为 `None`；
   `day-plan record` 的输入格式接受该字段。填 0 是有效值。
3. **新模块 `ky/pacing/`**（模块头写 M28、规格、公开接口）：
   - 设置加载与校验（§2 表逐条；`until` 必须是月初；`start` 按首项 kind 校验；内部右开区间）；周期函数（给定日期所在周期；早于 `start` 返回 `None`；闰年 2 月）。
   - 报告纯函数 `build_report(...)` 与 `report_to_mapping()`（§3 表每个字段按其口径；`reviews` 按 `completed_on` 统计、`completion_id` 去重取最早 `event.day`；
     `reviews_unattributed`、`duplicate_completion_ids`、`recorded_event_days`、`backlog_observed`（M12 口径，观测日 = `T`）、`freeze.latched_at_end` 只看终日前事件、
     `due_next` 只计当前一轮、`previous` 只取紧邻上一周期已保存报告；`report_hash` 按 M19 规范 JSON 去掉自身字段）。
     `base` 与 `reference_minutes` 需要逐日基数：本包先用 `ky.schedule.budget.daily_base_minutes` 的**现有**签名（只取配置），
     并在报告映射里写明"按生成时来源重算"；M28b 会把基数解析换成 §5 的完整规则，届时报告自动跟上，不需要再改本包的公式。
   - 报告存储：`state.plans` 下 `pacing/report--<终日>.yaml`，临时文件 + 重读 + `os.link` 不覆盖发布；读时校验格式与 `report_hash`；
     同一周期再运行：不重写，打印已保存报告；本次重算的 `sources` 不同则多打印一行提示；退出 0。
4. **CLI `ky pacing report --cycle-end D [--today T] [--config C] [--workspace W]`**：`D` 须为周期终日且 `D < T`；`--today` 缺省取系统日期（只在 CLI 装配层取一次）；
   `settings.pacing` 未登记 → 违约。退出码：用法 3、契约 2、成功 0。装配层一次读取全部来源（`read_state_sources` 等），纯函数不读时间。

## 不做

路线 v3、`base_daily_minutes` 字段、M8 基数解析、`base` 来源、M19 字段（M28b）；输入包、方案、护栏、意图、恢复、`prompts/`（M28c）；
不改 `kaoyan.workspace.yaml`、不碰 `data/personal/`、不改 `docs/模块地图.md`。

## 逐字节不变（`AGENTS.md` 11–12a）

未登记 `settings.pacing`、完成事件不带 `study_minutes` 时：`ky day-plan record` 写出的完成事件文件、`ky preflight`（文本与 `--json`）、`ky planner-input --kind day`
与固定提交 **`dcbb5b6`** 逐字节相同（用 `tests/_baseline_harness.py`，断言取到旧版；工作区只用两版都能读的主注册表登记，不用本地补充文件）。

## 测试（只写这些，全部合成数据）

- M0：`settings.pacing` 主表与本地补充文件各能登记；与主表重复 → `local.settings.pacing`；未登记为 `None`。
- 设置：§2 表每条规则各一例拒绝；sol 第 220 轮报告 §三"周期边界核对"表每一行一例。
- 完成事件：无 `study_minutes` 写 v2 字节不变；有值写 v3；v1/v2/v3 读取；0 与缺失区分。
- 报告：§3 表每个字段至少一例（含补录按 `completed_on`、重复 `completion_id`、队列里找不到科目、终日后的冻结事件不计入 `latched_at_end`、
  `previous` 有缺口为 `null`、`report_hash` 排除自身）；只写一次与重复运行语义；`sources` 变化提示。
- 上一节的逐字节对照。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_pacing_port tests.contract.test_workspace tests.test_completion tests.contract.test_day_plan_store_port tests.contract.test_state_sources_port tests.test_cli
```

写完含中文的文件查 `rg -n '\?\?\?' <文件>`。报告 `review/rounds/round-234-m28a-report-luna.md`（写在 worktree 里）：改动、做法、测试输出原文、
"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"、歧义与选择。不提交。
