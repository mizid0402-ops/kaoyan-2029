# 每日复习裁剪端口（M9）

本规格描述 `ky/schedule/review_clip.py`，按 2026-09-27 的代码如实写出（WP-S1，不改行为）。
预算从哪里来见 `contracts/config.md`（M8）；时间线阶段配额的来源见 `contracts/route_plan.md`；
手填可用时间见 `contracts/availability.md`；冻结见 `contracts/freeze.md`。

裁剪是纯函数：不读时钟、不取随机数、不做 IO，不修改传入的复习项。同样输入重放一天，
输出逐字节相同。

## 1. 对外接口

| 接口 | 作用 |
|---|---|
| `select_daily_reviews(config, items, today, *, seven_day_usage=None, policy=None, daily_minutes_override=None, subject_review_quotas=None) -> ClipResult` | 从到期项中选出今天做的复习 |
| `ReviewPolicy(urgent_overdue_days=3, urgent_defer_count=2)` | 紧急阈值（与 `ky.models.ReviewPolicy` 同名不同类） |
| `ClipResult` | 一天的裁剪结果（§5） |
| `ClipResult.summary() -> dict` | 结果的稳定 JSON 映射（§6） |
| `preflight_to_mapping(config, result, allocations) -> dict` | `ky preflight --json` 与 M19 共用的唯一 JSON 形状（§6） |

`ReviewPolicy` 两个阈值都必须 `>= 1`，否则构造时抛 `ValueError`。

## 2. 输入

| 参数 | 规则 |
|---|---|
| `config` | M8 校验过的 `KaoyanConfig` |
| `items` | 复习项元组或列表；`review_id` 唯一性由加载器保证，本函数不再查 |
| `today` | 调用方给的日期 |
| `seven_day_usage` | 科目 → 最近 7 天已用分钟；缺省或缺科目按 0；不设上限 |
| `policy` | 缺省 `ReviewPolicy()` |
| `daily_minutes_override` | 当天总分钟；`None` 时用 `config.default_daily_minutes` |
| `subject_review_quotas` | 科目 → 当天常规复习配额（D10）；`None` 表示按配置比例 |

入口检查，按顺序，第一处失败即抛出：

1. `validate_items_against_config`：复习项的 `subject_id` 不在配置里，或指向未启用科目 →
   `ContractError`，路径 `items[<序号>].subject_id`。
2. `daily_minutes_override < 0` → `ValueError`（不是 `ContractError`）。
3. 给了配额时，逐键：不是**在考**科目（包括值为 0 的未启用科目）→
   `ContractError("unknown or inactive subject ID", "subject_review_quotas.<id>")`；值不是
   `int`（布尔值、字符串、浮点都算不是）或 `< 0` →
   `ContractError("minutes must be a non-negative integer", "subject_review_quotas.<id>")`。
4. 配额之和大于当天硬上限 → `ContractError(..., "subject_review_quotas")`；配额必须先经
   M8 `resolve_day_budget` 缩放。配额可以不列出某个在考科目，缺的科目配额按 0。

## 3. 容量

记 `total = daily_minutes_override`（给出时）否则 `config.default_daily_minutes`：

- **硬上限** `hard_cap = hard_review_cap_minutes(total, config.hard_max_ratio)`（M8 共用函数）。
- **软配额** 无配额时 `soft_target = scale_minutes(total, config.review_reserve_ratio)`；
  有配额时 `soft_target = sum(配额)`，按科生效（§4.3）。
- **拆分门槛** `unschedulable_cap = max(config.review_hard_cap_minutes(), hard_cap)`：单项耗时
  严格大于它才算"必须拆分"。当天手填时间更短只会让该项今天延期；更长则可能排得下
  （sol 第 107 轮 C2、第 109 轮 N1）。不给覆盖值时两者相等。

不给覆盖值时，上述数值与 `config.review_target_minutes()` / `config.review_hard_cap_minutes()`
逐字节一致。

