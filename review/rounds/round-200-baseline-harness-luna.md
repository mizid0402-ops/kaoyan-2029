# Round 200 — baseline harness and retirement audit

**状态：未完成，不可据此退役 A 类测试。** 本轮完成了方法级盘点、共享 harness 初版和四份配置适配器的收敛；未完成 (b) 断言迁移、保留实例改写及变异等价证明，因此 9 个 A 类文件均保留。没有改 `ky/`、`tools/`、`contracts/` 或 `data/`。

## 1. 方法盘点

类别：(a) 固定旧版与当前实现对照；(b) 当前行为断言；(c) 旧版身份断言。一个方法可含多个类别。

| 文件 | 方法 | 类别 | 内容 |
|---|---|---|---|
| `tests/test_cli_split_baseline.py` | `test_preflight_cli_bytes_match_fixed_baseline` | a | 比较旧版与当前 CLI 的退出码及原始输出。 |
| 同上 | `test_day_plan_submit_cli_bytes_match_fixed_baseline` | a,b | 对照 CLI 字节；同时检查成功/失败后的写入状态。 |
| 同上 | `test_day_plan_record_cli_bytes_match_fixed_baseline` | a,b | 对照 CLI 字节；同时检查记录及失败时无完成事件。 |
| 同上 | `test_old_functions_are_pre_split_implementations` | c | 断言固定源中的旧函数满足拆分前长度条件。 |
| 同上 | `test_six_commands_match_fixed_baseline` | a,b,c | 比较六类命令输出，并检查旧函数身份及关键结果/状态。 |
| `tests/test_tools_split_baseline.py` | `test_verifier_and_report_tools_match_fixed_baseline` | a,b | 比较工具输出，并断言预期退出码。 |
| 同上 | `test_question_extraction_verifier_success_when_products_are_registered` | a,b | 注册产物存在时对照，并断言退出码为 0。 |
| 同上 | `test_eng1_verifier_success_matches_when_registered_papers_are_present` | a,b | 注册论文存在时对照，并断言退出码为 0。 |
| 同上 | `test_file_producers_match_outputs_and_failures` | a,b | 对照生成文件树、错误输出及成功/失败退出码。 |
| 同上 | `test_html_extraction_success_uses_temporary_product_root` | a,b | 对照临时产品目录文件树，并断言成功。 |
| 同上 | `test_html_extraction_argument_failure_needs_no_external_inputs` | a,b | 对照参数错误，并断言退出码为 2。 |
| 同上 | `test_pdf_probe_matches_download_and_non_pdf_failure` | a,b | 对照下载结果与文件字节，并断言成功和非 PDF 失败码。 |
| 同上 | `test_round24_success_matches_fixed_baseline` | a,b | 对照成功输出，并检查成功码。 |
| 同上 | `test_round24_status_error_matches_fixed_baseline` | a,b | 对照错误输出，并检查状态错误契约。 |
| 同上 | `test_round24_dual_error_order_matches_fixed_baseline` | a,b | 对照双错误次序及对应诊断。 |
| 同上 | `test_round29_success_matches_fixed_baseline` | a,b | 对照成功输出及结果码。 |
| 同上 | `test_round29_source_support_error_matches_fixed_baseline` | a,b | 对照 source-support 错误及诊断。 |
| `tests/test_deck_scaffold_split_baseline.py` | `test_split_tools_write_the_same_bytes_as_the_fixed_baseline` | a,b,c | 对照两个工具输出/文件树；检查旧模板内容和旧函数身份。 |
| `tests/contract/test_models_split_baseline.py` | `test_fixed_baseline_matches_seed_and_generated_variants` | a,c | 对照固定旧版及变体，并验证旧解析器身份。 |
| `tests/contract/test_schedule_split_baseline.py` | `test_review_selection_matches_fixed_baseline` | a | 比较旧版与当前复习选择结果。 |
| 同上 | `test_month_close_matches_fixed_baseline_with_duplicate_days` | a | 比较月结结果。 |
| 同上 | `test_invariant_checks_match_fixed_baseline` | a | 比较不变量检查结果。 |
| 同上 | `test_snapshot_matches_fixed_baseline_with_explicit_overrides` | a | 比较快照结果。 |
| 同上 | `test_completion_parser_preserves_validation_order` | a,b | 对照旧版，同时锁定多错误输入的校验先后顺序。 |
| `tests/contract/test_storage_ledger_split_baseline.py` | `test_review_shard_commit_matches_fixed_baseline` | a,b | 对照提交结果/文件树，并检查写后状态。 |
| 同上 | `test_day_plan_write_matches_fixed_baseline` | a,b | 对照计划写入及文件字节。 |
| 同上 | `test_resume_schedule_matches_fixed_baseline_d11_boundary` | a,b | 对照 D11 边界结果，并检查状态字段。 |
| 同上 | `test_validate_material_matches_fixed_baseline_and_error_paths` | a,b | 对照有效/无效材料及错误路径行为。 |
| 同上 | `test_citation_results_match_fixed_baseline_in_rule_order` | a,b | 对照引用结果/错误次序。 |
| 同上 | `test_restore_material_rows_match_fixed_baseline` | a,b | 对照逐行结果，并检查 `--check` 无临时下载目录。 |
| `tests/contract/test_workspace_split_baseline.py` | `test_fixed_baseline_matches_seed_and_generated_variants` | a,c | 对照种子与变体，并验证拆分前函数长度。 |
| `tests/contract/test_state_snapshot_counts_baseline.py` | `test_snapshot_json_matches_pinned_m12_with_date_boundaries` | a,b,c | 对照 JSON；另断言日期边界计数、零队列和固定旧实现身份。 |
| `tests/contract/test_index_tree_verifiers_split_baseline.py` | `test_registered_index_variants_match_fixed_baseline` | a,b | 对照索引变体；直接验证每个诊断标记。资源缺失时 skip。 |
| 同上 | `test_registered_trees_and_variants_match_fixed_cli` | a,b | 对照树校验 CLI；验证退出码/诊断标记。无注册树时 skip。 |

