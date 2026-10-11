# Round 50 任务书：WP-B′ 收尾（sol 第 47/48 轮 FAIL 项 + D7 可读性建议）

你是实现者（续同一会话）。依据：`review/rounds/round-47-48-review-sol-out.md`。遵守仓库根 `AGENTS.md` 全部规则（D7 可读性、数据不写字面量、编码、只跑点名模块）。
分五块，每块在报告里单列。**先做第 0 块**，它是回归。

## 0. B′4 退回：恢复被删掉的输出内容（回归，最高优先）

你在第 49 轮迁移路径时，重构掉了用户可见的输出（决策者用改动前后的中文行逐条比对发现）：
- `tools/build_408_deck_scaffold.py`：讲解单元只剩到"## 讲解正文（待填写）"。丢失了：生成注释行、知识单元 / 所属章 / 来源支持度表格行、真题定位的"引用请按 QUOTATION_POLICY.md"提示与表头、
  "无命中不等于不考，只说明这四套里没出现"、以及正文小节（考点提炼 / 原理与推导 / 易错点 / 真题印证（含每题"出处 / 摘录 / 讲解"占位）/ 练习指向）。
- `tools/extract_cs408_bundle.py`：覆盖报告丢失"命中次数最多的 40 个知识点"表、"层级分布"表、"无命中不等于不考"提示；结构大纲的标题说明行也变了。

要求（见 `AGENTS.md` 第 11–13 条，新增）：
1. 恢复全部原有输出。对**生效节点**，新版本输出必须与 `git show HEAD:<文件>` 版本在同一份临时输入上**逐字节一致**；
   唯一允许的差异：任务书要求新增的 `is_effective` / `view_name` 列、非生效节点的可见标注、补充视图名与 description。
2. 注意：旧版里"2023–2026 四套卷"这类写死的年份说明，改为从登记的索引推导（D5 规则），这是唯一允许的文案变化，并在报告里逐条列出。
3. 把新旧对照写成测试（`tests/test_cs408_lecture_pipeline.py` 中）：用改动前版本（从 git 取出到临时目录运行）与新版本对同一临时输入生成输出并比较。
4. 其他 5 个工具如有同类输出变化，一并恢复并说明。


## 1. P4：契约测试去掉数据量字面量（D5 规则）

`tests/contract/` 下所有写死数据规模的断言（`grep -nE "\b(403|410|11|432)\b" tests/contract/*.py` 可找到，包括投影、快照、注册表三个契约测试）：
- 契约测试的期望值**从注册表和被登记文件推导**：例如"生效表 cs408 行数 = 注册表生效树的节点数"、"补充表 is_effective=1 的行 = 生效树 ID 集"、"注册表索引集合 = `data/exam_questions/*.json` 集合"、"非生效 ID = 补充树 ID − 生效树 ID"。
- D1 的历史事实（生效树 403、补充树 410、7 个 legacy、11 份索引）**移到一个新的数据清单测试** `tests/test_data_manifest.py`，文件头注释写明："这是当前数据版本的快照；数据合法增长时只改这里"。
- 通用测试里挑选"某一科 / 另一科"时，从注册表里取（例如第一个有树的科目、另一个不同科目），不要写死 `cs408`/`math1`；专门测 cs408 补充视图的测试可以保留 cs408，但科目名从注册表的 `supplementary` 视图里读。

## 2. V1：词汇端口的关系形状校验

`ky/schedule/vocab_channel.py`：选关系时检查规格要求的必需列（`word_id`、`word_form`），不满足或 SQLite 查询出错时抛带关系名的 `VocabChannelError`，不让 `sqlite3.OperationalError` 外漏。
契约测试加：只有 `CREATE TABLE words (id INTEGER)` 的库 → `VocabChannelError`；`v_top_words` / `words` 分别作为表或视图时都能被选中。
零词预览与缺失库：**在规格里写明**"`count == 0` 时不打开数据库、直接返回空批次"这一例外（保持现有行为，不改实现）。

## 3. D7 可读性（sol 建议 1–3）

1. 投影：把解析结果收成一个有字段名的 `_ProjectionRows`（frozen dataclass），`_insert_projection_rows` / `_write_meta_and_views` / `_write_projection_database` 只收这一个对象。不改行为，保持"先解析全部输入、后写库"。
2. 词汇：抽出一个返回"关系名、列集合、过滤条件"的辅助步骤，`remaining_pool` 与 `preview_batch` 共用；`import_delivery_baseline` 复用 `_connect`。V1 的必需列检查放在这个共同步骤里。
3. 知识树文本入口：底层已带路径的 `ContractError` 转成 `KnowledgePointError` 时不再把文件路径重复拼进文案；接口注释说明重复 YAML 键目前是文件级定位。

## 4. 更新模块地图

`docs/模块地图.md`：M7、M12、M15 三行的"可替换性"与状态按本轮结果更新；M5/M6 行如 B′4 已改动也同步。只改对应行，不重写文件。

## 验收

`py -3.12 -m unittest tests.contract.test_projection_port tests.contract.test_state_snapshot_port tests.contract.test_workspace tests.contract.test_vocabulary_port tests.test_data_manifest tests.test_knowledge_contract tests.test_projection`。
全量不跑。写完检查所有改动文件没有 `???`。

## 产物

不提交。报告：`review/rounds/round-50-wp-b-wrapup-luna.md`（用 `apply_patch` 写，不要 here-string 管道）。
