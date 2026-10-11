# Round 52 任务书：WP-H2 科目档案（M0 / M2 / M4 / M15，决议 D6）

你是实现者。先读仓库根 `AGENTS.md`（全部规则适用）。**唯一依据：`contracts/workspace.md` §2.5**（schema_version 2 科目档案，决策者已写好）。
目标：加一个考研科目 / 方向（例如农学 `agri314`、数学专业自命题 `mathanalysis`）**只改注册表与数据，不改代码**。

## 要做的（按模块，报告里分节）

1. **M0 注册表**：`ky/workspace.py` 支持 schema_version 2（`subjects` 为档案映射：`name`、`tree_grammar`、`domain_segment`、`features`），只接受 2；
   `Workspace.subjects` 保持为科目 ID 元组（向下兼容调用方），新增 `Workspace.subject_profiles: Mapping[str, SubjectProfile]`（只读）。
   校验：登记了树的科目必须有 `tree_grammar`；`tree_grammar` / `features` 取值必须在已知集合内。升级仓库 `kaoyan.workspace.yaml` 到 v2。
   契约测试 `tests/contract/test_workspace.py` 的 `BASE_DOCUMENT` 与拒绝用例同步（字段路径精确断言）。
2. **M4 树语法**：新建 `ky/knowledge/tree_grammar.py`，把 `tools/verify_tree.py` 里的 `numbered_chapters`（原 cs408 规则）、`named_chapters`（原 math1）、`flat`（原 eng1）三种语法移过去，
   以名字注册（一个策略一个小类或函数，D7：新语法 = 新增一个策略，不改已有的）。`tools/verify_tree.py` 删除 `SUPPORTED_ROOT_SHAPES` 等写死的科目表，改为：
   加 `--workspace`，按"这棵树登记在哪个科目下 → 该科档案的 `tree_grammar`"选语法；树根命名空间必须等于该科目 ID。**对现有三棵树的校验结论必须与改动前一致**（输出逐字节一致，见 `AGENTS.md` 第 11–13 条）。
3. **M2 台账**：`ky/ledger/material.py` 的 `SUBJECT_IDS` 常量改为"注册表科目 ∪ 台账分类 `{general}`"，由调用方传入；`ky ledger` 加 `--workspace`，显式 `--ledger` 仍覆盖路径。
   对现有 `data/materials.yaml` 的校验结论不变。
4. **M15 投影**：`_domain_of` 的 cs408 特判改为读科目档案 `domain_segment`；投影内容对现有数据**逐字节不变**（用改动前版本对照）。
5. **替换演练（新科目）** `tests/contract/test_subject_onboarding.py`：临时工作区登记一个新科目（如 `agri314`，`tree_grammar: named_chapters`）+ 一棵最小合法树 + 一条台账资料，
   断言：注册表加载、`verify_tree`、台账校验、快照（`tree_total` 有值）、投影（`knowledge_points` 有该科行、`domain` 为空）**全部接受，且没有改任何代码**。再登记一个语法不符的树，`verify_tree` 拒绝。
6. `docs/模块地图.md`：M0、M2、M4、M15 行与"缺口形状"表中"科目是代码常量"一行更新。

## 不做的

- 卷面形状、出题单位（H3）、大纲多版本（H4）、权重流水线（H5）。
- 不改 `data/` 下任何数据文件（只改 `kaoyan.workspace.yaml`）。不提交。

## 验收

`py -3.12 -m unittest tests.contract.test_workspace tests.contract.test_subject_onboarding tests.contract.test_projection_port tests.contract.test_state_snapshot_port tests.test_ledger tests.test_verify_tree_shapes tests.test_tree_integrity`；
`py -3.12 tools/verify_tree.py <三棵生效树>` 与改动前输出一致；`py -3.12 -m ky ledger --ledger data/materials.yaml` exit 0。全量不跑。写完检查无 `???`。

## 产物

报告 `review/rounds/round-52-wp-h2-luna.md`（用 `apply_patch` 写）。
