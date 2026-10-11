# 第 249 轮：WP-IO2 定点复审

结论：**FAIL**。第 246 轮 R1–R3 的原反例均已关闭，但返工把两项既有的无条件格式检查移到了保留事件分支，导致被剔除事件绕过校验（N1）。恢复这两项检查后可以收尾合并；不要求扩大功能或安全防护范围。

本轮检查了 `git diff --cached`、`git diff`、返工任务书与实现报告末节；只评审本轮返工及辅助函数拆分。没有联网、读取仓库外原有文件或个人 PDF，只新增本报告。

## 必须改

### N1：剔除事件的改动绕过了既有互斥检查与起止类型检查

位置：`ky/timetable_io/ics_import.py` 的 `_excluded_masters`。

工作区 diff 明确显示：原先位于剔除判断之前的两项检查，现在都放进了 `else`，只对未被剔除的主事件执行：

- 同时有 `DTEND` 与 `DURATION` → 违约。
- `DTSTART` / `DTEND` 一个是日期、一个是日期时间 → 违约。

`contracts/timetable_import.md` §4 第 3 条明确规定这两种形状违约，不自动修复。R2 要求的是剔除后再查时区，不是删除剔除前的格式检查。

**可复现输入 A**：一个正常浮动课程，加一个 `DTSTART;VALUE=DATE:20260907`、`DTEND:20260907T084500` 的事件。

**可复现输入 B**：同一个正常课程，加一个取消主事件，该事件同时含 `DTEND:20260907T084500` 与 `DURATION:PT45M`。

**实测结果**：两种输入均成功发布；只留下正常课程，异常主事件被记一条忽略备注。应有结果是带异常 UID 的 ContractError，CLI 退出 2，不发布暂存。

这两例本身是畸形输入，未证明正常导出工具会生成。本项仍要求恢复，依据是 AGENTS.md 明文要求“**已有的安全防护保留，不删、也不必再扩展**”，以及本规格已有的明确检查；不是新增防畸形输入要求。修法只需把这两项原有检查恢复到剔除判断之前，时区检查仍留在剔除之后。

当前旧测试只单独输入日期/日期时间混用事件，断言得到某个 ContractError；现在它因“没有可导入课程”报错，仍然通过。加一个正常课程后才能暴露该回退。

**复现命令**：仓库根目录执行 `py -3.12 -B -`，输入以下 ASCII 脚本。只使用合成临时工作区。

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
cases = {
    'mixed-types': (
        'BEGIN:VEVENT\r\nUID:mismatch\r\nDTSTART;VALUE=DATE:20260907\r\n'
        'DTEND:20260907T084500\r\nSUMMARY:Ignore\r\nEND:VEVENT\r\n'
    ),
    'cancelled-both': (
        'BEGIN:VEVENT\r\nUID:cancel-both\r\nDTSTART:20260907T080000\r\n'
        'DTEND:20260907T084500\r\nDURATION:PT45M\r\n'
        'STATUS:CANCELLED\r\nSUMMARY:Ignore\r\nEND:VEVENT\r\n'
    ),
}
for name, bad in cases.items():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        workspace, _, _ = _workspace(root / 'fixture')
        source = root / 'input.ics'
        source.write_bytes(('BEGIN:VCALENDAR\r\nVERSION:2.0\r\n' + valid + bad
                            + 'END:VCALENDAR\r\n').encode())
        with patch('ky.timetable_io.ics_import.inspect_isolation', _detached_isolation), \
                redirect_stdout(io.StringIO()):
            target = import_ics(workspace, source, school='demo', label='candidate',
                                week1=date(2026, 9, 7))
        staged, _ = read_staging(target)
        print(name, 'PUBLISHED', len(staged.semester.courses),
              'notes', len(staged.notes))
