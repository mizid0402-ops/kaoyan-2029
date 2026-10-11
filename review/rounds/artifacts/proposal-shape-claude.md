# 静默降级缺陷 —— 修改建议（Claude）

> 依据：`round-32-shape-fix-brief.md` 第 2 节「已复现的缺陷」。第 3 节「未复现的指控」未被使用。
> 本建议表中标 **[实测]** 的结论，均由我本人在临时副本上独立复跑得到（命令与产物见文末「验证记录」），
> 与底本的复核相互独立；标 **[推断]** 的是未直接测试、基于代码阅读的判断。

---

## 0. 根因定位 [实测，读代码 + 复现]

`tools/verify_tree.py::infer_tree_shape`（第 51–80 行）只看 `scope == "chapter"` 的节点算「树形标记」：

```python
chapter_ids = [p.knowledge_point_id for p in points if p.scope == "chapter"]
if not chapter_ids:
    return "structure"
```

`scope` 是数据里可自由改写的字段，不是结构事实。只要把这个字段清空或改掉，
"有没有章"这件事在推断器眼里就消失了，于是分支必然滑向 `structure`（该分支检查最松）。
这不是"漏了一个 case"，是**推断的输入选错了**——选了一个可被数据本身推翻的信号。

---

## 1. 树形该怎么推断？

**推荐：只从 id 语法推断，完全不看 `scope`。** 两种已知形态的 id 语法标记互相独立：

| 形态 | 正标记（在**全体 id**中找，不筛 scope） |
|---|---|
| cs408 | 存在 id 满足 `^[^.]+\.[^.]+\.chapter-[0-9]{2}$`（章）**或** `^.+\.chapter-[0-9]{2}\.section-[0-9]{2}$`（节） |
| math1 | 存在 id 以 `.chapter` 结尾，**或** 存在 base 使得 `base+".content"` 与 `base+".requirements"` 同时在 id 集合里 |
| structure | 以上都不存在 |
| 都存在 | 判为 ambiguous，直接失败（保留原有行为） |

**为什么要把 `.content`/`.requirements` 兄弟对也算作 math1 的正标记**：cs408 的正标记里包含"节"级正则
（`CS408_SECTION_RE`），这样即使全部章节点被删，残留的 `chapter-NN.section-NN` 形态的节点 id 依然能撑住
"这是 cs408" 的判断。math1 需要对称处理——如果只用 `.chapter` 后缀做标记，P1 式攻击（删光所有
`scope=chapter` 节点）在 math1 树上会把 `.content`/`.requirements` 这两个"章的证据"也一并阴跌成
`structure`，重蹈覆辙。用 content+requirements 同时存在作为 math1 的第二标记，堵住了这个对称漏洞。
[实测确认，见下方 math1_P1 探针]

**代价**：cs408 和 math1 的正则需要理解 id 语法（本来就是内部约定，见 `cs408/knowledge_tree.yaml` 文件头注释
"ID 末段约定"），如果未来某形态改了 id 拼写习惯，这里要跟着改——但这本来就是 `CS408_CHAPTER_RE` /
`CS408_SECTION_RE` 现有的耦合，不是新增的脆弱性。

---

## 2. "本该有章却没有章"要不要单独报错？判据是什么？

**要。** 光换掉第 1 节的推断输入还不够——它只保证"树形认得对"，不保证"scope 标签本身没被动过手脚"。
需要在树形确定之后，加一条**双向**检查（新增函数 `scope_signature_failures`）：

- 对 cs408 树：`CS408_CHAPTER_RE.fullmatch(id)` 与 `scope == "chapter"` 必须**同真同假**。
  - id 像章、scope 不是 chapter → `"{id}: id matches the cs408 chapter-NN pattern but scope={scope!r} (expected 'chapter')"`
  - scope 是 chapter、id 不像章 → 反向同款报错。
- 对 math1 树：`id.endswith(".chapter")` 与 `scope == "chapter"` 同真同假，报错文案对称。

