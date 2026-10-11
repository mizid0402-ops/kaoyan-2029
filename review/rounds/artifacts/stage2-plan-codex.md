# 阶段②「24 个月计划与月度闭环」独立方案复核（Codex）

日期：2026-09-15  
范围：只读复核与方案；未查看另一位评审者的产出；未修改仓库文件。

## 0. 结论先行

**落地判断：能落地，但当前还没有落地。** 现有五个模块证明了若干纯函数内核可用，却没有形成“24 个月路线 → 当日事实快照 → AI 提案 → 系统验收并落盘 → 实际完成事件 → 月结 → 下一版路线”的闭环。主控列出的五个缺口均成立，其中缺口 1 的论证需要修正：系统缺的是可复现的事实快照，不是“替 AI 算出今天该给多少”。

②不应整体后置。阶段①已经有明确冻结总账，而且该总账明确说未人工 `reviewed/approved` 不影响复习调度；因此可以开始实现阶段②的合同、状态与闭环。但在以下三件事确定前，不应宣称“真实 24 个月计划已启用”：

1. 明确 `start_date / end_date / target_exam_date` 的关系和日历月语义；
2. 确定可执行学习单元的口径，以及完成后如何确定性地产生/推进 `ReviewItem`；
3. 把冻结词库中的只读词表与可变投递状态分离。

## 1. 实测范围与证据

以下均为本轮实测：

- 完整阅读 `review/rounds/round-36-stage2-brief.md`，并只读检查了五个现有模块、CLI、模型、分片存储、决议文档、阶段收尾总账和相关测试。
- `tests/` 中静态计数为 **306 个 `test_*` 函数**；本轮遵守最小范围原则，仅运行 `test_longitudinal.py + test_monthly_close.py`，结果为 **45 passed, 16 subtests passed**。因此“306 个测试函数存在”已复核，“本轮重新证明全套 306 全绿”没有做，也不作该声称。
- `data/monthly_reports/`、`data/study_records/`、`data/review_queue/`、`data/ability_profile/`、`data/course_schedule/` 当前均为 **0 个文件**。
- 阶段①冻结总账存在。当前三份主调度来源中，408 多源树 410 节点、数学一 69 节点、英语一 24 节点，状态均为 `extracted`；总账明确写明这不阻碍复习调度。
- 词库 SHA-256 仍为 `839d48be37d7716b1a12da04e3e2293868ee379b6e09a13dd198dae5498d0e2c`，与冻结总账一致；库内已有 15 条 `delivery_log`，`remaining_pool()` 当前返回 3137。
- `PlanHorizon(start=2026-09-15, months=24)` 的实际结果是 `end=2028-09-04`，枚举 721 个日期。它实现的是 `24×30` 天跨度并把首尾都算入，不是日历意义上的 24 个月；源码注释还误写成“730 days”。
- `monthly_close.close_month()` 接收的是 `list[DayPlan]`，汇总字段来自计划值，没有实际完成记录。重复传入同一天两次会得到 `days_planned=2`、`days_unplanned=29`，并把分钟重复累计。
- 护栏探针确认：`vocab_new_items=-5`、`backlog_minutes=-1` 均可通过；不传 `subject_minutes` 时比例倒置检查根本不运行；`max_single_item_minutes=30` 会把一个 60 分钟的**整个知识通道**当成“单个单元”拒绝；声明 40 分钟 backlog 后，60 分钟容量、100 分钟分配会被判合法。
- `KaoyanConfig` 仍把 `total_daily_minutes` 定义为唯一权威日预算，学科权重也在配置中静态保存；`review_clip.py` 直接使用这两个静态值。`budget.py` 的“分钟总额”虽已参数化，但动态学科权重并未贯通。
- `vocab_channel.preview_batch()` 接受调用方任意非负词数，但实际唯一写入器 `tools/daily_words.py` 仍强制 `10 <= count <= 20`；`--count 5` 实测退出码 2。

## 2. 对五个缺口的逐条复核

