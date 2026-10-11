# 任务书：B6 漏改的一个基线测试（窗口 `luna-b` 续做）

决策者提交前全量：`Ran 924 tests`，`FAILED (errors=2)`，两条都是
`tests/contract/test_day_budget_port.py::DayBudgetPortContractTests::test_unconstrained_clipping_matches_fixed_baseline_bytes`
（`route_registered=False/True` 两个子场景），日志 `logs/fullsuite/full-20260930-000247.log`：

```text
File "tests\contract\test_day_budget_port.py", line 154
    old_data = baseline_module._build_input_data(DAY, self.config, load_workspace(workspace_path))
File "planner_port_baseline.py", line 69, in _build_input_data
AttributeError: 'KaoyanConfig' object has no attribute 'total_daily_minutes'. Did you mean: 'default_daily_minutes'?
```

这个文件不含 `total_daily_minutes` 字样，所以第 185 轮的 `git grep` 没找到它；它和 `test_planner_port.py` 一样把当前配置对象喂给固定旧版
`_build_input_data`。

## 要改

只改 `tests/contract/test_day_budget_port.py`：照你在 `test_planner_port.py` 里第 190 轮定稿的做法——给旧版喂**只有旧字段**的配置视图，
比较前**只对旧版一侧**把输入包里的预算键改名（顶层与 `config` 映射里的那一个键），新版原样比较。尽量复用同一形状的辅助，
但**不要** import 另一个测试模块的私有名；若两处辅助完全相同，可在报告"建议"里提议提到共享测试辅助模块，本轮不做。

再用下面的方法确认没有别的漏网：
`git grep -ln "_build_input_data\|planner_input_data\|git\", \"show\"" -- tests`，逐个检查凡是把**当前** `KaoyanConfig` 对象交给**旧版**代码的地方，
报告里列出检查过的文件与结论。

## 撤实现验证

让旧版视图漏掉旧字段，确认该测试变红；报告写命令与结果。

## 不做的

不改 `ky/`、`contracts/`、其它测试；不跑全量。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_day_budget_port tests.contract.test_planner_port
```

## 报告

`review/rounds/round-192-b6-day-budget-baseline-luna.md`。写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。
