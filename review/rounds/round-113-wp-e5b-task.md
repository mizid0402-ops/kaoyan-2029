# 任务书：WP-E5b 时间线各科复习分钟生效到每日复习裁剪（M8 / M9 / M14 / M19，决议 D10）

先读仓库根 `AGENTS.md`，再读：`docs/阶段2.5-接缝收口.md` 的 **D10**（本包依据，细则逐条照做）、`contracts/route_plan.md`、`contracts/availability.md`、`contracts/planner_port.md`、
`ky/schedule/budget.py`、`ky/schedule/review_clip.py`（`select_daily_reviews`、`ClipResult`、`preflight_to_mapping`、紧急规则、`unschedulable` 判定）、
`ky/schedule/planning.py`（`RoutePlan`、`Phase`）、`ky/storage/route_store.py`、`ky/availability/`、`ky/__main__.py` 的 preflight（`main`）、`ky/planner/port.py` 的 `_build_input_data` / `_registered_route_store`。

你在 worktree `F:\workspace\kaoyan-wt-e5b`（分支 `stage25/e5b`）里工作，只改这个目录。下文"基线提交"指本 worktree 的起点提交（`git -C F:\workspace\kaoyan-wt-e5b rev-parse HEAD`，在测试里写成完整哈希字面量，照 `AGENTS.md` 12a 断言取到的是旧版）。

## 为什么做

D10：用户在时间线每个阶段写"各科每日复习分钟"，并要求**直接生效**到每天的复习安排。E5a 已换好格式；本包让它真正决定 `ky preflight` 与规划输入包里的复习裁剪。

## 决策者已定的设计（照做；有更好的写法先在报告里提，不要自行改设计）

### 1. 当日预算解析（M8，`ky/schedule/budget.py`）

新增公开值类型与函数（名字可调，写进规格）：`DayBudget`（`total_minutes`、`total_source`（`"availability"` / `"config"`）、`subject_review_quotas: Mapping[str, int] | None`、`phase_index: int | None`、`route_revision: int | None`）；
`resolve_day_budget(day, config, availability, route) -> DayBudget`：
- `total_minutes` / `total_source` 沿用 M26 `resolve_daily_minutes`（手填优先，回落配置）。
- `route` 为 `None`，或 `day` 不在任何阶段 `[start, end_exclusive)` 内 → `subject_review_quotas = None`（与现在逐字节一致的路径）。
- 命中阶段时：键必须是配置里的科目 ID（未知科目 → `ContractError`，路径 `route.phases[i].review_minutes.<id>`）；**每个在考科目都必须出现**（缺 → `ContractError`，消息写明"时间线阶段 i 缺少在考科目 <id> 的复习分钟"）；不在考科目写了 >0 分钟 → `ContractError`（提示先在配置启用它），写 0 或不写都可。
- 当天复习硬上限 `H` = 以 `total_minutes` 为基的 `hard_max_ratio` 取整（与 `select_daily_reviews` 现有算法同一函数，不要另写一份）。在考科目配额之和 ≤ `H` → 原样；> `H` → 按配额比例用精确有理数最大余数法缩到恰好 `H`（复用本模块 `_proportional_split` 或与之同等的公开实现，确定性、同分按科目 ID 排序）。

### 2. 裁剪（M9，`select_daily_reviews`）

- 新关键字参数 `subject_review_quotas: Mapping[str, int] | None = None`；为 `None` 时行为与结果**逐字节不变**。
- 给定时：按现有优先级顺序逐项处理；普通项需同时满足"本科已用 + 成本 ≤ 本科配额"与"全天已用 + 成本 ≤ 当天硬上限"；**紧急项**（沿用 `_is_urgent`）可以超出本科配额，但仍须"全天已用 + 成本 ≤ 当天硬上限"。放不下的进 `deferred`（沿用延期语义）。`unschedulable` 规则不变（成本 > max(配置硬上限, 当日硬上限)）。
- `ClipResult` 的 `soft_target_minutes` 在给定配额时 = 配额之和；新增只在给定配额时才出现的信息（例如 `subject_review_quotas`、各科已用分钟）。`preflight_to_mapping` 仅在有配额时输出这些新键，**无配额时 JSON 字节不变**。

### 3. 使用者（M14 preflight、M19 输入包）

- 两处都改为调用 `resolve_day_budget`，把 `daily_minutes_override`（仅手填来源时，规则不变）、`subject_review_quotas`、`floor_policy`（规则不变）传下去；不要在两处各写一份解析逻辑。
- preflight 取路线：能找到注册表（`_discovered_workspace`）且登记了 `state.routes` 时读 `RoutePlanStore.current()`；否则 `None`。
- 输入包 `review_clip` 仍须等于同配置同工作区 `ky preflight --json` 删去 `config`。
- preflight 文本：有配额时增加一行列出当日所在阶段与各科配额（格式自定，写进规格）；无配额时文本逐字节不变。

### 4. 规格

`contracts/route_plan.md` 增"生效规则"一节（D10 细则全文照录并对应到函数）；`contracts/availability.md` 与 `contracts/planner_port.md` 相应一句；`docs/模块地图.md` M8 / M9 行更新。

## 不做的

- 不改 E5a 的格式与存储；不改日计划护栏（`check_invariants`、availability 上限）。
- 不按阶段改新内容分配的科目权重（仍用配置权重）。
- 不改紧急判定阈值与排序键。

## 测试（只写这些，放 `tests/contract/test_route_plan_port.py` 或新 `tests/contract/test_day_budget_port.py`，二选一并说明）

每条都要在撤回对应实现时变红（报告里写怎么验证的）：
1. 无路线、当天在时间线外：preflight `--json` 与文本、输入包字节与基线提交一致。
2. 命中阶段：各科只在本科配额内入选普通项；某科配额 0 时该科普通项全部延期；紧急项可超出本科配额但全天不超过硬上限。
3. 配额之和 > 当天硬上限：缩放后之和恰为硬上限、确定性（重复两次相同）。
4. 手填可用时间 + 阶段同时存在：总时长取手填、分科取阶段。
5. 缺在考科目、未知科目、不在考科目 >0：各报契约错误（preflight 退出 2、无 traceback）。
6. 输入包 `review_clip` 与 preflight `--json` 一致（有配额时）。
不写数据量字面量。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_route_plan_port tests.contract.test_availability_port tests.contract.test_planner_port tests.test_review_scheduler tests.test_contracts tests.test_cli
```

worktree 没有 `data/raw_materials/`；依赖它的用例报缺目录属已知现象。

## 报告

`review/rounds/round-113-wp-e5b-luna.md`（写在 worktree 里）：改了哪些文件、每条设计的落点、逐字节对照做法、验收输出、建议。
写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。含中文的文件只用 `apply_patch` 编辑，写完查 `???`。
