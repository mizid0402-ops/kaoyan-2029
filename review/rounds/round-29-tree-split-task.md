# 任务：408 加权树改造 —— 拆成「可验证的树 + 一致性附注」

## 背景（都已实测，可直接采信）

项目有两棵 408 知识树：

| | `knowledge_tree.yaml`（基线） | `knowledge_tree_weighted.yaml`（加权） |
|---|---|---|
| 节点 | 403 | 410（严格超集：403 共有 + 7 个 2022 独有）|
| 每节点 `sources` | **记录列表** `{path, sha256, locator}` | **标签列表** `["A","B"]` |
| 逐节点 path/sha256/locator | 403/403 | **0/410** |
| `weight` / `source_count` / `evidence_tag` / `aliases` | 无 | 有 |
| **能否被 `verify_tree.py` 验** | **能，全过** | **不能，文档级就炸** |

**实测报错**（主控亲自跑的）：

```
$ py -3.12 tools/verify_tree.py data/structured_materials/cs408/knowledge_tree_weighted.yaml
CONTRACT FAILURE: ....baseline_relation_counts: unknown field 'baseline_relation_counts'

$ py -3.12 tools/verify_tree.py data/structured_materials/cs408/knowledge_tree.yaml
contract : OK (403 nodes validated)
```

**根因不止是 `sources` 格式**：加权树有 **6 个节点级字段全在 `ky.knowledge.knowledge_point` 的白名单外**
（`aliases` / `source_count` / `weight` / `evidence_tag` / `baseline_relation` / `match_kind`），
且**缺契约必填的 `source_kind`**。而那份契约被 `ky/` 的**状态流转、频率统计等工作流函数共用**，
所以"改契约"或"给验证器开例外"的影响面都远超本次改动。

## 已定案的方向（用户已批准，两位独立顾问一致同意）

**不合并成一棵塞满字段的树，而是拆成两部分：**

| | 内容 | 是否经过知识点契约 |
|---|---|---|
| **主表**：可验证的树 | 节点结构 + 每节点 `sources`（真实记录：path/sha256/locator/quote_ref）| ✅ 经过，`verify_tree.py` 必须全过 |
| **附表**：一致性附注 | `weight` / `source_count` / `evidence_tag` / `aliases` / `match_kind` / `baseline_relation` | ❌ **不经过**，自带小 schema |

**两位独立顾问（Claude / Codex）都反对"给验证器开例外"**，理由一致：
**一个允许两个相关字段不一致的例外，和 bug 无法区分**，而 `verify_tree.py` 的职责恰恰是
"把树弄坏必须变红"（它的 docstring 自称 mutation-test oracle）。

**另一位顾问还实测到一条关键事实**：`weight` **不是 `source_count` 的纯函数**：

```
weight  source_count  节点数
  1.0        2        318
 0.75        2         62      ← 两源却 0.75
 0.75        1         15      ← 一源却 0.75
  0.5        1         15
```

**即 `weight = f(source_count, match_kind/evidence_tag)`，编码的是匹配质量。**
所以**不存在"按源数重算 weight"这回事**。

## 执行顺序（有依赖，不要打乱）

### 第 1 步：把源移进项目（**这是后面一切可复核的前提**）

当前 `sources_registry` 里三个源，两个指向**临时目录**：

```
A: data/raw_materials/cs408/syllabus/archive408_408_outline_2026.html    ← 项目内 ✅
B: C:/Users/.../Temp/kaoyan-probe/ghsurvey/downloads/408_syllabus_2022.pdf  ← 临时 ❌
C: C:/Users/.../Temp/kaoyan-probe/ghsurvey/downloads/408q_full.json         ← 临时 ❌
```

要做：

- 把 B 与 C 的**文件复制进项目**（建议 `data/raw_materials/cs408/syllabus/` 与
  `data/raw_materials/cs408/exam_banks/`，目录名你可调）
- **复制后重新现算 SHA-256**，确认与复制前一致
- 注册表路径改为**项目内相对路径**
- **不要删临时目录里的原件**（留着做交叉核对）

### 第 2 步：把 `evidence_tag → weight` 的公式固化下来

**现在这个映射只存在于构建脚本里，没有任何文档记录。** 没有它，任何"重算"或"校验"都无从谈起。

要做：

- 去读 `tools/round24_build_weighted_tree.py`（或它调用的抽取/合并脚本），
  **把 `evidence_tag`（及 `match_kind`、`source_count`）到 `weight` 的判定规则抽出来**
