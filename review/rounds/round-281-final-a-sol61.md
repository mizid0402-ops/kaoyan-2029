# 第 281 轮：最终大检查 A（M18 / M29 / M28）

## 结论：FAIL

存在一项必须改：无效 ICS `DURATION` 漏出依赖异常，CLI 错按用法错误退出。
其余结论限于下面的代码路径与合成验证；未将测试通过当作全面验收。
按指定顺序读取规则、模块地图、规格、交接与已关闭评审；未重报已关闭问题。

## 逐条核查

| 项目 | 判定与最小证据 |
|---|---|
| A1 | 已核实。`ky/timetable/calendar.py:170` 起先算节次并集、大节数与空档，再按基数扣减封顶；学习窗口外的课仍扣大节。M8、M27、M28 的协议消费者只经 M26 取 `minutes_for(day, base_minutes)`；CLI、预览和图表使用 M18 自身的日历端口，没有把协议对象当日历。相关扣课与窗口外课程测试通过。 |
| A2 | 已核实其他调用方。合成学期外日期 `2026-09-06` / `2026-09-21`：preflight、日输入包均成功，无 traceback。preflight 仅在来源为 timetable 时访问日明细（`ky/__main__.py:477`）；日期显示、导出显式处理 None；预览可容忍 None。CLI / 图表周网格先校验学期周数，生成的整周均在学期内；M26、M28 报告、resume 回落基数。M33 的既有修正位于 `ky/today/port.py:150`。 |
| A3 | 已核实。`ky/timetable/calendar.py:98` 按时间排序、合并占用，再返回全部合格空档；只按已声明的 min_gap 过滤，没有另加数量上限或截断。封顶只改变 minutes，不裁掉 free_segments；空窗口相关测试通过。 |
| B1 | 已核实。合成优先级用例 `test_base_precedence_and_fallback_source` 验证阶段基数、initial、配置，及课表扣减与手填覆盖；同时断言 base_source / total_source。M8 在 `ky/schedule/budget.py:149` 先取基数再交 M26，回落来源按基数来源改写为 base / config。复习配额仍取阶段并按当天硬上限缩放。 |
| B2 | 已核实当前调用链。preflight、M19 日包、resume 候选日、M28 报告 / 输入 / status、M33、M17 progress 均传 pacing_initial；课表 CLI 与 IO2 / 周图经 daily_base_minutes。IO2 `ky/timetable_io/preview.py:89` 加载设置并传入同一解析器；其注册表驱动测试已执行通过。未发现漏接。 |
| B3 | 已核实直接受接线影响的旧路径。固定 `636bd09` 的对照用例验证 preflight 文本 / JSON、日输入包、resume dry-run、课表日期显示的字节与产物一致；pacing 模块另执行固定 `dcbb5b6` 的旧路径对照。**仅不登记 pacing 并非充分条件**：规格还要求路线无新基数、完成事件无新分钟字段，并区分有无课表；本轮不宣称覆盖全部历史输出矩阵。 |
| C1 | 不成立，见必须改 M1。正常导入、暂存不可覆盖、restage 重算、apply 校验在 IO 契约模块通过；缺日历尾、半截事件、非法 DTSTART 的独立输入均报 ContractError。无效 DURATION 却不按契约报错。 |
| C2 | 已核实。`ky/timetable_io/operations.py:192` 检查 staging 子目录与文件包含关系，写目标 / 临时文件 / 备份经隔离检查；无效哈希、重叠、缺学校在写前拒绝。重复 apply 返回 already_applied，不再备份或写主文件；越界和备份后中断重跑用例通过。 |
| C3 | 已核实契约与错误路径。`ky/timetable_io/zfsoft_pdf.py:158` 将提取失败转为带定位的 ContractError；未知片段、残片、孤立详情、非有限坐标、周次上界的合成测试通过，不部分导入。个人 PDF 的历史一致性本轮无法核实：按任务禁止读取该输入；未据此重新声明本机验收完成。 |
| C4 | “完整导出再导入幂等”不成立。一个正常合成学期的默认导出再导入因学习空档不匹配节次而报 VEVENT.periods；同夹具 classes-only 往返学期映射相等。时区转换、浮动时间、全天剔除与备注的 IO 用例通过。规格的导出目标是日历应用，未承诺课表备份式往返；例外展开、课程按大节切段也会丢失原结构，不能把单例 classes-only 相等推广为通用幂等。 |
| D1 | 已核实规则与仓库记录的用户选项一致：近后界并入下一周期，平距取短；未独立读取原始用户对话。`ky/pacing/port.py:203` 只处理首周期，后续首尾相接；分界起点的固定旧版对照通过。独立边界探针结果见下文。 |
| D2 | 已核实写一次不可改；“同周期重跑应拒绝”的前提不成立。规格要求返回已保存报告并成功退出，来源变化仅提示。`ky/pacing/storage.py:200` 用 os.link 发布；模块用例验证报告字节保留及 CLI 重跑提示，不覆盖旧报告。 |
| D3 | 已核实意图发布后路线写失败的恢复与重复提交。模块用例经 CLI 注入 StorageError，保留意图，重跑发布保存候选，再跑不新增修订；停用设置 / 修改 exam_date 后仍可恢复。`ky/pacing/submit.py:488` 先分流。强制终止遗留路线锁或孤儿版本时，需要按既有路线存储契约人工处理后重跑，不承诺无条件自动恢复。 |
| D4 | 已核实。`ky/pacing/port.py:509` 切段前半无 targets，后半保留原阶段末目标；阶段起点原地替换保留目标，后续阶段不变。模块用例有实质断言。`ky/pacing/submit.py:271` 限 effective_from 早于设置考试日及路线终点；已有路线的阶段终点与 target_exam_date 不因改设置而延长或缩短。 |
| D5 | 已核实。`ky/pacing/submit.py:81` 把 YAML date 规范成 ISO，模块 CLI 用例执行了无引号 effective_from。方案没有其他日期字段；设置 start / exam_date / cadence.until 的解析接受 YAML date，报告 / 输入包 / 意图的日期按 ISO 序列化，未发现同形的首次复盘阻断。 |
| E1 | 已核实差异，判断为可接受既有状态。独立空工作区去掉 manifest 后，preflight / 日输入包报契约错误，M32 使用的 read_state_sources 返回空队列。`contracts/review_intake.md` §4 明定初始化可读为空；规划读取则要求已有有效队列，避免把意外丢失当作无复习任务。区别是写入初始化与规划前置条件，并非同一端口结果矛盾；初始化应由 AI 建空队列。 |
| E2 | 已核实。冻结阈值仍用配置容量，不受 initial 或课表影响；冻结时 preflight / 日包覆盖分钟为零，不排新学 / 复习。M28 报告仍保留参考分钟及冻结历史（不是实际学习量）；新方案提交在 `ky/pacing/submit.py:277` 拒绝冻结状态。已有意图恢复不重新执行冻结护栏，这是完成已确认事务，符合恢复规格，不直接生成学习任务。相关预算、报告和护栏用例通过。 |

