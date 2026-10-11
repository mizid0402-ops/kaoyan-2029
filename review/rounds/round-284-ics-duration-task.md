# 第 284 轮任务书：坏 ICS 的 DURATION 要变成契约错误（gpt-6-luna，窗口 luna-fix-ics，新会话）

## 来源

最终大检查 A（`review/rounds/round-281-final-a-sol61.md`）的必须改 M1，决策者已按代码位置复核：
`ky/timetable_io/ics_import.py:79-80` 里 `elif duration is not None: result = duration.dt`
直接读依赖库属性；`DURATION` 是坏值时库抛 `BrokenCalendarProperty`，一路漏到 CLI，
用户看到英文库报错、退出码 3（用法错误），而不是带字段路径的契约错误、退出码 2。
注意同一个函数里的 `_date_property`（:56-62）已经在做这件事，照它的写法来。

复现输入（任务书原文）：

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

命令：`py -3.12 -B -m ky timetable import-ics cut-duration.ics --school demo --label term --week1 2026-09-07 --workspace <合成注册表>`
实测：退出 3，只打印库的 `Cannot access 'dt' on broken property 'DURATION'`，未发布暂存文件。

## 要做

1. 在 `ky/timetable_io/ics_import.py` 的 DURATION 解码处把异常转成 `ContractError`，
   错误里带**文件内的字段路径**（照 `_date_property` 的样子，例如 `UID cut-duration.DURATION`）。
   用同文件已有的措辞与错误形状，不要发明新格式。
2. CLI 侧应退出 **2**（契约错误），不是 3。
3. 只加**一条**回归测试（放 `tests/contract/test_timetable_io_port.py`，照该文件既有夹具与命名风格）：
   坏 DURATION 的合成 ics → 抛 `ContractError`（不是库异常）、错误文本含字段路径、不发布暂存文件。
4. 另外确认这些形态行为不变（不必新增测试，报告里写结论即可）：缺 DURATION、DTSTART+DTEND 与 DURATION 同时出现、
   DURATION 为负或零、`P0D`。只有"坏值"这一条应当新增报错路径。

## 不要做

- 不改导入范围、不动 ics 其他字段、不动 M18 日历、不动导出、不动 PDF 适配器。
- 不跑全量、不做顺手重构、不提交（提交由决策者做）。
- 不写任务书没要求的测试。

## 验收（只跑这两条 + 一条复现命令，把输出原文贴进报告）

```
py -3.12 -m unittest tests.contract.test_timetable_io_port
py -3.12 -m unittest tests.contract.test_timetable_port
```

第三条：把上面的复现命令改成断言"退出码 2 且错误文本含字段路径"，贴实测输出。

## 报告

写 `review/rounds/round-284-ics-duration-luna.md`，≤ 60 行：改了什么（`文件:行` + 为什么）；
复现输入修复前后的实测输出（退出码 + 关键行）；两条验收命令的 `Ran ... OK` 原文；
"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"；你怀疑受影响但没跑的模块名；未做/没把握的地方。

## 规则（照 `AGENTS.md`）

- 含中文的文件只用编辑工具写；写完查有没有连续 `???`。
- 行宽 ≤ 100；函数 ≤ 约 60 行；注释写"为什么"并引用 M29 / sol 281 M1。
- 模块头 docstring 保持 M 编号与规格引用（`contracts/timetable_import.md`）。
- 临时输入放系统临时目录，别写进仓库；设 `PYTHONDONTWRITEBYTECODE=1`。
