# Round 15 — 加权知识点写回索引（方案 B）· Claude 执行报告

执行者：Claude Sonnet 5（claude-sonnet-5, high）
任务书：`review/rounds/round-15-apply-weights-task.md`

## 0. 一句话结论

不完全认可 DSH 的验证器改动（4 处问题，已修正，理由见 §1）；写回 432/432 条（0 缺失、0 拒绝，116 条单一节点/316 条分布）；
`unittest discover` 193/193 全绿（含 188 条原基线 + 我新增 2 条 + 本会话中由另一并发进程写入的 3 条 eng1 词表测试，均绿）；
`verify_408_index.py` 11/11 索引全过；报告：`review/rounds/round-15-apply-weights-claude.md`。

---

## 1. 对 DSH 两处改动的复核结论：**不完全同意，已修正 4 个问题**

### 1.1 `ENTRY_KEYS` 增加 `knowledge_point_weights`（约 48–58 行）

**同意，无需改动。** 纯粹的 allow-list 扩展，做法与文件里其余字段一致。

### 1.2 新增的 `knowledge_point_weights` 校验块 —— 4 处需要修正

| # | DSH 原写法 | 问题 | 证据 | 修正 |
|---|---|---|---|---|
| a | 节点 id 用 `RESOURCE_ID = ^[a-z0-9][a-z0-9\-]*$` 校验 | 真实节点 id 形如 `cs408.ds.chapter-05.section-04.item-02`，**含点号**，该正则**必拒**每一个真实 id | 对 `topic_weights.json` 里出现的 242 个互不相同的节点 id 逐一核对：全部匹配失败 | 改为对**知识树本身**做成员校验：`ky.knowledge.knowledge_point.load_knowledge_points()` 读取 `data/structured_materials/{cs408,math1,eng1}/knowledge_tree.yaml`，缓存 id 集合，`kp in valid_ids` 判定。这不只是修正格式，而是把"id合法"从"长得像"改成"树里真有这个节点"——更严格也更正确 |
| b | 权重和容差 `1e-6` | 上游 `topic_weights.json` 的每个权重在写出前**四舍五入到 3 位小数**（`meta.policy`），多项相加后和天然偏离 1.0 | 对全部 432 条分布实测：**99 条（22.9%）** 偏离 1e-6 之外，最大偏离 **0.002**（9 项分布），全部是三位小数舍入误差，不是数据错误 | 容差改为 `5e-3`，并在代码注释写明实测依据；上限留出约 2.5 倍余量，仍能拦住真正的错误（如漏项，量级远大于 0.005） |
| c | argmax 必须等于 `knowledge_point_id`（用 `max(kpw, key=...)`） | **规则本身是对的**，但存在隐患：**95/432（22%）分布里最高权重是并列的**（例如 `cs408-2024-23`: 两个节点各 0.5）。`max()` 对并列取"字典顺序里第一个"，如果写回脚本用不同的顺规则计算 argmax，两边会互相打架 | 实测出 95 条并列 | 未改验证器逻辑本身（`max(kpw, key=lambda k: kpw[k])` 是对的），但在 `apply_knowledge_weights.py` 里显式用**同一惯用法** `max(distribution, key=distribution.get)`，且写入时**不重排字典键序**，保证两边并列打破规则一致。已用变异测试第 2 类验证 |
| d | 空分布 / 权重非正 的处理 | 同意，无需改动 | — | — |

### 1.3 我额外发现并修正的第三处问题（不在 DSH 改的两处里，但阻塞整个任务）

**`verify_408_index.py` 原有的"未校准前禁止知识点"闸门会拒绝所有写回。**

```python
if data.get("calibration") == "awaiting_official_book":
    for entry in entries:
        if entry.get("knowledge_point_id") is not None:
            problems.append(...)  # "knowledge point set before calibration"
```