D1 独立探针（终日均为闭区间显示；首周期后均接正常周期）：

- half_month：`2026-10-01 → 10-15`，`10-16 → 10-31`，平距 `10-24 → 10-31`，中途 `10-25 → 11-15`。
- 跨年：half_month `2026-12-29 → 2027-01-15`；month `2026-12-20 → 2027-01-31`。
- 闰年平距 `2028-02-23 → 02-29`；非闰年近后界 `2027-02-23 → 03-15`。
- cadence 切换：half_month 截至月初后改 month，`2026-11-27 → 12-31`；随后自然月继续。

## 必须改

### M1：无效 DURATION 未转为带字段路径的契约错误

位置：`ky/timetable_io/ics_import.py:80` 直接读 `duration.dt`；依赖库的 BrokenCalendarProperty
未在导入端口转成 ContractError，落到 `ky/__main__.py:2031` 的 ValueError 分支。
正常用户拿到字段损坏的外部文件时可触发；不是篡改内部存储或攻击前提。本轮 C1 明确要求此错误路径。

唯一复现输入：合成学校 demo（使用现有 `_workspace` 夹具），导入下列文件：

```ics
BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:cut-duration
DTSTART:20260907T080000
DURATION:PT45
SUMMARY:Math
END:VEVENT
END:VCALENDAR
```

命令：`py -3.12 -B -m ky timetable import-ics cut-duration.ics --school demo --label term --week1 2026-09-07 --workspace <合成注册表>`。
实测同一 CLI 入口退出 **3**，只打印依赖库的 “Cannot access 'dt' on broken property 'DURATION'” 错误；
公开 import_ics 抛 BrokenCalendarProperty，未附 UID / 文件字段路径；未发布暂存文件。
应为 **ContractError**（例如路径 `UID cut-duration.DURATION`），CLI 退出 **2**。
修复只需在 DURATION 解码 / 校验处转换错误，并加这一条回归；不扩展导入功能或重跑全集。

## 建议改

- `prompts/pacing_review.md:9` 的范围路径应改为输入包实际的 settings.minimum / settings.maximum；本轮生成的包没有 settings.base_daily_minutes，程序护栏本身正确。
- 指引中的“输入包的 input_hash”应注明取生成命令输出的摘要；本轮生成的 JSON 内没有该键。
- 统一 AI 初始化说明：先建立空队列 manifest，再运行规划命令；无需把所有缺文件读取放宽为空。
- 清理规格头部“草案 / 待复审”及交接中的旧起点、旧队列状态文字，避免把历史阶段当作当前事实。

## 不改（说明）

- 报告重跑成功返回旧报告是既定幂等语义；无需改成拒绝，也不重新计算并覆盖历史报告。
- 导出保留全部合格空档是可用窗口展示，daily cap 不表示只导出那部分窗口；完整 ICS 不作课表备份。
- 不取消路线存储对遗留锁 / 孤儿版本的人工恢复要求；恢复后重跑同一已确认事务不会创建另一修订。
- 起点就近吸附可能跨月或 cadence 边界形成较长首周期，属于已记录用户选择；不改成固定天数。

## 安全登记

未发现新的已证实安全项；第 250 轮伪造输入包 / 意图内层校验登记保持历史记录，本轮未重报或加固。
未探测恶意链接或另一进程精确插手；M1 是外部文件损坏的指定错误路径，不移入安全登记。

## 验证与最坏情况

本轮实际运行：timetable_port 指定计算 / 学期 / 缺登记用例 **5** 项通过；timetable_io_port **41** 项通过；
pacing_port **15** 项通过；day_budget_port 指定优先级与固定基线用例 **2** 项通过；
zfsoft_pdf 指定纯合成错误路径 **7** 项通过；resume_port 指定协议复用 / initial 用例 **2** 项通过。
另执行上述学期外、坏 ICS、导出往返、缺 manifest、周期边界与输入包字段探针；初版探针的夹具科目不符及隔离拒绝已校正，未作为实现缺陷。
所有执行设 PYTHONDONTWRITEBYTECODE=1、使用系统临时目录；未运行个人 PDF 用例、全量、冒烟或联网。
若本轮结论有误，最坏是用户首次复盘取错基础预算、切段目标错位或中断提交重复发布路线；
这些路径已做定点核查，仍不等于真实个人输入全体验收。当前已确认问题只会使坏 ICS 得到错误分类，不会生效写入课表。
只新增本报告；未修改实现、测试、规格、其他文档，未提交。
