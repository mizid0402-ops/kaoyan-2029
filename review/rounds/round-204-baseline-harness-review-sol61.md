# 第 204 轮：技术债包 B 独立评审（sol61-main）

结论：**FAIL**。共享 harness、保留实例、四个契约模块的辅助收敛成立；
但退役时丢失了若干独立的当前行为断言，“已有等价”的去向表不能作为全部删除的依据。
这些问题违反 200 / 203 轮“(b) 不得随文件删除、同样输入与期望”的要求。
不要求恢复八个迁移对照文件，只需把缺失的当前行为断言迁到正规模块。

范围：`git diff f52b8f6 -- tests` 与用户列出的五个新增测试文件。
基线为 `f52b8f6f2a6145e86970844278acf197184597d9`；包 D 的 `ky/` 改动不纳入评审。
已读 AGENTS.md、两轮任务书与报告、技术债清单 P1 / §6 / §7 / §9。
只新增本报告，未修改实现或测试，未提交，未跑全量。

## 必须改

### M1：partial-skip 的候选保留与失败提示没有等价保护（MAJOR）

已删除 `test_cli_split_baseline.py::_compare_case` 对
`record-question-partial-skip` 的直接断言包括：候选组恰为一组、review_id 为
`record-review`、候选非空，以及同时含 `check_question_suggestions_skipped`。
文本场景还直接检查“出题查询失败”提示。输入是两条 fluent / unchecked 复习：
第一科有登记索引，第二科无索引，第二项查询失败。

203 报告指定的三个方法分别覆盖单项候选、完全缺注册表的跳过、单项文本候选。
它们没有“已经取得候选后下一项失败”的输入，也没有同时保留候选与 skip 原因的期望。

可复现输入及实测：系统临时探针 `round204_probe.py` 复用固定提交中的
`_record_case(..., 'record-question-partial-skip')` 构造输入，只调用当前 CLI。
把 `_day_plan_record_query_candidates` 的错误分支
`return candidates, str(exc)` 定点改为 `return [], str(exc)`，临时源码中执行：
未变异时退出 0、候选组为 1；变异时仍退出 0、候选组变成 0，skip 原因仍存在。
报告指定的三个现存方法在同一变异下均通过。为使进程内变异生效，探针仅将测试的
`run_ky` 转接到当前 `cli.main`，返回相同形状的 CompletedProcess；参数和直接断言未改。
这不是对真实子进程启动方式作等价证明，而是证明三条断言缺少该输入条件。

修法：将 JSON 的四项直接断言及对应文本提示断言迁入 `tests/test_cli.py`，
保留两项查询的同类输入，不再取旧 CLI。

### M2：record 写冻结失败与推进失败的状态契约被误当成存储层等价（MAJOR）

旧 `_compare_case` / `_run_cli` 有明确的 CLI 故障场景：

- `record-freeze-write-failure`：`_latch_freeze_if_needed` 抛 StorageError，退出 2，
  **不写完成事件**；
- `record-advance-failure`：`advance_review_queue` 抛 ContractError，退出 2，
  **完成事件已经写入**。

后一项尤其不能改成“所有 record 失败都不写事件”；旧测试保护了两种失败阶段的不同语义。
前者对应冻结审计写入失败，后者对应已保存完成事件之后的队列推进失败，属于日常故障恢复问题。

复现输入：固定提交 `_record_case` 的上述两个场景，以及旧 injector 中
`fault='freeze'` / `fault='advance'` 的函数替换。查看原 `_compare_case` 的
`expected_written` 集合和 `failed_cases` 集合，即可同时得到写入状态与退出码期望。

203 报告指向的 `test_gate_failure_on_the_temp_reread_publishes_nothing` 与
`test_freeze_gate_checks_the_final_plan_day_before_writing` 测的是 **写日计划** 的 gate；
`test_queue_and_completion_ids_stay_unchanged_if_write_fails` 只测队列存储失败，
不调用 CLI、不检查完成事件存储或 CLI 退出码。
在当前 `tests/` 搜索 `_latch_freeze_if_needed`、`forced freeze`、`forced advance`
均无命中。现存未知 review_id / legacy queue 的无写入测试也没有上述故障触发条件。

修法：在正规 CLI 模块补两种故障阶段的直接断言；按旧输入分别检查事件存在性、退出 2、
无 traceback。不要用计划 gate / 队列单元测试代替 CLI 提交顺序保护。

### M3：round24 / round29 的 CLI 结果未迁移；双错误测试也含直接期望（MAJOR）

