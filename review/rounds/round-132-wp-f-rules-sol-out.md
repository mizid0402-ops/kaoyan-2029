# WP-F 学习状态投影细则审查（只审规则）

审查基线：`git archive fa9e11c` 的临时归档；阶段决议与前端范围文档按仓库现有文本只读核对。没有改实现，没有跑全量测试。严重度只按个人本机正常使用判断。

## 总判断

WP-F 把队列、计划、完成记录作为**已记录事实**投影，方向符合 `docs/阶段2.5-接缝收口.md` 的 WP-F 和“文件是真相源”的前端决议。但 F2、F3、F5 有已确认的端口或数据形状冲突；F1/F6 尚不能推出“站点保存后即时可见”。这些是实现任务书发出前应修的规则问题。

## 逐条结论

| 条款 | 结论 | 依据、反例与改法 |
|---|---|---|
| F1 | **修改** | 同一可重建 SQLite、schema 升到 3、参考表逐列逐行保留，可以接受。须明确“逐行不变”指相同参考输入下的行集合及字段值，`projection_meta` 版本与新增键是明示例外。现有 `ky/projection/__init__.py:582-588` 用 `os.replace`，Windows 上旧库被 Datasette 打开时会报 `ProjectionInUseError`；`serve.py` 使用 `--immutable`，不会因路径替换自动重读。故“同一命令”只证明**离线**重建；前端 W2 必须另定关闭旧连接、重建、重新打开/刷新并确认新版本的流程，不能把 WP-F 验收写成运行中即刻可见。`tests/test_projection_service.py:160` 还固定断言版本 `2`；依赖版本的消费者与测试需显式升级或明确拒绝 schema 3。 |
| F2 | **修改** | 只走公开解析端口是对的，但列举的端口不足以完成 F3。`DayPlanStore.load_month` 要先知道月份，且每个 `load_day_plan` 再读一次月 manifest（`day_plan_store.py:704-707,690-702`）；补一个 M13 公开、只读、一次遍历的**当前计划及完成事件枚举**，同时返回计划版本/来源。`ReviewShardStore.load()` 在缺 manifest 时实际抛 `StorageError`（临时归档只读探针已复现），不能按 F5 直接调用；必须显式按缺 manifest 空队列的既有 CLI 口径处理，存在但无效则报错。F3 的逐文件精确 SHA-256 也不能从所列对象读取端口得到；相关存储端口须在**同一次读取**中公开所用文件的相对路径和原始字节摘要，或删去“精确输入字节”承诺。不可加载对象后再读文件单独算哈希。 |
| F3 | **修改** | `ReviewItem` 还含 `revision/title/granularity`（`ky/models.py:595-610`）；排队页面至少需要 `title`，投影要保留公开事实字段。现有 `DayPlan` 只有日期、渠道分钟、`subject_minutes`、`notes`，没有逐条安排（`ky/schedule/longitudinal.py:121-132`）；不能凭空生成 `day_plan_entries`。改为当前计划主表完整保存渠道字段、`notes`，另设 `day_plan_subject_minutes(day, subject_id, minutes)`；如果以后出现真正任务明细，再由其新端口投影。完成复习表须保存 `completed_on/question_ref/self_rating` 和事件内顺序；以 `(event_day, ordinal)` 标识记录，因为 `completion_id` 只在**同一事件内**保证唯一（`ky/schedule/completion.py:338-393`）。词汇表须区分 `delivered` 与 `practiced`，不能将“投放”写成“掌握”。`route_phases` 要有 route ID/revision、阶段边界、label，科目分钟用子表，避免在一列塞任意科目。`freeze_events` 的序号/类型/日期足以重算锁存。当前版本日计划足以展示**当前日历**，完成事件足以展示已记录活动；历史计划版本、周计划、能力画像/目标差距不在此包事实范围，不能宣称已满足 §7.1 全部“学习进度”。历史版本文件虽保留，旧版来源信息没有保留（`contracts/planner_port.md` §M13 provenance），本轮不应伪造可审计的历史计划视图。完成事件存在也不等于队列推进成功：`day-plan record` 先落事件再推进队列，后一步可能失败（`ky/__main__.py:1035-1054`）；前端必须把“已记录完成”与“已推进队列”分开表述。 |
| F4 | **修改** | 不固化随查询日期变化的“今日到期/积压/冻结”是对的。`freeze_latched` 若保留，仅由 M27 `latch_active(events)` 算，命名为**事件锁存状态**，不得被前端当成 `frozen`；后者还取决于查询日、队列、配置和阈值（`contracts/freeze.md`、`ky/freeze/port.py:74-101`）。不允许前端各处自行写 SQL 复制口径：在 **M15 的公开只读查询端口**定义 `status_as_of(projection, day, config, policy)` 之类的日期参数接口，复用/提取 M12 的计数规则和 M27 的 `assess_freeze`，返回 `as_of`、到期、积压及完整冻结状态。尤其 M12 `due_today` 是 `due_date == day`，积压是 `< day`，二者不能混为“到期及以前”。若端口只读投影，须规定如何由投影行构造同一规则的输入；不要再从状态文件读一遍造成两份时点。 |
| F5 | **修改** | 目前 `state.review_queue` 与 `state.plans` 是注册表**必填**，不是可缺省键（`contracts/workspace.md:108-111`）；`state.routes` 可未登记，未登记即空；已登记但目录不存在时 `RoutePlanStore.current()` 为 `None`，M13 根目录不存在也是空。队列缺 manifest 按现有 CLI 约定是空，但 `ReviewShardStore.load()` 本身不是空。`state.availability` **登记即必须有文件**，缺失报契约错误（`contracts/availability.md` 与 `ky/availability/port.py:103-114`），不能当空。已登记路径存在但类型错误、manifest 或有效记录损坏须失败，不得降级为空。整个重建 fail-closed、旧投影不变是正确的，否则页面会显示一部分新事实、一部分旧事实；但前端遇重建失败必须显著显示“投影未更新”与出错路径，不可把旧库当本次写入后的新状态。修复源文件后重跑可恢复；投影重建不能改坏文件。 |
| F6 | **修改** | “成功写入登记的状态源 → 重建成功 → 新库查到本次事实”应成为契约。测试需分别覆盖 `submit/record/route submit/resume/review-queue migrate --apply` 的实际写入分支；`record` 要核对完成事件和（带 `--review-store` 时）队列两侧，`resume` 要核对重排结果与 resume 事件。显式 `--store`/`--items` 覆盖到非注册表路径时，不承诺 WP-F 会投影；未实际写入的 dry-run/no-op 也不应强求“新行”。额外测重建失败时旧库原字节不变，且调用方不会报告刷新成功。本包不自动重建可以，但与前端即时可见之间的集成门槛须留给 W2，不能视为已达成前端闭环。 |
| F7 | **同意** | 保留“不推荐”约束；表名、字段和说明只表达持久事实。计划的 `backlog_minutes` 是**写入当时的计划字段**，不能冒充按查询日计算的实时积压。 |
| F8 | **同意，补一条条件** | 相同已登记输入字节、注册表字节和明确的“空存储”状态，两次构建表与 meta 相同；规定枚举、行排序、JSON 键排序稳定。`state_inputs` 只记录实际参与本次构建的有效文件，不把旧版计划或未登记的孤儿文件算成当前事实。 |