### (b) 迁移状态

本轮尚未迁移任何 (b) 断言。计划对应正规测试模块需逐项查重：CLI 状态断言归 `tests/test_cli.py`；工具断言分别归相应 `tests/test_*` 或 `tests/contract/` 端口测试；模型、schedule、storage、workspace、snapshot 与 verifier 断言按 `docs/模块地图.md` 对应端口迁移。当前未声称已有等价覆盖，未删除承载这些断言的文件。`test_index_tree_verifiers_split_baseline.py` 的两个 skip 原因为注册索引/答题读取器缺失和无注册知识树；若迁移，资源门禁使用 `tests._resources.require_path`。

## 2. Harness 初版

新增 `tests/_baseline_harness.py`：`fixed_source` 仅接受十六进制固定提交哈希，先用 Git 对象类型验证其为 commit，再读取指定文件并运行调用方旧版判别器；`load_isolated` 使用唯一模块名隔离执行；`output_tree` 返回相对路径到原始字节映射；`ProcessResult` / `compare_results` 比较退出码、stdout、stderr 和写后文件树；`compare_runs` 在同一调用上下文运行两侧并比较。

新增 `tests/test_baseline_harness.py`：拒绝 `HEAD`、拒绝旧版判别失败、进程/文件字节差异时报错、完全一致时通过。

实际验证：`py -3.12 -m unittest tests.test_baseline_harness`，4 tests，OK。

限制：尚未把保留实例接入 harness，也未对真实端口实例执行两处临时变异。因此它目前是机制初版，不构成 9 份现有对照已由新机制等价替代的证明。

## 3. 测试辅助收敛

新增 `tests/_fixtures.py`，选择它而非继续扩展 `_resources.py`：后者职责是外部资源存在性与 skip/fail 策略；本次 legacy-shaped 配置和固定源读取是纯测试夹具。

- `LegacyConfigView` / `as_dataclass`：从 planner、availability、freeze、day-budget 四处重复实现收敛到共享夹具；调用处仍通过 `_LegacyConfigView` 别名，比较断言未改。
- `_git_source`：availability、freeze、day-budget 三处逐字节相同的读取与失败断言改用共享 `git_source`；保留各测试类方法入口。
- `test_schedule_split_baseline.py` 另有只实现 `__getattr__`、没有 `as_dataclass` 的微差实现，本轮未合并。
- `_write_registry`、`make_item`、`run_cli` 未合并：本轮尚未完成跨文件逐项比对，未把语义近似当作相同。

验证：`py -3.12 -m unittest tests.contract.test_planner_port tests.contract.test_availability_port tests.contract.test_freeze_port tests.contract.test_day_budget_port`，65 tests，OK。

## 4. 保留实例、变异及退役

未选定保留实例，未执行变异证明，未删除任何 A 类文件。故本任务的核心等价证明与退役步骤未完成；不要据此清理旧对照。

## 5. 耗时记录

退役前原 9 模块集合：

```text
py -3.12 -m unittest tests.test_cli_split_baseline tests.test_tools_split_baseline tests.test_deck_scaffold_split_baseline tests.contract.test_models_split_baseline tests.contract.test_schedule_split_baseline tests.contract.test_storage_ledger_split_baseline tests.contract.test_workspace_split_baseline tests.contract.test_state_snapshot_counts_baseline tests.contract.test_index_tree_verifiers_split_baseline
Ran 34 tests in 80.379s
OK (skipped=2)
实际墙钟 81.134s
```

退役后耗时：未测，因为尚未退役。

## 6. 验收与未完成项

已运行完整的当前可运行验收子集：

```text
py -3.12 -m unittest tests.test_baseline_harness tests.contract.test_state_snapshot_counts_baseline tests.contract.test_planner_port tests.contract.test_availability_port tests.contract.test_freeze_port tests.contract.test_day_budget_port
Ran 70 tests in 16.913s
OK
```

另单独运行 harness 自测：`py -3.12 -m unittest tests.test_baseline_harness`，4 tests，OK；四个端口模块单独运行，65 tests，OK。

未运行任务书完整验收命令：迁移模块、保留实例和变异证明尚未完成。未运行全量（遵守 `AGENTS.md`）。
