# 任务书：WP-H4a 大纲多版本登记 + 版本映射端口（M0 / M4，决议 D5）

先读仓库根 `AGENTS.md`，再读 `docs/阶段2.5-接缝收口.md` §七 D5 与 H4 行、`docs/模块地图.md` M0 / M4 行、
`contracts/workspace.md`（尤其 §2.4 补充视图、§2.5 科目档案）、`contracts/knowledge_tree.md`。

你在一个独立的 git worktree 里工作（派发时的工作目录），主工作区另有人在改真题索引校验器，与你的文件不重叠。
worktree 里没有 gitignore 的 `data/raw_materials/`；本包不需要它，若某个点名测试因此失败，如实写进报告，不要自己建链接。

## 为什么做

考研大纲每年可能变（新增、删除、拆分、改名知识点）。现在注册表每科只能登记一棵生效树，
补充视图 `cross_year_tree` 还假设"补充树 ⊇ 生效树"——新大纲删掉节点时这条不成立，无法同时登记新旧两版，
也就无法把复习队列里旧版的知识点 ID 迁到新版（那是 H4b 的事，本包只把端口立起来）。

目标：**新一年大纲到手 = 放新树文件 + 写一份版本映射 + 注册表登记两行 + 把生效指针指过去；不改代码。**

## 决策者已定的设计（照做；有更好的写法先在报告里提，不要自行改设计）

### 1. 注册表：新增可选键 `reference.syllabus_versions`（M0）

```yaml
reference:
  knowledge_trees:
    cs408: data/structured_materials/cs408/knowledge_tree.yaml     # 生效树：含义与消费方都不变
  syllabus_versions:                                               # 可选；键 ⊆ subjects
    cs408:
      versions:                                                    # 版本标签 → 树文件(F)
        "2026": data/structured_materials/cs408/knowledge_tree.yaml
      mappings: []                                                 # 版本映射文件(F)列表
```

- `knowledge_trees.<科目>` **保持现状**（所有消费方不改）。某科登记了 `syllabus_versions` 时，加载器检查：
  该科的 `knowledge_trees` 路径必须**等于** `versions` 里的某一个路径（这就是"生效指针指向其一"；换生效版本 = 改 `knowledge_trees` 那一行）。
  不等 → `ContractError`，路径 `reference.knowledge_trees.<科目>`。
- 版本标签是字符串，匹配 `^[0-9]{4}$`（大纲年份）。YAML 里写成带引号的字符串；写成整数 → `ContractError`（不做隐式转换）。
- `Workspace` 暴露 `syllabus_versions: Mapping[str, SyllabusVersions]`（每科：`versions: Mapping[str, Path]`、`mappings: tuple[Path, ...]`），
  并提供 `effective_version(subject) -> str | None`（有登记时返回生效树对应的版本标签，未登记返回 None）。
- `require()` 能取 `reference.syllabus_versions.<科目>.versions.<标签>`；映射文件用 `require_all`-式的接口或同样的键风格（照 `exam_indexes` 的做法，选一种写进规格）。
- 本仓库注册表为 cs408、math1、eng1 各登记当前唯一版本 `"2026"`，`mappings: []`（先核对三棵树确实都是 2026 大纲；
  若有一棵不是，在报告里写明并按它的真实年份登记，**不要**猜）。

### 2. 版本映射文件（新端口 `contracts/syllabus_mapping.md`，M4 的一部分）

```yaml
schema_version: 1
kind: syllabus_mapping
subject_id: cs408
from_version: "2026"
to_version: "2027"
basis: "对照 2026 / 2027 两版大纲逐章比对；…"     # 必填非空
changes:                                          # 只列变化；两版都有、没列出的 ID = 原样保留
  - {from: cs408.ds.chapter-02.section-01, to: [cs408.ds.chapter-02.section-01, cs408.ds.chapter-02.section-04]}   # 拆分
  - {from: cs408.os.chapter-05.section-03, to: [cs408.os.chapter-05.section-02]}   # 合并 / 改名
  - {from: cs408.cn.chapter-01.section-06, to: []}                                 # 删除
added: [cs408.co.chapter-03.section-07]           # 新版新增、没有来源的节点
```

