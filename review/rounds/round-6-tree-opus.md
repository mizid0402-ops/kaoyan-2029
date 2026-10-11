# Round 6 · 408 知识树独立抽取 + 对 Codex 产出的对抗性审查

执行模型：Claude Opus 5（`--model claude-opus-5`, `--effort high`）
执行时间：2026-09-13
最高优先级规则：**AI 不得根据自己知道的 408 补充考纲节点。只能：大纲原文 → 节点。**

**一句话结论：我独立抽到 358 个节点；Codex 树 403 个节点，编造 0 个、遗漏 0 个，层级归属 0 错、哈希 0 错，裁决为「需修正」（6 项元数据/结构缺陷，无一涉及内容真伪）。**

---

## A 独立抽取

### A.1 方法：不靠"阅读渲染文本"，而是解析大纲自身的结构标记

`archive408_408_outline_2026.html` 是一个 React/RSC 页面。它在 `__VINEXT_RSC_CHUNKS__`
里内嵌了**结构化的 markdown block 树**，每个节点自带 `h2`/`h3`/`h4`/`ol>li`/`p` 标签。
这比"把 HTML 转成纯文本再靠缩进/标点猜层级"可靠得多——层级是**源文件自己声明的**，
不是我推断的。

```
$ py -3.12 parse.py
chunks 32
payload len 63269
block tokens 489
Counter({'li': 226, 'h4': 116, 'ol': 86, 'p': 29, 'h3': 28, 'h2': 4})
```

层级映射（源文件标签 → 知识树层级）：

| 源标签 | 含义 | 数量 |
|---|---|---|
| `h2` | 科目「一、数据结构」 | 4 |
| `h3` | 模块「一、基本概念」 | 28（24 模块 + 4 个「考查目标」） |
| `h4` | 小节「（一）数据结构的基本概念」 | 116 |
| `ol > li` | 条目「1. 顺序存储」 | 226（214 条目 + 12 条考查目标） |
| `p` | 说明性小字「内核模式，用户模式。」 | 29 |

### A.2 两道自检，防止"静默丢节点"

第一版解析器 `items=209`，比 `li` 原始 token 数少 5 个，但**序号连续性检查却是 0 错误**
——因为丢掉的节点连同它所在的整个 `ol` 一起消失了，序号检查根本没机会发现。
加了一道**原始 token 数对账**后才暴露出来：

```
$ py -3.12 findmissing.py
strict 221 loose 226
--- MISSING block 71 item 0
"markdown-block-71-item-0",{"children":[["$","strong","markdown-block-71-item-0-inline-0",
 {"children":["基本运算部件"]}]]}]]}]
```

5 个漏掉的条目是**被 `<strong>` 包裹**的（大纲里这几条是黑体小标题）：
`基本运算部件`、`加/减运算`、`乘/除运算`、`浮点数的表示`、`浮点数的加/减运算`。
修好后两道检查同时通过：

```
$ py -3.12 build.py
raw tokens: h2=4 h3=28 h4=116 li=226 p=29
ordinal check errors: 0
subjects=4 modules=24 sections=116 items=214 notes=29 objectives=12
total knowledge nodes (L1..L4) = 358
  一、数据结构:     modules=7 sections=40 items=24 objectives=3
  二、计算机组成原理: modules=6 sections=29 items=52 objectives=3
  三、操作系统:     modules=5 sections=18 items=61 objectives=3
  四、计算机网络:   modules=6 sections=29 items=77 objectives=3
reconciliation: OK
SHA256 45121f451b3b0cf9880456ad2513f40e3f56f1c1b677c0205da14485f7814cbb
```

- **序号连续性检查**：每个模块的 `一、二、三…`、每个小节的 `（一）（二）…`、
  每个条目的 `1. 2. 3.…` 必须从 1 开始严格连续。0 错误。
  这一项能通过并不显然：条目列表被说明性 `p` 段落切成了多个 `<ol>`，
  源文件用 `"start":N` 标出续接位置（如 `（三）程序运行环境`：`ol(start=1)` → `p` → `ol(start=2)`），
  我按 `start` 还原后编号才连续。
- **原始 token 对账**：`214 条目 + 12 考查目标 = 226 = li 原始数`，
  `4 = h2`，`24 + 4 = 28 = h3`，`116 = h4`，`29 = p`。全部对得上，无静默丢失。

### A.3 产出

写入 `data/structured_materials/cs408/knowledge_tree_opus.yaml`（358 节点，359,494 字节），
通过**未修改的**契约校验器：

