# 日计划与学习记录存储端口（M11 DayPlan / M13 DayPlanStore）

本规格描述 M11 的 `DayPlan` 模型与护栏 `check_invariants`，以及 M13 `DayPlanStore` 的目录布局、
写入与读取语义、只写一次的记录，和放在同一模块里的复习队列推进入口。它**只描述现有行为**
（WP-S3，2026-09-27）：代码与旧文档不一致时以代码为准，出入列在 §10。

实现：`ky/schedule/longitudinal.py`（`DayPlan`、`check_invariants`）、
`ky/storage/day_plan_store.py`（`DayPlanStore`、`parse_day_plan`、`preflight_review_queue`、
`advance_review_queue`）、`ky/storage/atomic.py`（`replace_bytes`）。

以下内容由其他规格负责，本文只引用、不重复：

| 主题 | 规格 |
|---|---|
| `read_state_sources()` 的返回形状、来源摘要、单次读取 | `contracts/state_sources.md` |
| manifest 来源字段 `actor` / `input_hash` 的含义、`day_plan_provenance()`、M19 提案与 apply | `contracts/planner_port.md` |
| 冻结 / 重启事件的格式、序号、锁存判定、CLI 冻结门 | `contracts/freeze.md` |
| 手填可用时间文件与"当日上限"的来源 | `contracts/availability.md` |
| 完成事件字段、completion ID、D8′ 只算一次、schema-1 队列升级 | `contracts/review_progress.md` |
| 已投放词形 `delivered_words()` 的消费方 | `contracts/state_snapshot.md`、`contracts/vocabulary.md` |
| 路线版本存储 `RoutePlanStore` | `contracts/route_plan.md` |

## 1. DayPlan 模型（M11）

`DayPlan` 是不可变数据类，表示"某一天怎么分配时间"。系统只给护栏，不给数字：没有固定日预算，
40 分钟和 300 分钟的一天同样合法。

| 字段 | 类型 | 缺省 | 含义 |
|---|---|---|---|
| `day` | `date` | 必填 | 计划日 |
| `available_minutes` | `int` | 必填 | 当天可用分钟 |
| `knowledge_minutes` | `int` | 0 | 知识点通道总分钟，必须等于 `subject_minutes` 之和 |
| `vocab_minutes` | `int` | 0 | 词汇通道分钟 |
| `vocab_new_items` | `int` | 0 | 当天新词数 |
| `phrase_minutes` | `int` | 0 | 短语 / 长句通道（扩展槽，0 是正常值） |
| `backlog_minutes` | `int` | 0 | 放不下、如实报告的积压分钟 |
| `subject_minutes` | `Mapping[str, int]` | `{}` | 知识点通道按科目 ID 的分配 |
| `notes` | `str` | `""` | 备注 |

派生量：`allocated_minutes = knowledge_minutes + vocab_minutes + phrase_minutes`（不含积压）；
`over_capacity = allocated_minutes - available_minutes`。

`check_invariants(day, *, subject_weights, weight_tolerance=1e-6, max_single_item_minutes=None)
-> GuardResult` 是纯函数，返回**全部**违规（`violations` 元组，`ok` 为空元组时为真），不在第一条处停止：

1. `subject_weights` 非空（否则 `no active subjects`），且权重和在 1 ± `weight_tolerance` 内。
2. `available_minutes`、`knowledge_minutes`、`vocab_minutes`、`phrase_minutes`、`vocab_new_items`、
   `backlog_minutes` 各自非负。
3. `subject_minutes` 的键必须是 `subject_weights` 中的科目；值非负。
4. `subject_minutes` 之和严格等于 `knowledge_minutes`（省略分科明细不能绕过倒挂检查）。
5. 倒挂：在全部在考科目上两两比较（省略的科目按 0 分钟），权重严格更大的科目不得分到严格更少的分钟。
6. 给定 `max_single_item_minutes` 时，逐科目、以及词汇 / 短语通道各自总量不得超过它；
   不拿整个知识点通道之和比较。
7. `allocated_minutes <= available_minutes`；声明积压不能为超额分配开脱。

不检查：`available_minutes` 是否等于某个数；`notes`；新词数上限。数值字段的**类型**由 §3
`parse_day_plan` 检查，本函数不重复（§10 D3，WP-R3 已修）。
上述规则的回归测试在 `tests/test_longitudinal.py`。

