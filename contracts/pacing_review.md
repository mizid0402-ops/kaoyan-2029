# 端口规格：M28 周期复盘与调整（复盘报告 → AI 调整方案 → 用户确认生效）

> 决议来源：用户 2026-09-30（见 §10）。细则审阅：sol 第 220 轮 FAIL（R1–R8）→ 本版重写，见 §12。状态：**待复审**。
> 实现：`ky/pacing/`；契约测试：`tests/contract/test_pacing_port.py`；AI 指引：`prompts/pacing_review.md`（随本模块版本化）。

## 1. 职责与边界

每个复盘周期结束后回答两个问题：

1. **这一周期记录下来的情况是什么？**——确定性的**复盘报告**（不用 AI）。报告只陈述能由现有数据确定的事实；
   无法还原的历史量标 `null` 并写明观测口径，不冒充历史值（sol 220 R4/R5）。
2. **接下来基础时长与各科复习分钟怎么调？**——AI 读报告出**方案**，程序校验护栏，**用户运行提交命令才生效**。

- 可调的只有：**基础时长**（当日基数，课表在它上面扣大节）与**各科每日复习分钟**（路线阶段已有字段）。新学 = 当天总分钟 − 复习。
- 不可调：到期日、复习间隔、ease、复习算法参数、过去的日子、手填单日分钟、考试配置、冻结状态（硬不变量②③，D11）。
- 本模块不新建第二份"基础分钟"状态：基数只来自路线阶段、设置文件 `initial`、考试配置三处，按 §5 顺序解析。
- 所有纯计算不读系统时间：CLI 把"今天"作为参数传入（`--today`，缺省取系统日期，只在装配层取一次）。

## 2. 设置文件（`settings.pacing`，可选）

未登记 = 本模块不启用，所有旧输出逐字节不变（§9）。登记即必须存在且有效，否则 fail-closed（退出 2）。

```yaml
schema_version: 1
start: 2026-10-01                     # 第一个周期的第一天；从这天起基数按 §5 解析
exam_date: 2028-12-23                 # 路线终点（无路线时新建路线用）；初试日期确定后改这里
base_daily_minutes: {min: 180, max: 240, initial: 180}
max_step_minutes: 30                  # 一份报告的调整最多让基数变动多少
cadence:
  - {kind: half_month, until: 2026-12-01}   # 每月 1–15 日、16 日–月末
  - {kind: month}                           # 自然月
```

| 字段 | 规则 |
|---|---|
| `start` | 任意日期（用户 2026-10-02 取消"必须是 1 日或 16 日"）；不在 `cadence[0].kind` 的分界上时按下文"首周期就近吸附" |
| `exam_date` | 日期；晚于 `start` |
| `base_daily_minutes.min/max/initial` | 非负整数，`min <= initial <= max` |
| `max_step_minutes` | 非负整数 |
| `cadence` | 非空列表；`kind ∈ {half_month, month}`；除最后一项外必须有 `until`，最后一项不得有 |
| `cadence[i].until` | **必须是某月 1 日**（同时是两种 kind 的合法边界，因此不会截出半个自然月）；`cadence[0].until > start`，其后严格递增 |

未知字段、重复键拒绝；整数排除布尔；日期为 YAML 日期或严格 `YYYY-MM-DD`，拒绝 datetime。

**周期**内部一律用右开区间 `[start, end_exclusive)`，报告展示时终日 = `end_exclusive − 1`。
从 `start` 起按 `cadence` 首尾相接地切分：`half_month` 周期为 `[1 日, 16 日)` 与 `[16 日, 次月 1 日)`（2 月后半按实际天数，闰年 16–29 日）；
`month` 为 `[1 日, 次月 1 日)`。早于 `start` 的日期不属于任何周期（查询时返回 `None`，不产生负序号）。

**首周期就近吸附**（用户 2026-10-02）：`start` 不在 `cadence[0].kind` 的分界上（`half_month`：1 日 / 16 日；`month`：1 日）时，
取它之前最近的分界 `P` 与之后最近的分界 `N`（`N` 受 `cadence[0].until` 截断，同上文）。
- `N − start < start − P`（离下一个分界更近）→ 这几天并入下一个周期：首周期为 `[start, N 之后的下一个分界)`，跨过 `until` 时按下一项 `kind` 取分界；
- 否则（离上一个分界更近或一样近）→ 首周期为 `[start, N)`，较短。
- 其后周期照常切分。例：`half_month` 下 `start = 10-08` → 首周期 10-08–10-15；`start = 10-13` → 10-13–10-31。
- `start` 本在分界上时与此前逐字节一致（对照固定基线 `a1e83d9`）。

