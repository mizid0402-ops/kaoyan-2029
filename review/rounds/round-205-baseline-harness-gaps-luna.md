# 第 205 轮：baseline harness 退役缺口修复

结果：完成。本轮仅修改测试与本报告；没有修改 `ky/`、`tools/`，没有恢复已删除的八个对照文件，也没有提交。

## M1–M5 与 m1 迁移

| 项 | 固定提交中的输入与期望来源 | 当前直接断言 | 变异证明 |
|---|---|---|---|
| M1 JSON partial-skip | `git show f52b8f6:tests/test_cli_split_baseline.py` 的 `_record_partial_skip_args` / `_compare_case`：两条 fluent、unchecked 复习；第一科有登记索引，第二科没有；期望退出 0，候选组恰一组，ID 为 `record-review`，候选非空，JSON 含 `check_question_suggestions_skipped`。 | `tests.test_cli.DayPlanCliTest.test_record_partial_question_lookup_failure_keeps_earlier_candidate` 对当前 CLI 直接运行上述两项查询输入并逐项断言。 | 将当前查询异常分支定点改成丢弃已积累候选；该测试 AssertionError，明确失败在候选组数期望。 |
| M1 文本提示 | 同一固定提交中的 `record-question-partial-skip-text` 输入，期望 stdout 某行以“出题查询失败”开头。 | `tests.test_cli.DayPlanCliTest.test_record_partial_question_lookup_failure_prints_text_hint`。 | 将查询异常结果定点改成不返回 skip 原因；该测试 AssertionError，提示行缺失。 |
| M2 freeze 写入失败 | 固定提交 `_record_case(..., "record-freeze-write-failure")` 与 `_run_cli` injector：冻结函数抛 `StorageError("forced freeze write error", "freeze")`；期望退出 2、无完成事件。 | `tests.test_cli.DayPlanCliTest.test_record_freeze_write_failure_does_not_write_completion_event` 使用子进程 injector 替换 `_latch_freeze_if_needed`，检查退出码、事件文件树、无 traceback。 | 在冻结失败场景额外写入完成事件；测试因发现事件而失败。 |
| M2 queue advance 失败 | 固定提交 `_record_case(..., "record-advance-failure")` 与 injector：`advance_review_queue` 抛 `ContractError("forced advance failure", "queue")`；期望退出 2、完成事件已写入。 | `tests.test_cli.DayPlanCliTest.test_record_advance_failure_keeps_written_completion_event` 检查退出码、恰有一份事件、无 traceback。 | 在推进失败场景删掉已写事件；测试因事件数不符而失败。 |
| M3 round24 成功 / status 错误 | 固定提交 `tests/test_tools_split_baseline.py` 的 `test_round24_success_matches_fixed_baseline` 与 `test_round24_status_error_matches_fixed_baseline`：正常注册树 `main()` 退出 0；将第一节点改为 `status="approved"` 后退出 1，stdout 含 `status=approved is forbidden`。 | `tests.test_round24_weighted_tree.WeightedTreeStructureTest.test_validator_cli_succeeds_on_registered_weighted_tree` 与 `test_validator_cli_rejects_approved_status`。 | 让错误树的 validator 返回无错误；status CLI 测试因退出码 / 诊断缺失而失败。 |
| M3 round24 双错误 | 固定提交 `test_round24_dual_error_order_matches_fixed_baseline`：第一节点同时设 `approved`、`sources=[]`；固定 errors[0..3] 为 status 值域、approved 禁用、sources 非空、source_count 不符；CLI 退出 1，stdout 同时含 approved 与 sources 诊断。 | `tests.test_round24_weighted_tree.WeightedTreeStructureTest.test_validator_cli_preserves_dual_error_order_and_diagnostics` 固定完整四项列表，并检查 CLI 退出码和两条诊断。 | 定点反转 validator 错误列表；该测试在 errors[0..3] 顺序比较处失败。 |
| M3 round29 成功 / source_support 错误 | 固定提交 `tests/test_tools_split_baseline.py` 的 `test_round29_success_matches_fixed_baseline` 与 `test_round29_source_support_error_matches_fixed_baseline`：正常 `main()` 退出 0；第一条改为 `source_support=0.42` 后退出 1，stdout 含该诊断。 | `tests.test_round29_tree_split.AgreementValidatorRealFileTest.test_agreement_validator_cli_succeeds_on_registered_files` 与 `test_agreement_validator_cli_rejects_source_support_error`。 | 让错误 agreement 的 validator 返回无错误；错误 CLI 测试因退出码 / 诊断缺失而失败。 |
| M4 citation 聚合 | `git show f52b8f6:tests/contract/test_storage_ledger_split_baseline.py` 的 `test_citation_results_match_fixed_baseline_in_rule_order`：六个不同知识点、五份台账材料、`strict=True`、空临时 root；期望完整六项 reason 顺序为 dangling、withdrawn、unclear rights、forbid structuring、wrong digest、missing stored bytes。 | `tests.test_citation_gate.CitationGateTest.test_strict_bulk_report_preserves_all_six_reason_values_in_rule_order` 使用 `b"evidence"`、原相对路径、六个 `citation-{index}` ID、五份材料和相同完整 reason 列表；不加载旧版。 | 定点反转 `report.problems`；该测试在完整 reason 列表断言处失败。 |
| M5 restore 状态矩阵 | 固定提交同文件 `test_restore_material_rows_match_fixed_baseline` / `_restore_raw`：保留原八行输入，check-only；期望 `already_verified`、`existing_mismatch`、`invalid_url`、`storage_not_permitted`、`missing_url`、`invalid_path`、`reference_only`、`needs_download`。 | `tests.contract.test_material_restore_port.MaterialRestorePortTests.test_check_only_reports_all_eight_material_row_states` 直接调用当前 `restore_materials`，复制原字段、相对路径、URL、权限及已有文件状态；禁止网络并禁止创建临时目录。 | 将第四行 `storage_not_permitted` 定点改为 `needs_download`；测试因八项状态列表不符而失败。 |
| m1 命名 | 204 报告指出两方法只运行当前实现，没有 fixed source 或 old-run。 | `tests.contract.test_index_tree_verifiers` 两个方法现名为 `test_registered_index_variants_emit_expected_diagnostics` 和 `test_registered_trees_and_variants_have_expected_cli_diagnostics`。 | 纯命名改动，无行为变异。 |