```

实际两行均为 `PUBLISHED 1 notes 1`。

## R1–R3 与建议项复审

| 项目 | 判定与证据 |
|---|---|
| R1 学校只读一次 | 关闭。`preview_lines(..., schools=loaded)` 复用对象，独立预览才加载。ICS 与 PDF 两个入口均已传入映射；新增测试断言学校读一次，PDF 只 mock 字节提取层并走真实规范化/预览 |
| R2 剔除后检查时区 | 原缺口关闭。active 集合排除剔除主事件及其覆盖；“有效浮动课 + UTC 取消主事件，不给 timezone”实测成功。其余原有格式检查的回退见 N1 |
| R2 EXDATE | 原缺口关闭。检查每个属性的 TZID 和每个值；原先成功错收的未知 TZID 输入现在为 `UID utc.EXDATE.TZID` 契约错误，实际暂存目录为空。额外合成 WEEKLY COUNT=4、一个 EXDATE 属性含两个 UTC 值、另一个属性带 TZID=UTC，实测只保留第 1 周 |
| R3 失配汇总、不发布 | 关闭。第 246 轮两个 UID、四个失配端点全部出现在一次 `VEVENT.periods` 契约错误中，含字段、日期、时刻；实际 `staging/timetables/*.yaml` 无文件 |
| 辅助函数拆分 | 可保留。`_period_mismatches` 负责端点诊断，`_event_summary` 负责覆盖摘要优先及空白校验；调用位置仍在原流程位置，失配收集后 continue、最后统一报错。现有取消/移动覆盖测试通过，未发现拆分引入行为变化 |
| 新增正常结果测试 | 有实质断言：逐次事件周集合 `{1,2,3}`；重复导入同路径/同字节、发布结果 `[True, False]`；有效 TZID 的星期；课程 OPAQUE、学习段 TRANSPARENT/STUDY、浮动起点；跨阶段预览分钟及路线 current 调用一次 |
| 拒绝路径测试 | 已加入孤立覆盖、THISANDFUTURE、重复覆盖、EXDATE/覆盖冲突和空导入的拒绝用例。未发布断言的路径问题另列建议，不把该断言误当成有效证明 |
| 待确认标记 | 正确。公用网格恢复 `*`，PDF 接口与公用预览均有针对标记的断言 |
| 清理 | 正确。公开接口说明与 config 类型补齐；未用的 school_id 赋值删除；导出 mkdir 只有一次且进入 I/O 转契约错误的 try |
| 混用浮动/UTC 起止 | 已修。比较时区有无后报 `UID mixed.DTEND` ContractError，不再进行导致 TypeError 的减法；新增测试验证错误类型和字段路径 |

第 246 轮关于逐日基数、导出切段、身份/确定性、依赖的非阻断结论不重开。本次返工没有修改其业务规则。当前三个 IO2 生产文件 AST 检查未发现超过 60 行的函数或超过 100 字符的行。

## 建议改

1. **纠正“不发布”断言的目录**。新增多个测试使用 `(root / "fixture" / "staging").glob("*.yaml")`，实际发布在 `staging/timetables/`，因此该断言即使成功发布也可能通过。改查真实子目录、使用 rglob，或断言 publish_staging 未调用。本轮已独立检查真实子目录，确认 R2 未知 TZID 与 R3 失配不会发布；实现结论不依赖错误断言。
2. **消除重复忽略备注**。`_excluded_masters` 与 `_instance_rows` 各为被剔除主事件的覆盖追加一条同义备注。合成“正常课程 + 取消主事件 + 该 UID 的取消覆盖”实测 notes 数为 3，其中两条重复说明覆盖被忽略。选一个位置记即可；不会影响课程集合或暂存哈希，不作阻断。
3. **简化 EXDATE 校验循环**。`fields.extend(["EXDATE"] * len(exdates))` 后，每个 EXDATE 字段循环又遍历全部 exdates，k 个属性被重复检查 k 次。将 EXDATE 作为一个字段处理即可；当前没有漏检，但重复遍历不利于阅读。
4. **修正辅助函数标注**。`_period_for_time` 现在可能返回 None，返回类型仍为 int，且 uid/field 参数已不使用。标为 `int | None` 并清理无用参数即可，不改变汇总逻辑。

## 不改 / 合并条件

无需为了本次复审重跑全量、重审未变的 IO1/IO3 算法，或增加新的功能。学校映射复用的公开参数设计清楚，保留独立预览能力；两辅助函数拆分符合 D7。

**目前不能作为通过评审的结果收尾合并**，需先恢复 N1 的两项既有检查。检查时 `ky/__main__.py` 索引仍为 UU，整合/返工内容仍有 MM、AM：这只是尚未结束的合并状态，不另判实现失败。修复后由决策者统一暂存并结束合并，本轮没有操作索引或提交。

## 安全登记

第 246 轮登记的混用浮动/UTC 起止 TypeError 已有修复和测试，本轮可标记已处理。N1 是既有防护被回退，按“保留已有防护”的明确规则要求恢复，不新增安全加固范围。未发现需要另立返工的其他安全项；未探测恶意链接或并发插手。

## 验证记录

- `py -3.12 -B -m unittest tests.contract.test_timetable_io_port`：**39 tests，OK，5.314s**。
- 合成探针：R1 学校读取 1 次；R2 原误拒输入成功；未知 EXDATE TZID 拒绝且不发布；多个 EXDATE 值全部生效；R3 汇总四个端点且不发布；N1 两种输入错误发布。
- `git diff --check` 无输出。没有运行实际 PDF 测试，没有跑全量，也未把实现者报告的其他模块历史结果冒充本轮独立验证。

只新增本报告；未修改代码、测试或其他文件，未提交。
