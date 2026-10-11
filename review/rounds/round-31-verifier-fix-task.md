# 任务：修 `verify_tree.py` 的 cs408 树形模型（修复轮）

## 已完成的事实认定（主控亲自实测，可直接采信）

对 `data/structured_materials/cs408/knowledge_tree.yaml`（403 节点）与
`knowledge_tree_multisource.yaml`（410 节点）跑**去掉打印截断的验证器**，两棵树**各有 220 条失败**，
分三类：

| 类 | 条数 | 失败消息模板 | 根因归属 |
|---|---:|---|---|
| ① `section_ancestor` | **116** | `<section id>: section has no ancestor node '<id>.chapter'` | **验证器** |
| ② `chapter_missing_suffix` | **48** | `<chapter id>: missing <base>.content` / `.requirements` | **验证器** |
| ③ `subject_rank` | **56** | `<id>: scope subject must be narrower than subject` | **验证器** |

**三类全部归因于验证器，不是树的数据缺陷。理由如下（都已实测）：**

### ① 116 条：验证器假设章 id 带 `.chapter` 后缀

验证器源码（`tools/verify_tree.py` 第 147–151 行）：

```python
if point.scope == "section" and has_chapters:
    ancestor = ".".join(parts[:-1]) + ".chapter"
    if ancestor not in by_id:
        failures.append(f"{point.knowledge_point_id}: section has no ancestor node {ancestor!r}")
```

cs408 的章 id 是 `cs408.ds.chapter-01`（编号嵌在 id 内），**不带 `.chapter` 后缀**，但
**它确实是 section 的父前缀**（`cs408.ds.chapter-01.section-01` 以 `cs408.ds.chapter-01.` 开头）。
所以"祖先存在"这个事实是**可严格验证的**，只是拼接方式与 cs408 的命名不符。

### ② 48 条：验证器假设每个章都有 `.content` / `.requirements` 两个同级节点

同源码第 154–161 行，在 `has_chapters` 为真时，要求每个以 `.chapter` 结尾的 id 都有
`<base>.content` 与 `<base>.requirements`。

cs408 的章**没有**这两个占位节点，而是直接挂 2–6 个具名 section。
**这是 cs408 的真实建模，不是缺失**——把 math1 的"每章固定两块"结构强加给它才是错的。

**48 = 24 个章 × 2 个后缀**，与 cs408 章数一致。

### ③ 56 条：验证器把"同前缀同层级"当成违规

同源码第 163–174 行：

```python
if point.scope == "subject":
    prefix = point.knowledge_point_id.rsplit(".", 1)[0] + "."
    children = [p for p in points if p.knowledge_point_id.startswith(prefix) and p is not point]
    if not children:
        failures.append(f"{point.knowledge_point_id}: subject node has no descendants")
    for child in children:
        if SCOPE_RANK[child.scope] <= SCOPE_RANK["subject"]:
            failures.append(f"{child.knowledge_point_id}: scope {child.scope} must be narrower than subject")
```

**实测构成：4 科 × 14 = 56。每科 14 条的来历：**

| 来源 | 条数 |
|---|---:|
| `cs408.<d>.subject` 自身被当成自己的"后代"（它确实以 `cs408.<d>.` 为前缀） | 1 |
| `exam-objectives` 及其 3 个 item：共 4 个节点，彼此同层级，两两比较 | 4 |
| 3 个 objective item 各自与另外 2 个同前缀 item 比较 | 6 |
| `exam-objectives` 与 3 个 item 比较 | 4 |
| 小计 | **14** |

**关键：`scope: subject` 是刻意的设计，不是数据错误。** `ky/knowledge/knowledge_point.py` 源码写明：

- 408 考纲的**考查目标按设计就是 subject scope**（第 33–37 行注释）；
- `NON_EXAMINABLE_SCOPES = frozenset({"subject"})`（第 51 行），
  用于把考查目标**排除在频率统计与能力指标之外**；
- `eligible_for_frequency()`（第 332–340 行）与 `eligible_for_exam_metrics()`（第 343–346 行）
  **依赖这个 scope 判定**。

**所以不能改树的 scope**——改了会破坏"考查目标不进频率统计"这条真实约束。

**且两棵树都没有重复 id**（实测：403/403 distinct、410/410 distinct），
所以③不是重复数据问题。

## 你要做的

**只改验证器的树形模型，不改树的数据。**

### 1. 明确区分三种已经存在的树形，并各自严格校验

验证器第 134–139 行有注释说"两种树形都合法…推断是哪一种，不要把一种强加给另一种"，
但实现只覆盖了两种分支，**没覆盖 cs408 这种"以结构化 id 前缀表达父子关系"的树形**。

三种树形（都由完整 id 集合**可严格识别**，识别不明确时必须失败，不要容错猜测）：

