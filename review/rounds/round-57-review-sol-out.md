# Round 57 Codex 独立评审

范围：逐一审 `c234b9a`、`8cf3676`、`a7f7606`、`9f242e8` 的改动及对应契约。所有运行均在 `git archive <提交>` 导出的系统临时目录进行；主工作区只写本报告，未跑全量测试。以下“必须改”为阻断项，“建议改”为非阻断项。

## 1. `c234b9a` 知识点读写权限：**FAIL**

| 判断 | 发现、可复现输入与依据 |
|---|---|
| **必须改 K1** | **树文档顶层版本未校验。** `contracts/knowledge_tree.md:9-11,21` 规定映射文档可带 `schema_version` 且只接受 1；`ky/knowledge/knowledge_point.py:388-401` 只允许这个键，却没有验证它的值（251-253 仅验证**节点**版本）。在该提交归档运行 `load_knowledge_points_from_text('schema_version: 999\nitems: []\n', source='probe')` 返回空元组，未报错。若未来版本改变节点含义，旧读者会静默按 v1 接受。加载映射文档时校验顶层版本，并补 2、布尔、非法类型的拒绝测试。 |
| 不改 | 读端已移除 `writer`：`ky/knowledge/knowledge_point.py:247,373-415`；`apply_deterministic_frequency` 在写入边界检查写者，随后复用读取校验（316-322）；快照、投影、校验工具均不再冒用写者身份。`tests.contract.test_knowledge_tree_port` 3 个通过。归档初次运行因 Git 忽略的两份数学原始资料未随归档导出而失败；只复制这两份到**临时归档**后重跑通过，故不计为提交缺陷。 |
| 建议改 | `tests/contract/test_knowledge_tree_port.py` 覆盖合法/非法频率来源和无权限写者，却没有树文档顶层版本的拒绝断言；K1 的回归测试应落在本模块或既有知识树契约测试中。 |

## 2. `8cf3676` 台账 CLI 修复：**FAIL**

| 判断 | 发现、可复现输入与依据 |
|---|---|
| **必须改 L1（第 52 轮 M1 未完全修复）** | `ky/__main__.py:286-289` 只有 `--ledger`、`--root`、新增 `--subjects` **三者**齐备时才免注册表；旧调用 `ky ledger --ledger <台账> --root <根> --json` 在无注册表的临时 cwd 仍报 `kaoyan.workspace.yaml not found`、退出 2。对照 `git archive 00398b0^` 的旧 CLI，用完全相同的两个显式路径参数退出 0。`contracts/workspace.md:13,193-196` 承诺保留既有显式 CLI 用法，故新增必填 `--subjects` 不能算恢复原路径。应在保留动态科目校验的同时给旧用法明确的兼容规则，或先修改契约并取得破坏兼容的决议；补“只有 `--ledger --root` 且 cwd 无注册表”的回归测试。 |
| 不改 | 已给 `--subjects` 的独立模式在无注册表目录工作；注册表模式以 `workspace.root` 为默认内嵌路径根，登记台账通过 `workspace.require('reference.ledger')`（`ky/__main__.py:286-296`）。`tests.test_ledger_cli` 3 个通过，包括 junction 越界。 |
| 建议改 | `tests/test_ledger_cli.py:38-48` 的“独立模式”测试仍先从仓库注册表取科目，再传入新增 `--subjects`；它验证新调用方式，却不能发现 L1。 |

## 3. `a7f7606` WP-C2（D8′ / D9）：**FAIL**

