# 第 287 轮任务书：M33 来源一次读取 / 冻结阶段 / 全停用提示 / 模块头（gpt-6-luna，窗口 luna-fix-today，新会话）

来源：最终大检查 C（`review/rounds/round-283-final-c-sol61.md`）的 M1、M2、M4，与大检查 B
（`review/rounds/round-282-final-b-sol61.md`）的 M3。**逐条做，不要混在一起改。**

## C-M1 / MAJOR：来源快照没有贯穿今日计算与记录

位置：`ky/today/port.py:85`、`:173`、`:183`；`ky/today/questions.py:38`、`:54`；`ky/today/record.py:127`。

sol 的复现：合成队列放两个同科 progressing 项、登记该科树 / 真题索引 / 权重、当天已有完成事件；
计数 `Path.open` 的读模式后调用 `load_today` → 索引与权重各读 **2** 次、manifest **2** 次、
每个队列分片 **2** 次；树由出题计算现读，不是已加载参数。

要求：装配阶段**一次读取**并把上下文传下去（队列含已计算 ID、树 / 祖先关系、索引、冻结与复盘报告）；
M24 与记录计算走**已加载**的公开入口；复盘 helper 不再拿路径现读；预检 / 锁存 / 推进复用同一份来源。
写完临时输出后的"重读校验"**不算**重复读输入。判据：`contracts/today.md` §2/§3 + `AGENTS.md` 已知缺陷 #2。

硬约束：公开映射（`schema_version: 1`）的字段与值**一个都不能变**；`tests/contract/test_today_port.py`
的固定基线矩阵（对 `60a4fd2` 逐字节）必须保持通过——注意它现在有**一处明文例外**：停用提示行的原因
占位符带引号（`contracts/today.md` §6），那是刚修的，别去动它。函数仍要 ≤ 约 60 行，拆成有名字的 helper。

## C-M2 / MAJOR：冻结发布后的清理错误丢失持久化阶段

位置：`ky/storage/day_plan_store.py:220`；`ky/today/record.py:51`、`:53`。

sol 的复现：正常积压触发冻结，只在 freeze 目录临时文件的 `Path.unlink` 注入 `PermissionError`；
`record_day({}, study_minutes=5)` → stage=`rejected`，而磁盘上真实冻结事件 **1** 条、完成事件不存在。

要求：`os.link` **已发布之后**的清理失败，必须仍然报 `freeze_written`（或把发布后的残留清理按可恢复清理处理）。
**不许靠错误消息文字判断阶段**（`AGENTS.md` 已知缺陷 #3）。

## B-M3：全停用分支的输出优先级

位置：`ky/today/questions.py:73-80`。

sol 的复现：活动项 interval=7、登记空真题索引、自己唯一改编题已 retire → `ky review-questions --json`
输出"缺题（该点改编题已全部停用）"且**没有** `generation_command`。

要求：`learned` 与 `progressing` 两档在"自己的改编题全被停用"时都应提示"先生成"、注明已全部停用、
并给出生成命令（`contracts/question_bank.md` §5 末尾与 §6a）。

## C-M4 / 规则必改：模块头缺公开接口列表

位置：`ky/today/port.py:1`。要求列出 `load_today`、`today_view_hash`、`record_day`、`advance_recorded_day`
（`AGENTS.md` D7 的模块头要求）。不改行为。

## 不要做

- 不动 `ky/web/`（另一包在改）、不动 M31 选题算法、不动 M30。
- 不顺手做"建议改"（恢复命令绝对路径、深色视觉验证）。
- 不跑全量、不提交。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_today_port
py -3.12 -m unittest tests.contract.test_freeze_port tests.contract.test_resume_port
py -3.12 -m unittest tests.test_cli
```

另外两条探针：C-M1 给"每个来源只读一次"的计数输出（修复前 / 修复后）；C-M2 给注入 `PermissionError`
前后的 stage 对照。

## 报告

写 `review/rounds/round-287-today-fixes-luna.md`，≤ 80 行：逐条 C-M1 / C-M2 / B-M3 / C-M4 的改法（`文件:行` 与为什么）、
探针修复前后输出、三条验收命令的 `Ran ... OK` 原文、"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"、
你怀疑受影响但没跑的模块、未做 / 没把握的地方。

## 规则（照 `AGENTS.md`）

- 模块头写 M 编号与规格（`contracts/today.md`）；行宽 ≤ 100；函数 ≤ 约 60 行；注释引用 sol 283 M1/M2/M4、sol 282 M3。
- 含中文的文件只用编辑工具写；写完查有没有连续 `???`。
- 临时输入放系统临时目录；不读 `data/personal/`；设 `PYTHONDONTWRITEBYTECODE=1`。