**这条检查专门命中 P3 式攻击**（id 不动、只改 `scope`）。P1 式攻击（连 id 带节点整个删掉）不会触发这条——
它会触发已有的"section 的祖先章节点是否存在"检查（`by_id` 里找不到该祖先 id）。两条检查合起来，
"该有章却没有" 在两种伪造路径下都有专属的、按名字能一眼看出问题的失败信息，不再是泛泛的"通过"。

**判据可以严格区分三棵真实树**：cs408 用 `chapter-NN` 数字后缀，math1 用裸 `.chapter` 后缀，
两者字面互斥（一个要求两位数字后缀，一个要求恰好是单词 `chapter`），eng1 两者都不占用
[实测：见下方"跨形态误报排查"]。

---

## 3. 合法树形有几种？分类判据？识别不明确时的行为？

**当前证据支持 3 种，不多不少**：

1. **cs408**：id 集合命中 `chapter-NN` 或 `chapter-NN.section-NN` 正则。
2. **math1**：id 集合命中 `.chapter` 后缀，或 `.content`/`.requirements` 兄弟对。
3. **structure**（eng1 是其实例）：以上都不命中——没有"章"的概念，只有 section/item 的浅层嵌套。

**分类是由完整 id 集合严格判定的**（不掺 scope）：对每棵树，扫一遍所有 id，看是否命中上面两组正则/结构标记，
命中情况的四种组合（都不中/只中 cs408/只中 math1/都中）穷举了所有可能，无遗漏区间。

**识别不明确时**：两个标记都命中 → 判 ambiguous → `TreeShapeError` → 整体 `exit=1`（走 `failures` 列表，
不是 `exit=2` 的 contract 层错误）。**这条行为未变**，只是判断依据从"scope 过滤后的 chapter id 集合"
换成了"全体 id 集合"，[实测：见下方 ambiguous 探针，两个真实树的 `chapter-01`/`ch01`
子树拼在一起，`exit=1`，报错文案里明确写出"ambiguous"]。

**不确定项**：如果未来出现第 4 种真实形态（比如 id 里带纯数字章节号、不满足现有任何一条正则），
它会被兜底判成 `structure`（因为两个正标记都不中）而不是报错。这是**静默分类**，
不是**静默降级**（原缺陷是"标记会被数据改写而消失"，这个是"新形态没有专属正则")——
两者性质不同但都值得注意。我不确定这是否需要处理：底本没给出第 4 种真实形态的例子，
所以我不建议现在为假想形态加正则；如果以后出现，应该照本方案的模式（先定位它独有的 id 语法标记，
再补一对双向 `scope_signature_failures` 检查）。

---

## 4. 怎么证明修好了？（探针 + 哈希还原证明）

已在临时副本上验证（见文末"验证记录"完整命令与输出摘录）：

| 探针 | 构造 | 补丁前 | 补丁后 | 命中的真守卫 |
|---|---|---|---|---|
| cs408 P1 | 删光 24 个 `scope=chapter` 节点 | exit=0，PASS | **exit=1**，12+ 条 `section has no direct chapter-NN ancestor` | 既有的祖先存在性检查（原本因树形被误判为 structure 而从未跑到） |
| cs408 P3 | 24 个章节点 `scope: chapter→section`，id 不动 | exit=0，PASS | **exit=1**，24 条 `id matches the cs408 chapter-NN pattern but scope='section'` | 新增 `scope_signature_failures` |
| cs408 控制组 | 只删 1 个章节点 | exit=1（本就正确） | exit=1（不变，回归安全） | 原有检查 |
| math1 P1（本轮新补的对称探针，底本未测） | 删光 22 个 `scope=chapter` 节点 | 用旧代码测：会复现和 cs408 P1 一样的降级（未在底本中，但代码路径完全对称，可推断） | **exit=1**，`section has no ancestor node 'math1.xx.chNN.chapter'` | 既有祖先检查 + 新 math1 正标记（content/requirements 对） |
| math1 P3（同上，新补） | 22 个章节点 `scope: chapter→section` | 同上（推断会失守） | **exit=1**，22 条 `id matches the math1 '.chapter' pattern but scope='section'` | 新增 `scope_signature_failures` |
| math1 控制组（新补） | 只删 `math1.hs.ch01.chapter` 一个节点 | 未测 | exit=1，2 条 ancestor 缺失 | 原有检查，回归安全 |
| ambiguous（新补） | 拼接 cs408 一个章子树 + math1 一个章子树 成一棵"树" | — | **exit=1**，`ambiguous chapter tree: ...` | 新增 marker 冲突检测 |

