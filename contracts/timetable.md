# 端口规格：M18 课表协同（学校档案 + 个人课表 → 每日可用分钟）

> 路线图 ④a。决议来源：用户 2026-09-30（见 §9）。细则审阅：sol 第 217 轮（FAIL → 本版修订，见 §11）。
> 实现：`ky/timetable/`；契约测试：`tests/contract/test_timetable_port.py`。
> 本端口只产出 `{date → minutes}` 与每日空闲时段；下游经 M26 / M8 接入，见 §6。

## 1. 职责与边界

回答一个问题：**"按课表，某一天大约能学多少分钟、空闲时段在哪里？"**

- 两类数据文件，均登记在工作区注册表（§5），代码里**不写任何学校、学期、年份**（`AGENTS.md` 第 8 条）：
  - **学校档案**（`reference.timetable_schools.<id>`）：节次 → 时刻、大节划分。一所学校一份，长期不变。
  - **个人课表**（`state.timetable`）：计算规则 + 若干学期，每学期写引用的学校、第 1 周周一、周数、课程、例外日。
- 课表推算值是**参考基数**，不是硬上限：它替代配置 `default_daily_minutes` 作为复习裁剪与规划输入的当日总分钟；
  规划者（AI 或人）仍可在日计划里声明别的 `available_minutes`。硬上限只来自 M26 手填单日（§6.3）。
- 纯函数：给定文件内容与配置，结果确定；不读时钟、不联网、不写文件。

## 2. 学校档案（schema_version 1）

UTF-8 YAML，顶层恰好这些字段：

```yaml
schema_version: 1
school_id: example_school      # ^[a-z][a-z0-9_]*$；正式加载时必须等于注册表里登记它的键
name: 示例大学                  # 非空字符串
aliases: [示例大]              # 可选，非空字符串列表，不得重复；供"按校名查档案"
system: zfsoft                 # 教务系统格式标识，^[a-z][a-z0-9_]*$；④b 导入器按它选适配器，本端口只校验形状
source:
  kind: user_statement         # 枚举：official | user_statement
  recorded_on: 2026-09-30      # 日期
periods:                       # 节次 → 时刻（此处节选；blocks 覆盖的每一节都必须登记，用户本地的完整档案在 data/personal/schools/，不进 git）
  1: {start: "08:00", end: "08:45"}
  # 可选 unconfirmed: true（布尔，缺省 false）：该节时刻是待确认假设
blocks: [[1, 2], [3, 4], [5, 6], [7, 8], [9, 10]]   # 大节划分
```

| 字段 | 类型 | 必填 | 规则 |
|---|---|---|---|
| `schema_version` | 整数 | 是 | 精确为 1（布尔拒绝） |
| `school_id`、`system` | 字符串 | 是 | 匹配 `^[a-z][a-z0-9_]*$` |
| `name` | 字符串 | 是 | 非空 |
| `aliases` | 字符串列表 | 否 | 缺省空；每项非空、不重复 |
| `source.kind` | 枚举 | 是 | `official` / `user_statement` |
| `source.recorded_on` | 日期 | 是 | YAML 日期或严格 `YYYY-MM-DD`；datetime 拒绝 |
| `periods` | 映射 整数 → 节 | 是 | 非空；键为整数（布尔拒绝），从 1 起连续 |
| `periods.<n>.start` / `.end` | 字符串 | 是 | 解析后必须是严格 `HH:MM`（00:00–23:59）；`start < end` |
| `periods.<n>.unconfirmed` | 布尔 | 否 | 缺省 false |
| `blocks` | 整数列表的列表 | 是 | 见下 |

1. 未知字段、重复键拒绝（任何层级）；违约均带字段路径，文案不属于规格。
2. 时刻只接受**解析后的**严格 `HH:MM` 字符串，其他类型一律违约、不做转换。YAML 1.1 会把未加引号的 `13:30`
   读成六十进制整数 810，所以作者应始终给时刻加引号（本端口不检查引号语法本身）。
3. 节次按编号严格递增且时间互不重叠：`end[n] <= start[n+1]`。
4. `blocks` 非空，每个大节非空；把 `periods` 的全部节次**按编号**划分为连续段：大节内节次编号相邻（不要求时刻无间隙），
   大节之间按编号顺序排列、不重叠、不遗漏。大节划分由档案给出，不按时间间隔推断。

