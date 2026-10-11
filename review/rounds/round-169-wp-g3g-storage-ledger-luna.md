# WP-G3g 存储、台账、冻结拆分报告

## 拆分结果

只把长函数拆成具名辅助函数，未有意改变返回值、错误消息、异常类型、`.path`、顺序或写入内容。

| 文件 / 函数 | 基线长度 | 当前长度 | 辅助函数与职责 |
|---|---:|---:|---|
| `ky/storage/review_shards.py::_commit` | 114 | 23 | `_read_previous_groups` 读取现有分组；`_prepare_commit_plan` 计算分片描述和报告差异；`_record_removed_shards` 记录已移除分片；`_build_commit_manifest` 生成清单对象及字节；`_publish_commit` 执行原发布流程。`_CommitPlan` 保存准备阶段产物。 |
| `ky/storage/day_plan_store.py::write_day_plan` | 63 | 11 | `_check_day_plan_before_write` 按原顺序执行不变量、可用时间和冻结护栏；`_commit_day_plan` 完成版本、文件和 manifest 写入。 |
| `ky/ledger/material.py::validate_material` | 131 | 55 | `_load_material_schema_version` 校验 schema；`_load_material_subjects` 校验科目；`_load_material_provenance` 解析来源；`_validate_material_origin` 校验来源与存储关系。字段校验调用顺序保持不变。 |
| `ky/ledger/material.py::_load_rights` | 72 | 31 | `_validate_rights_permissions` 集中执行原有权限矛盾检查；缺失、类型、未知键和权限检查顺序保持不变。 |
| `ky/ledger/citations.py::check_knowledge_point_citations` | 102 | 37 | `_citation_rejection` 对单条引用按原拒绝理由顺序返回首个拒绝结果。 |
| `ky/freeze/resume.py::plan_resume` | 62 | 38 | `_assign_overdue_items` 计算逾期层级及分配日期，保留 D11 的“逾期天数大于当前间隔”边界和摊开顺序。 |
| `ky/acquisition/ledger_restore.py::restore_materials` | 66 | 19 | `_restore_material` 处理单行恢复及状态；外层保留逐行顺序。`--check` 仍不建临时目录，畸形 URL 仍在单行内处理。 |

### 超长函数扫描

改动前扫描了 `ky/storage/`、`ky/ledger/`、`ky/freeze/`、`ky/projection/`，并单独检查任务表中的 `ky/acquisition/ledger_restore.py`。超过 60 行的函数只有上表七个，没有额外项。改动后对这些目录及该恢复文件重新做 AST 行数扫描，超过 60 行的函数为 0。

### `_commit` 的基线事实

任务提醒提到 `os.link` 发布、临时文件身份复核及只清理本次发布文件。核对固定基线 `24371ee` 后，发现该提交中的 `ReviewShardStore._commit` 实际使用 `os.replace` 发布，并在失败清理中按已有 `final_paths` 删除；没有上述 `os.link` / 身份复核逻辑。已保留基线中的真实实现，避免把纯拆分变成行为修复。若要求这些保护，应另开修复任务；本报告不把它们记为本轮已满足的性质。

## 固定基线对照

新增 `tests/contract/test_storage_ledger_split_baseline.py`。测试从 `git show 24371ee:<文件>` 读取每个旧文件，并通过 AST 长度下界断言取到的是拆分前的长函数，然后在同组输入下比较：

- `_commit` 两次提交的 manifest、报告字段及存储树原始字节，覆盖新增分片和移除分片。
- `write_day_plan` 的摘要、版本、相对路径及存储树原始字节。
- `validate_material` 的数据类字段；rights 缺失、类型错误、未知键错误的异常类型、消息和 `.path`。
- 引用检查的摘要及拒绝理由顺序。
- `restore_materials` 每行结果与状态，覆盖 `--check` 不创建临时目录、畸形 URL 单行处理。
- `plan_resume` 的旧新逐项结果，并单独钉住逾期恰等于间隔与大于间隔一天时的 D11 分层。

命令：

```text
py -3.12 -m unittest tests.contract.test_storage_ledger_split_baseline
Ran 6 tests in 0.503s
OK
```

## 定点变异验证

每次变异前清理了作用目录中的 `.pyc` 和 `__pycache__`，运行时设置 `PYTHONDONTWRITEBYTECODE=1`，每项验证后恢复实现。