| 树形 | 判据 | 祖先规则 | 章的二件套 |
|---|---|---|---|
| **cs408 式**（前缀即父子） | 存在 `scope=chapter` 且 id 形如 `<subject>.<domain>.chapter-NN`，其 section 为 `<id>.section-NN` | 章的**直接前缀**即为 section 的祖先（`chapter-NN` 本身，不拼 `.chapter`） | **不要求** `.content`/`.requirements` |
| **math1 式**（`.chapter` 后缀） | 存在以 `.chapter` 结尾的 chapter 节点 | 沿用现有 `＋".chapter"` 规则 | **要求** `.content`/`.requirements` |
| **eng1 式**（无 chapter 层） | 不存在 `scope=chapter` | 现有的 structure-tree 规则 | 不适用 |

### 2. 修 subject 规则

`scope: subject` 的语义是"**这一层级的节点**"，不是"必须是顶层单例"。所以：

- **排除节点自身**：比较时把 `p is not point` 换成**按 id 排除**（`p.knowledge_point_id != point.knowledge_point_id`），
  因为 `p is not point` 在同一个 id 被重复加载时挡不住
- **同层级共享前缀不算违规**：当 `child.scope == point.scope` 时，若 `child` 是**同层级兄弟**
  （即 `child.knowledge_point_id` 与 `point.knowledge_point_id` 的**父前缀相同**），
  不得报"必须更窄"
- **仍然必须报**的真违规：`child` 的 scope **比 subject 更宽**（当前 `SCOPE_RANK` 下不存在更宽的），
  或 `child` 位于 `point` 的**真子树**内（父前缀为 `point.knowledge_point_id`）而 scope 未更窄

**即：要保留这条检查的真实目的（"子树必须更窄"），同时不再把同层级共享前缀误判为子树。**

### 3. 不许为了通过而放宽

- **不要**简单地删掉这三类检查——它们各自在挡真实约束（math1 的二件套、子树必须更窄）
- **不要**改成"识别不出就跳过"——识别不明确时应**失败**
- **不要**动 `ky/knowledge/knowledge_point.py` 的白名单或 scope 常量

## 完成标准（缺一不可）

1. `py -3.12 tools/verify_tree.py data/structured_materials/cs408/knowledge_tree.yaml` → **全过**
2. 同上对 `knowledge_tree_multisource.yaml` → **全过**
3. 同上对 `data/structured_materials/math1/knowledge_tree.yaml` → **仍然全过**（`.chapter` 规则未被破坏）
4. 同上对 `data/structured_materials/eng1/knowledge_tree.yaml` → **仍然全过**（structure-tree 规则未被破坏）
5. `py -3.12 -m unittest discover -s tests -q` → **全绿**（先记录开工前基线）
6. **变异测试**（每条都要给出**变异前/后 SHA-256 证明已还原**）：
   - a. 在 cs408 树里删掉一个 section 的章前缀节点 → 必须变红
   - b. 在 math1 树里删掉某章的 `.content` → 必须变红
   - c. 在 cs408 树里给某 section 塞一个 `scope=subject` 的真子节点 → 必须变红
   - d. 把 cs408 树改成"既能识别成 cs408 式又能识别成 math1 式"的歧义形态 → **必须失败**（不明即拒）
7. **不得改动**：所有 `data/**` 下的文件内容（**树是数据，本轮不许动**）；
   `ky/knowledge/knowledge_point.py` 的白名单与 scope 常量

## 报告

写入 `F:\workspace\kaoyan-ai-system\review\rounds\round-31-verifier-fix-codex.md`：

1. 你如何区分三种树形（具体判据代码）
2. subject 规则改成什么，**为什么这没有削弱它原本要挡的东西**
3. 五条完成标准的**实际输出**（原始命令 + 结果）
4. 四条变异测试的**前后哈希与红/绿结果**
5. 开工前 vs 结束后的测试基线对比
6. 你改了哪些文件、每个文件的**前后 SHA-256**
7. 「我实测到了」vs「我推断」
8. 没有把握的地方至少 3 条

## 纪律

- 可改：`tools/verify_tree.py`、`tests/**`、`review/rounds/`（只写你自己的报告）
- **禁止**改：`data/**`（含所有树文件）、`ky/knowledge/knowledge_point.py` 的常量与白名单、
  `data/materials.yaml`、`data/exam_questions/**`、`data/review_weights/**`、
  `data/english_vocabulary/**`
- **禁止为了让验证通过而削弱检查**——如果发现某个检查无法在保留其意图的前提下修好，
  **停下来在报告里说明**，不要自行删掉
- 不要执行 git
- 本机**没有 `rg`**，用 Glob/Grep 或 `Get-ChildItem -Recurse`
- 必须用 `py -3.12`
- 终端吞中文：结果写 UTF-8 文件再用 read 工具读
- **不要抄录考纲正文**，报告里只出现 id、字段名、计数

最后用一句话回复：改了哪些文件 + 四棵树 verify 结果 + unittest 结果 + 四条变异测试红绿 + 报告路径。