```
$ py -3.12 -c "from ky.knowledge.knowledge_point import load_knowledge_points; ..."
VALIDATED 358 points
statuses {'extracted'}
source_kinds {'official_outline'}
revisions {1}
example id: cs408.3-操作系统.3-内存管理.1-内存管理基础
example title: （一）内存管理基础
```

回源自检——**每个 title、每个 quote_ref 都必须逐字出现在源文件里**：

```
$ py -3.12 roundtrip.py
archive408 sha256 = 45121f451b3b0cf9880456ad2513f40e3f56f1c1b677c0205da14485f7814cbb
--- OPUS: 358 items
    titles NOT found verbatim in source: 0
    quote_ref NOT found verbatim: 0
    wrong sha256 on archive408 source: 0
    source path does not exist: 0
    duplicate ids: 0 []
```

### A.4 我做的取舍（都不是"源文件没有"，而是"要不要单列成节点"）

| 内容 | 数量 | 我的处理 | 理由 |
|---|---|---|---|
| 各科「考查目标」标题 | 4 | **不列为知识点** | 是能力要求陈述，不是知识点 |
| 考查目标正文条目 | 12 | **不列为知识点** | 同上 |
| 说明性小字（`p`） | 29 | **不单列**，作为所属节点 `sources` 的附加 `locator.quote_ref` 保留 | 它们是上一条目的解释，不是并列条目 |

这三类内容**一条都没丢**，只是没有获得独立的 `knowledge_point_id`。
Codex 选择把它们全部单列（见 B.2），这是本次两版差异的**全部来源**。

### A.5 交叉验证：xdf 结构完全一致，但 xdf 本身有 OCR 损坏

把 xdf 大纲按同样规则重建后与 archive408 逐节点对比：

```
$ py -3.12 xdfstruct.py
xdf 数据结构:     modules=7 sections=40 items=24
xdf 计算机组成原理: modules=6 sections=29 items=52
xdf 操作系统:     modules=5 sections=18 items=61
xdf 计算机网络:   modules=6 sections=29 items=77
xdf totals: modules=24 sections=116 items=214
```

**逐项与 archive408 完全相等**（24 / 116 / 214，且分科数字一一对应）。这是对任务 A 最强的独立佐证。

但 xdf **不能**用来"修正" archive408，它是质量更差的一版：

- `计算机组成的基里和基本方法` ← `基本原理` 的 OCR 错字（xdf 第 230 行）
- `VIAN 基本概念与基本原理` ← `VLAN` 的 OCR 错字
- `ISO/OSI 参考模型和 TCP/IP 参考模型【26 改动】` ← 混入了编者批注
- `(二）设备独立软件`、`(三）外存管理` ← 半角/全角括号混用

以及一批**实质措辞分歧**（archive408 在左，xdf 在右）：

