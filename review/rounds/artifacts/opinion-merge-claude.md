# 意见：408 两棵知识树合并的 schema 设计（Claude 独立作答）

## 0. 先声明范围
本轮只出意见，**没有修改任何项目文件**。为了不"拍脑袋"，我读了 `ky/knowledge/knowledge_point.py`、
`tools/verify_tree.py`、两棵树的实际内容，并跑了几条只读检查（见 §5"实测 vs 推断"）。
其中一条实测结果**改变了我对整个问题框架的判断**，先说这个。

## 1. 一个任务书没提到、但我实测到的事实：现在的加权树，连"字段合法性"这一关都过不了

`ky/knowledge/knowledge_point.py` 里 `_POINT_KEYS`（第 60 行）和文档级允许键 `{"schema_version","items"}`
是**严格白名单**——任何不在名单里的字段会被 `_unknown()` 直接拒绝（"unknown field 'x'"），这是所有节点
（不管是 verify_tree.py 还是别的消费者）共用的同一份契约代码。

我直接跑了 `py -3.12 tools/verify_tree.py data/structured_materials/cs408/knowledge_tree_weighted.yaml`，
**在文档级就先炸了**：

```
CONTRACT FAILURE: ...knowledge_tree_weighted.yaml.baseline_relation_counts: unknown field 'baseline_relation_counts'
```

我又直接调用 `validate_knowledge_point()` 单独验第一个节点，**节点级也炸**：

```
NODE-LEVEL FAILURE: <knowledge_point>.aliases: unknown field 'aliases'
```

逐个数了一下，加权树每个节点上，`aliases` / `source_count` / `weight` / `evidence_tag` /
`baseline_relation` / `match_kind` **这六个字段没有一个在契约白名单里**；而且节点里根本没有
`source_kind`（契约的必填字段）；`sources: [A, B]` 这种裸字符串列表送进 `_sources()` 也会在
`_source()` 的 `_map()` 检查上炸（"expected a mapping, got str"）。

**这意味着什么**：任务书把待决问题框成"补上 sources 记录之后，source_count/weight 要不要跟着变，
需不需要给验证器开一个数值不一致的例外"——但这只是**冰山一角**。哪怕把 `sources` 从标签改成
记录列表，加权树上现存的另外 6 个字段依然会让 `verify_tree.py`（准确说是它调用的共享契约模块）
整体拒绝。也就是说，"给 verify_tree.py 加显式例外"这句话低估了改动范围：这不是在 verify_tree.py
里加一行 `if`，而是要么

- (i) **升级共享契约**（`KNOWLEDGE_SCHEMA_VERSION` 从 1→2，扩大 `_POINT_KEYS` 白名单，
  给 `_source_kind` 一个默认值或让加权树补上它）——但这份契约不只 verify_tree.py 在用，
  `transition_knowledge_point` / `eligible_for_frequency` / `apply_deterministic_frequency`
  等工作流函数全部导入同一个模块，动它的影响面覆盖到状态流转和频率统计，不是"给验证器开例外"
  这么局部；
- (ii) **不让这 6 个字段上树**，另存到一个不经过 `ky.knowledge.knowledge_point` 校验的旁路文件里
  （见 §3 第四种做法）。

这条是我这次读代码之后认为**最该先确认的一件事**：主控/另一位审阅者如果没跑过 `verify_tree.py`
针对当前加权树的实际报错，可能还在假设"只要把 sources 填对，验证器基本就能过、顶多一个 count
例外"——实测下来不是这样。

## 2. 选哪个方案

**我不选 A/B 的字面写法，选一个和 C 同构但落点不同的做法：语义上站 A，机制上不采用"允许
`source_count != len(sources)` 的数值例外"，而是彻底不让这类"支持度分析"字段和"逐节点可验证
provenance"字段挤在同一个节点对象里。** 具体见 §3。

如果一定要在任务书给的三个选项里选一个（假设契约扩展已经解决、字段合法性问题已经不存在），
我选 **C（拆字段），但要求两个字段都不是"随手加的两个 key"，而是有明确的生成规则**：

- `sources`：**谁提到过**（provenance，逐条可验证：path/sha256/locator/quote_ref），
  这是"这句话我在哪见过"，回答的是可追溯性问题；
- `source_supports`（或类似命名）：**谁独立支持**，`source_count = len(source_supports)`，
  `weight = f(source_count, match_kind)`——这是"我有多大把握这是个独立考点"，回答的是置信度问题。