## 4. 选择规则

### 4.1 候选与优先级

候选是 `state == "queued"` 且 `due_date <= today` 的项。候选按下列八级键升序排成全序
（靠前的先考虑）：

| 级 | 键 | 含义 |
|---|---|---|
| 1 | `-(today - due_date).days` | 逾期越久越先 |
| 2 | `-defer_count` | 延期次数越多越先 |
| 3 | `-schedule.lapses` | 遗忘次数越多越先 |
| 4 | `-科目落后率` | 最近 7 天越落后的科目越先 |
| 5 | `due_date` | 与第 1 级等价，实际上不会单独起决定作用 |
| 6 | 类型优先级 | `concept`=`procedure`=0 < `question_pattern`=1 < `error_pattern`=2 < `vocabulary_batch`=3（其他值 99） |
| 7 | 自评 | `unknown`=0 < `vague`=1 < `basic`=2 < `fluent`=3 < 无自评=4 |
| 8 | `review_id` | 字符串升序，保证全序 |

科目落后率 `= (target - actual) / target`，`target = Fraction(str(weight)) ×
config.default_daily_minutes × 7`，`actual = seven_day_usage.get(科目, 0)`；`target <= 0` 时为 0。
全程用 `Fraction`，不转 `float`：巨大的预算或用量不会溢出，也不会把两个很接近的科目舍入成
同一名次。排序**只读配置的** `default_daily_minutes`，不读 `daily_minutes_override`，所以覆盖值只改
容量、不改名次。

自评只在前六级全部相同时才起作用；它不改 `due_date`、间隔或质量（硬不变量③）。

**紧急项**：`(today - due_date).days >= policy.urgent_overdue_days` 或
`defer_count >= policy.urgent_defer_count`。

### 4.2 无配额时（按配置比例）

按优先级逐项考虑，记已用分钟 `used`：

1. 耗时 `> unschedulable_cap` → `unschedulable`，继续下一项；
2. `used + 耗时 > hard_cap` → 延期；
3. `used + 耗时 > soft_target` 且不是紧急项 → 延期；
4. 否则入选，`used += 耗时`。

是"逐项能放就放"：某项放不下被延期后，排在后面的更小的项仍可入选。紧急项不插队，只是在
软配额用完后仍可借用到硬上限。

### 4.3 有配额时（D10，两遍）

先把耗时 `> unschedulable_cap` 的项放进 `unschedulable`，其余按是否紧急分两组（组内保持优先级）。

- **第一遍**：先全部紧急项、再全部普通项，逐项：本科已用 + 耗时 `<=` 本科配额，且全天
  `used + 耗时 <= hard_cap` 时入选。否则紧急项进入等待表，普通项延期。
  （只按优先级会让逾期更久的普通项排在同科紧急项前，sol 第 116 轮 B1。）
- **第二遍**：等待表中的紧急项按优先级逐项，`used + 耗时 <= hard_cap` 时入选，否则延期。
  紧急项**只借全天剩余空闲**，不会挤掉别科配额内的普通项（D10 补充，sol 第 114 轮）。

入选与延期两个列表最后都按优先级重新排序。普通项超出本科配额时即使全天还有空闲也延期。

## 5. 输出：五个桶与会计不变量

| 字段 | 内容 | 顺序 |
|---|---|---|
| `selected` | 入选项（原对象） | 优先级 |
| `deferred` | 延期项，已 `with_deferral()` | 优先级 |
| `unschedulable` | 耗时超过拆分门槛的到期项（原对象），需要拆分 | 优先级 |
| `scheduled_ahead` | `state == "scheduled"` 且 `due_date > today` | 输入顺序 |
| `unreachable` | `state == "scheduled"` 且 `due_date <= today`：`is_due` 只认 `queued`，它永远选不上，需要修状态 | 输入顺序 |
| `review_minutes` | 入选项耗时之和，`<= hard_cap` | — |
| `new_learning_minutes` | `total - review_minutes` | — |
| `soft_target_minutes`、`hard_cap_minutes` | §3 的数值 | — |
| `backlog_minutes` | 延期项耗时之和 | — |
| `over_capacity` | `deferred`、`unschedulable`、`unreachable` 任一非空 | — |
| `subject_review_quotas` | 给了配额时为其副本，否则 `None` | — |
| `subject_review_minutes` | 给了配额时为各科实际入选分钟（每个配额键都在，未用为 0；无配额键的科目有紧急项借用入选时也会出现），否则 `None` | — |

