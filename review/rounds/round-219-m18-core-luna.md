# 第 219 轮：WP-T1 M18 课表核心

> 决策者注（2026-09-30）：本报告所述 `timetable_for_workspace(workspace, config)` 与可选 `base_minutes`
> 已由决策者按规格改为 `timetable_for_workspace(workspace)`、`base_minutes` 必填；真实数据用例的固定数值
> 已按第 224 轮 R3 改为通用不变量。以当前代码与 `contracts/timetable.md` 为准。

## 改动文件

- `ky/timetable/__init__.py`：M18 包入口，只导出公开类型和函数。
- `ky/timetable/_common.py`：UTF-8 YAML 读取、重复键检测、字段/标量校验；摘要由解析时读取的同一字节计算。
- `ky/timetable/_models.py`：不可变的学校、课表、学期、课程、例外和每日结果类型。
- `ky/timetable/school.py`：按 §2 校验学校档案，包括字段、编号、时刻、别名和大节覆盖。
- `ky/timetable/weeks.py`：按周次表达式的逐项解析、越界检查、奇偶过滤、空集检查和两两不相交顺序校验。
- `ky/timetable/timetable.py`：按 §3 校验课表字段、规则、学期、课程和例外；保留允许课程冲突的规则。
- `ky/timetable/calendar.py`：工作区加载、引用学校 fail-closed 校验、同文件只读一次、来源摘要及 §4 计算；日历方法可接收逐日基数，未传时使用初始化时配置的默认基数。
- `ky/workspace.py`：加入 `reference.timetable_schools` 映射与 `state.timetable` 文件目标，并提供只读学校映射、`require` 与 `write_target` 行为。
- `contracts/workspace.md`：同步 §2 注册表示例、§2.1 字段表、§4 写入目标及 §6 `Workspace` 字段。
- `tests/contract/test_timetable_port.py`：学校/课表字段拒绝、周次表达式、例外、计算、follow、注册引用、字节摘要及仓库真实数据用例。
- `tests/contract/test_workspace.py`：补充学校 ID、路径、不可变映射、`require` 和课表写入目标用例。

没有修改 `ky/availability/`、`ky/schedule/`、`ky/__main__.py`、`ky/planner/`、`ky/freeze/`、
`docs/模块地图.md`、`kaoyan.workspace.yaml`、真实数据文件或 `tools/`。本轮按任务书只在临时
Workspace 对象里登记并读取仓库中的真实课表与学校档案，未改仓库注册表。

## 规格实现要点

- 学校档案与个人课表按各自 schema 精确限制必填/可选/未知字段；整数校验排除布尔和浮点，日期及时刻不做隐式转换。
- 周次表达式由具名小函数分阶段验证；验证次序先界限、后奇偶过滤，并拒绝过滤空集与展开重叠。
- 每次加载只读课表和每所引用学校一次；解析与 SHA-256 使用同一份原始字节。未引用学校不读取。缺失登记、无效文件、学校 ID 不匹配或节次缺失均 fail-closed，并按规格路径报错。
- `TimetableCalendar` 与结果对象为不可变数据；来源映射和学校节次映射只读。`b` 按原始节次集合和档案大节划分计算，与学习窗及缓冲无关。
- 真实数据的唯一固定数值验收在 `test_repository_timetable_and_school_real_data` 中，基数为 120；该组数值用于钉住仓库当前数据版本（AGENTS.md 第 7 条例外）。合成计算用例采用不同锚点日期。
- 注册表测试覆盖学校 ID 非法、路径语法错误、映射不可变、未登记/缺失引用、`state.timetable` 未登记及其目标类型检查。

## 规格歧义与采用选择

- §7 的类方法签名写有逐日 `base_minutes`，而任务书明确要求构造函数 `timetable_for_workspace(workspace, config)`。实现保留任务书的 config 参数，并让 `day`、`minutes_for`、`minutes_between` 接受可选的逐日基数；调用方未传时回落到 config 的默认值。这使下一包能传入当日基数，同时保留本轮配置默认行为。
- §7 未明确 `minutes_between` 的反向区间处理。实现将 `end_exclusive < start` 作为 `ContractError`（路径 `end_exclusive`）；相等端点返回空映射，符合半开区间定义。

## 验收

实际命令：

```text
py -3.12 -m unittest tests.contract.test_timetable_port tests.contract.test_workspace
```

输出原文：

```text
....................s..................
----------------------------------------------------------------------
Ran 39 tests in 1.293s

OK (skipped=1)
```

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。
