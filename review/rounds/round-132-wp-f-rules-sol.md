# 细则审查（只审规则，不审实现）：WP-F 学习状态投影（M15 schema 3）

遵守 `AGENTS.md`（"决策者细则先审再实现"；不跑全量；严重度按威胁模型）。本轮**没有实现**，请只审下面的规则：
与阶段决议是否一致、会不会让日常使用出错（数据算错、读到旧状态、构建失败无法恢复）、边界与反例。可在 `git archive fa9e11c` 上做只读探针。
注意：另有两个实现者在主仓库做 `tools/` 分层与 `ky/workspace.py` 拆分，请只在你自己的临时归档里运行。

## 背景

`docs/阶段2.5-接缝收口.md`：M15 投影只有参考数据（树、索引、权重），**没有学习状态**；前端"保存后即时反映"没有读模型（WP-F：队列 / 日计划 / 完成事件进投影，"写入 → 重建 → 可读到"契约）。
`docs/前端设计-范围与待定.md` 已定：文件是真相源；应用只写文件、再重建投影；投影保持只读（`--immutable`）。
现行规格 `contracts/projection.md`（schema 2）、`contracts/state_snapshot.md`（M12，"不推荐"约束）、`contracts/freeze.md`、`contracts/route_plan.md`、`contracts/availability.md`、`contracts/review_progress.md`。

## 决策者拟定的规则（请审）

F1. **同一个投影文件、同一条重建命令**（`py -3.12 -m ky.projection`），`projection_schema_version` 升为 3；学习状态表另写一份规格 `contracts/learning_state_projection.md`，实现放在 `ky/projection/` 下单独的文件（M15 的一块，模块地图登记）。参考数据各表与 schema 2 **逐列逐行不变**。
F2. **输入只来自注册表 `state.*`**（`state.review_queue`、`state.plans`、`state.routes`、`state.availability`），且**只经各自的公开端口读取**：`ReviewShardStore.load`、`DayPlanStore` 的公开读取方法、`RoutePlanStore.current`、`availability_for_workspace`、`DayPlanStore.freeze_events`。不直接 `yaml.safe_load` 状态文件、不 import 别的模块的私有名。
   现有 `DayPlanStore` 只能按月读；需要"列出所有已存月份 / 日期"时，在 M13 增加一个公开只读方法（本包内一并做，写进 M13 的规格说明），而不是投影自己遍历目录。
F3. **拟定的表**（列名以各端口的公开数据类字段为准，不另造语义）：
   - `review_items`：队列每项一行（`review_id` 主键；科目、知识点、状态、预计分钟、引入日、到期日、上次复习日、间隔 / 重复次数 / ease / lapses 等 `schedule` 字段、延期次数、上次质量、上次自评）。
   - `day_plans`：每天的**当前版本**一行（日期、版本号、可用分钟、来源 / actor、`input_hash`）＋ `day_plan_entries`（该版本的各条安排）。
   - `completion_events` ＋ `completion_reviews`（每条复习完成：`review_id`、核对方式、结果、`completion_id`）＋ `completion_vocab_words`。
   - `freeze_events`（序号、类型、日期）；`route_phases`（当前路线版本的各阶段与各科每日复习分钟）；`availability_days`（手填的逐日分钟）。
   - `projection_meta` 增加 `state_inputs`：本次读到的每个状态文件（相对路径 → SHA-256），与参考数据的 `inputs` 分开。
F4. **不存"今天"**：投影没有构建时间戳（schema 2 的确定性要求），所以"今日到期 / 积压分钟 / 是否冻结"这类随日期变化的量**不写进表**；前端按查询日期用 SQL 或调用 M12 快照计算。
   唯一例外是否要有：`freeze_latched`（锁存与日期无关，只看事件序列）——拟由 M27 公开函数 `latch_active` 计算后写入 `projection_meta`，投影不重写锁存规则。
F5. **缺失策略**：`state.*` 某键未登记 → 对应表为空；已登记但目录 / 文件尚不存在 → 与各存储的"空存储"行为一致，表为空；已登记且内容不合契约 → `ContractError`，**旧投影逐字节不变**（沿用 schema 2 的"先校验、临时库、原子替换"）。
F6. **"写入 → 重建 → 可读到"契约**：对每个写状态的命令（`day-plan submit / record`、`route submit`、`ky resume`、`review-queue migrate`），契约测试走"写 → `build_projection` → 查表能读到这次写入"。
   本包**不做**写命令后自动重建（前端 W2 未定，归 ⑥ 前端）。
F7. **不推荐约束**沿用：表 / 列 / 视图名不得出现建议、推荐、优先、下一步之类的处方语义；只描述已记录的事实。
F8. 重建仍幂等：同样的输入字节两次构建，表内容与 meta 完全相同。

## 请重点查

1. F3 的表是否够前端 §7.1 的"展示日计划、复习队列、学习进度"用，又没有多出投影不该承担的东西；`day_plans` 只放当前版本是否够（历史版本是否要进投影）。
2. F4 不存日期相关量是否会让前端算错（例如前端各处自行实现"积压"口径而与 M12 / M27 不一致）；是否应该提供一个带日期参数的公共查询（放在哪个模块）而不是让前端写 SQL。
3. F2 的"只经公开端口读"在数据增长后（两年约 800 天的计划 / 事件文件）重建时间是否可接受；若不可接受，给出不破坏"文件是真相源"的替代。
4. F5 与各存储现有空状态行为是否一致（例如 manifest 缺失的队列、未登记 `state.routes`）；"内容不合契约 → 整个投影构建失败"对日常使用是否过严（一个坏文件让参考数据页面也看不到）。
5. F1 把学习状态并入同一个文件与同一 schema 版本号，对现有依赖 schema 2 的测试 / 工具 / `serve` 的影响。

产物：`review/rounds/round-132-wp-f-rules-sol-out.md`：逐条"同意 / 修改（给出改法）/ 反对（理由与反例）"，最后给出你建议的最终规则。只写这一个文件。
