# 端口规格：M29 课表导入 / 导出（④b-1：ics 导入、应用、导出到日历）

> 路线图 ④b。决议来源：用户 2026-09-30（见 §9）。细则审阅：sol 第 225 轮 FAIL（R1–R8）→ 重写；第 226 轮 FAIL（N1–N5）→ 修订；第 227 轮 FAIL（G1）→ 本版修订，sol 裁定修正 G1 后可写实现任务书，见 §11。状态：**可实现**。
> 实现：`ky/timetable_io/`；契约测试：`tests/contract/test_timetable_io_port.py`。
> 轮子：`collective/icalendar`（2026-09-15 GitHub 调研选定，BSD-2；`ics-py` 已停更，排除）。
> **正方 PDF 备用导入（④b-2）另立规格**：本机探针显示其版式需要按模板锚点划分课程单元才能做到"要么正确、要么报错"（sol 225 R5），
> 先完成本文件，再对 PDF 版式做结构探针后写 `contracts/timetable_import_zfsoft_pdf.md`。两条导入路线都做，PDF 排在后面。

## 1. 职责与边界

- **导入**：把 `.ics` 转成 M18 格式的**一个学期**，写到暂存区；用户检查（可手工编辑）后运行 `apply` 才写入个人课表。
- **导出**：把个人课表在某日期区间内的课程与空闲学习时段写成 `.ics`，供日历应用导入。
- 适配器只负责"外部格式 → M18 学期"。M18 的业务格式与计算不变；本包给 M18 **补公开的候选校验与序列化入口**（§2），不复制其校验规则。
- 不经手账号密码：不登录教务系统、不抓网页。
- **个人数据隔离（sol 225 R1、226 N1）**：本模块写出的每个路径（暂存、备份、导出，**以及它们各自的临时文件**）写入前都做"隔离检查"。
  先一次性确定工作区所在的 git 工作树（按文件系统事实与退出码判断，不看错误文案；sol 227 G1）：
  1. 从 `Workspace.root` 逐级向上（到文件系统根为止）查找名为 `.git` 的目录或文件。**一个都没有** → **状态 B**：已确认不在任何 git 工作树内
     （例如解压的副本），没有本仓库可泄漏，允许写入。
  2. 找到了 → 必须由 git 确认：`git -C <Workspace.root> rev-parse --is-inside-work-tree` 退出 0 且输出恰为 `true`，
     并且 `git -C <Workspace.root> rev-parse --show-toplevel` 退出 0 且输出一个存在的目录 → **状态 A**，工作树根 `R` 为该目录。
  3. 其余一切情况 → **状态 C**（无法确认）：找不到 `git` 可执行文件、任一查询非零退出、输出为空或不符、启动进程的其他 `OSError`。
     拒绝本模块的一切写入（暂存、备份、导出及临时文件），退出 2，提示"无法确认个人数据不会进仓库"。

  状态 A 下对每个目标：解析后不在 `R` 内 → 允许；在 `R` 内 → 需要 `git -C R check-ignore -q <目标>` 退出 0（已忽略），
  且 `git -C R ls-files --error-unmatch <目标>` 退出 1（未跟踪）；这两条命令其他任何退出码都按"无法确认"拒绝。
- 暂存文件不记录源文件名（文件名常含姓名），只记来源类型与原始字节 SHA-256。

## 2. M18 补充的公开入口（`ky/timetable/`，同步 `contracts/timetable.md` §7）

公开类型与函数都从包入口 `ky.timetable` 导出；M29 不 import `ky.timetable._*`。

