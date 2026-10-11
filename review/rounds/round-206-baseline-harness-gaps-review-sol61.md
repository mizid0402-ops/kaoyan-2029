# 第 206 轮：技术债包 B 返工复审（sol61-main）

结论：**FAIL**。第 204 轮 M1–M5 的主要缺口已补齐，M1 / M3 原定变异现在会使新测试变红，
M2 子进程注入实测生效。仍有一条新增用例在错误的阶段失败，以及本轮剩余删除项扫描发现的
两组独立拒绝断言未迁移。无需恢复八个旧对照文件。

范围仅为 `git diff f52b8f6 -- tests` 中第 205 轮新增 / 修改部分，并按任务要求回查八个
已删文件的剩余断言。基线完整哈希为 `f52b8f6f2a6145e86970844278acf197184597d9`。
未修改实现或测试，未提交；报告是本轮唯一仓库写入。沿用 code-review-gate 和 AGENTS.md，
未跑全量。已读 205 任务书、实现报告和 204 评审。

## 必须改

### R1：未登记来源版本用例实际因队列不存在退出（MAJOR）

位置：`tests/test_cli.py::SnapshotCliTest.test_review_queue_migration_rejects_unregistered_source_version`。

原固定提交 `_case_args(..., 'review-queue-unregistered-version')` **先 `_write_queue(root, [])`**，
再运行 migrate，from 为 `unregistered-version`、to 为登记生效版本。
新测试没有创建队列，直接把不存在的路径传给 `--store`，所以没进入版本校验。

实测同一正式测试通过时 stderr 是：

```text
contract violation: file does not exist: <系统临时目录>\review-queue
```

以完全相同的 CLI 参数、只补上原输入的 `ReviewShardStore(queue).write([])` 后，stderr 为：

```text
contract violation: mappings: no mapping path unregistered-version -> 2026
```

其中 2026 来自本次注册表生效版本，不应写死到测试。
当前“退出 2、无 traceback”是另一个输入错误造成的假通过；它不保护来源版本拒绝。
这是本轮自查新增用例自身的问题，不是另起范围的实现缺陷。

修法：创建原来的合法空队列，再运行命令；除原退出码期望外，检查实际诊断指向
unregistered-version / mapping 路径拒绝，防止其他前置错误再次让测试假通过。
复现命令为文末 `round206_probe.py`；原输入出处为
`git show f52b8f6:tests/test_cli_split_baseline.py` 的 `_case_args`。

### R2：models / workspace 生成变体含独立接受与拒绝期望，不能整块称为已有等价（MAJOR）

第 204 轮对这两项“已有等价”的判断过宽。本轮按要求扫描剩余条目，确认原测试不仅比较新旧
结果：还直接检查当前是否成功，并对拒绝结果直接检查 ContractError。

具体复现输入：原 `test_models_split_baseline.py::_review_variants` 的
`review-type-revision`，将 reviews-normal.yaml 第一项的 `revision` 设为 `True`，
期望当前 `validate_review_item` 拒绝且为 ContractError。
原 `_compare_review` 直接断言 `expected_success=False`，还通过
`_exception_for_review` 检查 **当前**异常类型。

实测当前正确实现确实拒绝该输入。在系统临时源码中仅把 revision 解析从

```python
_require_int(node.get("revision"), f"{label}.revision", minimum=1)
```

改为先 `int(node.get("revision"))` 再调用原校验后，True 被接受为 1。
203 / 205 报告指定的 `tests.test_contracts.ReviewItemContractTest` **11 条仍全部通过**。
测试规划中的 RoutePlan revision=True 拒绝不是 ReviewItem 的同一接口，不能代替此项。
探针保持临时模块的 ContractError 与现存测试使用的错误类一致，排除了副本导入身份造成的假红。

