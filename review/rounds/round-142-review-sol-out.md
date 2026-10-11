# WP-F-b 实现评审与 WP-F-c 细则审查（第 142 轮）

基线：在独立临时目录解包 `git archive b867ae7`，补入原始资料和空 `products`；固定版本对照通过 `GIT_DIR` 访问主仓库对象库。只在归档中运行探针，主仓库只写本报告。严重度按单用户本机正常使用判断。

## 一、WP-F-b 实现评审

### 必须改

**B1｜五命令契约测试未证明 `record` 与 `resume` 写后的队列事实已进入投影。** `tests/contract/test_learning_state_projection.py:203` 在 `day-plan record --review-store` 后只断言 `review_items` 非空；该行在命令前已经存在。`227-228` 在 `ky resume` 后查了投影的恢复事件，却只从源队列 `queue.load()` 核对重排后的到期日。第 132 轮最终规则第 6 条及 F-b 任务书要求这两条命令各自的**两侧写入事实**都在重建后从投影读到；现有断言少了一侧。

可复现的反例：仅在临时归档把 `ky/projection/learning_state.py:91` 的 `_date(item.due_date)` 改为常量 `"1900-01-01"`，设置 `$env:GIT_DIR='F:\workspace\kaoyan-ai-system\.git'`，运行 `py -3.12 -m unittest tests.contract.test_learning_state_projection.LearningStateProjectionTests.test_real_cli_writes_are_visible_after_rebuild`，结果仍为 `Ran 1 test ... OK`。这证明投影的队列到期日即使被错误写入，当前验收也不会发现；探针后已撤销改动，归档文件的 Git 哈希恢复为 `bdafffc047315076289538538ffd16317c8aa806`。修法：`record` 后按 `review_id` 查询投影队列的状态、到期日、上次复习日等已推进字段，与写后的队列对象核对并证明较写前变化；`resume` 后同样从投影核对重排结果及恢复事件。当前实现未观察到这项实际写错；阻断理由是明确要求的契约验收尚未成立。

### 建议改

无另外的实现建议。上述断言属于任务书已列的验收，不另扩测试范围。

### 不改：已核对且符合本轮范围

- `ky/projection/learning_state.py` 的 `review_items` 覆盖 `ReviewItem` 的公开事实，包括版本、标题、粒度、反馈和全部 `schedule` 字段；计划保存当前版本的全部标量与科目分钟，完成复习按事件日及顺序保存，词汇投放与练习分开，路线只投当前版本。完成事件的计数是子项事实的汇总；计划的 `backlog_minutes` 是原计划字段，并未充当查询日积压。未发现“今日到期”“当前积压”“当日冻结”一类随日期变化的持久列，也未发现处方语义的表或列名。
- `read_learning_state` 只调用 F-a 的四个公开来源端口；`state_inputs` 采用 `state.<key>/<相对存储根路径>`，availability 以文件名相对其父目录。值直接取端口返回的同次解析摘要，M15 没有再打开状态文件。队列缺 manifest、未登记路线、未登记 availability 按空状态处理；已登记 availability 缺失、无效状态源按契约错误处理。此处沿用第 141 轮已复审的 F-a 端口行为。
- 状态与参考输入在替换输出前读完并校验；临时 SQLite 写入成功后才 `os.replace`。定点破坏队列分片摘要后，构建抛 `ContractError`，旧投影原始字节不变。两次相同输入构建的所有表与 meta 相同，`state_inputs` 每个值与对应文件的 SHA-256 相同，旧计划/路线版本未混入。固定 `b97f3ac` 的 schema 2 构建器对照通过：相同参考输入下参考表逐行相同，旧 meta 除版本值外不变，新 meta 只增加两键。
- 五个命令测试均实际调用 CLI 写入分支，退出码为 0 后各自重建并查询；`submit`、`route submit`、`migrate --apply` 查到了对应新事实，`record` 查到了完成事件及词汇记录，`resume` 查到了恢复事件。B1 仅针对两处**投影队列结果断言**。规格明确 `freeze_events_latched` 只代表当前事件锁存，不代表查询日冻结；运行中的 `serve --immutable` 不会自动刷新，W2 仍需解决连接刷新。

验证：`py -3.12 -m unittest tests.contract.test_learning_state_projection tests.test_projection_service tests.contract.test_state_sources_port`，`Ran 22 tests in 5.986s, OK`。另做上述单条变异探针，变异测试仍通过。全量未跑，按 `AGENTS.md` 由决策者提交前统一运行。实现者报告的约 800 天重建 `3.554 s` 是其测量，本轮未复测，不能把它表述为我的独立测量。

### 安全登记

本轮未发现新增的恶意注入或竞态类问题。第 141 轮已并入 `docs/安全风险登记.md` 的 S8 不在本轮重复登记；B1 是正常验收缺口，不归为安全问题。

**F-b 结论：FAIL。** 实现路径未发现现行数据错误，但 B1 使任务书规定的“写入 → 重建 → 从投影读到队列变更”缺少有效契约证明；补强这两处断言后可限域复审。

## 二、WP-F-c 细则审查（只审规则）