## 3. 复盘报告（`ky pacing report --cycle-end D [--today T]`）

`D` 必须是某周期的终日，且 `D < T`（周期未结束不出报告）。装配层**一次**读取所有来源（M13 `read_state_sources` 等），
纯函数 `build_report(...)` 计算，映射函数 `report_to_mapping()` 是 JSON / YAML 形状的唯一来源。

M33 今日提醒复用 `load_pacing_report_state(settings, today, plans_root)`：返回未报告周期元组和已存在且校验过的报告映射，
按周期终日键控；每个已存在报告只读取一次。`missing_report_cycles(...)` 保留同一筛选与校验行为，只返回周期元组。

| 字段 | 类型 | 计算口径 |
|---|---|---|
| `schema_version` | 1 | |
| `cycle` | `{start, end, days}` | `end` 为终日，`days = end − start + 1` |
| `generated_on` | 日期 | `T` |
| `base` | `{min, max, mean, source_note}` | 周期内逐日按 §5 解析三级来源（路线阶段 > 复盘设置 initial > 考试配置）；`mean` 为整数除法向下取整；`source_note` 固定为 `路线阶段 > 复盘设置 initial > 考试配置` |
| `reference_minutes` | 整数 | 周期内逐日 M8 总分钟之和（手填 > 课表 > 基数），同样"按生成时来源重算"；冻结日照算，另见 `freeze` |
| `reference_source_note` | 字符串 | 固定为 `按生成时来源重算` |
| `declared_minutes` | `{days, sum}` | 周期内**已落盘日计划**的天数与 `available_minutes` 之和（AI / 人声明值，可与上一项不同） |
| `recorded_event_days` | 整数 | 周期内有已存完成事件的**不同** `event.day` 数（空事件也计；有没有做事由 `reviews` 等看） |
| `study_minutes` | `{days, sum}` | 周期内 `event.day` 落在周期里、且写了 `study_minutes` 的完成事件天数与总和；**填 0 计入天数，缺失不计** |
| `reviews` | 按科目映射 | 见下 |
| `reviews_unattributed` | 整数 | 生成时队列里找不到 `review_id` 的完成条数（队列整理过会出现；不猜科目） |
| `duplicate_completion_ids` | 整数 | 同一 `completion_id` 出现在多个事件里的额外次数（只计一次，取 `event.day` 最早者） |
| `backlog_observed` | `{observed_on, total, by_subject}` | 生成当天 `T` 的逾期积压，**M12 口径**（`queued`/`scheduled` 且 `due_date < T`）。**不是周期末值** |
| `freeze` | `{events, latched_at_end}` | 周期内冻结 / 恢复事件数；只取日期 ≤ 终日的事件按全局序号与 D11 解除条件判断终日是否存在未解除锁存（不回算历史阈值） |
| `reviews` | 按科目统计映射 | 稀疏映射，只列出现过的科目；缺行不等于 0。字段为 `{completed, correct, partial, incorrect, none, miss_ratio}` |
| `due_next` | 按科目分钟 | 稀疏映射，只列出现过的科目；缺行不等于 0。生成时队列中 `queued`/`scheduled` 且 `due_date` 落在**下一周期**内的项的 `estimated_minutes` 之和（每项只计当前这一轮） |
| `previous` | 映射或 `null` | **紧邻的上一周期**已保存报告的完整 `reviews`、`backlog_observed`、`study_minutes`、`cycle`、`report_hash`；没有则 `null`（有缺口就是 `null`，不找更早的） |
| `sources` | 映射 | 所读每个文件的工作区相对 POSIX 路径 → 原始字节 SHA-256 |
| `report_hash` | 64 位十六进制 | 本映射去掉 `report_hash` 字段后的 M19 规范 JSON 字节的 SHA-256 |

