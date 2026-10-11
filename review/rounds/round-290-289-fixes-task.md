# 第 290 轮任务书：复验 289 的两条必须改（gpt-6-luna，窗口 luna-fix-289，新会话）

来源：独立复验 `review/rounds/round-289-recheck-sol61.md`（FAIL）。11 条里 10 条已确认修好，
只有下面两条要改。**只改这两条**，其它一律不动。

## M1 / MAJOR：记录写入仍重复读取旧来源

位置（sol 给的代码位置）：`ky/storage/day_plan_store.py:532` 没把已加载的来源传给写端；
`ky/storage/review_shards.py:630` 再读 manifest，`:646`、`:661` 再读旧 manifest 与旧分片（分片自身又读字节与 YAML）。

sol 的复现：合成两条同科 progressing 项、空登记索引 / 权重、知识树与前一日事件，次日 `record_day` 提交两项 correct；
计数 `Path.open` 读模式 → 旧 manifest 与两个旧分片各 **3** 次（索引 / 权重 / 树各 1 次）。
复现脚本在系统临时目录 `round289_probe.py` 的 `source_counts()`（若已不在，就自己合成等价输入）。

要求：**已加载的队列来源继续贯穿到实际存储写入所需的"旧状态比较"**；M33 的单次 `record` / `advance`
不再重开旧来源；保留旧调用方行为（缺省参数仍自行读取）；**临时输出的写完重读校验不算重复读输入**。
判据：原 C-M1 与 `AGENTS.md` 已知缺陷 #2。
注意：`record` 的 CLI 输出与写出文件必须与固定基线 `60a4fd2` 逐字节一致（`tests/contract/test_today_port.py`
的固定矩阵，例外只有 `contracts/today.md` §6 明写的两处）；公开映射字段一个都不能变。

## M2 / 验收必改：停用提示的基线例外放得太宽

位置：`tests/contract/test_today_port.py:609-636` 的 `_assert_only_retire_hint_differs`。
它只断言 old/new 里各含一个子串，然后**整行**用 old 替换 new——于是同一行里日期、题号、命令文字、
行尾等任何差异都会被放过。sol 的反例：把日期从 `2026-10-01` 改成 `2099-01-01` 的同时换占位符，helper 仍然通过。

要求：断言必须**精确**——`new_line` 恰好等于 `old_line` 把指定片段
（`--reason <原因>` → `--reason "替换为原因"`）替换后的结果，其余字节（题号、日期、命令前缀、换行）仍逐字节比较；
不能只查子串。改完在报告里给出"合法替换通过 / 日期改动被拒"两条实测证据。
允许的差异仍然只有 `contracts/today.md` §6 写的那两处，不要放宽。

## 不要做

- 不动其它模块（`ky/web/`、`ky/charts/`、`ky/question_bank/`、`ky/timetable_io/`、`ky/today/port.py` 的业务逻辑）；
  除非 M1 必须动到 `ky/today/record.py` 的传参，就只做传参本身。
- 不做顺手重构、不加新功能、不改规格里没写的输出文字。
- 不跑全量、不提交（提交由决策者做）。

## 验收（只跑这些 + 两条探针）

```
py -3.12 -m unittest tests.contract.test_today_port
py -3.12 -m unittest tests.contract.test_day_plan_store_port
py -3.12 -m unittest tests.test_review_queue_advance
py -3.12 -m unittest tests.contract.test_freeze_port tests.contract.test_resume_port
py -3.12 -m unittest tests.test_cli
```

探针：(a) M1 修复前后 `Path.open` 读模式计数（旧 manifest / 每个旧分片都应是 1，索引 / 权重 / 树 1）；
(b) M2 的合法替换通过与日期改动被拒。

## 报告

写 `review/rounds/round-290-289-fixes-luna.md`，≤ 70 行：逐条 M1 / M2 的改法（`文件:行` 与为什么）、
两条探针的前后输出、五条验收命令的 `Ran ... OK` 原文、"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"、
怀疑受影响但没跑的模块、未做 / 没把握的地方。

## 规则（照 `AGENTS.md`）

- 模块头写 M 编号与规格；行宽 ≤ 100；函数 ≤ 约 60 行；注释引用 sol 289 M1 / M2。
- 含中文的文件只用编辑工具写；写完查有没有连续 `???`。
- 临时输入放系统临时目录；不读 `data/personal/`；设 `PYTHONDONTWRITEBYTECODE=1`。
