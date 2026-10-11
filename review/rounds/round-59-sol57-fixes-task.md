# Round 59 任务书：修 sol 第 57 轮的六个阻断项

你是实现者（主工作区）。先读仓库根 `AGENTS.md`。依据：`review/rounds/round-57-review-sol-out.md`（每条都有可复现输入，照它写回归测试）。
另有 luna 会话在 worktree 里改 `tests/`（H1），与本任务文件不重叠；**不要改** `tests/test_data_manifest.py`、`tests/test_netem_source.py`、`tests/test_round24_weighted_tree.py`、`tests/test_tree_source_support.py`。

## 1. K1 知识树顶层版本（`ky/knowledge/knowledge_point.py`）
映射文档的顶层 `schema_version` 只接受 1（非布尔整数）；其他值 / 类型 → `KnowledgePointError`，字段路径 `schema_version`。回归放 `tests/contract/test_knowledge_tree_port.py`（2、true、"1"）。

## 2. L1 台账 CLI 旧用法兼容（`ky/__main__.py` 的 `_ledger_sources`）—— 决策者决议
- 只给 `--ledger` + `--root`（无 `--subjects`、无 `--workspace`）时：**先按规格 §3.1 发现注册表（cwd 向上），找不到再从台账文件所在目录向上找**；找到就用它的科目集合。
  都找不到 → `ContractError`，提示"加 `--subjects` 或 `--workspace`"。不得静默跳过科目校验。
- 在 `contracts/workspace.md` §3.2 下补一句台账命令的这条发现规则。
- 回归（`tests/test_ledger_cli.py`）：sol 的输入——只有 `--ledger --root`、cwd 无注册表、台账位于含注册表的目录树内 → exit 0；台账与 cwd 都不在任何注册表树内且无 `--subjects` → exit 2 且提示；
  把现有"独立模式"测试的 `--subjects` 改为不依赖仓库注册表的字面科目列表，使它真正独立。

## 3. C1 事件内重复 completion_id（`ky/schedule/completion.py`）
`parse_completion_event` 维护已见 ID 集（显式 ID 与自动生成的 `day#index` 一起算），重复 → `CompletionError`，字段路径 `reviews[i].completion_id`。队列预检保留。回归：sol 的两条 `completion_id: same`；显式 ID 等于另一条的自动 ID。

## 4. C2 旧版队列不能保证"只算一次"（`ky/storage/day_plan_store.py` / `review_shards.py`）—— 决策者决议
仓库目前没有任何真实复习队列（`data/review_queue/` 为空），无历史可迁移。规则：
- schema-1 manifest **可以读**；
- 在 schema-1 队列上**推进**时，若被推进的项已有 `last_reviewed_on`（说明有无法识别身份的历史计算），抛 `StorageError`："旧版队列无已计算记录，无法保证只算一次；请先升级队列"；
  从未复习过的项照常推进，推进后 manifest 写为 schema 2。
- 提供一个显式升级入口（函数即可，如 `upgrade_legacy_queue(store, *, acknowledge_unknown_history: bool)`：只有调用方显式确认才把 schema-1 升为 schema-2 并以空集起步），规格写明它的含义。
- `contracts/review_progress.md` 迁移一节按此改写。回归：sol 的跨版本探针（schema-1 队列里已推进的项重放 → 拒绝）；未复习项正常推进。
- 顺带按 sol 建议补一条原子性测试：注入**最后一次** `os.replace`（manifest 替换）失败，断言旧 manifest 与已计算 ID 集不变。

## 5. Q1 / Q2 M24 索引校验（`ky/review/check_questions.py`）
- Q1：同一 `question_id` 在同科登记索引中出现两次 → `ContractError`（不去重、不择一），字段路径指向第二次出现。
- Q2：`locator` 必须是映射（缺失 → `ContractError`）；条目 `subject_id` 必须等于该索引登记的科目，否则 `ContractError`。
- 规格 `contracts/check_questions.md` 同步；回归放 `tests/contract/test_check_questions_port.py`（sol 的三个输入）。

## 验收
`py -3.12 -m unittest tests.contract.test_knowledge_tree_port tests.test_ledger_cli tests.test_ledger tests.test_completion tests.test_review_queue_advance tests.test_day_plan_store tests.test_storage tests.contract.test_review_progress_port tests.contract.test_check_questions_port tests.test_cli`。
全量不跑。无 `???`。报告 `review/rounds/round-59-sol57-fixes-luna.md`（`apply_patch`，按 K1/L1/C1/C2/Q1/Q2 分节）。不提交。