`reviews.<科目>`：`{completed, correct, partial, incorrect, none, miss_ratio}`。
- 统计完成事件里 `completed_on` 落在周期内的复习完成（**按实际完成日**，补录也计入所属日期）；装配层读取**全部**完成事件再过滤，
  不能只读 `event.day` 在周期内的文件。同一 `completion_id` 出现在多个事件里只计一次，取 `event.day` 最早的那条；
  这种重复的个数记入 `duplicate_completion_ids`（整数字段）。
- 科目取生成时队列中该 `review_id` 的 `subject_id`；找不到计入 `reviews_unattributed`。
- `miss_ratio = (incorrect + partial) / (correct + partial + incorrect)`，分母为 0 时 `null`；十进制保留 3 位（四舍五入到偶数）。
- 这是"记录了的完成"，不代表队列都已成功推进（完成事件写成功而推进失败是正常恢复路径）。

读取已保存报告时校验格式与 `report_hash`，不符即违约。用户改了 `start` / `cadence` 使 `D` 不再是当前设置下的周期终日时，
`planner-input` 与 `submit` 对该报告违约退出 2；已保存报告仍可读，不重写。

**只写一次**：保存到 `state.plans` 下 `pacing/report--<终日>.yaml`，临时文件校验后 `os.link` 不覆盖发布（照 `route_store`）。
同一周期再次运行：不重写，打印已保存的报告；若本次重算的 `sources` 与已保存的不同，多打印一行"报告生成后记录有变化，已保存的报告不变"，退出 0。
后续 `planner-input` 一律读**已保存**报告。

## 4. AI 输入包与方案

输入包的 `settings` 是展平映射 `{start, exam_date, minimum, maximum, initial,
max_step_minutes, cadence}`；日期为 ISO 日期字符串，`cadence` 是有序对象列表，
每项含 `kind`，月度项另含 `until`（ISO 月初日期）。

`ky planner-input --kind pacing --cycle-end D [--today T]`：已保存报告不存在 → 违约（先 `report`）。
写 `staging/inputs/pacing--<D>--<hash12>.json`，内容：

```
{schema_version: 1, kind: pacing_input, as_of: T, report, settings, config,
 current_route: route_plan_to_mapping(...) 或 null,
 base_at: {date: T, minutes, source}}        # 最早可生效日 T（T > D）按 §5 的现行基数；步长仍按方案生效日的 b0 检查
```

`input_hash` 同 M19（规范 JSON 字节 SHA-256）。AI 读 `prompts/pacing_review.md` 与输入包，写方案到 `staging/pacing/<名>.yaml`：

```yaml
schema_version: 1
kind: pacing_proposal
actor: ai:claude-opus-5-5          # 同 M19 actor 规则
input_hash: <64 位十六进制>
effective_from: 2026-10-17
base_daily_minutes: 195
review_minutes: {math1: 40, eng1: 20, cs408: 40}
rationale:                          # 至少一条；evidence 为输入包 report 映射中存在的字段路径
  - claim: 408 错题比例两个周期都在 0.4 以上，复习分钟上调
    evidence: [report.reviews.cs408.miss_ratio, report.previous.reviews.cs408.miss_ratio]
notes: 可选，给用户看的文字，不产生效果
```

## 5. 当日基数解析（M8）

对日期 `d`：

1. 所在路线阶段有 `base_daily_minutes` → 用它，`base_source = route`；
2. 否则，`settings.pacing` 已登记且 `d >= start` → `initial`，`base_source = pacing_initial`；
3. 否则 `config.default_daily_minutes`，`base_source = config`。

然后照 `contracts/timetable.md` §6.1 解析当日总分钟：手填 > 课表（在基数上扣大节）> 基数。总来源 `total_source`：
`availability` / `timetable` / `base`（取了第 1 或第 2 步的基数）/ `config`（取了第 3 步）。
M26 回落时仍返回来源 `config`，由 M8 按 `base_source` 改写：`route` 或 `pacing_initial` → `base`，`config` → `config`。
本节是 `contracts/timetable.md` §6.1 / §6.2 的扩展，两处以本节为准。

**裁剪与分配**（扩展 `contracts/timetable.md` §6.2 的三步，sol 220 R3）：冻结 → override 0 + `drop_when_short`；
未冻结且 `total_source ∈ {availability, timetable, base}` → `daily_minutes_override = total_minutes` + `drop_when_short`；
`config` → 旧路径（不传 override，`strict`）。preflight、M19 日输入包、`ky resume` 都经这一处，M9 看到的是解析后的分钟。

