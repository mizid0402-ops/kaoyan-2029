# 评审任务书：第 196 轮 —— D11 补充返工（窗口 `sol61-main`，续你第 195b 轮）

请复审 `luna-c` 第 196 轮。任务书 `review/rounds/round-196-d11-scheduled-fix-task.md`，实现报告 `review/rounds/round-196-d11-scheduled-fix-luna.md`。
上一轮两份评审：你的 `review/rounds/round-195b-d11-scheduled-review-sol61.md`，以及另一位评审的
`review/rounds/round-195-d11-scheduled-review-codex.md`（它的 M1 是 preflight 说明行写"下方 deferred"但该行实际在上方，且不在冻结段——你上一轮没有指出这一点，本轮请重点核对它是否已修好）。
决策者提交前全量另发现 `test_storage_ledger_split_baseline` 因 `ResumePlan` 新字段失败，本轮也修了。

范围：`git diff 81285d2` 全部改动（重点是第 196 轮新改的部分）与 `tests/contract/test_freeze_scheduled_backlog.py`。

## 重点看

1. 说明行：位置紧随冻结状态输出、无方位词、只在新条件出现；自己实跑 preflight 看**实际打印顺序**，不要只读代码。
2. `test_storage_ledger_split_baseline` 的改法只放过 `scheduled_to_queued_count` 这一个键且先断言其为 0。
3. 两处规格文字已按你 m2 修正。
4. 三项 R5 对照已固化为测试，确实比较旧新原始字节、确实取到旧版；不再 import `FreezePortContractTests`。
5. 新测试里的环境变量 `D11_PROBE_NEW_ROOT`（让变异验证把"新版"指向临时副本）：正常运行时是否一定指向当前工作区代码；它的存在会不会让对照在某种环境下变成"新对新"或被静默绕过（`AGENTS.md`"不写聪明的捷径"）。给出结论。
6. 自己做一次定点变异确认变红。

## 规则

只跑与结论直接相关的单个模块或单条命令，**不跑全量**；复现用系统临时目录。结论 PASS / FAIL，分"必须改 / 建议改 / 不改"。

## 报告

`review/rounds/round-197-d11-scheduled-fix-review-sol61.md`。
