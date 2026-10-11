# 第 251 轮任务书：WP-M28c 返工（gpt-6-luna，续 luna-a，同一 worktree `F:\workspace\kaoyan-wt-m28c`）

sol 第 250 轮评审 FAIL，报告：`F:\workspace\kaoyan-ai-system\review\rounds\round-250-m28c-review-sol61.md`（先读全文，可复现输入都在里面）。
决策者已核实 C1–C5 成立。核心意图协议、意图发布、恢复判定逻辑**不重做**；只改下面列出的。

## 已知、不在本轮

- 复盘设置接到 IO2 `ky/timetable_io.base_resolver`、拆分 `apply_pacing`（64 行）：决策者合并时做，**本轮不要动**。
- sol 报告"五、安全登记"两条：不修。

## 要改的

1. **C1 变更摘要**（`ky/pacing/submit.py` `_print_change_summary` 及调用方；规格 `contracts/pacing_review.md` §6 末段、§7 第 2 段）
   - "旧"值取**旧路线**：新提交取写入前的当前路线（`_validate_guardrails` 返回的 `route`），恢复 / 历史应用取**保存输入包**的 `current_route`；
     无路线时旧复习分钟打印 `-`。不要把候选路线当旧路线。
   - 证据打印实际值：每个 evidence 路径一行 `evidence: <路径> = <值>`，值取输入包 `report` 映射里该路径的值，`json.dumps(..., ensure_ascii=False)`。
   - 加三行边界说明（文字照抄）：
     - `调整在 <受影响阶段 end_exclusive> 日阶段结束后失效`
     - `生效日上限：<日期>（取自路线 target_exam_date）` 或 `（取自设置 exam_date）`——两者取较早者，并写明取自哪一个；无路线时只有设置 `exam_date`。
       设置值一律取**输入包里的 `settings`**，恢复分支不读当前设置文件。
     - `有课表的日子，M8 仍会按当日容量缩放复习配额`
   - 正式新提交：**先打印摘要，再**发布意图与路线（§6"通过后打印变更摘要……否则按 §6.1 两步写入"）。
   - `ky/pacing/port.py` 切段 label 改为 `f"{phase.label} · 复盘 {cycle_end}"`（规格 §7），并加实质断言。
2. **C2 分流前的登记门槛**：`pacing_submit_main` 里 `workspace.pacing is None` 的检查移到新提交分支（`_submit_new` 开头）。
   恢复分支（意图存在）不要求 `settings.pacing` 已登记，也不读设置文件。
3. **C3 恢复与失败文案**（规格 §6.2；下列中文照抄）
   - 已生效：首行 `本报告已有提交（修订 <target_revision>），实际应用如下；不发布`（dry-run 时末尾加 `（dry-run）`）；
     若当前路线修订 > `target_revision`，再打印 `这是历史应用：当前路线已是修订 <当前修订>，以当前路线为准`。之后打印 C1 的摘要（来自意图与保存输入包），
     保留"本次文件未被采用"一行的现有判定。
   - 待恢复 dry-run：首行 `dry-run：将恢复提交（不写任何文件）`，然后摘要，再打印意图里完整的候选路线 YAML（同新提交 dry-run 的打印方式）；意图 / manifest / 版本文件原字节不变。
   - 发布失败：新提交第 2 步或恢复分支的 `write_route_plan` 抛错时，先照旧输出 `contract violation: <原错误>`，再多一行 `提交意图已保存：重跑同一命令完成提交`，退出 2；
     不删意图、不清锁 / 孤儿文件。只在"意图已存在"之后的写失败才打印这一行（意图发布本身失败不打印）。
4. **C4 测试**：见下节。旧版身份断言改成正反两面：固定 `636bd09` 的 `ky/__main__.py` 含某段**只在旧版出现**的调用片段且不含新接线片段，当前文件相反；
   仍固定 `636bd09`，不改 `HEAD`，不扩大归一化。
5. **C5 模块头**：`ky/pacing/port.py`（补 `apply_pacing`、`settings_for_workspace`）、`ky/pacing/submit.py`（写明 `contracts/pacing_review.md` §6–§7）、
   `ky/pacing/input.py`、`ky/pacing/cli.py` 的模块头按 `AGENTS.md` D7 写明模块编号、规格文件与对外接口。
6. 便宜的建议一并做：
   - `contracts/pacing_review.md` §4 写明输入包 `settings` 的确切形状（现在是 `_settings_mapping` 的展平形状，照实写，不改代码）；
   - `ky/pacing/cli.py` 报告来源变化提示恢复成规格 §3 原句 `报告生成后记录有变化，已保存的报告不变`（`636bd09` 的原样）。

## 测试（只写这些，均在 `tests/contract/test_pacing_port.py`，第 4 条在 `test_day_budget_port.py`）

1. C1：sol 报告 C1 的例子 → dry-run 摘要各科 `10 -> 20`、`report.base.mean = 180`、三行边界说明；同一输入的切段 label 等于 `phase · 复盘 2026-10-15`；
   正式提交时摘要在 `submitted:` 之前、且在意图发布之前打印（可用发布失败注入证明：意图发布失败时摘要已打印）。
2. C2：意图写入后路线发布前中断 → 移除 `settings.pacing` 登记 → 重跑同一命令，正式运行发布保存候选、dry-run 预告不写。
3. C3：已生效后又有 r3 时重跑（正式与 dry-run）出现"历史应用"行、不发布；待恢复 dry-run 打印完整路线且三类文件字节不变；注入 `StorageError` 时退出 2、意图保留、有恢复提示行。
4. 旧版身份正反断言（见上 4）。
5. sol C4 列出的缺口：无路线中断后修改 `exam_date`，经 CLI 恢复仍发布原终点；保存有效包后跨日（`--today` 变化）的新鲜度拒绝，退出 2 且未写意图 / 路线；
   第 7 条护栏拒绝后零写入；五种 `apply_pacing` 情形断言保留段原值、命中段新基数 / 配额、后续段原值、重编号、label 与 `stage1_input_hash`；
   timetable / resume / preflight 经注册表登记 `settings.pacing` 后由 CLI 取到 `initial`（不给 helper 显式传 settings），preflight 提醒出现 / 不出现各一例。

## 验收（只跑这些，在该 worktree 里）

```
py -3.12 -m unittest tests.contract.test_pacing_port tests.contract.test_route_plan_port tests.contract.test_day_budget_port tests.contract.test_resume_port tests.test_cli
```

报告追加到同一 worktree 的 `review/rounds/round-247-m28c-luna.md` 末尾一节"第 251 轮返工"：逐条做法、测试输出原文、"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。
不提交；报告与测试不含个人数据；含中文的文件只用 `apply_patch` 编辑，写完 `rg -n '\?\?\?'` 检查。