同一原变体表还直接规定各 review 必填字段 / schedule 必填字段缺失、bool 类型、日期值、
defer_count、last_quality 等输入的成功或拒绝类别。现存 ReviewItemContractTest 中的
类别枚举、minutes 上限、ease 范围等并不覆盖全部这些输入；不能只凭“都测了模型”删除其余行。
配置部分应同时对照 `tests/contract/test_config_port.py`：该模块确实有逐必填字段、
bool / number 类型与策略形状保护，已有真等价的行不必重复迁移。

workspace 同理：原 `_registry_variants` 逐顶层键删除时，supplementary / products / settings
可选，其余被固定为拒绝；`_compare` 对当前结果直接检查成功与 ContractError。
例如 `missing-top-level-state` 是直接拒绝期望。现存
`test_3_structure_rejections_report_contract_paths` 覆盖 missing version、空 subjects、
unknown reference 等，但没有逐必填顶层块缺失的输入，不能把它当该生成表的整块等价去向。

修法：对这两张原变体表按单项输入映射现存直接断言；没有真等价的，迁到对应正规契约模块，
保留原成功 / ContractError 期望，不加载旧模块。至少补上上述 revision=True 与
workspace 必填块缺失的保护。旧异常全文比较、旧函数身份 / 长度，以及仅为旧新校验次序
比较而存在的组合脚手架可继续退役，不要求重建旧基线框架。

复现来源：`git show f52b8f6:tests/contract/test_models_split_baseline.py` 的
`_review_variants` / `_compare_review`，以及同提交 workspace split baseline 的
`_registry_variants` / `_compare`。变异实测见文末探针。

### R3：material rights 整块无效的拒绝断言仍未迁移（MAJOR）

原 `test_storage_ledger_split_baseline.py::test_validate_material_matches_fixed_baseline_and_error_paths`
有独立的当前断言：有效 local-file 材料分别替换 `rights` 为
`None`、`'wrong-type'`、`{}`、`{'unknown_right': True}`，每项都必须抛 ValueError。
`with self.assertRaises(ValueError) as new_error` 不依赖旧版；只有之后的异常全文 / 路径相等
比较属于可退役部分。

第 203 轮将本项称为“没有独立于比较的额外当前值断言”不正确，205 自查也未补它。
本轮查看 `tests/test_ledger.py`、`tests/contract/test_ledger_port.py`：已有未知 rights 子键、
权限布尔值、权限间约束保护，但前者的拼错键和后者 `may_display=None` 不是
**整个 rights 块为 None / 字符串 / 空映射**的同类输入。unknown_right 的未知子键拒绝
有同类现存保护，可以注明等价后不重复迁移；不能据此把另外三项也一起删掉。

复现：按原 `_material_raw('fixture-material', 'data/raw/item.txt', b'payload')` 构造
合法材料，逐项换 rights，调用当前
`validate_material(..., source='fixture.yaml', subject_ids=原登记科目集合)`。
当前 ValueError 拒绝期望仍应存在，只需迁移缺少等价的直接断言到正规 ledger 测试。
不要求迁移旧新错误文本比较，也不扩展恶意路径或并发防护。

## 建议改

### m1：M4 的夹具元信息没有逐字段照搬，报告应注明（MINOR）

新的六项 citation reason 列表和次序与原期望完全一致，路径、digest、材料 ID、知识点 ID、
strict 模式及空 root 均对应原六个拒绝场景。测试已实际通过。
但复用现有 helper 后，原 point 的 raw / manual 变成 extracted / official_outline，
并增加 transition history；原材料默认 unreviewed 变为 verified，
unclear 材料的 may_be_structured 原为 True，新测试为 False。
所以不能称作所有原字段都原样复制。

本轮未发现这些元信息改变六类 reason 的现有判定；原未知 rights 且 structuring=True 的
许可门禁另由 `RightsGuardTest.test_unknown_status_with_structuring_flags_loads_but_stays_closed`
直接保护，因此不为这组夹具差异再判 M4 阻断。
建议使用原小型 raw fixture，或在报告注明这些差异及等价理由，方便后续追溯。

### m2：M2 正式断言可同时检查强制错误标记（MINOR）