## 2. 存储目录布局（M13）

存储根目录来自工作区 `write_target("state.plans")`，CLI `--store` 可覆盖。记录按其自身日期落在
`YYYY-MM` 月目录中：

```text
<root>/
  YYYY-MM/
    day_plans_manifest.yaml              # 本月每天的当前版本
    day_plans/YYYY-MM-DD--v<N>.yaml      # 日计划版本文件（旧版本保留，不再引用）
    completion--YYYY-MM-DD.yaml          # 完成事件（每天一份，只写一次）
    month_close.yaml                     # 月结（每月一份，只写一次）
  freeze/<序号:06>-<kind>--YYYY-MM-DD.yaml  # 冻结 / 重启事件，见 contracts/freeze.md
```

不存在的根目录是空库：各 `load_*` 返回 `None` 或空元组，`delivered_words()` 返回空集。
根路径存在但不是目录时 `read_state_sources()` 报错，见 `contracts/state_sources.md`。

## 3. 日计划文件格式

写入时按以下顺序输出 UTF-8 YAML 映射（`yaml.safe_dump`，`allow_unicode=True`，`sort_keys=False`）：
`schema_version`（精确为 1）、`day`（ISO 字符串）、`available_minutes`、`knowledge_minutes`、
`vocab_minutes`、`vocab_new_items`、`phrase_minutes`、`backlog_minutes`、`subject_minutes`、`notes`。

`parse_day_plan(raw, path) -> DayPlan` 是该格式唯一的解析入口，M19 提案的 `plan` 字段与
`day-plan submit --plan` 也用它（`contracts/planner_port.md`）：

- `raw` 必须是映射；未知键以 `StorageError` 拒绝，路径为 `<path>.<按字典序第一个未知键>`。
- `schema_version` 缺省视为 1；其他值在 `<path>.schema_version` 拒绝。
- `day` 接受 YAML 未加引号的日期标量（`day: 2026-09-15`，与 `contracts/route_plan.md`、
  `contracts/availability.md` 一致），或经 `date.fromisoformat` 转换的字符串；无法转换的字符串
  （如 `"2026-13-01"`）、`datetime` 与其他类型都以 `StorageError` 在 `<path>.day` 拒绝（§10 D2）。
- 数值字段缺省为 0；`subject_minutes` 缺省或为 null 时为 `{}`，非映射在 `<path>.subject_minutes` 拒绝；
  `notes` 缺省为 `""`。
- 六个数值字段与 `subject_minutes` 的每个值必须是整数：字符串、`null`、布尔值、浮点数（含 `30.0`）
  以 `StorageError` 拒绝，路径为 `<path>.<字段>` 或 `<path>.subject_minutes.<科目>`（§10 D3）。
  取值（非负、合计、倒挂）仍由 §4 的写入护栏负责。

## 4. 写日计划：`write_day_plan`

构造参数：`DayPlanStore(root, *, subject_weights=None, max_single_item_minutes=None,
availability=None, freeze_gate=None)`。存储不自带缺省值：`subject_weights` 缺省为空映射，
此时每次写日计划都因 `no active subjects` 被拒；只做月结 / 完成事件的调用方可以省略它。
CLI 从已加载的配置传入在考科目权重，从工作区传入 availability 与冻结门。

`write_day_plan(day_plan, *, actor="unknown", input_hash=None) -> WriteReport` 依次执行：

1. `check_invariants`（使用构造时的权重与单项上限）。有违规时抛 `StorageError`，消息为全部违规以
   `"; "` 连接，路径为 `day_plan`。
2. 可用时间上限：给定 `availability` 且其中有该日条目时，`available_minutes` 超过条目值即拒绝，
   路径 `day_plan.available_minutes`。没有条目的日子没有额外上限。
3. 冻结门：给定 `freeze_gate` 时以计划日调用它；门抛出的异常原样传出。门的判定规则见
   `contracts/freeze.md`。
4. 版本号：读取该月 manifest，版本号为该日当前版本加一，没有条目时为 1。版本号**按日**计数，
   只由 manifest 决定，不看磁盘上已有的版本文件。