## 3. 个人课表（schema_version 1）

```yaml
schema_version: 1
rules:
  study_window: {start: "08:00", end: "22:00"}   # 每天可学习的时段
  buffer_minutes: 15                         # 每节课前后各扣多少分钟
  min_gap_minutes: 25                        # 短于此长度的空档不计入
  block_deduction_minutes: 15                # 每占用一个大节，当天上限扣多少分钟
  # daily_cap_minutes: 150                   # 可选；缺省取 M8 传入的当日基数
semesters:
  - label: 2026-2027-1
    school: example_school
    week1_monday: 2026-08-31
    weeks: 18
    courses:
      - {name: 高等数学, weekday: 1, periods: "1-2", weeks: "1-15(单),2-16(双)"}
    exceptions:
      - {date: 2026-10-10, kind: follow, follow: 2026-10-08}  # 调休：按 10 月 8 日的课上
      - {from: 2026-10-01, to: 2026-10-07, kind: no_class}    # 闭区间，整天无课
      - {date: 2026-11-11, kind: no_class}
```

| 字段 | 类型 | 必填 | 规则 |
|---|---|---|---|
| `schema_version` | 整数 | 是 | 精确为 1 |
| `rules.study_window.start` / `.end` | 字符串 | 是 | 严格 `HH:MM`，`start < end` |
| `rules.buffer_minutes`、`min_gap_minutes`、`block_deduction_minutes` | 整数 | 是 | 非负；布尔、浮点拒绝 |
| `rules.daily_cap_minutes` | 整数 | 否 | 非负；缺省取**当日基数**（M8 传入，见 §4 第 7 条） |
| `semesters` | 列表 | 是 | 可为空（= 课表不覆盖任何日子） |
| `.label` | 字符串 | 是 | 非空，全文件唯一 |
| `.school` | 字符串 | 是 | 学校 ID 语法；正式加载时必须登记在 `reference.timetable_schools` |
| `.week1_monday` | 日期 | 是 | 必须是星期一；日期规则同 §2 |
| `.weeks` | 整数 | 是 | ≥ 1 |
| `.courses` | 列表 | 是 | 可为空 |
| `.courses[i].name` | 字符串 | 是 | 非空 |
| `.courses[i].weekday` | 整数 | 是 | 1–7（1 = 星期一） |
| `.courses[i].periods` | 字符串 | 是 | `"N"` 或 `"N-M"`，`1 <= N <= M`；正式加载时两端都须是所引学校的节次 |
| `.courses[i].weeks` | 字符串 | 是 | 周次表达式，见下 |
| `.exceptions` | 列表 | 否 | 缺省空；每项恰好是下面三种形状之一，多余或缺少字段即违约 |

例外的三种形状：`{date, kind: no_class}`、`{from, to, kind: no_class}`（闭区间，`from <= to`）、`{date, kind: follow, follow}`。

1. 未知字段、重复键拒绝；所有整数字段排除布尔。
2. 学期区间 = `[week1_monday, week1_monday + 7 × weeks)`；**任意两学期区间不得重叠**（首尾相接允许）。
3. **周次表达式**（照正方 PDF 写法）：逗号分隔若干项，不含空白；每项为 `N` 或 `N-M`，可在后面紧跟 `周`，
   可再跟 `(单)` 或 `(双)`（只取该范围内的奇数 / 偶数周）。每项必须满足 `1 <= N <= M <= weeks`（先查越界、再做奇偶过滤）；
   每项过滤后不得为空（如 `2(单)`，多半是转录笔误）；各项展开后的周次集合两两不相交
   （`1-6(单),2-6(双)` 接受，`1-3,3` 拒绝）。
4. 例外：日期都必须落在本学期区间内；同一日期不得被两条例外覆盖；`follow` 目标不得是任何例外日（含自身）。
5. 课程时间重叠（同一学期、同一天、同一节）**不是违约**（重修课可能真的冲突），计算时取并集，由 `ky timetable check` 列出。

## 4. 计算规则

对日期 `D`：