| 入口 | 职责（sol 226 N4：校验范围逐一写明） |
|---|---|
| `semester_from_mapping(raw, path_prefix) -> Semester` | 单个学期的文件内校验（字段、周次表达式、例外），不看学校、不看其他学期 |
| `timetable_from_mapping(raw) -> Timetable` | 整份课表的文件内校验：`rules`、各学期、label 唯一、**学期不重叠**（即现有 `load_timetable` 的全部规则） |
| `validate_semester_references(semester, school, path_prefix)` | 单个学期对一份学校档案：`school_id` 相符、课程节次都存在。不需要 `rules` |
| `load_referenced_schools(workspace, school_ids) -> Mapping[str, LoadedSchool]` | 只读给定 ID 的档案、每所一次；返回档案及其原始字节摘要；ID 未登记、文件缺失或档案 ID 不符 → 违约（字段路径同现有规则） |
| `build_calendar(timetable, schools, sources=None) -> TimetableCalendar` | 对每个学期调用 `validate_semester_references`，然后构造日历；不读文件。`sources` 缺省为空映射 |
| `semester_to_mapping(semester)`、`timetable_to_mapping(timetable)` | **唯一的形状来源**：日期写严格 ISO 字符串；`weeks` 由周集合生成升序、合并连续周的 `N` / `N-M` 列表（不保留原写法，sol 226 N2）；课程与例外**按对象里的顺序**输出（不排序）；`exceptions` 为空时写空列表 |

`timetable_for_workspace` 改为"读课表字节 → `timetable_from_mapping` → `load_referenced_schools` → `build_calendar(…, sources=两者的原始字节摘要)`"，
结果、`sources` 与错误字段路径都与现在相同（每个文件仍只读一次）。

## 3. 暂存文件

路径：`write_target("staging")/timetables/import--<hash12>.yaml`（不用学期名拼文件名，sol 225 建议）。

| 字段 | 规则 |
|---|---|
| `schema_version` | 精确整数 1 |
| `kind` | 恰为 `timetable_import` |
| `source.adapter` | 枚举 `ics`（④b-2 加 `zfsoft_pdf`） |
| `source.sha256` | 64 位小写十六进制；源文件一次读取的原始字节 |
| `semester` | M18 学期，形状由 `semester_to_mapping` 决定 |
| `notes` | 字符串列表，可空；给人看，不参与哈希、不影响 apply |

- 未知字段、重复键拒绝。
- `<hash12>` = `{schema_version, kind, source, semester}` 经 `semester_to_mapping` 规范化后，按 M19 `canonical_json_bytes` 求 SHA-256 的前 12 位。
- **导入器生成时**：`courses` 按 `(weekday, first_period, last_period, name)` 升序构造，`exceptions` 为空。
  实际的停课、调课由 ics 里的逐次出现直接体现为课程周次或另一条课程，不生成 M18 例外（sol 225 §二）。
  用户在暂存文件里手工加的合法例外，`restage` 与 `apply` 原样保留。
- 规范写出会把周次统一成 `N` / `N-M` 列表（例如 `1-15(单)` 写成 `1,3,5,…,15`），语义不变；原写法与注释在 apply 的备份里保留。

**发布（sol 225 R6）**：先在同目录写临时文件、重读校验，再 `os.link(临时, 目标)` 不覆盖发布并删除临时文件。
目标已存在：内容（含 `notes`）逐字节相同 → 视为已导入，退出 0；不同 → 违约，保留原文件。

**手工编辑后重新封装（sol 225 R2）**：`ky timetable restage FILE`
读取暂存文件（`hash12` 可以已不匹配），校验 `semester`，重算 `hash12`：
- 与文件名里的相同（只改了 `notes`、缩进或等价周次写法）→ 校验通过即返回原文件，不发布新文件；
- 不同 → 发布新暂存文件，原文件不动。
打印的差异以**当前已生效的同 label 学期**为比较基准（未生效时打印"新增学期"摘要），不从短摘要反推编辑前内容（sol 226 S1）。
`apply` 只接受 `hash12` 匹配的暂存文件。

## 4. ics 导入（`ky timetable import-ics FILE --school ID --label L --week1 D [--weeks N] [--timezone TZ]`）

