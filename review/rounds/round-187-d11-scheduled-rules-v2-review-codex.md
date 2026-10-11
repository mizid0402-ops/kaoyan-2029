# 第 187 轮：D11 过期 `scheduled` 计入积压——细则 v2 复审

只审规则，不审实现。依据当前工作区的 `AGENTS.md`、第 186 轮报告、D11 决议、相关规格和调用链静态核对；未运行测试或全量验证。以下“现行”指本轮读到的代码，不表示 v2 已实现。

## 必须改

无。第 186 轮 M1–M3 的阻断理由已被 v2 吸收，未发现新的日常使用阻断点。

## 建议改

1. **R9 区分预览与已执行的措辞。** `--dry-run` 只计算计划，不写队列或恢复事件（`ky/__main__.py:552-575`）；同一句“其中 N 项由 scheduled 转为 queued”在预览中容易被理解为已经改写。建议预览打印“其中 N 项将由 scheduled 转为 queued”，正式执行打印“其中 N 项已由 scheduled 转为 queued”。现有“重排预览”标题提供了上下文，因此这不是阻断项。JSON 如增加可选字段，应在 `contracts/freeze.md` 固定字段名和含义，并说明它表示本次计划的转换数；该映射也会写入恢复事件，不宜只规定 CLI 输出。
2. **R7 指明校验对象是本次冻结判定读取的注册队列。** `record --review-store` 可以显式指向另一存储，而冻结锁存读取 `state.review_queue`（`ky/__main__.py:157-178,1141-1157`）。实现规则宜写成：在同一份已加载的注册队列上筛出过期 `scheduled` 并校验，且在追加冻结事件前完成；无可用工作区时维持既有不检查锁存的路径。不要仅校验 `--review-store`，也不要为校验另读一次同一队列。`resume` 现有全队列校验比新增候选校验更严格，应保留，不能为满足 R7 而缩窄。
3. **R4 补齐旧文字的口径说明。** `ky/__main__.py:465` 的 `unreachable` 注释目前说它“不属于 backlog”，采纳 R4 后已不准确；`ky/__main__.py:244-245` 的 `--freeze-backlog-days` 帮助仍写 `queued overdue`。规格及文案应区分“当前队列逾期积压”与 M9 “本次裁剪延期”。R4 限于冻结且含过期 `scheduled` 时增印解释行，能消除“冻结积压 216 / 本次延期 0”的主要误读，并满足 R5；建议该行直接写明第二个数只计本次延期。`contracts/review_clip.md:119-125` 的五桶与 `ClipResult.backlog_minutes` 定义无需改。
4. **R5 把“无过期项”绑定到被比较的日期 D。** 例如一条 `scheduled` 的到期日为 D+1，按 D 查询属于旧路径；按 D+2 查询则应得到新积压。固定哈希对照应在相同日期、配置、事件与输入下进行，且只对该 D 没有过期 `scheduled` 的结果要求逐字节一致。

## 不改