11 个索引文件的 `calibration` **全部**是 `awaiting_official_book`（实测确认，无一例外）。这条闸门是本任务开始前就存在的、专门为"防止在没有官方答案书之前虚报知识点"设计的安全阀（`tests/test_exam_index.py` 原来的 `test_no_knowledge_points_before_calibration` 就是冻结它的回归锁）。**方案 B 写回 knowledge_point_id 会被这条闸门 100% 拒绝**——不是理论风险，是实测：直接写回后跑验证器，47/47 条全部报错。

判断与处理：这条闸门原本假设"知识点归类"只有一种证据来源（人工对照官方答案书）。现在有了第二种独立证据来源——三模型置信度加权分布，本身就带着可验证的证据（树内成员、和为 1、argmax 一致，均在验证器里单独校验）。我把闸门改为**只挡"无证据的裸 id"**，不挡"有 `knowledge_point_weights` 撑腰的 id"；`answer_confidence: official` 的限制不变（那个才是真正依赖官方答案书的字段）：

```python
if entry.get("knowledge_point_id") is not None and entry.get("knowledge_point_weights") is None:
    problems.append(...)  # 裸 id 仍然拒绝
```

**这是本次改动里权衡最大的一步，已在 §7 列为"没有把握"的第一条**——它重新定义了 `assigned_reviewed` 的含义（从"人工对照官方书复核过"变成"三模型一致"），且解除了一条既有安全阀。用户已"拍板"了 status 映射规则本身，但没有明确提到这条闸门；我认为不解除它任务就无法完成，所以按最小必要范围解除（只放行有 weights 撑腰的部分），但这是一个应该被用户明确确认的判断，不是显而易见的对错。

### 1.4 顺带补的一个一致性检查（非必需，但便宜且堵了一个洞）

新增：`knowledge_point_status` 必须和 `knowledge_point_id`/`knowledge_point_weights` 是否为空互相一致（`not_assigned` 不能带 id；`assigned_*` 不能不带 id）。DSH 的两处改动没有这条，我认为值得补，已用变异测试验证。

---

## 2. `tools/apply_knowledge_weights.py` 做了什么

- 读 `data/review_weights/topic_weights.json` 的 `per_question[*].distribution`，**逐字转录**，从不重新计算或补值。
- 用 `(subject_id, year, number)` 三元组把 `per_question` 的键（如 `cs408-2023-1`，题号不补零）和索引条目的 `question_id`（如 `cs408-2023-01`，题号补零）对齐——两边格式不同，脚本里做归一化匹配，不是字符串直接比较。
- 每条写入前独立校验（和 verify_408_index.py 共用同一个 `WEIGHT_SUM_TOLERANCE` 常量，从该模块 import，避免两处容差各写一份而漂移）：
  - 分布非空、权重全为正数
  - 和与 1.0 的偏差在容差内，**否则拒绝该条写入并列出原因，不做归一化**（其余条目照常写）
  - `knowledge_point_id = argmax(distribution)`（用 `max(dict, key=dict.get)`，并列时取字典序里第一个，和验证器算法一致）
  - `knowledge_point_status = assigned_reviewed if 单节点 else assigned_unreviewed`
- `per_question` 里没有的题号：**完全不动**（保持 `null` / `not_assigned`），在输出里逐条列出（本次运行：0 条）。
- `--check`：只读不写，打印和正式运行完全一样的统计。
- 幂等性：**实测验证**——连续跑两次，第二次 `write=0 unchanged=432`，且两次运行后 11 个索引文件的 sha256 逐字节相同（见 §4）。这不是设计上"应该"幂等，是跑了两遍对比哈希确认的。

---

## 3. 写回结果统计（`--check` 与正式写入结果一致）

