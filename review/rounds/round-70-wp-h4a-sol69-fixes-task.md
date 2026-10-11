# 任务书：修复 sol 第 69 轮对 WP-H4a 的 B1–B4（续你第 66 / 68 轮的工作）

H4a 已合入 master（`a691cb1`，后续 `def56be`），worktree 已删除；你这轮**在主工作区**改，不提交。
先读 `review/rounds/round-69-review-sol-out.md` 的 B 节（每条都有复现输入）。遵守 `AGENTS.md`。

## 必须改（决策者已定的修法）

1. **B1 覆盖规则闭合**（`ky/knowledge/syllabus_mapping.py`）：隐式自环只属于**两树都有且未列入 `changes.from`** 的 ID。
   检查改为：新树每个 ID 必须恰好由以下之一覆盖——某条 `changes.to` 的目标、未列入 `changes.from` 的同名旧 ID（隐式自环）、`added`；
   旧树每个 ID 必须要么在 `changes.from` 里（显式去向，可为空列表 = 删除），要么两树都有（隐式自环）。
   sol 的两个复现（`{from: 共同ID, to: []}`、`{from: 共同ID, to: [另一个新ID]}`，新树同名 ID 无来源）都必须被拒，报错说明是哪个新 ID 无来源。
   注意：共同 ID 显式写 `to: [同名ID]` 仍合法（等价于原样保留）。
2. **B2 同一条 `to` 内不得重复**：报 `changes[i].to[j]`。不同 `changes` 指向同一目标（合并）仍合法。
3. **B3 只读登记过的路径**：映射文件必须是 `workspace.require_all("reference.syllabus_versions.<科目>.mappings")` 返回的路径之一（按解析后的路径比较），否则 `ContractError`；
   两棵版本树经 `workspace.require("reference.syllabus_versions.<科目>.versions.<标签>")` 取得（这样越界 / junction 检查生效），不直接读 `record.versions[...]`。
4. **B4 一科内版本标签不得共用同一路径**：`ky/workspace.py` 加载时拒绝，报 `reference.syllabus_versions.<科目>.versions.<后一个标签>`。
   理由写进规格：大纲没变就不新增标签；这样 `effective_version()` 唯一。补"两标签同路径"负例，并加一条测试证明标签顺序互换不改变 `effective_version()` 结果。

## 同时做（sol 建议，决策者采纳）

5. `SyllabusMapping` 保存旧树 ID 集；`targets(old_id)` 对旧树里没有的 ID 抛 `ContractError`（H4b 迁移复习队列时，悬空 ID 必须被报出来，不能被当作"原样保留"）。规格同步。
6. 映射文件未知键排序改为 `key=str`，混合类型时仍以带字段路径的 `ContractError` 拒绝（根与 `changes[i]` 两处）。
7. `Workspace.require()` 对 `reference.syllabus_versions.<科目>.mappings`：只有该科确实登记了版本时才报"field is a path list; use require_all"，否则报"not registered"，与 `require_all()` 一致。

## 不做的

- 不做版本链解析（2026→2027→2028）、不迁移复习队列、不改 `ky/storage/`（H4b）。
- 不改数据文件、不改 `def56be` 里那 5 个测试辅助函数。

## 测试

在 `tests/contract/test_syllabus_mapping_port.py` 与 `tests/contract/test_workspace.py` 里给 1–7 每条加精确回归（断言错误子串 / 路径），B3 的越界用 junction 探针可仿照已有 junction 测试（先 `rg -n junction tests`），无权限时跳过并说明。
每条负例临时撤掉对应检查确认变红，再还原，写进报告。不写数据量字面量。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_syllabus_mapping_port tests.contract.test_workspace tests.test_verify_tree_shapes tests.contract.test_knowledge_tree_port tests.contract.test_subject_onboarding
```

## 报告

`review/rounds/round-70-wp-h4a-sol69-fixes-luna.md`：逐条落点、撤检查变红记录、验收输出。全量：未跑。不提交。含中文文件查 `???`。