| 判断 | 发现、可复现输入与依据 |
|---|---|
| **必须改 C1** | **解析器接受同一事件内重复的完成记录 ID。** `contracts/review_progress.md:15-17` 要求同一事件的 `completion_id` 唯一；`ky/schedule/completion.py:315-374` 逐条解析但不维护已见集合。给 `parse_completion_event` 一个 v2 事件，`day: 2026-09-12`、两条 `review_id: rv1` / `completed_on: 2026-09-12` / `check: none` / `completion_id: same`，返回两个 `same`，未报错。队列预检确实会拒绝，但不接队列的 `DayPlanStore.write_completion_event` 可将这种事件写为历史记录（`ky/storage/day_plan_store.py:561-576`）；自动生成 ID 与显式 ID 撞值也同理。应在解析端拒绝重复 ID，并保留队列预检作为防线。 |
| **必须改 C2（决议与迁移规格冲突）** | **旧队列重放会重复推进。** D8′ 在 `docs/阶段2.5-接缝收口.md:175-178` 要求同一条记录在重放/重建时只计算一次；`contracts/review_progress.md:73` 却让无 ID 集的旧 manifest 按空集读取，`ky/storage/review_shards.py:317-337` 和 `ky/storage/day_plan_store.py:395,412-415` 因而把旧完成记录视为新记录。隔离探针：用 `8cf3676` 的 schema-1 队列将 `rv1` 的 2026-09-12 正确核对推进到 `phase=1, interval=2`；再用 `a7f7606` 对同一队列重放同一事件，报告 `advanced=('rv1',)`、`replayed=()`，变成 `phase=2, interval=4`。旧 manifest 没有记录身份，无法仅凭它恢复已计算集合；需要明确一次性迁移历史完成记录的身份，或由用户明确批准旧历史不享受 D8′ 重放保证并禁止自动重放。补跨版本归档回归测试。 |
| 不改 | D8′ 核心路径按到达顺序处理不同完成记录、用 manifest 同次提交队列与已计算 ID，重放跳过、早期补录计算且 `last_reviewed_on` 不倒退（`ky/storage/day_plan_store.py:335-417`；`ky/storage/review_shards.py:499-542`）。D9 默认 strict，lenient 的 unknown/vague 只缩短间隔，basic/fluent 不凭自评延长；已核对走固定质量映射（`ky/schedule/completion.py:96-122,151-180`）。相关归档测试：`tests.contract.test_review_progress_port` 6 个、`tests.test_review_queue_advance` 13 个、`tests.test_storage` 7 个、`tests.test_cli` 29 个，均通过。 |
| 建议改 | `tests/test_review_queue_advance.py:193-205` 把整个 `store.write` 替换成抛异常，只证明调用失败时没有写入，未探测“分片已落盘、manifest 替换失败”这一原子提交边界。建议在临时目录注入最后一次 `os.replace` 失败，断言旧 manifest 仍指向旧队列且已计算 ID 未变；这是测试强度建议，不改变本轮 C1 结论。 |

## 4. `9f242e8` M24 核对出题：**FAIL**

| 判断 | 发现、可复现输入与依据 |
|---|---|
| **必须改 Q1** | `contracts/check_questions.md:36` 规定每题只产生一个候选。临时索引的 `entries` 放两条相同 `_entry('q1', 2024, 1, 0.8)`，调用 `candidate_check_questions(workspace, 'math1.demo.item')` 返回 `['q1', 'q1']`；`ky/review/check_questions.py:138-155` 直接逐行追加，未按题目 ID 去重或拒绝重复。应明确重复索引行的处理（建议以 `ContractError` 拒绝，避免跨文件冲突权重静默择一）并加测试。 |
| **必须改 Q2** | 必要索引内容没有校验：`ky/review/check_questions.py:101-128` 只验证 `subject_id` 是非空字符串，`locator = entry.get('locator')` 不验证。临时 `math1` 索引条目缺 `locator` 时返回候选的 `locator: None`；把该条 `subject_id` 改成 `eng1`，查询 `math1.demo.item` 竟返回 `('cross', 'eng1')`。与 `contracts/check_questions.md:12-27,39` 的按所请求科目索引选题、返回原始定位、无效必要字段报 `ContractError` 不符。应验证定位对象，并核对条目科目等于所读索引登记科目；补负例。 |
| 不改 | 正常路径会经 `require_all` 读登记索引、经 `require` 读权重，按权重/年份/题号/ID 排序；无映射时给 `ai_generated_allowed`，全被排除时不给 AI 后备，不返回题干。`tests.contract.test_check_questions_port` 7 个通过。 |
| 建议改 | 当前契约测试只用互异、定位齐全且科目一致的合成索引（`tests/contract/test_check_questions_port.py:48-169`）；Q1/Q2 的输入应成为拒绝或去重的精确回归断言。 |

## 总结

四个提交的既有相关测试均可通过，但仍有可复现的契约或兼容性阻断问题；WP-C2 与 M24 各有两条。最终判定：`c234b9a` **FAIL**、`8cf3676` **FAIL**、`a7f7606` **FAIL**、`9f242e8` **FAIL**。所有探针只写系统临时目录，主仓库实现和数据未改。
