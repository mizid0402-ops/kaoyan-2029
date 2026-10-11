# Round 48 任务书：WP-B′3 词汇通道迁移到工作区注册表（M7 读取端）

你是实现者（续同一会话）。只动 `ky/schedule/vocab_channel.py` 及引用 `DEFAULT_DB` 的地方。依据：`contracts/workspace.md` §3.2、§4。

## 要做的

1. `ky/schedule/vocab_channel.py`：删除 `DEFAULT_DB`（`Path(__file__).parents[2]` 拼接）。
   `remaining_pool`、`import_delivery_baseline` 以及第 134 行附近的函数，把 `db` 改为**必填**参数（调用方从注册表 `workspace.require("reference.vocabulary_db")` 取得后传入）。不留隐式默认。
2. 所有调用方与测试同步：`ky/schedule/state_snapshot.py`（WP-B′1 已改为走注册表，确认无残留）、`tests/test_monthly_close.py`、以及 `grep -rn "DEFAULT_DB" ky tests` 找到的其余引用——测试里改用仓库注册表 `load_workspace(REPO_ROOT / "kaoyan.workspace.yaml").require("reference.vocabulary_db")`。
3. 规格 `contracts/vocabulary.md`：词汇参考库端口——必须提供的 SQLite 视图/表与列（以 `_pick_view` 现有兼容逻辑为准：`v_top_words` 或 `words`）、只读打开方式、`delivery_log` 属于**待迁出的学习状态**（审查项 B2，WP-D 处理）且新代码不得再依赖它。
4. 契约测试 `tests/contract/test_vocabulary_port.py`：替换演练——把词库复制到临时工作区的另一相对路径并改注册表，`remaining_pool` 读到它、结果与原库一致；一个只含 `words` 视图不含 `v_top_words` 的最小库也能被读取（证明换一个最小实现可用）；缺失 → 违约。

## 不做的

- **不动 `tools/daily_words.py`、`tools/build_eng1_vocabulary.py`、`tools/verify_eng1_vocabulary.py`**（旧写入口的关闭与 `delivery_log` 迁移是 WP-D）。
- 不改词库文件本身。

## 验收

1. `py -3.12 -m unittest tests.test_monthly_close tests.test_state_snapshot tests.contract.test_vocabulary_port tests.contract.test_state_snapshot_port` 全绿。
2. `grep -rn "DEFAULT_DB" ky tests` 无结果（tools 里的保留，属 WP-D）。
3. 全量：**不跑**（按仓库根 `AGENTS.md`，由决策者提交前统一跑）。

## 产物

不要提交。报告：`review/rounds/round-48-wp-b3-vocab-luna.md`。
