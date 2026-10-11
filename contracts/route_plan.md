# RoutePlan 端口（M11 / M13 / M14）

本契约定义阶段 2.5 的路线时间线 YAML/JSON、版本存储与人工 CLI。它只表达阶段日期和各科
每日复习分钟，不生成日计划。文件格式的唯一 Python 映射接口为
`ky.schedule.planning.route_plan_to_mapping()` 与 `parse_route_plan(raw, path)`；解析后调用
现有 `validate_route_plan()`，闭合性规则由其负责。

## 文件格式

顶层键必须恰好为：`schema_version`、`route_id`、`revision`、`start_date`、
`target_exam_date`、`policy_version`、`stage1_input_hash`、`phases`。版本为精确整数 `2`，
布尔值不视为整数。每段对象键必须恰好为：`index`、`start`、`end_exclusive`、`label`、
`review_minutes`。未知键和缺键均拒绝，并报告字段路径。版本 `1` 已废止；解析时以包含 D10
的契约错误提示按时间线格式重写。

`phases` 必须非空；`index` 从 0 连续递增；首段从 `start_date` 开始，后段紧接前段的
`end_exclusive`；每段结束日期晚于开始日期；最后一段 `end_exclusive` 等于
`target_exam_date`。日期区间均为右开 `[start, end_exclusive)`。`label` 必须是非空字符串。
`review_minutes` 必须是非空映射，键是非空科目 ID 字符串，值是非负整数；所有整数拒绝布尔值
和浮点数。格式层不按配置校验科目 ID。日期可为 YAML 日期或严格 `YYYY-MM-DD` 字符串，不接受
`datetime`；序列化总是输出 ISO 字符串。YAML 读取使用 `ky.models.load_yaml_text()`，重复键
fail-closed。闭合性错误沿用 `RoutePlanError.path`。

`stage1_input_hash` 在路线提案中等于其 M19 `input_hash`，标识提案所依据的路线输入包；
人工 `--plan` 提交也使用本节路线格式，并以空 `input_hash` 记录来源。

## 版本存储

存储根目录由工作区 `write_target("state.routes")` 提供，也可由 CLI `--store` 覆盖。目录布局：

```text
routes_manifest.yaml
route--r<revision>.yaml
```

版本文件不可覆盖，由临时文件校验后对目标执行原子、不覆盖的硬链接发布保证；目标已存在时拒绝。
若文件系统不支持硬链接，存储报错并说明原因，不改用可能覆盖目标的发布方式。库为空时只接受
revision 1；之后 `route_id` 必须不变，revision 必须恰为当前版本加一。比较失败报告 `route_id` 或
`revision`，不得落下路线或 manifest 文件。写路线时先校验，再写临时版本文件、重读并解析校验，
写入前使用 manifest 相同的来源校验：`actor` 必须为字符串，`input_hash` 必须为 null 或小写
64 位十六进制；不合格时报 `StorageError`，且不写任何文件。发布版本文件后以 `replace_bytes()`
原子替换 manifest。硬链接发布**之前**先记录本次临时文件的 `st_dev` / `st_ino`（硬链接与其共用同一
inode），不在发布后读取目标，以免记下发布与读取之间被替换进来的文件。若 manifest 替换失败，
仅当目标仍有相同身份时才删除，然后原样抛出替换异常。身份核对与删除之间仍有极短窗口；该检查
只防止不遵守锁的写者在回滚前替换目标文件，不提供无锁并发安全。并发写入使用目录内短暂独占锁
`.routes.lock` 串行化比较和写入；锁已存在时拒绝写入，
错误路径为锁文件路径。写入进程异常退出可能遗留该锁：确认没有写入正在进行后，由用户手动删除，
存储不会自动清除。

磁盘 manifest 顶层键必须恰为 `schema_version`、`route_id`、`revisions`；版本是精确整数 1，
`route_id` 是非空字符串，`revisions` 是列表。每项键必须恰为 `revision`、`path`、`sha256`、
`actor`、`input_hash`；revision 是从 1 开始连续递增的精确整数，path 必须等于
`route--r<revision>.yaml`，SHA-256 和非空 input hash 必须是小写 64 位十六进制，actor 为字符串，
input hash 也可为 null。任一格式错误都以 `StorageError` 拒绝并指明字段。读取版本时先核对 SHA-256，
再确认路线自身的 revision 与 route_id 等于 manifest 对应值；不一致即报错。路线 manifest 保留每个
版本的来源。不存在的存储目录表示空库。