**日期口径（sol 226 N3）**：`--week1` 与 `--weeks` 表示**本地（目标时区）墙上日期**上的学期：导入域 = 本地日期 `[week1, week1 + 7N)`。
浮动时间事件的本地日期就是它自己的日期；带时区事件先转换到 `--timezone` 再取日期。**任何"是否在域内"的判断都用转换后的本地日期**，
不在原始时间域上用同名午夜比较。

处理顺序固定（sol 225 R3 / R4、226 N3 / S4）：

1. **读取**：一次读入原始字节（计算 `source.sha256`），用 `icalendar` 解析；非法 → 违约。
2. **按 UID 分组**：每个 UID 至多一个主事件（无 `RECURRENCE-ID`）加若干覆盖事件（有 `RECURRENCE-ID`）。同一 UID 两个主事件 → 违约。
3. **先剔除不导入的事件**（写进 `notes`，不参与后面的域检查）：主事件为全天事件（`DTSTART` 是日期）、主事件 `STATUS:CANCELLED`、
   主事件既无 `DTEND` 也无 `DURATION`。同一事件同时有 `DTEND` 与 `DURATION`、或 `DTSTART` / `DTEND` 一个是日期一个是时刻 → 违约（不自动修复）。
4. **展开主事件**（在其原始时间域中，用 `python-dateutil`）：
   - 支持：单次事件；`RRULE` 的 `FREQ=WEEKLY`，可带 `INTERVAL`、`BYDAY`、`UNTIL`（含末次，按 RFC 5545 与 DTSTART 同一时间域比较）或 `COUNT`（计全部出现，含 DTSTART）；
     `EXDATE`（多个属性、一个属性多个值都处理）。拒绝（违约并指出 UID）：其他 `FREQ`、`RDATE`、`BYSETPOS` 等未列出的规则部分。
   - 每个实例的结束 = 实例开始 + 主事件时长（`DTEND − DTSTART` 或 `DURATION`），不照抄首日的 `DTEND`。
   - 有终止（`COUNT` / `UNTIL`）的规则全部展开。**无终止**的规则必须给 `--weeks`（否则违约），展开到"本地域末日 + 1 天"投影回原始时间域的时刻为止。
5. **应用覆盖**：覆盖事件的 `RECURRENCE-ID` 必须精确对应该 UID 某个已展开的原始实例，否则违约（孤立覆盖，含指向无终止规则展开范围之外的实例）。
   - `STATUS:CANCELLED` → 删除该实例；否则用覆盖事件的时间替换（时长取覆盖自己的 `DTEND` / `DURATION`，都没有则沿用主事件时长），`SUMMARY` 缺省沿用主事件。
   - 拒绝：`RANGE=THISANDFUTURE`、同一实例多个覆盖、覆盖事件自带 `RRULE`、`EXDATE` 与覆盖指向同一实例。
6. **时区**：浮动时间保持墙上时间；带 `TZID` / UTC 的转换到 `--timezone`（IANA 名）。出现带时区时间而未给 `--timezone`、或 `TZID` 无法解析 → 违约。
7. **按本地日期检查每个实际出现**（覆盖之后的结果）：转换后跨日 → 进 `notes` 不导入；本地日期早于 `week1` → 违约；
   给了 `N` 时：来自无终止规则、晚于域末的出现 → 截去（`notes` 记一条"规则无终止，截至第 N 周"）；其他出现晚于域末 → 违约
   （包括被覆盖移出域外的一次课）。原始实例在域外、被覆盖移入域内的出现按其实际日期接受。
8. **对回节次**：开始时刻必须精确等于学校档案某节 `start`、结束时刻精确等于某节 `end`（到秒；`09:00:30` 不等于 `09:00`），且首节 ≤ 末节。
   对不上的全部列出后违约（多半是学校作息与导出工具不一致）。
9. **定周次**：`w = (本地日期 − week1)//7 + 1`。`N` 缺省取最大周次（此时所有规则都有终止）。
10. **合并**：按 `(SUMMARY 去首尾空白, 星期, 首节, 末节)` 分组，组内周次集合即课程周次；同组同一周出现两次 → 违约。`SUMMARY` 为空 → 违约。
    `LOCATION`、`DESCRIPTION`、教师等一律丢弃。
