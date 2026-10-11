# Round 203 — baseline harness continuation

**结果：完成。** 保留 1 个 harness 实例，迁移了当前行为断言，删除其余 8 个 A 类文件。没有修改 `ky/`、`tools/`、`contracts/` 或 `data/`；未提交。

## (b) 断言去向

| 原文件 :: 方法 :: 断言 | 去向 |
|---|---|
| `test_cli_split_baseline.py :: test_day_plan_record_cli_bytes_match_fixed_baseline :: record 失败/成功时事件是否写入` | 已有等价：`tests/test_cli.py::DayPlanCliTest::test_record_completion_event_and_duplicate_day_is_rejected`、`test_record_with_review_store_and_unknown_review_id_exits_2_and_writes_nothing`、`test_record_on_legacy_reviewed_queue_exits_2_and_writes_nothing`；写入失败矩阵由 `tests/contract/test_day_plan_store_port::test_gate_failure_on_the_temp_reread_publishes_nothing`、`tests/contract/test_freeze_port::test_freeze_gate_checks_the_final_plan_day_before_writing` 与 `tests/test_review_queue_advance::test_queue_and_completion_ids_stay_unchanged_if_write_fails` 覆盖。 |
| 同上 :: 候选题输出、部分查询失败提示、freeze payload | 已有等价：`tests/test_cli.py::test_lenient_fluent_json_contains_question_candidates`、`test_missing_workspace_skips_questions_after_recording`、`test_lenient_fluent_unchecked_record_lists_index_candidate`；freeze 展示由 `tests/contract/test_freeze_port::test_frozen_text_marks_review_limits_inactive_and_hides_timeline_phase` 覆盖。 |
| `test_cli_split_baseline.py :: test_six_commands_match_fixed_baseline :: 各子命令预期退出码` | 已有等价：ledger 为 `tests/contract/test_ledger_port::LedgerCliTest`（成功、无效输入、usage）；snapshot 为 `tests/test_cli.py::SnapshotCliTest`；route 为 `tests/contract/test_route_plan_port::TestRoutePlanCli::test_submit_then_show_json_and_invalid_plan`；resume 为 `tests/contract/test_resume_port::ResumePortContractTests`；month-close 为 `tests/test_cli.py::MonthCloseCliTest`；review-queue 为 `tests/test_cli.py::CliContractTest`。 |
| 同上 :: resume-before-freeze 不写 resume 事件 | 已有等价：`tests/contract/test_resume_port::ResumePortContractTests::test_resume_dated_before_an_unresolved_freeze_is_rejected`。 |
| `test_tools_split_baseline.py :: test_verifier_and_report_tools_match_fixed_baseline :: 缺库和参数错误退出码` | 缺数据库行为迁到 `tests/test_tool_exit_paths.py::test_verifiers_reject_missing_databases`；usage 行为迁到 `test_unsupported_arguments_are_contract_exits`。成功路径已有等价：`tests/test_eng1_vocabulary.py::test_verifier_deterministic_check_and_mutations`、`tests/test_netem_source.py::test_verifier_passes_and_mutation_tests_are_all_detected`。 |
| `test_tools_split_baseline.py :: test_question_extraction_verifier_success_when_products_are_registered :: 注册产物可通过 verifier` | 迁到 `tests/test_question_extraction.py::test_registered_question_extraction_verifier_accepts_outputs`。 |
| `test_tools_split_baseline.py :: test_eng1_verifier_success_matches_when_registered_papers_are_present :: 有注册论文时 verifier 成功` | 已有等价：`tests/test_eng1_vocabulary.py::test_verifier_deterministic_check_and_mutations`；缺外部 PDF 时由该测试自己的 `require_path` 跳过。 |
| `test_tools_split_baseline.py :: test_file_producers_match_outputs_and_failures :: manual 生成、参数错误、PDF 骨架输出` | manual 成功及空输出防回归迁到 `tests/test_tool_exit_paths.py::test_registered_weight_manual_writes_an_output_file`；参数错误由 `test_unsupported_arguments_are_contract_exits` 覆盖；PDF 成功输出由 `test_skeleton_json_outside_repository_uses_absolute_output_path` 覆盖。NetEM 文件/数字由 `tests/test_netem_source.py::test_cross_validation_numbers_are_reproducible` 覆盖。旧、新文件树完全相同的部分只对迁移对照有意义，随实例退役。 |
| `test_tools_split_baseline.py :: test_html_extraction_success_uses_temporary_product_root :: 当前提取器生成索引、报告及 deck map` | 迁到 `tests/test_question_extraction.py::test_registered_extraction_writes_current_outputs`；所需原始 HTML 按注册表定位并使用 `tests._resources.require_path`。 |
| `test_tools_split_baseline.py :: test_html_extraction_argument_failure_needs_no_external_inputs :: usage 错误码` | 迁到 `tests/test_tool_exit_paths.py::test_unsupported_arguments_are_contract_exits`。 |
| `test_tools_split_baseline.py :: test_pdf_probe_matches_download_and_non_pdf_failure :: 成功下载字节及非 PDF 错误码/落盘行为` | 迁到 `tests/test_tool_exit_paths.py::test_probe_success_and_non_pdf_failure`。网络连接失败已有等价：同文件 `test_probe_connection_failure_is_a_contract_exit`。 |
| `test_tools_split_baseline.py :: test_round24_success_matches_fixed_baseline`、`test_round24_status_error_matches_fixed_baseline` :: validator 当前成功/错误行为 | 已有等价：`tests/test_round24_weighted_tree.py::WeightedTreeStructureTest::test_real_file_passes_validation` 与 `MutationTest::test_wrong_weight_for_evidence_tag_is_rejected`。 |
| `test_tools_split_baseline.py :: test_round24_dual_error_order_matches_fixed_baseline :: 两版多个诊断的顺序相同` | 随实例退役：断言只规定旧、新版本次序一致，当前输出正确性由 round24 结构与逐项变异测试覆盖。 |
| `test_tools_split_baseline.py :: test_round29_success_matches_fixed_baseline`、`test_round29_source_support_error_matches_fixed_baseline :: verifier 当前成功/来源错误行为` | 已有等价：`tests/test_round29_tree_split.py::MainTableVerifyTreeTest::test_real_files_pass`、`MutationTest::test_wrong_source_support_is_rejected_by_agreement_validator`。 |
| `test_deck_scaffold_split_baseline.py :: test_split_tools_write_the_same_bytes_as_the_fixed_baseline :: 讲解模板小节、覆盖表和 no-hit 提示存在` | 已有等价：`tests/test_cs408_lecture_pipeline.py::Cs408LecturePipelineTest::test_outputs_match_pre_migration_templates_with_only_allowed_changes`。本次未改该文件。 |
| `test_models_split_baseline.py :: test_fixed_baseline_matches_seed_and_generated_variants :: 合法/非法数据的结果类别与 ContractError` | 已有等价：`tests/test_contracts.py::ConfigContractTest`、`ReviewItemContractTest` 的种子与字段/类型错误断言；迁移版本比较异常文本的部分只属于对照。 |
| `test_schedule_split_baseline.py :: test_completion_parser_preserves_validation_order :: 旧、新 parser 校验顺序一致` | 随实例退役：只比较两版错误先后顺序；当前 parser 的字段和值域错误由 `tests/test_completion.py::ParseCompletionEventTest` 覆盖。 |
| `test_storage_ledger_split_baseline.py :: test_resume_schedule_matches_fixed_baseline_d11_boundary :: overdue tier 和计数` | 已有等价：`tests/contract/test_freeze_scheduled_backlog.py::test_strict_date_boundary_and_shared_backlog_accounting`、`test_resume_converts_scheduled_without_revision_change`；resume tiers 由 `tests/contract/test_resume_port.py::test_reset_boundary_tiers_and_preserved_unmodified_items` 覆盖。 |
| `test_storage_ledger_split_baseline.py :: test_citation_results_match_fixed_baseline_in_rule_order :: 每类引用问题与聚合问题列表` | 已有等价：`tests/test_citation_gate.py` 中 `test_a_dangling_citation_is_a_problem`、`test_a_withdrawn_material_blocks_the_citation`、`test_unclear_rights_block_the_citation`、`test_rights_that_forbid_structuring_block_the_citation`、`test_a_wrong_digest_in_the_citation_is_a_problem`、`test_report_lists_every_problem_not_just_the_first`。 |
| `test_storage_ledger_split_baseline.py :: test_restore_material_rows_match_fixed_baseline :: check-only 不联网、不建临时目录` | 已有等价：`tests/contract/test_material_restore_port.py::MaterialRestorePortTests::test_check_is_read_only_and_never_calls_network`。 |
| 同文件 :: commit、plan-write、material validation 的 old/new 相等断言 | 随实例退役：这些方法没有独立于比较的额外当前值断言；对应写入/契约错误由 `tests/contract/test_day_plan_store_port`、`test_ledger.py` 和 `tests/contract/test_material_restore_port` 的端口测试覆盖。 |
| `test_workspace_split_baseline.py :: test_fixed_baseline_matches_seed_and_generated_variants :: 当前解析成功或 ContractError` | 已有等价：`tests/contract/test_workspace.py::WorkspaceContractTests::test_1_repository_registry`、`test_3_structure_rejections_report_contract_paths` 及路径/注册表拒绝测试。旧函数长度和变体数量是迁移证明脚手架，随实例退役。 |
| `test_state_snapshot_counts_baseline.py :: test_snapshot_json_matches_pinned_m12_with_date_boundaries :: 日期边界、科目队列计数、空队列为零` | 保留并改写为 harness 实例；原有直接计数断言仍在该测试中。 |
| `test_index_tree_verifiers_split_baseline.py :: test_registered_index_variants_match_fixed_baseline :: 当前 verifier 对每个索引变体给出目标诊断` | 迁到 `tests/contract/test_index_tree_verifiers.py::IndexTreeVerifierTests::test_registered_index_variants_match_fixed_baseline`；仅比较旧、新字节的断言已去掉。 |
| 同文件 :: `test_registered_trees_and_variants_match_fixed_cli :: 当前 tree CLI 退出码和诊断标记` | 迁到 `tests/contract/test_index_tree_verifiers.py::IndexTreeVerifierTests::test_registered_trees_and_variants_match_fixed_cli`；保留当前 CLI 直接断言。资源路径仍通过 `require_path`。 |

