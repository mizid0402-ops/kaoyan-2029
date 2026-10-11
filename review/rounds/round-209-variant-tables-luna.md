# 第 209 轮：迁移对照变体表整表迁移

## 迁移位置与断言方式

- Config 输入生成器 `_config_variants` 位于 `tests.contract.test_config_port`；共享的嵌套字段写入与跨段组合构造辅助函数位于 `tests._fixtures`。`tests.contract.test_config_port.ConfigFormatTests.test_single_error_variant_table` 对每个保留变体按原 `expected_success` 直接运行当前 `validate_config`，要求成功或抛 `ContractError`。
- ReviewItem 输入生成器 `_review_variants` 位于 `tests.test_contracts` 的 ReviewItem 测试模块；`tests.test_contracts.ReviewItemContractTest.test_single_error_variant_table` 对每个保留变体直接运行当前 `validate_review_item`，按原 `expected_success` 断言结果类别。
- Workspace 输入生成器 `_registry_variants` 位于 `tests.contract.test_workspace`；`tests.contract.test_workspace.WorkspaceContractTests.test_single_error_variant_table` 对每个保留变体直接运行当前 `load_workspace`，按原 `expected_success` 断言结果类别。
- 三个原比较器没有给单错误变体指定固定 `ContractError.path` 期望；它们比较的是新旧异常路径。因此当前表对每个失败变体断言异常类别为 `ContractError`，没有从本次运行反抄路径。
- 每张表按唯一变体名确认没有重名。生成器保留组合输入的构造，以便统计源表完整规模；测试只过滤下列仅用于错误顺序比较的组合输入。

## 数量

数量由三个生成器运行时产出并在本轮独立统计，测试没有写死数量：

| 变体表 | 原生成器产出 | 迁移到当前行为断言 | 退役的组合顺序探针 |
|---|---:|---:|---:|
| Config | 104 | 61 | 43 |
| ReviewItem | 93 | 55 | 38 |
| Workspace | 55 | 33 | 22 |

每行“迁移”计数包含生成器直接产出的成功与单项失败输入；本轮只退役用于发现多处错误检查先后变化的组合变体。

## 退役变体名与理由

这些输入同时包含两个或更多错误，只用于比较重构前后首错顺序 / 异常路径。它们不再对应独立的当前行为断言；单错误情况均保留在表中。

### Config（43 项）

```text
config-hard-ratio-order-probe
config-subject-field-order-probe
config-cross-root-schema, config-cross-root-policy, config-cross-root-project,
config-cross-root-subject, config-cross-root-unique, config-cross-root-no-active,
config-cross-root-weights, config-cross-root-minimums, config-cross-root-floor-room,
config-cross-schema-policy, config-cross-schema-project, config-cross-schema-subject,
config-cross-schema-unique, config-cross-schema-no-active, config-cross-schema-weights,
config-cross-schema-minimums, config-cross-schema-floor-room,
config-cross-policy-project, config-cross-policy-subject, config-cross-policy-unique,
config-cross-policy-no-active, config-cross-policy-weights, config-cross-policy-minimums,
config-cross-policy-floor-room, config-cross-project-subject, config-cross-project-unique,
config-cross-project-no-active, config-cross-project-weights, config-cross-project-minimums,
config-cross-project-floor-room, config-cross-subject-unique, config-cross-subject-no-active,
config-cross-subject-weights, config-cross-subject-minimums, config-cross-subject-floor-room,
config-cross-unique-no-active, config-cross-unique-weights, config-cross-unique-minimums,
config-cross-unique-floor-room, config-cross-weights-minimums, config-cross-weights-floor-room
```

### ReviewItem（38 项）