| 条款 | 结论 | 依据与改法 |
|---|---|---|
| C1 | **修改** | 提取 M12 公共纯计数函数是对的，过滤口径保持原样：`due_today` 仅 `queued` 且 `due_date == day`，积压仅 `< day`，在队列中为 `queued` 或 `scheduled`。函数应明定对无队列项科目的零计数；`build_snapshot` 仍按 `config.subjects` 的原顺序输出，包括零项科目，不能因改用字典而丢行或改顺序。以固定 `b867ae7` 读取旧 M12 实现，在同一组输入上逐字节比较快照 JSON；不要用浮动 `HEAD`。 |
| C2 | **修改** | schema 3 的 `review_items` 已保存重建 `ReviewItem` 所需的全部字段，日期为 ISO 文本，SQLite `REAL` 可还原浮点；但 `validate_review_item` 接受的是嵌套 `schedule`，输入键为 `self_rating`，而投影列是扁平 `schedule_*`、`last_self_rating`。须逐列组装其公开输入映射并经唯一校验器验证，不能直接传 `dict(sqlite3.Row)`。冻结所需队列、事件、配置与策略齐全；事件按序重建 `FreezeEvent` 并交 M27 `latch_active`、`assess_freeze`。`freeze_to_mapping` 只含冻结时的数值和 `resume`，**没有 `frozen` 布尔值**，且文档称其为“冻结时”载荷；统一 JSON 形状须显式给出 `frozen`，非冻结时不得无条件给出 `resume` 操作提示。日计划须连同科目分钟返回，路线阶段须连同各科复习分钟返回，阶段边界用 `start <= day < end_exclusive`。最关键的是定义 `as_of`：它只能表示“用投影里的**最新队列和当前事件锁存**按日期 D 计算”，不能声称还原 D 当时的历史状态。反例：9 月 1 日冻结、9 月 5 日恢复后查询 9 月 3 日，全部事件的 `latch_active` 已为假；而投影也没有 9 月 3 日的旧队列快照。 |
| C3 | **修改** | 调用方给配置可以，但必须复用 `validate_items_against_config`，它会拒绝队列中未知或已停用的科目；不要只核对名称存在。把“不一致”限定为参与 M12/M27 当前队列计算的科目，避免把旧日计划中后来停用的科目当错误而使历史事实无法展示。冻结阈值按**本次传入配置**计算，配置改变后对同一投影的查询可变，JSON/文档应明示这个基准；只读投影无法证明配置与构建时是同一版本。 |
| C4 | **修改** | `ky.projection` 当前无子命令，原命令 `py -3.12 -m ky.projection [--workspace ...] [--out ...] [--json]` 就是重建；新增 `status` 需保持该旧入口及输出兼容。当前归档 `kaoyan.workspace.yaml:58` 是 `settings: {}`，`settings.exam_config` 为可选项，因此仅从注册表取配置的拟定命令在当前工作区无法日常使用。提供 `--config PATH` 显式覆盖，未登记且未提供时给带路径的契约错误及设置方法；或在同一工作包先登记有效默认配置。投影文件不存在或 schema 不符提示重建，但不可暗示重建后运行中的 `serve --immutable` 已更新。 |
| C5 | **同意** | 只接受 schema 3；先以 SQLite 只读方式打开并核对 `projection_meta.projection_schema_version`，缺文件、缺表、无效版本均转为可操作的契约错误，不创建空库。schema 2 提示重建即可。 |
| C6 | **修改** | 保留不写入、不自动重建、不改 `serve` 的边界，同时明确 `status` 读取的是**最近一次成功重建的快照**。正常反例：`day-plan record` 成功后直接运行 `status`，未重建便会读到旧队列和旧完成事件。CLI/JSON 文案不得称“实时”或“已反映刚才写入”；W2 要在写入后成功重建、重新打开只读连接并核对结果，失败时显示投影未更新。F-c 不必为了识别陈旧而重新读取状态文件。 |

### 建议给实现者的最终规则

1. M12 公开一个只按 `ReviewItem` 与日期计算的纯计数端口；快照调用同一端口，保留原有科目次序和零值行。用固定 `b867ae7` 对照旧快照输出，并在相同队列与日期下比较 M12、M15 的四项计数；覆盖昨日、今日、明日及 `scheduled`、当天到期、逾期边界。
2. M15 `status_as_of` 只读 schema 3 SQLite；按表的完整列映射还原并验证队列，复用 M12 计数及 M27 冻结规则。唯一 JSON 形状包含计算日期、各科计数、带 `frozen` 布尔值的冻结状态、该日当前计划及科目分钟、完成事件存在性、手填分钟、所在路线阶段及各科分钟；缺项用约定的 `null`/`false`，不得由界面另算口径或加入学习建议。事件锁存反映投影当前事件序列；`as_of` 是按 D 评估最新投影事实，**不是历史回放**。
3. 配置和策略由调用方传入，队列与当前配置的科目关系用公开校验器检查；配置决定本次冻结阈值。CLI 优先使用显式 `--config`，否则使用注册表 `settings.exam_config`；两者均无则契约错误。保留旧重建 CLI 的调用和输出，`status --date` 只读注册表所指投影，缺失/旧版报可操作错误。
4. F-c 不写状态、不自动重建、不更改 `serve`；明确结果仅为最近成功构建的投影。契约测试在同一份队列、配置、日期上比较 M12/M15 的计数和 M27 冻结结果，并验证当前锁存与查询日期含义；W2 负责写后重建、连接刷新和失败提示。全量仍由决策者统一运行。
