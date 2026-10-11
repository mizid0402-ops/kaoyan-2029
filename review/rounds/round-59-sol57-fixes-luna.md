# Round 59：修复 Round 57 六个阻断项

## K1 知识树顶层版本

`load_knowledge_points_from_text` 现在检查映射文档的 `schema_version`：只接受非布尔整数 `1`；
`2`、`true` 和字符串 `"1"` 均以 `KnowledgePointError` 拒绝，路径为
`<source>.schema_version`。

回归位于 `tests/contract/test_knowledge_tree_port.py`。该模块通过。

## L1 台账 CLI 旧用法兼容

仅给 `--ledger` 和 `--root` 时，先按 cwd 向上发现注册表；未找到时再从台账所在目录
向上发现，并使用注册表科目。两处均未找到时返回 `ContractError`，提示增加
`--subjects` 或 `--workspace`。独立模式测试现在使用固定科目参数，不从仓库注册表读取科目。
`contracts/workspace.md` §3.2 已记录规则。

回归位于 `tests/test_ledger_cli.py`：验证从台账目录发现注册表成功，以及两处均无注册表时退出码为 2 并显示提示。该模块通过。

## C1 事件内重复 completion_id

`parse_completion_event` 为显式 ID 与自动生成的 `day#index` 维护同一已见集合；重复 ID 以
`CompletionError` 拒绝，路径指向第二条记录的 `completion_id`。队列预检仍保留原重复检查。

回归位于 `tests/test_completion.py`：覆盖两个相同显式 ID，以及显式 ID 与另一条自动 ID 冲突。该模块通过。

## C2 旧版队列只算一次保证

schema-1 manifest 仍可读取。推进 schema-1 队列中已有 `last_reviewed_on` 的项时，拒绝并提示
“旧版队列无已计算记录，无法保证只算一次；请先升级队列”；未复习项正常推进并写出 schema 2。
新增 `upgrade_legacy_queue(store, acknowledge_unknown_history=True)` 显式入口：调用方确认
旧历史身份未知后，保留队列项并以空的已计算 ID 集升级。规格已同步至
`contracts/review_progress.md`。

`tests/test_review_queue_advance.py` 覆盖跨版本重放拒绝、未复习项推进、显式升级确认，
以及最后一次（manifest）`os.replace` 失败时旧 manifest 和已计算 ID 集不变。队列与
day-plan 两模块共 33 项通过。

## Q1 同科登记索引重复题目

索引读取按登记科目汇总已见 `question_id`；重复题目抛出 `ContractError`，路径指向第二次出现的题目 ID，不去重也不择一。

回归位于 `tests/contract/test_check_questions_port.py`，并与 Q2 用例一并通过。

## Q2 索引条目字段校验

每条索引记录的 `locator` 必须是映射；`subject_id` 必须与该登记索引所属科目一致。
不满足时以 `ContractError` 指向对应字段。`contracts/check_questions.md` 已同步。

回归覆盖缺少 `locator` 和科目不匹配；`tests/contract/test_check_questions_port.py` 通过。

## 验收记录

任务书列出的十个测试模块首次合跑时有 149 项通过，另有一项测试因捕获了错误模块的
同名 `StorageError` 失败。修正捕获类型后，`tests.test_review_queue_advance` 17 项通过；
随后因队列实现的最后一次边界修正，重跑
`tests.test_review_queue_advance tests.test_day_plan_store`，33 项通过。其余任务书验收
模块在首次合跑中通过。

全量测试：未跑（按 `AGENTS.md`，由决策者提交前统一跑）。未提交。
