# 第 237 轮：M29 iCalendar 导入与日历导出

## 改动

- `pyproject.toml`：加入 `icalendar>=7,<8`、`python-dateutil>=2.8,<3`、`tzdata`。
- `ky/timetable_io/ics_import.py`：实现 ICS 读取、UID 分组、VEVENT 过滤、有限 RRULE 展开、EXDATE 与单实例覆盖、时区校验、本地日期域检查、节次对回、周次分组、M18 引用校验及暂存发布。
- `ky/timetable_io/ics_export.py`：从 M18 日历生成浮动时间事件；按大节和 free segment 正长度交集切分课程；生成稳定 UID、排序与 DTSTAMP；隔离检查后用临时文件和硬链接发布，拒绝覆盖。
- `ky/timetable_io/preview.py`：提供公开 `preview_lines(workspace, semester, config_path=None)`，输出候选学期第 1 周网格；仅在个人课表和配置都可用时附每日分钟。`import-ics` 调用此入口。
- `ky/timetable_io/__init__.py`：从包入口导出 `import_ics`、`export_ics`、`preview_lines`。
- `ky/__main__.py`：增加 `import-ics` 与 `export-ics` 参数和退出码处理。
- `tests/contract/test_timetable_io_port.py`：加入合成 ICS 导入、规则、覆盖、时区、导出确定性、切段、隔离和 CLI 测试。

未修改 PDF 适配器、注册表、个人数据或 IO1 的其他实现文件。

## 主要处理

- ICS 输入只读一次；解析器与 `source.sha256` 使用同一份原始字节。暂存发布复用 IO1 的 `publish_staging`，每条命令只检查一次隔离状态。
- 周次比较按目标时区本地日期。浮动时间保留原墙上时间；UTC / TZID 值要求明确的目标 IANA 时区，TZID 本身也必须能由 `ZoneInfo` 解析。节次端点精确对照，秒不会被截断。
- 只接受单次事件和有限规则的 `WEEKLY`（`INTERVAL`、`BYDAY`、`UNTIL` 或 `COUNT`）及 EXDATE。无终止规则必须给 `--weeks`；规则自然投影出的域外额外实例会截去并留备注。覆盖移出域外仍拒绝。取消覆盖移除原实例；移动覆盖使用新日期分组；孤立、重复覆盖、`THISANDFUTURE`、覆盖自带 RRULE / EXDATE 均拒绝。
- `DTEND` 按各重复实例的开始时间加主事件时长计算；`DURATION` 可替代 `DTEND`。两者并存、起止类型不一致或倒置均拒绝。全天、取消、缺少结束时间及跨本地日事件按规格过滤并写入 notes；若没有可导入课程则拒绝发布。
- 导出每天都读取 M18 的完整 `DaySchedule`，包括 `--classes-only`。课程相邻节只有在同一大节且间隙没有与 M18 `free_segments` 正长度相交时合并；空闲事件按各段时长标注。UID 的 index 在相同身份组内分配，因此选择过滤不改变课程 UID。空选择会写合法空日历，完全无覆盖日期则拒绝且不写文件。

## 测试覆盖

新增合成用例覆盖单次导入、WEEKLY COUNT / INTERVAL / BYDAY / UNTIL、单个与多个 EXDATE、取消和移动覆盖、覆盖移出域外、UTC 前一日按目标本地日期接收、浮动时间、有无时区参数、未知 TZID、秒级不匹配、DURATION 重复展开、DTEND 与 DURATION 并存、RDATE / 非 WEEKLY 拒绝、全天 / 跨日 / 缺结束时间备注、重复课程身份拒绝与不同课程名并存。

导出用例覆盖可重复字节、浮动事件、同一身份组重复课程 UID、classes-only 与完整导出的课程 UID 稳定、大节内长空档分段、有覆盖但选择结果为空、未覆盖范围不写、已有目标不覆盖及仓库内未忽略目标拒绝。CLI 用例覆盖导入重复运行成功、导出成功和反向日期用法错误。

## 依赖安装

执行命令：

```text
py -3.12 -m pip install "icalendar>=7,<8" "python-dateutil>=2.8,<3" tzdata
```

安装成功：`icalendar 7.3.0`；`python-dateutil 2.9.0.post0` 与 `tzdata 2026.2` 已满足要求。

## 验收

实际命令：

```text
py -3.12 -m unittest tests.contract.test_timetable_io_port tests.contract.test_timetable_port tests.test_cli
```

验收输出原文：

```text
Ran 107 tests in 57.635s

OK (skipped=1)
```

`git diff --check` 通过。修改的 Python 文件行宽均不超过 100 字符；函数均不超过约 60 行。全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。

## 歧义与选择

