# 共同评审底本：408 知识树的现状、问题与待决方向

> 用途：**三方（Claude / Codex / 主控）共同评审的同一份事实底本**。
> 要求：评审者**先复核底本里的每条claim**（底本可能有错——这个项目里主控已经错过多次），
> 再给出**改进方向**。**目标是一个三方都能认可的、不再反复返工的方向。**
> 日期：2026-09-14 ｜ 工作目录：`F:\workspace\kaoyan-ai-system`

---

## 0. 为什么要做这次共同评审

过去若干轮采取"发现问题 → 立刻派人修"的零敲碎打方式，结果**反复返工**，而且：
- 主控自己**多次误判**（把工具 bug 当数据缺陷、用二手材料否定一手证据、只看输出开头就下结论）
- 修一处暴露出两处，**没有一次是"改完就稳定"**

**所以本轮不改代码。** 只做一件事：**三方对"该怎么改"形成一致方向。**
方向确定后，实现应由**单一任务**一次做完，而不是继续打补丁。

---

## 1. 现有的 408 相关文件（实测清单）

`data/structured_materials/cs408/` 下：

| 文件 | 大小 | 是什么 |
|---|---:|---|
| `knowledge_tree.yaml` | 301,389 B | **单源基线树**，403 节点，来源只有 A（2026 HTML）|
| `knowledge_tree_weighted.yaml` | 162,864 B | round-24 加权树，410 节点，`sources` 是标签 `["A","B"]` |
| `knowledge_tree_multisource.yaml` | 387,074 B | round-29 **主表**，410 节点，`sources` 是真记录列表 |
| `knowledge_tree_agreement.yaml` | 102,187 B | round-29 **附表（sidecar）**，410 行，含 `source_support` 等 |
| `knowledge_tree_opus.yaml` | 359,494 B | 早期 Opus 独立抽取版（358 节点，用于比对）|
| `audit_round6.py` / `generate_tree_round6.py` | — | round-6 的临时脚本 |

**加上 `data/exam_questions/*.json` 里的 11 份题目索引**（432 题，`knowledge_point_id` 全部已填），
以及 `data/review_weights/topic_weights.json`（题目→知识点权重分布）。

---

## 2. 实测的验证状态（主控亲自跑过，可复核）

```
$ py -3.12 tools/verify_tree.py data/structured_materials/cs408/knowledge_tree.yaml
  contract : OK (403 nodes) ... 但 FAILURES 段有若干条：
  - cs408.ds.chapter-01.section-01: section has no ancestor node 'cs408.ds.chapter-01.chapter'

$ py -3.12 tools/verify_tree.py data/structured_materials/cs408/knowledge_tree_multisource.yaml
  contract   : OK (410 nodes validated by ky.knowledge.knowledge_point)
  sources    : 2 distinct files, 2 hashed
  hashes     : OK (every sources[i].sha256 matches the bytes on disk)
  quote_ref  : OK (every quote_ref locates in its declared source)
  tree shape : catalog (subject/chapter/section)
  structure  : {'subject': 20, 'chapter': 24, 'section': 116, 'item': 250}
  FAILURES:
  - cs408.ds.chapter-01.section-01: section has no ancestor node 'cs408.ds.chapter-01.chapter'

$ py -3.12 tools/verify_tree.py data/structured_materials/cs408/knowledge_tree_agreement.yaml
  CONTRACT FAILURE: ....baseline_relation_counts: unknown field 'baseline_relation_counts'

$ py -3.12 tools/verify_tree.py data/structured_materials/cs408/knowledge_tree_weighted.yaml
  CONTRACT FAILURE: ....baseline_relation_counts: unknown field 'baseline_relation_counts'
```

**验证器代码（`tools/verify_tree.py` 146–158 行）的祖先规则**：

```python
# a section must have an ancestor chapter node, where the tree has chapters
ancestor = ".".join(parts[:-1]) + ".chapter"
if ancestor not in by_id:
    ... f"section has no ancestor node {ancestor!r}"
```

**即它假设章节点 id 形如 `cs408.ds.chapter-01.chapter`，而树里实际是 `cs408.ds.chapter-01`。**

---

## 3. round-29 拆分交付物的实际质量

**已确认通过的部分**：

| 项 | 结果 |
|---|---|
| 主表节点数 | 410（基线 403 + 7 个 2022 独有）|
| 主表契约 | `OK (410 nodes validated)` |
| 主表 hash / quote_ref | 两者 `OK` |
| **每节点 `sources` 已是真记录列表** | ✅ path + sha256 + locator + quote_ref |
| **sidecar 权重与拆分前逐一相等** | ✅ `{1.0:318, 0.75:77, 0.5:15}`，**逐 id 差异 = 0** |
| 源 B/C 移入项目 | ✅ `data/raw_materials/cs408/syllabus/`、`.../exam_banks/` |
| 2022 PDF 的文本抽取副本 | ✅ `408_syllabus_2022.extracted.txt`（供 `quote_ref` 定位用）|
| 字段改名 | ✅ `weight` → `source_support`（避免与另两处同名字段混淆）|

**两个未通过的部分**：

### 问题 1：主表因"祖先前缀"规则失败——**且基线树同样失败**

- 失败原因是**命名约定不一致**（验证器期望 `.chapter` 后缀，树里没有）
- **`tools/verify_tree.py` 的 mtime = 2026-09-13 10:33**，**早于 round-24 与 round-29**，
  所以**这条规则不是这两轮引入的**
- **因此 round-22 报告里"基线树 verify 全过"是错的**——当时只看了输出前 6 行，
  `FAILURES` 段在更下面。**主控的又一次误读。**