5. 发布版本文件：序列化后写同目录临时文件 `.<文件名>.<uuid>.tmp`，**重读临时文件**并再做一次
   第 1–3 步（解析 → 不变量 → 可用时间 → 冻结门，冻结门用重读出的计划日），全部通过后以
   `os.replace` 发布为 `day_plans/<日期>--v<N>.yaml`。任一步失败都删除临时文件，不发布。
6. 替换 manifest：`schema_version: 2`；`days` 按日期排序；每项恰有 `date`、`path`（相对月目录）、
   `sha256`（版本文件字节的小写十六进制 SHA-256）、`version`、`actor`、`input_hash`。同样经
   临时文件、重读（仅 YAML 解析）后 `os.replace`。
7. 返回 `WriteReport(path=<版本文件 POSIX 路径>, sha256=<同上>, version=N)`。

因此一次成功写入恰好调用冻结门两次，都用计划日。第 1–3 步任一失败时，存储目录逐字节不变
（`tests/test_day_plan_store.py`）；第 5 步重读失败时也不留下文件。

`actor` 与 `input_hash` 原样写入 manifest，存储本身不校验它们（M19 负责，§10 D5）。旧版本文件
不会被改写或删除，但只有当前版本带来源信息（`contracts/planner_port.md` §M13 provenance）。
读取旧 manifest 时缺失的 `actor` / `input_hash` 视为 `unknown` / null，下一次写入把整份 manifest 升为
schema 2。

若进程在第 5 步发布后、第 6 步完成前中断，会留下未被引用的版本文件；下次为同一天写入时算出同一个
版本号，并用 `os.replace` 覆盖这份孤儿文件（与 `RoutePlanStore` 的拒绝策略不同，§10 D6）。
存储不加锁；同月的并发写入以最后替换的 manifest 为准（单用户威胁模型，`AGENTS.md`）。

## 5. 读日计划

- `load_day_plan(day) -> DayPlan | None`：manifest 中没有该日条目时为 `None`；否则先核对当前版本
  文件的 SHA-256，不一致时抛 `StorageError`，路径为该文件，再解析返回。
- `load_month(year, month) -> tuple[DayPlan, ...]`：该月全部当前版本，按日期排序。
- `day_plan_provenance(day)`：见 `contracts/planner_port.md`。
- `read_state_sources()`：见 `contracts/state_sources.md`。

manifest 读取只把缺失的来源字段补成缺省值，不校验 `schema_version` 与条目形状（§10 D4）。

## 6. 只写一次的记录：完成事件与月结

完成事件与月结是历史事实（"不能被改分"），同一天 / 同一月的第二次写入直接拒绝，不替换。

- `write_completion_event(event) -> WriteReport`：路径 `<YYYY-MM>/completion--<日期>.yaml`。
  目标已存在时抛 `StorageError`（路径为目标文件）。否则写出 `schema_version`（当前为 2）、`day`、
  `reviews`、`vocab.delivered_words`、`vocab.practiced_words`；每条复习记录只写出非 null 的可选字段，
  因此内存中未带 `completion_id` 的记录落盘后由读取方按 `"<day>#<index>"` 补齐
  （`contracts/review_progress.md`）。临时文件经 `parse_completion_event` 重读后以 `os.replace` 发布。
  返回的 `version` 为 `None`。
- `load_completion_event(day)`：没有文件时为 `None`。
- `load_month_completions(year, month)`：该月目录下全部 `completion--*.yaml`，按文件名（即日期）排序；
  月目录不存在时为空元组——这是"确认没有事件"，`close_month` 靠它区分"无数据"。
- `delivered_words() -> frozenset[str]`：整个根目录下所有完成事件的已投放词形并集。文件不在其
  自身日期对应的路径时抛 `StorageError`（`not at its store path`），不计入。
- `write_month_close(month_close) -> WriteReport`：路径 `<YYYY-MM>/month_close.yaml`，已存在即拒绝。
  写出 `schema_version: 1` 与 `MonthClose` 的全部字段（包括 `actual_*` 与
  `vocab_delivered_vs_planned`）；临时文件重读校验后发布，`version` 为 `None`。
  `load_month_close(year, month)` 在文件不存在时为 `None`。`MonthClose` 由 M11
  `ky/schedule/monthly_close.close_month` 计算，只报告不建议。

"只写一次"由"先检查目标是否存在、再 `os.replace`"实现，不是原子的不覆盖发布（§10 D1）。

## 7. 冻结与重启事件