M19 日输入包：`availability` 字段在 `state.availability`、`state.timetable`、`settings.pacing` 任一登记时给出对象，否则 `null`；
`settings.pacing` 登记时对象多两个键 `base_minutes`、`base_source`，否则保持 `{"minutes", "source"}` 两键。

## 6. 提交（`ky pacing submit --from-staging FILE [--dry-run] [--today T]`）

**先分流，再校验**（sol 230 R12）：读取方案 `FILE` 并做形状校验（未知字段、类型、`actor` 格式；不看新鲜度），得到报告终日 `D`
（取自方案 `input_hash` 对应的已保存输入包；找不到该包 → 违约）。然后：

- `state.plans/pacing/applied--<D>.yaml`（提交意图，§6.1）**已存在** → 走 §6.2 **恢复分支**，不做下面的新提交校验；
- 不存在 → 走**新提交分支**，按顺序检查，任一不过即违约退出 2，**不写任何文件**：

1. `rationale` 非空且每个 `evidence` 路径在输入包 `report` 映射里存在（只证明引用可解，不评判推理）。
2. 新鲜度：在 `staging/inputs/` 找到文件名为 `pacing--<D>--<input_hash[:12]>.json` 且规范哈希等于 `input_hash` 的包；
   再按同一 `D` 与本次 `T` **重新生成**输入包，其哈希必须相等（同 M19；跨日提交因 `as_of` 变化而过期，需重出输入包）。
3. `min <= base_daily_minutes <= max`；`|base_daily_minutes − b0| <= max_step_minutes`，`b0` = **旧路线下 `effective_from` 当天**按 §5 解析的基数（sol 220 R7）。
4. `review_minutes` 键恰为配置全部在考科目，值为非负整数；和 ≤ `scale_minutes(base_daily_minutes, hard_max_ratio)`（方案本身不得超出基础预算；有课表的日子 M8 仍会按当日容量再缩放，摘要里说明）。
5. `effective_from`：`> D` 且 `>= T`；`< exam_date`；有路线时 `>= route.start_date` 且 `< route.target_exam_date`。
6. 冻结：用 M27 `assess_freeze` 与锁存判定，日期 `T`，只读。冻结中拒绝（先 `ky resume`）。
7. 构造候选新路线（§7）并调用 `validate_route_plan`；失败即拒绝。

通过后先打印**变更摘要**，再按 §6.1 两步写入：`effective_from`、基数 `b0 → 新值`、各科复习分钟（旧路线值 → 新值；无旧路线打印 `-`）、每条理由与证据的实际值（从输入包 `report` 映射取值并以 JSON 显示）。还需打印受影响阶段结束边界、有效日期上限（输入包 `settings.exam_date` 与旧路线 `target_exam_date` 中较早者并标出来源；无路线时只用设置日期），以及课表容量会缩放复习配额的说明。
`--dry-run` 到此为止，不写任何文件。否则按 §6.1 两步写入。

### 6.1 新提交的两步写入（sol 221 R9、230 R14）

第一步写的是**提交意图**，不是"已完成"：

1. 以临时文件 + 重读校验 + `os.link` 不覆盖发布 `applied--<D>.yaml`，字段见下表；其中保存**第 7 条已校验的完整候选路线**及其规范摘要。
2. `RoutePlanStore.write_route_plan(候选路线, actor, input_hash)`。

| 意图字段 | 规则 |
|---|---|
| `schema_version` | 精确整数 1 |
| `report_hash`、`input_hash` | 64 位小写十六进制 |
| `actor` | 同 M19 actor 规则 |
| `proposal` | 完整方案映射（与方案文件同形） |
| `proposal_sha256` | `proposal` 的 M19 规范 JSON 摘要 |
| `base_revision` | 写入前当前路线修订号，无路线为 0 |
| `target_revision` | `base_revision + 1` |
| `b0` | 第 3 条算出的基数 |
| `route` | 候选路线的 `route_plan_to_mapping` 结果 |
| `route_sha256` | `route` 的规范 JSON 摘要 |

未知字段、重复键拒绝；读取时逐项校验并核对两个摘要，不符即违约（意图文件损坏按"找到但无效"处理，不当作不存在）。