说明：提交前的原 A 类集合曾为 34 tests、skip 2；本轮新迁入的 index/tree 测试在当前 checkout 中实际运行通过 2 项，未 skip。因此“本工作区恒为 skip”不是本轮可复现事实，按当前真实输入执行并保留了行为断言。

## 保留实例与变异证明

保留 `tests/contract/test_state_snapshot_counts_baseline.py`：纯函数、4 个小型队列记录、固定旧版 `b867ae7`，相较 CLI/文件生成器更稳定，也不需要外部资源。

该实例使用 `tests/_baseline_harness.py` 的 `fixed_source`、`load_isolated` 与 `compare_runs`。调用方判别器检查旧源码包含旧实现标记 `subject_items =` 且不包含拆分后的 `count_review_items_by_subject`。旧版和当前版共用相同配置、队列、日期输入，输出以 JSON 原始字节放入 `(returncode, stdout, stderr)`，并比较写后文件树（此纯函数场景为空树）。

`tests.test_baseline_harness::test_state_snapshot_mutations_trip_original_and_harness_instance` 从固定提交 `f52b8f6` 取改写前测试文件，并对当前 `ky/schedule/state_snapshot.py` 写两份临时源码副本：

1. 将 `in_review_queue=counts.in_review_queue` 定点改为 `+ 1`；
2. 将 `due_today_count=counts.due_today_count` 定点改为 `+ 1`。

