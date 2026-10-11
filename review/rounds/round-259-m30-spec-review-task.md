# 第 259 轮任务书：M30 掌握度规格**初检**（gpt-6.1-sol，续 sol61-m17）

## 只做初检（用户 2026-10-01）

- 只审规格本身（`AGENTS.md`"决策者细则先审再实现"）：`contracts/mastery.md` 全文与 `contracts/charts.md` §8。不写代码、不跑测试。
- 重点：§7 末尾决策者自拟的细则是否与用户四项选择一致、有没有日常使用会算错或自相矛盾的地方；引用的现有接口 / 字段名是否真实存在
  （`ReviewItem`、`ReviewSchedule.interval_days` / `lapses`、`VALID_REVIEW_STATES`、`topic_weights.json` 的 `topic_weight` 形状、M4 `tree_parent`、M28 设置 `start` / `exam_date`）。
- 特别确认一点：**自评是否真的无法让 `interval_days` 变长**（读 `ky/schedule/completion.py` 与 `contracts/review_progress.md`，strict 与 lenient 两档）。
  若有任何路径能让未核对的完成拉长间隔，就是"必须改"。
- 必须改附反例；其他一行写进"留给最终大检查"。报告约 40 行。

## 输出

`F:\workspace\kaoyan-ai-system\review\rounds\round-259-m30-spec-review-sol61.md`：PASS / FAIL；必须改；留给最终大检查。

## 禁止

不联网；只写这一份报告；不改其他文件；不读 `data/personal/` 与 gitignore 的学习状态。