格式、序号、文件名、读取校验与锁存语义见 `contracts/freeze.md`。本模块的补充约定：

- `write_freeze_record(day, status_mapping)` 与 `write_resume_record(day, mapping)` 返回
  `WriteReport`，`version` 为 `None`。
- 载荷不是映射时抛 `StorageError`，路径分别为 `freeze.status` 与 `resume.resume`，不写任何文件。
- 序号为 `freeze_events()` 中最大序号加一；发布走 §8 的不覆盖硬链接。

## 8. 原子写辅助

| 辅助 | 位置 | 语义 | 使用者 |
|---|---|---|---|
| `_write_atomically(final, data, *, reread_check)` | `day_plan_store.py`（私有） | 建父目录；写同目录临时文件；`reread_check(临时文件)`；`os.replace` 到目标；失败时删临时文件 | 日计划版本、日计划 manifest、完成事件、月结 |
| `_write_once_atomically(final, data, *, reread_check)` | 同上（私有） | 临时文件重读校验后 `os.link` 到目标；目标已存在报"序号已被占用，请重试"，其他 `OSError` 报无法硬链接发布；最后总是删临时文件 | 冻结 / 重启事件 |
| `replace_bytes(path, data)` | `ky/storage/atomic.py`（公开） | 父目录须已存在；`mkstemp` 同目录临时文件；`os.replace`；不重读 | M19 输入包、`RoutePlanStore` manifest |

三者都替换目录项而不打开旧 inode，因此不会写穿指向外部文件的硬链接。新代码做普通替换写时用公开的
`replace_bytes`；"只写一次"用 `os.link` 模式（参照 `ky/storage/route_store.py`）。私有辅助不对外。

## 9. 复习队列推进：`preflight_review_queue` / `advance_review_queue`

这两个函数位于本模块，但作用于 M13 `ReviewShardStore` 与 M10 `ReviewAlgorithm`。D8′ 的业务规则
（只算一次、补录、schema-1 队列）见 `contracts/review_progress.md`；这里固定函数层面的约定。

`preflight_review_queue(review_store, event, *, source_state=None) -> None` 只检查、不写：

1. 默认读取队列；可传 `ReviewShardStore.read_state_sources()` 的结果复用已加载队列，manifest
   不存在时视为空队列。
2. 队列有未经证明的 schema-1 历史时拒绝，路径 `calculated_completion_ids`。
3. 按 `event.reviews` 顺序，第 i 条的 completion ID 为显式值，缺省时为 `"<event.day ISO>#<i>"`：
   事件内重复时在 `reviews[i].completion_id` 拒绝；**先**查重复、**再**查复习项：`review_id` 不在队列中
   时在 `reviews[i].review_id` 拒绝。

`advance_review_queue(review_store, event, *, algorithm=None, source_state=None) -> ReviewQueueAdvanceReport`
先做与预检相同的检查，然后：

- 缺省算法为 `LadderSm2Algorithm()`（strict）；CLI 按配置 `review_policy.self_rating_mode` 构造。
- 逐条按事件顺序处理：completion ID 已在队列的已计算集合中 → 记入 `replayed_review_ids`，不推进；
  否则对**当前**状态（同一事件内已推进过的项用推进后的状态）调用 `algorithm.advance`，记入
  `advanced_review_ids`；`completed_on` 早于原 `last_reviewed_on` 时同时记入 `late_review_ids`；
  原 `last_reviewed_on` 非空时推进后取两者较大值，日期不后退。
- 算法的 `self_rating_mode` 为 `lenient`、`check == "none"` 且自评为 `basic`、`fluent` 或缺省时，
  记入 `needs_check_review_ids`。
- 没有任何推进时不写队列，`write_report` 为 `None`。否则调用一次
  `ReviewShardStore.write(全部队列项, calculated_completion_ids=原集合 ∪ 本次推进的 ID)`，
  队列与已计算集合在同一次 manifest 替换中提交。
- 报告中的各元组按事件顺序排列；同一复习项在一个事件里推进两次时会出现两次。

CLI `day-plan record` 的顺序是：解析 `--done` → 预检队列 → 冻结锁存检查 → 写完成事件 → 推进队列。
推进失败时完成事件已经落盘，CLI 报告"completion event written … but the review queue was not
advanced"并退出 2。

## 10. 与旧文档 / 代码注释的出入（以代码为准）

