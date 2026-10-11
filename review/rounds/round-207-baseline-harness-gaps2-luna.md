# 第 207 轮：技术债包 B 再返工补缺

## 改动

- R1：`tests/test_cli.py::SnapshotCliTest.test_review_queue_migration_rejects_unregistered_source_version` 在临时目录先写入合法空队列，再执行迁移；断言退出 2、stderr 包含 `unregistered-version` 与 `mappings`、无 traceback。目标版本仍从工作区注册表读取。
- 第 205 轮新增的其余 CLI 用例：缺配置断言 `file does not exist` 与缺失文件名；revision=0 断言诊断含 `revision`；空 route JSON 成功断言 stdout 非空；空 review queue 成功断言 stdout 含 `OK`。这些断言各自命中实际诊断 / 输出。
- M2：冻结写入失败与推进失败分别断言 stderr 包含注入标记 `forced freeze write error` / `forced advance failure`，并保留既有状态断言。
- R2：`tests/test_contracts.py` 新增 revision=True 拒绝；以表驱动子测试检查 ReviewItem 必填字段缺失拒绝、三个可选字段缺失成功、Schedule 必填字段缺失拒绝。`tests/contract/test_workspace.py` 新增逐顶层键删除测试，只有 supplementary / products / settings 缺失成功，其余拒绝。
- R3：`tests/test_ledger.py::LedgerContractTest.test_non_mapping_rights_values_are_rejected` 对 rights=None、字符串、空映射逐项断言 ValueError。现有 `test_unknown_key_has_a_precise_path` 覆盖 unknown_right，故不重复。
- m1：M4 聚合测试改回 raw/manual 知识点、空 transition history、unreviewed 台账材料；unclear 材料保留 `may_be_structured=True`。六项 reason 顺序断言未改。

## R2 原变体逐行去向

原输入与期待来自 `git show f52b8f6:tests/contract/test_models_split_baseline.py` 的 `_config_variants` / `_review_variants`，以及 `git show f52b8f6:tests/contract/test_workspace_split_baseline.py` 的 `_registry_variants`。以下按变体生成规则逐项列出；同一规则中每个字段名均对应一条原变体。

### Config 变体

| 原变体行 | 当前直接断言去向 |
|---|---|
| `config-missing-{schema_version,project_id,default_daily_minutes,review_reserve_ratio,hard_max_ratio,subjects,review_policy}` | `tests.contract.test_config_port.ConfigPortTests.test_each_missing_required_root_field_is_reported_at_its_path`：前六项拒绝，review_policy 可选并有默认值；原表另有重复的 `config-missing-review_policy`，同一断言覆盖。 |
| `schema-version-bool`、`schema-version-unsupported`、`project-id-type` | `test_integer_fields_reject_booleans_and_floats` / `test_the_first_failing_check_in_documented_order`；旧期望均为拒绝。 |
| `daily-minutes-bool`、`daily-minutes-lower-bound`、`ratio-bool`、`ratio-nan`、`ratio-inf`、`ratio-out-of-range`、`ratio-zero`、`ratio-below-reserve` | `test_integer_fields_reject_booleans_and_floats`、`test_number_fields_reject_booleans_and_strings_but_accept_integers`、`test_subject_level_semantics_report_documented_paths` 及 reserve/hard-ratio 范围测试；拒绝期望已有直接覆盖。 |
| `subjects-type`、`subjects-empty`、`review_policy-type`、`review_policy-mode-missing`、`review_policy-mode-invalid`、`review_policy-unknown` | `test_review_policy_mode_values_and_shape`、`test_the_first_failing_check_in_documented_order`；subjects 空 / 类型拒绝已有 config 结构断言。 |
| `unknown-root`、`unknown-subject`、`subject-missing-{subject_id,display_name,weight,active,min_daily_minutes}` | `test_unknown_keys_report_the_first_in_sorted_order`、`test_each_subject_field_is_required_except_min_daily_minutes`（可选字段成功）。 |
| subject id/display/weight/active/minutes 类型与范围、重复 ID、无 active subject、权重和不闭合、floor overflow | `test_subject_level_semantics_report_documented_paths`、`test_duplicate_subject_ids_are_rejected`、`test_weights_must_close`、`test_minimum_budget_cannot_exceed_daily_budget`；直接断言拒绝。 |
| `hard-ratio-order-probe`、`subject-field-order-probe`、各 validation section 的 cross-section pair | `test_the_first_failing_check_in_documented_order` 覆盖规格规定的首错路径；这些只检验拒绝先后次序，旧函数身份 / 新旧输出比较随退役。 |
| `config-root-not-mapping` | ConfigPort 结构拒绝测试直接检查非 mapping 输入为 ContractError。 |

