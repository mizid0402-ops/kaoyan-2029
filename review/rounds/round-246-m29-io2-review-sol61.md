# 第 246 轮：WP-IO2 合并后实现评审

结论：**FAIL**。三项必须改：公用预览重复读取学校档案；时区检查顺序及范围不符合契约；节次不匹配未汇总报告。

评审对象为本轮主工作区的暂存区与工作区合并结果。没有评审其他 worktree，没有联网、安装依赖或读取个人原始文件；只新增本报告。

## 必须改

### R1：导入与公用预览分别读取同一学校档案

位置：`ky/timetable_io/ics_import.py:362`、`:378`；`ky/timetable_io/preview.py:48`；`ky/timetable_io/zfsoft_pdf.py:577`、`:599`。

**可复现输入**：学校使用测试文件 `_school_document()`；候选只有周一 Math、节次 1、第 1 周。ICS 如下，`week1=2026-09-07`，不提供配置也会触发。

```ics
BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:valid
DTSTART:20260907T080000
DTEND:20260907T084500
SUMMARY:Math
END:VEVENT
END:VCALENDAR
```

**实际结果**：一次 `import_ics` 对学校文件调用 `Path.read_bytes` **2 次**。第一次供节次匹配与引用校验，第二次由 `preview_lines → _calendar_for_semester → load_referenced_schools` 重新加载。使用合成 PDF 解析结果、mock 提取层，同样测得 **2 次**。

**应有结果**：一次导入只加载一次学校档案，候选校验与预览消费同一个已加载对象。可让公用预览接受已加载的学校资料或已构造的候选日历；独立调用预览时再自行加载。不应为两个适配器复制网格逻辑。

这是 `AGENTS.md` 已知缺陷第 2 条的直接违约；PDF 的重复读取是本次接入公用预览引入的。无需依赖恶意替换或并发才能成立。

### R2：时区检查提前误拒已剔除事件，又漏查 EXDATE

位置：`ky/timetable_io/ics_import.py:323`、`:359–361`、`:160–167`。

**输入 A**：在 R1 的浮动课程后增加以下主事件，不给 `--timezone`。

```ics
BEGIN:VEVENT
UID:cancel
DTSTART:20260907T080000Z
DTEND:20260907T084500Z
STATUS:CANCELLED
SUMMARY:Ignore
END:VEVENT
```

**实际结果**：`ContractError --timezone: --timezone is required for zoned events`，没有导入有效课程。

**应有结果**：按 §4 固定顺序，先分 UID、剔除取消主事件并记 notes，再检查仍参与导入的时间。有效浮动课程应成功暂存，取消事件不应使它额外需要目标时区。无结束时间的 UTC 主事件也存在同样的提前检查路径。

**输入 B**：用下列课程，目标时区设为 `UTC`。

```ics
BEGIN:VEVENT
UID:utc
DTSTART:20260907T080000Z
DTEND:20260907T084500Z
RRULE:FREQ=WEEKLY;COUNT=2
EXDATE;TZID=Unknown/Zone:20260914T080000
SUMMARY:Math
END:VEVENT
```

**实际结果**：成功发布暂存；Math 的周次为 `{1, 2}`。`_validate_timezones` 只检查 DTSTART、DTEND、RECURRENCE-ID；未知 EXDATE TZID 没有拒绝，随后原始身份键不匹配，取消日期失效。

**应有结果**：对仍参与导入的 EXDATE 属性及其中每个时间值检查时区，未知 TZID 明确违约，不发布。外部工具使用本系统不支持的 TZID 是正常兼容性场景，不能静默保留原本要取消的课程。有效 EXDATE 仍应按原始实例时间域精确匹配，不改成猜测或跨域匹配。

两例应一起修：不能只补 EXDATE 循环而继续在剔除之前检查所有原始组件；也不能为了跳过已剔除事件而放过保留课程的未知时区。

### R3：节次匹配失败只报第一处，没有全部列出

位置：`ky/timetable_io/ics_import.py:223`、`:267–270`。契约 §4 第 8 条明确要求“对不上的全部列出后违约”。

**可复现输入**：测试学校节次仍为 08:00–08:45、08:55–09:40、10:10–10:55、11:05–11:50。两个独立单次事件：

```ics
BEGIN:VEVENT
UID:off-a
DTSTART:20260907T080100
DTEND:20260907T084600
SUMMARY:Math
END:VEVENT
BEGIN:VEVENT
UID:off-b
DTSTART:20260907T101100
DTEND:20260907T105600
SUMMARY:Physics
END:VEVENT
```

**实际结果**：立即抛出 `UID off-a.DTSTART: time does not match a period boundary`。第二个事件与第一个事件的结束端点都没有诊断。

**应有结果**：收集所有实际出现的匹配失败，至少包含两个 UID 的起止字段；统一返回契约错误、CLI 退出 2、不发布暂存。学校作息与日历源有系统性偏差是日常输入问题；只让用户每次修一个端点重跑不符合已审定规则。不需要显示教师、地点等被丢弃的信息。