| 缺口 | 判断 | 实测事实 | 修正/限定 |
|---|---|---|---|
| 1. 没有当天状态输入面 | **成立** | 有零散原料：`remaining_pool()`、复习条目及排序核、知识树；但没有统一快照，没有知识学习进度，真实 review queue 为空 | “没有快照所以系统算不出今天给多少”是错误表述。系统不该算数值；它应确定性给出剩余量、到期项、积压、历史实际、距目标日等事实，AI据此定数值 |
| 2. 没有 AI 提交决定接口 | **成立** | `DayPlan` 只是 dataclass；现有 `py -m ky` 只有只读 preflight/ledger，没有计划提交、验收、版本或原子提交 | 不需要在系统内调用模型。最小接口是“AI/调用方生成提案文件，CLI 校验并提交” |
| 3. 计划没有落盘与查询 | **成立** | 五个②模块无计划写入；review 分片只服务 `ReviewItem`，语义不匹配；计划相关数据目录为空 | 不应硬复用 review shard schema。按月/按日的不可变版本文件已足够，不需要先上 SQLite |
| 4. 没有完成反馈回路 | **成立，而且比底本描述更严重** | 没有完成事件模型、写入入口、复习推进器；当前月结拿 `DayPlan` 当“observed outcome” | 必须拆分 `planned` 与 `actual`。投递单词也不等于学会单词，不能用 delivery 代替完成 |
| 5. 系统/AI 边界未划清 | **成立** | 当前护栏存在空洞且跨模块口径冲突；没有“拒绝后不写入、返回结构化错误、AI重提”的协议 | 不需要系统自动修计划。合法性失败的最小闭环就是：退出码 2 + 结构化 violations + 零写入；AI基于错误重提 |

没有一项应判为“不必要”。但缺口 5 是架构规则而非单独功能模块，落实点应分布在合同、CLI 和存储提交协议中。

## 3. 主控漏掉的承重缺口

### 3.1 24 个月路线本身并不存在，且当前日期语义错误

【实测】`longitudinal.py` 只有若干独立 `DayPlan` 和汇总，没有阶段、月容量包络、路线版本、目标考试日或月度修订关系。当前“721 天”不能等价于“24 个日历月”。

【判断】最小终态必须有一个 AI 编写、系统验收的 `RoutePlan`：只把未来做成 24 个“计划月/阶段容量包络”，不预生成 721 天的具体任务。否则要么没有纵向结构，要么制造两年后的虚假精度。

### 3.2 缺少“冻结知识树 → 可执行学习单元 → 复习队列”的连接层

【实测】知识点模型没有学习完成状态和预计耗时；`DayPlan` 只有知识通道总分钟，没有 `knowledge_point_id` 列表；review queue 为空；代码中只有 `with_deferral()`，没有完成后创建/推进复习计划的状态机。

【判断】这比单纯的“快照缺失”更基础。快照必须能列出可计划的节点，日计划必须绑定具体单元，完成事件必须确定性地产生或推进 `ReviewItem`。否则所谓“把①变成计划”实际只是在分分钟数。

首版建议复用已有 `DAY_ASSESSABLE_SCOPES = {section, item}` 作为默认候选口径，较大的节点拆成多个 pass；是否允许 `chapter` 直接作为日任务列入不确定项，不应擅自放宽。

### 3.3 新决议尚未贯通原有配置和排序核

【实测】`KaoyanConfig.total_daily_minutes`、静态 subject weight、review soft/hard cap 仍按固定配置工作；`budget.py` 仍从配置取权重。词汇预览允许任意 N，但真实投递器只允许 10–20。

【判断】不能把“纯函数测试通过”误认为新决议已经端到端实现。应引入每日日预算上下文，把 AI 的 `available_minutes` 和当日权重传给既有排序/切分核；排序键本身不改。

### 3.4 五条护栏尚不是可承重的提交合同

【实测】比例检查可被省略；“单单元上限”实际检查通道总量；负词数/负 backlog 可过；重复日可被月结双计。决议文档的五条还与 brief 的“五条”不完全相同：前者含 `due_date/defer_count`，后者以“不为负”替代。