旧成功场景不止检查 `validate()`：还执行 `main()` 并断言退出 0。
旧错误场景分别令第一节点 `status='approved'`、第一条 agreement
`source_support=0.42`，执行 `main()`，断言退出 1，stdout 含对应错误诊断。

报告引用的 round24 `test_wrong_weight_for_evidence_tag_is_rejected` 输入甚至是
`weight=0.42`，不是 status 错误；已有 `test_status_approved_is_rejected` 可以覆盖
validate 拒绝该状态，但仍没有 CLI 退出码和输出断言。
round29 引用的 `MainTableVerifyTreeTest::test_real_files_pass` **不存在**；
同名实际位于 `AgreementValidatorRealFileTest`，仅断言 agreement validate 的 errors 为空。
现存 MainTableVerifyTreeTest 跑的是另一个 `verify_tree.py`，不是 agreement 校验器 CLI。

可复现变异：仅在系统临时源码把 `round29_validate_agreement.main` 的错误分支
`return 1` 改为 `return 0`。固定提交中的原
`test_round29_source_support_error_matches_fixed_baseline` 未变异时通过，变异时
**AssertionError 失败**；203 报告指定的
`MutationTest::test_wrong_source_support_is_rejected_by_agreement_validator`
在同一变异下仍通过（其 validate 行为未变）。仓库搜索没有第二个测试调用该 CLI。
探针保留了原失败栈，排除了资源 skip、加载错误或变异未生效。

此外，`test_round24_dual_error_order_matches_fixed_baseline` 不能全部归成
“只比较两版顺序”：它直接指定 `errors[0]` 是 status 值域诊断、`errors[1]` 是
approved 禁用、`errors[2]` 是 sources 非空要求、`errors[3]` 是 source_count 诊断，
并直接检查 CLI 退出 1 与两条输出诊断。这些固定期望独立于旧新对照存在。
复现输入就是第一节点同时设 approved 与 `sources=[]`。

修法：迁移两校验器成功 / 错误 CLI 的直接期望，以及 round24 双错误的固定期望。
允许退役的是 old == new 部分，不是错误位置、固定码和诊断存在性这些 (b) 断言。

### M4：引用问题的六项完整聚合期望没有等价测试（MAJOR）

旧 `test_citation_results_match_fixed_baseline_in_rule_order` 明确检查当前
`new_report.problems` 的六项 **完整 reason 列表**，依次为 dangling、withdrawn、
unclear rights、forbid structuring、wrong digest、missing stored bytes。
这是当前结果的直接断言，不只是 `old_report.summary() == new_report.summary()`。

复现输入：从 `git show f52b8f6:tests/contract/test_storage_ledger_split_baseline.py`
取该方法，按其 cases 构造六个知识点和五份台账材料，在空临时 root 下 strict=True。
完整 expected reason 列表就在方法末尾；无需执行旧版即可断言。

报告指定的现存测试分别只检查单个问题的部分 reason 子串；
`test_report_lists_every_problem_not_just_the_first` 只有两条 dangling 输入，
只检查问题数与 checked_points。它不检查六种混合问题的完整 reason 或列表次序。
`test_strict_mode_detects_changed_bytes` 确实另有 strict 字节损坏保护，但同样不代替六项聚合。

修法：将这组输入与当前六项完整 reason 列表迁到 `tests/test_citation_gate.py`，
去掉旧模块加载和 summary 对照即可。

### M5：restore 去向表漏记八行状态期望，至少存储权限拒绝已失去保护（MAJOR）

旧 `test_restore_material_rows_match_fixed_baseline` 不止守 check-only 无网络 / 临时目录，
还直接断言八行结果状态为：already_verified、existing_mismatch、invalid_url、
storage_not_permitted、missing_url、invalid_path、reference_only、needs_download。
这组状态期望没有出现在 203 报告去向表中。

复现输入：原方法 `_restore_raw('no-store', 'raw/no-store.txt', b'no', may_store=False)`，
调用当前 `restore_materials(..., check_only=True)`，期望 storage_not_permitted。
该权限拒绝是正常台账权限语义，不是恶意攻击场景。
当前 `tests/` 搜索 storage_not_permitted 没有命中；material_restore 端口已有远程参考、
missing_url、坏 URL 等保护，但没有 local-file / may_store=False 的对应状态期望。
报告所指 `test_check_is_read_only_and_never_calls_network` 只有一行 missing 输入，
仅断言 needs_download 与 raw_root 不存在，不能覆盖八行矩阵。

