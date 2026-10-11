# 任务书：D11 补充实现 —— 过期 `scheduled` 计入冻结积压（窗口 `luna-c`，新会话）

先读 `AGENTS.md` 全文（尤其"迁移 / 重构不得改变输出"第 11–13 条与 12a、"已知缺陷清单"第 2、3、6、7 条），
然后读定稿细则：`docs/阶段2.5-接缝收口.md` D11 一节末尾"D11 补充：过期 `scheduled` 计入积压"（R1–R9），
以及两轮细则审查 `review/rounds/round-186-d11-scheduled-rules-review-codex.md`、
`review/rounds/round-187-d11-scheduled-rules-v2-review-codex.md`（第 187 轮"不改"一节列了每个入口的现状与行号，"实现包应定点验证的边界"是你的测试清单）。

基线：本轮改动前的 master 提交哈希由决策者在派发时给出为 **`BASELINE`**（见文末），所有固定对照用它，**不得用 `HEAD`**。

## 要改（按模块）

1. **M27 `ky/freeze/port.py`**：`overdue_review_items` 按 R1 改口径（它是冻结与 resume 共用的公开判定）。docstring 与 `contracts/freeze.md` 同步。
2. **M27 `ky/freeze/resume.py`**：R3——过期 `scheduled` 与过期 `queued` 同样分层、同样摊开；被赋新到期日时状态改 `queued`，
   `revision` 不变；其它字段按既有重排。R9 的提示行（`--dry-run` 用"其中 N 项将由 scheduled 转为 queued"，正式执行用
   "其中 N 项已由 scheduled 转为 queued"）只在 N > 0 时打印。JSON 若加字段，只能在 N > 0 时出现，并在 `contracts/freeze.md`
   固定字段名与含义（"本次计划的转换数"）；该映射若也写进恢复事件，规格里写明。你选加或不加，报告说明理由。
3. **M12 `ky/schedule/state_snapshot.py`**：`backlog_minutes` 用 R1 口径（**调用 M27 的公开判定**，不要复制一份条件）；`due_today` 不变。
   同步 `contracts/state_snapshot.md`。M15 `ky/projection/status.py` 复用 M12 / M27，确认随之同口径并同步 `contracts/projection_status.md`
   （投影 schema 仍为 4：这是统计口径变化而非投影表的填充规则变化——如果你认为它改变了某个已存列的填充，停下来写进报告，不要自行升 schema）。
4. **preflight 文本（R4）**：仅当冻结判定计入了过期 `scheduled` 时，冻结段多打印一行，说明"其中 N 项（M 分钟）为已过期的 scheduled
   （M9 列为 unreachable），已计入冻结积压；下方 deferred → backlog 只计本次裁剪延期"之类（措辞你定，意思要全）。JSON 不加字段。
   同步修正 `ky/__main__.py` 里 `unreachable` 的注释（现称"不属于 backlog"）与 `--freeze-backlog-days` 帮助文字（现称 queued overdue）——
   **注意**：帮助文字属于用户可见输出，改它会改变 `ky preflight -h` 的字节；这是本轮明文允许的差异，报告里列出前后对照。
5. **R7 写前校验**：`day-plan record` 与 `day-plan submit --plan` 在追加冻结事件之前，在**冻结判定读取的同一份注册队列对象**上，
   用公开校验器（`ky.models.validate_items_against_config` 或其公开等价物）校验本次纳入的过期 `scheduled` 候选；配置外 / 停用科目 →
   契约错误、**退出 2**、不写冻结事件 / 计划 / 完成记录 / 队列。不要只校验 `--review-store`，不要为校验再读一次队列（已知缺陷第 2 条）。
   `_day_plan_record_freeze` 现在只捕获 `StorageError`，要让 `ContractError` 也变成退出 2，不留 traceback。
   `ky resume` 的既有全队列校验保留（用测试证明它仍在写前拒绝）；`submit --from-staging` 已由 M9 校验（用测试证明）。
6. **R8** 写进 `contracts/freeze.md`：只影响阈值，低于阈值时仍 `unreachable`、可手动 `ky resume`。

## 测试

新增 `tests/contract/test_freeze_scheduled_backlog.py`，覆盖第 187 轮"实现包应定点验证的边界"四条全部（D−1 / D / D+1 的 `scheduled` 混合
`queued` / `retired` / `suspended`；阈值等号、空积压、锁存后已清空；M12 / M15 / M27 同日同输入一致而 M9 桶与延期数不变；遗忘分界
`== interval_days` 与 `+1`；resume 实写与 `--dry-run` 的队列、事件、状态、`revision`、间隔、提示；停用 / 配置外科目分别走 `record`
（有 / 无复习完成、显式 `--review-store`）、`submit --plan`、`submit --from-staging`、`resume`，断言退出 2、提示文字、且**什么都没写**）。
测试里不写死数据量 / 年份 / 科目（`AGENTS.md` 第 7–8 条）——科目从测试配置取。

**固定基线对照（R5）**：在**同一日期 D、同一配置 / 事件 / 输入**下、该 D 没有过期 `scheduled` 时，比较 `BASELINE` 旧版与新版的
preflight 文本 / JSON、record、submit、resume 输出与写出的事件 / 队列原始字节、M12 快照与 M15 状态映射——逐字节一致；
唯一允许的差异是第 4 条的 `-h` 帮助文字（单独一条用例断言前后对照，不要在其它比较里抹掉）。断言取到的确实是旧版。

## 撤实现验证

至少三处定点变异：R1 口径改回只数 `queued`；resume 不把 `scheduled` 改回 `queued`；R7 校验移到写入之后。
设 `PYTHONDONTWRITEBYTECODE=1` 并清 `__pycache__`，报告写实际命令与结果（哪条测试、哪一行断言变红），然后恢复。

## 不做的

- 不改 M9 的五个桶、`is_due`、候选选择、`ClipResult.backlog_minutes`；不改月结；不改冻结阈值 / 锁存 / 事件格式。
- 不改投影 schema 版本号（见第 3 条）。不动 `tools/`、`data/`。
- 不跑全量。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_freeze_scheduled_backlog tests.contract.test_freeze_port tests.contract.test_resume_port tests.contract.test_review_clip_port tests.contract.test_state_snapshot_port tests.contract.test_projection_status tests.test_cli
```

模块名以仓库实际为准（快照 / 投影状态的契约测试文件名你自己 `ls tests/contract` 确认），报告里写实际命令。

## 报告

`review/rounds/round-189-d11-scheduled-impl-luna.md`：逐条写 R1–R9 与第 1–6 条的落点、`-h` 帮助前后对照、测试覆盖清单、
撤实现验证命令与结果、验收输出原文。写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。
不提交。含中文只用 `apply_patch`，写完查 `???`。

---

**BASELINE = `81285d2`**（B6 配置键改名后的 master；配置键已是 `default_daily_minutes`，旧版与新版可喂同一份配置）。
