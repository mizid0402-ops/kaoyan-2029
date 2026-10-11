# 第 152 轮 · WP-S2：补写 M2 资料台账 / M3 引用门禁端口规格（Opus 实现报告）

执行者：Claude Opus 5.5（实现者）；日期：2026-09-27；基线提交：`b43eb1f`。
范围：只写规格与契约测试，**不改行为**；`ky/__main__.py`、`docs/模块地图.md` 未改动。

## 1. 改动文件

| 文件 | 类型 | 说明 |
|---|---|---|
| `contracts/ledger.md` | 新增 | M2 端口规格：文档形状、条目字段、rights / source_tier 两轴、存储与哈希、来源追溯、审核与历史、派生判定、错误、`ky ledger` CLI、已知限制 |
| `contracts/citation_gate.md` | 新增 | M3 端口规格：引用解析、六条规则及顺序、不属于门禁的事项、严格模式、结果形状、错误、已知限制 |
| `tests/contract/test_ledger_port.py` | 新增 | 39 条契约测试（库 31 条 + CLI 8 条） |
| `tests/contract/test_citation_gate_port.py` | 新增 | 17 条契约测试 |
| `review/rounds/round-152-ws2-specs-opus.md` | 新增 | 本报告 |

实现代码零改动（`git status` 只有上述 5 个未跟踪文件）。测试全部在临时目录里自建台账、注册表、
知识点，不读仓库的 `data/materials.yaml`，不写死资料条数或 `resource_id`；科目 ID 用临时注册表
里的 `alpha` / `beta`（D5/D6）。

## 2. 规格摘要

### M2 `contracts/ledger.md`

- **对外接口**：`load_ledger` / `validate_ledger` / `validate_material`、三个查询
  （`structurable_materials`、`evidence_capable_materials`、`integrity_report`）、`ledger_summary`、
  两个哈希辅助、`LedgerError(.path)`、五个数据类与全部枚举常量（集合内容逐项钉住）。
- **文档形状**：列表，或只含 `schema_version` + `items` 的映射；其他情况在 `<source>.items` 报错；
  `resource_id` 唯一，在第二次出现处报错。
- **允许科目**：显式 `subject_ids` 即完整集合（库**不会**自动并入 `general`）；未给时 =
  注册表科目 ∪ `{general}`，注册表发现失败抛 `ContractError`。
- **两条独立轴**：`rights`（能不能用）与 `provenance.source_tier`（该不该信）。五档可信度，
  缺省最弱档 `community_archive`；只有 `official` / `official_publisher` / `university` 可
  `may_define_syllabus()`。`source_tier` 不参与任何门。
- **rights 七条矛盾校验**按顺序列出，每条给出报错字段路径；`unknown` 可以写
  `may_be_structured: true` 而通过校验，但永远不可结构化（`is_clear()` 为假）。
- **存储**：`local_file` 必须有 path / 64 位十六进制 sha256（载入后小写）/ 非负 byte_size；
  `storage.sha256` 是**本地文件字节哈希**；`remote_reference` 必须有 url，不得带 path / sha256 /
  byte_size。storage 先于 rights 校验。
- **来源追溯**：除 `acquisition: generated` 外，`source_url` / `publisher` / `isbn` 至少一项；
  整块 provenance 缺省同样适用。
- **审核状态**：`withdrawn` 关掉两道门；`verified` 与 `unreviewed` 对门无区别。
  历史只校验保存，当前视图不由历史推导。
- **派生判定**：`can_back_evidence`（未撤回 + 本地有摘要）⊇ `may_be_structured`（再加权利清楚且
  允许结构化）。`verify_bytes` 从不因文件缺失抛错，相对路径在 root 下解析，绝对路径忽略 root。
- **CLI**：三种数据来源模式（独立 / 旧式 / 注册表）成表；`--subject` 在完整校验后过滤；
  `--json` 顶层与每行键集合钉住；退出码 0 = 已报告（**字节不符不改变退出码**），2 = 台账或数据
  来源违约（stderr 前缀 `ledger violation: `，stdout 空），2 = argparse 用法错误；只读。

### M3 `contracts/citation_gate.md`