修法：把原多行 check-only 输入的当前状态断言迁到 material_restore 正规模块；
无网络和无临时目录的现存测试可以复用，不再运行旧版。
本条不把 invalid_path 的攻击防护扩大成新的安全返工要求。

## 建议改

### m1：迁入方法仍宣称 fixed baseline / fixed CLI（MINOR）

`tests/contract/test_index_tree_verifiers.py` 两方法仍名为
`test_registered_index_variants_match_fixed_baseline` 和
`test_registered_trees_and_variants_match_fixed_cli`，实际仅运行当前实现。
复现：打开这两个方法，没有 fixed_source / git show / old-run / 新旧比较。
建议改为说明当前输入变体、错误码与诊断验证的名字，避免读者误以为仍在守旧版。
模块头已经写明 Current behavior，因此本项是非阻断的可读性改进。

## 不改与去向抽查

以下逐项打开原断言及去向方法；“部分等价”不视为满足退役要求。

| 抽查项 / 原行为 | 指定或实际去向及核验 | 判断 |
|---|---|---|
| record 未知 review_id，退出 2、不写事件 / 队列 | `DayPlanCliTest.test_record_with_review_store_and_unknown_review_id_exits_2_and_writes_nothing`：不存在的 ID，事件树为空、队列原字节不变 | 等价 |
| legacy reviewed queue 拒绝，不写事件 | `test_record_on_legacy_reviewed_queue_exits_2_and_writes_nothing`：schema 1 已复习项，退出 2、无 traceback、事件树空 | 等价 |
| record 正常写入、重复日期拒绝 | `test_record_completion_event_and_duplicate_day_is_rejected`：先成功再重复，检查记录 | 等价 |
| record freeze 写失败无事件 / advance 失败已有事件 | 报告三项存储层测试没有 CLI 故障条件或完成事件断言 | 不等价，M2 |
| submit 冻结时不写计划 | `FreezePortContractTests.test_submit_is_rejected_while_record_remains_allowed`：human / staging 两入口退出 2，无 day-plan manifest | 有直接保护 |
| submit 超容量不写计划 | `DayPlanCliTest.test_violating_plan_exits_2_and_writes_nothing`：60 容量 / 100 分配，整个 store 文件树不变 | 有直接保护 |
| fluent JSON / 文本单项候选 | `test_lenient_fluent_json_contains_question_candidates` / `test_lenient_fluent_unchecked_record_lists_index_candidate`：当前索引 ID 和候选展示 | 单项等价 |
| 第二项查询失败，保留第一组并打印原因 | 三个指定方法分别测单项或全跳过 | 不等价，M1 |
| resume 早于尚未解除的 freeze，不写 resume 事件 | `test_resume_dated_before_an_unresolved_freeze_is_rejected`：检查拒绝与 resume 事件缺失 | 等价 |
| restore --check 只读、不联网、不建下载临时目录 | `test_check_is_read_only_and_never_calls_network`：open_url 调用即失败，TemporaryDirectory 被置为抛错，raw_root 不存在 | 等价（但不包含状态矩阵，M5） |
| 讲解正文六个标题、题表、excerpt slot、覆盖小节和 no-hit 提示 | `Cs408LecturePipelineTest.test_outputs_match_pre_migration_templates_with_only_allowed_changes`：固定 762786f 文件对照，正文 / coverage 未被允许归一化抹除 | 保护保留，实跑通过 |
| round24 成功 / approved 错误 | 结构测试只检查 validate；报告错误项指向 weight 输入 | CLI 不等价，M3 |
| round24 多错误的固定索引期望 | 被误报为只有两版顺序一致 | 未迁，M3 |
| round29 成功 / source_support 错误 | 真正同名 real-files 方法只检查 validate；引用类写错；mutation 同样只调用 validate | CLI 不等价，M3 |
| workspace unknown-root / unknown-reference / unknown-index-subject 的 ContractError 与路径 | `WorkspaceContractTests.test_3_structure_rejections_report_contract_paths`：同类单字段错误，assertRaises(ContractError) 且 exception.path 精确相等；另有路径拒绝测试 | 有直接保护 |
| citation 单项拒绝和批量完整报告 | 单项子串等价；两条 dangling 计数不能代替六种完整混合 reason 列表 | 部分等价，M4 |
| HTML 临时产物提取成功 / 注册产物 verifier 成功 | `tests.test_question_extraction` 两方法直接加载当前工具，检查文件、索引非空、stderr 空 / verifier 退出 0 | 实际运行，无 skip |
| index/tree 变体当前诊断及 CLI 码 | `tests.contract.test_index_tree_verifiers`：当前 verify 捕获与当前 verify_tree 子进程，未加载旧版 | 实际运行，无 skip；建议改名字 |

