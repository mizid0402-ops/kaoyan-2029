# 任务书：WP-E4 手填可用时间 `state.availability`（新模块 M26）

先读仓库根 `AGENTS.md`，再读：`contracts/workspace.md`（`state.availability` 为可选文件键、`write_target`）、`contracts/planner_port.md`（输入包 `availability` 字段）、
`docs/模块地图.md`、`ky/models.py`（`total_daily_minutes`、`load_yaml_text`）、`ky/schedule/review_clip.py`（`select_daily_reviews` 的 `daily_minutes_override`）、
`ky/schedule/longitudinal.py`（`DayPlan.available_minutes`、`check_invariants`）、`ky/storage/day_plan_store.py`（`DayPlanStore` 构造参数）、
`ky/planner/port.py`、`ky/__main__.py` 的 `preflight`、`planner-input`、`day-plan submit`。

你在 worktree `F:\workspace\kaoyan-wt-e4`（分支 `stage25/e4`，起点 `79623ee`）里工作，只改这个目录。下文"本包开始时的提交哈希"即 `79623ee`。

## 为什么做

"每天能学多少分钟"现在只有配置里一个固定的 `total_daily_minutes`。实际上考试周、假期、实习每天都不一样（路线图 ④ 课表协同的前置）。
本包先做**手填**：用户在一份文件里写"某天可用多少分钟"，系统在复习裁剪、规划输入包和日计划护栏里用它；没写的日子回落到配置值。

## 决策者已定的设计（照做；有更好的写法先在报告里提，不要自行改设计）

### 1. 文件格式与读取端（新模块 M26，`ky/availability/`，规格 `contracts/availability.md`）

- YAML：`schema_version: 1`（精确整数）、`days`（映射：`YYYY-MM-DD` → 非负整数分钟；键可为 YAML 日期或严格 ISO 字符串，`datetime` 拒绝；值拒绝 bool / 浮点）。顶层与格式错误都报契约错误并带路径（如 `days.2026-10-01`）。用 `ky.models.load_yaml_text`（重复键 fail-closed；注意同一天写成日期与字符串两种形式也算重复）。
- 公开接口（名字可调，写进规格）：`load_availability(path) -> Availability`；`resolve_daily_minutes(day, config, availability) -> DailyMinutes`，
  其中 `DailyMinutes` 有 `minutes` 与 `source`（`"availability"` 或 `"config"`）；`availability` 为 `None`（未登记）时一律 `config`。
- 注册表：`state.availability` **登记即必须存在**（不把"文件不存在"静默当空）；仓库注册表登记 `data/availability.yaml` 并提交一份 `schema_version: 1`、`days: {}` 的空文件。
  读取端从工作区取路径的辅助函数放 M26（例如 `availability_for_workspace(workspace) -> Availability | None`，未登记返回 `None`）。

### 2. 使用者

- **复习裁剪（M9 调用方）**：`ky preflight` 与 M19 输入包都经 `resolve_daily_minutes` 得到当日分钟；来源为 `availability` 时把它作为 `daily_minutes_override` 传给 `select_daily_reviews`，来源为 `config` 时**不传**（保证无手填时输出逐字节不变）。
  preflight 能加载注册表时（显式 `--workspace` 或向上发现）才读 availability；发现不到注册表且未给 `--workspace` 时按配置（照 E3b `--plan` 检查的写法）。
- **输入包 `availability` 字段**：`state.availability` 未登记 → `null`（与现在逐字节相同）；已登记 → `{"minutes": N, "source": "availability" | "config"}`。规格改掉"reserved for E4"。
- **日计划护栏**：`DayPlanStore` 增加可选参数（例如 `availability: Availability | None`），`write_day_plan` 在该日有手填值时要求 `day_plan.available_minutes <= 手填分钟`，违规报 `StorageError`（与 `check_invariants` 违规同一路径风格），什么都不写；无手填值不检查。
  `day-plan submit`（两种形式）由 CLI 从注册表取 availability 传入。**不改 `check_invariants`**（它刻意不看"每天多少分钟"）。

### 3. 规格与地图

`contracts/availability.md`（格式、接口、回落规则、谁在用）；`contracts/planner_port.md` 的 `availability` 字段；`contracts/workspace.md` 中 `state.availability` 行补"登记即必须存在，格式见 availability.md"；
`docs/模块地图.md` 新增 M26 一行，§4 缺口表删去 E4 一行。

## 不做的

- 不做区间 / 每周模板 / 课表导入（④）；只认逐日条目。
- 不改 `total_daily_minutes` 的名字（B6 另议）；不改 `_sort_key`、`check_invariants`。
- 不改月结与快照。

## 测试（只写这些）

新 `tests/contract/test_availability_port.py`：
1. 格式：合法文件读取；负例各一条（断言路径）：未知顶层键、`schema_version: true`、负分钟、浮点分钟、`datetime` 键、同一天日期键与字符串键重复。
2. `resolve_daily_minutes`：有手填 → `availability`；无该日 / 未登记 → `config`。
3. 注册表：登记但文件不存在 → 契约错误；未登记 → `None`。
4. preflight：该日有手填值时 `--json` 的容量字段按手填分钟；无手填时输出与改动前逐字节相同（对照固定到本包开始时的提交哈希，照 `AGENTS.md` 12a 断言取到的是旧版）。
5. 输入包：未登记时 `availability` 为 `null` 且包字节不变；已登记时字段值与来源正确；`review_clip` 仍等于同配置同工作区下 `ky preflight --json` 删去 `config`。
6. 护栏：手填 60 时提交 `available_minutes: 90` 的日计划被拒且不写；等于或小于时成功；该日无手填时不检查。
不写数据量字面量。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_availability_port tests.contract.test_planner_port tests.test_day_plan_store tests.test_cli tests.test_review_scheduler tests.contract.test_workspace
```

worktree 没有 `data/raw_materials/`；`tests.contract.test_workspace` 里依赖它的一项报缺目录属已知现象。

## 报告

`review/rounds/round-103-wp-e4-luna.md`（写在工作目录里）：改了哪些文件、每条设计的落点、逐字节对照的做法、验收输出、建议（包括你认为该不该让月结 / 快照也读 availability）。
写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。含中文的文件只用 `apply_patch` 编辑，写完查 `???`。
