# 第 237 轮任务书：WP-IO2 ics 导入 + 导出到日历（gpt-6-luna，续 luna-c，独立 worktree `F:\workspace\kaoyan-wt-io2`）

> worktree 基于 master `8f97c50`（IO1 已提交，含 sol 236 的修正）。主仓库里决策者正在合并 ④b-2 的 PDF 适配器（`ky/timetable_io/zfsoft_pdf.py`、`import-pdf`），
> 你不要创建或修改这两处；合并时由决策者处理 `ky/__main__.py` 的冲突。
> **预览**写成公开函数（例如 `ky/timetable_io/preview.py` 的 `preview_lines(workspace, semester, config_path=None) -> tuple[str, ...]`，输出第 1 周课程网格，能解析基数时附每日分钟），`import-ics` 调用它；决策者合并时让 `import-pdf` 也调用它。

## 背景

规格 `contracts/timetable_import.md` §4（ics 导入）、§6（导出）、§7（依赖），以它为准。IO1 已提交：用 `ky.timetable` 的公开入口
（`semester_from_mapping`、`semester_to_mapping`、`load_referenced_schools`、`validate_semester_references`、`build_calendar`、`timetable_from_mapping`）
与 `ky.timetable_io` 的 `inspect_isolation` / `check_isolated_path` / `publish_staging` / `StagedSemester`，**不 import 任何 `_` 开头的名字**。

## 要做的

1. `pyproject.toml` 加 `icalendar>=7,<8`、`python-dateutil>=2.8,<3`、`tzdata`；本机 `py -3.12 -m pip install "icalendar>=7,<8" "python-dateutil>=2.8,<3" tzdata`。
2. `ky/timetable_io/ics_import.py`：规格 §4 的 12 步，每步一个有名字的函数；日期口径与覆盖规则照规格。以下口径钉死（sol 227 细节）：
   - 域比较一律半开：`week1 <= 本地日期 < week1 + 7N`，"晚于域末" = `>= 域末日`。自动截断只用于无终止规则自然展开的额外实例；被覆盖移出域外的实例按拒绝处理（优先于截断）。
   - `EXDATE`、`RECURRENCE-ID` 与实例身份在原时间域中比较（值与类型都相同才算同一实例）；起止倒置、非法类型组合、无法解析的 `TZID` → 违约；不截秒、不猜时区。
     覆盖事件的 `DTSTART` 类型须与主事件一致；主事件在第 3 步被剔除时，它的覆盖事件一并进 `notes`（不当作孤立覆盖）。
   - 预览基数：个人课表已登记时，基数经 M8 同一解析（`daily_base_minutes` 的现有签名），配置取 `--config`，缺省读注册表 `settings.exam_config`；
     两者都没有 → 只打印课程网格、不打印分钟。
3. `ky/timetable_io/ics_export.py`：规格 §6。课程事件合并条件钉死：节间隙为 `[上一节.end, 下一节.start)`，与某个 `free_segments` 有**正长度交集**才算"有空闲时段"，
   端点相接不算；用当天完整 M18 结果判断（`--classes-only` 时也一样）；分段之后再定 UID 身份组。导出基数同上。
4. CLI：`ky timetable import-ics …`、`ky timetable export-ics …`（参数照规格；用法错误 3，契约 / I/O / 隔离失败 2，成功 0）。
5. 测试（`tests/contract/test_timetable_io_port.py` 追加；全部合成 `.ics` 文本，不含个人数据）：
   规格 §8 中 ics、export 两部分；sol 第 225 轮报告 §二表格每一行一例；sol 第 226 轮 N3（UTC 前一日按本地日期接受、覆盖移出域外拒绝、全天事件不参与域检查）
   与 N5（大节内长空档分两段）；S3（UID 同身份组序号、空选择写空日历）；S4（重复实例结束时间、`DTEND` 与 `DURATION` 并存拒绝）；
   同一输入两次导入字节相同且第二次退出 0；导出同一输入逐字节相同。

## 不做

正方 PDF（④b-2 另派）；不改 M18 计算与 IO1 已有行为；不改 `kaoyan.workspace.yaml`、个人数据、`docs/模块地图.md`。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_timetable_io_port tests.contract.test_timetable_port tests.test_cli
```

报告 `review/rounds/round-237-m29-io2-luna.md`：改动、做法、测试输出原文、"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"、歧义与选择。报告与测试不得含个人数据。
