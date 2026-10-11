# Round 69 Codex 复审：H3 收口与 WP-H4a

评审以 `git show bf4c137`、`a92c04f`、`a691cb1`、`def56be` 和两份端口规格为准。执行代码来自系统临时目录的 `git archive def56be`，仅向归档复制本机已有的 gitignore 原始资料。`bf4c137` 至 `def56be` 的真题校验实现、规格和契约测试无后续差异。未改仓库实现，未跑全量测试。

## A. `bf4c137`：第 67 轮两项

| 判断 | 证据与可复现输入 |
|---|---|
| **不改：`kind` / `calibration` 的空值绕过已关闭** | 从 2026 索引造 `calibration: null` 并把首题 `answer_confidence` 改为 `official`，`verify` 报 `$.calibration: must not be null`；造 `kind: null` 报 `$.kind: must not be null`。专门的非空检查在 `tools/verify_408_index.py:67-74,357-362`，与 `contracts/exam_index.md:14-20,27-30` 一致。`tests/contract/test_exam_index_port.py:300-311` 对两者逐项断言目标错误。进程内临时撤掉 `NON_NULL_ENUM_KEYS` 时两个子例都变红，未修改源码。 |
| **不改：三个描述字段恢复可选，契约一致** | 分别删除 `content_policy`、`verified_facts`、`unverified_facts`，三次 `verify(...) == []`；新规格 §1 明示可选，§2 仍用“when present”（`contracts/exam_index.md:14-20,81-82`）。`REQUIRED_TOP_KEYS` 已排除三者（`tools/verify_408_index.py:67-71`）。进程内临时将三者重新设为必需，`test_descriptive_fields_stay_optional` 的三个子例均变红（`tests/contract/test_exam_index_port.py:313-322`）。归档中该模块 15 项通过。 |
| **不改：不因十进制极端值阻断本次收口** | 第 67 轮的 `1e28 + 0.1` 确实超出默认 Decimal 上下文精度，但没有真实卷面分值接近这个量级；决策者在 `bf4c137` 提交说明中明确未采纳。保留为已知数学边界即可，不把它当成本轮现实阻断项。 |

**A 结论：PASS。**

## B. WP-H4a：版本登记与映射端口

