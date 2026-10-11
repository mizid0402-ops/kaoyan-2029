# 第 210 轮：技术债包 B 整表迁移复审（sol61-main）

结论：**FAIL**。三张生成表的输入和原 expected_success 已逐项保留，第 204、206、208 轮
全部必须改项的保护已关闭。但本轮“只退役多错误组合”的新要求尚未完全落实：workspace
退役集合里有三条实际上只有一个错误的变体。补回这三条即可，不要求恢复旧版对照框架。

已读 209 任务书、实现报告、208 评审，并回核 204 / 206 必须改清单。沿用
code-review-gate 和 AGENTS.md；范围只涉及本轮指定的四份测试文件。未改实现或测试、
未提交；本报告为本轮唯一仓库写入。没有跑全量或冒烟测试。

## 必须改

### M1：按名字过滤误退役了三条单错误 workspace 输入（MAJOR）

位置：`tests.contract.test_workspace.WorkspaceContractTests.test_single_error_variant_table`
的 `name.startswith("double-error-")` 过滤。

误退役的原变体是：

```text
double-error-schema-before-supplementary
double-error-schema-before-products
double-error-schema-before-settings
```

可复现输入：从固定提交 `f52b8f6:kaoyan.workspace.yaml` 取合法底稿，分别删除
supplementary / products / settings，再令 schema_version='2'（字符串）。
三条原 expected_success 都是 False，要求当前抛 ContractError。

这三个块本来可选，缺失不是错误。独立实测：原输入均在 schema_version 拒绝；
**只把 schema_version 修回整数 2，仍保留对应块缺失，就全部成功**。
因此三个名字虽含 double-error，实际只有 schema 类型这一处错误；不是两个错误的首错次序探针。

209 任务书第 3 条明确为“只退役”多错误组合，用户本轮又要求查单错误误归类。
不能凭历史名字把这三个输入一起过滤。它们有独立当前拒绝期望，应留在正式表中。
208 轮按名义上的 double-error / paired 类别接受旧新顺序比较退役；本轮逐项验证发现
上述三个例外，故收窄该判断。不是新增实现缺陷，也不重开已接受的 CLI / ledger 修复。

修法：把三条从 retired 集合移回 cases，继续使用原 expected_success=False 和
assertRaises(ContractError)。数量按当前实际产出将为 workspace 36 迁移 / 19 退役，
合计退役 100；数字写报告即可，不钉死到测试。其余确实为顺序组合的输入继续退役。

## 建议改

无新增独立建议。报告“103 条都同时含两个或更多错误”的说明随 M1 一并修正。
整表迁移的方向成立，不再逐项寻找替代测试，也不要求补旧异常全文比较。

## 不改：生成器、期望和比较器核对

独立探针用 git show 读取固定提交
`f52b8f6f2a6145e86970844278acf197184597d9` 的三个原生成器及其输入辅助函数，
仅提取输入构造函数执行，没有加载旧版 validator 或旧测试类。
同时核对该提交与当前 SUBJECT_KEYS、REVIEW_ITEM_KEYS、SCHEDULE_KEYS、
MAX_SINGLE_PASS_MINUTES，以及三份种子 YAML 的内容一致。

对每个变体按名字比较完整 document 和 expected_success：保留字典键顺序及值类型，
区分 True 与 1；NaN 只按 NaN 类型 / 值类别比较，避免 NaN!=NaN 造成假差异。

| 表 | 原 / 新总数 | 正式 subTest 实际执行 | 实际过滤 | 输入与期望 |
|---|---:|---:|---:|---|
| Config | 104 | 61 | 43 | 全部逐项一致；生成顺序也一致。 |
| ReviewItem | 93 | 55 | 38 | 全部逐项一致；生成顺序也一致。 |
| Workspace | 55 | 33 | 22 | 全部逐项一致；duplicate-path 变体在列表中的位置改变，未改其输入 / 期望。 |

正式执行集合从 unittest 的真实 addSubTest 回调收集，未凭复制过滤表达式推定。
209 报告列出的 43 / 38 / 22 条名字与实际过滤集合完全一致；合计确为 103。
其中三条不符合多错误退役条件，见 M1。其余构造保留原跨段双错误 / paired 关系。

config-hard-ratio-order-probe 中 reserve=0.4 本身合法，但 hard=0 同时违反
hard>=reserve 与 hard>0 两条约束，原用途是比较这两条检查的先后；独立 hard>0 输入
config-hard-ratio-must-be-positive 仍保留。它与“删除可选块并不会增加一个错误”的
三个 workspace 例外不同，不为它另开返工。

原 `_compare_config`、`_compare_review`、workspace `_compare` 确实只把异常 path
放入 outcomes 后比较旧新结果，没有为单错误变体另写固定 path 字面量 / 期待表。
它们独立固定的是当前成功与 expected_success 一致，以及当前错误为 ContractError。
因此新表不从本次运行抄 path、只保留成功 / ContractError 类别，符合任务书第 2 条。

三个正式方法只调用当前 validate_config / validate_review_item / load_workspace；
没有旧版加载、git 取源码、恒 skip 或当前输出反推 expected_success。
tests._fixtures 的新增共享函数只构造输入；LegacyConfigView / git_source 未借本轮扩大用途。

## 第 207 轮零散方法与第 208 轮具体缺项

