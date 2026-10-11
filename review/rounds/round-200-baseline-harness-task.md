# 任务书：技术债包 B —— 迁移对照测试收敛并退役（P1-1 / P1-2 / P1-3，窗口 `luna-a`，新会话）

先读 `AGENTS.md` 全文，尤其"迁移 / 重构不得改变输出"第 11–13 条与 12a；再读 `docs/技术债与整改清单.md` 的 P1 一节、§6、§7 与 §9。
**用户 2026-09-30 决定：9 个迁移对照测试"收敛并退役"。** 它们守的是阶段 2.5 的拆分波次，而阶段 2.5 已于 2026-09-30 收口
（`docs/阶段2.5-接缝收口.md` §九）；此后每改一次代码都要跟着适配它们（B6 一次就适配了 5 个文件）。

另一个窗口 `luna-c` 在改 `ky/` 的模块头与超长行，**不要碰 `ky/`**。`tools/` 也不要碰（之后另一包处理）。

## 范围：9 个 A 类文件

`tests/test_cli_split_baseline.py`、`tests/test_tools_split_baseline.py`、`tests/test_deck_scaffold_split_baseline.py`、
`tests/contract/test_models_split_baseline.py`、`tests/contract/test_schedule_split_baseline.py`、
`tests/contract/test_storage_ledger_split_baseline.py`、`tests/contract/test_workspace_split_baseline.py`、
`tests/contract/test_state_snapshot_counts_baseline.py`、`tests/contract/test_index_tree_verifiers_split_baseline.py`。

契约测试里嵌着的基线对照（`test_planner_port`、`test_availability_port`、`test_freeze_port`、`test_day_budget_port`、`test_projection_*`、
`test_freeze_scheduled_backlog` 等）与 `tests/test_cli.py` 的 `CliLegacyOutputTest` **不在退役范围**，只按第 3 步做辅助函数收敛。

## 顺序（清单 §7，不可颠倒）

### 第 1 步：盘点（先于任何删除）

逐个文件、逐个测试方法列表，分三类：
- **(a) 新旧对照**：取固定提交的旧版，与当前版比较输出 / 返回值 / 文件字节；
- **(b) 现有行为断言**：不依赖旧版、直接断言当前代码的输出、错误消息、退出码、状态（例如"失败场景下没有写完成事件"）；
- **(c) 旧版身份断言**：断言取到的旧函数确实是拆分前的长函数（AST 长度等）。
报告里给出完整表格（文件、方法、类别、一句话说明）。**(b) 类断言不得随文件删除**：逐条迁到对应的正规测试模块
（按模块地图找它守的那个端口的契约测试或单元测试），迁移后在新位置运行通过；若某条在正规模块里已有等价断言，写明等价的是哪条，就不重复迁。

### 第 2 步：共享 harness

新建 `tests/_baseline_harness.py`（公开测试辅助模块，模块头写明用途与 `AGENTS.md` 第 12 / 12a 条），承载这套机制：
按**固定提交哈希**取旧文件（拒绝 `HEAD` 与分支名）、断言取到的确是旧版（调用方给出判别条件）、隔离导入旧模块、
在同一输入上运行旧 / 新并比较 `(退出码, stdout, stderr)` 原始字节与写后文件树字节。只放机制，不放某个端口的业务数据。
新建 `tests/test_baseline_harness.py` 自测：给 `HEAD` 拒绝、旧版判别失败时报错、字节差异时报错、一致时通过。

### 第 3 步：辅助函数收敛（P1-2）

把跨文件重复的脚手架收进公开的测试辅助模块（`tests/_resources.py` 或新的 `tests/_fixtures.py`，你定并说明理由）：
至少 `_LegacyConfigView` / `as_dataclass`（`test_planner_port`、`test_availability_port`、`test_freeze_port`、`test_day_budget_port` 各一份）、
`_git_source`、`_write_registry`、`make_item`、`run_cli` 中确实**逐字节或语义相同**的那些。各调用方改为引用共享版本，
**断言一行不改**。有"微差"的不强行合并，报告列出差在哪。

### 第 4 步：等价证明，然后退役

- 从 9 个文件里挑 **1–2 个**改写为基于 harness 的实例保留（挑输入小、被测代码稳定、今后不太需要适配的；说明理由）。
  等价证明：对每个保留实例，至少做两处定点变异（在临时副本里改被测代码），**原文件与改写后的实例都必须变红**；
  再证明两者在未变异时都通过。报告写实际命令与结果。
- 然后删除其余文件。删除前确认第 1 步的 (b) 类都已迁走。
- `test_index_tree_verifiers_split_baseline.py`：清单 P1-3 原建议保留并标注，**决策者裁定随其余一起退役**（它守的也是已结束的拆分，
  且在本工作区恒为 skip）；其中若有 (b) 类，照第 1 步迁走，需要外部资源的用 `tests._resources.require_path`。

## 不做的

- 不改 `ky/`、`tools/`、`contracts/`、`data/`；不改任何保留测试的断言（第 3 步只换辅助函数的来源）。
- 不动 `tests/test_cli.py`、`tests/test_eng1_vocabulary.py`、`tests/test_cs408_lecture_pipeline.py` 的对照（它们不在 A 类）。
- 不跑全量。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.test_baseline_harness <保留的实例模块> <第 1 步迁入 (b) 断言的各模块> tests.contract.test_planner_port tests.contract.test_availability_port tests.contract.test_freeze_port tests.contract.test_day_budget_port
```

报告里写实际命令。再单独记录一次：退役前后，这 9 个文件原先所在模块集合的运行耗时（各跑一次，取实测）。

## 报告

`review/rounds/round-200-baseline-harness-luna.md`：盘点表、(b) 类迁移清单（从哪到哪、新位置测试名）、harness 接口说明、
辅助函数收敛清单与未合并的微差、保留实例与理由、等价证明的变异命令与结果、删除的文件清单、耗时对比、验收输出原文。
有未完成的如实写明。写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。含中文只用 `apply_patch`，写完查 `???`。
