# Round 150 评审：WP-G3d 与 G3c 复审

## 方法

分别用 `git archive 9cb8132`、`git archive b43eb1f` 展开到系统临时目录，各补入上一轮临时副本保存的 47 份原始资料（73,005,384 字节）和 `products` 空目录。旧版只通过 `GIT_DIR=F:\workspace\kaoyan-ai-system\.git` 读取固定对象；所有运行、探针与变异均在临时归档，设 `PYTHONDONTWRITEBYTECODE=1` 并在换序前后清理对应 `.pyc`。主仓库工作区只写并复读本报告；没有跑全量测试。

## 一、WP-G3d（`9cb8132`）：**FAIL**

### 必须改

**G3d-M1：索引对照的若干“错误变体”没有触发标称检查段。** `tests/contract/test_index_tree_verifiers_split_baseline.py` 从注册表选中 `data/exam_questions/408_index_2023.json`。直接把各单项变体交给 `verify`，结果如下：

| 变体及实际赋值 | 实际结果 |
| --- | --- |
| `header`: `schema_version=999` | 问题列表为空；该校验器这里只要求整数。 |
| `calibration`: `calibration='awaiting_official_book'` | 问题列表为空；种子原本就是这个值。 |
| `provenance`: `provenance.paper.sha256='0'*64` | 格式合法；错误来自后面的 `_verify_registered_provenance`（磁盘哈希、locator 哈希），没有测试 `_verify_provenance_shape`。 |
| `coverage`: `answer_source_coverage.choice_total=-1` | 错误来自后面的 `_verify_answer_coverage`，没有测试 `_verify_coverage_shape`。 |

因此“12 个单错、66 个跨段双错”是生成数量，不代表每项有对应段错误。`notes` 检查和 `entries` 空列表提前返回也没有变体。实证：在临时源码同时去掉 `_verify_provenance_shape`、`_verify_coverage_shape`、`_verify_calibration` 及单题 `notes` 检查，索引对照测试仍 exit 0；去掉空 `entries` 分支的提前返回，同一测试也 exit 0。`_with_value` 的列表下标实现正确，变体的 `entries[0]` 仍是完整字典；问题在所填值和缺失路径。

可复现的替代输入：在该登记索引副本上分别设 `schema_version=None`、`provenance.paper.sha256='bad'`、`answer_source_coverage=[]`、`entries[0].notes='probe'`、`entries[0].answer_confidence='official'`、`entries=[]`，当前校验器各报 1、3、2、1、1、1 项，且旧 `ec832c7` 与新版返回/异常/输出逐项相同。请用会到达各检查段的错误替换空变体，补 `notes` 和早退输入，并断言每个变体确实产生了预期类别的问题。

**G3d-M2：知识树的 provenance 阶段和相邻顺序未被锁住。** 三棵树的 `source-hash`、`quote-ref`、`contract`、`structure`、`require-scopes` 变体确实分别进入相应失败路径；但没有一个变体使 `_check_provenance` 追加失败或状态提示。临时删除 `main` 中 `_check_provenance(points, failures, notes)`，18 个树输入的对照测试仍 exit 0；对调相邻的“结构/provenance”或“provenance/必需 scope”两次调用也都 exit 0。可复现补例：复制登记的 Math I 树，在一个有 `sources` 的节点加 `evidence: [{validation: guided, source: <该节点现有第一份 source>}]`；知识点契约通过，`verify_tree.py` exit 1，报 `extracted node must not carry evidence`。请补这类能到达 provenance 阶段的变体，并与结构或 scope 错误组成双错误以固定问题顺序。

**G3d-M3：`_verify_totals` 仍执行答案覆盖检查。** 它检查连续编号、数量与分值后，直接调用 `_verify_answer_coverage`；后者是另一项独立检查，任务书与 `AGENTS.md` 均要求每个步骤函数做一件事。可复现输入：阅读 `tools/verify_408_index.py` 中 `_verify_totals` 末尾调用及 `verify` 的阶段调用；上述 `coverage.choice_total=-1` 恰在 `_verify_totals` 内才出错。请由 `verify` 按旧顺序分别调用合计与答案覆盖两个步骤，保持问题列表顺序不变。

### 建议改

本包没有另需阻断范围外的建议。

### 不改：实现对照及已锁住的路径