**还原后有哈希证明**：所有探针都在 `tempfile.gettempdir()` 下的临时文件上跑，从未写回
`data/structured_materials/**`。每轮探针脚本运行前后都对源文件重新计算 SHA-256 并断言相等；
本次复测的两个源文件哈希：
- `cs408/knowledge_tree.yaml`：`a535394dafe21681...`（跑完 3 个探针后不变）
- `math1/knowledge_tree.yaml`：跑完 3 个探针后与探针脚本读取时的哈希一致（脚本内 `assert` 通过，无抛错）

**math1 P1/P3 "旧代码会失守"这一行是 [推断] 不是 [实测]**——我只在补丁后的代码上跑了 math1 探针，
没有额外去跑"未打补丁的 verify_tree.py + math1 mutation"这一组对照（底本也没提供）。
如果要把这行坐实为实测，需要额外跑一次：`py -3.12 tools/verify_tree.py <math1_P1_tmp.yaml>`，
预期 `tree shape: structure` 且 `ALL CHECKS PASSED`——我判断这是高置信推断（cs408/math1 两分支的
`infer_tree_shape` 代码结构完全对称，同一个 bug 模式），但没有把它变成实测证据，如实标注。

---

## 5. 会不会引入新的误报？

**[实测] 不会，四棵真实树补丁后仍全过**：

```
cs408/knowledge_tree.yaml            → exit=0, tree shape: cs408,     ALL CHECKS PASSED
cs408/knowledge_tree_multisource.yaml→ exit=0, tree shape: cs408,     ALL CHECKS PASSED
math1/knowledge_tree.yaml            → exit=0, tree shape: math1,     ALL CHECKS PASSED
eng1/knowledge_tree.yaml             → exit=0, tree shape: structure, ALL CHECKS PASSED
```

**为什么改动不会让 eng1 误报**：eng1 的 24 个 id 里没有一个匹配 `chapter-[0-9]{2}` 也没有一个以
`.chapter` 结尾（[实测]：对三棵树的 id 列表分别 grep `chapter-[0-9]{2}` 和 `\.chapter$`，
math1 里查无 `chapter-NN` 式 id，cs408 里查无 `.chapter` 式 id，eng1 两者都查无）。
三棵树的两组标记互不相交是现有事实，不是本次改动引入的假设。

**为什么改动不会让 cs408/math1 内部误报**：新增的 `scope_signature_failures` 只检查"id 语法"和"scope"
是否一致；在未被破坏的真实树里，两者本来就是一致的（这正是 round-31 让四棵树全过的前提），
所以补丁不会对干净树产生新的失败项——[实测确认，四棵树补丁后仍 `ALL CHECKS PASSED`]。

---

## 6. 明确不做

1. **不新增"形态 4"的猜测性正则。** 没有第 4 种真实树，不为假想形态预留分支（YAGNI；也避免把不存在
   的形态错误分类为某个已知形态）。
2. **不改 `SCOPE_RANK` / `subject_scope_failures` / provenance 检查等与本缺陷无关的逻辑。** 缺陷范围
   严格限定在"树形怎么推断"和"scope 是否与 id 语法一致"这两点。
