# Codex 独立共同评审意见

评审范围：完整复核 `review/rounds/round-30-common-review-brief.md`，读取其引用的当前文件，并用 `py -3.12` 实际运行指定验证器。除本报告外没有主动修改项目文件。

## 1. 对共同底本的复核结果

### 1.1 已复现的事实

- 文件清单、大小和节点规模均可复现：`knowledge_tree.yaml` 为 403 节点，`knowledge_tree_weighted.yaml`、`knowledge_tree_multisource.yaml`、sidecar 均为 410 条，Opus 文件为 358 条；11 个题目 JSON 共 432 条，`knowledge_point_id` 无空值。
- `knowledge_tree.yaml` 的所有 `sources` 都是项目内 A 源；`knowledge_tree_multisource.yaml` 的 `sources` 是真实 `{path, sha256, locator}` 记录，当前验证器确认 2 个源、哈希和 `quote_ref` 均通过。
- 以下四条命令均按底本要求实际运行：

  ```text
  knowledge_tree.yaml: contract OK; sources/hashes/quote_ref OK; exit 1
  knowledge_tree_multisource.yaml: contract OK; sources/hashes/quote_ref OK; exit 1
  knowledge_tree_agreement.yaml: CONTRACT FAILURE: baseline_relation_counts unknown field
  knowledge_tree_weighted.yaml: CONTRACT FAILURE: baseline_relation_counts unknown field
  ```

- sidecar 当前确实含有文档级 `baseline_relation_counts`；`tools/round29_validate_agreement.py` 实际返回 `VALID: 410 agreement entries, 0 errors`。当前字段值与 items 派生计数相等：`kept=403`、`new_vs_baseline=7`，但该校验器目前没有校验这个文档级字段。
- round-29 的独立派生函数确实存在于 `tools/tree_source_support.py`。我没有运行会写出 YAML 的 builder，而是独立读取 410 条旧 weighted 记录，用独立条件表按 `(evidence_tag, match_kind, scope)` 重算，再同时调用 `derive_source_support()` 对 410 条逐条比对：

  ```text
  weighted_items                         410
  weighted_combinations                  16
  literal_formula_mismatches              0
  derive_unknown                         0
  derive_mismatches                      0
  sidecar_vs_weighted_mismatches         0
  ```

  因此“round-29 已抽出函数并重现全部 410 个旧值”这条，在当前文件状态下得到独立复现。它证明的是数值映射的可复现性，不证明 round-24 的匹配分类本身正确。
- 三处同名 `weight` 的语义确实不同：`ky/schedule/review_clip.py` 是学科时间预算权重；`tools/apply_knowledge_weights.py` 是题目到知识点的分布置信度；round-24/29 节点字段是来源支持度。改名为 `source_support` 的方向合理。
- 对 `ky/` 以及排除测试、评审、数据后的代码做了字面引用检索，没有发现生产代码直接读取这几份 408 树文件或这些附加字段。`ky` 中确有通用 YAML/知识点加载器，因此“没有这些树文件的直接生产消费”可以确认；“不存在任何动态方式消费它们”不能仅凭检索证明。

### 1.2 底本不完整或我认为错误的地方

1. **“两棵树因 section has no ancestor 而失败”只说对了一部分。** 两棵树确实都退出码 1，且当前验证器首先显示 section ancestor 错误；但按验证器源码完整复算，CS408 基线和主表各有 220 个结构失败：

   ```text
   section ancestor       116
   chapter content/requirements 48
   subject rank            56
   total                  220
   ```

   所以不是只有 `.chapter` 这一类失败。验证器只打印前 20 个失败，容易造成底本和历史报告所说的“只有一类问题”的误读。

2. **“因为 verify_tree.py 的 mtime 更早，所以该规则不是 round-24/29 引入的”不是已证实事实。** 当前 mtime 确实是 `2026-09-13 10:33:42`，round-24/29 文件时间更晚；但 mtime 不能证明代码规则的历史来源或因果归属，且仓库没有 `.git`。最多只能说“当前文件的最后修改时间更早”，不能据此排除复制、回写或其他历史过程。