| 变异 | 实际命令 | 实际结果 |
|---|---|---|
| `_commit` 的移除分片报告值改为常量字符串 | `$env:PYTHONDONTWRITEBYTECODE='1'; py -3.12 -m unittest tests.contract.test_storage_ledger_split_baseline.StorageLedgerSplitBaselineTests.test_review_shard_commit_matches_fixed_baseline` | 退出码 1；基线 `new_hashes` 对应值为 `None`，变异值为 `removed`，固定基线比较失败。 |
| 删除 `validate_material` 的 `return provenance` | `$env:PYTHONDONTWRITEBYTECODE='1'; py -3.12 -m unittest tests.contract.test_storage_ledger_split_baseline.StorageLedgerSplitBaselineTests.test_validate_material_matches_fixed_baseline_and_error_paths` | 退出码 1；出现 `AttributeError: 'NoneType' object has no attribute 'source_url'`。 |
| 改变引用拒绝顺序：把 withdrawn 检查改为 rights 检查 | `$env:PYTHONDONTWRITEBYTECODE='1'; py -3.12 -m unittest tests.contract.test_storage_ledger_split_baseline.StorageLedgerSplitBaselineTests.test_citation_results_match_fixed_baseline_in_rule_order` | 退出码 1；同一项由旧实现的 withdrawn 拒绝变成存储字节缺失拒绝，报告不相等。 |
| 将恢复行的 `needs_download` 状态改为 `already_verified` | `$env:PYTHONDONTWRITEBYTECODE='1'; py -3.12 -m unittest tests.contract.test_storage_ledger_split_baseline.StorageLedgerSplitBaselineTests.test_restore_material_rows_match_fixed_baseline` | 退出码 1；逐行对照显示旧状态 `needs_download`、变异状态 `already_verified`。 |
| 把可用时间检查移到不变量错误之前 | `$env:PYTHONDONTWRITEBYTECODE='1'; py -3.12 -m unittest tests.contract.test_day_plan_store_port.DayPlanWriteGuardTests.test_invariants_then_availability_run_before_the_freeze_gate` | 退出码 1；错误路径由预期 `day_plan` 变成 `day_plan.available_minutes`，证明护栏顺序回归。 |
| 把 `_assign_overdue_items` 的分配日期改为当前日期 | `$env:PYTHONDONTWRITEBYTECODE='1'; py -3.12 -m unittest tests.contract.test_storage_ledger_split_baseline.StorageLedgerSplitBaselineTests.test_resume_schedule_matches_fixed_baseline_d11_boundary` | 退出码 1；固定基线在“大于间隔”样例中的分配日期与变异版不同。 |
| 删除 `_load_rights` 的未知键校验 | `$env:PYTHONDONTWRITEBYTECODE='1'; py -3.12 -m unittest tests.contract.test_storage_ledger_split_baseline.StorageLedgerSplitBaselineTests.test_validate_material_matches_fixed_baseline_and_error_paths` | 退出码 1；未知键样例从 `.rights.unknown_right: unknown field` 变为 `.rights.status: expected a non-empty string`。 |

曾先用 `tests.test_review_queue_advance` 检查“分配日期一律设为当天”的变异；该模块 18 项仍通过，说明它没有锁住此边界。随后把固定基线和 D11 边界断言加入本轮新增测试；同一变异被上表的专用用例检出。此处记录先前无效探针，避免把它误报为变异通过。

## 验收

执行任务书指定命令：

```text
py -3.12 -m unittest tests.test_ledger tests.test_ledger_cli tests.test_day_plan_store tests.test_review_queue_advance tests.contract.test_material_restore_port tests.contract.test_ledger_port tests.contract.test_citation_gate_port tests.contract.test_day_plan_store_port tests.contract.test_state_sources_port
Ran 169 tests in 4.369s
OK
```

改动后 AST 长函数扫描：`LONG_COUNT 0`。`git diff --check` 通过；对本轮修改的中文文件扫描连续问号占位符，无命中。

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）

## 留意事项与建议

- 纯拆分基线测试证明列出的调用结果与 `24371ee` 一致；它不能证明该提交原本不存在的发布保护。
- 建议另行确认 `review_shards` 的 `os.replace` / 清理行为是否需要按 sol 99/102 的发布保护要求修复，再以独立行为变更处理。
- 本轮未提交。