### 问题 2：sidecar 仍带着 `baseline_relation_counts`，触发契约报错

- sidecar 文档级键：`schema_version / generated_at / generator / concept_name / concept_note / source_registry / baseline_relation_counts / items`
- `baseline_relation_counts` 正是最初让加权树在文档级炸掉的字段
- **而"sidecar 不经过知识点契约"正是这个方案的全部理由**

---

## 4. 已确认的关键设计事实（三方都应据以判断）

### 4.1 `weight` 不是 `source_count` 的纯函数

```
source_support  source_count  节点数
     1.0             2        318
    0.75             2         62     ← 两源却 0.75
    0.75             1         15     ← 一源却 0.75
     0.5             1         15
```

按 `evidence_tag` 交叉：

| evidence_tag | weight | source_count | 节点数 |
|---|---:|---:|---:|
| `dual_source_exact` | 1.0 | 2 | 315 |
| `structural_equivalent` | 0.75 | 2 | 57 |
| `structural_equivalent` | 0.75 | 1 | 8 |
| `candidate_recent_new` | 0.75 | 1 | 7 |
| `text_layer_ocr_risk` | **1.0** | 2 | 3 |
| `text_layer_ocr_risk` | **0.75** | 2 | 5 |
| `legacy_only_pending` | 0.5 | 1 | 7 |
| `single_source_unverified` | 0.5 | 1 | 8 |

**即 `weight = f(source_count, match_kind/evidence_tag)`——编码的是"匹配质量"。**

### 4.2 项目里已有**三样东西都叫 `weight`**，指三个不同概念

| 位置 | 含义 |
|---|---|
| `ky/schedule/review_clip.py` | 学科级时间预算权重 |
| `tools/apply_knowledge_weights.py` | 题目→知识点分布的置信度 |
| round-24/29 的节点级 | 来源支持度（已改名为 `source_support`）|

### 4.3 契约是共享的，不是验证器私有的

`ky/knowledge/knowledge_point.py` 的白名单（`_POINT_KEYS`）被
`transition_knowledge_point` / `eligible_for_frequency` / `apply_deterministic_frequency`
等工作流函数**共用**。所以"扩白名单"的影响面覆盖**状态流转与频率统计**，不是局部改动。

### 4.4 目前**没有生产代码**在消费加权树

`ky/` 下 grep 不到读取 `knowledge_tree_weighted.yaml` 或 `knowledge_tree_multisource.yaml`
或其 `weight`/`source_support`/`evidence_tag` 字段的地方。**现在重构的迁移成本接近零；
等下游代码写死之后再动，成本才变高。**

### 4.5 `evidence_tag → weight` 的公式**只存在于构建脚本里**，无文档记录

（round-29 声称把它抽成了独立函数并重现了全部 410 个值——**主控尚未独立复验这一点**）

---

## 5. 待决方向（请三方各自表态）

### 方向 A：树形命名统一
`chapter` 节点 id 到底该是 `cs408.ds.chapter-01` 还是 `cs408.ds.chapter-01.chapter`？
- 改验证器（放宽/兼容两种）还是改树的 id？
- **`data/exam_questions/*.json` 里的 `knowledge_point_id` 已指向现有 id**，
  改 id 会牵动那 432 条映射与 `data/review_weights/topic_weights.json`

### 方向 B：sidecar 的归属与校验方式
- `baseline_relation_counts` 这类文档级摘要该不该留在 sidecar 里？
- sidecar 由**自己的校验器**管，还是也要求能过 `verify_tree.py`？
- sidecar 若永远不能被任何验证器验，能否接受？

### 方向 C：基线树的去留
现在有四份树文件（基线 / 加权 / 主表 / sidecar）+ 一份 opus 比对版。
- 该保留哪几份？哪几份应退休？
- "退休"是指删除，还是移到 `archive/` 并标注？

### 方向 D：验证器与契约的边界
- `verify_tree.py` 的祖先规则当初为什么写成 `.chapter` 后缀？**（需查 git/历史文档，本仓库无 git）**
- 契约白名单要不要为节点级来源支持度字段扩展？还是**永远不让这类字段上树**？

### 方向 E：一次性收敛 vs 继续打补丁
- 三方共同认可的**最小稳定终态**是什么？
- 达成它需要哪几步、顺序如何、每步的完成标准是什么？
- **哪些步骤可以明确"不做"**（范围裁剪比加班更重要）

---

## 6. 请评审者遵守的纪律

1. **先复核底本，再表态。** 底本可能有错——**如果你复现不出某条 claim，请直接说，不要接受。**
2. **不要为了让某份文件"通过验证"而建议放宽验证器**——本项目多次确认：与 bug 无法区分的例外
   比不通过更危险。
3. **区分「实测」与「推断」**，逐条标注。
4. **给出一个可执行的终态**，而不是一串"可以考虑"。若有多个方案，**明确推荐一个并说明代价**。
5. **明确指出你认为底本里错的地方**——这是本轮最有价值的输入。
6. **不要修改任何文件**，只出意见。

## 7. 输出

写入各自文件（两个评审者各一份，互不可见），主控随后汇总：

- Claude：`%TEMP%\kaoyan-probe\review-state-claude.md`
- Codex：`%TEMP%\kaoyan-probe\review-state-codex.md`

报告须含：
1. **对底本的复核结果**（哪几条你复现了、哪几条复现不出、哪几条你认为错）
2. **对方向 A–E 的逐项表态与理由**
3. **你推荐的最小稳定终态**（具体到"保留哪些文件、字段叫什么、由谁校验"）
4. **实施步骤与顺序**，以及每步的完成标准
5. **明确建议"不做"的事**
6. 没有把握的地方
7. 「我实测到了」vs「我推断」