- 只有 `local_file` 资料进索引，远程引用永远解析不到；路径规范化为 `\`→`/` 再去掉开头所有
  `.` 与 `/`，之后大小写敏感精确比较；两份资料占同一路径 → `LedgerError`（先于任何引用核对）。
- 六条规则依次检查、**只记第一条不满足的**：无台账条目 → 已撤回 → 权利不明 → 不允许结构化 →
  摘要不符（与台账小写摘要精确比较）→（严格模式）字节不符或文件缺失。
- **不属于门禁**：`source_tier`、科目是否一致、`may_display` / `may_redistribute`、
  `review_index`、`verified` 与否。禁止状态落在"不允许结构化"。
- 结果：`checked_citations` 含有问题的引用；问题按知识点、引用顺序排列并全部报告；
  `CitationProblem.path` 是原始路径；`raise_for_problems` 抛 `LedgerError(path="sources")` 列出每条；
  `summary()` 键集合钉住。映射形式的知识点不合 M4 时 `KnowledgePointError` 原样抛出。
  `check_ledger_citations` 经注册表发现科目。

## 3. 代码与旧文档的不一致（规格一律以代码为准）

| # | 旧文档 / 注释 | 代码现状 | 规格处理 |
|---|---|---|---|
| D1 | `docs/模块地图.md` M2、M3 行"端口规格：未写" | — | 本轮补写 |
| D2 | `docs/模块拆分与架构审查.md` M2 审查发现"`SUBJECT_IDS` 写死在 `material.py:105`"；`docs/阶段2.5-接缝收口.md:150` "台账白名单 `material.py:105`"；`contracts/workspace.md:334` 仍称"台账 `SUBJECT_IDS`" | 已改为注册表科目 ∪ `LEDGER_SUBJECT_CATEGORIES`（`_subject_ids_for_validation`），无科目字面量 | §3.1 按现状写；三处旧文档待决策者更新 |
| D3 | 同文 M2"替换时必须满足：`ky ledger --ledger <file>` 校验通过" | 退出 0 **不代表**字节完好：哈希不符 / 文件缺失只体现在 `bytes_verified`；另外只给 `--ledger` 不给 `--root` 时走注册表模式，需要可发现的注册表 | §10.1、§10.3 写明；验收应看 JSON 的 `bytes_verified` |
| D4 | 同文"`verified` 的含义建议在规格里写清楚" | `verified` 与 `unreviewed` 对所有门无区别；只有 `withdrawn` 生效 | §7 写明"`verified` 不表示权利已核实" |
| D5 | `ky/ledger/material.py` 模块 docstring 第 3 条"审计轨迹只追加，当前视图由事件推导" | `history` 只校验并保存；`review_status`、`rights` 等以条目字段为准，不从历史推导，也不校验历史与字段一致 | §7 按现状写 |
| D6 | `ledger_main` docstring "0 = reported, 2 = ledger invalid"；`ky/__main__.py` 模块 docstring "3 = usage error" | `ky ledger` 的用法错误由 argparse 退出 2，本命令没有 3；非 UTF-8 台账抛 traceback（退出 1） | §10.3、§11 |
| D7 | 任务书"how tiers/rights gate use"；`docs/数学一英语一知识树设计说明.md:15` 的"台账的 `source_tier` 判定" | M3 **只按 rights 门禁**，不看 `source_tier`；可信度只经 `Provenance.may_define_syllabus()` 由调用方自行判断 | M3 §3"不属于门禁的事项"，并有测试钉住 |
| D8 | `ky/ledger/citations.py` `__all__` | 漏列 `check_ledger_citations`（包 `ky.ledger` 仍导出） | M3 §6 记录 |
| D9 | `contracts/exam_index.md` 要求 provenance `resource_id` 匹配 `^[a-z0-9][a-z0-9-]*$`、`rights_status` 只取 5 值 | 台账本身不限 `resource_id` 字符集，`rights.status` 9 值 | 不冲突（M5 更严）；M2 §11 记录 |

## 4. 建议（需决策者裁定；本轮未改代码）

按 `AGENTS.md`"评审严重度"判断：

1. **S1（建议列为必须改，日常问题）**：台账文件非 UTF-8（例如在 Windows 编辑器里另存为 GBK）时，
   `load_ledger` 抛未包装的 `UnicodeDecodeError`，`ky ledger` 以 traceback 退出而不是退出 2。
   修法：`load_ledger` 捕获 `UnicodeDecodeError` 转为 `LedgerError`（`.path` 为空），并补一条契约测试。
   已实测：`main(["ledger", "--ledger", <非UTF-8文件>, "--root", ..., "--subjects", ...])` 抛
   `UnicodeDecodeError`。
2. **S2（建议列为必须改，日常问题）**：台账 YAML 的重复键被 `yaml.safe_load` 静默"后者覆盖"。
   手工编辑 `data/materials.yaml` 时写出两个 `rights:` / `storage:` 会静默丢值。工作区注册表与
   `ky.models.load_yaml_text` 已 fail-closed；台账改用同一读取函数即可。
3. **S3**：`CitationProblem` 没有机器可读的规则编号，调用方只能按原因文字区分（与 `AGENTS.md`
   已知缺陷第 3 条冲突）。建议加 `rule` 字段（如 `unregistered` / `withdrawn` / `rights_unclear` /
   `not_structurable` / `digest_mismatch` / `bytes_changed`），规格表已按此顺序排好。
4. **S4**：M4 接受大写摘要，M2 载入时统一小写，而 M3 对引用摘要不做规范化——大写摘要的引用会
   被报"摘要不符"，原因文字误导。建议 M3 比较前小写，或 M4 只接受小写。当前行为已按现状钉住
   （`test_digest_is_compared_exactly_against_the_lowercase_ledger_digest`），改时同步改规格与该测试。
5. **S5（低）**：`_normalise` 用 `lstrip("./")` 去掉开头所有 `.` 与 `/`，`../x`、`.hidden/x` 会被
   当成 `x`、`hidden/x`；本意应是去掉 `./` 前缀。日常数据不会出现，登记即可。
6. **S6（低）**：`check_ledger_citations` 无法传 `subject_ids`，只能依赖注册表发现；目前仓库内
   无调用者。
7. **S7（低）**：`load_ledger` 对目录也报"file does not exist"，文字不准确。

### 安全登记

- **SR1**：`storage.path` 允许绝对路径，`verify_bytes` 直接读取该路径（不受 `Workspace.root`
  约束，与 `contracts/workspace.md` §2.3"内嵌路径相对 `Workspace.root`"的约定不一致）。触发条件：
  手工在台账写入工作区外的绝对路径或经 junction 越界；影响：完整性检查读取工作区外文件（只读、
  只算哈希）。可能的修法：`local_file.path` 按注册表路径语法校验，解析后做两步包含检查
  （`AGENTS.md` 已知缺陷第 5 条）。属"手工篡改仓库内部文件"，不在本工作包修。

## 5. 变异验证（每条新测试一个定向变异）

方法：脚本（系统临时目录，不在仓库）对实现文件做一次字符串替换，设
`PYTHONDONTWRITEBYTECODE=1` 与去掉 `KY_WORKSPACE` 后只跑对应的一条测试，先确认基线为绿，再确认
变异后为红，随后写回原始字节并用 SHA-256 核对。CLI 相关 8 条的变异落在 `ky/__main__.py`
（仅在本 worktree 临时替换、立即逐字节还原；`git status` 显示该文件无改动）。

结果：**56 条变异，56 条变红，0 条漏检；三个实现文件还原后 SHA-256 与变异前一致**：

```
ky/ledger/material.py  64706c27b6066eac6b00ae943343c4ad2ecba8afc326b339aa7409d8b19e8133 True
ky/ledger/citations.py 1f97102dd54efa2906925c06536fd2b5a0be8c58ae4fcc9a79f0dbfa7e4e8924 True
ky/__main__.py         ae2200dd2813a631df88c17605a1f831375b81411cf458fd52e3fc0052e3ab92 True
```

| 测试 | 变异（文件：替换） | 变异后 |
|---|---|---|
| `test_enumerations_equal_the_spec` | material：历史动作集合删去 `superseded` | failures=1 |
| `test_a_list_and_an_items_mapping_are_the_same_ledger` | material：`raw["items"]` → `raw["items"][:1]` | failures=1 |
| `test_the_items_mapping_rejects_other_top_level_keys` | material：顶层允许键加入 `owner` | failures=1 |
| `test_a_mapping_without_items_or_an_empty_document_is_not_a_list` | material：报错路径 `.items` → `source` | failures=1 |
| `test_duplicate_resource_id_is_reported_at_its_second_occurrence` | material：路径下标 `index` → `index - 1` | failures=1 |
| `test_optional_fields_take_their_documented_defaults` | material：`review_status` 缺省改 `verified` | failures=1 |
| `test_explicit_subject_ids_are_the_complete_allowed_set` | material：`validate_material` 自动并入 `general` | failures=1 |
| `test_subjects_must_be_a_non_empty_list_without_duplicates` | material：去重检查改 `if False:` | failures=1 |
| `test_without_subject_ids_the_registry_plus_general_is_allowed` | material：注册表科目不再并 `general` | errors=1 |
| `test_registry_discovery_failure_is_a_contract_error` | material：注册表发现失败时吞掉错误 | errors=1 |
| `test_each_guard_reports_its_documented_path` | material：第 5 条校验路径 `may_display` → `may_store` | failures=1 |
| `test_remote_reference_may_not_store` | material：第 6 条校验改 `if False:` | failures=1 |
| `test_permission_flags_must_be_booleans` | material：`_bool` 只拒绝 `None` | failures=2 |
| `test_unknown_status_with_structuring_flags_loads_but_stays_closed` | material：`is_clear` 恒真 | failures=1 |
| `test_every_status_but_unknown_is_clear` | material：`restricted` 也算不清楚 | failures=1 |
| `test_local_sha256_is_stored_lowercase` | material：摘要不转小写 | failures=1 |
| `test_local_file_field_rules` | material：摘要长度检查 `!= 64` → `< 63` | failures=1 |
| `test_remote_reference_holds_no_local_facts` | material：byte_size 报错路径改名 | failures=1 |
| `test_storage_is_checked_before_rights` | material：先校验 rights（按 local_file） | failures=1 |
| `test_a_missing_provenance_block_is_untraceable` | material：缺 provenance 块时跳过追溯要求 | failures=1 |
| `test_any_one_of_url_publisher_isbn_is_enough` | material：isbn 用 `_str`（拒绝整数） | errors=1 |
| `test_tier_does_not_move_any_gate` | material：`may_be_structured` 加 `may_define_syllabus()` | failures=2 |
| `test_withdrawn_loads_but_closes_both_gates` | material：`can_back_evidence` 不看撤回 | failures=1 |
| `test_verified_and_unreviewed_open_the_same_gates` | material：只有 `verified` 可结构化 | failures=1 |
| `test_history_entries_are_validated_with_indexed_paths` | material：历史路径下标恒 0 | failures=1 |
| `test_evidence_capable_is_wider_than_structurable` | material：证据查询改按可结构化过滤 | failures=1 |
| `test_verify_bytes_resolves_relative_paths_under_root_only` | material：root 下只拼文件名 | failures=1 |
| `test_integrity_report_covers_remote_references_as_false` | material：完整性报告跳过远程引用 | failures=1 |
| `test_summary_has_exactly_the_documented_keys`（台账） | material：`unclear_rights` 改名 | failures=1 |
| `test_file_errors_are_ledger_errors` | material：YAML 错误不带文件路径 | failures=1 |
| `test_item_paths_are_prefixed_with_the_file_path` | material：前缀用文件名 | failures=1 |
| `test_byte_mismatch_is_reported_with_exit_zero` | main：字节不符时 JSON 模式退出 1 | failures=1 |
| `test_json_has_exactly_the_documented_keys` | main：每行多输出 `source_tier` | failures=1 |
| `test_subject_filter_applies_after_full_validation` | main：只按首个科目过滤 | failures=1 |
| `test_invalid_ledger_exits_two_with_a_prefixed_message` | main：前缀改 `contract violation:` | failures=1 |
| `test_usage_error_exits_two` | main：`parse_known_args` 忽略未知参数 | failures=1 |
| `test_registry_mode_defaults_and_subject_override` | main：注册表模式忽略 `--subjects` | failures=1 |
| `test_missing_registered_ledger_exits_two` | main：只捕获 `LedgerError` | errors=1 |
| `test_the_command_writes_nothing` | main：运行时写一个报告文件 | failures=1 |
| `test_remote_references_are_never_indexed` | citations：远程引用按 url 进索引 | failures=1 |
| `test_leading_dot_slash_and_separators_normalise` | citations：不去掉开头 `./` | failures=1 |
| `test_matching_is_case_sensitive` | citations：规范化后转小写 | errors=1 |
| `test_a_shared_path_fails_before_any_citation_is_checked` | citations：冲突报错路径改为 resource_id | failures=1 |
| `test_only_the_first_failing_rule_is_reported` | citations：撤回规则后去掉 `continue` | errors=1 |
| `test_a_clear_but_prohibitive_status_fails_on_structuring` | citations：规则 3 改用 `permits_evidence()` | failures=1 |
| `test_digest_is_compared_exactly_against_the_lowercase_ledger_digest` | citations：引用摘要先转小写 | errors=1 |
| `test_source_tier_does_not_gate_a_citation` | citations：弱档视同撤回 | failures=2 |
| `test_subject_review_status_and_display_are_not_checked` | citations：规则 4 加 `may_display` | failures=1 |
| `test_a_missing_file_is_a_problem_not_an_exception` | material：`verify_bytes` 去掉 `is_file` 检查 | errors=1 |
| `test_non_strict_ignores_root` | citations：给了 root 就核字节 | failures=1 |
| `test_counts_order_and_indices` | citations：只计每点首条引用 | failures=1 |
| `test_problem_path_is_the_raw_citation_path` | citations：问题里记规范化路径 | failures=1 |
| `test_raise_for_problems_names_every_problem` | citations：消息只列第一条 | failures=1 |
| `test_summary_has_exactly_the_documented_keys`（门禁） | citations：`source_index` 改名 | failures=1 |
| `test_mapping_points_are_validated_and_errors_propagate` | citations：跳过无来源的映射点 | failures=1 |
| `test_check_ledger_citations_loads_with_registry_subjects` | citations：`load_ledger` 写死科目集合 | failures=1 |

## 6. 测试输出

命令（任务书点名，未跑其他模块）：

```
py -3.12 -m unittest tests.contract.test_ledger_port tests.contract.test_citation_gate_port tests.test_ledger tests.test_citation_gate
----------------------------------------------------------------------
Ran 97 tests in 0.526s

