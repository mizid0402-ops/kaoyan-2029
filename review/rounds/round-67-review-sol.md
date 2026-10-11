# 复审：`d8f5031`（你第 64 轮对 WP-H3 的 M1 / M2 与建议项的修复）

遵守 `AGENTS.md`（不跑全量）。运行用 `git archive d8f5031` 导到系统临时目录（缺 gitignore 原始资料照第 64 轮的做法复制进临时归档）。
另有一个 worktree `../kaoyan-wt-h4a` 在做别的包，与本次无关，不用看。

范围：`git show d8f5031`；实现者报告 `review/rounds/round-65-wp-h3-sol64-fixes-luna.md`。

请判断：
1. M1、M2 的原复现是否关闭；十进制比较有没有新的误拒 / 误收（例如 `marks: 2` 与 `marks_each: 2.0`、索引里的非数值分值、`marks_total` 为布尔）；
2. "除 `paper_source` 外顶层键全部必需"是否与规格一致，有无误伤现有 11 份索引；
3. 新回归测试在撤回对应检查时是否会变红；
4. 决策者延后的一项（投影里 `question_id` 撞车报 `IntegrityError` 而非带路径的契约错误，留给后续投影包）你是否同意延后。

产物：`review/rounds/round-67-review-sol-out.md`，每项"必须改 / 建议改 / 不改"附可复现输入，最后 PASS / FAIL。只写这一个文件。