11. **结果为空**（没有任何可导入的出现）→ 违约"没有可导入的课程"，不写暂存。
12. **校验范围只到候选学期本身**（sol 226 N4：与其他学期是否重叠留给 apply）：`semester_from_mapping` + `load_referenced_schools` + `validate_semester_references`。
    发布暂存文件，打印摘要与第 1 周课程网格。个人课表已登记时，再用"当前 `rules` + 只含本学期"的临时课表经 `build_calendar` 算出第 1 周每日分钟一并打印；
    未登记时只打印课程网格、不打印分钟。

## 5. 应用（`ky timetable apply --from-staging FILE [--replace] [--dry-run]`）

1. `FILE` 必须是 `write_target("staging")/timetables/` 下的真实文件：先确认该子目录解析后在 staging 内，再确认 `FILE` 解析后在该子目录内（M29 自己的具名辅助，不 import M19 私有函数）。
2. 读取暂存文件并校验格式与 `hash12`；读取个人课表（`state.timetable`，未登记 → 违约）**一次**，同一份原始字节用于解析、比较与备份。
3. **先完整校验，再决定做什么**（sol 226 N4）：现有课表字节经 `timetable_from_mapping` 解析；构造合并结果——暂存学期 `label` 已存在则替换该位置，
   否则追加到末尾；其余学期的顺序与 `rules` 原样保留。合并结果经 `timetable_to_mapping` 生成新字节，再用 `timetable_from_mapping`（整表规则，含学期不重叠）
   + `load_referenced_schools` + `build_calendar`（学校已登记、档案存在、节次存在）校验。任何一步不过 → 违约，不写。
4. 然后判断：`label` 已存在且与现有学期规范映射完全相同 → 打印"已应用"，退出 0（有无 `--replace` 都一样，不写备份）；
   `label` 已存在但不同、且无 `--replace` → 违约；其余情况继续。
5. 打印变更：新增 / 替换的学期；课程差异按 `(name, weekday, first_period, last_period)` 列出新增、删除、周次变化；学校、第 1 周周一、周数变化也列出；
   第 1 周网格；**"规范写出会去掉原文件注释"**与备份文件名。`--dry-run` 到此为止。
6. 写入顺序（sol 225 R6）：
   1. 备份：把第 2 步读到的原始字节发布为同目录 `<主文件名去扩展名>.previous-<该字节 sha256 前 12 位>.yaml`（临时文件 + `os.link`）。
      同名已存在且字节相同 → 跳过；字节不同 → 违约，不替换主文件。
   2. 用 `ky/storage/atomic.replace_bytes` 替换主文件。
   - 备份前中断：主文件不变。备份后、替换前中断：主文件不变，备份完整，重跑即可。替换后中断：主文件已是新版、备份在；重跑走第 4 步"已应用"。
   - I/O 错误转为契约错误（退出 2），不产生 traceback。

## 6. 导出到日历（`ky timetable export-ics --from D --to D2 --config C --out FILE [--free-only | --classes-only]`）

- `--from < --to` 必须成立（否则用法错误退出 3）；`--free-only` 与 `--classes-only` 互斥。区间内课表不覆盖任何一天 → 违约，不写文件。
  有覆盖日但按所选类别没有任何事件（例如全是停课日时只导出课程）→ 写一个合法的空日历，退出 0（sol 226 S3）。