1. 找到区间包含 `D` 的学期；**没有 → 课表对这一天不发言**（结果为 `None`，下游回落当日基数，§6.1）。
2. 确定当天课程（"基本规则"：周次 `w = (d − week1_monday).days // 7 + 1`、星期 `d.isoweekday()`，
   取 `weekday` 相等且周次集合含 `w` 的课程）：
   - `D` 是 `no_class` 例外 → 无课；
   - `D` 是 `follow` 例外 → 对目标日期用基本规则（目标的周次与星期）；
   - 否则对 `D` 用基本规则。
3. **节次集合** `P` = 当天全部课程覆盖的节次（重叠课不重复）。
4. **占用区间**：`P` 中每节换成学校档案里的 `[start, end)`，逐节两侧各扩 `buffer_minutes`，与 `study_window` 取交集后求并集。
   （逐节而不是整段：`3-8` 节跨午休，午休不算占用。）
5. **空闲时段** = `study_window` 减去占用区间；只保留长度 `>= min_gap_minutes` 的段；`free_minutes` = 其长度之和。
6. **大节数** `b` = `P` 落在多少个不同大节里。**只由 `P` 计算，与学习时段和缓冲无关**：学习时段外的晚课也扣精力。
7. 上限 `cap` = `rules.daily_cap_minutes`，缺省为调用方传入的**当日基数** `base_minutes`。
   基数由 M8 解析，规则以 `contracts/pacing_review.md` §5 为准（路线阶段基础时长 > M28 设置 `initial` > 考试配置 `default_daily_minutes`）。
   M18 不读配置、不读路线（用户 2026-09-30：基数在 180–240 内由复盘调整，课表在基数上按大节扣减）。
8. **当天分钟** = `max(0, min(cap − b × block_deduction_minutes, free_minutes))`。结果为 0 是有效推算（不是 `None`）。

例（作息：每堂 45 分钟、大节内间隔 10 分钟、大节间 30 分钟，上午 08:00、下午 13:30 起；学习时段 08:00–22:00、缓冲 15、
最短空档 25、每大节扣 15；基数 120、未设 `daily_cap_minutes`；当天有第 3–8 节课）：
占用 09:55–12:05、13:15–17:35；空闲 08:00–09:55、12:05–13:15、17:35–22:00，共 450 分钟；`b = 3`；
`min(120 − 45, 450) = 75`。基数 180 时为 135。

## 5. 注册表（`contracts/workspace.md` 同步修改）

| 路径 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `reference.timetable_schools` | 映射 学校 ID → 路径(F) | 否 | ID 匹配 `^[a-z][a-z0-9_]*$`；未登记 = 空映射 |
| `state.timetable` | 路径(F) | 否 | 登记即必须存在；`write_target` 接受它（④b 的 apply 写它） |

- `Workspace` 增加 `timetable_schools: Mapping[str, Path]`（只读）与 `timetable: Path | None`；
  `require("reference.timetable_schools.<id>")` 按 `contracts/workspace.md` §4 的四种情况报错；未知字段照旧拒绝。
- 只登记学校、不登记个人课表 → 课表不参与计算（与都不登记相同）。
- 被学期引用的学校缺失、无效或 `school_id` 与登记键不符 → 违约（fail-closed），不得当作"没有课表"回落。

**新增一所学校的流程**（用户 2026-09-30："先搜一下有没有，没有就照例子创建放进库里"）：

1. 按 `school_id`、`name`、`aliases` 在已登记档案中查。
2. 查不到时照已有档案格式起草一份。AI 起草的按硬不变量②放 `staging/`。
3. `ky timetable check --school <文件>` 单独校验这份候选档案（不要求已登记；不做"ID 等于登记键"检查）。
4. 用户确认后放入 `data/personal/schools/`（学校会暴露用户身份，不进 git）并在本地补充注册表登记（`contracts/workspace.md` §2.6），再让课表学期引用它。

本端口不提供自动搜索或自动新建。

## 6. 与下游的连接

### 6.1 M26 / M8（优先级：手填单日 > 课表 > 配置）

- M26 定义协议 `DerivedDailyMinutes`（`minutes_for(day, base_minutes) -> int | None`），M26 **不 import M18**。
- `resolve_daily_minutes(day, base_minutes, availability, timetable=None)`：手填有该日（含 0）→ `availability`；
  否则 `timetable.minutes_for(day, base_minutes)` 非 `None`（含 0）→ `DailyMinutes(n, "timetable")`；
  否则 `DailyMinutes(base_minutes, "config")`。`source` 枚举加 `timetable`。