【判断】提交合同必须逐字段闭合：所有数量非负、学科分钟合计等于知识通道、每个 pass 单独受上限、已安排分钟不超过可用容量、未安排需求逐项进入 backlog、同一版本同一天唯一。`due_date` 不变和 `defer_count+1` 继续由既有 review 核验证。

### 3.5 冻结词库与可变投递日志冲突

【实测】整个 SQLite 文件已按字节冻结，但 `daily_words.py` 会写其内部 `delivery_log`。下一次合法投递就会改变冻结哈希。

【判断】②不得继续把可变状态写入冻结数据库。首版把现有 15 条 delivery 作为基线导入/引用，后续 `vocab_delivered`、`vocab_practiced` 写入外部学习事件；词表 SQLite 永久只读。投递与掌握必须分开统计。

## 4. 最小可执行终态

最小终态是 **5 个责任模块 + 1 组 CLI**，复用现有 `budget.py`、`review_clip.py`、`vocab_channel.py` 和 `ReviewShardStore`，不替换排序核。

### M1. `ky/schedule/planning.py`：路线与当日提交合同

包含：

- 日历感知的 `RoutePlan`：`route_id`、不可变 `revision`、`start_date`、`end_exclusive`、`target_exam_date`、24 个连续月包络、`policy_version`、阶段①输入哈希；
- 每个月包络的阶段标签、预测容量、学科权重、通道容量、目标词数；这些数值都由 AI 提案，系统只验闭合性；
- `DailyProposal`：`day`、`route_revision`、`snapshot_sha256`、`available_minutes`、当日学科权重、具体 `new_units[{knowledge_point_id, pass_id, planned_minutes}]`、`vocab_new_items`、`minutes_per_word`、notes；
- `CommittedDayPlan`：在提案上增加系统确定的 review 选择、词汇 batch、逐项 backlog、验收时间和内容哈希；
- 完整护栏。`max_single_item_minutes` 检查 pass，而不是通道合计。

“24 个月路线”只到月级容量/阶段边界；具体日计划按当天快照滚动提交。这样既保留纵向结构，也不假装知道 721 天后当天能学几分钟。

### M2. `ky/schedule/state_snapshot.py`：确定性事实快照

只读汇总：

- 路线版本、当前计划月、距目标考试日天数；
- 各科可执行节点总数、completed/partial/remaining 数量及 ID，已有实际分钟；
- 今日到期复习项、每项成本、review backlog、近窗实际用时；
- 词汇基线已投递、外部事件已投递/已练习、剩余唯一词族；
- 上月月结及未清 backlog；
- 每个输入文件/事件集合的 SHA-256、`as_of` 和快照 SHA-256。

相同输入必须生成字节一致的规范 JSON。快照只陈述事实和明确的初始默认 40/20/40，不输出“推荐今日学多少”。

### M3. `ky/storage/stage2_store.py`：不可变版本落盘与查询

本地文件/事件是唯一真相源；SQLite 留到阶段③作为可删重建投影。建议路径：

```text
data/plans/routes/<route_id>--r0001.yaml
data/plans/snapshots/<snapshot_sha256>.json
data/plans/daily/YYYY-MM/YYYY-MM-DD--r0001.yaml
data/study_records/YYYY-MM/<event_id>.yaml
data/review_queue/manifest.yaml + shards/...       # 由事件重建的投影
data/monthly_reports/YYYY-MM--r0001.yaml
```

所有已提交文件不可覆盖；修订新增 revision。提交过程先完整校验并在临时文件生成，再以单一 manifest/current 指针作为原子可见点。重复 `decision_id/event_id` 必须幂等或明确拒绝，不能重复计数。

### M4. `ky/progress/study_events.py`：实际反馈与复习状态投影

最小事件字段：`event_id`、`occurred_at`、`plan_id`、`task_id/review_id`、`event_type`、`result={completed|partial|skipped}`、`actual_minutes`、`evidence_origin={user_report|timer|import}`、`recorded_by`、notes。