理由：这两个问题**在语义上本来就不是一回事**，我实测过加权树里已经有区分这两者的真实案例
（见下），继续用一个字段表达两件事，早晚会有人把它们混用出错。

## 3. 反驳另外两个方案 + 我认为该拒绝 A 的"机制"（但不是它的"语义"）

### 反驳 B（重算）
任务书自己已经指出 B 的后果："会把'仅 2022 有'的节点权重抬高，抹掉分歧信息"，我认为这个判断是对的，
而且我**实测到一个比这更硬的反驳**：

我把加权树 410 个节点的 `weight` 按 `(source_count, evidence_tag)` 分组统计，发现 **weight 从来
不是 `source_count` 的纯函数**：

| evidence_tag | source_count | weight |
|---|---|---|
| `candidate_recent_new` | 1（仅 A） | **0.75** |
| `single_source_unverified` / `legacy_only_pending` | 1 | **0.5** |
| `dual_source_exact` | 2 | **1.0** |
| `structural_equivalent` | 2 | **0.75** |
| `text_layer_ocr_risk` | 2 | **1.0**（但带风险标记）|

也就是说 `weight = f(source_count, match_kind)`，是个二元函数，`match_kind`（`exact` /
`only_26` / `only_a` / `full_text_no_match` / …）本身就编码了"这条 2022 侧到底是不是真独立支持"。
B 方案说的"`weight` 按新源数重算"如果只用 `len(sources)` 当唯一输入，**连现有的加权逻辑本身都对不上**
——现在的 weight 从一开始就不是单纯数源头数量，B 会把这层已经存在的精细度判断直接抹平，不只是
"抬高仅 2022 有的节点"这一个后果，而是让 `weight` 整体退化成一个更粗的函数。**这是我自己重新统计
数据后得到的结论，不是转述任务书。**

### 反驳 A 的"机制"（不是反驳它的"语义"）
A 的语义我认可：`sources` 补上定位信息不等于"独立支持"，`legacy_only_pending` 那批节点就是最好的
反例——我抽查了几条，它们的 `sources: [B]`、`match_kind: only_a`（跟基线树的对应关系是
`new_vs_baseline`），确实是"2022 提到了，但只是宽泛的节标题级别的对应"，把这种情况计入
`source_count=2` 是错的。

但 A 提出的**机制**——"给 verify_tree.py 加显式例外，让 `source_count != len(sources)` 合法"——
我不建议，原因不是"开例外不对"，而是这个具体例外**在读者眼里和 bug 无法区分**：任何看到
"字段叫 sources，另一个字段叫 source_count，两者数值对不上，且验证器专门为此开了洞"的人，
第一反应是"这里是不是漏更新了"，而不是"这是有意为之的设计"。`verify_tree.py` 自己的 docstring
说它要能当"mutation-test oracle"用（把树弄坏，验证器必须变红）——一个**允许两个同名相关字段
不一致**的例外，恰恰是这类互变测试最容易漏掉、也最难在代码评审里一眼看出"这是故意的还是漏的"
的那种洞。**同样的语义用 C 的拆字段方式表达，不需要开任何例外，`len(sources)` 和
`len(source_supports)` 本来就是两个不同东西，没有"数值不一致"这回事，因为它们不叫同一个名字。**
所以我认为 A 的判断是对的，落地方式应该换成 C，而不是"以增加验证器例外为代价保留一个字段"。

### C 本身没写完的地方
C 在任务书里只回答了"叫什么名字、拆成几个字段"，**没有回答这两个新字段（连同 weight/
source_count/evidence_tag/aliases/baseline_relation/match_kind）到底要不要上升为
`ky.knowledge.knowledge_point` 契约认可的字段**。如果答案是"要"，就要走 §1 说的 (i) 契约升级路线，
影响面不小；如果答案是"不要"，那就自然滑向 §4 的第四种做法——不合并进同一个节点对象，
拆到旁路文件里。我认为后者更对，见下。

## 4. 第四种做法（我认为是更优解）

**不要把"支持度分析"字段（weight / source_count / evidence_tag / aliases / baseline_relation /
match_kind）写进知识点节点本身，也不要为了让它们合法而扩大 `ky.knowledge.knowledge_point` 的
契约白名单。** 让它们活在一个单独的、按 `knowledge_point_id` 关联的"共识附注"文件里
（比如 `knowledge_tree_agreement.yaml`），这个文件**不经过** `validate_knowledge_point()`，
有自己独立的、小得多的 schema。

