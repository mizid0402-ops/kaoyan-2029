# 评审：WP-E4 手填可用时间（新模块 M26；合并提交 `dedab00`，实现提交 `19a721e`）

遵守 `AGENTS.md`（不跑全量）。运行用 `git archive dedab00`（原始资料与 `products` 空目录照前几轮补）。

范围：`git diff dedab00^1 dedab00`；任务书 `review/rounds/round-103-wp-e4-task.md`；实现者报告 `review/rounds/round-103-wp-e4-luna.md`；新规格 `contracts/availability.md`。
决策者审查时只把 CLI 的可选注册表辅助函数改名为 `_discovered_workspace`（preflight 也用它了）。

请判断：
1. 格式：`load_availability` 的严格性（键、日期、重复日、分钟类型、`schema_version`）与错误路径；登记即必须存在。
2. 逐字节不变：无手填值时 `ky preflight`（含 `--json` 与文本）、M19 日输入包与 `79623ee` 是否一致；对照测试是否真的固定了旧版。
   注意 preflight 现在会向上发现注册表：发现到**无效**注册表时 preflight 由原来的成功变为退出 2——这个行为变化是否可接受、是否应写进规格。
3. 有手填值时：复习裁剪的容量、输入包 `availability` 字段、`review_clip` 与 `ky preflight --json` 仍一致。
4. 日计划护栏：两种 submit 都经注册表取 availability；超限拒绝且不写；无手填值不检查；`check_invariants` 未改。
5. M13 依赖 M26 的方向（`day_plan_store` import `ky.availability`）是否符合拼图边界。
6. 新测试撤实现是否变红。

产物：`review/rounds/round-107-review-sol-out.md`，每项"必须改 / 建议改 / 不改"附可复现输入，最后 PASS / FAIL。只写这一个文件。