约束：

- 计划被接受不等于完成；AI 自己的文字也不构成完成证据；
- 新学单元完成后按版本化的既有 bootstrap policy 确定性地产生 review item；复习完成后确定性推进状态；不由 AI 直接写 `due_date/quality`；
- review queue 是事件的可重建投影，分片存储可复用；
- 单词至少区分 `vocab_delivered` 与 `vocab_practiced`，均写外部事件，不改冻结 SQLite。

这里不引入 FSRS，也不改 `review_clip.py` 的八键排序；只补齐排序核前后的生命周期。

### M5. `ky/schedule/monthly_close.py`：真实月结

把输入从单一 `DayPlan` 列表改为“已接受计划 + 实际事件 + 月初状态 + 月末状态”。输出至少分开：

- planned / actual / variance，按科目、通道、具体任务统计；
- days planned / recorded / unplanned / duplicate-or-invalid；
- 新学完成、复习完成、词汇 delivered/practiced；
- 未完成任务 ID、review backlog ID 与分钟、未知耗时项；
- 输入哈希、route revision、close revision、violations。

月结只报告和结转事实，不生成下月预算。AI读取月结后的新快照，提交下一版路线或当日计划。

### CLI：`py -m ky plan ...`

```powershell
# AI先提交月级24个月路线提案；系统验收，系统不生成数值
py -3.12 -m ky plan route-submit --file route-proposal.yaml --json

# 只读输出今日事实
py -3.12 -m ky plan snapshot --date 2026-10-01 --json

# 验证但不写；适合AI第一次自检
py -3.12 -m ky plan validate --file daily-proposal.yaml --json

# 重算当前快照、防陈旧、校验、确定性选review/words，然后原子提交
py -3.12 -m ky plan submit --file daily-proposal.yaml --json

# 第3个计划月第2周；计划月/周的边界必须在合同中唯一规定
py -3.12 -m ky plan show --month-index 3 --week-index 2 --json

# 记录用户/计时器提供的实际，不接受“因为计划了所以完成”
py -3.12 -m ky plan record --file study-event.yaml --json

# 由计划和事件生成并提交月结
py -3.12 -m ky plan close-month --month-index 1 --commit --json

# 只读重放和全链校验
py -3.12 -m ky plan verify --all --json
```

退出码建议沿用现有约定：0 成功，2 合同/状态冲突，3 用法错误，1 内部错误。任何 2/3/1 都必须保持生产状态字节不变。

## 5. 系统与 AI 的边界

| 事项 | AI 管 | 系统管 | 验证方式 |
|---|---|---|---|
| 24 月路线 | 阶段标签、每月预测容量、预测权重、词量目标及修订理由 | 24 月连续性、日期边界、非负与合计、输入哈希、版本 | route contract + 重放哈希 |
| 当日可用时间 | 决定数值 | 检查非负、与本日提案内部合计一致 | schema + arithmetic invariants |
| 动态学科分配 | 按 remaining/completed 作判断，选择权重和新学单元 | 提供真实 remaining/completed；验证 ID 存在、权重和为 1、分钟闭合、不得倒置 | snapshot hash + unit contract |
| 到期复习 | 决定给当天多少总容量时需考虑它 | 保留现有排序核，确定性选择/延期，维护 backlog；AI不能改顺序、due_date、defer_count | 既有排序回归 + 新动态预算适配测试 |
| 单词 | 决定 N 和每词成本估计 | 按冻结顺序选具体词，校验池容量，记录 delivery/practice 事件 | 同输入 batch 一致；冻结 DB 哈希不变 |
| 超载 | AI明确哪些需求放 backlog，可重提计划 | 验证 scheduled 不超容量、所有未排需求逐项可见；不静默截断 | 守恒式和 ID 集合相等 |
| 实际完成 | AI可把用户陈述结构化，但不能自行断言完成 | 只接受带来源的事件；确定性更新投影 | 事件 ID、来源、计划引用、重放 |
| 月结与调整 | 读取事实后决定下月是否改路线/数值 | 只计算 actual/variance/backlog，不开处方 | 同一事件集月结字节一致 |

