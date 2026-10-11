# 408 两棵知识树合并：schema 设计意见

## 结论

如果必须把两棵树物理合成一棵，在 A/B/C 三个方案中我选 **C**：显式区分“支持该节点的来源”和“提到、对应、提供定位或别名的来源”。

但我不建议把 C 实现成两份手工维护、容易漂移的数组。实际落地应采用 C 的语义、第四种做法的物理模型：维护一份带关系类型的来源事实表（或每节点的关系记录），再派生 `source_supports`、`source_count` 和 `weight` 等视图字段。

关键原则是：

- `sources` 不能同时承担“可复核定位”和“独立支持”的含义。
- `source_count` 应统计支持关系，而不是定位记录数。
- B 侧补充定位信息本身不改变 `source_count` 或 `weight`；只有经明确规则判定为独立支持时才可能改变它们。
- `weight` 必须有可复现的计算依据，不能仅凭 `len(sources)` 重算。

## 已确认事实、推断与未验证处

### 本轮直接核对到的事实

我读取了任务书、`data/structured_materials/cs408/knowledge_tree.yaml`、`data/structured_materials/cs408/knowledge_tree_weighted.yaml` 和 `tools/verify_tree.py`，没有读取对方产出，也没有修改项目文件。

- 基线树有 403 个节点；加权树有 410 个节点。逐 ID 比较显示基线 ID 集合是加权树的子集，加权树多 7 个节点。
- 基线节点的 `sources` 元素是包含 `path`、`sha256`、`locator` 的记录；加权树节点的 `sources` 值是 `A`/`B` 标签。
- 加权树当前的计数为：`weight=1.0/0.75/0.5` 分别 318/77/15，`source_count=2/1` 分别 380/30；这两个字段不是简单的同一计数的不同写法。
- 特别是：`structural_equivalent` 中存在两个来源但权重为 0.75 的节点；`candidate_recent_new` 中存在一个来源但权重为 0.75 的节点；`single_source_unverified` 和 `legacy_only_pending` 的单源节点权重为 0.5。这直接说明“源数量”不足以定义现有 `weight`。
- 当前 `verify_tree.py` 会逐条校验来源文件、哈希和 `quote_ref`，但不会判断一条引用是“支持”“提及”“别名”还是“结构对应”。因此它可以验证定位真实性，不能替代来源关系语义。
- 加权树的 B/C 文件记录仍指向 Temp 路径。文件在本轮检查时存在，但 Temp 路径不等于可长期复核的项目来源。

### 沿用任务书但本轮未重新实测的事实

源 C 的 799 道题 `knowledgePointIds` 全为 null，以及由此不能为树节点提供支持，是任务书给定的实测事实；本轮没有重新遍历该 JSON。因此 C 应作为已登记的相关数据源或独立验证材料，而不能因为出现在 `sources_registry` 就计入节点支持。

### 我的推断和设计判断

我推断当前 `weight` 实际上包含来源关系/匹配质量等策略信息（至少不能只由源数量决定），但任务书没有给出 `evidence_tag -> weight` 的完整公式。这个公式在 schema 决策前必须补齐；否则任何“重算”都只是猜测。

## 为什么选 C

C 能保留两个本来不同的事实：

1. 某来源在什么位置提到了、对应了或提供了别名；这是溯源和复核事实。
2. 某来源是否独立支持该节点；这是加权和复习调度事实。

例如，一个 2022 大纲条目可能只是宽泛上位标题、同义表述、结构对应或待确认候选。它应当留下定位记录，方便 Web 展示和人工复核，但不能自动成为独立支持。反过来，如果复核规则认定它确实独立支持，就应该显式登记为支持关系，而不是依靠“它恰好出现在 `sources` 里”来暗示。

建议的语义至少应能表达以下关系：

```yaml
sources:
  - source_id: A
    path: ...
    sha256: ...
    locator: {section: ..., offset: ..., quote_ref: ...}
    relation: supports
    support_kind: exact
  - source_id: B
    path: ...
    sha256: ...
    locator: {page: ..., quote_ref: ...}
    relation: mentions
    mention_kind: broad_heading
source_supports: [A]
source_count: 1
weight: 0.5
```

