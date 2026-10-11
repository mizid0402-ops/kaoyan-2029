# Round 54 任务书：知识点接口读写权限拆分 + 知识树端口规格（M4）

你是实现者。先读仓库根 `AGENTS.md`（全部规则适用）。依据：sol 第 47 轮 D1（`review/rounds/round-47-wp-b2-review-sol-out.md` §1 第二行）。

## 问题

`ky/knowledge/knowledge_point.py` 的 `load_knowledge_points(..., writer=...)` / `validate_knowledge_point(..., writer=...)` 把"谁在读"当成"谁有权写 `frequency.value`"来校验：
只有 `writer="deterministic_script"` 的读者能加载带频率值的树。现在所有树 `frequency: null` 所以没暴露；一旦确定性脚本写入频率，
快照（`writer="state_snapshot"`）会拒读，投影（`writer="deterministic_script"`）能读——读者之间行为分叉，而且读者冒用了写者身份。

## 要做的

1. **读取只校验数据本身**：`load_knowledge_points(path)`、`load_knowledge_points_from_text(text, *, source)`、`validate_knowledge_point(raw, *, source)` **去掉 `writer` 参数**。
   频率存在时校验其形状与来历（值有限且 ≥ 0、`computed_by == "deterministic_script"`、AI 生成节点不得带频率）——这是数据的来历约束，与谁在读无关。
2. **写入动作保留权限**：`apply_deterministic_frequency(..., writer=...)`、`transition_knowledge_point(..., actor=...)` 等变更入口继续检查写者 / 执行者身份；它们内部复用上面的读取校验。
3. **更新全部调用方**（`grep -rn "writer=" ky tools tests`）：`ky/schedule/state_snapshot.py`、`ky/projection/__init__.py`、`tools/*.py`、`tests/*.py`。不留兼容参数（D7：不留"以防万一"的别名）。
4. **规格 `contracts/knowledge_tree.md`**（M4 的四件套之"规格"）：知识点字段表（以现有契约代码为准）、scope 与状态机（`raw→extracted→reviewed→approved→superseded`，后三步只能 human）、
   频率的来历约束、**读取与写入的权限分离**、树语法由科目档案选择（链接 `contracts/workspace.md` §2.5 与 `ky/knowledge/tree_grammar.py`）、重复键拒绝。
5. **契约测试 `tests/contract/test_knowledge_tree_port.py`**：同一棵带合法频率的临时树，快照、投影、`verify_tree` 三个读者都能读、读出同一结果；`computed_by` 不是 `deterministic_script` 的树被所有读者拒绝；
   非 `deterministic_script` 调用 `apply_deterministic_frequency` 被拒绝。
6. `docs/模块地图.md` 的 M4 行：规格与可替换性更新；"缺口形状"表里"知识点契约把读者身份与写频率权限混用"一行删除。

## 不做的

- 不改任何树文件与 `data/`；不改树语法；不做大纲多版本（H4）。不提交。

## 验收

`py -3.12 -m unittest tests.test_knowledge_contract tests.test_tree_integrity tests.test_state_snapshot tests.test_projection tests.test_exam_index tests.test_cs408_lecture_pipeline tests.contract.test_knowledge_tree_port tests.contract.test_projection_port tests.contract.test_state_snapshot_port`；
`py -3.12 tools/verify_tree.py <三棵生效树>` 输出与改动前逐字节一致。全量不跑。无 `???`。

## 产物

报告 `review/rounds/round-54-knowledge-rw-luna.md`（用 `apply_patch` 写）。