- M8 `resolve_day_budget(..., timetable=None)` 先解析当日基数（本包内恒为 `config.default_daily_minutes`；
  M28 落地后改为 `contracts/pacing_review.md` §5，该节同时扩展本节与 §6.2），再调 M26；`DayBudget.total_source` 枚举加 `timetable`。
  阶段配额之和超过当日硬复习上限时照旧按比例缩放。
- `contracts/availability.md`、`contracts/route_plan.md` 的来源说明同步修订。

### 6.2 调用方（M14 preflight、M19 输入包、M27 `ky resume`）

- 各自从注册表加载一次课表（`timetable_for_workspace`），把**同一对象**传给所有用到它的计算（`AGENTS.md` 已知缺陷第 2 条）；
  `ky resume` 的逐日搜索从 `plan_resume` 一路传到每个候选日的 `resolve_day_budget`。
- 裁剪与分配参数按下面的**优先顺序**决定（sol 第 218 轮 R3；第 1、3 步即现行行为，第 2 步把现行的 `availability` 扩到 `timetable`）：
  1. 冻结：`daily_minutes_override = 0`，`floor_policy = drop_when_short`，不传阶段配额；
  2. 未冻结且当日来源为 `availability` 或 `timetable`：`daily_minutes_override = total_minutes`，`floor_policy = drop_when_short`；
  3. 未冻结且来源为 `config`（含课表已登记但当日在学期外）：不传 override，`floor_policy = strict`。

  切换依据是**当日解析出的来源**，不是"课表对象存在"。
- M19 输入包 `availability` 字段：`availability` 或 `timetable` 任一登记即给出 `{"minutes", "source"}`，否则 `null`；
  其余字段不变，输入包 `schema_version` 不变（旧包仍合法；同 route_plan 字段先例）。`contracts/planner_port.md` 写明：
  `source` 为 `timetable` / `config` 时是参考基数，只有 `availability` 来源对应 M13 硬上限。
- preflight 文本：仅当来源为 `timetable` 时，在 `daily budget` 行后多一行，写学期、第几周、星期（`follow` 时注明按哪天的课）、
  大节数、空闲分钟；当天用到 `unconfirmed` 节次时加标记。

### 6.3 不变的部分

- M13 `DayPlanStore` 的可用时间上限**只看手填**；课表推算值不限制日计划（课表 75、AI 声明 200 合法；同日手填 90 时 200 仍拒绝）。
- M27 冻结阈值仍用配置容量（D11 细则），不看课表。
- M15 投影本包不读课表（课表投影与周课表图归 ⑤）。
- **未登记 `state.timetable` 且 M28 各项都不存在时**（联合条件见 `contracts/pacing_review.md` §9），preflight / 输入包 / resume /
  day-plan / 快照 / 投影输出与固定基线 `e381792` **逐字节一致**；对照测试固定该哈希并断言取到的是旧版（`AGENTS.md` 12a）。
  ④a 实施时 M28 尚不存在，该条件即"未登记 `state.timetable`"。

### M28b source and clipping update

M8's daily base precedence is route phase `base_daily_minutes`, effective
pacing `initial`, then exam configuration. A timetable without an explicit cap
deducts block minutes from that resolved base. M26 reports its unchanged
fallback source; M8 rewrites that source to `base` when the selected base came
from route or pacing.
Callers use the M28b three-step frozen / override / legacy clipping policy
documented in `contracts/pacing_review.md` §5, resolving each candidate day
separately during resume search.

## 7. Python 接口（`ky/timetable/`）