这段只是语义示例，不是要求现在照抄字段名。若保留 C 的两个字段，`source_supports` 最好引用来源记录的稳定 ID，而不是再复制一份完整的 path/hash/locator。否则两份记录会产生哈希、定位器或关系不一致。

另外，`source_count` 与 `weight` 应区分：前者是支持边的计数，后者是按正式策略计算的支持度分数。若权重继续保留为物化字段，至少要有 `weight_basis` 或策略版本；更稳妥的是由支持关系和匹配类型确定性派生。

## 对 A 的反驳

A 只有在一个很窄的前提下成立：新增的 B 记录确实只是定位补全，而且 schema 已经能指出这条记录不是支持证据。

问题在于 A 没有表达“这条记录只是提及/定位”的机器可读事实。将 `source_count != len(sources)` 作为验证器例外，只能掩盖字段含义冲突，不能回答每一条来源记录到底是什么关系。未来新增来源时，任何调用方都无法仅凭数据判断应不应计数，容易再次把全部 `sources` 当成支持源。

因此，例外本身不是绝对错误；正确的例外应建立在明确的关系字段或双字段契约上，并由验证器检查：所有定位记录可复核，只有 support 关系进入 `source_count`。A 当前的冻结方案缺少这个语义标记。

此外，A 把 `weight` 描述成“几个来源独立支持”也与现有数值分布不完全相容。若 0.75 还表达结构对应、时效性或匹配类型，A 必须先修正权重定义，不能把它继续当作源数量的直接编码。

## 对 B 的反驳

B 把“出现”误当成“独立支持”。这是最危险的语义跃迁：

- 同义别名、宽泛上位标题、结构对应和局部提及都可能出现，但不一定独立支持同一粒度的节点。
- 只有 B 侧出现的 `legacy_only_pending` 节点不能因存在定位就自动获得与双源精确对应相同的支持语义。
- 源 C 即使在注册表中存在，也不能因登记存在而成为节点来源；任务书给出的 null ID 实测恰好说明“数据源存在”和“节点支持”是两回事。
- B 会抬高仅 2022 出现节点的权重，并把跨年份的分歧、粒度差异和待复核状态压平；调度层会因此错误地减少或增加复习优先级，Web 层也会错误显示“多源支持”。

即使某条 B 记录最终被认定为支持，`weight` 也不能只按支持源数量重算，因为当前 `structural_equivalent` 等数据已经显示支持关系类型会影响权重。应先定义策略，再按策略计算。

## 第四种做法：一份关系事实表，派生多个视图

第四种做法是把来源关系建模为一等事实，而不是维护 `sources` 与 `source_supports` 两个平行事实集。例如：

```yaml
provenance:
  - source_id: A
    path: ...
    sha256: ...
    locator: {...}
    relation: supports       # supports / mentions / alias / equivalent / contradicts
    support_kind: exact      # 仅 relation=supports 时有意义
    mapping_basis: direct
  - source_id: B
    path: ...
    sha256: ...
    locator: {...}
    relation: equivalent
    support_kind: null
    mapping_basis: structural_match

# 以下均为派生值，或带有明确策略版本的物化缓存
source_supports: [A]
source_count: 1
weight: ...
```

在这个模型中，`provenance` 是唯一事实源；`source_supports` 是查询视图，`source_count` 是 `relation=supports` 的去重计数，`weight` 是策略函数的结果。这样既保留了 C 的语义边界，又避免两套列表漂移，并能为将来新来源记录 `contradicts`、`partial`、`alias` 等关系。

如果必须兼容现有字段，可以暂时保留 `sources` 作为兼容投影，但不应再让人工直接编辑它；生成器从关系事实表生成投影，并在校验时检查投影一致性。

## 是否可以根本不合并两棵树

可以，而且从审计角度看，这可能比“把所有内容塞进一棵树”更稳。

建议把加权树作为面向下游的 canonical view，把 403 节点单源基线作为不可变的原始基线，不把它的记录直接混入加权树的语义字段；另外维护一份项目内、可复核、带哈希锚定的 reconciliation/provenance ledger。对每个加权节点和 A/B（以及未来来源）记录：