八个删除文件均从固定提交取回查看，并未仅依据报告判断。明确纯 old/new 比较的
review selection、monthly close、invariants、snapshot overrides、shard commit、
day-plan-write、completion parser 的 `_call_bytes(old)==_call_bytes(new)` 等部分可按裁定退役。
models / workspace 的旧函数长度与变体数量也是脚手架，不要求迁移。
但 tools、CLI、storage/ledger 中上列 (b) 断言确实独立于旧版，不能随脚手架消失。

### Harness 与固定依赖

`fixed_source` 先限制 7–40 位十六进制字符串，拒绝 HEAD / 分支名，再验证 commit 并读取源码，
调用 identity；对照 ProcessResult 与文件树使用原始 bytes，没有归一化。
保留实例旧源码身份条件是包含 `subject_items =` 且没有
`count_review_items_by_subject`，基线固定 b867ae7，实测有效。

`test_baseline_harness` 的变异证明确实同时执行固定 f52b8f6 中的改写前测试、当前改写后测试，
在 patch 生效后再 exec 测试源码，使两侧导入同一个变异 build_snapshot。
先分别证明未变异通过，再对 queue count / due_today count 两处各证明失败。
本轮自测 5 项通过；另做独立 queue count +1，保留实例产生 AssertionError，
没有 error / skip。不是靠历史测试不存在、语法错误或资源缺失“变红”。

从 f52b8f6 读取原测试的依赖在本机可用，提交后也不会转成新版；§9 已决定不改写历史，
其他保留契约本来也依赖固定 Git 对象，所以此依赖符合当前项目策略，不要求换 HEAD 或复制兼容版本。
自测中解析 HEAD 仅用于负面的 identity=False 检查，不是业务基线比较。

### 四处辅助收敛

独立 AST 对比各 `test_*` 方法，仅将旧 `_LegacyConfigView` 名称统一为公开名，
结果逐方法完全相同：availability 12、day-budget 12、freeze 13、planner 28，共 65。
逐文件 diff 确认只有增加 import、删除重复配置视图 / Git 读取体、调用公开名和 helper 转发。
四份 as_dataclass 的旧字段形状与断言保留；day-budget 原来仅有 as_dataclass，
合并后增加的 __getattr__ 没有引入新调用。planner 引用 LegacyConfigView，
另三份同时引用 git_source，无 `_LegacyConfigView` 兼容别名。
移走的 helper 内部断言在共享版本保留，不算业务测试断言被删。

## 独立验证及复现文件

只运行直接相关的单模块 / 单方法，未重复实现者的验收集合：

| 命令（前缀 `py -3.12 -B -m unittest`） | 实测 |
|---|---|
| `tests.test_baseline_harness` | 5 tests，0.655s，OK |
| `tests.contract.test_index_tree_verifiers` | 2 tests，20.757s，OK，无 skip |
| `tests.test_question_extraction` | 2 tests，2.638s，OK，无 skip |
| `tests.test_cs408_lecture_pipeline.Cs408LecturePipelineTest.test_outputs_match_pre_migration_templates_with_only_allowed_changes` | 1 test，1.808s，OK |

系统临时探针复现命令：

```powershell
$env:PYTHONIOENCODING='utf-8'
py -3.12 -B $env:TEMP\round204_probe.py
```

最后一次成功输出与变异文件所在目录：
`C:\Users\Lenovo\AppData\Local\Temp\round204-sol61-_28gsqtj`。
包含快照 AssertionError、round29 原测试 AssertionError、变异源码、两条 partial-skip 临时输入树。
探针另用现存 lecture pipeline 的临时 fixture 生成产物，逐项验证原六个讲解标题、题表、
全部 coverage 标题和 deck / coverage 两处 no-hit 提示实际存在。
讲解文件对照只允许既有视图 / 行尾变化；其删除练习标题的内置检查也实际执行通过。

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。不把“当前相关测试都通过”
等同于“删除后的保护等价”；M3 的变异明确展示了两者可以同时成立。

## 安全登记

本轮未发现需新增登记的安全缺陷。没有扩展已有恶意路径 / 并发攻击防护范围；
必须改项针对日常输出、错误码、正常失败阶段的存储顺序及明确禁止删除的行为断言。
