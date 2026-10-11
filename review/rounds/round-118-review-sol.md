# 复审 + 评审：`a79c06a`（你第 116 轮 B1）与 WP-R1 积压冻结（新模块 M27，决议 D11）

遵守 `AGENTS.md`（不跑全量）。运行用 `git archive b7f6a7b`（R1 合并提交；照前几轮补原始资料与 `products` 空目录）。

## A. `a79c06a`

请用你第 116 轮的同科反例（配额 `math1=10, eng1=62`，普通 `regular` 逾期更久，紧急 `urgent` 延期 2 次，另科 `other` 62）重跑，并判断：第一遍"先紧急、后普通"是否在任何输入下都让本科紧急项先占本科配额；`sum(quotas) > hard_cap` 的拒绝；docstring；撤修复是否变红。

## B. WP-R1

依据：`docs/阶段2.5-接缝收口.md` 的 D11（用户决定 + 决策者细则）；任务书 `review/rounds/round-117-wp-r1-task.md`；实现者报告 `review/rounds/round-117-wp-r1-luna.md`；规格 `contracts/freeze.md`。
决策者审查时改了：冻结 payload 收到 `freeze_to_mapping`（CLI 与 M19 共用）；`day-plan submit` 的冻结检查抽成 `_reject_submission_while_frozen`；**至少一个逾期项才冻结**（配置容量极小时硬上限取整为 0，否则空队列也会冻结）；
合并后发现主仓库 `data/review_queue` 是空目录（无 manifest），改为"没有 manifest = 空队列"（与 `_review_queue_plan` 一致）。

请判断：
1. `assess_freeze` 的计数口径（`queued` 且 `due_date < day`）、阈值（配置硬上限 × 天数）、等号、空队列；是否应把 `scheduled` 且已过期（`unreachable`）也算进积压。
2. 冻结效果：preflight / 输入包在冻结时复习与新内容都为 0、`freeze` 键只在冻结时出现；未冻结时与 `2bbeaae` 逐字节一致（对照是否真固定旧版）；冻结优先于阶段配额与手填可用时间。
3. `day-plan submit` 两种形式在冻结时拒绝且不写；注册表发现 / 无效 / 缺失时的行为；`day-plan record` 不受影响。**这个入口先自行解析提案文件读 `day`，再交给 M19 完整校验**——是否有提案内容让两次解析得到不同的 `day`、从而绕过冻结检查。
4. `--freeze-backlog-days` 校验与退出码。
5. **D11 细则本身**（可以反驳）：冻结是"由队列推导"而非落盘状态——用户冻结期间自己学了并 `record` 完成，积压降到阈值以下就自动解冻，是否合理；阈值用配置容量而非手填是否合理。
6. 新测试撤实现是否变红。

产物：`review/rounds/round-118-review-sol-out.md`，A、B 每项"必须改 / 建议改 / 不改"附可复现输入，各自给 PASS / FAIL。只写这一个文件。