### 合成复现命令

在仓库根目录运行 `py -3.12 -B -`，输入下面的 ASCII 脚本即可复现 R1、R2。全部数据来自测试夹具与脚本创建的临时文件；隔离检查使用已有测试的脱离仓库状态模拟。

```python
import io, tempfile
from pathlib import Path
from datetime import date
from contextlib import redirect_stdout
from unittest.mock import patch
from tests.contract.test_timetable_io_port import _workspace, _detached_isolation
from ky.timetable_io import import_ics, read_staging

valid = (
    'BEGIN:VEVENT\r\nUID:valid\r\nDTSTART:20260907T080000\r\n'
    'DTEND:20260907T084500\r\nSUMMARY:Math\r\nEND:VEVENT\r\n'
)
cancel = (
    'BEGIN:VEVENT\r\nUID:cancel\r\nDTSTART:20260907T080000Z\r\n'
    'DTEND:20260907T084500Z\r\nSTATUS:CANCELLED\r\n'
    'SUMMARY:Ignore\r\nEND:VEVENT\r\n'
)
excluded = (
    'BEGIN:VEVENT\r\nUID:utc\r\nDTSTART:20260907T080000Z\r\n'
    'DTEND:20260907T084500Z\r\nRRULE:FREQ=WEEKLY;COUNT=2\r\n'
    'EXDATE;TZID=Unknown/Zone:20260914T080000\r\n'
    'SUMMARY:Math\r\nEND:VEVENT\r\n'
)
for name, body, zone in [('R1', valid, None),
                         ('R2-A', valid + cancel, None),
                         ('R2-B', excluded, 'UTC')]:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        workspace, _, school = _workspace(root / 'fixture')
        source = root / 'input.ics'
        source.write_bytes(('BEGIN:VCALENDAR\r\nVERSION:2.0\r\n' + body
                            + 'END:VCALENDAR\r\n').encode())
        original = Path.read_bytes
        reads = []
        def counted(path):
            if path == school:
                reads.append(path)
            return original(path)
        try:
            with patch.object(Path, 'read_bytes', counted), redirect_stdout(io.StringIO()), \
                    patch('ky.timetable_io.ics_import.inspect_isolation', _detached_isolation):
                target = import_ics(workspace, source, school='demo', label='candidate',
                                    week1=date(2026, 9, 7), timezone_name=zone)
            staged, _ = read_staging(target)
            print(name, 'school_reads', len(reads),
                  'weeks', sorted(staged.semester.courses[0].weeks))
        except Exception as exc:
            print(name, type(exc).__name__, str(exc))
```

R3 可用同一脚本，将 body 换成前述两个事件、zone=None。实际执行得到的首错与上文相同。

## 建议改

1. **补齐任务书已有的验收项**。新增用例确实断言了周集合、覆盖后的星期、重复 UID、空日历、切段时刻、错误路径及字节一致性，并非普遍只断言能跑。但还没有看到：三个独立逐次事件合并的用例；孤立覆盖、THISANDFUTURE、同实例重复覆盖及 EXDATE/覆盖冲突的明确用例；空导入结果不发布；有效 TZID 输入；TRANSP、CATEGORIES 与浮动时间的断言。重复导入测试断言第二次退出 0，没有直接比较暂存字节或发布次数。实现者报告对部分覆盖的表述强于测试证据。
2. **联合逐日基数测试**。新增 `TimetableIOBaseResolverTests` 只检查某阶段内的 210 与阶段外配置回落；建议补任务范围内的公用预览跨阶段分钟和路线只读一次断言。当前代码调用顺序正确，合成预览实测为 `160 210 210 120 120 120 120`：首日有课扣减/空档封顶，周四开始基数变为 120。导出物理空档通常不随基数改变，不能仅比较导出字节来证明基数解析已接上。
3. **保留待确认提示**。PDF 原网格的标题、节次 `*` 标记被公用网格替换；此次统一网格是明确授权的整合，但公用网格没有 `unconfirmed` 标记。建议保留学校档案已有的待确认标识，避免显示具体时刻而丢掉不确定性提示。当前 M29 规格未单独强制此标识，不作阻断。
4. **小范围整理**。`preview.py` 模块头应补公开 `base_resolver`，为 config 参数加类型；删除 `ics_import.py` 的未使用 `school_id = None`。`ics_export._publish` 有重复 mkdir，首次 mkdir 在 I/O 转契约错误的 try 外；CLI 会捕获 OSError，但公开端口的异常形式可统一。
5. **合并状态收口**。检查时 `ky/__main__.py` 工作文件没有冲突标记，相关 CLI 测试能正常导入、运行；但索引仍为 `UU`，其余整合文件有 `MM`/`AM`。因此这是工作文件结果的评审，并不意味着暂存区已经完整包含整合。由决策者修完、重新暂存并结束合并；本轮未替其操作 Git。

