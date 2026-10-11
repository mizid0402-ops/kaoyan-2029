# 评审任务书：D11 补充实现 —— 过期 `scheduled` 计入冻结积压（第 189 + 194 轮，窗口 `sol-main`）

这是阶段 2.5 的最后一个实现包。请评审 `luna-c` 第 189 轮与第 194 轮的合并结果：
任务书 `review/rounds/round-189-d11-scheduled-impl-task.md`、`review/rounds/round-194-d11-scheduled-complete-task.md`；
实现报告 `review/rounds/round-189-d11-scheduled-impl-luna.md`、`review/rounds/round-194-d11-scheduled-complete-luna.md`；
定稿细则 `docs/阶段2.5-接缝收口.md` D11 末尾"D11 补充"R1–R9（sol-rules 第 186 FAIL → 第 187 PASS）。
范围：`git diff 81285d2` 全部改动（`ky/`、`contracts/`、`docs/阶段2.5-接缝收口.md`、`tests/`）与新增 `tests/contract/test_freeze_scheduled_backlog.py`。

先读 `AGENTS.md`（"评审严重度"、"迁移 / 重构不得改变输出"、"已知缺陷清单"）。

## 重点看

1. R1–R9 逐条是否按定稿实现；M12 / M15 是否复用 M27 公开判定而非复制条件；`revision` 不变、`interval_days` 不增。
2. R7：`_latch_freeze_if_needed` 在同一份已加载注册队列上校验并在写冻结事件之前失败；`record` / `submit --plan` / `--from-staging` / `resume` 均退出 2、无写入、无 traceback。
3. R4 / R9 新增文字只在新条件下出现；`-h` 帮助差异是唯一允许的旧路径字节变化。
4. **实现者自报未完成的 R5 对照**（第 194 轮报告"当前仍未完成的对照"三条：非空 queued 积压下 `ky resume` 的队列 / 恢复事件字节；
   注册队列触发冻结时的冻结事件字节与 submit 输出；M12 `count_review_items_by_subject` / M15 `status_to_mapping` 的新旧对照）。
   请**自己用探针在系统临时目录复现这三项**（`git archive 81285d2` 对当前工作区），给出新旧是否逐字节一致的实测结论，
   并判断：缺这三条测试是否属于"必须改"（即日常使用下有未被守住的回归风险），还是探针已证明无差异、可列"建议改"。
5. 自己做至少一处定点变异确认对应测试变红。

## 规则

只跑与结论直接相关的单个模块或单条命令，**不跑全量**；复现用系统临时目录，不写进仓库。
结论 PASS / FAIL，分"必须改 / 建议改 / 不改"，每条附可复现输入；安全类单列"安全登记"。

## 报告

`review/rounds/round-195b-d11-scheduled-review-sol61.md`。

## 附注

另一个评审窗口正在并行审同一份代码（只读），报告写到 `round-195-...-codex.md`；**不要读它**，独立给出你的结论。
