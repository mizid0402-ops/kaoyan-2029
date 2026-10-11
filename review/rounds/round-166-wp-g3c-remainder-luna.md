# WP-G3c 余项拆分报告

## 六个主函数的拆分

| 主函数 | 新行数 | 拆出的函数及职责 |
|---|---:|---|
| `ledger_main` | 30 | `_ledger_reconfigure_utf8` 保留原命令的流编码设置；`_ledger_parser` 构造参数解析器；`_ledger_load_materials` 解析数据来源并读台账；`_ledger_measure` 计算完整性、结构化/证据能力集合和汇总；`_ledger_print_json` 输出 JSON；`_ledger_print_header` 输出文本头部；`_ledger_print_rights_and_capabilities` 输出权利与能力清单；`_ledger_print_integrity` 输出字节完整性。 |
| `snapshot_main` | 35 | `_snapshot_parser` 构造解析器；`_snapshot_parse_dates` 按原序解析两个可选日期，失败由主函数返回 3；`_snapshot_items` 加载注册表、队列和可选词库路径；`_snapshot_build` 生成快照；`_snapshot_print_text` 输出文本。JSON 单行输出留在主函数。 |
| `route_main` | 9 | `_route_submit_parser` / `_route_show_parser` 分别解析子动作参数；`_route_submit` 执行提交；`_route_show` 读取并格式化指定路线；`_route_print_plan` 输出文本路线。主函数只校验子动作并分派。 |
| `resume_main` | 23 | `_resume_parser` 构造解析器；`_resume_context` 读取依赖、计算恢复计划，并在返回前检查冻结日期；`_resume_without_backlog` 保留无积压时的锁存处理与输出；`_resume_write_plan` 按原顺序写队列和恢复记录；`_resume_print_plan` 选择 JSON 或文本输出。日期早于未解除冻结的拒绝仍发生在任何写入之前。 |
| `month_close_main` | 29 | `_month_close_parser` 构造解析器；`_month_close_load_inputs` 依次解析存储路径、加载配置；`_month_close_compute` 读取计划/完成事件并计算月结；`_month_close_to_mapping` 组装原有字段和顺序；`_month_close_print_text` 输出文本。 |
| `review_queue_main` | 22 | `_review_queue_parser` 构造含 `check` / `migrate` 的解析器；`_review_queue_check` 检查队列引用；`_review_queue_migrate` 规划迁移、先验证再按需写入。空映射链仍先检查目标版本与队列，之后才跳过写入。 |

新拆出的函数均不超过约 60 行；改动范围内代码行长不超过 100 字符。

## 固定基线与对照场景

新增 `CliG3cRemainderSplitBaselineTests`，固定从 `git show 24371ee:ky/__main__.py` 读取旧模块，并逐个断言六个目标函数仍达到旧实现长度下界。每个场景在同一临时目录路径上分别执行旧版和新版，比较 `(退出码, stdout, stderr)` 原始字节。

- `ledger`：注册表台账文本成功；非法台账失败。
- `snapshot`：JSON 成功；配置文件缺失失败。
- `route`：`show --json` 成功；revision 0 不存在失败。
- `resume`：空积压成功；日期早于未解除冻结失败，并对旧版与新版都断言没有恢复记录。
- `month-close`：文本成功；`--month 13` 失败。
- `review-queue`：空队列 `check` 成功；迁移起始版本未注册失败。

成功与失败共 12 个场景；JSON 与文本输出都被覆盖。科目与迁移目标版本从已有配置/注册表读取，月份年份从测试运行日期派生。

## 撤修复验证

临时将 `_snapshot_parse_dates` 改为固定 `return None`，先清理 `ky/` 与 `tests/` 下的 `.pyc`，并设置 `PYTHONDONTWRITEBYTECODE=1`。实际运行：

```text
PYTHONDONTWRITEBYTECODE=1 py -3.12 -m unittest tests.test_cli_split_baseline.CliG3cRemainderSplitBaselineTests.test_six_commands_match_fixed_baseline
```

结果：退出码 1，测试报告两个失败子场景：`snapshot-success` 新版变为退出码 3、旧版为 0；`snapshot-missing-config` 新版变为退出码 3、旧版为 2。随后恢复函数实现。

## 验收

实际命令：

```text
py -3.12 -m unittest tests.test_cli tests.test_cli_split_baseline tests.test_ledger_cli tests.test_day_plan_store
```

原始结果：

```text
Ran 86 tests in 75.597s

OK
```

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。

## 建议

按任务书保留了 `ledger` 内部的 UTF-8 stream 重配置循环；它与 `_reconfigure_streams_utf8()` 重复，后续若要统一，可另开明确允许此行为改动的任务。
