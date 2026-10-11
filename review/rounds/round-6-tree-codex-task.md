# 任务：从官方大纲构建 408 知识树（Codex 执行，主提取）

## 背景与已定规则

项目：计算机考研 2029 届（数学一 + 英语一 + 408），本机学习系统在 `F:\workspace\kaoyan-ai-system`。

**最高优先级规则（来自项目契约，不得违反）：**

> **AI 不得根据"自己知道的 408"补充考纲节点。只能：大纲原文 → 节点。**

也就是说：**你产出的每一个节点，都必须能在给定的源文件里找到对应文本。**
你可以修正明显的排版断裂（例如"IPv"还原为"IPv4/IPv6"），但**必须在该节点上标注你做了修正**，
并且不得凭领域知识新增源文件里没有的节点。宁可少一个节点，也不要多一个编造的节点。

## 你的唯一权威来源（必须是这个）

```
data/raw_materials/cs408/syllabus/archive408_408_outline_2026.html
```

这是「408 考试大纲」页面，含**大纲自身的层级**（用「一、」「（一）」「1.」这类编号），
不是教材章节。已实测其中含："一、数据结构 / 考查目标 / 一、基本概念 / （一）数据结构的基本概念 / …"。

**交叉验证来源（只用于比对，不要当作主来源）：**
```
data/raw_materials/cs408/syllabus/xdf_408_outline_2026.html
```
该页含试卷结构：数据结构 45 分、计算机组成原理 45 分、操作系统 35 分、计算机网络 25 分；
满分 150 分、考试时间 180 分钟。

**注意**：`data/raw_materials/cs408/syllabus/hep_408_outline_analysis_2026.html` 是
**教辅（大纲解析）的章节目录**，不是大纲。它可作参考，但**不要用它替代大纲层级**——
两者编排不同（教辅是"第1章 基本概念"，大纲是"一、基本概念"）。若你发现二者节点不一致，
以 **archive408** 为准，并在报告里列出差异。

## 你的任务

### 1. 提取完整层级
从 archive408 页面提取 408 大纲的完整考查内容层级：

```
408
├─ 数据结构
│  ├─ 一、基本概念
│  │  ├─ （一）数据结构的基本概念
│  │  └─ （二）算法的基本概念
│  └─ ...
├─ 计算机组成原理
├─ 操作系统
└─ 计算机网络
```

保留**大纲原有的编号与措辞**，不要改写成教材语言。

### 2. 输出为项目契约要求的 YAML

每个节点一条记录，写到：

```
data/structured_materials/cs408/knowledge_tree.yaml
```

必须符合 `ky/knowledge/knowledge_point.py` 的契约（**先读这个文件**）。关键字段：

- `knowledge_point_id`：稳定 id，格式 `<subject>.<module>.<slug>`，例如
  `cs408.ds.basic-concepts.data-structure-definition`。**小写、连字符、稳定**，后续不得随意改。
- `title`：**照抄大纲原文措辞**（可含中文编号）
- `status`：本次全部为 `extracted`（**不是 approved** —— 未人工复核前不允许 approved）
- `source_kind`：`official_outline`
- `sources`：至少一条，且**必须是**
  `path: data/raw_materials/cs408/syllabus/archive408_408_outline_2026.html`
  `sha256: <用文件真实哈希，自己算>`
   `locator`: 定位信息（例如该节点在页面文本中的位置/章节路径）
- `evidence`：可留空
- `transition_history`：至少一条 `raw → extracted`，`actor: ai`
- `revision: 1`

**哈希必须真实**：用 `py -3.12` 自己算文件 SHA-256，不要用占位符或从别处抄。

### 3. 明确标注不确定项
凡遇到下列情况，**在该节点上显式标注**（可加自定义字段，但必须写在 `notes` 里，因为契约禁止未知键）：

- 页面排版导致文本断裂，你做了还原（例如 "IPv" → "IPv4/IPv6"、"散列（ash）表" → "散列表"）
- 你无法确定某个编号层级归属（是二级还是三级）
- archive408 与 xdf 或 hep 三者出现节点差异

### 4. 报告

写 `F:\workspace\kaoyan-ai-system\review\rounds\round-6-tree-codex.md`，包含：

- 提取到的**节点总数**，按四科分别统计（章/节/子节各多少）
- **你做过的所有文本修正**清单（原文 → 你写的），逐条给依据
- **三源差异**：archive408 / xdf / hep 在节点层级上的不一致处，逐条列出
- **你没有把握的地方**（诚实列出，不要为了完整而猜测）
- 完整测试命令输出

## 验收命令

```powershell
cd F:\workspace\kaoyan-ai-system
py -3.12 -c "import sys; sys.path.insert(0,'.'); from ky.knowledge import load_knowledge_points; pts=load_knowledge_points('data/structured_materials/cs408/knowledge_tree.yaml'); print(len(pts), 'nodes loaded OK')"
```
（本机 `py` 启动器不回显输出，**必须用 `py -3.12`**。）

必须能加载成功。加载失败要修到成功为止。

## 边界

- 允许新建/修改：`data/structured_materials/**`、`review/rounds/round-6-tree-codex.md`
- **禁止修改**：`ky/**`（契约代码）、`data/materials.yaml`（台账）、`docs/**`、`tools/**`、
  `tests/**`，以及 `F:\workspace\study` 下任何文件。不要执行 git。
- 如果契约代码有任何地方妨碍你正确表达，**不要改它**，在报告里说明"需要修改 X + 最小 diff"。

最后用一句话回复我：节点总数 + 四科分布 + 你的文本修正条数 + 三源差异条数 + 报告路径。