- 对区间 `[D, D2)` 内课表覆盖的每一天取 M18 `DaySchedule`（基数经 M8 同一解析，`contracts/timetable.md` §4 第 7 条），不重新实现计算：
  - **课程事件（sol 225 R8、226 N5）**：每门课的节次逐节考虑，相邻两节**同属一个大节**、且两节之间的间隙里**没有** M18 给出的任何空闲时段时才合并，
    否则分成两个事件（每个事件从首节起点到末节终点）。因此课程事件永远不会盖住当天导出的学习时段，也不要求学校的大节在时间上连续。
    `SUMMARY` = 课程名，`TRANSP:OPAQUE`。
  - **学习时段事件**：每个 `free_segments` 一个事件，`SUMMARY` = `可学习 <分钟> 分钟`，`CATEGORIES:STUDY`，`TRANSP:TRANSPARENT`（是可用窗口，不在日历里显示为忙碌）。
- 时间写**浮动本地时间**（不带时区），按显示设备时区解读。
- 确定性：`UID` = `sha256(规范 JSON {kind, date, start, end, summary, index})` 前 16 位 + `@kaoyan-ai-system`；
  `index` 是**同一身份组**（前五项都相同）内按稳定顺序的序号，非重复事件为 0，因此不随 `--classes-only` 或区间变化而改变；
  `DTSTAMP` = 区间起日 00:00:00Z；事件按 `(date, start, end, kind, summary, index)` 排序；`VERSION:2.0`、`PRODID:-//kaoyan-ai-system//M29//ZH`；
  编码、折行、转义交给 `icalendar`。承诺的是"同一依赖环境、同一输入 → 逐字节相同"；依赖锁在 `icalendar>=7,<8`，升级任何版本后重新核对导出字节基线。
- `--out` 必填、不覆盖（已存在 → 违约）；写入前做 §1 隔离检查；临时文件 + `os.link` 发布。

## 7. 依赖

`pyproject.toml` 显式加 `icalendar>=7,<8`、`python-dateutil>=2.8,<3`、`tzdata`（Windows 上 `zoneinfo` 需要它提供时区数据）。

## 8. 测试（`tests/contract/test_timetable_io_port.py` 与 M18 契约测试增补，全部合成数据）

- M18 新入口：`semester_to_mapping` / `timetable_to_mapping` 往返等价；`build_calendar` 与 `timetable_for_workspace` 结果一致。
- ics：sol 225 报告 §二表格每一行一例；§R3 / R4 的无终止规则、取消覆盖、移动覆盖、`DURATION`、孤立覆盖与 `THISANDFUTURE` 拒绝；空结果拒绝；
  同一输入两次导入字节相同且第二次退出 0。
- 暂存：中断残留（目标已存在但内容不同）拒绝且不覆盖；`restage` 编辑后新哈希；`apply` 拒绝哈希不符。
- apply：追加、`--replace`、"已应用"重跑、label 冲突、重叠拒绝、备份同名不同内容拒绝、`--dry-run` 不写、staging 外路径拒绝、其余学期与 `rules` 保持。
- export：确定性字节、大节切段（跨午休）、`TRANSP`、重复课程不同 UID、`--out` 已存在拒绝、空覆盖拒绝、隔离检查拒绝未忽略的工作区内路径。
- 隔离检查：状态 A 下工作树外允许、树内已忽略且未跟踪允许、未忽略或已跟踪拒绝，**注册表在仓库子目录时工作区外但仓库内的目标同样检查**（226 N1）；状态 B（向上找不到 `.git`）允许；状态 C 拒绝，含"找到 `.git` 但 git 查询失败"（227 G1）；临时文件与备份各自检查。
- sol 226 报告的 N2（三种周次写法规范成同一学期、走"已应用"）、N3（UTC 前一日的课按本地日期接受；覆盖移出域外拒绝；全天事件不参与域检查）、N4（候选与旧学期重叠在写前拒绝；"已应用"但学校档案缺失 → 违约）、N5（大节内有长空档时课程分两段、学习时段不被盖住）各一例；S1 只改 notes 的 `restage` 返回原文件；S3 空选择写空日历；S4 重复实例结束时间、`DTEND`+`DURATION` 并存拒绝。

## 9. 决议记录（用户 2026-09-30）

