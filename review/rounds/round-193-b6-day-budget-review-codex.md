# 第 193 轮评审：B6 day-budget 固定基线漏改

## 结论

**PASS。** `test_day_budget_port.py` 现在把只有旧字段的数据类视图交给固定旧版 `_build_input_data`，只归一化旧版输入包；独立检索未发现另一个仍将当前 `KaoyanConfig` 直接交给会读取旧分钟字段的固定旧版入口。复现仅在系统临时归档中运行。全量：未跑（按 AGENTS.md）。

## 必须改

无。

## 建议改

- 四个契约测试模块各自有几乎相同的 `_LegacyConfigView`。以后若再改配置字段，可将这段测试专用适配器放入共享测试辅助模块，减少漏改机会。本轮只有 `test_day_budget_port.py` 在范围内，不为此扩改。

## 不改

- **旧版模型形状与归一化范围。** `test_day_budget_port.py::_LegacyConfigView.as_dataclass()` 从字段列表排除 `default_daily_minutes`，再加入 `total_daily_minutes`；非字段属性 `default_daily_minutes` 只返回旧字段值，以供固定旧入口调用的当前 schedule/availability 辅助函数使用。临时归档独立探针检查 `dataclasses.fields` 与 `asdict()`：旧字段存在且值 120，新字段不存在，属性访问器值也为 120。`_rename_legacy_package_keys` 仅作用于旧版 `old_data` 的顶层和 `config` 两处键；新版 `new_data` 原样进入规范 JSON 字节比较。探针给额外嵌套映射放入同名旧键，该映射保持原样，说明没有递归抹掉其它位置的差异。固定旧版 `20f4391e:ky/planner/port.py::_build_input_data` 在第 69 行直接读取 `config.total_daily_minutes`，并以 `asdict(config)` 生成 `config` 映射。
- **定点测试。** 从 `git archive d692365` 加入已审 B6 改动和本轮测试文件的系统临时归档，设置 `GIT_DIR` 与 `PYTHONDONTWRITEBYTECODE=1`，运行 `py -3.12 -m unittest tests.contract.test_day_budget_port tests.contract.test_planner_port -q`：`Ran 40 tests in 12.159s`，`OK`。其中 day-budget 的 `route_registered=False/True` 对照均实际运行。
- **撤修复变异。** 只在临时副本把固定旧入口的参数从 `_LegacyConfigView(self.config).as_dataclass()` 改回 `self.config`，运行 `py -3.12 -m unittest tests.contract.test_day_budget_port.DayBudgetPortContractTests.test_unconstrained_clipping_matches_fixed_baseline_bytes -q`：两个 route 子场景都在旧 `_build_input_data` 第 69 行报 `AttributeError: 'KaoyanConfig' object has no attribute 'total_daily_minutes'`，结果 `FAILED (errors=2)`。恢复后临时副本与工作区的 SHA-256 均为 `095DCE4A5357C9BE1718D41C1D74B9A8DC6961840FB2179B282D9C25C5746B4B`；未留下 `__pycache__`。
- **独立漏项检索。** 用 `rg` 分别找 `"show"`、`exec(compile`、`spec_from_file_location`、`load_config(`、`KaoyanConfig(`、旧入口调用，检查了所有取固定旧源码且涉及配置的测试。`test_availability_port.py`、`test_planner_port.py`、`test_freeze_port.py` 的旧 `_build_input_data` 均已用旧字段视图；本轮补上 `test_day_budget_port.py`。`test_schedule_split_baseline.py` 给旧 `select_daily_reviews` 旧名视图，其旧 `build_snapshot` 与 `test_state_snapshot_counts_baseline.py` 的旧快照函数只用 `config.subjects`；`test_storage_ledger_split_baseline.py` 的旧 `plan_resume` 直接读取的是 `review_reserve_ratio`，没有旧分钟属性。`test_cli.py`、`test_cli_split_baseline.py` 的固定旧 CLI 通过命令行运行且相应旧源码无 `total_daily_minutes` 属性访问。`test_learning_state_projection.py`、`test_projection_port.py`、`test_projection_status.py` 的固定旧投影入口收到工作区/数据库/CLI 参数，没有直接收到当前 `KaoyanConfig`。`test_models_split_baseline.py` 给旧 `validate_config` 旧键文档，已在第 191 轮审过。`test_contracts.py`、`test_review_scheduler.py` 虽被宽检索命中，但该命中不是调用固定旧源码。未发现另一个与本轮两个 ERROR 同形的调用点。

## 安全登记

本轮没有发现需按恶意输入、手工篡改或精确竞态新增登记的问题。