**是否已生效只看路线存储**：manifest 历史中存在修订 `target_revision`，其记录的 `input_hash` 等于意图的 `input_hash`，且该修订文件按现有 `load_revision` 规则核对通过、
内容的规范摘要等于意图的 `route_sha256` → 已生效。查询时用路线存储的**一次** manifest 快照（公开读接口，不 import 存储私有方法）。

### 6.2 恢复分支（意图已存在；sol 230 R12–R14）

恢复是**完成一笔已经确认过的事务**，不是一份新方案：**不做新鲜度比较、不重跑第 3–7 条、不读当前设置重新构造路线**；
所用的只有意图文件里保存的内容与路线存储的当前状态。

| 路线存储状态 | 处理 | 退出 |
|---|---|---|
| 已生效（如上） | 打印"本报告已有提交，实际应用如下"与**意图里**的方案摘要；调用方这次的方案文件若与意图的 `proposal_sha256` 不同，多打印一行"本次文件未被采用" | 0 |
| 当前修订 = `base_revision`（上次在第 2 步前中断） | 发布意图里保存的 `route`（先核对 `route_sha256`），打印"已完成上次中断的提交"；若 `effective_from` 已早于 `T`，多打印一行说明"生效日已过，过去的日子按新路线重算的只是参考值，已落盘的日计划与记录不变" | 0 |
| 其他（中断后路线已被别的提交改变） | 不再应用；意图文件保留作历史；提示"如需调整请手工 `ky route submit --plan`，或等下一周期复盘" | 2 |

- 已生效时首行打印 `本报告已有提交（修订 <target_revision>），实际应用如下；不发布`；`--dry-run` 时末尾加 `（dry-run）`。若当前路线修订较高，再打印历史应用提示及当前修订，随后显示基于意图与保存输入包的摘要。待恢复 dry-run 首行打印 `dry-run：将恢复提交（不写任何文件）`，然后显示摘要与完整候选路线 YAML。路线发布失败时保留意图，先输出原契约错误，再提示 `提交意图已保存：重跑同一命令完成提交`。
- **`--dry-run` 覆盖所有分支**（sol 230 R13）：只打印当前属于哪一行、将要发布的路线与摘要；不写路线、不改意图与 manifest。
- 设置改动后旧报告不能**新提交**（§3），但不影响已存在意图的恢复（恢复只用意图内容）。
- 第 2 步遇到路线存储既有的遗留锁 `.routes.lock` 或孤儿版本文件（崩溃遗留），照 `contracts/route_plan.md` 报错并提示人工处理；处理后重跑即走上表第二行。
- 第 2 步在进程仍存活时失败：不删意图文件，原样报错并提示"重跑同一命令完成提交"。
- 因此"失败不写"只针对新提交分支的校验拒绝与所有 `--dry-run`；正式提交的 I/O 失败可能留下意图文件，但它总能被上表判定与收尾。

## 7. 路线转换（纯函数 `apply_pacing(route | None, proposal, settings, cycle_end) -> RoutePlan`）

`cycle_end` 由已校验的报告传入（用于 `label`），不从文件名或哈希倒推。
摘要里说明生效日的上限来自 `exam_date` 还是路线的 `target_exam_date`（取较早者）；改 `exam_date` 不会自动延长已有路线。

- **有路线**：找包含 `effective_from` 的阶段 `P`。
  - `effective_from == P.start` → 原地替换 `P` 的 `review_minutes` 与 `base_daily_minutes`；
  - 否则切成 `[P.start, effective_from)`（保留原值）与 `[effective_from, P.end_exclusive)`（新值），`label` 为 `f"{phase.label} · 复盘 {cycle_end}"`；
  - 其后阶段不动；全部阶段 `index` 从 0 重编号；`revision = 旧 + 1`，`route_id`、`start_date`、`target_exam_date`、`policy_version` 不变，
    `stage1_input_hash = input_hash`（本修订的派生依据）。
- **无路线**：新建 `route_id = pacing`、`revision = 1`、`start_date = effective_from`、`target_exam_date = exam_date`、
  `policy_version = pacing-v1`、`stage1_input_hash = input_hash`，一个阶段 `[effective_from, exam_date)`，`label = 复盘 <D>`。
  `start` 与 `effective_from` 之间的日子不在路线内，基数按 §5 第 2 步取 `initial`。
- `state.routes` 未登记 → 违约（不自选路径）。

## 8. 版本与兼容（sol 220 R8）