3. **“主控尚未独立复验 410 个值”是底本记录的历史状态，不再是本次评审的未决项。** 本次已经用独立重算和函数逐条比较得到 0 个不匹配；但这不等于已审查证据分类逻辑。

4. **sidecar 的 `VALID` 不能被解释成完整文档契约已通过。** 它的自有校验器检查了 item 白名单、主表 1:1 ID、`source_count` 和 `source_support`，但没有限制文档级键，也没有校验 `baseline_relation_counts`。因此它当前只是“条目级检查通过”。

5. **底本关于“规则为什么写成 `.chapter`”没有事实答案。** 现有 math1 树确实使用 `math1.hs.ch01.chapter` 这种命名，而 CS408 使用 `cs408.ds.chapter-01`；因此“验证器可能把 math1 的命名假设套到了 CS408”是合理推断，不是历史事实。

## 2. 对方向 A–E 的表态

### A：树形命名统一——保留 CS408 现有 ID，修正验证器的结构模型

推荐保留 `cs408.<domain>.chapter-NN` 及其 `.section-NN`、`.item-NN` ID，不改名为 `.chapter` 后缀。

理由：现有 432 条题目映射和 `topic_weights.json` 已使用这些 ID；改名会产生大范围同步风险，却不能增加证据质量。CS408 的 section 的直接前缀就是现有 chapter ID，这是一个可严格验证的关系，不是需要放宽的例外。

但不能只把 `.chapter` 拼接逻辑删除就宣布完成。验证器应明确区分已存在的树形配置：

- CS408：chapter 是 section 的直接前缀；`exam-objectives` 分支是非考试内容的 subject-scope 目标分支，不应用“同一 subject 下所有节点必须严格变窄”的错误规则。
- math1：继续验证现有 `.chapter` 后缀及每章的 `.content`/`.requirements` 结构。
- eng1：继续使用无 chapter tier 的 structure-tree 规则。

这不是“允许任意两种 ID”，而是把三种已经存在、可由完整 ID 集合严格识别的树形模型分别校验；识别不明确时应失败。

### B：sidecar——独立契约，不交给 `verify_tree.py`

推荐 sidecar 永远不作为知识点树传给 `verify_tree.py`。`verify_tree.py` 的输入契约是节点列表，sidecar 是按 ID 关联的注释文档；让它通过树契约会混淆职责。

推荐删除 `baseline_relation_counts` 这个可由 items 重新计算的重复摘要，保留并明确校验：`schema_version`、`generated_at`、`generator`、`concept_name`、`concept_note`、`source_registry`、`items`。items 保留：

```text
knowledge_point_id
source_support
source_count
evidence_tag
match_kind
baseline_relation
aliases
review_note  # 仅新节点可选
```

如果审计确实需要摘要，也只能保留在 sidecar，并由 sidecar 校验器逐条从 items 重算；不能把它塞进主表，也不能要求 `verify_tree.py` 接受 sidecar 文档格式。就“最小稳定终态”而言，我推荐删除它，避免重复状态。

### C：文件去留——一个活动主表、一个活动 sidecar、一个冻结基线

推荐：

- 保留并作为活动主表：`knowledge_tree_multisource.yaml`。
- 保留 `knowledge_tree_agreement.yaml` 作为活动 sidecar。
- 保留 `knowledge_tree.yaml`，但明确标记为冻结的 A-only baseline，仅用于差异、来源和迁移审计，不作为 410 节点活动主表。
- 将 `knowledge_tree_weighted.yaml` 移到 `archive/round-24/`，作为旧格式历史证据，不再作为输入或验收目标。
- 将 `knowledge_tree_opus.yaml` 和 round-6 临时脚本移到带轮次标记的 archive；不删除，避免丢失比对依据。

“退休”推荐采用可追溯归档而不是删除。归档后活动代码和文档必须只指向主表、sidecar、冻结基线和项目内源文件。

### D：验证器与契约边界——修正结构检查，不扩白名单

不建议把 `source_support`、`evidence_tag`、`match_kind`、`aliases` 等字段加入 `_POINT_KEYS`。该白名单被状态流转和频率工作流共用，扩展它会改变共享契约，且这些字段并不是知识点生命周期字段。

