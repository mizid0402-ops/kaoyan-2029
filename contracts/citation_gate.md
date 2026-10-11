# 引用门禁端口（M3）

模块：M3（见 `docs/模块地图.md`）；实现：`ky/ledger/citations.py`（经 `ky.ledger` 公开）；
契约测试：`tests/contract/test_citation_gate_port.py`（另有 `tests/test_citation_gate.py`）。
依赖：M2 资料台账（`contracts/ledger.md`）、M4 知识点（`contracts/knowledge_tree.md`）。

M2 单独校验一条资料，M4 单独校验一个知识点；两者各自正确时，知识点仍可能引用一个台账里
没有的路径，或引用一份权利不允许结构化的资料。引用门禁回答跨契约的问题：**这条引用所指的资料，
项目是否被允许据此派生结论，且字节是否仍与登记一致？** 本端口只读、纯函数（严格模式只读文件），
不写任何文件，也没有 CLI 子命令。

## 1. 对外接口

| 接口 | 说明 |
|---|---|
| `check_knowledge_point_citations(points, materials, *, root=None, strict=False) -> CitationReport` | 核对每个知识点的每条 `sources[]` |
| `check_ledger_citations(ledger_path, points, *, root=None, strict=False) -> CitationReport` | 先 `load_ledger(ledger_path)`，再同上 |
| `check_material_map(materials) -> dict[str, Material]` | 按规范化存储路径索引资料（§2） |
| `CitationReport`、`CitationProblem` | 不可变结果（§4） |

`points` 的元素可以是 `KnowledgePoint` 或映射；映射先经 `validate_knowledge_point` 校验，
失败时 `KnowledgePointError` 原样抛出（不折算成引用问题）。`materials` 是已校验的
`Material` 序列（通常来自 `load_ledger`）。

`check_ledger_citations` 调用 `load_ledger` 时不传 `subject_ids`，因此按 M2 §3.1 从
`KY_WORKSPACE` / 当前目录发现注册表；台账无效抛 `LedgerError`，注册表发现失败抛 `ContractError`。

## 2. 引用如何解析到资料

一条引用是知识点 `sources[i]` 的 `{path, sha256, locator}`。门禁只用 `path` 与 `sha256`；
`locator` 由 M4 校验，本端口不看。

- 只有 `storage.mode == local_file` 的资料进入索引；`remote_reference` 没有本地路径，
  **任何引用都不能解析到远程引用**。
- 规范化：把 `\` 换成 `/`，再去掉开头所有的 `.` 与 `/` 字符。因此 `./data/x`、`data\x`、
  `data/x` 解析到同一份资料。规范化后**按字符串精确比较**，大小写敏感。
- 两条 `resource_id` 不同的资料规范化后占用同一路径时，`check_material_map` 抛
  `LedgerError`（`.path` 为规范化后的路径）：引用必须解析到恰好一份资料，不静默择一。
  `check_knowledge_point_citations` 在核对任何引用之前先建索引，因此同样抛出。

## 3. 每条引用的规则

对每条引用按下列顺序检查，**只记录第一条不满足的规则**，然后继续下一条引用：

| # | 规则 | 问题原因中的固定短语 |
|---|---|---|
| 1 | 规范化路径能在索引中找到资料 | `no ledger entry stores this path` |
| 2 | 资料 `review_status != withdrawn` | `is withdrawn` |
| 3 | 资料 `rights.is_clear()`（`status != unknown`） | `an unclear right cannot authorise a claim` |
| 4 | 资料 `rights.may_be_structured` 为真 | `does not permit structuring` |
| 5 | 引用的 `sha256` 字符串**等于**台账摘要（台账载入时已统一为小写；引用摘要不做大小写规范化，大写摘要视为不符） | `does not match the ledger digest` |
| 6 | 仅 `strict=True`：`Material.verify_bytes(root)` 为真（文件存在且字节哈希等于登记摘要） | `no longer hash to the recorded digest` |

规则 1–5 合起来等价于 M2 的 `Material.may_be_structured()` 加摘要一致：能进索引的资料都是
`local_file`，必有摘要。原因文字给人读；上表的固定短语是当前区分规则的唯一途径（结果里没有
机器可读的规则编号，见限制 §6）。

**不属于门禁的事项**（有意为之，调用方需要时自行判断）：

- `provenance.source_tier` 不参与：`trusted_reprint`、`community_archive` 的资料只要权利允许，
  引用即通过。可信度由 M2 的 `may_define_syllabus()` 另行回答；M3 只管"能不能用"。
- `rights.status` 除 `unknown` 以外都视为"清楚"；禁止状态（如 `scoring_rubric_restricted`）
  在 M2 已被强制 `may_be_structured: false`，因此落在规则 4。
- 资料的 `subjects` 与知识点所属科目是否一致、`may_display` / `may_redistribute`、
  `review_index`、`review_status` 是 `verified` 还是 `unreviewed`，都不检查。

### 3.1 严格模式与字节根

`strict=False`（缺省）只比对记录，不读文件，`root` 被忽略；用于批量预检。
`strict=True` 重新读取并哈希被引文件；用于把知识点从 `extracted` 推进到 `reviewed` 的时刻。
严格模式下相对存储路径在 `root` 下解析，`root` 为 `None` 时相对当前工作目录；文件缺失或
字节变化都记为规则 6 的问题，不抛错。

## 4. 结果

`CitationProblem(knowledge_point_id, source_index, path, reason)`：`source_index` 是该引用在
知识点 `sources` 中的下标；`path` 是引用里写的**原始**路径（未规范化）。

`CitationReport`：

- `checked_points`：核对的知识点数；`checked_citations`：核对的引用总数（含有问题的）。
- `problems`：按知识点顺序、再按引用顺序排列；一次核对报告**全部**有问题的引用，不在第一处停下。
- `ok` ⇔ 没有问题。
- `raise_for_problems()`：`ok` 时什么都不做；否则抛一个 `LedgerError`，`.path == "sources"`，
  消息以 `unsupported citations: ` 开头，逐条列出 `<知识点>.sources[<i>] (<原始路径>): <原因>`，
  以 `; ` 分隔，包含每一个问题。
- `summary()`：恰好含 `checked_points`、`checked_citations`、`ok`、`problems`；`problems` 每项
  恰好含 `knowledge_point_id`、`source_index`、`path`、`reason`。

## 5. 错误

| 情况 | 行为 |
|---|---|
| 引用不被支持（§3） | 记入 `problems`，不抛错 |
| 两份资料占同一路径 | `LedgerError`（§2） |
| 映射形式的知识点不合 M4 | `KnowledgePointError` |
| `check_ledger_citations` 的台账无效 / 注册表不可发现 | `LedgerError` / `ContractError`（M2 §9） |

## 6. 已知限制（记录现状，不是规格承诺）

- 问题没有机器可读的规则编号，调用方只能按原因文字区分；`AGENTS.md` 已知缺陷第 3 条不鼓励这样做。
- 路径规范化去掉开头的所有 `.`，因此 `../x` 与 `.hidden/x` 分别被当作 `x` 与 `hidden/x`。
- 引用摘要大小写敏感（规则 5），而 M2 与 M4 都接受大写摘要输入。
- `check_ledger_citations` 无法传入 `subject_ids`，只能依赖注册表发现。
- `ky/ledger/citations.py` 的 `__all__` 漏列 `check_ledger_citations`（`ky.ledger` 包仍导出它）。
