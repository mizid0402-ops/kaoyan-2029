# 评审：`4701bdc` WP-H4b 复习队列按大纲版本迁移 + 参照完整性（新模块 M25）

遵守 `AGENTS.md`（不跑全量）。运行用 `git archive 4701bdc` 导到系统临时目录（缺 gitignore 原始资料照前几轮做法复制进临时归档）。

背景：任务书 `review/rounds/round-72-wp-h4b-task.md`（迁移规则表是决策者定的保守策略）、实现报告 `round-72-wp-h4b-luna.md`、
新规格 `contracts/syllabus_migration.md`；你第 69 轮对 H4b 的两条设计意见（来源成员判定、版本链解析；带版本登记的集成演练）。

重点：
1. 链解析：唯一性、环、重复边的判定是否正确；多步链上拆分后的项在下一步继续映射是否正确；指数级路径枚举在现实规模（每年一版）下是否可接受。
2. 迁移规则：逐条对照任务书表格，找出与规则不符的结果；合并去重与拆分生成的 `review_id` 冲突；`suspended` / `scheduled` 状态的项；同一步里既被改名又被合并的项的分类。
3. 悬空 ID 整体拒绝、`check_queue_references` 对无生效树科目的处理。
4. CLI：dry-run 真不写盘；`--apply` 失败不写盘；`--to` 缺省取 `effective_version()`（实现者提醒：先迁移、后切生效指针时必须显式 `--to`）是否合理；与 `ed456ec` 旧队列保护的交互。
5. 契约测试撤检查是否变红。

产物：`review/rounds/round-73-review-sol-out.md`，每条"必须改 / 建议改 / 不改"附可复现输入，最后 PASS / FAIL。只写这一个文件。