不建议让 `verify_tree.py` 兼容 sidecar 的文档级 mapping。应改的是验证器的结构分派和 CS408 的实际祖先关系；契约校验、哈希校验、引用定位、来源卫生检查继续保持严格。

关于 `.chapter` 的历史来源：仓库无 git，无法确认。math1 的现状支持“规则可能来自 math1 命名模型”的推断，但不能写成已证实的历史结论。

### E：一次性收敛——推荐一次有边界的收敛任务

推荐一次性完成“验证器结构模型 + sidecar 独立 schema + 活动/归档边界 + 针对性验收”，不要继续按错误输出逐条打补丁。代价是需要一次性明确 CS408 objective 分支的结构语义，并增加 profile-specific 测试；收益是不会再把一个 profile 的规则误套到另一个 profile。

## 3. 推荐的最小稳定终态

### 活动文件

1. `data/structured_materials/cs408/knowledge_tree_multisource.yaml`：唯一活动 408 树。每个节点只使用知识点契约字段；`sources` 为真实记录，包含项目内相对 `path`、磁盘字节 `sha256`、`locator.quote_ref`。不出现 `weight`、`source_support`、`evidence_tag`、`match_kind`、`baseline_relation`、`aliases`。
2. `data/structured_materials/cs408/knowledge_tree_agreement.yaml`：唯一活动来源一致性 sidecar。字段如上，不使用节点级 `weight`；来源支持度统一叫 `source_support`。
3. `data/structured_materials/cs408/knowledge_tree.yaml`：冻结 A-only baseline，只用于 403/410 差异和审计。
4. 项目内 B/C 原件和可定位副本：`408_syllabus_2022.pdf`、`408_syllabus_2022.extracted.txt`、`408q_full.json`，其哈希由相应来源校验覆盖。

### 校验责任

- `ky.knowledge.knowledge_point`：只负责节点契约和生命周期字段。
- `tools/verify_tree.py`：只负责活动主表的契约、源文件存在性、SHA-256、`quote_ref`、ID 唯一性、三类树形结构和来源卫生；修正后基线和主表都应完整退出码 0。
- 独立 sidecar validator：负责 sidecar 文档/条目 schema、未知字段拒绝、主表与 sidecar 的 ID 双向一致、`source_count == len(main.sources)`、`source_support` 派生值、`source_registry` 的文件哈希；不调用 `verify_tree.py` 解析 sidecar。
- 一项窄范围的 cross-artifact check：负责冻结 baseline 是主表子集、差异恰为 7 个 ID、sidecar 与主表均为 410 条。该检查不应通过把历史 weighted 文件重新纳入活动输入实现。

## 4. 实施步骤、顺序和完成标准

### 第一步：冻结当前证据

记录当前活动文件、源文件、410 个 ID、403/410 集合关系、sidecar 逐 ID 支持度和 SHA-256；不生成新 YAML。

完成标准：有可复核的 manifest；后续任何重建都能证明输入和输出差异。

### 第二步：先修验证器的树形 profile

仅改结构判断，不放宽节点契约和来源检查。为 CS408、math1、eng1 各写最小回归样例；重点覆盖 CS408 的 116 个 section ancestor、48 个错误的 chapter suffix 假设和 56 个 objective subject-rank 假失败。

完成标准：当前基线和主表的 contract、hashes、quote_ref、structure 全部通过；故意破坏 chapter/section 前缀、来源哈希或 quote_ref 时分别变红；sidecar 仍然被明确拒绝为非树输入。

### 第三步：收紧 sidecar 自有 schema

删除 `baseline_relation_counts`，或若业务坚持保留，则把它纳入文档级白名单并从 items 重算。推荐删除。明确拒绝未知文档级键和未知 item 键。

完成标准：sidecar validator 能独立通过当前 410 条；删除/新增 ID、修改 `source_count`、修改 `source_support`、添加未知字段都能变红。

### 第四步：确立活动/归档边界

把 weighted、Opus 和 round-6 临时产物移入带轮次的 archive，更新使用说明和构建入口；不删除，不改题目 JSON 和 `topic_weights.json`。

完成标准：生产入口只引用主表和 sidecar；冻结 baseline 仍可用于差异审计；活动目录没有两个竞争的 408 主表。