OK
```

全量：未跑（按 `AGENTS.md`，由决策者提交前统一跑）。
怀疑受影响的其他模块：无（未改实现）。`tests/test_ledger_cli.py` 与本轮 CLI 测试相邻但未改，
建议决策者把它并入 M2 验收命令（见下）。

自检：两个测试文件无超过 100 字符的行；四个新文件 `rg '\?\?\?'` 无命中。

## 7. `docs/模块地图.md` M2 / M3 行的替换文本

（可替换性保留 B：M2 的 CLI 仍在 `ky/__main__.py` 内，M3 依赖 M2 / M4 的 Python 类型；是否升为 A 由决策者定。）

```
| M2 资料台账 | 校验资料身份、来源追溯、权利（rights）与可信度（source_tier）两轴及本地字节完整性；只读报告 | `contracts/ledger.md` | `ky/ledger/material.py`、`ky.__main__.ledger_main`、`data/materials.yaml` | 注册表科目 ∪ `{general}`、`reference.ledger`；`ky ledger --workspace` | B | `py -3.12 -m unittest tests.contract.test_ledger_port tests.test_ledger tests.test_ledger_cli`；`py -3.12 -m ky ledger --workspace <registry> [--ledger <path>] --json`（看 `bytes_verified`） |
| M3 引用门禁 | 知识点只引用台账中本地持有、未撤回、权利清楚且允许结构化、摘要一致的资料（不看可信度档） | `contracts/citation_gate.md` | `ky/ledger/citations.py` | —（`check_ledger_citations` 经 M2 发现注册表科目） | B | `py -3.12 -m unittest tests.contract.test_citation_gate_port tests.test_citation_gate` |
```