```python
load_school(path) -> SchoolProfile                   # 只校验本文件
load_timetable(path) -> Timetable                    # 只校验本文件；学校引用与节次在正式加载时核对
semester_from_mapping(raw, path_prefix) -> Semester   # 单学期文件内校验
timetable_from_mapping(raw) -> Timetable              # 整份课表文件内校验
validate_semester_references(semester, school, path_prefix) -> None
load_referenced_schools(workspace, school_ids) -> Mapping[str, LoadedSchool]
build_calendar(timetable, schools, sources=None) -> TimetableCalendar
timetable_for_workspace(workspace) -> TimetableCalendar | None
    # state.timetable 未登记 → None；登记但缺失 → 违约。
    # 只读取被学期引用的学校档案（每所一次）；引用未登记学校 → 违约，路径 semesters[i].school；
    # 档案 school_id ≠ 登记键 → 违约；课程节次不在学校档案 → 违约，路径 semesters[i].courses[j].periods。

semester_to_mapping(semester) -> Mapping
timetable_to_mapping(timetable) -> Mapping
    # 日期写 ISO；时刻严格 HH:MM；周次升序合并连续区间；课程与例外按对象顺序输出。
    # daily_cap_minutes 为 None 时省略；exceptions 即使为空也输出空列表。

LoadedSchool(profile: SchoolProfile, path: Path, sha256: str)  # 冻结数据类

TimetableCalendar
    .day(d, base_minutes) -> DaySchedule | None
    .minutes_for(d, base_minutes) -> int | None      # 满足 DerivedDailyMinutes
    .minutes_between(start, end_exclusive, base_minutes) -> Mapping[date, int]   # 固定基数；区间内有课表覆盖的日子
    .sources -> Mapping[str, str]                    # 工作区根相对的 POSIX 路径 → 解析所用原始字节的 SHA-256
```

`DaySchedule` 字段：

| 字段 | 含义 |
|---|---|
| `day`、`semester`（label）、`week` | 实际日期及其所在周 |
| `followed` | `follow` 例外的目标日期，否则 `None` |
| `weekday_used` | 用来匹配课程的星期（`follow` 时为目标日的星期；`no_class` 时为 `None`） |
| `no_class` | 是否 `no_class` 例外 |
| `classes` | 元组，按课表文件顺序；每项 `name, first_period, last_period, start, end`，`start`/`end` 是首节起点与末节终点，**只作展示**（跨午休时不能拿它算占用） |
| `periods` | 节次集合 `P`（有序元组） |
| `blocks` | 大节数 `b`（整数） |
| `free_segments`、`free_minutes` | 空闲时段元组 `(start, end)` 与总分钟 |
| `cap` | 扣减**前**的上限 |
| `minutes` | 当天分钟 |
| `unconfirmed_periods` | `P` 中标了 `unconfirmed` 的节次，升序元组 |

时刻一律以 `"HH:MM"` 字符串返回；`free_segments` 按时间升序。所有错误为 `ContractError`（带字段路径）；映射只读，列表为元组。

## 8. CLI（M14）

- `ky timetable show --week N [--semester L]`：打印星期 × 节次网格（行首节次与时刻，`unconfirmed` 节次加标记），末行为 7 天的推算分钟。
  只有一个学期时可省 `--semester`；多个学期时省略、`N` 超出 1..weeks 或学期不存在 → 用法错误退出 3（与现有子命令一致）；
  未登记个人课表或零学期 → 说明"没有可显示的学期"，退出 3。
- `ky timetable show --date D`：打印当天课程、空闲时段、大节数、上限与推算分钟；不在任何学期或未登记个人课表 → 说明"课表不覆盖此日"，退出 0。
- `--week` 与 `--date` 必须恰好给一个。不读当前时间。契约违约（文件无效等）退出 2。
- `ky timetable check`：正式加载个人课表（已登记时）与**全部**已登记学校档案，个人课表未登记也照样检查学校；
  列出重叠课程、用到的 `unconfirmed` 节次；有违约退出 2。
- `ky timetable check --school FILE`：只校验一份候选学校档案（§5 流程第 3 步）；不读注册表。
- `show` / `check`（不带 `--school`）接受 `--workspace`、`--config`（与 preflight 相同的取法）；`show` 的基数经 M8 同一解析得到。

## 9. 决议记录（用户 2026-09-30）