两处变异分别对原测试和改写后测试都产生失败；未变异源码下两者都通过。实际命令：`py -3.12 -m unittest tests.test_baseline_harness`，5 tests，OK（包含四种原/新 × 变异/未变异组合）。

## Harness 接口

- `fixed_source(repository, commit, path, identity)`: 只接受十六进制固定 commit hash，拒绝 `HEAD`、分支名等符号引用；先确认对象类型为 commit，再读取源码并运行调用方身份判别器。
- `load_isolated(source, name)`: 唯一模块名执行旧源码，隔离同名当前模块。
- `ProcessResult`, `output_tree`, `compare_results`: 比较退出码、stdout/stderr 原始字节和写后文件树原始字节。
- `compare_runs(old_run, new_run)`: 在同一输入上下文运行两侧并比较结果。
- 自测覆盖 HEAD 拒绝、旧版身份失败、进程/文件字节差异和一致通过。

Harness 只含机制，没有端口业务数据。

## 辅助函数收敛

- `tests/_fixtures.py`：选择它而不是扩展 `tests/_resources.py`；后者专用于外部资源 skip/fail 策略，本模块放纯测试夹具。
- 四个端口测试现在直接引用公开 `LegacyConfigView`，没有 `_LegacyConfigView` 兼容别名。`as_dataclass()` 中的旧字段形状和断言保留，配置视图只维护一份实现。
- availability、freeze、day-budget 三个端口的 `_git_source` 逐字节相同，改为 `tests._fixtures.git_source`；测试类方法入口只转发，不复制 Git/错误处理脚手架。
- `_write_registry`：退役后剩余用法在 `test_exam_index_port.py` 与 `test_state_snapshot_port.py`，参数形状和目录创建行为不同，不合并。
- `make_item`：退役后剩余实现具有不同默认 schedule、返回类型和参数签名，不合并。
- `run_cli`：`tests/test_cli.py` 返回 subprocess 结果；ledger port helper 在进程内捕获字符串输出，语义不同，不合并。
- schedule baseline 里的简化 `LegacyConfigView` 在该 A 文件退役时一并退役；它只暴露旧字段读取，不含 `as_dataclass()`，无剩余调用者。