**会计不变量**：每个 `state == "scheduled"` 的项和每个候选（到期的 `queued` 项）恰好落在一个
桶里；`visible_ids` 按 selected、deferred、unschedulable、scheduled_ahead、unreachable 的顺序
给出并集。尚未到期的 `queued` 项是未来工作，不出现；`suspended` 与 `retired` 项刻意不出现在
任何桶里（到期也一样）。函数返回前核对"应出现的都出现了"，缺漏时抛 `AssertionError`，
以防将来新增状态后静默丢项。

**延期语义**：`with_deferral()` 只把 `defer_count` 加 1，其余字段（含 `due_date`、`revision`、
`schedule`、自评）原样保留。不改期、不写回、不需要审计记录；逾期天数增长本身会在后续日期
抬高它的名次。本函数不落盘，延期计数由调用方决定是否持久化。

## 6. JSON 形状

`ClipResult.summary()` 顶层键恰为：

`date`（ISO 日期）、`selected`、`deferred`、`unschedulable`、`scheduled_ahead`、`unreachable`、
`review_minutes`、`new_learning_minutes`、`soft_target_minutes`、`hard_cap_minutes`、
`backlog_minutes`、`over_capacity`；给了配额时再加 `subject_review_quotas` 与
`subject_review_minutes`（无配额时这两个键**不出现**，旧 JSON 字节不变）。

`selected`、`deferred`、`scheduled_ahead`、`unreachable` 的每个元素是
`{review_id, subject_id, estimated_minutes, overdue_days, defer_count, state}`，
`overdue_days` 相对 `today`（未到期为负）；`deferred` 元素的 `defer_count` 是**加 1 之后**的值。
`unschedulable` 只列 `review_id` 字符串。

`preflight_to_mapping(config, result, allocations)` 是 CLI 与 M19 共用的唯一形状来源：
在 `summary()` 之上加

- `subject_allocation`：M8 `allocate_new_content` 的结果逐项
  `{subject_id, display_name, weight, new_content_minutes}`（`new_content_minutes` 为
  `SubjectAllocation.minutes`）；
- `config`：`{project_id, default_daily_minutes, review_reserve_ratio, hard_max_ratio}`。

调用方的附加：冻结时再加 `freeze`（`contracts/freeze.md`）；M19 输入包的 `review_clip` 去掉
`config`。`ky preflight --json` 以 `sort_keys=True` 序列化，所以字段顺序不属于契约。

## 7. 调用方组合

`ky preflight` 与 M19 如何由 M8 `resolve_day_budget`、M27 冻结得出 `daily_minutes_override`、
`subject_review_quotas` 与新学切分策略，见 `contracts/config.md` §7。要点：

- 总时长来源为 `config` 时不传覆盖值；来源为 `availability` 时传当天手填值；
- 当天落在时间线阶段内且未冻结时传该阶段（已缩放）的配额；
- 冻结时传 `daily_minutes_override=0` 且不传配额：没有复习入选，到期项全部延期（超过拆分门槛
  的仍报 `unschedulable`）；
- `ky preflight` 的紧急阈值来自 `--urgent-overdue-days` / `--urgent-defer-count`，M19 用缺省
  `ReviewPolicy()`。

## 8. 验收

`py -3.12 -m unittest tests.contract.test_review_clip_port tests.test_review_scheduler
tests.contract.test_day_budget_port tests.contract.test_planner_port`
