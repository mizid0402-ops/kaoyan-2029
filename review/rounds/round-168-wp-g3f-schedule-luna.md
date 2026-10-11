# WP-G3f：`ky/schedule/` 大函数拆分报告

## 拆分结果

本轮只改了五个 `ky/schedule/` 模块，并新增 `tests/contract/test_schedule_split_baseline.py`。原有五个指定测试文件未改断言。AST 扫描 `ky/schedule/*.py` 后，当前没有超过 60 行的函数。

### `review_clip.py`

- `select_daily_reviews`（48 行）：保留入口校验和原调用顺序，组织容量计算、两条选择路径、计划状态分类、结果构造及返回前会计检查。
- `_validate_subject_review_quotas`（13 行）：先校验科目是否激活及分钟值类型/范围，保证后续算术不会吞掉契约路径错误。
- `_daily_review_capacity`（14 行）：计算软目标、硬上限、不可调度上限，并按原规则拒绝超过硬上限的配额总和。
- `_select_without_subject_quotas`（27 行）：独立执行非配额选择循环。
- `_select_with_subject_quotas`（34 行）：组织配额候选、两阶段选择并恢复原排名顺序。
- `_select_subject_quota_pass`（23 行）：按紧急项优先、常规项随后，在各自科目配额内选择。
- `_select_urgent_quota_overflow`（17 行）：使用剩余硬上限选择等待中的紧急项。
- `_classify_scheduled_reviews`（12 行）：将计划项分成 scheduled-ahead 与 unreachable。
- `_build_clip_result`（31 行）：按原字段和值构造 `ClipResult`。
- `_assert_review_accounting`（12 行）：保留 `expected - accounted` 不变量检查，并在入口返回前调用。

### `monthly_close.py`

- `close_month`（42 行）：组织月份边界、日期去重、汇总、残量、完成事件和最终违规赋值。
- `_deduplicate_month_plans`（18 行）：每个日期保留输入中第一份计划，其余逐日期记录 violation；返回值按日期排序。
- `_accumulate_month_plans`（29 行）：仅对去重且排序后的计划累计各项总量与逐日不变量违规。
- `_record_month_residue`（14 行）：记录闲置时间及原有超量、积压、无计划提示。
- `_record_month_completions`（24 行）：汇总月内完成事件，并保持 delivered/practiced 分开统计。

### `longitudinal.py`

- `check_invariants`（44 行）：按既有顺序调用预检与五项不变量检查。
- `_check_weight_closure`（11 行）：保留原先最先执行的活动科目权重闭合检查。
- `_check_nonnegative_quantities`（11 行）：不变量 1，逐项检查数量字段非负。
- `_check_subject_attribution`（16 行）：不变量 2，检查科目归属和知识分钟合计。
- `_check_weight_inversions`（17 行）：不变量 3，逐对检查权重与分钟倒置。
- `_check_single_item_bounds`（17 行）：不变量 4，检查知识、词汇和短语单项上限。
- `_check_day_capacity`（7 行）：不变量 5，检查总分配是否超过可用分钟。

### `state_snapshot.py`

- `build_snapshot`（39 行）：先校验输入源和 workspace 科目，再构建科目行、日期差和词汇摘要。
- `_validate_snapshot_sources`（18 行）：先保留“无数据源”检查，再检查科目是否登记。
- `_snapshot_subject`（27 行）：按显式 `tree_paths` 或 workspace 登记路径构造一个科目快照。
- `_snapshot_subjects`（17 行）：先统计 review items，再按配置科目顺序构造快照行。
- `_snapshot_vocabulary`（16 行）：保持显式 `vocab_db` 优先于注册表的行为，并沿用原词汇启用条件。

### `completion.py`

- `parse_completion_event`（15 行）：保留顶层 mapping、未知字段、schema、日期、reviews、vocab 的校验顺序。
- `_parse_review_completions`（47 行）：依次验证 reviews 列表、每项字段、版本分支和 completion ID。
- `_parse_completion_vocab`（16 行）：验证 vocab mapping 并按 delivered、practiced 顺序解析词表。

## 固定基线对照

对照测试固定从 `git show 24371ee:<文件>` 读取旧实现，并断言旧函数确实超过拆分前长度下界：`select_daily_reviews >150`、`_select_with_subject_quotas >60`、`close_month >110`、`check_invariants >95`、`build_snapshot >85`、`parse_completion_event >65`。

- review 选择：使用现有 over-capacity review fixture，比较无配额、零配额、负配额、超过硬上限配额、负日预算与负配额并存等输入。返回对象按 dataclass 字段序列化比较；异常比较规范化类型名、消息和路径。
- 月结：比较同日重复计划、跨日计划、月外计划及空完成事件序列，确认首份计划计入、重复项违规和日期排序均一致。
- 不变量：比较一个同时触发多项检查的 `DayPlan` 的 `GuardResult` 字段。
- snapshot：比较显式空 `tree_paths` 与显式缺失 `vocab_db` 覆盖输入的 `StateSnapshot` 字段。
- completion：比较合法输入，以及日期/reviews/vocab 多处错误并存时的首个异常类型、消息和路径。

## 撤实现验证

将 `_select_without_subject_quotas` 临时改成 `return [], [], [], 0`。在 `PYTHONDONTWRITEBYTECODE=1` 下清理 `ky/schedule/__pycache__` 与 `tests/contract/__pycache__` 中的 `.pyc`，并执行：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; py -3.12 -c "from pathlib import Path; root=Path.cwd().resolve(); targets=[root/'ky/schedule/__pycache__',root/'tests/contract/__pycache__']; files=[p for d in targets if d.exists() and d.resolve().is_relative_to(root) and d.name=='__pycache__' for p in d.glob('*.pyc') if p.is_file()]; [p.unlink() for p in files]; print(f'cleared {len(files)} pyc files from target caches')"; py -3.12 -m unittest tests.contract.test_schedule_split_baseline
```

实际结果：`cleared 9 pyc files from target caches`；基线对照测试 `FAILED (failures=1)`，变红用例为 `test_review_selection_matches_fixed_baseline`，原版返回选择结果，新版触发会计不变量异常。之后已恢复辅助函数实现。

## 验收输出

按任务书指定命令运行：

```text
py -3.12 -m unittest tests.test_review_scheduler tests.test_monthly_close tests.test_state_snapshot tests.test_longitudinal tests.test_completion tests.contract.test_state_snapshot_counts_baseline tests.contract.test_state_snapshot_port tests.contract.test_review_clip_port
```

```text
Ran 161 tests in 4.281s

OK
```

新增固定基线测试另行运行：

```text
py -3.12 -m unittest tests.contract.test_schedule_split_baseline
Ran 5 tests in 0.285s

OK
```

语法编译、`git diff --check` 通过；本轮编辑文件未发现连续问号替代字符。验收后又只调整了异常类型比较辅助与注释；固定基线测试重跑通过。全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。
