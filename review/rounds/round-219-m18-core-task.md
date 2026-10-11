# 第 219 轮任务书：WP-T1 M18 课表核心 + 注册表两键（gpt-6-luna，窗口 luna-c）

## 背景

路线图 ④a 课表协同。规格已定稿：`contracts/timetable.md`（经 sol 第 217 / 218 轮审过，**以它为准**，不要自行改规则）。
本包只做 M18 本身与注册表两个新键；接入 M26 / M8 / preflight / 输入包 / resume 与 CLI 是下一包 WP-T2，**本包不碰**。

先读：`AGENTS.md`（全部，尤其 D7 可维护性、验证范围、编码规则 9–10、已知缺陷清单）、`contracts/timetable.md`、
`contracts/workspace.md`、`ky/workspace.py`、`ky/availability/port.py`（风格参照：模块头、`ContractError` 带路径、`MappingProxyType`）。

## 要做的

1. **新模块 `ky/timetable/`**（照 `ky/availability/` 的包结构：`__init__.py` 只导出公开名，实现分文件）：
   - `load_school(path)`、`load_timetable(path)`：按规格 §2、§3 全部校验（表格里每一行、编号规则每一条）。
   - `timetable_for_workspace(workspace, config)`：规格 §5、§7；只读被引用的学校、每所一次；
     `sources` 为工作区根相对 POSIX 路径 → **解析所用同一份字节**的 SHA-256（已知缺陷第 2 条）。
   - `TimetableCalendar`（`day` / `minutes_for` / `minutes_between` / `sources`）与 `DaySchedule`（字段见规格 §7 表）：规格 §4 的计算规则。
   - 模块头 docstring 写"M18、`contracts/timetable.md`、公开接口"。函数 ≤ 约 60 行、行宽 ≤ 100。
   - 周次表达式解析按规格 §3 第 3 条写成**有名字的小函数**（逐项解析 → 越界检查 → 奇偶过滤 → 空集检查 → 两两不相交），不要一条大正则吞下全部。
2. **注册表**：`ky/workspace.py` 加 `reference.timetable_schools`（映射 ID → F，可选）与 `state.timetable`（F，可选）；
   `Workspace` 加 `timetable_schools: Mapping[str, Path]`（只读）、`timetable: Path | None`；
   `require("reference.timetable_schools.<id>")`、`write_target("state.timetable")` 按 `contracts/workspace.md` §4 行为。
   同步改 `contracts/workspace.md`（§2 示例、§2.1 字段表、§4 write_target 列表、§6 接口）。
3. **不登记进仓库注册表**：`kaoyan.workspace.yaml` 本包**不改**（登记由决策者在 WP-T2 合并后做）。
   用户学校档案与个人课表（当时位于 data/ 下，现已移到 `data/personal/`，不进 git）是真实数据，**不要改**；测试可以读它们做"真实数据能加载"的用例。
4. **契约测试 `tests/contract/test_timetable_port.py`**：
   - 学校档案、个人课表各字段的拒绝用例（断言字段路径，不断言文案），至少覆盖规格 §2 / §3 每条编号规则各一例；
     时刻为整数（未加引号的 `13:30`）必须拒绝。
   - 周次表达式：sol 第 217 轮报告 §三"weeks 表达式"一节列出的全部例子（接受 / 拒绝各自如报告所述），加 `2(单)` 拒绝。
   - 计算：sol 第 217 轮报告 §三 表格的每一行作为一个用例（数值照抄报告），加 `follow` 各例（§三"follow 与学期"1–5 条）。
     注意第 217 轮报告里第 11 节相关的例子不适用（用户学校档案已删第 11 节）——用测试自建的档案。
   - `b` 只由节次集合计算（报告里"学习窗 08:00–09:00、仅周一第 9–10 节、cap=60 → 45"）。
   - 真实数据：用临时工作区登记两份真实文件，断言若干日期的推算分钟（具体日期与数值为个人数据，提交前已脱敏；
     第 224 轮 R3 起该用例只断言通用不变量，数值计算由合成用例覆盖）。
   - 注册表：`reference.timetable_schools` 键非法、路径语法、`state.timetable` 写成目录等拒绝；引用未登记学校、`school_id` 与登记键不符、课程节次不在档案中 → 违约且路径如规格 §7。
   - `tests/contract/test_workspace.py` 补新键的用例（照该文件已有结构，不重写别的用例）。

## 不做

- 不改 `ky/availability/`、`ky/schedule/`、`ky/__main__.py`、`ky/planner/`、`ky/freeze/`（WP-T2）。
- 不写 CLI、不写 ④b 导入器、不碰投影。
- 不改 `docs/模块地图.md`、README（决策者做）。

## 验收（只跑这些，按 `AGENTS.md` 不跑全量）

```
py -3.12 -m unittest tests.contract.test_timetable_port tests.contract.test_workspace
```

写完含中文的文件查 `rg -n '\?\?\?' <文件>`。

## 报告

写到 `review/rounds/round-219-m18-core-luna.md`：改了哪些文件、每条要求怎么实现、测试结果原文（`Ran … OK`）、
"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"、规格里你认为有歧义并做了选择的地方（逐条列出，不要自己改规格）。
