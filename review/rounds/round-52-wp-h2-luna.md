# Round 52 — WP-H2 科目档案实现报告

## M0 注册表

- `ky/workspace.py` 只接受 `schema_version: 2`，将 `subjects` 解析为档案映射；每个档案要求非空 `name`，校验可选 `tree_grammar`、`domain_segment` 与 `features`。
- 登记知识树的科目必须指定已知树语法。`Workspace.subjects` 仍是科目 ID 元组；新增不可变的 `Workspace.subject_profiles` 映射及冻结的 `SubjectProfile`。
- 仓库注册表已升级为 v2，原有四科档案对应数学一 `named_chapters`、英语一 `flat`、CS408 `numbered_chapters`、政治无树语法。
- `tests/contract/test_workspace.py` 已切换到 v2 基准，并覆盖 v1 拒绝、字段类型/枚举错误、缺失树语法及精确字段路径。

## M4 树语法

- 新增 `ky/knowledge/tree_grammar.py`，按名字注册 `numbered_chapters`、`named_chapters`、`flat` 策略；策略包含原 CS408、数学一、英语一的章节语法与结构检查。
- `tools/verify_tree.py` 通过被登记树路径选科目档案，再由档案选择语法；树 ID 根命名空间必须等于登记科目 ID。登记路径仍经过 `Workspace.require` 的存在性与工作区边界检查。
- 改动前 `HEAD:tools/verify_tree.py` 与当前版本在相同三棵树上的退出码、stdout、stderr逐字节一致：CS408、数学一、英语一均为 `IDENTICAL`。

## M2 台账

- 移除固定科目白名单。台账校验接受调用方传入的科目集合；默认校验集合由工作区注册表科目与台账分类 `{general}` 组成。
- `py -m ky ledger` 新增 `--workspace`，省略 `--ledger` 时使用注册表路径；显式 `--ledger` 仍覆盖路径。
- 既有 `data/materials.yaml` 使用任务书命令校验通过，退出码为 0（49 条资料）。

## M15 投影

- `_domain_of` 改为查询科目档案的 `domain_segment`，不再按 `cs408` ID 特判。
- 快照的词汇段仅在档案启用 `vocabulary` 时读取，未启用时为 `null`。
- 用 `git show HEAD:ky/projection/__init__.py` 的旧实现和当前实现，对同一 v2 注册表分别重建 SQLite；输出数据库文件字节完全一致。

## 替换演练与文档

- 新增 `tests/contract/test_subject_onboarding.py`：在临时工作区仅通过档案、树、台账数据登记 `agri314`，验证注册表加载、树校验、台账校验、快照 `tree_total`、投影知识点行及空 `domain`；章节语法不符时树校验拒绝。
- 演练数据均在临时目录；仓库 `data/` 内容未改。
- 已更新 `docs/模块地图.md` 的 M0、M2、M4、M15 行及“科目是代码常量”缺口。

## 验证

- 任务书指定的七模块命令首次运行 102 项时，唯一错误来自快照契约测试仍对 v1 列表调用 `.remove()`。已将其改为删除 v2 档案映射键，并重跑该受影响模块：9 项通过。
- 后续定向复跑树形、科目演练、快照与树完整性模块：46 项通过；工作区契约：13 项通过（1 项平台跳过）；台账、树形与演练定向复跑：54 项通过。
- 最终复跑工作区契约、科目演练、树形与树完整性模块：50 项通过（1 项平台跳过）。
- 三棵现有生效树均通过不带 `--workspace` 的任务书命令；改动前后完整输出对照均逐字节一致。
- `py -3.12 -m ky ledger --ledger data/materials.yaml`：退出码 0。
- `rg -n '\?\?\?'` 对本轮修改文件无命中。全量测试未跑，按仓库 `AGENTS.md` 由决策者提交前统一运行；未提交。