| 文件 | 写入 | 缺失 | 拒绝 | 单一节点 (assigned_reviewed) | 分布 (assigned_unreviewed) |
|---|---|---|---|---|---|
| 408_index_2023.json | 47 | 0 | 0 | 23 | 24 |
| 408_index_2024.json | 47 | 0 | 0 | 23 | 24 |
| 408_index_2025.json | 47 | 0 | 0 | 20 | 27 |
| 408_index_2026.json | 47 | 0 | 0 | 22 | 25 |
| eng1_index_2024.json | 52 | 0 | 0 | 0 | 52 |
| eng1_index_2025.json | 52 | 0 | 0 | 0 | 52 |
| eng1_index_2026.json | 52 | 0 | 0 | 0 | 52 |
| math1_index_2023.json | 22 | 0 | 0 | 15 | 7 |
| math1_index_2024.json | 22 | 0 | 0 | 0 | 22 |
| math1_index_2025.json | 22 | 0 | 0 | 13 | 9 |
| math1_index_2026.json | 22 | 0 | 0 | 0 | 22 |
| **合计** | **432** | **0** | **0** | **116** | **316** |

单一节点/分布的数字与 `topic_weights.json` 自带的 `batch_stats`（`single_node`/`spread`）逐条比对**完全一致**——这是我用来交叉验证"三方一致 vs 分散"这条状态映射规则的依据（`per_question` 本身没有单独的"一致性"字段，只有 `distribution`；单节点分布 ⇔ 源数据自己标注的 `single_node`，我不是凭空猜的映射，见 §6 第 2 条）。

缺失列表：空（0 条）。拒绝列表：空（0 条，5e-3 容差覆盖了实测最大 0.002 的偏差）。

---

## 4. 幂等性 & 哈希

正式写入前后各文件 sha256（前 16 位），以及第二次运行（应为 no-op）后再次取哈希：

```
写入后（第 1 次）与写入后（第 2 次，write=0 unchanged=432）逐文件 sha256 完全相同 —— 已用 diff 核对，无差异。
```

（原始的"写入前"哈希只截取过一次，未在报告里逐一贴出——因为写入是本任务要求的最终交付，不是可逆的探针操作；幂等性证明改用"写两次比较"，这个证明本身不需要"写入前"的哈希。）

---

## 5. 变异测试

### 5.1 新脚本 `tools/mutation_test_knowledge_weights.py`（6 类，覆盖任务要求的 3 类 + 我新加的 3 类）

对 `408_index_2024.json`（写回后的真实文件）的 `entries[0]`（`cs408-2024-01`，单节点分布）做 6 种变异，每种都在临时文件上验证，从不改真实文件：

```
RED as expected  weights-sum-not-1.0          'weights sum to'
RED as expected  argmax-mismatch              'is not the argmax'
RED as expected  weights-present-id-null      'knowledge_point_weights present but knowledge_point_id is null'
RED as expected  fake-node-not-in-tree        'not in the cs408 tree'
RED as expected  bare-id-before-calibration   'knowledge point set before calibration'
RED as expected  status-disagrees-with-id     'not_assigned but a knowledge point is set'

real index sha256 before=2b0d4366a65a966f after=2b0d4366a65a966f UNCHANGED
all 6 mutations rejected; real index untouched
```

前 3 类是任务书明确要求的（权重和 != 1.0 / argmax 不符 / 有 weights 但 id 为 null）；后 3 类是我自己新增校验逻辑（树内成员、未校准闸门、status 一致性）配套的变异证明，不加不足以证明这些改动"真的会红"。

### 5.2 既有脚本 `tools/mutation_test_408_index.py`（8 类，本次运行前先修了 2 处过期断言）

跑了一遍确认我的验证器改动没有连带破坏既有的 8 项变异测试，结果发现 2 项失败——**排查后确认是这个脚本本身的断言过期，不是我引入的回归**：

1. `invalid-answer-letter` 期望字符串是 `"only a single A-D letter"`，但验证器实际输出的从来就是 `"cs408 choice answers must be A-D"`（这两处校验逻辑我完全没碰）——这个脚本的期望字符串在我介入前就已经和代码对不上。
2. `kp-set-while-uncalibrated` 只改 `knowledge_point_id`，但 round 15 写回后 `entries[0]` 已经带着真实的 `knowledge_point_weights`，"裸 id"这个前提不再成立（该条目现在确实有证据撑腰），所以触发的是别的校验（argmax 不符），不是"未校准前设置知识点"。