关键协议：系统不“修正”非法提案。它返回机器可读的 `violations[{code,path,actual,expected}]`，不落盘；AI自行修改后再次提交。系统负责的是**事实、守恒、权限、确定性和审计**，AI负责的是**有不确定性的数值判断与取舍**。

系统能验证“提案合法”，不能验证“这个权重教育学上最好”。后者只能通过真实完成率、积压与学习证据按月回看；不得把合法性测试包装成效果证明。

## 6. 实施顺序与机器可验证完成标准

### Step 0：先固定语义，不写业务功能

确定计划起止、24 个日历月/计划月定义、目标考试日的暂定状态、日任务可用 scope、review bootstrap policy 版本、词汇“每天”是否允许 0。

完成标准：形成 schema fixtures；`end_exclusive == add_calendar_months(start, 24)`；24 个 period 无缝、无重叠；闰年和月末（1/31、2/29）用例明确。当前 2026-09-15 → 2028-09-04 的结果必须被回归测试拒绝为“24 calendar months”。

### Step 1：修正合同和动态预算贯通

实现 M1；让既有 review 核接收当日预算上下文、budget 接收当日权重，保持排序键不变。

完成标准：

- 负 `vocab_new_items/backlog/actual_minutes` 全部拒绝；
- 缺 subject breakdown、分钟不守恒、重复日期/版本、陈旧 snapshot 全部拒绝；
- 60 分钟知识通道由 3 个 20 分钟 pass 构成时通过，单个 31 分钟 pass 在上限 30 时拒绝；
- 对同一批 due items，改造前后在相同 120/40-20-40 输入下 selected 顺序逐项相同；
- 40、120、300 分钟日预算均可跑，review hard cap 以当日预算计算；
- 只跑相关合同、budget、review、longitudinal 测试即可，最小范围通过前不跑全套。

### Step 2：不可变存储与查询

实现 M3，不接 AI、不接月结。

完成标准：有效 route/day/event 写入后可逐字节重读；相同 ID 重放不重复；非法输入、模拟中途失败、陈旧 revision 后目录哈希不变；`show --month-index 3 --week-index 2` 返回唯一确定日期集合；两个进程竞争提交只能有一个 current revision。

### Step 3：事实快照与可执行单元目录

实现 M2，连接冻结树、题目权重、事件、review projection、只读词库。

完成标准：基线快照重复 100 次 SHA-256 相同；每个 remaining/completed ID 都存在于冻结树；集合互斥且并集守恒；删除/增加一个事件只改变预期计数；快照列出每个输入的哈希；快照生成不改任何源文件。

### Step 4：AI 提案验收链

实现 `validate/submit`，但不在程序内调用模型。

完成标准：合法提案产生 committed plan；非法提案 exit 2、结构化定位到字段且零写入；同一 proposal + snapshot + policy 产生相同 review IDs、vocab IDs、backlog 和 decision hash；提交时状态已变化则以 `STALE_SNAPSHOT` 拒绝；不得自动改权重、词数、任务或 notes。

### Step 5：完成事件与 review/vocab 投影

实现 M4，复用 review shard 存储作为可重建投影。

完成标准：计划提交不会增加 completed；一条 `completed` 事件只推进对应任务一次；重复 event 不双计；partial/skipped 不冒充 completed；新学完成确定性产生 review item，复习完成按 policy 推进，单靠 self-rating 不改 due date/quality；从空投影重放全部事件得到字节一致 review queue；所有投递后冻结词库 SHA-256 保持不变。

### Step 6：真实月结与结转

实现 M5。

完成标准：月结同时显示 planned 与 actual；重复日不会双计且会报错；未记录日显式列出；backlog 以 ID 集合和分钟守恒；相同输入月结 hash 相同；月结对象不存在 `recommended_budget/next_month_minutes`；下一次 snapshot 能读到结转，但不会自动修改路线。