| 问题 | 用户选择 |
|---|---|
| 导入路线 | 两条都做，**ics 优先**（用已选轮子 icalendar），正方 PDF 解析备用 |
| 导出到日历 | 要，放在 ④b |
| 生效方式 | 导入产物先进暂存区，用户确认后生效 |
| 个人数据 | 课表类文件不进 git；暂存 / 导出 / 备份都在隔离路径 |

**决策者拟定、可被用户推翻**：PDF 另立 ④b-2；节次时刻精确相等；导入不生成单双周与例外；apply 规范重写（丢注释、留备份）；
导出按大节切段、浮动时间、学习时段不占忙闲、`--out` 必填且不覆盖；无终止重复规则必须给 `--weeks`。

## 10. 不在范围

- 正方 PDF（④b-2 另立规格）；登录教务系统抓取；CSV；网页上传与编辑（⑥）；在线订阅日历；冬夏作息。

## 11. 审阅记录（sol 第 225 轮）

| 意见 | 处理 |
|---|---|
| R1 导出只提醒不拒绝 | 采纳：§1 隔离检查，写前拒绝 |
| R2 手工编辑后哈希失配；日期规范化 | 采纳：`restage`；§2 `semester_to_mapping` 统一形状 |
| R3 无终止 RRULE | 采纳：有限展开域，无终止规则必须给 `--weeks`；空结果拒绝 |
| R4 覆盖事件顺序与支持子集；`DURATION` | 采纳：§4 固定顺序与支持 / 拒绝清单 |
| R5 PDF 记录边界 | 采纳方向：PDF 另立 ④b-2，先做结构探针，按模板锚点定单元 |
| R6 原子发布 | 采纳：暂存、备份、导出都临时文件 + `os.link`；apply 写入顺序与中断状态 |
| R7 M18 无公开候选校验入口 | 采纳：§2 新增四个公开入口 |
| R8 课程跨度包住空档 | 采纳：按大节切段 |
| 建议：TRANSP、UID、排序与编码、空状态、重跑语义、差异键、字段表、文件名、依赖 | 采纳：§3、§5、§6、§7 |

第 226 轮（R1–R8 关闭或部分关闭；R5 以 ④b-2 另立规格处理，被认可，但不能记为 PDF 已完成）：

| 意见 | 处理 |
|---|---|
| N1 工作区外不等于仓库外 | 采纳：§1 以 git 工作树为界，三种状态（A 在树内 / B 不在任何仓库 / C 没有 git）；按退出码判断 |
| N2 原周次写法已被模型丢弃 | 采纳：§2 序列化由周集合生成规范写法；课程与例外保持对象顺序；导入器自己排序；用户例外保留 |
| N3 有限域的日期口径 | 采纳：§4 本地日期口径；先剔除不导入的事件；覆盖后按实际出现检查；无终止规则投影展开 |
| N4 整表校验职责与"已应用"绕过校验 | 采纳：§2 列清各入口校验范围；§5 先完整校验再判"已应用"；导入只校验候选学期本身 |
| N5 大节内长空档 | 采纳：§6 只在同大节且间隙内没有空闲时段时合并 |
| S1 restage 比较基准、同哈希 | 采纳：§3 |
| S2 新入口保持 sources 与错误路径 | 采纳：§2 `build_calendar(…, sources)`、`timetable_for_workspace` 行为不变 |
| S3 UID 序号、空选择、版本确定性 | 采纳：§6 |
| S4 重复实例结束时间与异常事件 | 采纳：§4 第 3、4、5 条 |

第 227 轮（N2–N5 关闭，N1 部分关闭）：

| 意见 | 处理 |
|---|---|
| G1 git 查询失败被当作"没有仓库"放行 | 采纳：§1 状态 B 只由"向上找不到 `.git`"确认；找到后任何查询失败都是状态 C、拒绝写入 |
| 实现细节 1–8（半开域比较、LoadedSchool 字段、预览基数、序列化形状、合并条件、restage 摘要、ics 类型、退出码） | 采纳：写进第 228 轮实现任务书，不改本规格的业务规则 |