节点树本身（即任务书计划里"合并后的那一棵"）**保持和现在的 `knowledge_tree.yaml` 完全同构**：
`sources` 就是记录列表（path/sha256/locator/quote_ref），A 侧沿用基线树的记录，B 侧对已确认
独立支持的节点补真实记录；7 个仅 2022 独有的节点（`legacy_only_pending`/`candidate_recent_new`）
如果确认要收进正式树，就作为普通节点、`sources` 只含 B 一条记录——**这本来就是契约已经支持的
形态**（`_sources` 只要求非空列表，不要求跨源），不需要动契约一个字符。

这样做的好处：
1. `verify_tree.py` **不需要改一行代码**、不需要任何例外，因为它验的对象（节点树）本来就没有
   引入任何新字段；
2. 契约模块（被状态流转、频率统计等共用）**不需要碰**，风险面从"整个共享契约"缩小到"一个新增的、
   没有历史包袱的旁路文件";
3. 我 grep 了一下 `ky/` 生产代码，**目前没有任何模块读取 `knowledge_tree_weighted.yaml` 或它的
   `weight`/`source_count`/`evidence_tag` 字段**（`ky/schedule/review_clip.py` 里的 `weight` 是
   学科级时间预算权重，`tools/apply_knowledge_weights.py` 里的 `weight` 是"题目→知识点"分布置信度，
   两个都是同名不同义的字段，跟 round24 加权树的节点级 weight 完全是三件事）。也就是说，
   任务书 Q4 提到的"下游会用到"目前都还是**计划中**、不是已有代码在消费旧结构——**现在换成
   旁路文件几乎零迁移成本**，反而是拖到真有下游代码写死"节点里直接读 weight"之后再拆分，
   成本才会变高。

## 5. 对下游的影响

- **复习调度按 weight 降权**：旁路文件方案下，调度器要多一次按 id 的 join（读节点树 + 读
  agreement 文件），成本很小；好处是调度器可以同时看到 `weight` 和 `evidence_tag`
  （比如 `text_layer_ocr_risk` 尽管 weight=1.0，但这是"两源都有，可是那份 2022 PDF 的文本层
  在这段可能有 OCR/抽取噪声"——如果调度器只认 weight，会漏掉这个信号）。**这一条是我的推断**：
  我没有看过复习调度器打算怎么消费这两个字段（`ky/schedule/` 下目前也确实没有读取加权树的代码），
  只是从数据本身的设计看，`weight` 和 `evidence_tag` 携带的是不同维度的不确定性，建议下游至少
  两个都读，不要只读 weight。
- **Web 展示来源**：只要 `sources` 是真实记录（这点两个方案都要做），Web 层就能展示"这句话在
  A/B 源的第几页/哪个偏移"；weight 放不放在同一个文件对 Web 层几乎没有区别，就是多读一个文件。
- **将来加源**：旁路文件方案下，加一个新源 D，只需要：① 给相关节点的 `sources` 追加真实记录
  （走契约、走 verify_tree.py，天然被验证）；② 在 agreement 文件里重新跑一遍
  "谁独立支持"的判断逻辑，产出新的 `source_supports`/`source_count`/`weight`。**这个判断逻辑
  本身应该是一段可读、可测的代码（因为我实测到 weight 不是 source_count 的纯函数，见 §3），
  而不是人工填的静态值**——不管选哪个 schema 方案，这一条都成立，只是旁路文件方案更容易把它
  写成一个独立、可单测的函数，不需要碰知识点契约。

## 6. 反过来：有没有可能根本不需要合并两棵树

**我认为不仅"可能"，而且应该这样做——但要把任务书里"加权树 + 溯源对照表"的主次关系反过来。**

任务书的表述是"只保留加权树，另写一份可复核的溯源对照表"，隐含加权树是主表。我建议反过来：

- **主表 = 单源基线树的结构**（每节点 sources 是可验证记录），**扩展**为把已确认独立支持的 B 侧
  记录也放进同一节点的 `sources` 列表里（此时它就是"合并后的树"，跟今天的
  `knowledge_tree.yaml` 同构，`verify_tree.py` 不用改）；
