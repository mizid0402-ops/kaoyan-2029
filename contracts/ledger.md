# 资料台账端口（M2）

模块：M2（见 `docs/模块地图.md`）；实现：`ky/ledger/material.py`（库，经 `ky.ledger` 公开）与
`ky/__main__.py` 的 `ledger_main`（CLI `ky ledger`）；契约测试：`tests/contract/test_ledger_port.py`
（另有 `tests/test_ledger.py`、`tests/test_ledger_cli.py`）。

台账是资料身份与法律地位的**唯一**登记处：一份资料一行，记录它是什么、从哪来、能不能用、
该不该信、本地字节是否完好。下游（M3 引用门禁、M5 真题索引校验等）只能引用台账里登记的资料，
不得自行发明来源。本端口只读：库函数和 CLI 都不写台账，也不写任何其他文件。

本规格以当前代码为准；与旧文档不一致处见 `review/rounds/round-152-ws2-specs-opus.md`。

## 1. 对外接口

| 接口 | 说明 |
|---|---|
| `load_ledger(path, *, subject_ids=None) -> tuple[Material, ...]` | 读 UTF-8 YAML 文件并按 §2–§7 校验 |
| `validate_ledger(raw, *, source="<ledger>", subject_ids=None)` | 校验已解析的整份台账 |
| `validate_material(raw, *, source="<material>", subject_ids=None) -> Material` | 校验一条资料 |
| `structurable_materials(ms)`、`evidence_capable_materials(ms)` | 按 §8 过滤，保持台账顺序 |
| `integrity_report(ms, *, root=None) -> tuple[(resource_id, bool), ...]` | 逐条 `verify_bytes(root)` |
| `ledger_summary(ms) -> dict` | §8.2 的机器可读概览 |
| `sha256_bytes(data)`、`sha256_file(path)` | 小写十六进制 SHA-256 |
| `LedgerError(message, path)` | 契约错误；`.path` 为字段路径（§9） |
| `Material`、`Rights`、`Storage`、`Provenance`、`HistoryEvent` | 不可变数据类 |
| 常量 `VALID_*`、`FORBIDDEN_RIGHTS_STATUS`、`SYLLABUS_AUTHORITATIVE_TIERS`、`LEDGER_SUBJECT_CATEGORIES`、`MATERIAL_SCHEMA_VERSION` | 本规格列出的枚举，集合内容与本规格逐项相等 |

## 2. 文档形状

台账文档二选一：

- 顶层是资料列表；
- 顶层是含 `items` 键的映射，只允许 `schema_version` 与 `items` 两个键，其他键拒绝
  （路径 `<source>.<键>`）。`schema_version` 缺省为 `1`，必须是整数 `1`（布尔值不算整数）。

不含 `items` 的映射、标量或空文档（YAML `null`）都按"不是资料列表"拒绝，路径 `<source>.items`。
`items` 可以为空列表。`resource_id` 在整份台账内唯一，重复者在第二次出现处报错
（`<source>.items[i].resource_id`）。YAML 任一层映射中显式写出的重复键以 `LedgerError` 拒绝，
不会静默保留后写的值；合法的 `<<` 合并键及显式覆盖继承字段按 YAML 原语义展开（WP-R3）。

## 3. 资料条目字段

未知键在每一层都拒绝（`_MATERIAL_KEYS` 等），路径精确到键名。

| 字段 | 必填 | 规则 |
|---|---|---|
| `schema_version` | 否 | 缺省 `1`；必须是整数 `1` |
| `resource_id` | 是 | 非空字符串；台账内唯一（本端口不限定字符集） |
| `title` | 是 | 非空字符串 |
| `material_kind` | 是 | `official_syllabus`、`outline_structure`、`official_exam_notice`、`textbook`、`past_exam_paper`、`reference_notes`、`ai_generated` |
| `subjects` | 是 | 非空列表；每项是允许科目之一（§3.1）；不得重复（路径 `…subjects`） |
| `acquisition` | 是 | `public_download`、`user_provided`、`licensed`、`purchased`、`generated`、`unknown` |
| `rights` | 是 | §4.1 |
| `storage` | 是 | §5 |
| `provenance` | 否 | 映射，缺省 `{}`；§4.2、§6 |
| `review_index` | 否 | 布尔，缺省 `false` |
| `review_status` | 否 | `unreviewed`（缺省）、`verified`、`withdrawn`；§7 |
| `notes` | 否 | 非空字符串或整数（整数转为字符串） |
| `history` | 否 | 列表，缺省空；§7 |