本轮已独立验证两次真实子进程 stderr 包含 forced freeze write error / forced advance failure，
注入当前确实生效。正式测试只检查退出码、事件文件和无 traceback；建议把这两条标记也断言，
避免今后 fixture 提前失败时，尤其 freeze 场景仍满足“2 + 无事件”而假通过。

## 不改：原返工项逐条结果

| 项 | 原输入 / 期望对照与本轮结论 |
|---|---|
| M1 JSON | 两条 fluent / unchecked；首科有索引，次科无索引。ID 与四项候选 / skip 断言相同；日期和 knowledge-point 名称使用现存 CLI fixture，实际到达第二项失败分支。原 drop-earlier-candidate 变异产生 AssertionError，未变异通过。 |
| M1 文本 | 相同两项查询场景，stdout 行以“出题查询失败”开头。移除 skip 原因的变异产生 AssertionError，未变异通过。 |
| M2 freeze | 合法单项复习，子进程替换 `_latch_freeze_if_needed` 抛原 StorageError；实际退出 2、stderr 为强制错误、完成事件数 0。不是导入失败 / 无效输入造成的通过。 |
| M2 advance | 合法单项复习，子进程替换 `advance_review_queue` 抛原 ContractError；实际退出 2、stderr 为强制错误、完成事件数 1。保留“先写事件再推进失败”的原语义。 |
| M3 round24 | 成功 main 返回 0；首节点 approved 错误返回 1 并输出原诊断；双错误 approved + sources=[] 的四项 reason 与顺序、main 退出 1、两条输出诊断均迁入。新测试对来源文件校验作隔离，只锁定原四项节点错误，未抹去节点错误。成功项因外部来源缺失 skip，两个错误项实际通过。 |
| M3 round29 | 实际调用当前 main；正常返回 0，首条 source_support=0.42 返回 1 且输出原诊断。第 204 轮 return 1→0 的同一定点变异现在导致新测试 AssertionError。 |
| M4 | 六个拒绝场景与完整 reason 列表 / 次序有直接保护；元信息差异见建议 m1，不能描述为逐字段一致。 |
| M5 | 八行 ID、路径、URL、字节与权限条件和原 _restore_raw 一致；subject 使用正规端口 fixture alpha，原也是调用方提供科目集。八项状态完全相同；forbidden 网络函数与 TemporaryDirectory 抛错也保留。单方法实跑通过。 |
| 第 204 轮 m1 命名 | index/tree 两方法已改为 emit_expected_diagnostics / have_expected_cli_diagnostics，不再宣称 fixed baseline / fixed CLI。 |

M1 正式测试未读取旧 CLI，M2 runner 仅导入当前 ky；M3–M5 也只调用当前实现。
固定提交只用于本轮评审取证。没有借旧新对照让迁入用例继续依赖旧实现。

## 新增 CLI 场景与剩余扫描

用户提到四个场景；报告和 diff 实际还新增一项 route 空 store 成功，共五项。

| 新增用例 | 原固定提交对应输入与结论 |
|---|---|
| route show --revision 0 | 原 route-invalid-revision，空 store / revision 0 / 退出 2；区别于旧 route submit invalid-plan，补迁合理，实跑通过。 |
| snapshot 缺配置 | 原 snapshot-missing-config，reviews / workspace 有效、config 文件缺失、退出 2；区别于内容无效配置，补迁合理，实跑通过。 |
| review-queue check | 原 registered empty queue / 退出 0；新用例实际创建合法空队列，直接调用当前 CLI，实跑通过。 |
| review-queue migrate 未登记 from | 原合法空队列，当前却未创建，失败阶段不等价，见 R1。 |
| route show 空 store JSON | 原 route-success，没有 route revision、JSON 请求、退出 0；新用例一致，实跑通过。 |

另对第 204 轮抽查之外的余项查看原方法及现存去向，没有重跑它们的模块全集：

