# Round 58 任务书：WP-H1 剩余——测试里的数据量字面量收进数据清单（D5）

你是实现者，在独立 worktree（分支 `stage25/h1`）。先读仓库根 `AGENTS.md`（第 7 条：测试不得把数据量写成字面量）。
主工作区另有会话在改 `ky/__main__.py`、`tests/test_cli.py`、`contracts/review_progress.md`、`docs/模块地图.md`——**这些文件不碰**。

## 要做的

1. 找出 `tests/` 下（`tests/contract/` 已清理过）仍把**当前数据版本的数量**写成字面量的断言，例如 `tests/test_netem_source.py`（3409、5530）、
   `tests/test_tree_integrity.py`（69、24、11 个 item）、`tests/test_round24_weighted_tree.py`（410、403/7）、`tests/test_tree_source_support.py`（410）等。
   用 `rg -n "assertEqual\(.*\b[0-9]{2,}\b" tests` 之类的方式找，逐条判断：是"数据版本的数量"还是"算法常量 / 规格常量"（后者保留）。
2. 数据版本数量：改为从被测数据推导（例如"节点数 = 树文件条目数"这种自洽断言），或移进 `tests/test_data_manifest.py`（文件头已写明"数据合法增长时只改这里"）。
   移动时保持**检测力不变**：原测试想防的回归（例如"有人删掉了一批节点"）仍要能被数据清单测试抓到。
3. 在报告里列一张表：每个被改的断言 → 原值 → 处理方式（推导 / 移入清单 / 保留及理由）。

## 不做的

- 不改任何数据文件；不改被测实现。只改测试。

## 验收

在本 worktree：`py -3.12 -m unittest` 跑你改过的每个测试模块 + `tests.test_data_manifest`。
注意本 worktree 没有 `data/raw_materials/`（被 gitignore），依赖原始资料的测试会因缺料失败——报告里如实列出，不要为此改测试。全量不跑。无 `???`。
报告 `review/rounds/round-58-h1-luna.md`（`apply_patch`）。不提交。