- **路线**：阶段可选 `base_daily_minutes`。`route_plan_to_mapping` 在**没有任何阶段**带该字段时输出 v2 形状（`schema_version: 2`、阶段无此键），
  有则输出 v3（`schema_version: 3`，只在带值的阶段写此键）。解析接受 v2 与 v3；v2 中出现此键 → 违约。
- **完成事件**：可选 `study_minutes`（当天实际学习总分钟，非负整数，不区分复习与新学）。没有该值时仍写 v2，有则写 v3；v1 / v2 / v3 都可读，v1 / v2 读为 `None`。
- **M0**（sol 230 R15）：`settings.pacing` 为可选 F 键，`Workspace.pacing: Path | None`；它是个人设置，**写在本地补充注册表**
  （`contracts/workspace.md` §2.6 的允许键加入 `settings.pacing`，只增不改、未知 / 重复键拒绝、`local.` 错误路径、本地指纹规则照旧）。
  真实设置文件放 gitignore 路径（如 `data/personal/pacing.yaml`）；复盘报告、提交意图（`state.plans/pacing/`）、输入包与方案（`staging/`）都是学习状态，
  所在目录已 gitignore。仓库里只可以有不含个人信息的示例设置。

## 9. 不变的部分与对照基线

- **联合条件**（sol 221 R11）：未登记 `state.timetable`、未登记 `settings.pacing`、路线无 `base_daily_minutes`、完成事件无 `study_minutes`
  **四者同时成立**时，preflight / 日与路线输入包 / resume / day-plan / 快照 / 投影与固定基线 **`e381792`** 逐字节一致。
  对照测试固定该哈希并断言取到的是旧版（`AGENTS.md` 12a）。
- 只有课表（M18）生效、M28 三项都不存在时，输出与 **④a 提交 `4816a14`** 逐字节一致。
- 路线阶段的 `base_daily_minutes` 独立生效，不需要登记 `settings.pacing`（例如用户手工在路线里写基数）。
- 固定基线夹具（sol 230 建议 1）：`e381792` 不支持本地补充注册表。对它的对照只用两版都能读的主注册表登记或显式 `--config`；
  用到本地补充文件的场景只对 `4816a14` 之后的版本比较。
- M13 可用时间硬上限仍只看手填；M27 冻结阈值仍用配置容量；M11 月结不改（它汇总已落盘日计划，与本报告职责不同，不 import 其私有函数）。
- preflight：`settings.pacing` 已登记、`T` 所在周期之前存在已结束但没有已保存报告的周期时，多打印一行复盘提醒；其余不变。

## 10. 决议记录（用户 2026-09-30）

| 问题 | 用户选择 |
|---|---|
| 基础时长 | 180–240 分钟"只是基础的时间"；**在区间内由复盘按数据调整**，起步 180 |
| 生效方式 | AI 方案进暂存区，**用户确认后生效** |
| 复盘周期 | **前两个月每半月，之后每月** |
| 实际用时 | 不逐条记录（"学的时候不会考虑到哪些是复习"）；决策者改为可选的**当天总分钟** |
| 调整依据 | 用户采用的规划假设"新学 + 约 0.6–0.8 倍复习 + 单词"，见 §11 |
| 起点（2026-10-02 补） | "必须是 1 日或 16 日"不合理，取消；起点不在分界上时首周期**就近吸附**（离下一个分界近则并入下一周期，避免太短的周期；一样近按较短），见 §2 |

**决策者拟定、可被用户推翻**：一份报告最多变 30 分钟且只应用一次；方案只改命中阶段（到该阶段结束失效，之后阶段不动）；冻结中不接受方案；
`study_minutes` 字段；报告积压取生成当天观测值；`exam_date` 暂填 2028-12-23（初试日期公布后改）。

## 11. AI 指引（`prompts/pacing_review.md`）

指引是**建议的判断方法**，不是算法，护栏在代码里。"0.6–0.8 倍"是用户采用的规划假设，不是已验证的规律。