### ReviewItem 变体

| 原变体行 | 当前直接断言去向 |
|---|---|
| `review-missing-{review_id,revision,subject_id,knowledge_point_id,title,granularity,state,estimated_minutes,introduced_on,due_date,schedule,defer_count}` | `tests.test_contracts.ReviewItemContractTest.test_required_review_and_schedule_fields_cannot_be_omitted`：逐项 ContractError。 |
| `review-missing-{last_reviewed_on,last_quality,self_rating}` | 同上：逐项作为可选字段缺失成功。 |
| `review-schedule-missing-{mode,phase,interval_days,ease_factor,repetitions,lapses}` | 同上：逐项 ContractError。 |
| `review-type-revision` | `test_revision_boolean_is_rejected`，专门断言 revision=True 被拒绝。 |
| 其余 `review-type-{review_id,subject_id,knowledge_point_id,title,granularity,state,estimated_minutes,introduced_on,due_date,last_reviewed_on,schedule,defer_count,last_quality,self_rating}` | 对应 ReviewItem 字段结构 / 日期 / optional feedback 的现有直接契约测试；本轮必填缺失表补齐字段存在性，类型断言以 `ReviewItemContractTest` 的类型、日期、schedule、feedback 专项测试为去向。 |
| `review-unknown-key`、`review-schedule-unknown-key` | `test_unknown_reviews_root_key_is_rejected` 覆盖文件根未知键；ReviewItem 未知字段由 `test_unknown_state_rejected` 等当前契约结构测试及 unknown-key 检查覆盖。 |
| phase bool / 越界、interval 下界、ease NaN / 范围、repetitions bool、lapses 负数、mode invalid、state / granularity invalid | `test_phase_mode_consistency_enforced`、`test_ease_factor_range_enforced`、`test_unknown_state_rejected`、`test_unknown_granularity_rejected` 与 schedule / progress 契约测试。 |
| estimated over cap、last_quality 越界、self_rating invalid、日期倒置、vocabulary batch 超长 | `test_single_pass_cap_rejects_oversized_item`、`test_unknown_self_rating_rejected`、`test_due_before_introduced_rejected`、`test_vocabulary_batch_cost_is_bounded`；`last_reviewed_on` 日期与 defer / quality 边界由 progress port 测试覆盖。 |
| category/date/identity order probes、cross-section pair、root-not-mapping | 其中首错顺序属于与旧版比较的语境，随旧对照退役；拒绝类别由前述当前断言覆盖。原表要求的 revision identity 输入另由专项用例锁定。 |

### Workspace 变体

| 原变体行 | 当前直接断言去向 |
|---|---|
| `missing-top-level-{schema_version,subjects,reference,materials,state,staging,projection}` | `tests.contract.test_workspace.WorkspaceContractTests.test_required_top_level_blocks_cannot_be_omitted`：逐项 ContractError。 |
| `missing-top-level-{supplementary,products,settings}` | 同一方法：逐项成功。 |
| schema-version type、subjects/reference type、unknown root、invalid subject id、profile type | `test_3_structure_rejections_report_contract_paths` 的结构拒绝表已直接断言。 |
| topic_weights parent/backslash/absolute path | `test_4_registered_path_syntax_is_rejected`。 |
| syllabus versions type、unknown subject、record type、empty versions、bad label、duplicate path、mapping type、effective-tree mismatch | `test_syllabus_versions_effective_pointer_and_labels`、`test_syllabus_versions_reject_duplicate_tree_path`。 |
| paper_shapes type / unknown subject / invalid path | `test_3_structure_rejections_report_contract_paths` 与 `test_4_registered_path_syntax_is_rejected`。 |
| weight-batches invalid path / type | `test_4b_weight_batch_path_is_optional_but_validated_when_present`。 |
| exam-index unknown subject before value type | `test_require_mapping_list_error_depends_on_registration`。 |
| `double-error-schema-before-{每个顶层键}`、全部 paired error-order probes | 这些变体只用于旧 / 新比较首错次序；当前输入拒绝由相应结构 / 路径断言覆盖，比较新旧错误内容的脚手架随旧对照退役。 |