| 判断 | 证据与可复现输入、最小处置 |
|---|---|
| **必须改 B1：共同 ID 改走后，新树中同名 ID 可没有来源** | `ky/knowledge/syllabus_mapping.py:203-208` 只检查 `old_ids - new_ids` 和 `new_ids - old_ids`。使用 `tests/contract/test_syllabus_mapping_port.py:20-76` 的合法双树，往有效映射再加 `{from: old_ids[0], to: []}`；该 ID 同时在两树，加载**通过**且 `targets(old_ids[0]) == ()`，但新树同名 ID 没有任何入边。改为 `{from: old_ids[0], to: [new_ids[1]]}` 也通过，新树同名 ID 仍无来源。原样保留只应在该 ID **未列入** `changes.from` 时形成隐式自环；请按“显式目标 + 未变 ID 的隐式自环 + `added`”覆盖**全部**新树 ID，再检查旧树每个 ID 有明示去向或合法隐式自环/删除。给这两种输入补负例。旧树独有 ID 不列变化、以及新树独有 ID 无目标也不在 `added`，现有测试和代码会拒绝；拆分、合并、改名、正常删除/新增的正例通过（`tests/contract/test_syllabus_mapping_port.py:105-147`）。 |
| **必须改 B2：同一 `to` 列表可重复目标** | 在现有拆分项的 `to` 末尾再次附加其第一个目标，形成 `[new_ids[1], new_ids[2], new_ids[1]]`；加载**通过**，`targets()` 原样返回重复 ID。`_parse_changes` 仅把目标加入集合以做覆盖判断，未对单条 `to` 去重/拒重（`ky/knowledge/syllabus_mapping.py:161-172`）。跨不同 `changes` 的同一目标是合法合并，应保留；只拒绝**同一条** `to` 内重复 ID，报 `changes[i].to[j]`。否则 H4b 逐目标迁移可能重复生成同一复习项。 |
| **必须改 B3：映射加载器绕过注册表路径与越界检查** | `load_syllabus_mapping` 直接读调用者传的 `path`，`_load_version_tree_ids` 直接读 `registered.versions[...]`（`ky/knowledge/syllabus_mapping.py:81-85,125-143,211-220`），均未调用公开 `workspace.require` / `require_all`。临时归档探针：把有效映射复制到**工作区外、未登记**的 YAML，传同科目 `subject_id`，加载通过；再将 `versions.2027` 指向工作区内 junction `data/escape/new.yaml`，junction 目标在工作区外，`workspace.require("reference.syllabus_versions.alpha.versions.2027")` 正确报 `resolves outside the workspace`，而 `load_syllabus_mapping(...)` 仍成功读取外部树。Windows junction 在系统临时目录创建，未改仓库。应先以 `require_all(reference.syllabus_versions.<科目>.mappings)` 确认映射文件是该科登记的路径，再用 `require(reference.syllabus_versions.<科目>.versions.<标签>)` 取两树；这样与 `contracts/workspace.md:281-284` 的越界门槛一致。 |
| **必须改 B4：多个版本标签可共用一路径，`effective_version()` 随 YAML 顺序变** | 临时注册表中 `versions: {"2026": data/tree.yaml, "2027": data/tree.yaml}` 能加载；标签顺序 2026→2027 时 `effective_version("alpha") == "2026"`，反序时结果为 `"2027"`。`ky/workspace.py:97-106,363-371` 只检查生效路径在版本值中并返回第一个匹配。路径相同可能代表大纲未变，但 H4b 不能从路径推断唯一生效标签。要么拒绝一科多标签共用同一路径，要么另登记明确的生效版本标签；补顺序互换测试。 |
| **不改：已覆盖的注册表端口与识别顺序按规格工作** | `_registered_path` 拒绝 `..`、反斜杠、绝对路径等（`ky/workspace.py:267-277`）；`require` 可取版本树，`require_all` 可取映射文件元组，对接口类型调用错会报 `ContractError`（`:108-202`）。临时双树中，`verify_tree._registered_subject` 对旧生效树先选 `reference.knowledge_trees.alpha`，对新登记版本选 `reference.syllabus_versions.alpha.versions.2027`；显式 `--subject beta` 与登记科目冲突时报错（`tools/verify_tree.py:65-105`）。实际归档命令 `py -3.12 tools/verify_tree.py data/structured_materials/cs408/knowledge_tree.yaml` 为 `ALL CHECKS PASSED`。指针比较是 `Path` 值比较，不跟随 junction：同一实体的不同 junction 路径会按“登记路径必须相等”被拒，符合字面规格；Windows 默认大小写等价，`..` 无法通过路径语法。大小写敏感目录中的两份仅大小写不同的文件是条件性风险，本轮未构造该文件系统环境。 |
| **建议改：未登记映射列表的 `require` 错误分类** | 对 `reference.syllabus_versions.ghost.mappings` 调 `require()` 得到“field is a path list; use require_all”，但 `ghost` 未登记；同一键调 `require_all()` 得到“not registered”。`ky/workspace.py:167-175,193-202` 的 `require()` 仅按前后缀判断列表。统一先确认该科确有列表，再报错接口类型，可使字段路径诊断一致；不影响已登记路径的取值。 |
| **建议改：未知键混合类型抛原生异常** | 映射根同时增加 YAML 整数键 `7` 和字符串键 `zzz`，`load_syllabus_mapping` 抛 `TypeError: '<' not supported between instances of 'int' and 'str'`，未按 `contracts/syllabus_mapping.md:29-31,54-58` 以带字段路径的契约错误拒绝；源于 `ky/knowledge/syllabus_mapping.py:90-93` 的 `sorted(unknown)`（变化项 `:157-160` 同样存在）。坏数据未被接受，故列为建议；按字符串稳定排序或先拒非字符串键。 |
| **建议改：H4b 须补来源成员判定与版本链解析** | 当前 `SyllabusMapping` 只保存 `changes`；`targets("alpha.ds.chapter-01.section-99")` 对**旧树不存在的 ID**仍返回自身（`ky/knowledge/syllabus_mapping.py:27-36`）。对有效旧 ID，`(old_id,)` 与 `()` 可以区分原样保留和删除；对悬空队列 ID 则不能。H4b 在调用 `targets()` 前必须核对队列 ID 属于 `from_version` 树，或端口保存旧 ID 集并拒绝未知 ID。对 2026→2027→2028，现有记录带 `from_version`/`to_version`，但 `mappings` 只是无序路径列表；H4b 需验证每一步版本连续、唯一链、无重复边/环，并逐步处理拆分与删除，不能直接对旧 ID 调一次 `targets()`。这些是 H4b 设计意见，本包尚未承诺队列迁移。 |
| **建议改：`def56be` 修测试辅助函数合理，但减少了版本登记集成覆盖** | 五处辅助函数在复制注册表后改动 `knowledge_trees` 却保留旧版本路径，触发新一致性检查；删除可选 `syllabus_versions` 使这些**非版本功能**夹具重新有效，符合 `def56be` 提交说明，也没有改生产代码。可是快照、投影、CLI、讲解产线的迁移夹具此后都不再验证“改生效指针时同步版本登记”的场景。建议在 H4b 或工作区契约中保留至少一项**带版本登记**的临时工作区演练，随有效树切换同步更新 `versions`，而不是让所有跨模块测试都绕开新键。现有 `tests/contract/test_workspace.py:69-111` 只守单版本指针；`tests/test_verify_tree_shapes.py:46-58` 只测 `_registered_subject`，不验证完整 CLI 路径。 |

局部验证：归档中 `tests.contract.test_syllabus_mapping_port` 10 项通过；`tests.contract.test_exam_index_port` 15 项通过；工作区新指针测试与版本树识别测试 2 项通过；未跑全量。实际 `verify_tree` 单命令通过。

**B 结论：FAIL。** 映射覆盖对共同 ID 有真实漏检，重复目标会原样流入 `targets()`；版本标签可因路径复用变得含糊，映射加载还能绕过注册表的边界检查。修复后复审限定 B1–B4 与各自精确回归输入。
