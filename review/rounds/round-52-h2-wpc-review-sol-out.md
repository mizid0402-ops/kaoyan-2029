# Round 52 Codex 评审：WP-H2 与 WP-C 非 D8 部分

范围：`00398b0` 全部 H2 改动；`57dc49c` 仅自评记录、裁剪排序及质量映射。D8 已由 D8′ 取代，本报告不评价同日冲突、`out_of_order`、CLI 冲突预检或旧队列幂等规则。为避开主工作区正在进行的修改，运行验证使用 `5e1f2ff` 的系统临时目录归档；未跑全量测试。

## 1. WP-H2（00398b0）：FAIL

| 项目 | 判断 | 证据与处理意见 |
|---|---|---|
| 科目档案 v2 | 不改 | `ky/workspace.py:307-366,462` 校验 v2 档案、语法、分域与功能开关，并冻结映射；`kaoyan.workspace.yaml` 已改为档案映射。对应 `contracts/workspace.md:140-166`。隔离副本 `tests.contract.test_workspace`：13 个通过、1 个跳过。 |
| `verify_tree` 科目选择 | 不改 | `tools/verify_tree.py:65-101` 先匹配生效树，再匹配补充树；已登记树与显式 `--subject` 不一致时报 `subject` 违约；未登记候选树须显式指定已知科目。隔离副本直接探测分别得到 `cs408`、`cs408`、冲突错误、显式候选 `cs408`；`tests.test_verify_tree_shapes`：23 个通过。符合 `contracts/workspace.md:166-170`。 |
| 新科目演练 | 建议改 | `tests/contract/test_subject_onboarding.py:103-234` 在临时工作区只改注册表与数据，验证新科目树、台账加载、快照与投影，1 个测试通过；它确实证明**沿用现有语法**的一个新科目可由数据接入。但台账只直调 `load_ledger(..., subject_ids=...)`（153-157），没有调用 `ky ledger --workspace`，未覆盖下述 CLI 问题。建议补 CLI 用例。 |
| 台账 CLI 的注册表发现和内嵌路径根 | **必须改 M1** | `ky/__main__.py:316-325` 无条件 `load_workspace(args.workspace)`；`--ledger` 与 `--root` 均显式给出时，在无注册表的系统临时目录运行 `py -3.12 -m ky ledger --ledger <归档>/data/materials.yaml --root <归档> --json` 仍报 `kaoyan.workspace.yaml not found`。与 `contracts/workspace.md:189-192` 的完整显式输入无需注册表冲突。另在给 `--workspace`、显式台账放到另一临时目录而不传 `--root` 时，JSON 的 `root` 是台账文件的祖目录，不是 `Workspace.root`（代码 318-324）；与内嵌路径按工作区根解析的 `contracts/workspace.md:120-122` 冲突。应区分独立显式模式与工作区模式；后者默认根取 `workspace.root`，显式 `--root` 仍优先。独立模式的科目集合来源也需在修复时明确，不能仅删除 `load_workspace` 一行。 |
| 注册表默认台账未经过 `require` | **必须改 M2** | `ky/__main__.py:317` 直接取 `workspace.ledger`，与 `contracts/workspace.md:194-201` 的按需 `require(key)` 冲突。Windows 临时工作区把 `data` 设为指向工作区外的 junction，`ky ledger --workspace <临时注册表> --json` 仍成功读出 JSON；同一注册表的 `workspace.require('reference.ledger')` 报 `resolves outside the workspace`。注册表默认路径应取 `workspace.require('reference.ledger')`。 |
| 投影与快照消费档案 | 不改 | `ky/projection/__init__.py:76-79` 按档案 `domain_segment` 决定 `domain`；`ky/schedule/state_snapshot.py:210-218` 按 `features` 决定词汇段是否启用；`ky/ledger/material.py:724-744` 接受工作区科目集合。与 `contracts/workspace.md:168-172` 一致。隔离副本 `tests.contract.test_projection_port` 13 个、`tests.contract.test_state_snapshot_port` 9 个、`tests.test_ledger` 30 个均通过。 |
| `named_chapters` 语法说明 | 建议改 | `contracts/workspace.md:160-163` 只列章节 ID 以 `.chapter` 结尾；`ky/knowledge/tree_grammar.py:102-112` 还强制每章有 `.content` 与 `.requirements`。临时新科目树改用 `.topics`、`.goals` 时验证器报缺这两节。现有语法策略可自行定义约束（`contracts/workspace.md:158`），故不判实现缺陷；但应在规格说明该策略的完整约束，避免把“章节后缀符合”误认为可直接复用。 |

上述两个“必须改”均在隔离副本复现，故 H2 **FAIL**。相关测试最初因归档不含 Git 忽略的原始资料文件而失败；补入仓库现有的三份原始资料到**系统临时归档**后，`tests.test_verify_tree_shapes` 23 个通过。这是测试环境缺料，不计作提交缺陷。未修改仓库数据。

## 2. WP-C 非 D8 部分（57dc49c）：PASS

| 项目 | 判断 | 证据与处理意见 |
|---|---|---|
| 自评写回及裁剪核 tie-break | 不改 | `ky/schedule/completion.py:163-165` 有新自评时写入 `last_self_rating`，未给自评时保留旧值；`ky/schedule/review_clip.py:197-213` 将其用于其他优先级相同后的排序。`tests/contract/test_review_progress_port.py:50-76,99-129` 断言纯自评不改变排程但更新记录，并验证裁剪选择受到该值影响。隔离副本该契约模块 5 个通过，`tests.test_completion` 20 个通过。 |
| outcome → 质量映射归算法 | 不改 | `ky/schedule/completion.py:90-109` 的 `LadderSm2Algorithm.progress_quality()` 持有 `correct/partial/incorrect → 4/3/1`，`check=none` 返回 `None`；`advance()` 调用该方法。`tests/contract/test_review_progress_port.py:79-90,130-148` 断言映射和推进结果。符合 `contracts/review_progress.md:20-35`。 |

本节仅对上述非 D8 改动作 **PASS**；不对将被 D8′ 重写的队列规则给出接受结论。
