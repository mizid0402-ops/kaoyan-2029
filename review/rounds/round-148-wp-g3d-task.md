# 任务书：WP-G3d 拆分 `verify_408_index.verify` 与 `verify_tree.main`（D7，M5 / M4 校验工具）

你是固定窗口 `luna-b`（`tools/` 与数据管线），上一包做了 G2b（`tools/` 分层与 `tools/README.md`）。本包是**行为逐字节不变**的拆分，照窗口 `luna-a` 在 G3a / G3b / G3c 用过的固定基线对照做法。
先读仓库根 `AGENTS.md`，再读 `tools/verify_408_index.py`（`verify` 约 346 行）、`tools/verify_tree.py`（`main` 约 139 行）、`contracts/exam_index.md`、`contracts/knowledge_tree.md`、
`tests/contract/test_exam_index_port.py`、`tests/test_exam_index.py`、`tests/contract/test_knowledge_tree_port.py`，以及已有的对照测试写法 `tests/contract/test_models_split_baseline.py`。
**吸取已有教训**：测试辅助函数给嵌套路径赋值时列表下标不能用 `key not in node`（那是成员判断）；做"调换顺序看测试是否变红"的变异时设 `PYTHONDONTWRITEBYTECODE=1`。

在主仓库 `F:\workspace\kaoyan-ai-system` 工作，**只改这两个文件里的这两个函数（拆出私有辅助函数），新增一个对照测试文件**。其他窗口可能同时在做评审，不碰其他文件。
不改公开接口、命令行参数、输出文字、退出码；不改其他函数；不加兼容别名。

## 要做的

- `verify`：按检查段拆成有名字的函数（例如文件与 schema、卷面形状、题号与题型、分值合计、答案、知识点权重、出题单位与 `question_id`、跨文件唯一性……），主函数只按原顺序调用并汇总。
- `verify_tree.main`：拆成参数解析、树加载、来源哈希、`quote_ref`、契约、结构、输出等步骤。
- 每个函数一件事、不超过约 60 行、嵌套不超过三层；**报错 / 报告的先后顺序与每一个字节不变**。

## 测试（只写这一个）

`tests/contract/test_index_tree_verifiers_split_baseline.py`：`git show ec832c7:tools/verify_408_index.py` 与 `git show ec832c7:tools/verify_tree.py` 取旧版（断言取到的是旧版，例如旧 `verify` 超过 300 行），作为独立模块或独立入口运行。
- `verify`：以注册表登记的 408 索引为种子，在系统临时目录按规则生成变体（每类检查一个错误、跨段两两组合、合法原样），新旧比较返回值 / 异常 / 打印输出逐字节相同。缺原始资料时照 `tests/_resources.require_path` 跳过并写明缺什么。
- `verify_tree`：对三棵登记树原样与若干变体（哈希不符、`quote_ref` 找不到、契约错误、结构错误、`--require-scopes`），新旧各跑一遍 CLI，比较 `(退出码, stdout, stderr)` 字节。
不写死科目、年份或数量。撤修改验证：对调某个辅助函数的两次调用 → 变红（`PYTHONDONTWRITEBYTECODE=1`），报告写实际命令与结果。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_index_tree_verifiers_split_baseline tests.contract.test_exam_index_port tests.test_exam_index tests.contract.test_knowledge_tree_port tests.test_tools_catalog
```
另实跑一次 `py -3.12 tools/verify_408_index.py --workspace kaoyan.workspace.yaml` 与 `py -3.12 tools/verify_tree.py data/structured_materials/math1/knowledge_tree.yaml --workspace kaoyan.workspace.yaml`，把输出与 `ec832c7` 版本逐字节比较，结果写进报告。

## 报告

`review/rounds/round-148-wp-g3d-luna.md`：拆出的函数清单（名字、行数、职责）、变体类别与数目、撤修改验证、验收输出、实跑对比、建议。
写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。含中文的文件只用 `apply_patch` 编辑，写完查 `???`。