若进程在版本文件发布后、manifest 替换前崩溃，会留下未登记的版本文件。后续提交发现该文件时拒绝
覆盖，并提示“未登记的版本文件，确认后手动删除”；核实文件内容和没有其他写入后，由用户手动删除，
再重试提交。

只读接口：`current() -> RoutePlan | None`、`load_revision(n) -> RoutePlan`、
`provenance(n) -> (actor, input_hash)`。写接口：
`write_route_plan(plan, actor="unknown", input_hash=None) -> WriteReport`。

## 生效规则（D10）

路线是可变时间线。每个阶段只通过 `label`、`start`、`end_exclusive`、`review_minutes` 表达；阶段日期区间为右开 `[start, end_exclusive)`。每日总时长仍由 M26 当日手填值优先、配置回落决定，不从路线读取。

M8 `resolve_day_budget(day, config, availability, route, timetable=None) -> DayBudget` 负责解析统一预算：`total_minutes` / `total_source` 沿用 M26 `resolve_daily_minutes`，优先级为手填单日 > 课表 > 配置基数；本包配置基数为 `config.default_daily_minutes`。没有路线或当天不在阶段内时，`subject_review_quotas` 为 `None`，M9 保持既有裁剪结果。当天命中阶段时，`review_minutes` 的键必须是配置科目 ID；未知科目以 `route.phases[i].review_minutes.<id>` 报契约错误。在考科目均须有值，缺少时错误消息指出“时间线阶段 i 缺少在考科目 <id> 的复习分钟”。未启用科目只允许缺省或 0 分钟，正数时报错并提示先在配置启用。

命中阶段时，在考科目的每日分钟作为 M9 常规复习配额。配额总和不超过以当日总时长和 `hard_max_ratio` 算出的每日硬上限时原样使用；超过时用精确有理数最大余数法缩至硬上限，同余数按科目 ID 排序。M8 与 M9 共用 `hard_review_cap_minutes()`。M9 `select_daily_reviews(..., subject_review_quotas=...)` 按既有优先级裁剪：分两遍：第一遍只在本科配额内入选且不超过全天硬上限——**先处理全部紧急项、再处理普通项**，两组内部各按优先级（只按优先级会让逾期更久的普通项排在同科紧急项前，sol 第 116 轮）；传入配额之和超过当天硬上限报契约错误（配额须经 `resolve_day_budget` 缩放）；第二遍让仍未入选的紧急项（沿用 `_is_urgent`）使用全天硬上限剩余的空位——紧急项**只借剩余空闲**，别科配额内的普通项不会被挤掉（D10 补充，sol 第 114 轮）；入选与延期列表保持优先级顺序；未入选项继续延期，`unschedulable` 判定不变。给定配额时 `soft_target_minutes` 为配额之和，并输出各科配额与实际已用分钟；未给定时这些新字段不出现，既有 JSON 字节不变。

M14 `ky preflight` 从发现到的工作区读取已登记的 `state.routes` 当前路线；M19 `_build_input_data` 使用同一 M8 解析和 M9 裁剪。两者仅在总时长来源为 `availability` 或 `timetable` 时传入 `daily_minutes_override`，并继续使用 `floor_policy="drop_when_short"`。preflight 命中阶段时额外显示 `timeline phase : <阶段序号> <标签> (<科目ID>=<分钟> ...)`，科目按 ID 排序；有配额时 `review soft / hard` 行括号内的软配额来源写 `timeline quotas`（软值是阶段配额之和，不是配置比率）；没有配额时文本输出保持原样。M19 `review_clip` 与同配置、同工作区的 `ky preflight --json` 去掉 `config` 后一致。
M19 生成一个日输入包时**只读一次**当前路线，同一个 `RoutePlan` 对象同时用于配额解析与 `route_plan.phase` 字段，保证两者来自同一修订（sol 第 114 轮）。

D11 的 M27 积压冻结在 M8 预算解析之后判定，并优先于阶段复习配额：冻结日不选复习、不排新内容。冻结规则与入口 payload 见 `contracts/freeze.md`。

