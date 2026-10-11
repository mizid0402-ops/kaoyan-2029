# 第 285 轮：图表数据端口参数护栏

## 改动

- `ky/charts/data.py:24`：`week_chart_data` 先检查 `days`，拒绝 `None`，路径为 `week.days`。
- `ky/charts/data.py:209`：`progress_chart_data` 先检查 `start`，拒绝 `None`，路径为 `progress.start`。
- `ky/charts/data.py:284`：`ability_chart_data` 先检查 `today`，拒绝 `None`，路径为 `ability.today`。
- 三处均抛 `ContractError`；数据映射生成逻辑未改，合法输入走原有计算。
- `tests/contract/test_charts_port.py:155`：新增三端口 `None` 输入断言错误类型和路径。

## 规格依据

- M17 `contracts/charts.md` §3 规定周图数据为周一至周日 7 天；`days=None` 不合法。
- §4.5 将进度区间映射为 `from: ISO`，纯函数接收已加载对象；`start=None` 不合法。
- §8 能力图 `today` 写入映射，且 T 缺省当天是页面/CLI语义；纯函数不以 `None` 表示缺省。
- 因此三个 `None` 都不是“未登记”语义，不允许透传至后续运算。

## 探针

修复前：

- `week.days=None` → `TypeError: 'NoneType' object is not iterable`
- `progress.start=None` → `TypeError: fromisoformat: argument must be str`
- `ability.today=None` → `AttributeError: 'NoneType' object has no attribute 'isoformat'`

修复后：

- `week.days=None` → `ContractError: week.days: expected seven day rows`
- `progress.start=None` → `ContractError: progress.start: expected a date`
- `ability.today=None` → `ContractError: ability.today: expected a date`

## 验收

- `py -3.12 -m unittest tests.contract.test_charts_port`：

  ```text
  Ran 7 tests in 0.663s

  OK
  ```

- `py -3.12 -m unittest tests.contract.test_mastery_port`：

  ```text
  Ran 6 tests in 0.002s

  OK
  ```
- 全量：未跑（按 `AGENTS.md`）。
- 怀疑模块：无；本改动仅涉及 M17 图表数据端口。
- 未做：render、CLI 装配、M30 端口和“建议改”项均未改。
