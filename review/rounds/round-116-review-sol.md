# 复审：sol 第 114 轮修复（`cdff892`）+ 紧急项"只借剩余空闲"（D10 补充）

遵守 `AGENTS.md`（不跑全量）。范围：`cdff892` 与本轮紧急借用提交 `2bbeaae`；运行用 `git archive 2bbeaae`（照前几轮补原始资料与 `products` 空目录）。
依据：`docs/阶段2.5-接缝收口.md` 的 D10 补充（你第 114 轮指出"紧急项可占满硬上限、长期挤占他科"，决策者改为只借剩余空闲）与 D11（冻结 / 重启，后续包实现，本轮不审）。

A. `cdff892`：请用你第 114 轮的原探针重跑——M19 两次读路线（`current()` 依次返回 r1、r2）；非整数配额的错误类型与路径；文本 `timeline quotas` 标注；阶段首尾日。
B. 紧急借用：`_select_with_subject_quotas` 两遍——第一遍只在本科配额内（且不超硬上限）入选，第二遍让未入选的紧急项用硬上限剩余空位；两个列表保持优先级顺序。请判断：
   1. 别科配额内普通项是否在任何输入下都不会被紧急项挤掉；紧急项是否仍能用上剩余空闲；
   2. 无配额路径是否逐字节不变（`select_daily_reviews` 的 `else` 分支应与改动前完全同义）；
   3. 会计不变量、`unschedulable`、`subject_review_minutes` 统计；
   4. 新测试 `test_urgent_backlog_only_borrows_leftover_capacity` 撤回为旧规则时是否变红。

产物：`review/rounds/round-116-review-sol-out.md`，A、B 每项"必须改 / 建议改 / 不改"附可复现输入，最后 PASS / FAIL。只写这一个文件。