"非空字符串"指去掉首尾空白后非空；原值保留，不做裁剪。

### 3.1 允许的科目

允许集合只有一个来源：

- 调用方显式给 `subject_ids` 时，**它就是完整的允许集合**，库不再自动并入 `general`；
  需要台账自有分类的调用方自行并入 `LEDGER_SUBJECT_CATEGORIES`（= `{general}`，CLI 就这样做）。
- 未给 `subject_ids` 时，库调用 `ky.workspace.load_workspace()`（按工作区端口 §3.1 发现注册表：
  `KY_WORKSPACE`，再从当前目录向上查找），允许集合 = 注册表科目 ∪ `{general}`。
  发现或加载注册表失败时抛 `ContractError`（不是 `LedgerError`），原样传给调用方。

`load_ledger` / `validate_ledger` 只确定一次允许集合，再传给每一条资料。

## 4. 两条独立的轴

`rights` 回答"**能不能用**"（法律与许可），`provenance.source_tier` 回答"**该不该信**"
（手里这份字节的可信度）。两者互不推导：权利完全放开的资料可以是不可信的转载，
官方来源的资料也可以不允许结构化。任何判定只读自己那一条轴。

### 4.1 `rights`

键：`status`、`licence`、`licence_url`、`may_store`、`may_display`、`may_redistribute`、
`may_be_structured`。四个 `may_*` 必填且必须是布尔值（字符串、整数都拒绝）。`licence`
为 `null`、非空字符串或整数；`licence_url` 为 `null` 或非空字符串。

`status` 取值：`public_domain`、`official_public`、`licensed`、`personal_use`、`unknown`、
`restricted`、`state_secret_exam_period`、`officially_published`、`scoring_rubric_restricted`。

- `is_clear()` ⇔ `status != "unknown"`。`restricted` 与两个禁止状态都是"清楚的"——
  清楚但禁止。
- `permits_evidence()` ⇔ `is_clear() and may_be_structured`。

矛盾校验按下列顺序执行，第一条命中即报错（路径相对 `<资料>.rights`）：

| # | 条件 | 路径 |
|---|---|---|
| 1 | `status` ∈ `FORBIDDEN_RIGHTS_STATUS`（`state_secret_exam_period`、`scoring_rubric_restricted`）且任一 `may_*` 为真 | `.status` |
| 2 | `status == unknown` 且 `may_display` 或 `may_redistribute` | `.status` |
| 3 | `status == restricted` 且 `may_display` 或 `may_redistribute` | `.status` |
| 4 | `may_redistribute` 而非 `may_display` | `.may_redistribute` |
| 5 | `may_display` 而非 `may_store` | `.may_display` |
| 6 | `storage.mode == remote_reference` 且 `may_store` | `.may_store` |
| 7 | `may_be_structured` 而非 `may_store` | `.may_be_structured` |

`unknown` 状态**可以**写 `may_store: true` 与 `may_be_structured: true` 而通过校验，
但因 `is_clear()` 为假，它永远不能结构化、不能授权引用（fail-closed）。

### 4.2 `provenance.source_tier`

五档，从强到弱：`official`、`official_publisher`、`university`、`trusted_reprint`、
`community_archive`。**缺省为最弱档 `community_archive`**：没写可信度不等于可信。

只有前三档（`SYLLABUS_AUTHORITATIVE_TIERS`）可以决定考纲包含什么：
`Provenance.may_define_syllabus()` ⇔ `source_tier ∈ {official, official_publisher, university}`。
较弱的档只能提供线索、交叉核对和题面文本。

`source_tier` 不参与 §8 的任何门：`may_be_structured()`、`can_back_evidence()`、
`verify_bytes()`、M3 引用门禁都不看它。需要"能否定义考纲"的调用方自己调用
`may_define_syllabus()`。