## CLI

### M28b daily base extension

The earlier D10 sentence saying daily total minutes are not read from the route
is superseded for base fallback: a phase may provide the base, while M26 hand
entry and timetable values retain priority. The earlier file-format paragraph's
v2 description covers v2 files; schema v3 adds the optional field described
here. Route plan schema v2 remains the serialized shape when every phase omits
`base_daily_minutes`. If any phase supplies the optional non-negative integer
(booleans excluded), serialization uses schema v3 and includes the field only
on phases that supply it. Parsers accept v2 and v3; v2 rejects the field.
M8 resolves each day's base in this order: matching route phase, pacing
`initial` on or after its `start`, then exam configuration. Its `base_source`
is `route`, `pacing_initial`, or `config`. M26 hand-entered and timetable
values remain higher priority; fallback from a non-config base is reported as
`total_source: base`.

Callers use frozen `0` plus `drop_when_short`; otherwise sources
`availability`, `timetable`, and `base` use the resolved total as override plus
`drop_when_short`. `config` retains the legacy strict path. Resolve M8 for each
day, including every resume search candidate.

M19's availability mapping adds `base_minutes` and `base_source` only when
pacing settings are registered; they contain the resolved `DayBudget` base
and source, including zero and `config`. Registered `settings.pacing` supplies
its `start` and `initial` to M8; when unregistered, M8 receives no pacing object.

`RoutePlanStore.read_revision_context(revision)` reads one manifest snapshot and
returns its current revision together with the requested revision's actor,
input hash, and route after the normal manifest and route validation. If the
requested target revision is not present, its provenance and route are `None`;
this permits crash recovery to distinguish the pre-publication state.

`py -3.12 -m ky route submit (--plan FILE | --from-staging FILE) [--config C] [--store DIR]`
`[--workspace W]`
两种输入互斥，均经 M19 的同一 apply 函数。`--plan` 解析 YAML 并以 `actor="human"`、
`input_hash=null` 提交；若能加载工作区注册表且文件真实路径位于登记 staging 根目录下则
拒绝。无显式 workspace 且无法发现注册表时不做路径检查；显式 workspace 加载失败仍报错。
`--from-staging` 使用 M19 路线提案校验和新鲜度检查；成功均打印路径、revision 和 SHA-256。

`py -3.12 -m ky route show [--revision N] [--store DIR] [--workspace W] [--json]` 显示路线摘要、
逐段日期（右开）、标签、各科每日复习分钟及该版本来源。JSON 形状为
`{"route_plan": <mapping>, "actor": ..., "input_hash": ...}`；
空库时 JSON 为 `null`，文本为“尚无路线”，均退出 0。若省略 `--store`，从工作区注册表
`state.routes` 解析；未登记时提示 `--store` 或登记 `state.routes`。

退出码：0 成功；2 契约、存储或护栏违规（提交未写入）；3 用法错误或输入文件不存在。

### 阶段目标（schema v4，用户 2026-10-01；供 M30 目标差距，`contracts/mastery.md` §5）

阶段对象可选键 `targets`：映射，键恰为 `covered` 与 `consolidated`，值为 0–100 的精确整数（排除布尔），表示**该阶段末**（`end_exclusive` 当天）应达到的
覆盖百分比与已巩固百分比。规则：

- `consolidated <= covered`；按阶段顺序，写了 `targets` 的阶段其两个值都**不减**（后一阶段不得低于前一个写了目标的阶段）。违反 → 契约错误，路径 `phases[i].targets.<键>`。
- 任一阶段写了 `targets` → 序列化用 schema v4（同时保留 v3 的 `base_daily_minutes` 规则）；没有任何阶段写 → 仍按 v2 / v3 输出，**既有路线文件字节不变**。
  解析器接受 v2 / v3 / v4；v2、v3 出现 `targets` 即拒绝。
- M28 `apply_pacing` 切段时：`targets` 属于原阶段的**末尾**，所以留在后半段（含原 `end_exclusive` 的那段）；前半段不带 `targets`；原地替换保留原值。
- M19 路线提案与 `ky route submit --plan` 可以写 `targets`；AI 路线规划指引见 `prompts/route_planning.md`（2026-10-02 补，含"每个阶段末写覆盖与巩固目标"）。
