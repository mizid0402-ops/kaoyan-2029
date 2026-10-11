# 任务：408 知识树独立抽取 + 对 Codex 产出的对抗性审查（Claude Opus 5 执行）

## 背景

项目：计算机考研 2029 届（数学一 + 英语一 + 408）本地学习系统，位于 `F:\workspace\kaoyan-ai-system`。

正在用**官方大纲**构建 408 知识树。**另一个模型（Codex / gpt-5.6-luna）正在同时做同一件事**，
它会把结果写到 `data/structured_materials/cs408/knowledge_tree.yaml`。你们不共享会话。

**你的任务有两部分**：先自己独立抽一遍（用于比对），再对 Codex 的产出做**对抗性审查**。

## 最高优先级规则

> **AI 不得根据"自己知道的 408"补充考纲节点。只能：大纲原文 → 节点。**

每个节点都必须能在源文件里找到对应文本。允许修正明显排版断裂，但**必须标注**。
宁可少节点，不要编节点。

## 源文件

**主来源（大纲自身层级）**：
```
data/raw_materials/cs408/syllabus/archive408_408_outline_2026.html
```

**交叉验证来源**：
```
data/raw_materials/cs408/syllabus/xdf_408_outline_2026.html      （含试卷分值结构）
data/raw_materials/cs408/syllabus/hep_408_outline_analysis_2026.html  （教辅目录，非大纲）
```

**本机注意**：`py` 启动器不回显子进程输出，所有 Python 命令**必须用 `py -3.12`**。

---

## 任务 A：独立抽取（先做，且不要看 Codex 的产出）

自己从 archive408 提取**完整层级**，写到：

```
data/structured_materials/cs408/knowledge_tree_opus.yaml
```

节点总数、`knowledge_point_id` 命名规则、契约字段要求，与 Codex 相同：
- 先读 `ky/knowledge/knowledge_point.py` 了解契约（**不得修改它**）
- `status: extracted`、`source_kind: official_outline`、`sources` 带**真实 SHA-256**、
  `transition_history` 含一条 `raw → extracted`（`actor: ai`）、`revision: 1`
- id 用 `<subject>.<module>.<slug>` 形式，小写连字符

**如实记录**你抽到多少、哪里不确定。

---

## 任务 B：对抗性审查 Codex 的产出

读 `data/structured_materials/cs408/knowledge_tree.yaml`（若它还没写完，等一会儿再看；
如果始终不存在，明确写"未能审查：文件不存在"）。

逐项判定：

1. **有无编造节点**：Codex 树里的每一个节点，**回到源文件里找对应文本**。
   找不到的，逐条列出——这是最严重的问题（违反最高优先级规则）。
2. **有无遗漏节点**：拿你自己任务 A 的结果做对照，列出 Codex 树里**缺**的节点。
   同时说明这些缺失是"源文件确实没有"还是"Codex 漏了"。
3. **层级是否正确**：节点挂在正确的父级下吗？大纲的「一、」「（一）」「1.」编号
   与实际归属一致吗？
4. **哈希是否正确**：Codex 写的 source `sha256` 是否真的等于源文件的实际哈希？
   自己算一遍比对。
5. **id 稳定性**：`knowledge_point_id` 是否合理、唯一、可长期沿用？有没有会随
   排版变化而漂移的命名？有没有重复 id？
6. **文本修正是否诚实**：Codex 声称做的每一处还原（如 "IPv"→"IPv4/IPv6"），
   在源文件里核验其依据。有没有**未声明的**改写？
7. **来源层级选择是否正确**：有没有拿 hep 教辅目录的节点冒充大纲节点？
   （大纲是"一、基本概念"，教辅是"第1章 基本概念"，编排不同）

### 变异/对抗手法（必须做）

- **随机抽查**：从 Codex 树里随机抽 15 个节点，逐个回源核验，报告命中率。
- **边界抽查**：专挑最可能出错的——网络层的 IPv4/IPv6、组成原理的 Cache 与
  流水线、操作系统的虚拟内存与 I/O、数据结构的 B 树/B+ 树与外部排序。
- **反例构造**：尝试构造一个"看起来合理但源文件里没有"的节点，看 Codex 树里
  是否混入了类似的（例如"红黑树""并查集""动态规划"这类教辅常见但大纲未必单列的内容）。

---

## 任务 C：裁决

给出：
- **Codex 树的质量**：可接受 / 需修正（列出必须改的项）/ 不可接受（说明原因）
- **需要人工复核的清单**：哪些节点必须由用户本人确认（例如粒度是否过粗、是否要拆更细）
- **你自己抽的版本与 Codex 版本的差异汇总**（节点数、层级、命名）

---

## 输出

- 报告写到 `F:\workspace\kaoyan-ai-system\review\rounds\round-6-tree-opus.md`
- 用**中文**，`## A 独立抽取` / `## B 对抗性审查` / `## C 裁决` 作二级标题
- 给真实命令输出，不要只说结论
- 允许并鼓励直接指出 Codex 的错误；反驳必须给依据（源文件原文 + 行号/定位）

## 边界

- 允许新建/修改：`data/structured_materials/cs408/knowledge_tree_opus.yaml`、
  `review/rounds/round-6-tree-opus.md`
- **禁止修改**：`ky/**`、`data/structured_materials/cs408/knowledge_tree.yaml`（那是 Codex 的产出）、
  `data/materials.yaml`、`docs/**`、`tools/**`、`tests/**`，以及 `F:\workspace\study`。不要执行 git。

最后用一句话回复我：你自己抽了多少节点 + Codex 树的裁决 + 编造/遗漏节点数 + 报告路径。