## 5. 存储与哈希

`storage` 键：`mode`、`path`、`sha256`、`byte_size`、`url`、`retrieved_on`。`mode` ∈
`local_file`、`remote_reference`。`retrieved_on` 可选，为 ISO 日期（YAML 日期或
`YYYY-MM-DD` 字符串；YAML 时间戳取其日期部分）。

- `local_file`：`path` 非空字符串（相对路径按调用方给的根解析，见 §8.1）；`sha256` 是 64 位
  十六进制，大小写均可，**载入后统一为小写**；`byte_size` 为非负整数；`url` 可选。
  `storage.sha256` 是**本地那份文件的字节哈希**，不是远端响应或出版物的哈希。
- `remote_reference`：`url` 必填；`path`、`sha256`、`byte_size` 必须缺省或为 `null`，
  否则分别在 `.storage.path`、`.storage.sha256`、`.storage.byte_size` 报错。
  远程引用不持有字节，因此**不得携带哈希**：需要哈希就下载后按 `local_file` 登记。

`storage` 先于 `rights` 校验（§4.1 第 6 条依赖 `mode`）。

## 6. 来源追溯要求

`provenance` 键：`source_url`、`source_tier`、`publisher`、`published_on`、`isbn`、
`retrieved_at`、`retrieved_by`、`archive_url`。`source_url`、`archive_url` 为 `null` 或非空字符串；
`publisher`、`isbn`、`retrieved_by` 为 `null`、非空字符串或整数（整数转为字符串，照顾 YAML 里
不加引号的 ISBN）；`published_on` 为可选 ISO 日期；`retrieved_at` 为可选 ISO-8601 时间戳。

除 `acquisition: generated` 外，`source_url`、`publisher`、`isbn` **至少有一项**非空，
否则在 `<资料>.provenance` 报错——无法追溯的资料以后也无法撤回。整块 `provenance` 缺省时
同样适用此规则。

## 7. 审核状态与历史

`review_status`：

- `withdrawn`：资料仍可登记、仍出现在台账里，但 `may_be_structured()` 与
  `can_back_evidence()` 均为假。
- `verified` 与 `unreviewed`：对 §8 的门**没有区别**。`verified` 不表示权利已核实，
  权利只看 `rights`。

`history` 每项键：`at`（可选 ISO-8601 时间戳）、`action`（必填，∈ `registered`、
`rights_changed`、`path_changed`、`verified`、`withdrawn`、`superseded`）、`actor`（必填
非空字符串）、`detail`（可选，非空字符串或整数）。路径 `<资料>.history[i].<键>`。
本端口只校验并保存历史；**当前视图不由历史推导**，`review_status` 等字段以条目本身为准。

## 8. 派生判定与查询

| 判定 | 定义 |
|---|---|
| `Storage.has_verifiable_bytes()` | `mode == local_file` 且有 `sha256` |
| `Material.can_back_evidence()` | 未撤回 且 `has_verifiable_bytes()` |
| `Material.may_be_structured()` | 未撤回 且 `rights.permits_evidence()` 且 `has_verifiable_bytes()` |

`can_back_evidence` 不看权利：本地持有但 `may_be_structured: false` 的资料可以作 `path + sha256`
证据，却不能授权派生结论。`structurable_materials` ⊆ `evidence_capable_materials`。

### 8.1 字节完整性

`Material.verify_bytes(root=None) -> bool` 从不因文件缺失而抛错：

- 非 `local_file` → `False`（远程引用不是"未核实"而是"无法核实"）；
- `storage.path` 为相对路径且给了 `root` → 在 `root` 下解析；未给 `root` → 相对当前工作目录；
  绝对路径忽略 `root`；
- 目标不是普通文件 → `False`；否则比较 `sha256_file` 与登记的小写摘要。

`integrity_report(ms, root=root)` 对每条资料（含远程引用）给出 `(resource_id, verify_bytes(root))`，
保持台账顺序。

### 8.2 概览

`ledger_summary(ms)` 恰好含下列键：`total`（条数）、`by_kind`、`by_rights_status`、
`by_review_status`（计数映射，按键排序）、`structurable`、`evidence_capable`、
`unclear_rights`（`resource_id` 列表，保持台账顺序；`unclear_rights` 即 `status == unknown`）。