## 定点变异

- R1 不建队列反证：在内存中 patch `ReviewShardStore.write` 为 no-op，再运行 `SnapshotCliTest.test_review_queue_migration_rejects_unregistered_source_version`。命令：
  `py -3.12 -c "import unittest; from unittest.mock import patch; import tests.test_cli as m; from ky.storage.review_shards import ReviewShardStore; p=patch.object(ReviewShardStore, 'write', lambda *a, **k: None); p.start(); r=unittest.TextTestRunner().run(unittest.TestSuite([m.SnapshotCliTest('test_review_queue_migration_rejects_unregistered_source_version')])); p.stop(); print('NO_QUEUE_MUTANT_CAUGHT=', not r.wasSuccessful())"`
  结果：测试在 `unregistered-version` 诊断断言处失败，stderr 实为 `file does not exist`；`NO_QUEUE_MUTANT_CAUGHT=True`。
- R2 revision=True 变异：patch 被测调用，把布尔 revision 转成整数 1。命令：
  `py -3.12 -c "import unittest, tests.test_contracts as m; original=m.validate_review_item; m.validate_review_item=lambda x, **kw: original({**x, 'revision': 1} if isinstance(x, dict) and x.get('revision') is True else x, **kw); r=unittest.TextTestRunner().run(unittest.TestSuite([m.ReviewItemContractTest('test_revision_boolean_is_rejected')])); print('MUTANT_CAUGHT=', not r.wasSuccessful())"`
  结果：`ContractError not raised`，测试失败，`MUTANT_CAUGHT=True`。
- R3 rights=None 变异：patch 校验入口把 None 换成有效 rights 再调用原函数。命令：
  `py -3.12 -c "import unittest, tests.test_ledger as m; original=m.validate_material; m.validate_material=lambda raw, **kw: original({**raw, 'rights': m.local_material()['rights']} if isinstance(raw, dict) and raw.get('rights') is None else raw, **kw); r=unittest.TextTestRunner().run(unittest.TestSuite([m.LedgerContractTest('test_non_mapping_rights_values_are_rejected')])); print('RIGHTS_NONE_MUTANT_CAUGHT=', not r.wasSuccessful())"`
  结果：rights=None 子测试因未抛 ValueError 而失败，`RIGHTS_NONE_MUTANT_CAUGHT=True`。
- Workspace 顶层缺失和新增 M2 诊断断言未单独做 mutation probe；这是本轮未完成项。

## 验收

命令：

```text
py -3.12 -m unittest tests.test_cli tests.test_contracts tests.contract.test_config_port tests.contract.test_review_progress_port tests.contract.test_workspace tests.test_ledger tests.contract.test_ledger_port tests.test_citation_gate
```

验收输出原文：

```text
...............................................................................................................s.....................................................................................................
----------------------------------------------------------------------
Ran 266 tests in 28.548s

OK (skipped=1)
```

初次验收曾失败一次：缺配置诊断的实际文本不含 `--config`；改为断言实际 `file does not exist` 和文件名后，最终指定验收通过。

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。

## 未完成

Workspace / Review / Config 的原变体表规模较大；本报告按原生成规则归并列出去向，但不是每个原始变体实例都已由本轮新增一条直接测试独立重建。尤其需复核类型、范围、跨段首错序断言映射是否为同输入同期望。Workspace 顶层缺失变体与 revision=True 已补测；其余旧对照文件不恢复。未提交。
