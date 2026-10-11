# 评审：WP-E5a 路线改为可变时间线（决议 D10）

遵守 `AGENTS.md`（不跑全量）。范围：本包提交（`git log -1 --format=%h -- ky/schedule/planning.py`），运行用 `git archive <该提交>`（照前几轮补原始资料与 `products` 空目录）。
依据：`docs/阶段2.5-接缝收口.md` 的 D10（用户决定 + 决策者细则）；任务书 `review/rounds/round-111-wp-e5a-task.md`；实现者报告 `review/rounds/round-111-wp-e5a-luna.md`。
决策者审查时改了一处：`parse_route_plan` 先检查 `schema_version` 再检查键名，使真正的旧 24 月文件（带 `months`）得到"已作废（D10）"提示而不是"未知字段"。

请判断：
1. 时间线闭合规则：首段起点、相邻段首尾相接、无重叠 / 空隙、末段等于考试日、`end_exclusive > start`、`index` 连续；有无能经 YAML 绕过的输入（日期类型、键类型、`review_minutes` 的值类型、空阶段）。
2. 格式严格性与错误路径；`schema_version` 1 / 2 / 其他 / 缺失的处理。
3. 删除的公开名（`ROUTE_PLAN_MONTHS`、`MonthEnvelope`、`envelope_bounds`、`RoutePlan.months`）与字段是否还有调用方或文档残留；`RoutePlan.end_exclusive` 现等于考试日是否与规格一致。
4. 存储（比较并交换、锁、manifest、回滚）是否未受影响；`ky route show` 文本与 `--json`。
5. 日输入包 `route_plan.phase`：段边界、考试日当天为 `null`、无路线字节不变（`f0df351` 对照）；路线输入包与路线提案的新格式。
6. 新 / 改测试撤实现是否变红。

产物：`review/rounds/round-112-review-sol-out.md`，每项"必须改 / 建议改 / 不改"附可复现输入，最后 PASS / FAIL。只写这一个文件。