- `--timezone` 按规格仅在输入含 UTC / TZID 日期时间时必需；纯浮动时间即使提供目标时区也保持墙上时间。未把浮动值猜成 UTC。
- “可学习 N 分钟”按每一个输出 `free_segment` 自身的时长计算，因为规格要求每段单独成为事件。
- 一个无终止 RRULE 写一条截断备注；如果多个规则被截断，则每条规则各写一条，即使备注文本相同。
- 已有规则未规定的 RFC 5545 扩展（包括 `RDATE`、非 WEEKLY 频率）采用明确拒绝，未忽略后继续导入。

## 第 248 轮返工

### 改动与处理

- `ky/timetable_io/preview.py`：`preview_lines` 新增可选 `schools: Mapping[str, LoadedSchool] | None`；有传入对象时复用它，独立预览时才加载学校。网格行恢复 `unconfirmed` 节次的 `*` 标记；`base_resolver` 参数标注为 `KaoyanConfig`。
- `ky/timetable_io/ics_import.py`：先按 UID 分组、识别排除主事件及其覆盖事件，再对活动主事件和覆盖事件校验 `DTSTART`、`DTEND`、`RECURRENCE-ID` 与每个 `EXDATE` 的 TZID / 时区；导入预览传入已加载学校映射。删除未使用的 `school_id = None`。原时间身份键保留值类型；`DTSTART` / `DTEND` 浮动与带时区类型混用时抛出带 UID、字段路径的 `ContractError`。节次端点错误延后统一收集 UID、字段、日期、时刻，再一次性违约，因而不会进入暂存发布。
- `ky/timetable_io/zfsoft_pdf.py`：预先加载的学校映射传入公用预览，避免重复读取档案。
- `ky/timetable_io/ics_export.py`：删除 `_publish` 中重复的父目录创建；唯一一次 `mkdir` 留在 I/O 转契约错误的 `try` 内。
- `tests/contract/test_timetable_io_port.py`：增加学校只读一次、PDF 预览复用与 `*`、路由分阶段逐日基数且路线只读一次、排除事件时区顺序、EXDATE 未知 TZID、有效 TZID、混合起止时间域、边界错误汇总且不暂存、多个独立单次事件合并、孤立 / `THISANDFUTURE` / 重复覆盖 / EXDATE 冲突、空导入不发布、重复导入不改暂存字节且第二次未发布、导出 `TRANSP` / `CATEGORIES` / 浮动时间等合成用例。

### 验收

指定的完整命令：

```text
py -3.12 -m unittest tests.contract.test_timetable_io_port tests.contract.test_timetable_io_zfsoft_pdf tests.contract.test_timetable_port tests.test_cli
```

完整命令首轮在约 30 秒时工具先返回了尚未结束的进度 ` .E...............F....E...E..............s...`；等待完整命令结束后的输出如下。新增用例的断言与夹具问题修正后，完整命令的四个模块里只有 `test_timetable_io_port` 被改动，因此按 AGENTS.md 只重跑该模块。

完整命令（修正前）结束输出原文：

```text
......................E...................s.........................................................................................
======================================================================
ERROR: test_independent_single_events_merge_and_school_is_read_once (tests.contract.test_timetable_io_port.TimetableIOIcsTests.test_independent_single_events_merge_and_school_is_read_once)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "F:\workspace\kaoyan-ai-system\tests\contract\test_timetable_io_port.py", line 1124, in test_independent_single_events_merge_and_school_is_read_once
    self.assertEqual(staged.semester.courses[0].weeks, frozenset({1, 2, 3}))
                     ^^^^^^^^^^^^^^^
AttributeError: 'tuple' object has no attribute 'semester'

----------------------------------------------------------------------
Ran 132 tests in 79.276s

FAILED (errors=1, skipped=1)
```

修正后受影响模块命令及输出原文：

```text
py -3.12 -m unittest tests.contract.test_timetable_io_port
.......................................
----------------------------------------------------------------------
Ran 39 tests in 5.019s

OK
```

完整命令运行中 `test_timetable_io_zfsoft_pdf`、`test_timetable_port`、`test_cli` 均通过；修正后的 `test_timetable_io_port` 也通过。连续问号检查无命中，改动 Python 文件均无超过 100 字符的行。全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。

### 歧义与选择

- 排除取消 / 全天 / 无结束时间的主事件时，其覆盖事件不做时区检查，并保留“已排除主事件的覆盖”备注；其余事件的 EXDATE 每个值继承并校验其属性上的 TZID。实例身份仍要求值类型一致。
- 同一事件起止时间一个浮动、一个带时区时，统一作为 `UID <id>.DTEND` 契约错误；不尝试推测缺失时区。
- 节次起点或终点对不上时均收集；若已能确定两端点且起点节次大于终点，也作为同一汇总类错误记录，不逐条提前中断。