| 问题 | 用户选择 |
|---|---|
| 换算方式 | 扣课取空档再封顶；课多的日子**按大节数减上限** |
| 与手填 availability | 读取时叠加：手填单日 > 课表 > 配置 |
| 120 的地位 | 只是默认基数，实际安排由 AI 裁定（因此课表值不作硬上限） |
| 空闲时段 | 端口产出，本阶段不接排程 |
| 学习时段 | 08:00–22:00 |
| 学校作息 | 用户学校：每堂 45 分钟，大节内间隔 10 分钟，大节间 30 分钟；上午 08:00、下午 13:30、晚上 18:30 起；晚上只到第 10 节 |
| 兼容其他学校 | 课程表库：学校档案按数据登记，查不到就照例新建；同校四年格式固定 |
| ④b 导入 / 导出 | ics 导入（`icalendar`，已选轮子）优先，正方 PDF 解析备用；加导出到日历（`.ics`） |
| 个人数据 | 课表、学校档案不进 git（"只上传项目骨架"），见 `contracts/workspace.md` §2.6 |

**决策者拟定、可由用户改的参数**（写在个人课表 `rules` 里，不是代码默认值）：缓冲 15 分钟、最短空档 25 分钟、每大节扣 15 分钟。

## 10. 不在本端口范围

- ④b（另写 `contracts/timetable_import.md`，用户 2026-09-30 选定）：
  - **ics 导入优先**，用 2026-09-15 GitHub 调研选定的轮子 `collective/icalendar`（BSD-2；`ics-py` 已停更，排除）：
    任意来源导出的 `.ics`（学校课表 App、用户自己在浏览器里运行的正方导出脚本）→ 按学校档案把时刻对回节次 → 生成本规格 §3 的课表 → 进 staging 由用户确认；
  - **正方 PDF 解析**作备用（`pypdf` 取坐标），产出同一份课表；
  - **导出到日历**：`icalendar` 生成课程与每日空闲学习时段的 `.ics`，写到 `data/personal/`（不进 git）。
  - 不接入需要教务账号密码的抓取方式（zfnew、ZhengFang 等）：系统不经手用户凭据。
- CSV 导入；网页编辑（⑥）。
- 冬夏两套作息（需要时升 schema_version 2，节次按生效日期分版本）。
- 按时段拆分任务（规划者的事）；课表投影与周课表图（⑤）。
- 寒暑假等学期之外的日子：课表不发言，回落当日基数（配置或 M28 基数）；需要时用 M26 手填。
- 学校档案来源类别只有 `official` / `user_statement`；将来若有整份由 AI 推断的档案，再加类别。

## 11. 审阅记录（sol 第 217 轮）

| 意见 | 处理 |
|---|---|
| R1 候选学校档案无检查入口 | **采纳**：`check --school FILE`，§5 写全流程 |
| R2 第 11 节时刻与"大节间 30 分钟"依据矛盾 | **采纳，改法不同**：用户说晚上只到第 10 节，用户学校档案删去第 11 节，不猜时刻；用到即违约 |
| 格式表补全（容器、必填、布尔、日期、例外互斥形状） | 采纳：§2、§3 表格 |
| 时刻按解析后值校验，不查引号语法 | 采纳：§2 第 2 条 |
| blocks 相邻按编号 | 采纳：§2 第 4 条 |
| `b` 不受学习时段裁切 | 采纳：§4 第 6 条 |
| self-follow、空展开周次 | 采纳：拒绝（§3 第 3、4 条） |
| DaySchedule / sources / CLI 消歧 | 采纳：§7 表、§8 |
| 15 / 25 / 15 标为拟定参数 | 采纳：§9 |
| M19 不升版本、文档写明参考与硬上限 | 采纳：§6.2 |
| M0 同步 Workspace 字段与 require / write_target | 采纳：§5 |
| preflight 解释行标 unconfirmed | 采纳：§6.2 |

第 218 轮（R1、R2 关闭）：

| 意见 | 处理 |
|---|---|
| R3 冻结时分配策略未写明 | **采纳**：§6.2 三步优先顺序（冻结 → 手填 / 课表 → 配置），与现行代码一致；属规格补全，不另开复审轮 |
| 引用 `workspace.md` §4、示例注明节选 | 采纳 |
| 学校档案注释措辞 | 采纳：改为"当前仅登记第 9–10 节" |
| CLI 空状态与退出码 | 采纳：§8（用法错误 3，与现有子命令一致） |
| DaySchedule 表示与顺序 | 采纳：§7 |

用户 2026-09-30 追加（M28 周期复盘）：基础时长 180–240 由复盘在区间内调整、课表在当日基数上扣大节。
因此 `cap` 缺省改为调用方传入的当日基数，M18 不再读配置（§4 第 7 条、§6.1、§7）。