- 基线固定为 `ec832c7`，测试断言旧 `verify` 超过 300 行、旧 `verify_tree.main` 超过 120 行。`py -3.12 -B -m unittest tests.contract.test_index_tree_verifiers_split_baseline`：2 项 OK。新旧实跑登记数据的两条任务书命令：`tools/verify_408_index.py --workspace kaoyan.workspace.yaml` 均 exit 0、stdout 314 字节、stderr 0；`tools/verify_tree.py data/structured_materials/math1/knowledge_tree.yaml --workspace kaoyan.workspace.yaml` 均 exit 0、stdout 376 字节、stderr 0，三元组逐字节相同。
- 知识树来源哈希失败和 `quote_ref` 不存在均在旧/新版本中提前 exit 1。临时去掉来源阶段或引用阶段的提前返回，各有三棵树的相应变体变红。对 Math I 同时破坏来源哈希与 `quote_ref`，旧/新均只输出来源失败，不进入引用报告。合同错误 exit 2、结构和必需 scope 错误 exit 1，当前树变体确实走到对应阶段。
- 索引可独立换序的相邻步骤探针：`header/provenance`、`provenance/coverage`、`coverage/entries 早退`、单题 `assignment/notes`、`notes/sources`、`paper shape/calibration` **仍绿**；单题 `identity/values`、`weights/assignment`、`sources/locator`，以及主流程 `entries 循环/free-text`、`free-text/totals`、`totals/registered provenance`、`registered provenance/paper shape` 均变红。知识树 `structure/provenance`、`provenance/required scopes` 仍绿。数据依赖的边（例如 `values` 产生 `kp` 后才能检查权重）不作直接换序。变异均已恢复；两个临时工具文件与 `git show 9cb8132` 原始字节相同。
- 除 M3 外，拆出的函数均短于约 60 行，职责及名称与执行内容基本一致。未观察到已覆盖输入上的新旧实现输出回归；M1/M2 是对照门禁不足。

## 二、G3c 复审（`b43eb1f`）：**FAIL**

### 必须改

**G3c-M5：拆开的候选查询在后续项失败时丢弃此前成功结果，违反固定基线。** 旧 `b867ae7` 在候选循环中保留已经 `append` 的结果，遇到 `ContractError` 只设置 `question_skip_reason`；新版 `_day_plan_record_query_candidates` 的异常分支却 `return [], str(exc)`。这在正常的多条待核对复习中可达。

可复现输入：从 `tests/test_cli_split_baseline.py` 的 `_record_case(root, 'record-needs-question')` 构造有效 JSON 候选场景；用 `_write_queue` 将队列写成两项：原 `record-review` 属于已登记试卷索引的首个科目，新增 `record-second` 属于配置中另一活跃科目（例如当前夹具的 `eng1`），知识点 ID 用该科目前缀；在 `done.yaml` 追加 `record-second` 的 `check=none, self_rating=fluent` 完成记录。测试注册表只给首科目登记 `exam_indexes`，故第一项找到候选、第二项在 `reference.exam_indexes.eng1` 报 `not registered`。旧版与 `b43eb1f` 均 exit 0、写入事件，skip 原因相同；旧版 JSON 的 `check_question_candidates` 有 1 组，新版为 0 组，输出字节不同。请在异常分支返回已累计的 `candidates`，并给固定基线对照加“先成功、后跳过”的双项场景。

### 建议改

本轮无额外建议。

### 不改：第 146 轮 M1–M4 与 S1 的指定修复

- 固定基线对照现有 39 个场景，`py -3.12 -B -m unittest tests.test_cli_split_baseline`：3 项 OK。`record-needs-question` 现在实际返回 1 组、内含 1 道候选题且无 skip；新增文本场景确实打印候选题。冻结 JSON 含 `freeze` 字段。
- 注入 `advance_review_queue` 抛 `ContractError` 时，旧/新均 exit 2 且事件已写；注入冻结锁存 `StorageError` 时均 exit 2 且事件未写。队列预检与冻结双错先报队列；其他 usage/配置、配置/策略、注册表/配置、配置/缺失 done 的双错按旧版首报。
- 重放第 146 轮 12 对相邻步骤换序：preflight 6 对、submit 1 对、record 5 对均使各自单模块对照测试 exit 1，且命中报告所列场景；其中冻结检查/事件写入的换序由事件存在性断言抓到。每轮禁用并清理字节码，结束后临时 `ky/__main__.py` 与 `git show b43eb1f:ky/__main__.py` 原始字节相同。
- `_day_plan_record_advance_queue` 与 `_day_plan_record_query_candidates` 已分开；前者失败终止，后者查询错误转为 skip，职责和名称清楚（M5 是后者的累计值回归）。`_CliExit` 只在 record 步骤的既有受控退出处抛出，外层仅捕获 `_CliExit` 并返回其退出码；用 `RuntimeError('unexpected-probe')` 注入预检步骤时实际 exit 1、traceback 可见、事件未写，没有吞掉未知异常。混合“结果或整数退出码”的分派已移除。

## 安全登记

本轮没有发现需按恶意输入、手工篡改内部文件或精确竞态单列的新增安全问题。G3c-M5 的第二项未登记试卷索引是合法注册表下日常可能出现的建议跳过路径，属于正常行为回归。

## 结论

- **WP-G3d FAIL**：真实登记数据输出一致，但对照变体多处无效或未到达标称阶段，结构与 provenance 顺序仍未锁住，合计步骤混入答案覆盖。
- **G3c FAIL**：第 146 轮指定修复均已落地并抓住 12 对换序；多条待核对复习时，后续出题查询失败会清空先前候选，与旧版 JSON 不一致。