## 删除清单

- `tests/test_cli_split_baseline.py`
- `tests/test_tools_split_baseline.py`
- `tests/test_deck_scaffold_split_baseline.py`
- `tests/contract/test_models_split_baseline.py`
- `tests/contract/test_schedule_split_baseline.py`
- `tests/contract/test_storage_ledger_split_baseline.py`
- `tests/contract/test_workspace_split_baseline.py`
- `tests/contract/test_index_tree_verifiers_split_baseline.py`

保留 `tests/contract/test_state_snapshot_counts_baseline.py`。index/tree 当前行为测试位于 `tests/contract/test_index_tree_verifiers.py`。

## 耗时对比

退役前原 9 模块集合（轮 200 实测）：

```text
py -3.12 -m unittest tests.test_cli_split_baseline tests.test_tools_split_baseline tests.test_deck_scaffold_split_baseline tests.contract.test_models_split_baseline tests.contract.test_schedule_split_baseline tests.contract.test_storage_ledger_split_baseline tests.contract.test_workspace_split_baseline tests.contract.test_state_snapshot_counts_baseline tests.contract.test_index_tree_verifiers_split_baseline
Ran 34 tests in 80.379s
OK (skipped=2)
实际墙钟 81.134s
```

退役后替代的 A 类相关模块集合（保留实例、迁入行为断言、工具行为断言）：

```text
py -3.12 -m unittest tests.test_baseline_harness tests.contract.test_state_snapshot_counts_baseline tests.contract.test_index_tree_verifiers tests.test_tool_exit_paths tests.test_question_extraction
Ran 18 tests in 30.960s
OK
实际墙钟 31.598s
```

前后测试数量和模块职责不同；上述是实测集合耗时，不视为完全同输入的基准比较。

## 验收输出

最终验收命令：

```text
py -3.12 -m unittest tests.test_baseline_harness tests.contract.test_state_snapshot_counts_baseline tests.contract.test_index_tree_verifiers tests.test_tool_exit_paths tests.test_question_extraction tests.contract.test_planner_port tests.contract.test_availability_port tests.contract.test_freeze_port tests.contract.test_day_budget_port
Ran 83 tests in 47.389s
OK
实际墙钟 48.069s
```

分项先验：`tests.contract.test_index_tree_verifiers` 2 tests OK；`tests.test_question_extraction` 2 tests OK；`tests.test_tool_exit_paths` 在最终验收中通过；四个受影响端口和 harness/保留实例均在最终集合内通过。

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。