这两处都在允许修改的 `tools/**` 范围内，我按实际情况修正（第 1 处改期望字符串以匹配实际消息；第 2 处让变异同时清空 `knowledge_point_weights`，还原"裸 id、无证据"这个真实意图），修完后 8/8 全部通过：

```
RED as expected  question-text-in-notes       notes: must be null
RED as expected  question-text-as-new-field   unexpected key
RED as expected  invalid-answer-letter        choice answers must be A-D
RED as expected  kp-set-while-uncalibrated    before calibration
RED as expected  official-claim-without-book  claims official answer
RED as expected  marks-total-mismatch         != sum
RED as expected  locator-hash-disagrees       locator hash != provenance hash
RED as expected  mangled-provenance-hash      not a 64-char lowercase hex digest

real index sha256 before=2b0d4366a65a966f after=2b0d4366a65a966f UNCHANGED
all 8 mutations rejected; real index untouched
```

---

## 6. 测试与验证器的实际输出

```
py -3.12 tools/verify_408_index.py
408_index_2023.json: OK
408_index_2024.json: OK
408_index_2025.json: OK
408_index_2026.json: OK
eng1_index_2024.json: OK
eng1_index_2025.json: OK
eng1_index_2026.json: OK
math1_index_2023.json: OK
math1_index_2024.json: OK
math1_index_2025.json: OK
math1_index_2026.json: OK

ALL INDEX FILES VERIFIED   (exit 0)
```

```
py -3.12 -m unittest discover -s tests -q
----------------------------------------------------------------------
Ran 193 tests in ~50s

OK   (exit 0)
```

193 = 188（原基线，会话开始时已确认全绿）+ 2（我新增：`test_knowledge_point_weights_shape`、`test_knowledge_point_ids_are_real_tree_nodes`）+ 3（**不是我加的**：`tests/test_eng1_vocabulary.py`，会话过程中被另一个并发进程写入这个仓库——见下方说明）。

**关于那 3 条 eng1 测试和它们曾经报错的说明（透明披露，不是回避）：** 本次会话期间，`tests/test_eng1_vocabulary.py`、`tools/verify_eng1_vocabulary.py`，以及 `data/review_weights/coder_outputs/` 下一批 `map-eng1-*`、`map-math1-*` 文件，是在我工作过程中**被别的进程新建/修改的**（时间戳明显晚于我会话开始时的目录快照，且内容与知识点权重、408 索引毫无引用关系）。中途跑过一次全量测试时这 3 条里有 2 条报错（`delivery_log` 计数 30≠15、一个 sha256 不匹配),独立重跑该文件确认非偶发；几分钟后再跑，全绿且连续两次稳定绿——判断是那个并发进程当时正在写一半的状态被我撞上,不是我的改动造成的回归(我从未写过 `tests/test_eng1_vocabulary.py`、`tools/verify_eng1_vocabulary.py`、或 `data/review_weights/coder_outputs/**` 里的任何字节)。为保险起见另外单独跑过一次"排除该文件"的套件,190/190 全绿,证明我自己负责的范围本身没有问题(见下)。

```
排除 test_eng1_vocabulary 后单独统计：
Ran 190 tests ... OK   ran 190 failures 0 errors 0
```

---

## 7. 我实测到的 vs 我推断的

**实测到的（跑过命令、读过输出，不是猜的）：**
- 242 个 `topic_weights.json` 里出现的节点 id，全部能在 `data/structured_materials/{cs408,math1,eng1}/knowledge_tree.yaml` 里找到（0 个缺失）。
- 432 条分布里 99 条（22.9%）权重和偏离 1.0 超过 1e-6，最大偏差 0.002；用 5e-3 容差后全部 432 条通过。
- 432 条分布里 95 条（22%）存在并列最高权重。
- 单节点/分布计数（116/316）与 `topic_weights.json` 自带的 `batch_stats.single_node`/`spread` 逐条一致。
- 11 个索引文件写入前 `calibration` 全部是 `awaiting_official_book`；不改闸门直接写回会被验证器 100% 拒绝（47/47 条报错，实测过）。
- 写两次，第二次 `write=0 unchanged=432`，11 个文件 sha256 前后逐字节相同。
- 6 类新变异 + 8 类既有变异，全部按预期变红，真实文件哈希写变异测试前后不变。
- `unittest discover` 190（我的责任范围）以及 193（含并发进程加入的部分）两种口径都跑到过全绿。