- **附表 = 共识/权重附注**，只记 `weight`/`source_count`/`evidence_tag`/`aliases`/
  `match_kind`/`baseline_relation`，按 id 关联，不作为"树"，不经过知识点契约校验。

这样"两棵树"变成"一棵可验证的树 + 一份可再生成的附注"，而不是"两棵结构不同、只有一棵能验证的树"。
`knowledge_tree_weighted.yaml` 这个名字本身其实是问题的一部分——它自称"树"，但从 `verify_tree.py`
的角度看它现在什么都不是（连契约都过不了），把它降格成"附注/报告"而不是"另一棵树"，
是我认为最贴近现状、成本最低的做法。

## 7. 我没有把握的地方

1. 我**没有**找到 `ky/schedule/` 或任何 Web 层代码里已经在读 `knowledge_tree_weighted.yaml`
   的地方（grep 只找到 round24 系列工具和测试引用它），所以"下游会用到 weight 降权"这件事
   目前是计划，不是既成事实——如果主控这边知道有我没搜到的消费代码，我的"零迁移成本"判断需要
   重新评估。
2. 我没有跑过 `ky.knowledge.knowledge_point` 的完整测试套件，所以"扩大 `_POINT_KEYS` 白名单/
   升级 schema_version 风险很大"是我读代码结构后的判断（它被工作流转移函数共用），不是我实测出
   "改了之后哪些测试会红"。
3. 我没有重新独立核对 27 条 alias 尾巴问题的判定（round-26 那轮的甲/乙判定），只读了那次的任务书
   作为"这类问题过去怎么处理"的参考，本轮结论不依赖它是否成立。
4. `weight = f(source_count, match_kind)` 这个二元函数关系是我从当前 410 个节点的数据里**反推**
   出来的（分组统计），不是看到了生成它的源代码逻辑本身（`tools/round24_build_weighted_tree.py`
   我没有完整读，只读了产出数据）——真实的计算规则可能比我反推的更细，如果它有我没覆盖到的
   分支，我这条反驳 B 的证据强度会打折扣。

## 8. 「实测」vs「推断」清单

**实测（我自己跑过/读过，可复核）**：
- `ky/knowledge/knowledge_point.py` 的 `_POINT_KEYS`/文档级白名单确实不包含
  `aliases`/`source_count`/`weight`/`evidence_tag`/`baseline_relation`/`match_kind`，
  且 `source_kind` 是必填字段。
- 直接跑 `verify_tree.py` 和直接调用 `validate_knowledge_point()`，两处都实际报错
  （"unknown field 'baseline_relation_counts'"、"unknown field 'aliases'"）。
- 加权树节点数 410、基线树节点数 403、`weight` 分布 `{1.0:318, 0.75:77, 0.5:15}`、
  `source_count` 分布 `{2:380, 1:30}`、`evidence_tag` 六类计数——都用脚本重新统计过，
  和任务书给的数字一致。
- `weight` 不是 `source_count` 的纯函数（用分组统计验证）。
- `sources_registry` 里 B/C 两个源确实指向
  `C:/Users/Lenovo/AppData/Local/Temp/kaoyan-probe/ghsurvey/downloads/...`，且这两个文件
  **现在仍然存在**于我这台机器的临时目录里。
- 直接打开 `408q_full.json`（1056638 字节）统计：17 个年份、共 799 题、
  `knowledgePointIds` 非空数 = **0**——独立复现了任务书"源 C 对树没有提供支持"的结论，
  不是转述文档自带的 `source_c_verification` 元数据。
- `ky/` 生产代码里 grep `weight`/`evidence_tag`/`source_count`/`knowledge_tree_weighted`，
  没有发现读取 round24 加权树的消费代码；`ky/schedule/review_clip.py` 和
  `tools/apply_knowledge_weights.py` 里的同名字段是另外两个不相关的概念。

**推断（未实测，基于任务书描述或代码结构做的判断）**：
- 复习调度器"计划"怎么消费 weight/evidence_tag——没有代码可读，纯推断。
- 扩大知识点契约白名单会牵连哪些具体测试——没跑测试套件，只是从"契约被多处工作流函数共用"
  这个结构事实做的风险判断。
- 2022 PDF 是否真的存在 OCR 抽取噪声（`text_layer_ocr_risk` 标签背后的具体原因）——
  我没有打开 PDF 逐页核对，只看到了打了这个标签的节点样例。