故障场景沿用原 injector 的函数替换机制，保留真实 CLI 子进程、退出码与 stderr 检查。M1 的定点变异通过进程内转接 `run_ky` 到当前 `cli.main`，查询输入与正式测试一致；变异点只丢弃候选或 skip 原因。round24 / round29 变异作用于对应 validator 的错误处理结果，测试仍调用真实 `main()` 并检查退出码与 stdout。

实际变异命令：`py -3.12 review/rounds/round205_mutation_probe.py`。探针逐项执行正式测试，在临时 patch / 临时状态变异下确认预期 AssertionError；输出摘要如下：

```text
M1 drop-earlier-candidate mutation: expected failure observed
M1 suppress-text-hint mutation: expected failure observed
M2 freeze-stage event mutation: expected failure observed
M2 advance-stage missing-event mutation: expected failure observed
M3 round24 accepts-approved mutation: expected failure observed
M3 round24 changes-dual-error-order mutation: expected failure observed
M3 round29 accepts-source-support mutation: expected failure observed
M4 reverse-reason-order mutation: expected failure observed
M5 storage-permission-state mutation: expected failure observed
```

该临时探针执行后已删除；仓库没有留下变异源码或探针文件。各正式测试在未变异状态下通过最终验收。

## 第 203 轮“已有等价”自查

下表仅列 sol 204“不改与去向抽查”之外的第 203 轮“已有等价”项。打开了原固定提交输入构造和被指向的当前测试；确认同类直接期望，或补齐原来输入不一致的 CLI 场景。