| 编号 | 出入 | 分类建议 |
|---|---|---|
| D1 | 完成事件与月结的"只写一次"是 `path.exists()` 后 `os.replace`，不是 `AGENTS.md` 已知缺陷第 1 条要求的 `os.link` 原子不覆盖发布；两次检查之间另一个写入者可被覆盖 | 安全登记（需要并发写入者恰好插入） |
| D2 | 原先 `parse_day_plan` 只接受字符串 `day`，拒绝未加引号的 YAML 日期标量；`"2026-13-01"` 这类非法日期字符串抛 `ValueError`，`day-plan submit` 出 traceback | **WP-R3 已修**：接受日期标量，非法日期字符串为 `StorageError`（退出 2），见 §3；回归测试 `tests.test_day_plan_store.HandWrittenPlanInputTest`、`tests.test_cli.DayPlanCliTest` |
| D3 | 原先 `parse_day_plan` 不检查数值类型：字符串分钟数使 `check_invariants` 抛 `TypeError`（traceback）；布尔值与浮点数被当作数字接受并落盘 | **WP-R3 已修**：非整数（含布尔、浮点）为 `StorageError`（退出 2），见 §3；回归测试同 D2 |
| D4 | 日计划 manifest 读取不校验 `schema_version` 与条目键；条目缺 `date` / `path` 等键时抛 `KeyError`。`load_day_plan` 对缺失的当前版本文件抛 `FileNotFoundError`，而 `read_state_sources()` 已改为 `StorageError`（sol 136 M1） | 安全登记（需手工篡改 / 删除内部文件） |
| D5 | `DayPlanStore.write_day_plan` 不校验 `actor` / `input_hash`，而 `RoutePlanStore.write_route_plan` 会校验；目前只有 M19 保证其形状 | 登记；如需对齐另开工作包 |
| D6 | 日计划版本文件用 `os.replace` 发布，崩溃遗留的孤儿版本会被下一次写入覆盖；`RoutePlanStore` 对同类孤儿拒绝并要求用户手动删除 | 行为可接受（孤儿从未被引用），记录差异 |
| D7 | `load_day_plan` 先 `read_bytes` 核对摘要、再经 `read_text` 解析，同一文件读两次（`AGENTS.md` 已知缺陷第 2 条）；`day-plan record` 的预检与推进也各读一次队列 | 安全登记（需另一进程在两次读取之间替换文件） |
| D8 | `load_month_completions` 不核对文件名与事件日期是否一致，而 `delivered_words()` 与 `read_state_sources()` 会核对 | 安全登记（需手工放错文件） |
| D9 | 模块内注释（"CompletionEvent -> ReviewShardStore" 一节）仍写"同日同质量视为重放、同日不同质量拒绝"，已被 D8′ 的 completion ID 规则取代；模块 docstring 称所有记录都经 `os.replace` 发布，冻结事件实际用 `os.link` | 文档过时，代码正确 |
| D10 | `contracts/freeze.md` 写冻结门"在每次文件提交前"运行；实际只在版本文件发布前（原计划与重读各一次）运行，manifest 替换前不再调用 | 措辞差异，行为与本规格 §4 一致 |
| D11 | `docs/模块地图.md` M13 的验收命令未包含本规格的契约测试 | 模块地图更新时补上 |

## 11. 契约测试

`tests/contract/test_day_plan_store_port.py` 固定本规格新增的约定：manifest 形状与排序、按日版本号、
日计划文件字段顺序与解析缺省、`load_day_plan` 摘要核对、空权重拒绝、写入护栏顺序、重读冻结门、
完成事件与月结路径、冻结载荷校验、隐式 completion ID 与预检检查顺序。其余行为由
`tests/test_day_plan_store.py`、`tests/test_review_queue_advance.py`、`tests/test_longitudinal.py`、
`tests.contract.test_freeze_port`、`tests.contract.test_state_sources_port`、
`tests.contract.test_planner_port` 与 `tests.contract.test_availability_port` 覆盖。

替换后的验收命令：

```text
py -3.12 -m unittest tests.contract.test_day_plan_store_port tests.test_day_plan_store
  tests.test_review_queue_advance tests.test_longitudinal tests.contract.test_freeze_port
  tests.contract.test_state_sources_port tests.contract.test_planner_port
```