### Step 7：最小端到端验收

使用隔离 fixture 完成一次：提交 24 月 route → 快照 → 合法日提案 → 完成/partial/skipped 事件 → review 投影 → 月结 → 下一月快照；再做一次非法提案和一次陈旧快照反例。

完成标准：`py -3.12 -m ky plan verify --all --json` 返回 0；两次从零重放的所有派生产物哈希一致；阶段①冻结清单哈希全部不变；然后才补跑受影响测试集合。除非发现跨模块风险，不需要以全量 306 测试作为每一步的默认动作。

## 7. 明确不做

1. 不做阶段③ Web/SQLite 投影，不做阶段④课表协同，不做阶段⑤可视化。
2. 不预生成 721 天的具体任务；远期只做 24 个月级路线，日计划临近当天提交。
3. 不替换或重写 `review_clip.py` 的既有排序核，不引入 FSRS、SM-2 新库或通用优化求解器。
4. 不在系统内托管/调用 AI，不做自动 retry、自动修正、自动 fallback；只提供文件合同和 CLI。
5. 不写死 120 分钟、20 词、40/20/40，也不把临考清空 backlog 恢复成硬约束。
6. 不导入长难句/短语材料；保留 schema 槽位，但无 `material_ref` 时不得生成可执行 phrase task。
7. 不修改阶段①冻结树、题目索引、权重或词库；尤其不再写冻结 SQLite 的 `delivery_log`。
8. 不把 `extracted` 冒充 `reviewed/approved`，也不为补齐 G1/G2 分值而编数据。
9. 不把 AI 自述、计划落盘、单词已投递当作实际完成或掌握。
10. 不做成绩预测、教育效果保证、能力画像或自动处方。

## 8. 不确定项与需要主控拍板的最小清单

1. **路线日期**：目标考试的确切日期尚未给出；从 2026-09-15 起算 24 个月也不会覆盖到“2028 年 12 月初试”。需要明确路线是“从某日起 24 个月”还是“倒推考试日前 24 个月”。在此之前可以写合同和测试，不能落真实 route。
2. **月的定义**：自然月、从 start_date 起的周年月、首尾残月三者会给“第 3 个月第 2 周”不同答案。必须选一个并写进合同。
3. **可执行节点粒度**：本方案保守采用已有 section/item；数学 section、408 item/section 的实际单次工作量仍需通过 pass 拆分。chapter 是否可直接排一天未确认。
4. **复习推进 policy**：现有模型允许 `fixed_bootstrap/sm2_lite`，但没有状态推进实现；具体间隔、30 分钟单 pass 上限、0.45/0.60、3 天/2 次和 7 天窗口均缺真实校准。它们应作为带版本、可替换的暂定 policy，不应写成效果事实。
5. **“每天分一点词”与 AI 自由决定 N**：若 AI 可给 0，就不能机器保证“每天都有词”；若强制 `N>0`，又新增了决议未明确的硬约束。本方案默认不强制正数，只在月结显式报告 0 词日，需主控确认。
6. **已有 15 条 delivery 基线**：它们在冻结 SQLite 内，尚未核对是否代表真实学习、仅投递或测试。迁移时只能记作 `delivered_unknown_practice`，不能当 completed。
7. **实际记录主体**：用户可自由选择每日/每周/里程碑频率；首版事件需要允许批量补录，但如何证明是用户报告而非 AI 猜测，需要 UI 之外的最小操作约定。
8. **政治通道**：当前配置样例中政治未激活，且阶段①没有政治知识树。本轮不把它算入可执行新学单元；未来激活条件应另行版本化，不能用“三科”快照暗中生成第四科任务。

## 9. 最终一句话

**②可以落地；最小终态包含“路线/当日合同、事实快照、不可变存储与查询、完成事件及复习投影、真实月结”五个模块和一组 CLI；边界是 AI 决定所有带判断的数值与取舍，系统只提供事实、执行既有确定性排序、校验守恒与权限并持久化，非法提案一律结构化拒绝且零写入。**