规则（加载 + 校验，全部 fail-closed，带字段路径）：
- 未知键拒绝、重复键拒绝（用项目已有的严格 YAML 加载器）；`from_version` ≠ `to_version`，两者都必须是该科已登记的版本。
- `changes[].from` 必须是旧树里的 ID，且在 `changes` 里只出现一次；`to` 里每个 ID 必须在新树里。
- 旧树里**不在**新树里的 ID，必须出现在某条 `changes.from` 里（否则报"未声明的删除 / 改名"）。
- 新树里**不在**旧树里的 ID，必须要么是某条 `changes.to` 的目标，要么在 `added` 里；两处都出现 → 报错。
- `added` 里的 ID 必须在新树、不在旧树。
- 对外接口（Python）：`load_syllabus_mapping(path, workspace) -> SyllabusMapping`，
  `SyllabusMapping.targets(old_id) -> tuple[str, ...]`（原样保留的返回 `(old_id,)`；删除的返回 `()`）。
  树的读取走 `ky.knowledge.knowledge_point.load_knowledge_points`（知识树端口），不自己 `yaml.safe_load` 树文件。
- 实现放新模块 `ky/knowledge/syllabus_mapping.py`（模块头按 AGENTS.md 写明模块与规格）。
- 注册表加载器**不**读取映射内容（`contracts/workspace.md` §1："只登记路径，不校验被登记文件的内容"）；内容校验由上面的加载器做。

### 3. 与现有补充视图的关系

- `supplementary.cs408_multisource`（`cross_year_tree`，⊇ 假设）**保持不变**，它描述的是"同一批节点的跨年来源"，与版本映射是两件事。
  在 `contracts/workspace.md` §2.4 加一句：跨大纲版本的增删改由 `syllabus_versions` + 版本映射表达，`cross_year_tree` 只用于"生效树的超集"视图。
- `tools/verify_tree.py` 的"已登记"判定（`_registered_subject`）加上 `syllabus_versions` 里登记的树，这样新版本树登记后可直接按科目档案校验。

## 不做的

- **不迁移复习队列**、不加参照完整性检查、不改 `ky/storage/`（那是 H4b）。
- 不改任何知识树数据文件，不新建 2027 树（仓库里没有 2027 大纲）；测试里的新版本树在临时目录里造。
- 不改投影（`ky/projection/`）、不改快照。
- 不改 `tools/verify_408_index.py`、`ky/exam/`、`contracts/exam_index.md`、`contracts/paper_shape.md`（另一个包在改）。

## 测试（只写这些）

1. `tests/contract/test_syllabus_mapping_port.py`（新）：在临时工作区造两棵小树（照 `tests/contract/test_subject_onboarding.py` 的做法造合法树），登记两个版本 + 一份映射：
   正例（保留 / 拆分 / 合并 / 删除 / 新增各至少一处，`targets()` 结果逐一断言）；
   负例各一条，断言具体错误子串：未声明的删除、新节点既没来源也不在 `added`、`added` 与 `changes.to` 重复、`from` 重复、`to` 不在新树、版本未登记、`from_version == to_version`、未知键。
2. `tests/contract/test_workspace.py`：`syllabus_versions` 正例；生效路径不在 `versions` 里 → 失败；整数版本标签 → 失败；未声明科目 → 失败。
3. `tools/verify_tree.py` 识别 `syllabus_versions` 里登记的树：在已有的 verify_tree 测试模块里加一条（先 `rg` 找到它），不另开模块。
不写数据量字面量（AGENTS.md 第 7 条）。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_syllabus_mapping_port tests.contract.test_workspace tests.contract.test_knowledge_tree_port tests.contract.test_subject_onboarding
py -3.12 -m unittest <你加 verify_tree 测试的那个模块>
py -3.12 tools/verify_tree.py data/structured_materials/cs408/knowledge_tree.yaml
```

另：`docs/模块地图.md` 的 M0、M4 两行补上新键与新规格、新契约测试；§4 缺口表"补充视图假设"那行改写为剩余缺口（复习队列迁移与参照完整性 → H4b）。

## 报告

写到 `review/rounds/round-66-wp-h4a-luna.md`（在你的 worktree 里）：改了哪些文件、每条设计的落点、三棵树的大纲年份核对结果、验收输出、建议。
写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。含中文的文件写完查 `???`。