| archive408（主来源） | xdf（交叉验证源） |
|---|---|
| 树**与**二叉树 | 树**和**二叉树 |
| 树**形**查找 | 树**型**查找 |
| 散列（**hash**）表 | 散列（**Hash**）表 |
| 多处理器基本概念 | 多处理器**的**基本概念 |
| 总线和输入**/**输出系统 | 总线和输入输出系统 |
| ARP 协议、DHCP 协议**与** ICMP 协议 | ARP 协议、DHCP 协议**、**ICMP 协议 |
| 路由表与**分组**转发 | 路由表与**路由**转发 |
| UDP 数据**报** | UDP 数据**段** |
| HTTP **协议** | HTTP |

**处理方式**：一律以 archive408 原文为准，未做任何"择优合并"。
这些分歧属于需要用户确认的事项，已列入 C.2。

### A.6 不确定的地方（如实记录）

1. **`（八）数据链路层设备` 只有一段 `p`，没有 `li`。** 源文件里它是
   `<p>以太网交换机及其工作原理。</p>`，不是列表项。我按"说明"处理（不单列节点），
   Codex 按"条目"处理（单列为 `detail-01`）。此处我倾向于 Codex 的处理更好——
   该小节若不单列，就只剩一个空标题。**建议采纳 Codex 的做法**，同样适用于
   `（二）计算机性能指标` 和 `（四）操作系统结构`（共 3 处）。
2. **id 命名规则我做了扩展。** 任务书写的是 `<subject>.<module>.<slug>`（3 段），
   但大纲实际有 4 层。我用了 4 段点分路径，并保留中文（见 C.3）。
3. **29 条说明性小字的归属**是我按文档顺序推断的（`p` 紧跟 `ol` → 归属该 `ol` 的最后一条；
   `p` 紧跟 `h4` → 归属该小节）。源文件没有显式的父子标记，这一层是**我的推断**，
   虽与排版语义一致，但严格说不是"大纲自己声明的"。

---

## B 对抗性审查

审查对象：`data/structured_materials/cs408/knowledge_tree.yaml`（403 节点，263,273 字节）。
文件在我完成任务 A 之后才出现；任务 A 全程未参考它。

### B.1 有无编造节点 —— **0 个**

两种互相独立的方法都得到 0：

**方法一：全量回源。** 剥离 Codex 自加的 `N. ` 序号前缀后，403 条 title 逐条在源文件中查找：

```
$ py -3.12 audit.py
--- [1] 编造检测 ---
归一化后仍找不到的 title: 0
```

**方法二：位置反查。** 把每个 `chapter-N.section-M.detail-K` 按编号映射回我自己解析出的
archive408 同位置节点，比对文本是否一致：

```
--- [C] 层级归属：Codex 的 chapter/section/detail 与大纲编号是否一致 ---
层级归属错误数: 0
```

403 个节点全部落在大纲的正确位置上。**没有一个编造节点。**

### B.2 有无遗漏节点 —— **0 个**

```
--- [2] 遗漏检测：与 Opus 树逐条比对 ---
Opus 有 / Codex 无: 0
Codex 有 / Opus 无: 42（去重后；实际 45 个节点）
```

Codex 是我这版的**严格超集**。多出的 45 个，正是 A.4 里我主动不单列的三类：

| 多出的内容 | 数量 | 源文件里有吗 | 判定 |
|---|---|---|---|
| 各科「考查目标」标题 | 4 | **有**（`h3`，`archive=True`） | 粒度选择差异，非编造 |
| 考查目标正文条目 | 12 | **有**（`li`） | 同上 |
| 说明性小字 | 29 | **有**（`p`，`archive=True`） | 同上 |

`4 + 12 + 29 = 45 = 403 − 358`。**差额完全可解释，没有一条来路不明。**

结构计数也与我的独立解析完全对账：

```
--- [E] 结构计数 ---
{'subject': 4, 'exam-objectives': 4, 'objective-detail': 12,
 'chapter': 24, 'section': 116, 'detail': 243} total 403
archive408 实际: subject=4 module=24 section=116 item=214 annotation=29 objective=12 objective-hdr=4
  -> 214 + 29 = 243 应等于 Codex 的 detail 数   ✓
```

### B.3 层级是否正确 —— 编号归属全对，但有 26 处"提了一级"

**编号归属：0 错误**（见 B.1 方法二）。`一、`/`（一）`/`1.` 三级编号与实际归属完全一致。

**但是**：29 条说明性小字被 Codex 提升成了**与条目并列**的 `detail-NN`，
而它们在大纲里是**上一条目的下属说明**：

```
$ py -3.12 audit3.py
archive408 注释总数 = 29
  附属于某个「条目」的注释 = 26   （Codex 把它们提成了条目的同级 detail）
  附属于「小节」本身的注释 = 3    （该小节无条目，提成 detail-01 合理）
     · 一、计算机系统概述 / （二）计算机性能指标  ->  吞吐量、响应时间；CPU 时钟周期、主频、CPI…
     · 一、操作系统基础 / （四）操作系统结构      ->  分层，模块化，宏内核，微内核，外核。
     · 三、数据链路层 / （八）数据链路层设备      ->  以太网交换机及其工作原理。

被错误提升为同级的注释（示例）:
   · （二）运算方法和运算电路 下，条目「基本运算部件」的说明 ->「加法器，算术逻辑部件（ALU）。」
   · （七）虚拟存储器 下，条目「页式虚拟存储器」的说明 ->「基本原理，页表，地址转换，TLB（快表）。」
   · （三）I/O 方式 下，条目「程序中断方式」的说明 ->「中断的基本概念，中断响应过程…」
```

**依据**：源文件 `markdown-block-71` 是 `<ol start=1>` 含 `基本运算部件`，
紧随的 `markdown-block-72` 是 `<p>加法器，算术逻辑部件（ALU）。</p>`，
再后面的 `markdown-block-73` 是 `<ol start=2>` 含 `加/减运算`。
`start=2` 明确表明 `加/减运算` 是**第 2 条**——那么中间的 `p` **不是第 2 条**，
它是第 1 条的说明。Codex 却把它编成了 `detail-02`，把 `加/减运算` 挤到 `detail-03`。

后果：`（二）运算方法和运算电路` 在 Codex 树里显示为 6 个并列条目，
而大纲只有 3 条（各带一段说明）。**这 26 处需要修正。**
其余 3 处（该小节本身没有条目）提升为 `detail-01` 是合理的，我认可。

### B.4 哈希是否正确 —— **0 错误**

自己重算一遍比对：

```
$ py -3.12 audit.py
--- [4] 哈希检测 ---
实际 sha256:
   45121f451b3b0cf9880456ad2513f40e3f56f1c1b677c0205da14485f7814cbb  archive408_408_outline_2026.html
   8a2b2710a90e47f57f527575df84cdb3fd4727b5083caf1bf14cc51047122026  xdf_408_outline_2026.html
   7487644cf10c85d1fca0e64a1577f577159836b6d31c09225620cd9851c7b11c  hep_408_outline_analysis_2026.html
   8a2b2710a90e47f57f527575df84cdb3fd4727b5083caf1bf14cc51047122026  408_outline_xdf.html
sha256 与实际不符: 0
source.path 不存在: 0
引用的源文件分布: {'archive408_408_outline_2026.html': 403}
```

403 个节点全部只引用 archive408，哈希全对。

**额外检查（任务书未要求）**：`locator.offset` 是否真的指向 `quote_ref`：

```
--- [A] locator.offset 是否真的指向 quote_ref ---
检查 403 个 offset, 不精确指向 quote_ref 的: 0
```

403/403 字节偏移精确命中。这一项 Codex 做得很扎实。

> 附带发现：`408_outline_xdf.html` 与 `xdf_408_outline_2026.html` **哈希完全相同**
> （`8a2b2710…2026`），是同一文件的两份副本。两版树都没引用它，不影响本轮结论，
> 但 `data/materials.yaml` 里可能存在重复登记，建议单独核对。

### B.5 id 稳定性 —— 无重复、无大写，但有两处结构缺陷 + 漂移风险

```
--- [5] id 稳定性 ---
重复 id: 0  []
含大写/异常字符的 id: 0  []
最长 id 长度: 44
```

唯一性和字符规范没问题。但：

**(a) id 链不是前缀树 —— 44 个"孤儿"**

```
--- [3] 层级检测 ---
父节点缺失(孤儿)数: 44
   ! cs408.ds.subject                             -> missing parent cs408.ds
   ! cs408.ds.chapter-01                          -> missing parent cs408.ds
   ! cs408.ds.exam-objectives.objective.detail-01 -> missing parent cs408.ds.exam-objectives.objective
```

两个问题：
- 科目节点是 `cs408.ds.subject`，而模块是 `cs408.ds.chapter-01`——
  科目成了模块的**兄弟**而非**祖先**，`cs408.ds` 本身不是节点。
  任何"按 id 前缀求父节点"的代码都会在这里失败。
- `cs408.ds.exam-objectives.objective.detail-01` 里的 `.objective.` 是个**幽灵段**，
  从来不对应任何节点。

**(b) 漂移风险：纯位置编号**

```
--- id 漂移风险演示 ---
   cs408.cn.chapter-04.section-02                 （二）路由算法
   cs408.cn.chapter-04.section-03                 （三）IPv4
   cs408.cn.chapter-04.section-03.detail-01       1. IPv4 分组
```

`chapter-NN`/`section-NN`/`detail-NN` **不含任何语义**。2027 大纲若在网络层插入一节，
`section-03` 就从 `IPv4` 变成别的内容，而 id 字符串不变——
历史学习记录会静默挂到错误的知识点上。这是长期沿用的实质隐患。

我这版用 `序号-中文slug`（如 `cs408.4-计算机网络.4-网络层.3-ipv4`）：同样含位置序号，
但保留了 slug，一旦错位可以被检测出来。代价是 id 更长（平均 36.8 vs 35.6，最长 66 vs 44）。
**两种方案都不理想**，见 C.2。

### B.6 文本修正是否诚实 —— 有 1 处**未声明**的改写（226 个节点）

```
--- [B] title 与 quote_ref 的差异 ---
   前缀「N. 」（源文本无，来自 <ol> 序号）: 226
   其他差异全部:
   （空）
```

- **好消息**：除序号前缀外，**没有任何其他文本差异**。没有改字、没有补词、没有合并。
  `quote_ref` 里存的都是干净的源文本。
- **问题**：226 个节点的 `title` 被加上了 `1. ` `2. ` 这样的序号前缀。
  这个序号**不在源文本里**——它来自 `<ol>` 的渲染序号。

客观地说，这个"还原"是**正确的**：226 = 214 条目 + 12 考查目标，
与源文件 `<ol>` 的 `start` 序号完全吻合，一个不多一个不少。
但任务书写得很清楚：**"允许修正明显排版断裂，但必须标注"**。
而 Codex 的 YAML 是一个**裸列表，没有任何文件头、没有任何方法说明、没有声明这处加工**：

```yaml
- schema_version: 1
  knowledge_point_id: cs408.ds.subject
  title: 一、数据结构
```

**判定：违反"必须标注"，但属于程序性违规，不涉及内容真伪。必须补声明。**

> 任务书举例的 `"IPv"→"IPv4/IPv6"` 还原：**Codex 没有做过这个声明，树里也没有这类节点。**
> 见 B.7——那个截断只存在于教辅文件里。

### B.7 来源层级选择 —— **完全正确，未混入教辅**

```
--- [7] 教辅(hep)污染检测 ---
命中教辅专有措辞: 0
title 含「第N章/第N部分」编排: 0 []
节点顺序指纹: 路由算法@343  IPv4@348  -> 符合大纲(路由算法在前)
```

三道检测都通过：

1. **教辅专有措辞 0 命中。** 检测词表取自 hep 目录里大纲**没有**的表述：
   `同步练习`、`算法和算法评价`、`两种存储结构的对比`、`数据的存储和排列`、
   `I/O系统基本概念`、`操作系统的发展与分类`、`文件系统基础`、`存储器概述`、
   `程序的机器级代码表示`、`用户数据报协议`、`万维网`、`域名系统`、
   `文件传输协议`、`设备独立性软件`、`进程同步` 等 20 条。全部 0 命中。
2. **无「第N章」编排。** 大纲用 `一、`/`（一）`，教辅用 `第1章`/`1.1`。Codex 全用前者。
3. **顺序指纹通过。** 这是最有力的一条——两个来源的网络层**排序不同**：

   | 大纲（archive408） | 教辅（hep） |
   |---|---|
   | （一）网络层的功能 | 4.1 网络层的功能 |
   | **（二）路由算法** | **4.2 IPv**（截断） |
   | **（三）IPv4** | **4.3 IPv**（截断） |
   | （四）IPv6 | **4.4 路由算法** |

   Codex 树里 `路由算法` 在 `IPv4` **之前**，是大纲顺序，不是教辅顺序。

**关于任务书提到的 `"IPv"→"IPv4/IPv6"`**：我核验了截断的真实来源——

```
$ py -3.12 -c "...re.finditer('IPv', hep_html)..."
'络层<ul class="pl-40"><li>4.1 网络层的功能<ul class="pl-40"></ul></li><li>4.2 IPv<ul...'
'...<li>4.2 IPv<ul class="pl-40"></ul></li><li>4.3 IPv<ul class="pl-40"></ul></li><li>4.4 路...'
```

`4.2 IPv` / `4.3 IPv` 的截断**只存在于 hep 教辅文件**。archive408 里是干净的
`（三）IPv4` / `（四）IPv6`，根本不需要还原。
**因此："谁声称还原了 IPv，谁就是在读教辅。" Codex 没有声称，也没有读。这一项它做对了。**

### B.8 随机抽查 15 个（`seed=20260913`）—— 命中率 100%

> **先更正我自己的一个测量错误。** 第一遍抽查我直接用 title 原文回源，得到 4/15 = 26.7%。
> 那个数字是错的——它测的是"title 是否带序号前缀"，不是"节点是否编造"。
> 剥离 `N. ` 前缀后重测：

```
$ py -3.12 audit2.py
--- [D] 修正后的随机抽查 15 个（剥离「N. 」序号前缀后回源） ---
 1. [HIT] cs408.ds.chapter-05.section-04.detail-03  quote_ref回源=True   '拓扑排序'
 2. [HIT] cs408.cn.chapter-03.section-04.detail-03  quote_ref回源=True   '后退 N 帧协议（GBN）'
 3. [HIT] cs408.cn.chapter-06.section-05.detail-01  quote_ref回源=True   'WWW 的概念与组成结构'
 4. [HIT] cs408.co.chapter-02.section-02.detail-03  quote_ref回源=True   '加/减运算'
 5. [HIT] cs408.co.chapter-03.section-05             quote_ref回源=True   '外部存储器'
 6. [HIT] cs408.os.chapter-01.section-03.detail-05  quote_ref回源=True   '程序的链接与装入'
 7. [HIT] cs408.os.chapter-01.section-04             quote_ref回源=True   '操作系统结构'
 8. [HIT] cs408.os.chapter-02.section-03.detail-02  quote_ref回源=True   '基本的实现方法'
 9. [HIT] cs408.co.chapter-06.section-02.detail-02  quote_ref回源=True   'I/O 端口及其编址'
10. [HIT] cs408.ds.chapter-04.section-02.detail-03  quote_ref回源=True   '二叉树的遍历'
11. [HIT] cs408.os.chapter-01.section-03.detail-01  quote_ref回源=True   'CPU 运行模式'
12. [HIT] cs408.os.chapter-02.section-01.detail-05  quote_ref回源=True   '进程与线程的组织与控制'
13. [HIT] cs408.co.chapter-02.section-04.detail-02  quote_ref回源=True   'IEEE 754 标准。'
14. [HIT] cs408.os.chapter-05.section-03             quote_ref回源=True   '外存管理'
15. [HIT] cs408.cn.chapter-04.section-03.detail-04  quote_ref回源=True   'ARP 协议、DHCP 协议与 ICMP 协议'
命中率: 15/15 = 100.0%
```

15/15 全部命中，`quote_ref` 也全部回源成功。

### B.9 边界抽查 —— 24/24 全对

专挑最易出错的：网络层 IPv4/IPv6、组成原理 Cache 与流水线、操作系统虚拟内存与 I/O、
数据结构 B 树/B+ 树与外部排序。

```
--- [9] 边界抽查 ---
   archive=True  codex=True  opus=True   IPv4
   archive=True  codex=True  opus=True   IPv6
   archive=True  codex=True  opus=True   IPv4 分组
   archive=True  codex=True  opus=True   IPv4 地址与 NAT
   archive=True  codex=True  opus=True   ARP 协议、DHCP 协议与 ICMP 协议
   archive=True  codex=True  opus=True   Cache 的基本原理
   archive=True  codex=True  opus=True   Cache 和主存之间的映射方式
   archive=True  codex=True  opus=True   Cache 中主存块的替换算法
   archive=True  codex=True  opus=True   Cache 写策略
   archive=True  codex=True  opus=True   指令流水线的基本概念
   archive=True  codex=True  opus=True   结构冒险、数据冒险和控制冒险的处理
   archive=True  codex=True  opus=True   超标量和动态流水线的基本概念
   archive=True  codex=True  opus=True   虚拟内存的基本概念
   archive=True  codex=True  opus=True   请求页式管理
   archive=True  codex=True  opus=True   页置换算法
   archive=True  codex=True  opus=True   内存映射文件（memory-mapped files）
   archive=True  codex=True  opus=True   I/O 控制方式
   archive=True  codex=True  opus=True   I/O 软件层次结构
   archive=True  codex=True  opus=True   假脱机技术（SPOOLing）
   archive=True  codex=True  opus=True   B 树及其基本操作、B+ 树的基本概念
   archive=True  codex=True  opus=True   外部排序
   archive=True  codex=True  opus=True   红黑树
   archive=True  codex=True  opus=True   并查集及其应用
   archive=True  codex=True  opus=True   堆及其应用
```

三列完全一致，无一处 MISMATCH。

> 注：`红黑树`、`并查集及其应用`、`堆及其应用` 看着像教辅内容，但它们**确实是 2026 大纲原文**
> （`（五）树形查找` 下第 3 条、`（四）树与二叉树的应用` 下第 2、3 条）。两版都正确收录了。

### B.10 反例构造 —— 两版均 0 污染

构造 17 个"看起来非常合理、教辅里必有、但大纲未单列"的节点名，看是否混入：

```
--- [10] 反例构造 ---
   archive=False codex=False opus=False  动态规划
   archive=False codex=False opus=False  贪心算法
   archive=False codex=False opus=False  分治法
   archive=False codex=False opus=False  KMP 算法
   archive=False codex=False opus=False  AVL 树
   archive=False codex=False opus=False  哈希冲突
   archive=False codex=False opus=False  磁盘阵列
   archive=False codex=False opus=False  RAID
   archive=False codex=False opus=False  进程调度算法
   archive=False codex=False opus=False  Belady 异常
   archive=False codex=False opus=False  银行家算法
   archive=False codex=False opus=False  拥塞避免
   archive=False codex=False opus=False  快速重传
   archive=False codex=False opus=False  三次握手
   archive=False codex=False opus=False  Trie 树
   archive=False codex=False opus=False  跳表
   archive=False codex=False opus=False  布隆过滤器
```

17/17 三列全 `False`。两版都**没有**用"自己知道的 408"去补节点。
这是本轮最高优先级规则的核心检验项，**Codex 通过**。

### B.11 契约校验

```
--- [6] 契约校验 ---
契约校验通过: 403 points
statuses {'extracted'} kinds {'official_outline'} revisions {1}
transition_history 不是单条 raw->extracted(ai) 的节点: 0 []
```

`status`/`source_kind`/`revision`/`transition_history` 四项要求全部满足。

但：

```
--- [F] transition_history 字段完整性 ---
缺少 at 时间戳的节点: 403 / 403
evidence 非空的节点: 0
```

**403/403 的 `transition_history` 都没有 `at` 时间戳。** 契约不强制
（`TRANSITION_RULES` 只 `requires={"source"}`），所以校验能过；
但 `ky/knowledge/knowledge_point.py:246` 的 `transition_knowledge_point()`
是**总是**写 `at` 的。缺了它，这批节点没有任何抽取时间可追溯。

---

## C 裁决

### C.1 Codex 树的质量：**需修正**

**内容层面无可指摘。** 编造 0、遗漏 0、层级编号 0 错、哈希 0 错、offset 0 错、
教辅污染 0、反例污染 0、随机抽查 15/15、边界抽查 24/24。
在"不得凭自己知道的补节点"这条最高优先级规则上，Codex **完全合格**。

缺陷集中在元数据和结构表达，按严重度排序：

| # | 问题 | 影响范围 | 严重度 | 必改 |
|---|---|---|---|---|
| 1 | **未声明**给 title 加了 `N. ` 序号前缀（源文本无此序号） | 226 节点 | 中（违反"必须标注"） | **是** |
| 2 | **26 条说明性小字被提升为条目同级**，应为下属说明 | 26 节点，影响 12 个小节的条目数 | 中（层级失真） | **是** |
| 3 | `transition_history` 全部缺 `at` 时间戳 | 403/403 | 中（无抽取时间可追溯） | **是** |
| 4 | id 链非前缀树：`.subject` 与 `.chapter-NN` 同级；`.objective.` 是幽灵段 | 44 处 | 中（前缀求父会失败） | **是** |
| 5 | 文件无任何头部/来源说明/方法声明 | 全文件 | 低-中 | **是** |
| 6 | id 用纯位置编号，大纲改版会静默错位 | 全部 | 中（长期隐患） | 需决策，见 C.2 |

**不构成缺陷、我认可 Codex 做法的地方**（我这版反而应当改）：

- 把 `（二）计算机性能指标`、`（四）操作系统结构`、`（八）数据链路层设备` 这 3 个
  "只有说明没有条目"的小节，其说明提升为 `detail-01`——**合理，我采纳**。
- 收录「考查目标」的 4 + 12 个节点——它们确实在大纲原文里。是否作为"知识点"是
  粒度问题，不是对错问题，交用户定（见 C.2 第 1 条）。
- 用 YAML 锚点（`&id001` / `*id001`）让 `sources[0]` 和 `transition_history[0].source`
  指向同一对象——**这是个好设计**，从结构上杜绝了两处 source 不一致。

### C.2 需要用户本人确认的清单

| # | 事项 | 选项 | 我的建议 |
|---|---|---|---|
| 1 | 「考查目标」4 段 + 12 条要不要作为知识点？ | Codex：要（16 个节点）／我：不要 | **不要**。它是能力要求，不是可学习/可复习的知识点，混进来会污染后续的频次统计和复习排程 |
| 2 | 29 条说明性小字要不要单列节点？ | Codex：全单列／我：全不单列 | **折中**：3 条"小节自身说明"单列；26 条"条目说明"作为条目的属性而非独立节点 |
| 3 | **粒度是否够细**：214 个叶子里，有些明显偏粗 | 如 `（二）二叉树` 下只有 4 条；`TCP 拥塞控制` 是一个叶子 | 需要你判断。大纲本身就到这一层为止，**再细拆就必须引入大纲外知识，会违反最高优先级规则**。建议保持现状，细拆留到"真题→知识点"映射阶段用真题驱动 |
| 4 | archive408 与 xdf 的 9 处措辞分歧以哪个为准？（A.5 表） | | **archive408**。xdf 有 OCR 错字（`基里`/`VIAN`）和编者批注（`【26 改动】`），可靠性明显更低 |
| 5 | id 命名最终方案（见 C.3） | Codex 纯位置／我 序号+中文slug／第三方案 | 建议**序号 + 语义 slug**，并单独维护一张 `id → 大纲原文` 的映射表用于跨年份改版比对 |
| 6 | `408_outline_xdf.html` 与 `xdf_408_outline_2026.html` 哈希相同，是重复文件 | | 建议核对 `data/materials.yaml` 是否重复登记，删其一 |
| 7 | 两版树是否合并，保留哪一份？ | | 见 C.4 |

### C.3 我的版本与 Codex 版本差异汇总

**节点数**

| 层级 | Opus (我) | Codex | 差 | 说明 |
|---|---|---|---|---|
| 科目 | 4 | 4 | 0 | |
| 考查目标标题 | 0 | 4 | +4 | 我不列为知识点 |
| 考查目标条目 | 0 | 12 | +12 | 同上 |
| 模块「一、」 | 24 | 24 | 0 | |
| 小节「（一）」 | 116 | 116 | 0 | |
| 条目「1.」 | 214 | 214 | 0 | **完全一致** |
| 说明性小字 | 0 | 29 | +29 | 我作为 `locator.quote_ref` 保留 |
| **合计** | **358** | **403** | **+45** | 差额 = 4+12+29，完全可解释 |

分科条目数两版一致：数据结构 24、组成原理 52、操作系统 61、计算机网络 77。

**层级**

| | Opus | Codex |
|---|---|---|
| id 深度分布 | `{1:4, 2:24, 3:116, 4:214}` | `{2:32, 3:116, 4:255}` |
| 科目节点位置 | 深度 1，是模块的真祖先 | `cs408.ds.subject`，与模块同级（深度 2） |
| id 是否前缀树 | **是**（0 孤儿） | **否**（44 孤儿） |
| 说明性小字层级 | 不成节点 | 提升为条目同级（26 处偏高） |

**命名**

| | Opus | Codex |
|---|---|---|
| 风格 | 序号 + 中文 slug | 英文缩写 + 纯位置编号 |
| 示例 | `cs408.4-计算机网络.4-网络层.3-ipv4.1-ipv4-分组` | `cs408.cn.chapter-04.section-03.detail-01` |
| 平均长度 | 36.8 | 35.6 |
| 最长 | 66 | 44 |
| 重复 id | 0 | 0 |
| 可读性 | 高（一眼看出是哪个知识点） | 低（必须查表） |
| 改版鲁棒性 | 中（错位可检测） | **低（错位静默）** |
| 与任务书 `<subject>.<module>.<slug>` 的吻合度 | 扩展为 4 段，保留中文 | 段数吻合但 slug 无语义 |

**元数据**

| | Opus | Codex |
|---|---|---|
| 文件头声明 | 有（7 行，写明来源/sha256/层级映射/取舍） | **无** |
| `transition_history.at` | 有 | **全部缺失** |
| `locator` 字段 | `section` + `offset` + `quote_ref` | `section` + `offset` + `quote_ref` |
| offset 准确性 | 指向 RSC block 标记 | **指向 quote_ref 首字符，403/403 精确** |
| 说明性小字保存方式 | 作为附加 `sources[]` 条目 | 作为独立节点 |
| YAML 锚点复用 source | 无（重复写两份） | **有（更严谨）** |
| 文件大小 | 359,494 B | 263,273 B |

### C.4 结论与建议

**Codex 的树在内容正确性上和我独立抽取的结果完全一致**——两个模型、两套完全不同的
解析路径（我走 RSC 结构树，它走文本序列），在 214 个叶子条目上逐字吻合，
在 116 个小节、24 个模块上编号归属零分歧。这是很强的交叉验证，
说明**这份大纲的骨架已经可以信任了**。

建议以 **Codex 的 `knowledge_tree.yaml` 为基线**（它的 offset 精度和 YAML 锚点设计更好），
按 C.1 表格改掉 6 项缺陷，其中第 2 项（26 条说明性小字降级）和第 1 项（声明序号前缀）
必须在进入下一阶段前完成。我的 `knowledge_tree_opus.yaml` 保留作为**对照基准**，
用于改完后回归比对——改完后两版的 214 个叶子条目应当仍然逐字一致。

---

## 附录：可复现命令

所有脚本在 `%TEMP%\opus6\`（未写入仓库）。本机 `py` 启动器不回显子进程输出，
全部使用 `py -3.12`；Windows 控制台无法显示中文，故所有输出先写 UTF-8 文件再读取。

```
py -3.12 parse.py        # 提取 RSC payload，统计 block 标签
py -3.12 parse2.py       # 按文档顺序还原 block 序列
py -3.12 findmissing.py  # 找出被严格正则丢掉的 <li>
py -3.12 build.py        # 建树 + 序号连续性检查 + 原始 token 对账
py -3.12 emit.py         # 生成 knowledge_tree_opus.yaml
py -3.12 roundtrip.py    # 全量回源校验（title / quote_ref / sha256 / path）
py -3.12 others.py       # 抽取 xdf、hep 文本
py -3.12 crossval.py     # 与 xdf 逐条比对
py -3.12 xdfstruct.py    # 重建 xdf 结构并与 archive408 逐节点 diff
py -3.12 audit.py        # 对抗性审查 [1]-[10]
py -3.12 audit2.py       # offset / title 漂移 / 层级归属 / 修正后抽样
py -3.12 audit3.py       # 注释归属量化 / locator 一致性 / id 漂移演示
```

**边界遵守**：本轮只新建了 `data/structured_materials/cs408/knowledge_tree_opus.yaml`
和本报告。未修改 `ky/**`、未触碰 `knowledge_tree.yaml`（Codex 产出，仅只读解析）、
未修改 `data/materials.yaml`、`docs/**`、`tools/**`、`tests/**`、`F:\workspace\study`，
未执行任何 git 命令。