| 原保护 | 整表实际覆盖 |
|---|---|
| revision=True 专项 | review-type-revision，False，当前 ContractError。 |
| review 必填 / 可选字段删除 | review-missing-*，原三个可选字段均在 seed 首项中，逐项真实删除并执行成功分支；其余拒绝。已解决旧方法对两个可选字段直接 continue 的描述问题。 |
| schedule 必填删除 | review-schedule-missing-* 全部执行拒绝分支。 |
| workspace 顶层删除 | missing-top-level-*：supplementary / products / settings 成功，其余拒绝。 |

删除这三个零散方法合理，覆盖由一套正式表承担。
第 208 轮 R2-a 的 project_id=12、subjects 字符串、subject ID / active 类型和子字段缺失；
R2-b 的各 review 类型、非法日期、root 非 mapping、quality / last-review 边界及 schedule
类型 / 下界；R2-c 的 schema 类型、reference/profile 形状、syllabus 单错误、paper_shapes
类型 / 路径与 weight_batches 类型，均在旧新逐项一致的集合中，并实际进入保留 subTest。
没有把 root-not-mapping 再当作组合次序探针过滤。

## 历轮必须改项关闭情况

这里区分此前已独立实测且本轮未改的项目，与本轮整表新验证的项目，未把实现者的全模块
验收结果冒充本轮实跑。

| 轮次 / 必须改 | 关闭证据与现存位置 |
|---|---|
| 204 M1 partial-skip | tests.test_cli.DayPlanCliTest 的 test_record_partial_question_lookup_failure_keeps_earlier_candidate / test_record_partial_question_lookup_failure_prints_text_hint 仍保留；206 轮实跑及变异已通过，本轮未改。 |
| 204 M2 record 故障状态 | 同类的两个 record_*failure 方法及真实子进程注入仍保留；207 补错误标记，208 已用临时 CLI 源码提前失败证明诊断防假通过。本轮未改。 |
| 204 M3 校验器 CLI / 双错固定期望 | tests.test_round24_weighted_tree 中三个 test_validator_cli_* 方法及 tests.test_round29_tree_split.AgreementValidatorRealFileTest 的两个 test_agreement_validator_cli_* 方法仍保留。206 已独立验证，round24 成功路径的资源 skip 限制沿用前轮记录。 |
| 204 M4 citation 六项 reason | tests.test_citation_gate.CitationGateTest.test_strict_bulk_report_preserves_all_six_reason_values_in_rule_order 保留；207 元信息修正、208 实跑通过。本轮未改。 |
| 204 M5 restore 八项状态 | tests.contract.test_material_restore_port.MaterialRestorePortTests.test_check_only_reports_all_eight_material_row_states 保留，206 已实跑通过，本轮未改。 |
| 206 R1 migrate 失败阶段 | tests.test_cli.SnapshotCliTest.test_review_queue_migration_rejects_unregistered_source_version 保留合法空队列与 mappings / unregistered-version 诊断，208 已实跑通过。 |
| 206 R2 models / workspace 变体保护 | 本轮三张表逐项固定输入 / 期望，并实际执行所有原单错误缺项；关闭。新增退役例外另列本轮 M1。 |
| 206 R3 rights 整块拒绝 | tests.test_ledger.LedgerContractTest.test_non_mapping_rights_values_are_rejected 保留，208 已实跑通过。 |
| 208 R2-a / b / c | 上节列出的全部具体缺项均进入正式表；本轮实际执行通过，关闭。 |

因此，**204 / 206 / 208 的全部必须改项已关闭**；包 B 仍因本轮 M1 尚不能给 PASS。
不是要继续扫描包 B 的其他范围，只需修正三条退役分类。

## 独立源码变异与复现

选择与实现者 project_id / last_quality / paper_shapes 不同的字段：
临时 ky/models.py 的 schedule.interval_days minimum=1 改为 0。
先直接验证同一临时源码确实接受 interval_days=0，再运行当前正式
`tests.test_contracts.ReviewItemContractTest.test_single_error_variant_table`。

结果：variant='review-interval-lower-bound' 在 assertRaises(ContractError) 处失败，
`ContractError not raised`；1 test，1 failure。没有在测试侧 patch 被测函数。
runner 断言 ky.__file__ 来自临时 checkout，排除误测回当前工作区。

系统临时探针命令：

```powershell
py -3.12 -B $env:TEMP\round210_audit.py
py -3.12 -B $env:TEMP\round210_audit.py --inputs-only
py -3.12 -B $env:TEMP\round210_report_names.py
py -3.12 -B $env:TEMP\round210_mutation.py
```

证据目录：

- `C:\Users\Lenovo\AppData\Local\Temp\round210-audit-d2t94rwl`：三个正式表输出、实际迁移 / 退役名字集合；三条单错误退役的反证见 audit 脚本输出。
- `C:\Users\Lenovo\AppData\Local\Temp\round210-mutation-99wkbzie`：临时 ky 副本、runner、stdout / stderr 与失败子测试。

正常验证只运行三个正式 table 方法，**3 tests，0.240s，OK，无 skip**。
输入比较再次加强为保留字典顺序时使用 --inputs-only，没有重复跑测试。
本轮没有重跑作者的 117 条验收或全量；已有未改项沿用此前独立验证，并现场确认保护仍在。

## 临时文件与安全登记

git diff --check -- tests 通过；当前 ky 工作区 diff 为空。
检查 review / tests 中 probe、mutant、mutation、temp 名字：没有 209 探针或临时副本遗留，
命中的是既有 D11 probe-root 任务书 / 报告。

无新增安全登记。M1 是本轮明确迁移 / 退役边界的执行问题，不涉及扩大安全防护。