- 对应的基线节点 ID（若有）及 7 个新增节点的明确状态；
- 来源文件 ID、项目内稳定路径、SHA-256 和 locator；
- `supports`、`mentions`、`alias`、`equivalent`、`contradicts`、`pending` 等关系；
- 匹配方法、粒度差异、冲突和待人工复核原因；
- 权重策略版本及其派生输入。

这样可以做到：加权树供复习调度和展示使用，ledger 供逐节点复核，基线树保留原始审计边界。未来新来源只需新增来源快照和关系边，不必改写基线。

但“不合并”不等于只保留当前加权 YAML 再写一张随意的对照表。若对照表没有稳定 ID、哈希、locator、关系枚举和完整覆盖，它只是说明文档，不能替代溯源。尤其要把 2022 PDF 和题库从 Temp 目录迁移或固化到项目可长期访问的位置，并重新记录哈希；否则将来 ledger 也无法复核。

如果现有下游只能读取单个树文件，可以由 canonical tree + ledger 生成一个兼容投影；关键是只保留一个事实源，避免两棵手工维护的树继续分叉。

## 对下游的影响

### 复习调度

调度器只能消费正式定义的 `weight`，不能把 `source_count` 或 `len(sources)` 当作替代品。B 仅补充定位时，节点优先级不应变化；B 被判定为独立支持时，是否变化取决于权重策略，并应产生可解释的变更原因。

对 `legacy_only_pending`、`candidate_recent_new`、`structural_equivalent` 等状态，建议同时暴露 `support_state`/`relation_summary` 或等价字段。低权重不应被解释成“内容错误”，因为树声明的权重反映来源支持度而非正确性；待复核节点也不应仅靠降权来隐藏。

### Web 来源展示

Web 应分别显示“支持来源”和“相关/提及来源”，并展示年份、匹配类型、locator 和复核状态。否则用户会把一个宽泛标题或别名看成第二个独立证据。源 C 在当前事实下应显示为题库/外部关联材料，而不是节点支持来源。

### 将来合并新来源

新来源接入时必须逐节点判定关系，而不是批量把来源 ID追加到 `sources`。需要稳定的 source ID、来源快照哈希、关系枚举、匹配方法和冲突记录；支持计数应按独立来源去重，权重按版本化策略派生。这样新增来源既能增加支持，也能只增加反例、别名或待复核信息而不误抬权重。

### 验证与数据契约

当前 `verify_tree.py` 的职责是契约、文件哈希、引用定位和结构检查，并不理解支持关系。后续若关系数据放入树内，应扩展正式 schema 使关系和派生字段可校验；若采用 sidecar，则应为 sidecar 建独立校验，并检查它与树节点 ID、来源注册表和哈希的一致性。不能通过放宽验证器、忽略字符串来源或静默接受计数不一致来“修复”问题。

还需注意：当前 `ky.knowledge.knowledge_point` 的严格契约只允许既定节点字段和记录型 `sources`，并对未知字段报错。`weight`、`source_count`、`evidence_tag`、`aliases` 以及加权树顶层注册信息若要进入同一份可验证树，需要正式 schema 版本/契约设计；这不是本轮为了让验证器通过而添加的例外，而是应在实施阶段明确的兼容性决策。采用 canonical tree + 独立 ledger 可以减少对现有知识点契约的侵入。

## 最终建议

1. 语义选择：选 C，不把“定位/提及”自动当成“独立支持”。
2. 数据实现：采用第四种关系事实表，派生 `source_supports`、`source_count` 和 `weight`，避免两个数组手工漂移。
3. 权重决策：先补齐 `evidence_tag`/关系类型到 `weight` 的正式公式；在公式缺失前，不接受 B 式按源数量重算，也不把现有 0.75/0.5 解释成简单源计数。
4. 架构决策：若下游允许，优先保留加权 canonical tree、不可变基线树和可复核 provenance/reconciliation ledger 三者分工；若必须单文件，则由关系事实表生成单树投影，而不是手工合并两份语义不同的 `sources`。
