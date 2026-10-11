# 第 284 轮：ICS DURATION 契约错误修复

## 改动

- `ky/timetable_io/ics_import.py:79-86`：捕获 `DURATION.dt` 的解码异常，抛带
  `UID <uid>.DURATION` 路径的 `ContractError`；注释追溯 M29 / sol 281 M1。
- `ky/__main__.py:2031-2036`：将契约错误处理放到 `ValueError` 前；`ContractError`
  继承 `ValueError`，此前被用法错误分支拦截而返回 3。
- `tests/contract/test_timetable_io_port.py:985-998`：新增唯一回归用例，断言类型、字段路径
  和无暂存 YAML 发布。

## 复现输出

输入为任务书给出的 `UID:cut-duration`、`DURATION:PT45`。修复前（第 281 轮复现记录）：

```text
exit: 3
Cannot access 'dt' on broken property 'DURATION'
staged: 0
```

修复后运行任务书 CLI 命令；临时 ICS / 注册表由脚本创建，并断言退出 2、错误含字段路径：

```text
exit: 2
stdout:
stderr: contract violation: UID cut-duration.DURATION: invalid duration property
staged: 0
```

## 验收

```text
py -3.12 -m unittest tests.contract.test_timetable_io_port
Ran 42 tests in 5.383s
OK

py -3.12 -m unittest tests.contract.test_timetable_port
Ran 18 tests in 2.252s
OK
```

行为检查：缺 `DURATION`、同时有 `DTEND` 与 `DURATION` 的既有分支未改；解码为非正
时长（负值、零值及 `P0D`）仍由原 `result <= timedelta(0)` 检查拒绝。本轮未对这些形态
另跑探针，结论依据未改动的代码分支。

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。

怀疑受影响但未跑的模块：无；指定的 M29 / M18 契约模块及 CLI 复现均已覆盖。

未做 / 不确定：负值的具体 ICS 序列化是否由依赖库解码为负 `timedelta`，本轮未单独探测。