- 数据不足 = `recorded_event_days` 少于周期天数一半（`study_minutes` 可选，缺失不算数据不足）→ 宁可不调，在 `notes` 说明。
- `backlog_observed` 高于 `previous.backlog_observed`（两者观测日不同，只能说明一次变化）→ 先加该科复习分钟，其次加基数。
- 记录天数不足一半 → 不加基数（D11 精神：不继续压迫）。
- 某科 `miss_ratio` 高且 `previous` 同样高 → 加该科复习分钟；积压为 0 且错题比例低 → 可把分钟挪给别科。
- `due_next.<科目>` 明显大于该科复习分钟 × 下一周期天数 → 提前加配额。
- 每条调整必须引用报告字段；`previous` 为 `null` 时不得声称"两个周期"。

## 12. 审阅记录（sol 第 220 轮）

> 下表中的"§6 第 N 条"是各轮当时版本的编号；§6 已于第 230 轮后重排（先分流，新提交分支七条）。

| 意见 | 处理 |
|---|---|
| R1 cadence 边界 | 采纳：`until` 必须是月初、首个 `until > start`、`start` 按首项 kind 校验；内部右开区间 |
| R2 `initial` 未参与解析 | 采纳：§5 第 2 步 |
| R3 路线基数未进入 M9 / M19 | 采纳：§5 总来源加 `base`，走 override；M19 对象加两键 |
| R4 周期末积压无法还原 | 采纳：改为 `backlog_observed` + 观测日，不称周期末 |
| R5 科目归属 / 补录 / planned / 冻结口径 | 采纳：§3 表逐字段定口径；`reviews_unattributed`；`reference` 与 `declared` 分开；`latched_at_end` |
| R6 路线切分边界与无路线 | 采纳：§7；`exam_date` 进设置；§6 第 6、8 条 |
| R7 步长基准与重复提交 | 采纳：`b0` 取生效日旧基数；一份报告只应用一次（`applied--<D>.yaml`） |
| R8 v3 序列化与逐字节不变冲突 | 采纳：§8 按需输出 v2 / v3；基线 `e381792` |
| 输入包附上一报告指标 | 采纳：`previous` 带完整相关指标 |
| 新鲜度需重新生成比较 | 采纳：§6 第 2 条 |
| 冻结复用 M27 只读判定 | 采纳：§6 第 7 条 |
| 配额护栏措辞、摘要说明课表缩放 | 采纳：§6 第 5 条 |
| `settings.pacing` 登记 | 采纳：§8 |
| M18 残留"缺省配置"描述 | 采纳：`contracts/timetable.md` 同步 |
| 与月结关系 | 采纳：不复用私有函数、不改月结 |

第 221 轮（R1–R8 关闭或核心关闭）：

| 意见 | 处理 |
|---|---|
| R9 两步写入中断后误锁 | 采纳：§6.1 提交意图 + 以路线存储为准的恢复表 |
| R10 缺完成事件天数 | 采纳：`recorded_event_days`；§11 "数据不足"只看它 |
| R11 逐字节条件需与 M18 联合 | 采纳：§9 联合条件；M18 单独生效时对 ④a 合并提交；`contracts/timetable.md` §6.3 同步 |
| M26 回落来源映射 | 采纳：§5 由 M8 改写为 `base` / `config` |
| `base_at` 日期 | 采纳：取 `T` |
| 积压"两次上升"措辞 | 采纳：改为一次变化 |
| `apply_pacing` 参数 | 采纳：传 `cycle_end` |
| 重复 `completion_id` | 采纳：取最早 `event.day`，计 `duplicate_completion_ids` |
| 设置改动后旧报告 | 采纳：§3 违约规则；读取校验 `report_hash` |
| `latched_at_end` 只取终日前事件 | 采纳：§3 表 |

第 230 轮（R10、R11 关闭）：

| 意见 | 处理 |
|---|---|
| R12 新鲜度挡住恢复 | 采纳：§6 先分流；意图存在即走恢复分支，不做新鲜度比较 |
| R13 恢复写路线与 `--dry-run` 冲突 | 采纳：§6.2 `--dry-run` 覆盖所有分支 |
| R14 恢复缺固定候选 | 采纳：§6.1 意图保存已校验的完整候选路线与摘要；恢复只发布它，不读当前设置；生效日已过时打印说明 |
| R15 `settings.pacing` 的本地登记 | 采纳：§8；`contracts/workspace.md` §2.6 允许键在 M28 实现时同步加入 |
| 建议 1–5（基线夹具、端口清单、意图身份、manifest 一次读、字段落点） | 采纳：§3 表、§6.1 表、§6.2、§9；端口同步清单写进实现任务书 |