## 建议的最终规则（给决策者改写任务书）

1. **范围**：schema 3 沿用同一重建入口和 SQLite 目标，参考表内容在相同参考输入下保持 schema 2 值不变；学习状态表只存当前队列、当前日计划及其科目分配、历史完成事件、冻结事件、当前路线、手填可用分钟。`projection_meta` 增加状态来源摘要。当前 `serve` 的在线刷新问题列为 W2 的明确前置门槛。
2. **读取端口**：M15 不解析状态 YAML。M13 提供可枚举的计划/完成记录只读端口；队列缺 manifest 用既有空队列口径。每个相关端口公开“解析对象 + 同次读取的来源路径/原始 SHA-256”，避免内容与摘要来自不同读取。增长到约 800 天的耗时目前**未实测**，不得先断言可接受或不可接受；验收增加此规模的定量构建时长记录，若慢，优先把 M13 月 manifest 一月读一次、流式遍历当前文件并批量写 SQLite，仍以文件为真相源，不做独立状态缓存。
3. **行身份和语义**：完成记录用事件日期和事件内序号定主键，`completion_id` 保留为事实字段；词汇投放/练习分型；计划科目分钟从 `subject_minutes` 投影，不设无来源的逐条任务。只展示当前计划，旧版本历史不承诺进入投影。记录完成与队列推进分别展示。
4. **日期查询**：表不存“今天”；由 M15 对外提供显式 `as_of` 查询，调用 M12/M27 的公开纯规则形成统一的到期、积压、冻结口径。`freeze_latched` 可作为事件锁存事实，不等于当日冻结。
5. **缺失和故障**：可选注册表键未登记为空；已登记的 availability 文件缺失失败；队列缺 manifest、路线/计划目录未建按各自**已确认**的空库口径处理；存在但无效的源失败并保持旧投影字节。重建失败不得向站点报告保存后的展示已刷新。
6. **验收与版本**：按 F6 的真实写入分支做最小契约测试；对 schema 2 的固定断言及外部消费者作显式迁移。相同输入的表/meta 确定性与原子替换继续守护。全量测试未跑（按 `AGENTS.md` 由决策者提交前统一跑）。

## 验证边界

在归档内仅做只读端口探针：空 `RoutePlanStore.current()` 返回 `None`、空 `DayPlanStore.load_day_plan()` 返回 `None`、缺 manifest 的 `ReviewShardStore.load()` 抛 `StorageError`，并列出 `DayPlan` 字段。没有跑性能基准或全量测试；约 800 天的实际重建时长、未来前端连接生命周期、外部 schema 2 使用者数量均暂无法确认。
