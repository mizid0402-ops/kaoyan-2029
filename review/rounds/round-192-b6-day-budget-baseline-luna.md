# 第 192 轮：B6 day-budget 固定基线漏改

日期：2026-09-30  
窗口：luna-b 续做

## 修改

仅修改 `tests/contract/test_day_budget_port.py` 和本报告。

- 新增旧版配置视图：`default_daily_minutes` 不进入 dataclass fields；由 `total_daily_minutes` 替代。为当前的共享
  schedule/availability 辅助函数提供同值的非字段访问器，因此 `dataclasses.asdict()` 仍是旧模型形状。
- 固定旧版 `_build_input_data` 收到该旧视图。序列化前只在旧数据包的顶层与 `config` 映射内改名预算键；新版
  `new_data` 未归一化，直接比较。

## 调用点盘点

按任务书执行：

```text
git grep -ln "_build_input_data\|planner_input_data\|git", "show" -- tests
```

命中 4 个测试文件，逐一结论：

- `tests/contract/test_availability_port.py`：固定旧 planner `_build_input_data` 收到 `_LegacyConfigView(...).as_dataclass()`；
  已是旧字段视图。
- `tests/contract/test_day_budget_port.py`：此前将当前 `self.config` 直接传给固定旧 `_build_input_data`，是本轮漏改点；
  现已使用只含旧 dataclass 字段的视图。
- `tests/contract/test_freeze_port.py`：固定旧 planner `_build_input_data` 使用 `_LegacyConfigView(...).as_dataclass()`；
  已是旧字段视图。
- `tests/contract/test_planner_port.py`：固定旧 planner `_build_input_data` 使用 `_LegacyConfigView(...).as_dataclass()`；
  已是旧字段视图。

未发现其他测试文件将当前 `KaoyanConfig` 直接交给固定旧 `_build_input_data`。本轮未导入其他测试模块的私有辅助名。

建议：后续可把重复的旧 `KaoyanConfig` 测试适配器提取到共享测试支持模块；本轮按要求不做。

## 撤实现验证

临时从 `_LegacyConfigView.as_dataclass()` 移除 `total_daily_minutes` 赋值后，执行：

```text
py -3.12 -m unittest tests.contract.test_day_budget_port.DayBudgetPortContractTests.test_unconstrained_clipping_matches_fixed_baseline_bytes -q
```

结果：失败，两个子场景 `route_registered=False/True` 均报：

```text
TypeError: LegacyConfig.__init__() missing 1 required positional argument: 'total_daily_minutes'
```

恢复赋值后再次核对 SHA-256，与变异前一致：

```text
095DCE4A5357C9BE1718D41C1D74B9A8DC6961840FB2179B282D9C25C5746B4B
```

## 验收

执行命令：

```text
py -3.12 -m unittest tests.contract.test_day_budget_port tests.contract.test_planner_port
```

输出：

```text
Ran 40 tests in 18.465s

OK
```

`git diff --check` 通过；本次改动文件已检查编码完整性。

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。未提交。