## 9. 错误

所有格式与语义错误抛 `LedgerError`（`ValueError` 子类），第一条错误即停止。`.path` 是字段路径，
属于规格；消息文字不属于规格。路径前缀：`load_ledger` 用文件的 POSIX 路径，`validate_ledger` 用
`source`（缺省 `<ledger>`），条目为 `<前缀>.items[i]`；`validate_material` 直接用 `source`。

| 情况 | 行为 |
|---|---|
| 台账文件不存在或不是文件 | `LedgerError`，`.path` 为空 |
| YAML 语法错误 | `LedgerError`，`.path` 为文件 POSIX 路径 |
| 注册表发现 / 加载失败（未给 `subject_ids`） | `ContractError`（§3.1） |
| 文件读取失败或不是合法 UTF-8 | `LedgerError("cannot read YAML: ...")`，`.path` 为文件 POSIX 路径（WP-R3） |
| 任一层映射出现重复键 | `LedgerError("duplicate field '<键>' (line N); ...")`，`.path` 为文件 POSIX 路径（WP-R3） |

## 10. CLI：`ky ledger`

`py -3.12 -m ky ledger [--ledger P] [--workspace R] [--root D] [--subjects a,b] [--subject s] [--json]`

只读：不写台账、不写任何文件。

### 10.1 数据来源（与 `contracts/workspace.md` §2.3、§3.2 一致）

| 模式 | 触发条件 | 台账 | 字节根 | 允许科目 |
|---|---|---|---|---|
| 独立 | `--ledger`、`--root`、`--subjects` 都给且无 `--workspace` | `--ledger` | `--root` | `--subjects` ∪ `{general}` |
| 旧式 | `--ledger`、`--root` 都给，无 `--subjects`、无 `--workspace` | `--ledger` | `--root` | 注册表科目 ∪ `{general}`；注册表先从当前目录发现，找不到再从台账所在目录发现；都找不到则违约，提示补 `--subjects` 或 `--workspace` |
| 注册表 | 其余情况 | `--ledger`，否则 `require("reference.ledger")` | `--root`，否则 `Workspace.root` | `--subjects`（给出时**取代**注册表科目），否则注册表科目；再 ∪ `{general}` |

`--subjects` 按逗号拆分，去空白，丢弃空项。

### 10.2 过滤与输出

整份台账先完整校验；随后 `--subject s` 只保留 `subjects` 含 `s` 的资料，概览与完整性都按过滤后
的集合计算。`s` 不在任何资料里时结果为空，仍退出 0。

`--json` 输出一个对象（键排序），顶层键恰好为 `ledger`（台账 POSIX 路径）、`root`（字节根
POSIX 路径）、`summary`（§8.2）、`materials`。`materials` 每项键恰好为：`resource_id`、`title`、
`material_kind`、`subjects`、`acquisition`、`rights_status`、`rights_clear`、`storage_mode`、
`review_status`、`bytes_verified`、`can_back_evidence`、`may_be_structured`、`source_url`、
`publisher`。不加 `--json` 时输出供人阅读的文本，行格式不属于规格。

### 10.3 退出码

| 码 | 含义 |
|---|---|
| 0 | 已报告。**字节缺失或哈希不符、权利不明都不改变退出码**，只体现在 `bytes_verified` / 文本 `MISMATCH or MISSING` |
| 2 | 台账无效或数据来源违约（`LedgerError` / `ContractError`）：stderr 以 `ledger violation: ` 开头，stdout 为空 |
| 2 | 参数用法错误（argparse 自身的退出码；本命令没有单独的 3） |

## 11. 已知限制（记录现状，不是规格承诺）

- （WP-R3 已修）非 UTF-8 台账与 YAML 重复键原先分别抛 traceback / 后者覆盖，现为
  `LedgerError`，`ky ledger` 退出 2。YAML 语法错误的解析器原文随 libyaml 措辞，前缀
  `invalid YAML: ` 不变。
- `resource_id` 不限定字符集；M5 真题索引另行要求 `^[a-z0-9][a-z0-9-]*$`。