3. **不放宽任何现有失败条件去将就某棵树。** 本次改动只新增失败信号（`scope_signature_failures`），
   对现有信号（祖先检查、去重、provenance）零改动。
4. **不处理"scope 标签内部再细分错误"（例如把 chapter 错标成 subject 而不是 section）之外的组合。**
   `scope_signature_failures` 目前只判"是不是 chapter"这一位；chapter 被错标成 item、item 被错标成
   section 等其它两两组合，理论上也可能被 `subject_scope_failures` 或 `SCOPE_RANK` 相关检查间接捕获，
   但**我没有逐一探测这些组合**——这是本建议未覆盖、留给后续对抗性验证的面。
5. **不在本次改动里处理"contract 层（`ky.knowledge.knowledge_point`）本身信不信 scope 字段"的问题。**
   `verify_tree.py` 是这条 contract 之上的第二层检查，本次只动第二层。

---

## 附：最小代价评估

- 改动范围：`tools/verify_tree.py` 一个文件，`infer_tree_shape` 函数体重写（输入源从"scope 过滤后的
  chapter id 列表"换成"全体 id 列表"，正则不变），新增 `scope_signature_failures` 一个函数
  （约 25 行）+ `main()` 里一行调用。**不改数据文件，不改 contract 模块，不改测试之外的任何其它文件。**
- 新增失败信号：2 组（cs408 双向、math1 双向），复用已有正则常量 `CS408_CHAPTER_RE`。
- 已跑通全部既有单测前置条件（四棵真实树 exit=0）；**未跑 `unittest discover -s tests -q` 全量**——
  这是我的建议里明确的空白：正式落地前应补跑一次全量单测确认没有依赖旧 `infer_tree_shape` 签名的测试
  （我通读了 `verify_tree.py`，未在其它文件里发现调用点，但没有全仓 grep 确认零调用点，[推断]非[实测]）。

---

## 验证记录（本人独立复现，命令与输出摘录）

复现环境：`F:\workspace\kaoyan-ai-system`，Python 3.12（`py -3.12`），全部读写发生在
`%TEMP%\kaoyan-probe-claude\` 与系统临时目录下的一次性 yaml 文件，源文件从未被写入。

1. **补丁前复现底本 P1/P3/控制组**（与底本第 2 节数字一致）：
   - P1（删光 24 个 cs408 章节点）：`exit=0`，`tree shape: structure`，`ALL CHECKS PASSED`
   - P3（24 个章节点 scope 改 section，id 不动）：`exit=0`，`tree shape: structure`，`ALL CHECKS PASSED`
   - 控制组（只删 `cs408.ds.chapter-01`）：`exit=1`，命中 `section has no direct chapter-NN ancestor`
   - 复跑后 `cs408/knowledge_tree.yaml` 哈希前后一致（`a535394dafe21681...`），未改动源文件

2. **补丁后重跑同一组探针**（`verify_tree_patched.py`，逻辑见本文件第 1/2 节）：
   - cs408 P1 → `exit=1`（新增：12+ 条祖先缺失）
   - cs408 P3 → `exit=1`（新增：24 条 `id matches ... but scope='section'`）
   - cs408 控制组 → `exit=1`（不变，回归安全）
   - math1 P1（新补探针）→ `exit=1`
   - math1 P3（新补探针）→ `exit=1`
   - math1 控制组（新补探针）→ `exit=1`
   - 四棵真实树（cs408 基线/多源、math1、eng1）→ 全部 `exit=0`，`ALL CHECKS PASSED`
   - ambiguous 拼接探针（cs408 一个章子树 + math1 一个章子树）→ `exit=1`，
     `tree shape: ambiguous chapter tree: both cs408 chapter-NN/section-NN ids and math1 .chapter/.content+.requirements ids are present`
   - 全程对 `cs408/knowledge_tree.yaml`、`math1/knowledge_tree.yaml` 做了修改前后 SHA-256 断言，
     两者均一致，探针脚本本身在断言失败时会抛异常（未抛出）