## 不改与逐条判断

| 项目 | 裁定与证据 |
|---|---|
| ICS 原始字节及源摘要 | 源文件一次 read_bytes，解析与 sha256 使用同一份字节。保留 |
| WEEKLY 与有限展开 | 支持字段集合、COUNT/UNTIL 互斥、无终止必须给 weeks；投影截止、本地半开域检查、覆盖移出域拒绝均符合规则。COUNT、INTERVAL、BYDAY、UNTIL、多个 EXDATE 已有实质测试 |
| 覆盖与 DURATION | 原实例身份、取消/移动、缺省 SUMMARY/时长、每实例重新计算结束时刻的设计正确；EXDATE 与覆盖同指实例会成为孤立覆盖并拒绝。测试缺口不等于已确认算法失败 |
| 节次与周次 | 保留秒级精确匹配、不猜容差；本地日期决定星期/周次；同组同周重复拒绝、候选引用验证正确。汇总诊断按 R3 修 |
| 导出课程分段 | 同大节且间隙无 free_segments 正长度交集才合并；classes-only 仍取完整 DaySchedule。N5 的长空档测试断言两个精确课程区间，满足要求 |
| 日历身份及字节 | 规范 JSON 哈希、同身份组 index、排序、浮动 DTSTART/DTEND、固定 DTSTAMP、TRANSP/CATEGORIES 均按契约实现；重复课程 UID 及类别过滤稳定性有断言。相同输入导出字节实测测试通过 |
| 空覆盖与空选择 | 无覆盖拒绝且不写；有覆盖但课程类别为空输出合法空日历。均有结果断言 |
| 隔离与发布 | 复用 IO1 公开检查；最终目标与真实临时路径分别检查；临时文件重读后 os.link 不覆盖发布。提前 exists 检查并非最终发布依据，没有使用 exists 后 replace 的错误模式 |
| 公用基数解析 | 路线 current 在 resolver 构造时读一次，返回闭包逐日调用 M8；网格之后的每日分钟、导出的 DaySchedule 都使用逐日基数。未复制 M8 算法 |
| M28 接缝 | 当前 M28b 的路线阶段基数已正确接入。`pacing_initial=None` 的接线限制在 docstring 明示由 M28c 完成；本轮不能声称已支持登记复盘 initial，但不要求提前实现下一包 |
| CLI 冲突整合 | 工作文件保留 import-pdf、restage/apply、show/check，并新增 import/export；PDF config 参数已传给公用预览。反向区间退出 3，契约错误退出 2 的正常路径成立 |
| 依赖 | pyproject 新增三项与 §7 完全一致：icalendar>=7,<8、python-dateutil>=2.8,<3、tzdata。没有重新安装或联网 |

实现者四处选择均可保留：浮动时间不因传 timezone 而转换；学习事件分钟取物理段时长；每个无终止规则各记一条备注；未支持的 RFC 扩展明确拒绝。第三项即使备注文本相同也不影响课表身份；第四项不应作为漏检其他时区字段的理由。

D7：模块头、具名步骤与函数拆分总体清楚；生产改动未发现跨业务模块 import 私有名或按错误消息文本分支。新 ICS 逻辑限定在新子命令，未把解析规则塞入 M18。AGENTS 已知缺陷中第 1、3、4、5、8 条未发现本轮新增阻断问题；第 2 条见 R1；第 6 条的畸形外部输入见下节；第 7 条未见旧命令业务分支的非授权改写，PDF 预览格式变更及索引状态已单列。

## 安全登记

**畸形 ICS 混合浮动/UTC 起止会逃逸 TypeError。** 合成事件写 `DTSTART:20260907T080000Z`、`DTEND:20260907T084500`，传目标时区 UTC，`_duration` 的 `end - start` 实测抛 `TypeError: can't subtract offset-naive and offset-aware datetimes`。CLI 没有捕获该异常，可能 traceback。该输入混用起止时间域，不是正常受支持的日历事件；未证明正常导出工具会产生，按威胁模型作为畸形输入登记，不增加本轮阻断项。可在将来的加固中统一验证起止时间域、包装解码/运算异常为带 UID/字段的 ContractError。

没有探测恶意链接、跨进程插手或个人文件；不为其增设本轮返工。

## 验证记录

运行 `py -3.12 -B -m unittest tests.contract.test_timetable_io_port`：**30 tests，OK，5.148s**。使用禁止写 pyc 的环境运行合成探针，复现 R1–R3；PDF 接缝探针只 mock 提取层与课程映射，不读任何 PDF。逐日预览探针通过。`git diff --check` 无输出；工作文件冲突标记检索无命中。

未跑全量，未运行个人 PDF 测试，未修改实现、测试或其他报告，未提交。关闭 R1–R3 后可对这些修复及受影响的单个模块作定点复审。
