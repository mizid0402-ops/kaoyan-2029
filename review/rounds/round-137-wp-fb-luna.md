# WP-F-b 实施报告（luna-c）

## 接口与实现

- `read_learning_state(workspace: Workspace) -> LearningState`：在
  `ky/projection/learning_state.py` 通过 M13/M26 公开读取端口取得队列、当前日计划、完成与
  冻结事件、当前路线及可用时间。`LearningState` 保存这些不可变快照、`state_inputs` 与
  `freeze_events_latched`。
- `write_learning_state(connection: sqlite3.Connection, state: LearningState) -> None`：在临时
  SQLite 数据库创建并填充学习状态表。
- `projection_schema_version` 升为 3。参考表创建和写入逻辑保持原样；`projection_meta` 增加
  `state_inputs` JSON 与 `freeze_events_latched` 两项。
- 状态源在创建临时输出前完成读取和校验；任一状态端口报 `ContractError` 时，不会替换既有
  投影文件。

## 表、列与来源

列名和 SQL 类型详见 `contracts/learning_state_projection.md`。

| 表 | 列 | 来源 |
|---|---|---|
| `review_items` | `review_id`, `revision`, `subject_id`, `knowledge_point_id`, `title`, `granularity`, `state`, `estimated_minutes`, `introduced_on`, `due_date`, `last_reviewed_on`, `schedule_mode`, `schedule_phase`, `interval_days`, `ease_factor`, `repetitions`, `lapses`, `defer_count`, `last_quality`, `last_self_rating` | `ReviewShardStore.read_state_sources()` 的 `ReviewItem` 与其 `schedule`。 |
| `day_plans` | `day`, `available_minutes`, `knowledge_minutes`, `vocab_minutes`, `vocab_new_items`, `phrase_minutes`, `backlog_minutes`, `notes`, `version`, `actor`, `input_hash` | `DayPlanStore.read_state_sources()` 的当前 `DayPlanRecord`。计划分钟数为写入当时记录值。 |
| `day_plan_subject_minutes` | `day`, `subject_id`, `minutes` | 当前 `DayPlan.subject_minutes`。 |
| `completion_events` | `event_day`, `review_count`, `delivered_word_count`, `practiced_word_count` | 每个完成事件一行，计数汇总该事件的子记录。 |
| `completion_reviews` | `event_day`, `ordinal`, `completion_id`, `review_id`, `completed_on`, `check_method`, `outcome`, `question_ref`, `self_rating` | 每个 `ReviewCompletion` 一行，按事件内原序编号。 |
| `completion_vocab_words` | `event_day`, `vocab_kind`, `ordinal`, `word` | `VocabProgress` 的 delivered / practiced 两组词分别入行。 |
| `freeze_events` | `sequence`, `kind`, `day` | M13 全部冻结与恢复事件。 |
| `route_phases` | `route_id`, `revision`, `phase`, `label`, `start`, `end_exclusive` | 当前 `RoutePlan` 的各阶段；不登记路线时为空。 |
| `route_phase_review_minutes` | `phase`, `subject_id`, `minutes` | 当前路线阶段的 `review_minutes` 映射。 |
| `availability_days` | `day`, `minutes` | M26 已登记可用时间。 |

`state_inputs` 的键格式是 `<注册表键>/<相对该存储根的 POSIX 路径>`，值由对应 F-a 端口提供。
可用时间文件是单文件来源，键使用 `state.availability/<文件名>`（相对其父目录）。哈希未由
M15 重读或重算。旧计划版本不纳入 `state_inputs`；仅当前路线修订纳入。

`freeze_events_latched` 取 `latch_active(freeze_events)`，写为 `"1"` 或 `"0"`。它描述冻结事件
历史是否仍有未恢复的锁存，不代表任意某一天的冻结状态。

## 定点变异验证

每次只对实现作临时变异，运行指定单测后恢复原实现：

1. 删除 `_review_rows` 中 `last_self_rating` 的绑定值。运行
   `py -3.12 -m unittest tests.contract.test_learning_state_projection.LearningStateProjectionTests.test_real_cli_writes_are_visible_after_rebuild`
   失败，SQLite 报 20 个绑定参数需要 19 个；测试捕获到字段投影遗漏。
2. 把路线条件临时改成无条件读取。运行
   `py -3.12 -m unittest tests.contract.test_learning_state_projection.LearningStateProjectionTests.test_missing_state_inputs_follow_registry_and_port_rules`
   失败，未登记的 `state.routes` 报 `ContractError: state.routes: not registered`。
3. 把锁存结果临时固定为 `False`。运行
   `py -3.12 -m unittest tests.contract.test_learning_state_projection.LearningStateProjectionTests.test_determinism_and_state_input_hashes_use_port_sources`
   失败，断言实际值为 `0`、预期值为 `1`。

## 验收

运行命令：

```text
py -3.12 -m unittest tests.contract.test_learning_state_projection tests.test_projection_service tests.contract.test_state_sources_port
```

输出：`Ran 22 tests in 5.674s`，`OK`。

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）

## 规模实测

临时工作区合成 800 天日计划、800 个完成事件及 800 个队列项；只计 `build_projection`。
耗时 **3.554 秒**，输出数据库 **761,856 字节**。写入合成输入的时间不计入此数值。

## 留给 F-c 的注意事项

- 按查询日期解释 `due_date`、逾期与实时积压；这些不是本次投影时计算的列。
- 结合 `freeze_events`、队列与查询日推导某天冻结状态；`freeze_events_latched` 只给事件历史锁存值。
- `day_plans.backlog_minutes` 等是存储的计划输入值，不应当作查询日实时积压。
- 所有日期是 ISO 文本；完成事件子项由 `event_day` 加 `ordinal` 稳定关联。当前路线表仅含当前修订。

## 建议

F-c 使用本规格的表名和列名建立只读查询端口，并保持按查询日推导的值不写回投影。网页重载
流程及运行中 `serve --immutable` 的数据库切换仍由 W2 决定。