### 第五步：窄范围最终验收

顺序固定为：主表 `verify_tree.py` → 冻结 baseline `verify_tree.py` → sidecar validator → cross-artifact ID/计数检查 → 独立 410 条 `source_support` 重算。只在这些最小检查不足以覆盖风险时再扩大测试范围。

完成标准：以上全部退出码 0、主表 410 条、基线 403 条、差异恰为 7 条、sidecar 410 条、支持度逐 ID 无漂移；不得用“只看输出开头”作为验收。

## 5. 明确建议不做的事

- 不把 sidecar 文档强行改造成知识点列表，不让 `verify_tree.py` 接受它。
- 不向共享 `_POINT_KEYS` 添加来源一致性字段。
- 不为当前文件增加“忽略结构失败”或“两个字段任选其一”的验证器例外。
- 不重命名 CS408 的现有 chapter/section/item ID，不重写 432 条题目映射，不重算 `topic_weights.json`。
- 不按 `source_count` 重新计算 `source_support`；当前数据已证明两源节点也可能是 0.75，一源节点也可能是 0.75。
- 不把旧 weighted 文件继续当作活动事实源，不删除历史归档。
- 不在验证器结构模型未收敛前重新运行 builder 反复覆盖主表和 sidecar。
- 不以一次全量 unittest 绿色替代主表生产路径、源文件存在性和逐 ID 数据证据。

## 6. 没有把握的地方

1. `.chapter` 规则的真实历史来源无法确认：当前仓库无 git，mtime 只能作为时间信息，不能作为因果证明。
2. 本次独立重算验证了 `evidence_tag/match_kind` 到数值的映射，但没有重新审查 round-24 的跨源匹配分类是否应该如此；那是语义审计，不是公式复现。
3. `quote_ref` 验证证明文本可定位，不证明每个 OCR/别名文本的语义翻译完全正确；aliases 的内容质量仍需单独人工抽查。
4. 对生产消费的结论是“没有发现具体文件和字段的直接引用”；通用 YAML 加载器或外部运行时动态传路径的可能性，不能仅凭静态字面检索完全排除。
5. B 源采用项目内抽取文本作为可定位副本、PDF 作为原件的长期 provenance 约定已能通过当前验证器，但是否符合项目未来统一的 PDF 证据政策，当前材料不足以最终确认。

## 7. 「我实测到了」vs「我推断」

### 我实测到了

- 四次指定 `verify_tree.py` 命令的当前完整结果和退出码。
- 基线/主表各 220 个结构失败的独立计数：116 + 48 + 56。
- sidecar 确实含 `baseline_relation_counts`，且当前 `round29_validate_agreement.py` 返回 410 条、0 错误；该 validator 未检查文档级摘要。
- 独立规则表、`derive_source_support()`、旧 weighted `weight`、新 sidecar `source_support` 的 410 条逐 ID 比较均为 0 mismatch。
- 当前主表是基线的严格超集，差异为 7 个 `legacy-item` ID；sidecar、主表、weighted 各为 410 条。
- 直接字面检索未发现 `ky/` 生产代码读取这些 408 树文件或附加字段。
- 当前三处 `weight` 的代码位置和语义确实不同。

### 我推断的

- `.chapter` 规则很可能来自对 math1 命名模式的错误泛化；没有 git 证据，不能当作历史事实。
- CS408 objective 分支应按非考试目标元数据处理，而不是套用内容章节的严格 scope-rank 规则；这一判断依据 `knowledge_point.py` 对 408 考查目标的注释和当前 ID/scope 组合。
- sidecar 删除派生摘要是最小稳定选择；若未来审计需求强制保留，则必须由独立 validator 校验，不能靠 `verify_tree.py`。

**最终推荐**：保留现有 CS408 ID 和数据映射；把 `knowledge_tree_multisource.yaml` 定为唯一活动主表，把 `knowledge_tree_agreement.yaml` 定为独立 sidecar，修正 `verify_tree.py` 的树形 profile 而不是放宽它，删除或独立校验 sidecar 的重复摘要，并将旧 weighted/Opus/round-6 产物归档。