- 写成一份**独立、可读、可单测的函数**（建议 `ky/exam/tree_weight.py` 或 `tools/` 下独立模块）
- **在文档里明确写出这张表**：什么关系 → 什么权重，以及理由
- **用当前 410 个节点验证这个函数**：喂入现有的 `(evidence_tag, source_count, match_kind)`，
  **必须重现现有的全部 410 个 weight 值**。**有任何一条对不上，就说明规则没抽全，必须继续挖**
  （这是硬门槛：函数抽对了，才能说 weight 是"可复现"的）

### 第 3 步：拆分

**主表**（建议直接改造 `knowledge_tree_weighted.yaml`，或新建并退休旧的）：

- 与 `knowledge_tree.yaml` **完全同构**：节点字段就是契约白名单里的那些
- 每节点 `sources` 是**真实记录列表**：
  - A 侧记录从基线树继承
  - B 侧记录**对已确认为独立支持的节点**补上
  - **7 个 2022 独有的节点**（`legacy_only_pending` / `candidate_recent_new`）如果收进正式树，
    就作为普通节点、`sources` **只含 B 一条记录**——这本来就是契约支持的形态
- **必须保留 `source_kind`（契约必填）**

**附表**（建议 `knowledge_tree_agreement.yaml`）：

- 只装 `weight` / `source_count` / `evidence_tag` / `aliases` / `match_kind` / `baseline_relation`，
  按 `knowledge_point_id` 关联
- **不经过 `validate_knowledge_point()`**，自带一份**小得多的独立 schema**
- 附表的 `weight` **必须由第 2 步那个函数派生**，不是手工填的静态值
- 附表要能**再生成**（给同样的树 + 同样的来源，重复跑结果一致）

### 第 4 步：验证（**这几条是完成标准，缺一不可**）

1. `py -3.12 tools/verify_tree.py <主表>` **全过**（contract / hashes / quote_ref / structure）
2. **主表与基线树的节点集合关系**：应为超集（403 共有 + 7 独有），且差异清单可复现
3. **附表的 `weight` 与改造前逐一相等**（410 个值，一个都不能变）——否则说明拆分过程改坏了数据
4. 附表的独立校验脚本（schema、id 是否都能在主表里找到、weight 是否与派生函数一致）
5. **变异测试**：把某节点 weight 改掉、把附表里某个 id 改成主表没有的、把 `sources` 里某条 sha256
   改错 → 对应校验必须变红；给**还原哈希**
6. `py -3.12 -m unittest discover -s tests -q` **必须全绿**（先记录开工前基线，结束时对比）

## 命名冲突要顺手处理（顾问指出的真实问题）

项目里**已有三样东西都叫 `weight`，指三个不同概念**：

| 位置 | 含义 |
|---|---|
| `ky/schedule/review_clip.py` 的 `weight` | **学科级时间预算权重** |
| `tools/apply_knowledge_weights.py` 的 `weight` | **题目→知识点分布的置信度** |
| 本任务的节点级 `weight` | **来源支持度** |

**请给本任务这个起一个不冲突的名字**（如 `source_support` 或 `support_weight`），
并在文档里说明三个概念的区别。**这只是改名，不改语义。**

## 报告

写入 `F:\workspace\kaoyan-ai-system\review\rounds\round-29-tree-split-claude.md`：

1. 第 1 步：B/C 移入项目的路径、复制前后 SHA-256
2. 第 2 步：**`evidence_tag → weight` 的完整规则表**，以及"410 个值全部重现"的证明
3. 第 3 步：主表与附表的规模、字段清单、命名选择
4. 第 4 步：五项验证的实际输出
5. 三个同名 `weight` 的处理
6. 「我实测到了」vs「我推断」
7. 没有把握的地方至少 3 条

## 纪律

- 可改/新建：`data/structured_materials/cs408/**`、`data/raw_materials/cs408/**`、
  `tools/**`、`tests/**`、`ky/**`（**仅当你确实需要动契约时，且必须说明理由**）、`review/rounds/`
- **禁止**改：`data/materials.yaml`（登记由主控统一做）、`data/exam_questions/**`、
  `data/review_weights/**`、`data/english_vocabulary/**`、
  `data/structured_materials/{math1,eng1}/**`
- **禁止为了让验证器通过而放宽验证器**——如果必须开例外，先停下来在报告里说明，不要自己决定
- **不要动 `ky/knowledge/knowledge_point.py` 的白名单**，除非第 2 步证明非动不可（动了要单独说明影响面）
- 不要执行 git
- 本机**没有 `rg`**，用 Glob/Grep 或 `Get-ChildItem -Recurse`
- 必须用 `py -3.12`
- 终端吞中文：结果写 UTF-8 文件再用 read 工具读
- **只列条目/字段/哈希，不要抄录考纲正文段落**

最后用一句话回复：B/C 是否已移入项目 + weight 公式是否重现全部 410 个值 + 主表 verify 是否全过 + 附表 weight 是否逐一相等 + unittest 结果 + 报告路径。