| 第 203 轮条目 | 自查与处理 | 结果 |
|---|---|---|
| 六个 CLI 的成功 / 错误退出码：ledger、snapshot、route、resume、month-close、review-queue | ledger 的 `tests.contract.test_ledger_port.LedgerCliTest` 覆盖成功、无效台账和 usage；snapshot 成功与配置拒绝由 `tests.test_cli.SnapshotCliTest` 覆盖；resume 的执行 / 拒绝由 `tests.contract.test_resume_port.ResumePortContractTests` 覆盖；month-close 成功 / 非法月份由 `tests.test_cli.MonthCloseCliTest` 覆盖；review-queue 迁移端口已有成功 / 未登记版本拒绝。原表指向的 route-invalid-plan 不是原输入 `--revision 0`，原表对 snapshot 的 invalid-config 也不是 missing-config。新增 `test_route_show_rejects_zero_revision`、`test_snapshot_missing_config_exits_2`；原空队列 review check 与未登记 from-version 输入分别新增 `test_review_queue_check_succeeds_for_registered_empty_queue`、`test_review_queue_migration_rejects_unregistered_source_version`。另新增原输入的 `test_route_show_empty_store_json_exits_0`。 | 补齐输入差异；断言均为当前 CLI 直接退出码 / 无 traceback。 |
| resume-before-freeze 不写 resume 事件 | `tests.contract.test_resume_port.ResumePortContractTests.test_resume_dated_before_an_unresolved_freeze_is_rejected` 使用未解除 freeze 的日期输入，检查拒绝及 resume event 不存在。 | 同输入语义与状态期望均有直接保护。 |
| verifier / report 工具缺数据库、usage 和成功 | `tests.test_tool_exit_paths` 的 `test_verifiers_reject_missing_databases`、`test_unsupported_arguments_are_contract_exits`；Eng1 成功由 `tests.test_eng1_vocabulary.English1VocabularyRegressionTests.test_verifier_deterministic_check_and_mutations` 当前执行 verifier，外部 PDF 用 `require_path`；NetEM 成功由 `tests.test_netem_source.NetemSourceTests.test_verifier_passes_and_mutation_tests_are_all_detected` 当前执行 verifier。 | 直接当前进程结果，不依赖旧版。此处只读核对，模块不在本轮验收集合。 |
| manual、NetEM cross-validation、PDF skeleton 输出 | manual 当前退出 0 且生成非空文件：`tests.test_tool_exit_paths.ToolExitPathTests.test_registered_weight_manual_writes_an_output_file`；NetEM 当前执行并断言输出数值字段：`tests.test_netem_source.NetemSourceTests.test_cross_validation_numbers_are_reproducible`；PDF 成功路径由 `test_skeleton_json_outside_repository_uses_absolute_output_path` 检查输出，missing PDF 由 `test_skeleton_extractor_rejects_missing_pdf` 检查退出 2。 | 已有当前行为断言；旧、新产物逐字节比较本身属于对照。 |
| PDF probe 下载成功 / 非 PDF 失败 | `tests.test_tool_exit_paths.ToolExitPathTests.test_probe_success_and_non_pdf_failure` 使用本地 HTTP 服务，直接断言成功下载原始 PDF 字节、非 PDF 字节落盘与退出码；连接失败由同模块的 connection-failure 方法检查。 | 相同输入类别、当前输出字节与错误码均有直接保护。 |
| models seed 与字段变体 | `tests/test_contracts.py` 的 `ConfigContractTest`、`ReviewItemContractTest` 对相同公开模型字段的合法值与拒绝类别作当前断言；旧、新异常全文相等属于基线比较部分。 | 当前成功 / `ContractError` 类别有直接契约测试；不保留旧版异常文本相等断言。 |
| workspace seed 与注册表变体 | `tests/contract/test_workspace.py::WorkspaceContractTests.test_1_repository_registry` 检查注册表加载；`test_3_structure_rejections_report_contract_paths` 对结构错误断言 `ContractError` 与精确路径；路径和注册拒绝另有直接用例。 | 当前解析结果 / 契约拒绝有直接测试；旧函数长度、变体总数和 old/new 异常文本比较随脚手架退役。 |
| resume schedule boundary / due tiers | `tests.contract.test_freeze_scheduled_backlog` 的 `test_strict_date_boundary_and_shared_backlog_accounting`、`test_resume_converts_scheduled_without_revision_change` 与 `tests.contract.test_resume_port.ResumePortContractTests.test_reset_boundary_tiers_and_preserved_unmodified_items` 检查边界、计数、tier。 | 等价当前断言存在；纯新旧对象相等退役。 |
| 已由 sol 204 明确复核的引用聚合、restore 八行、round24/29 CLI、partial-skip、deck 模板、workspace path、index/tree | 本轮按 M1、M3、M4、M5 补齐引用条目；round24/29 CLI 和 partial-skip 依上表新增。deck 固定模板对照由 `Cs408LecturePipelineTest.test_outputs_match_pre_migration_templates_with_only_allowed_changes` 保留。 | 不重复新增；具体判断见 sol 204 表及 M1–M5 记录。 |

## 最终验收

执行命令：

```text
py -3.12 -m unittest tests.test_cli tests.test_round24_weighted_tree tests.test_round29_tree_split tests.test_citation_gate tests.contract.test_material_restore_port tests.contract.test_index_tree_verifiers tests.test_baseline_harness tests.contract.test_state_snapshot_counts_baseline
```

验收输出原文：

```text
Ran 118 tests in 63.880s
OK (skipped=4)
```

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。不提交。