| 剩余项 | 扫描结果 |
|---|---|
| ledger 成功 / schema 99、month-close 空计划目录 / month 13、resume 空队列 | 现存 LedgerCliTest、MonthCloseCliTest 和 ResumePortContractTests 有相应成功 / 拒绝码与状态直接保护；不是仅以不同子命令替代。 |
| Eng1 / NetEM verifier 成功、缺 SQLite、usage | 现存 verifier regression 方法实际执行当前工具检查 0；tool_exit_paths 有 missing DB / usage 期望；外部 PDF 的 require_path 不代表恒 skip。 |
| manual、NetEM cross-validation、PDF skeleton | 现存测试直接检查当前成功 / 文件输出；NetEM 正规方法检查输出统计字段；missing PDF 退出 2 已保留。原 old==new 文件树比较可退役。 |
| HTML extractor / question verifier、PDF probe | 203 迁入的方法只执行当前工具；成功、非 PDF / 参数失败期望有去向，本轮未改这些测试，不重复跑已确认模块。 |
| schedule 的 review selection / monthly close / invariant / snapshot overrides / completion parser | 原方法主要断言 `_call_bytes(old)==_call_bytes(new)` 或对象相等；completion 的三个多错误输入未另固定当前错误值。按既有裁定退役，无新发现的独立固定期望。 |
| shard commit / day-plan write | 原方法比较新旧 report / 文件树，没有独立当前固定字节值；端口写入 / 队列事务保护仍在。 |
| material validation | 原四种 rights 形状有独立拒绝期望，其中整块无效的三项尚无去向，见 R3。 |
| models / workspace seed 与变体 | 发现当前成功 / 拒绝的独立期望，不能整块称为已有等价，见 R2；其中旧源码身份、长度、变体命名唯一性等脚手架不要求恢复。 |
| resume tier / scheduled_to_queued_count=0 | 现存 scheduled backlog / resume 端口仍直接检查相应日期边界、tier、计数，非旧新相等即可。 |
| 其余 CLI record / preflight 的多错误顺序比较 | 无新增独立固定诊断序列；已拒绝的输入类别和写入保护由既有测试及本轮 M2 承担，原 stdout/stderr 新旧相等部分按裁定退役。 |

## 独立验证与证据

系统临时探针：`C:\Users\Lenovo\AppData\Local\Temp\round206_probe.py`。

```powershell
$env:PYTHONIOENCODING='utf-8'
py -3.12 -B $env:TEMP\round206_probe.py
```

成功证据目录：`C:\Users\Lenovo\AppData\Local\Temp\round206-sol61-dmv3zk6x`。
包含 M1 两次、M3 一次 AssertionError 的测试输出；M2 两个真实子进程的 stderr 与事件文件；
错误阶段不同的 migrate stderr；revision=True 变异源码与现存 11 条 review 测试通过输出。
所有变异仅在临时源码 / 进程内 patch 下运行，未改仓库实现。

直接相关的正常验证：

- 五个新增 route / snapshot / review-queue 方法：5 tests，1.324s，OK；其中 migrate 的通过为 R1 假通过。
- round24 三个新方法与 round29 成功方法：4 tests，3.288s，OK，skip 1；skip 是 round24 来源资源缺失。
- M4、M5 两个新方法：2 tests，0.057s，OK。
- 探针单独运行 M1 / M2 四个新方法及 round29 错误方法，未变异均通过且无 skip；原定变异在正确断言处失败。

未把实现者自报的 118 条算成本轮独立实跑。全量未跑，按 AGENTS.md 由决策者提交前统一跑。

## 临时文件与安全登记

检查 review/rounds 目录及 `rg --files review tests`：没有 round205_mutation_probe.py、
round205 变异源码或探针文件遗留；只有报告内保留其历史命令文本。
实现者曾把探针放入仓库再删除，违反临时文件应放系统临时目录的工作规则；当前无残留，
不要求为已删除文件再开代码返工，后续探针应始终在系统临时目录。

本轮没有新增安全登记项。R1–R3 是删除保护 / 测试输入和错误阶段的问题，
没有扩展恶意链接、攻击注入或并发防护。
