# 复审：`ed456ec`（你第 60 轮 C2 与两条 L1 建议的修复）

遵守 `AGENTS.md`（不跑全量）。主工作区有 luna 正在做的 WP-H3 未提交改动，运行请用 `git archive ed456ec` 导到系统临时目录。

范围只有 `git show ed456ec`。决策者的取舍写在提交信息与 `contracts/review_progress.md` 修订段：
schema-1 队列只要有任一已复习项，**任何写入**（推进、upsert、delete）都拒绝，直到 `upgrade_legacy_queue` 显式确认；
检查放在写入前预检（完成事件写入之前）并在 `ReviewShardStore.write` 兜底。

请判断：
1. 你第 60 轮的两个探针（混合队列绕过；CLI 先写事件后失败）是否都已关闭；
2. 还有没有别的写入路径能绕过（例如 `write_review_queue`、直接构造 store 调 `_commit`、`upgrade_legacy_queue` 对 schema 2 或空队列的行为）；
3. 新增三条测试的断言强度；L1 两条建议的落实是否恰当。

产物：`review/rounds/round-62-review-sol-out.md`，每项"必须改 / 建议改 / 不改"附可复现输入，最后 PASS / FAIL。只写这一个文件。
