# 评审：`340cd08` WP-E1 CLI 从注册表取状态路径 + `Workspace.write_target`

遵守 `AGENTS.md`（不跑全量）。运行用 `git archive 340cd08`（原始资料照前做法复制）。

背景：任务书 `review/rounds/round-88-wp-e1-task.md`、实现报告 `round-88-wp-e1-luna.md`；决策者另把三处重复的 `--store` 解析收成 `_plans_store_path`。

重点：
1. `write_target`：越界判定（junction、父目录是链接、目标不存在时的解析、大小写）与 `require()` 第 4 类判定是否同一口径；允许的键集合是否恰当。
2. 缺省路径：显式参数优先；无注册表时的报错；`preflight` / `snapshot` 读 `state.review_queue` 时不走越界检查是否可接受（这是读，但读的是写入目标）。
3. `--review-store` 不给缺省值的取舍（避免 `record` 悄悄推进队列）。
4. 行为变化：以前必传的参数变可选后，有没有哪条旧用法现在会读 / 写到不同位置。
5. 契约测试撤实现是否变红。

产物：`review/rounds/round-90-review-sol-out.md`，每条"必须改 / 建议改 / 不改"附可复现输入，最后 PASS / FAIL。只写这一个文件。