1. **M1 已吸收。** R4 让 M12 `count_review_items_by_subject(items, day)` 的 `backlog_minutes` 与 M27 共用 R1 逾期口径；M15 `status_as_of` 在 `ky/projection/status.py:222,302` 分别复用 M12 计数和 M27 冻结判定，故同一投影队列、配置和日期下数值应一致。`due_today` 保持只数当天到期的 `queued`。M9 `ClipResult.backlog_minutes` 只累计 `deferred`（`ky/schedule/review_clip.py:501`），不应改成当前队列总积压；`monthly_close` 只累加日计划声明的积压（`ky/schedule/monthly_close.py:139-141`）。这些是不同会计量，v2 已说明。例：27 条各 8 分钟、D−1 到期的 `scheduled` 在 216 分钟阈值下应使 M27/M12/M15 均报 216，而 M9 延期仍为 0，新增文本解释 27 项、216 分钟的来源。
2. **M2 已吸收。** R3 保持 `revision`，只对实际重排的过期 `scheduled` 转成 `queued`；逾期天数等于当前 `interval_days` 时保留进度，大于时调用 M10 重学起点。R6 明确约束 `schedule.interval_days` 不增，允许旧过期日移到 D 或以后；不会再把日历到期日变晚误称违反方向约束。转 `queued` 使新到期日可由 M9 选择；不转也并非当天立即再冻结，真正风险是新到期日仍 `unreachable`。M25 迁移后的实际状态按 R1 判断，`retired`/`suspended` 不纳入。
3. **M3 已吸收，但三个入口的现状不同。** `ky resume` 在 `_resume_context` 加载队列后立即调用 `validate_items_against_config`，早于规划及队列/事件写入（`ky/__main__.py:499-525,568-575`）；此入口现有检查覆盖全队列，包括停用或配置外科目，实施 R7 只需证明它仍在写前拒绝，不应移除。`day-plan record` 的 `_day_plan_record_preflight` 仅核对完成记录引用和重复 ID，且无复习完成时直接跳过；随后 `_latch_freeze_if_needed` 可写冻结事件（`ky/__main__.py:1154-1156,1208-1225,168-178`）。`day-plan submit` 通过 `DayPlanStore.freeze_gate` 调用同一锁存函数（`ky/__main__.py:1091-1097`、`ky/storage/day_plan_store.py:850-855`）；直接 `--plan` 路径没有注册队列科目校验。`--from-staging` 的提案要求有效 `input_hash`（`ky/planner/port.py:221-224`），会经 `planner_input_data`、M9 在写计划前校验队列（`ky/planner/port.py:304-315,43-62`）；此路径已有检查，实施时用测试确认即可。因此 record 与直接 submit 的冻结写入边界仍需要 R7 的条件校验。当前 `_day_plan_record_freeze` 只捕获 `StorageError`，实现时还须把校验器的 `ContractError` 转成 R7 要求的退出 2，不能留下 traceback。`retired`/`suspended` 不成为新增逾期候选；不能以此改变 `resume` 既有的全队列校验。
4. **M15 名称核实。** 公开端口为 `ky.projection.status.status_as_of(projection_path, day, config, policy=FreezePolicy())`，JSON 端口为 `status_to_mapping`；规格确为 `contracts/projection_status.md:1-5`。当前投影规格标明 schema 4，规则不应沿用早期 schema 3 字面量。按日期查询评估的是最近一次成功重建的投影事实，不能称为写后实时状态。
5. **其余 `queued` 条件无需一概替换。** `ky/models.py:672` 的 `is_due`、M9 `scheduled_ahead/unreachable` 和候选选择、`ky/freeze/resume.py:134` 的未来容量占用均服务于“可选/已占容量”，不是“逾期积压”统计；保持原义。`ky/planner/port.py:50-51` 调用 M27 与 M12，随两端口自动取得新口径；`ky/projection/learning_state.py` 存原始事实，`status.py` 复用 M12/M27，无独立 `queued && due < D` 计数。检索到的独立旧积压判断是 `ky/freeze/port.py:70` 与 `ky/schedule/state_snapshot.py:108`，正是 R1/R4 的修改目标。`ky/schedule/monthly_close.py` 与日计划存量字段维持声明量。R8 如实说明低于阈值仍 `unreachable`、可手动 `resume`，不承诺自动修复。

## 实现包应定点验证的边界

- D−1、D、D+1 的 `scheduled`，混合 `queued`、`retired`、`suspended`；阈值等号、空积压零上限、锁存后队列积压已清空；M12/M15/M27 同日期同输入的分钟数与 M9 桶/延期数分别核对。
- 遗忘分界 `overdue_days == interval_days` 与 `+1`，包括进度已满、迁移后仍为 `scheduled` 的项；`resume` 实写及 `--dry-run` 的队列、事件、状态、`revision`、间隔与提示。
- 配置外和停用科目的过期 `scheduled`：分别走 `record`（有/无复习完成、显式 `--review-store`）、`submit --plan`/`--from-staging`、`resume`，核对退出 2、具体修正提示以及任何冻结事件、计划、完成记录、队列写入均未发生；`resume` 既有全队列校验仍在。
- 固定旧提交哈希对照无过期 `scheduled` 的同日输入，分别比较 preflight 文本/JSON、record、submit、resume、快照和投影状态；新增条件下只放行规则明确要求的差异。只跑直接相关模块或单条命令。

## 安全登记

未发现新的恶意输入、链接或竞态类问题。上述校验顺序针对合法队列加配置变化后的日常写入，不属于安全登记范围。

## 结论

**PASS（细则可下发实现）。** R1–R8 已解决第 186 轮 M1–M3；R9 的预览措辞和 R7 的校验对象建议在任务书中写清，不改变规则方向。