```text
review-category-order-probe, review-date-order-probe, review-identity-order-probe,
review-cross-unknown-identity, review-cross-unknown-category, review-cross-unknown-minutes,
review-cross-unknown-dates, review-cross-unknown-schedule, review-cross-unknown-defer,
review-cross-unknown-feedback, review-cross-unknown-vocabulary,
review-cross-identity-category, review-cross-identity-minutes, review-cross-identity-dates,
review-cross-identity-schedule, review-cross-identity-defer, review-cross-identity-feedback,
review-cross-identity-vocabulary, review-cross-category-minutes, review-cross-category-dates,
review-cross-category-schedule, review-cross-category-defer, review-cross-category-feedback,
review-cross-category-vocabulary, review-cross-minutes-dates, review-cross-minutes-schedule,
review-cross-minutes-defer, review-cross-minutes-feedback, review-cross-dates-schedule,
review-cross-dates-defer, review-cross-dates-feedback, review-cross-dates-vocabulary,
review-cross-schedule-defer, review-cross-schedule-feedback, review-cross-schedule-vocabulary,
review-cross-defer-feedback, review-cross-defer-vocabulary, review-cross-feedback-vocabulary
```

### Workspace（22 项）

```text
double-error-schema-before-schema_version, double-error-schema-before-subjects,
double-error-schema-before-reference, double-error-schema-before-supplementary,
double-error-schema-before-materials, double-error-schema-before-products,
double-error-schema-before-settings, double-error-schema-before-state,
double-error-schema-before-staging, double-error-schema-before-projection,
subject-before-reference, knowledge-before-syllabus, syllabus-before-exam-indexes,
exam-indexes-before-paper-shapes, paper-shapes-before-weight-path,
reference-before-supplementary, supplementary-before-materials, materials-before-products,
products-before-settings, settings-before-state, state-before-staging, staging-before-projection
```

## 第 207 轮零散测试

`tests.test_contracts.ReviewItemContractTest.test_revision_boolean_is_rejected` 和 `tests.test_contracts.ReviewItemContractTest.test_required_review_and_schedule_fields_cannot_be_omitted` 已由 `tests.test_contracts.ReviewItemContractTest.test_single_error_variant_table` 覆盖，故删除两条重复方法。`tests.contract.test_workspace.WorkspaceContractTests.test_required_top_level_blocks_cannot_be_omitted` 已由 `tests.contract.test_workspace.WorkspaceContractTests.test_single_error_variant_table` 覆盖，故删除重复方法。三个表保留一套表驱动写法。

## 源码变异证明

变异探针脚本在系统临时目录 `round209_variant_mutation_probe.py` 创建并运行，完成后删除；其中每个变异都复制工作区 `ky/` 到独立临时目录，把副本放到 `sys.path` 前端后导入正规测试模块。未修改仓库中的 `ky/`，未在测试侧 patch 被测函数。

实际调用命令（脚本创建后）：

```powershell
py -3.12 $probePath project
py -3.12 $probePath quality
py -3.12 $probePath workspace
```

| 探针 | 临时 `ky/` 源码变异 | 被测整表 / 失败变体 | 结果 |
|---|---|---|---|
| project | `validate_config` 将 `project_id` 先转为 `str()` 再校验 | `tests.contract.test_config_port.ConfigFormatTests.test_single_error_variant_table`；`config-project-id-type` 不再抛异常 | 测试失败，`PROJECT_MUTANT_CAUGHT=True` |
| quality | `_review_item_feedback` 的 `last_quality` maximum 从 5 改为 6 | `tests.test_contracts.ReviewItemContractTest.test_single_error_variant_table`；`review-last-quality-over-range` 不再抛异常 | 测试失败，`QUALITY_MUTANT_CAUGHT=True` |
| workspace | `_parse_paper_shapes` 对 list 输入返回空映射 | `tests.contract.test_workspace.WorkspaceContractTests.test_single_error_variant_table`；`paper-shapes-type` 不再抛异常 | 测试失败，`WORKSPACE_MUTANT_CAUGHT=True` |

三个探针均由对应 `assertRaises(ContractError)` 失败捕获，退出码为 0 表示探针确认变异被测试抓住。临时副本分别位于 `TemporaryDirectory(prefix='round209-')` 并在退出时清理。

## 验收

实际命令：

```text
py -3.12 -m unittest tests.contract.test_config_port tests.test_contracts tests.contract.test_workspace
```

输出原文：

```text
....................................................................................................s...............
----------------------------------------------------------------------
Ran 117 tests in 1.415s

OK (skipped=1)
```

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。未提交。