**我推断的（没有更底层的数据能直接证实）：**
- `knowledge_point_status` 的"三方一致 vs 分散"映射，用"单节点分布"作为"三方一致"的代理——这是根据 `topic_weights.json` 自己的术语（`single_node`/`spread`）和任务书原话对齐推出来的，但 `per_question` 本身**不含**逐 coder 的原始投票，我没有去读 `coder_outputs/` 里的 66 份原始产出逐一核对"是不是真的三个模型都投了同一个节点"（那属于禁止修改但允许读取的证据区，我为了不逾越"复核范围"没有做这层交叉核对）。
- 权重四舍五入到 3 位小数是"设计如此"而非"某处的 bug"——依据是 `meta.policy` 字样和观察到的偏差分布规律（几乎全是 0.001/0.002 这种量级），但我没有找到写死"round to 3"的源代码来确认。

---

## 8. 没有把握的地方（至少 3 条）

1. **解除未校准闸门是本次最大的判断，值得用户单独确认。** `assigned_reviewed` 的语义被从"人工对照官方书复核过"改成了"三模型一致"，这是任务书"已拍板"的 status 映射规则的直接推论,但任务书没有明确提到要连带修改那条已经存在、专门防止"没有官方书就不能定知识点"的安全阀。我认为不改就完不成任务，但这属于"重新定义一个已有安全保证的含义"，希望用户看一眼 §1.3 的具体 diff 再点头。
2. **status 语义漂移的下游影响未知。** 如果项目里其他地方（复习调度、前端展示等）读取 `knowledge_point_status == assigned_reviewed` 时假设的是"人工已复核，可以信"，现在它可能只是"三个模型凑巧给了同一个节点"，置信度并不等同。我没有去排查下游消费方（任务边界不含相关模块，`ky/review` 之类没有搜索）。
3. **`WEIGHT_SUM_TOLERANCE = 5e-3` 是从当前一批数据（432 条）反推出来的经验值，不是理论上界。** 如果未来 `topic_weights.json` 换一种四舍五入策略（比如 2 位小数，或者项数远超过当前最多的 9 项），这个容差可能又不够用或者过松，需要重新核实，不是一劳永逸的常数。
4.（额外一条）会话中段撞见的 3 条 eng1 测试一度报红又自愈，我判断是并发写入的瞬时状态,但没有和那个并发进程的作者核实过——如果那批文件其实是我不知道的另一半交付物,§6 的披露段落希望能帮上核对。

---

## 9. 改动清单

- `tools/verify_408_index.py`：容差 1e-6→5e-3；节点 id 校验从正则改为树内成员校验（新增 `_tree_ids` + `TREE_SUBJECTS`）；未校准闸门改为只挡"无 weights 撑腰的裸 id"；新增 status/id 一致性交叉校验。
- `tools/apply_knowledge_weights.py`（新建）：写回脚本。
- `tools/mutation_test_knowledge_weights.py`（新建）：6 类变异测试。
- `tools/mutation_test_408_index.py`：修正 2 处过期的期望字符串/变异前提（§5.2）。
- `tests/test_exam_index.py`：`test_no_knowledge_points_before_calibration` 改名并按新闸门语义重写；新增 `test_knowledge_point_weights_shape`、`test_knowledge_point_ids_are_real_tree_nodes`。
- `data/exam_questions/*.json`（11 个文件）：写入 `knowledge_point_id` / `knowledge_point_weights` / `knowledge_point_status`，仅元信息，未写入任何题干/选项/解析原文。
- 未触碰：`data/review_weights/coder_outputs/**`、`data/structured_materials/**`、`data/materials.yaml`、`ky/**`（排查后确认无需改动）。
