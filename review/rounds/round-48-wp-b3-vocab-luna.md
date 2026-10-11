# Round 48：WP-B′3 词汇参考读取端迁移

## 改动

- `ky/schedule/vocab_channel.py`
  - 删除 `DEFAULT_DB` 和基于模块路径的拼接。
  - `remaining_pool(db)`、`import_delivery_baseline(db)`、`preview_batch(..., db=...)` 的数据库路径都改为必填。
  - 普通池计数和预览只查 `_pick_view` 选中的 `v_top_words` 或 `words`，不再依赖 `delivery_log`；移除失效的 `exclude_delivered` 参数。
  - 连接继续用 SQLite URI `mode=ro`。
  - `import_delivery_baseline(db)` 仍作为显式迁移桥读取旧 `delivery_log`，供 WP-D 迁移既有 15 条状态记录。
- `tests/test_monthly_close.py`：改从仓库注册表加载词库路径，并向所有通道函数显式传入 `db`。
- `tests/contract/test_vocabulary_port.py`：新增注册表换路径、仅有 `words` 视图的最小库和登记库缺失测试。
- `contracts/vocabulary.md`：记录支持的关系名、必需/可选列、只读方式及 `delivery_log` 的状态归属。

未改词库数据库或 `tools/`。

## 验收

- 指定四模块命令首跑：`Ran 59 tests`，仅新最小库测试在清理临时目录时失败。原因是 SQLite 夹具创建视图后未提交，修正为提交并关闭连接。
- 按仓库 `AGENTS.md`，修改测试后只重跑受影响模块：`py -3.12 -m unittest tests.contract.test_vocabulary_port`，**Ran 3 tests, OK**。首轮组合运行中的 `tests.test_monthly_close`、`tests.test_state_snapshot` 和 `tests.contract.test_state_snapshot_port` 均无测试失败。
- `rg -n "DEFAULT_DB" ky tests`：无匹配。
- 全量测试未运行，依仓库规则由决策者提交前统一执行。

## 范围说明与待迁移项

- 现存 `ky/schedule/state_snapshot.py` 仍读取 `delivery_log` 以计算 `delivered`。本任务边界限定为 `vocab_channel.py` 和 `DEFAULT_DB` 引用处，且状态迁出属于 WP-D，因此未改 M12 快照。普通 `remaining_pool` / `preview_batch` 新读取路径已不查询该表。WP-D 迁移后应同步改快照的 `delivered` 来源。
- `import_delivery_baseline` 仍显式读取 `delivery_log`，这是已存在的一次性迁移桥；若把“新代码不得依赖”解释为词汇模块任何公开函数都不得查询此表，则它与本任务仍要求保留该函数且 WP-D 才迁移状态的安排冲突。当前实现把它限定为迁移用途，并从词汇参考端口的日常读路径中隔离。
- `vocab_channel` 本身收到缺失的路径时抛 `VocabChannelError`；注册表调用方先经 `Workspace.require("reference.vocabulary_db")`，缺失时按工作区契约抛 `ContractError`。缺失测试分别覆盖两层。


## 修正（撤回越界的语义变化）

> 注：本节原文由 gpt-6-luna 通过 PowerShell 5.1 here-string 管道写入，中文被编码成 `?` 丢失（见 AGENTS.md 编码规则）。
> 以下由 Claude 根据 diff 与本地测试重述。

- `ky/schedule/vocab_channel.py`：恢复 `remaining_pool` / `preview_batch` 对已投放词的排除与 `exclude_delivered=True` 参数；
  读取集中到 `_legacy_delivered_word_ids(con)`，docstring 标明它是审查项 B2 的遗留桥接、WP-D 后删除。
  `count == 0` 恢复为打开数据库之前返回。模块头按 D7 写明 M7 与规格。
- `contracts/vocabulary.md`：日常读路径目前仍经遗留桥接排除已投放词；WP-D 后改为调用方传入已投放集合。
- `tests/contract/test_vocabulary_port.py`：新增 `test_legacy_deliveries_are_excluded_from_pool_and_preview`，期望值从库内计算，不写字面量。
- luna 报告的验收：`py -3.12 -m unittest tests.contract.test_vocabulary_port tests.test_monthly_close tests.test_state_snapshot` → Ran 51, OK。全量未跑（按 AGENTS.md）。
