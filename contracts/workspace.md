# 端口规格：工作区注册表 `kaoyan.workspace.yaml`（schema_version 2）

> 阶段 2.5 WP-B。决策依据：`docs/阶段2.5-接缝收口.md` D1、D2。
> 本文件是**与实现语言无关**的规格；Python 实现是 `ky/workspace.py`，契约测试是 `tests/contract/test_workspace.py`。
> 任何替换实现（别的语言、别的加载器）只要满足本文件就能接上。
> 审阅：gpt-6-sol 第 44 轮（`review/rounds/round-44-workspace-spec-codex.md`），采纳与否见 §9。

## 1. 职责

回答一个问题：**"当前生效的某份文件在哪里？"**

- 注册表提供各模块的**默认数据源**。消费方迁移后（WP-B′），不得再用 `Path(__file__).parents[…]`、盘符绝对路径或约定式拼接来定位**登记在本文件里的**数据。
- **显式参数仍可覆盖**：CLI 已有的 `--config`、`--items`、`--vocab-db`、`--ledger`、`--out` 等保持可用，优先级见 §3.2。迁移不得删除既有 CLI 用法。
- "换一棵树 / 换一个词库 / 换目录" = 放入新文件 → 过该端口的校验 → 改本文件一行 → 重建投影。**不改代码。**
- 它**只登记路径**，不读取、不校验被登记文件的内容（那是各自端口的事）。

## 2. 文件格式

UTF-8 YAML，顶层是映射。

> 下例是 schema_version 1 的写法；**当前版本为 2**，唯一差别是 `subjects` 改为科目档案映射，见 §2.5。其余字段两版相同。

```yaml
schema_version: 1

subjects: [math1, eng1, cs408, politics]      # 本工作区启用的考试科目

reference:                                     # 参考数据：冻结，可整体替换
  knowledge_trees:                             # 每科"生效范围"树；键 ⊆ subjects；未登记 = 该科暂无树（合法）
    math1: data/structured_materials/math1/knowledge_tree.yaml
    eng1:  data/structured_materials/eng1/knowledge_tree.yaml
    cs408: data/structured_materials/cs408/knowledge_tree.yaml
  syllabus_versions:                           # 可选；键 ⊆ subjects
    cs408:
      versions:                                # 年份标签 → 树文件
        "2026": data/structured_materials/cs408/knowledge_tree.yaml
      mappings: []                             # 版本映射文件列表
  exam_indexes:                                # 生效的真题索引，逐个文件登记；键 ⊆ subjects
    cs408: [data/exam_questions/408_index_2023.json, data/exam_questions/408_index_2024.json,
            data/exam_questions/408_index_2025.json, data/exam_questions/408_index_2026.json]
    math1: [data/exam_questions/math1_index_2023.json, data/exam_questions/math1_index_2024.json,
            data/exam_questions/math1_index_2025.json, data/exam_questions/math1_index_2026.json]
    eng1:  [data/exam_questions/eng1_index_2024.json, data/exam_questions/eng1_index_2025.json,
            data/exam_questions/eng1_index_2026.json]
  paper_shapes:                                # 卷面登记；键 ⊆ subjects；未登记 = 该科暂无卷面登记
    cs408: data/paper_shapes/cs408.yaml
    math1: data/paper_shapes/math1.yaml
    eng1: data/paper_shapes/eng1.yaml
  # timetable_schools:                         # 可选；M18 学校作息档案（个人数据，通常写在本地补充文件，§2.6）
  #   example_school: data/personal/schools/example_school.yaml
  topic_weights:  data/review_weights/topic_weights.json
  weight_batches: data/review_weights/batches.yaml  # 可选；M6 题→知识点批次清单
  vocabulary_db:  data/english_vocabulary/eng1_vocabulary.sqlite
  ledger:         data/materials.yaml

supplementary:                                 # 补充视图：可选；不属于"生效范围"
  cs408_multisource:
    kind: cross_year_tree
    subject: cs408
    description: 403 生效节点的 2022 大纲补充来源 + 7 个 legacy_only_pending 旧节点；附表为跨年来源支持
    files:
      tree:      data/structured_materials/cs408/knowledge_tree_multisource.yaml
      agreement: data/structured_materials/cs408/knowledge_tree_agreement.yaml

materials:                                     # 资料层根目录（被 gitignore，可按台账重取）
  raw_root: data/raw_materials

products:                                      # 独立内容子系统的工作目录（可选）
  cs408_lecture_workspace: review/408知识点树与真题

settings:                                      # 可选；用户编辑的设置文件
  # exam_config: data/kaoyan_config.yaml       # 尚无正式配置，暂不登记

state:                                         # 学习状态真相源：由写入方创建，加载时可以不存在
  review_queue: data/review_queue
  plans:        data/plans
  # availability: data/personal/availability.yaml         # 可选，M26；个人数据，写在本地补充文件（§2.6）
  # routes:       data/routes                               # 可选，WP-E 启用
  # timetable:    data/personal/timetable.yaml              # 可选，M18；个人数据，写在本地补充文件（§2.6）

staging: staging                               # AI 产物先落这里（WP-E 启用）
projection: data/projections/kaoyan_projection.sqlite
```

### 2.1 字段表

"类型"一列的 **F** = 必须是文件、**D** = 必须是目录；这决定 `require()` 的类型检查。

| 路径 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `schema_version` | 整数（非布尔） | 是 | 只接受 `2`（见 §2.5） |
| `subjects` | 非空字符串列表 | 是 | 每项匹配 `^[a-z][a-z0-9]*$`，不得重复 |
| `reference.knowledge_trees` | 映射 科目→路径(F) | 是 | 键 ∈ `subjects`；可为空映射；若该科登记多版本，生效路径必须等于其某个 `versions` 路径 |
| `reference.syllabus_versions` | 映射 科目→版本记录 | 否 | 键 ∈ `subjects`；未登记 = 无多版本档案 |
| `reference.syllabus_versions.<科目>.versions` | 映射 年份标签→路径(F) | 是 | 至少一版；标签必须是引号包围的四位数字字符串；同科各标签不得共用路径 |
| `reference.syllabus_versions.<科目>.mappings` | 路径(F) 列表 | 否 | 缺省为空列表；只登记文件位置，不读取文件内容 |
| `reference.exam_indexes` | 映射 科目→非空路径列表(F) | 是 | 键 ∈ `subjects`；同一路径不得出现两次（跨科目也不行） |
| `reference.paper_shapes` | 映射 科目→路径(F) | 否 | 键 ∈ `subjects`；未登记 = 该科暂无卷面登记 |
| `reference.timetable_schools` | 映射 学校 ID→路径(F) | 否 | ID 匹配 `^[a-z][a-z0-9_]*$`；未登记 = 空映射 |
| `reference.topic_weights` | 路径(F) | 是 | |
| `reference.weight_batches` | 路径(F) | 否 | 未登记 = 暂无题→知识点聚合批次清单 |
| `reference.vocabulary_db` | 路径(F) | 是 | |
| `reference.ledger` | 路径(F) | 是 | |
| `supplementary` | 映射 名称→视图 | 否 | 缺省 = 空；名称匹配 `^[a-z][a-z0-9_]*$` |
| `supplementary.<名>.kind` | 枚举 | 是 | 见 §2.4 |
| `supplementary.<名>.subject` | 字符串 | 是 | ∈ `subjects` |
| `supplementary.<名>.description` | 非空字符串 | 是 | 下游展示时如实标注用 |
| `supplementary.<名>.files` | 映射 角色→路径(F) | 是 | 角色集合必须**恰好等于** kind 规定的角色 |
| `materials.raw_root` | 路径(D) | 是 | |
| `products` | 映射 名称→路径(D) | 否 | 名称匹配 `^[a-z][a-z0-9_]*$` |
| `settings.exam_config` | 路径(F) | 否 | |
| `settings.pacing` | 路径(F) | 否 | M28 周期设置；个人文件通常通过 §2.6 本地补充注册 |
| `state.review_queue` | 路径(D) | 是 | `ReviewShardStore` 根目录 |
| `state.plans` | 路径(D) | 是 | `DayPlanStore` 根目录 |
| `state.availability` | 路径(F) | 否 | 登记即必须存在，格式见 `contracts/availability.md` |
| `state.routes` | 路径(D) | 否 | |
| `state.timetable` | 路径(F) | 否 | 登记即必须存在；格式见 `contracts/timetable.md` |
| `state.question_bank` | 路径(D) | 否 | M31 改编题库目录（个人数据，写在本地补充文件）；格式见 `contracts/question_bank.md` §3 |
| `staging` | 路径(D) | 是 | |
| `projection` | 路径(F) | 是 | 投影 SQLite 输出文件 |

- **未知字段一律拒绝**（任何层级），错误带字段路径，例如 `reference.vocab_db: unknown field`。
- **重复键一律拒绝**（任何层级；YAML 默认"后者覆盖"会静默丢值）。
- 顶层不是映射、字段类型不符（例如路径写成数字、`subjects` 写成字符串）→ 违约，带字段路径。
- 错误**文案**不属于规格（不同实现可不同）；**字段路径**属于规格，契约测试断言它（精确相等，列表项带 `[index]`）。
- 无法定位到字段的错误（YAML 语法错误、非 UTF-8）字段路径为**空串**，即文件级错误。
- 路径去重按所在文件系统的同一文件语义：Windows 上大小写不同的两个写法视为同一路径。

### 2.2 路径语法（被登记路径）

一个被登记路径是满足下列全部条件的字符串，否则违约：

1. 非空；分段以 `/` 分隔；**不得含 `\`**（因此 UNC 路径也被拒绝）。
2. 不以 `/` 开头；不含 `:`（拒绝 `C:/x`、`C:x` 等一切盘符写法）。
3. 每一段非空（拒绝 `a//b`、尾部 `/`），且不是 `.` 或 `..`。
4. 不做 `~`、环境变量展开。

解析：**相对于注册表文件所在目录**（`Workspace.root`），不相对于当前工作目录。
注册表文件**自身**的位置（`--workspace` / `KY_WORKSPACE` 的值）不受本节约束，可以是绝对路径。

> v1 刻意要求工作区自包含，以便整体拷贝、克隆后照常工作。把状态放到另一块盘、临时替换词库等需求，
> 用 §3.2 的显式参数覆盖满足；"授权外部根"留到 schema_version 2 再设计。

### 2.3 被登记文件里的内嵌路径

台账、知识树 `sources[].path`、真题索引里记录的资料路径（如 `data/raw_materials/…`）一律**相对于 `Workspace.root`** 解析。
本端口不校验它们；它们所属的端口按此根解析。

### 2.4 补充视图的 kind

| kind | 必需角色（恰好这些） | 语义 |
|---|---|---|
| `cross_year_tree` | `tree`、`agreement` | `tree` 是 `subject` 生效树的**超集**（生效 ID ⊆ 补充 ID），多出的节点是非当年生效的旧年节点；`agreement` 是**对 `tree` 的**逐节点注记 |

跨大纲版本的增删改由 `reference.syllabus_versions` 和版本映射文件表达；`cross_year_tree` 只用于生效树的超集视图，表示同一批节点的跨年来源，不承担版本迁移。

消费方必须遵守（加载器不检查，由消费方的契约测试守护，WP-B′）：

1. `agreement` 的属性（`source_support`、`source_count`、`evidence_tag` 等）**只能**挂在补充视图自己的读模型上，**不得**拼接到生效树的节点上——两者来源数不同（本仓库 403 个共同节点中 380 个不同）。
2. 生效读模型只含生效树的节点；补充视图多出的节点必须能被机器识别为"补充、非当年生效"（例如带视图名与 `is_effective = false`）。
3. 展示补充数据时必须同时给出视图名与 `description`。

### 2.5 科目档案（schema_version 2，WP-H2，决议 D6）

schema_version 2 把 `subjects` 从 ID 列表改为 **科目档案映射**，让"加一个科目 / 一个考研方向"只改数据：

```yaml
schema_version: 2
subjects:
  math1:    {name: 数学一, tree_grammar: named_chapters}
  eng1:     {name: 英语一, tree_grammar: flat, features: [vocabulary]}
  cs408:    {name: 计算机学科专业基础, tree_grammar: numbered_chapters, domain_segment: true}
  politics: {name: 思想政治理论}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `subjects.<id>` | 映射 | — | 键 = 科目 ID，匹配 `^[a-z][a-z0-9]*$`（如 `agri314`、`mathanalysis`）；至少一科 |
| `.name` | 非空字符串 | 是 | 展示名 |
| `.tree_grammar` | 枚举 | 该科在 `reference.knowledge_trees` 登记了树时必填 | 知识点 ID 的层级 / 编号语法，取值见下表 |
| `.domain_segment` | 布尔 | 否（缺省 false） | 为 true 时，ID 第二段是该科的"分域"（如 cs408 的 ds/co/os/cn），投影单列 `domain`，不当作科目 |
| `.features` | 字符串列表 | 否（缺省空） | 可选模块开关：`vocabulary`（英语词汇通道）、`weighted_mastery`（M30 掌握度按 `reference.topic_weights` 加权，`contracts/mastery.md` §4）。未知值 → 违约 |

**树语法是代码提供的策略，科目档案只做选择**（拼图原则 D7：新科目若能用现有语法，只改数据；需要新语法时新增一个策略模块，不改已有的）：

| `tree_grammar` | 章节 ID 规则 | 现用于 |
|---|---|---|
| `numbered_chapters` | `<科目>.<分域>.chapter-NN`，节 `….section-NN` | cs408 |
| `named_chapters` | 章节 ID 以 `.chapter` 结尾；**每章必须有** `<章>.content` 与 `<章>.requirements` 两个 scope=section 子节点（考试内容 / 考试要求）；节必须有对应的 `.chapter` 祖先 | math1 |
| `flat` | 无章节语法约束（只校验层级与 scope） | eng1 |

策略实现集中在 `ky/knowledge/tree_grammar.py`（从 `tools/verify_tree.py` 移出），`verify_tree` 按注册表的科目档案选语法，**不再有写死的科目表**。

> 各语法的**完整**约束以 `ky/knowledge/tree_grammar.py` 为准；新科目复用某语法前先对照它，章节后缀相符不代表其余约束也相符（sol 第 52 轮）。

**消费方（WP-H2 一并迁移）**：
- 台账（M2）：资料的 `subject_id` 必须 ∈ 注册表科目 ∪ 台账自有分类 `{general}`；`ky ledger` 加 `--workspace`。
- 树校验（M4）：`tools/verify_tree.py` 按档案选语法；树根命名空间必须等于该树登记的科目 ID。
- 投影（M15）：`domain` 列只对 `domain_segment: true` 的科目取 ID 第二段，删掉 cs408 特判。
- 词汇通道：只在含 `features: [vocabulary]` 的科目下启用（快照的 `vocab` 段在没有此类科目时为 null）。

schema_version 1 的注册表不再接受（本仓库只有一份注册表，随 H2 一起升级）。

### 2.6 本地补充文件 `kaoyan.workspace.local.yaml`（个人数据登记，不进 git）

> 用户 2026-09-30："git 只提交不敏感信息"；"现有的 git 仓库只上传整个项目的骨架"，学习记录与课表只在本机。
> 主注册表进 git，所以它不能登记会暴露个人信息的键（例如用户学校的档案），也不能登记克隆后必然缺失的个人文件。

- **位置**：与主注册表同目录、固定文件名 `kaoyan.workspace.local.yaml`（`--workspace` / `KY_WORKSPACE` 指向别处的注册表时，看那个注册表所在目录）。
  不存在 = 没有本地登记，加载结果与只有主注册表时完全相同。存在但无效 → 违约（fail-closed，与 §3.1 同理），字段路径前缀 `local.`。
- **格式**：UTF-8 YAML 映射，`schema_version` 精确为 1，其余只允许下面这些键，**写法与主注册表相同的嵌套结构**
  （例如顶层 `state:` 下写 `timetable:`；未知键、重复键拒绝）：

  | 路径 | 类型 | 说明 |
  |---|---|---|
  | `reference.timetable_schools` | 映射 学校 ID → 路径(F) | 同 §2.1 |
  | `settings.exam_config`、`settings.pacing` | 路径(F) | 同 §2.1 |
  | `state.availability` | 路径(F) | 同 §2.1 |
  | `state.timetable` | 路径(F) | 同 §2.1 |
  | `state.question_bank` | 路径(D) | 同 §2.1 |

- **只增不改**：本地文件里出现的任一键（对映射键是整个键，如 `reference.timetable_schools`）若主注册表也登记了 → 违约，路径 `local.<键>`。
  不合并映射、不覆盖，避免同一键两处都写时说不清以谁为准。
- 路径语法同 §2.2，**相对 `Workspace.root`**（主注册表所在目录）解析；登记后的行为（`require`、`write_target`、缺失策略）与写在主注册表里完全相同。
- **指纹**：`Workspace.sha256` 仍只是主注册表原始字节的哈希；新增 `Workspace.local_sha256: str | None`（本地文件原始字节的 SHA-256，无文件为 `None`）。
- 仓库惯例：个人文件放 `data/personal/`（已 gitignore）；学习状态目录 `state.review_queue` / `state.plans` / `state.routes` 与 `staging`
  的**路径**可以写在主注册表（路径本身不含个人信息），但目录内容已 gitignore。
- 测试不得依赖本机是否有本地补充文件：用临时工作区的测试不受影响；读仓库根注册表并需要真实个人文件的测试，缺文件时 skip 并写明恢复方法。

## 3. 如何找到本文件

### 3.1 发现

按优先级，**命中即停，失败不回退**：

1. 显式参数（CLI：`ky <子命令> … --workspace <path>`；Python：`load_workspace(path)`）。相对路径相对当前工作目录。
2. 环境变量 `KY_WORKSPACE`（空字符串视为未设置）。相对路径相对当前工作目录。
3. 从当前工作目录**向上逐级**查找名为 `kaoyan.workspace.yaml` 的文件，**最近者优先**。

第 1、2 步给出的文件不存在或不合法 → 直接违约，并说明来源（`--workspace` / `KY_WORKSPACE`），**不得**继续向上查找。
三步都没有 → 违约：`kaoyan.workspace.yaml not found (searched upward from <cwd>; set --workspace or KY_WORKSPACE)`。

### 3.2 与既有显式参数的优先级（消费方迁移时遵守）

对任何一个数据源：**该数据源的显式 CLI 参数 > 注册表**。例如 `ky snapshot --vocab-db X` 用 X，不传则用 `reference.vocabulary_db`。
一条命令的全部数据源都由显式参数给出时，该命令**不要求**注册表存在（保证旧用法与现有测试不被破坏）。
`day-plan submit|record`、`month-close` 的显式 `--store` 覆盖 `state.plans`；未给 `--store`
时使用 `write_target("state.plans")`。`preflight`、`snapshot` 的显式 `--items` 覆盖
`state.review_queue`；未给 `--items` 时使用注册表中的 `state.review_queue`。这些默认值需要
注册表，可通过 `--workspace` 选择。没有显式参数且没有可发现的注册表时属于契约错误，错误
应提示补对应的 `--store` / `--items` 或 `--workspace`。
`ky ledger --ledger X --root Y` 未提供 `--subjects` 或 `--workspace` 时，先按 §3.1
从 cwd 向上发现注册表，再从台账文件所在目录向上发现；找到后使用注册表科目。两处都
找不到时必须报错，并提示补 `--subjects` 或 `--workspace`，不得跳过科目校验。

## 4. 存在性

- **加载只校验格式与路径语法，不检查被登记物是否存在**；加载是纯读，不创建目录、不写文件。
- 写入目标通过 `write_target(key)` 获取：只接受 `state.review_queue`、`state.plans`、
  `state.availability`、`state.routes`、`state.timetable`、`state.question_bank`、`staging`、`projection`。未登记（含可选键未填）报
  `not registered`；目标路径经 `resolve(strict=False)` 跟随已存在部分的符号链接 / junction 后，
  若落在 `Workspace.root` 外则报 `resolves outside the workspace`。该方法不要求目标存在，
  不创建目录或文件；目标已存在时还会按 §2.1 的 F / D 类型校验，类型不符报
  `expected a file` 或 `expected a directory`，错误路径为登记键。
- 需要某个被登记物时，调用 `require(key)`。它区分四种情况，均为违约且带登记键：
  1. 键未登记（含可选键未填、`knowledge_trees` 里没有该科）→ `not registered`；
  2. 路径不存在 → `registered file does not exist: <解析后路径>`；
  3. 类型错（F 字段指向目录或反之）→ `expected a file` / `expected a directory`；
  4. 解析后的真实路径（跟随符号链接 / junction）落在 `Workspace.root` 之外 → `resolves outside the workspace`。
- **缺失策略由消费方定义**，并写进消费方的规格：
  - 快照：未登记树的科目显示"无树"（合法）；已登记但缺失 → 违约。
  - 投影、索引校验器：任一登记输入缺失 → 违约；**不得**静默跳过后产出"成功"的投影。
  - 测试：缺失的是 gitignore 的资料层文件时可以 skip 并提示；**生产运行不得以 skip 代替失败**。
- `state.*`、`staging`、`projection` 是写入目标，由写入方负责创建，不走 `require`。

## 5. 输入指纹

加载结果带 `sha256`：**注册表文件原始字节**的 SHA-256（不做换行归一——同内容 LF 与 CRLF 哈希不同，这是有意的，与 C3 的字节口径一致）。
被登记文件各自的哈希由消费它们的端口记录（例如投影记录"实际读取的每个文件"的哈希）。

## 6. Python 接口（`ky/workspace.py`）

```python
WORKSPACE_FILENAME = "kaoyan.workspace.yaml"
WORKSPACE_ENV = "KY_WORKSPACE"

@dataclass(frozen=True)
class SupplementaryView:
    name: str
    kind: str
    subject: str
    description: str
    files: Mapping[str, Path]            # 只读；已解析的绝对路径

@dataclass(frozen=True)
class SyllabusVersions:
    versions: Mapping[str, Path]          # 只读；年份标签 → 树文件
    mappings: tuple[Path, ...]            # 版本映射文件

@dataclass(frozen=True)
class Workspace:
    source: Path                          # 注册表文件的绝对路径
    root: Path                            # source.parent
    sha256: str
    subjects: tuple[str, ...]
    knowledge_trees: Mapping[str, Path]
    syllabus_versions: Mapping[str, SyllabusVersions]
    exam_indexes: Mapping[str, tuple[Path, ...]]
    topic_weights: Path
    timetable_schools: Mapping[str, Path]       # 只读；学校 ID → 档案文件
    weight_batches: Path | None
    vocabulary_db: Path
    ledger: Path
    supplementary: Mapping[str, SupplementaryView]
    raw_root: Path
    products: Mapping[str, Path]
    exam_config: Path | None
    review_queue: Path
    plans: Path
    availability: Path | None
    routes: Path | None
    timetable: Path | None
    staging: Path
    projection: Path
    local_sha256: str | None                    # §2.6 本地补充文件原始字节的哈希；无文件为 None

    def require(self, key: str) -> Path: ...
    # key 为点路径（单个路径字段）：'reference.vocabulary_db'、'reference.knowledge_trees.cs408'、
    # 'supplementary.cs408_multisource.files.tree'、'products.cs408_lecture_workspace'。

    def require_all(self, key: str) -> tuple[Path, ...]: ...
    # 用于列表字段（'reference.exam_indexes.cs408'、
    # 'reference.syllabus_versions.cs408.mappings'）：逐个检查，全部通过才返回。
    # 对非列表字段调用 → 违约；对列表字段调用 require() → 违约。

    def effective_version(self, subject: str) -> str | None: ...
    # 有版本登记时返回与 knowledge_trees[subject] 路径相等的标签；否则 None。

同一科目下，两个版本标签不得指向同一路径：大纲未变化时不新增标签；唯一的树路径使
`effective_version(subject)` 不受 YAML 标签顺序影响。

def find_workspace(start: Path | None = None, *, explicit: str | Path | None = None) -> Path: ...
def load_workspace(path: str | Path | None = None) -> Workspace: ...
```

- 所有错误抛 `ky.models.ContractError`（带字段路径），CLI 据此输出 `contract violation: …` 并 exit 2。
- **所有**映射字段只读，包括嵌套的 `SupplementaryView.files`；列表字段用元组。
- 路径对象为绝对路径，但不做 `resolve()`（不跟随链接）；越界检查只在 `require` 时做。

## 7. 契约测试（替换实现必须通过）

`tests/contract/test_workspace.py`，以"加载函数"为参数（`LOADERS`），对当前实现跑一遍；替换者注册自己的实现再跑一遍。
每个拒绝用例断言**字段路径**，不断言文案。

1. **仓库注册表**：根目录的 `kaoyan.workspace.yaml` 能加载；`knowledge_trees['cs408']` 指向 403 版（D1）；`exam_indexes` 恰好登记 11 个文件，与 `data/exam_questions/*.json` 一致；每个 `require`/`require_all` 在本仓库都通过。
2. **解析基准**：同一份注册表复制到临时目录，解析结果随之移动；从子目录调用时仍相对注册表所在目录。
3. **结构拒绝**：顶层非映射；未知字段（顶层、`reference` 内、补充视图内各一例）；重复键（顶层与嵌套各一例）；`schema_version` 为 `2`、为 `true`、缺失；`subjects` 为空、为字符串、含重复、含非法 ID；`knowledge_trees`/`exam_indexes` 的键不在 `subjects`；`exam_indexes` 某科为空列表、同一路径登记两次；补充视图 `kind` 未知、`subject` 不在 `subjects`、缺 `agreement` 角色、多出角色；路径字段为数字。
4. **路径语法拒绝**：`/abs`、`C:/x`、`C:x`、`\\\\server\\share`、`a\\b`、`a/../b`、`./a`、`a//b`、`a/`、空串。
5. **存在性**：加载不要求任何被登记物存在；`require` 分别报出未登记（含 politics 无树）、不存在、类型错（F 指向目录、D 指向文件）、链接越界（能建符号链接/junction 的平台上测，否则 skip 并说明）；`require_all` 在列表中有一个缺失时失败；对列表/非列表字段调用错接口失败。
6. **发现**：显式参数 > `KY_WORKSPACE` > 向上查找；显式参数指向缺失文件时报错且**不回退**；`KY_WORKSPACE` 同理；`KY_WORKSPACE=""` 视为未设置；相对的显式值与环境值相对 cwd；嵌套目录各有一份注册表时取最近者；都没有时报错。
7. **指纹**：`sha256` 等于原始字节的 SHA-256；同内容 LF 与 CRLF 两份文件哈希不同。
8. **纯读与不可变**：加载前后临时工作区目录树逐字节不变（不创建 `state`/`staging`）；修改 `knowledge_trees`、`exam_indexes`、`supplementary[...].files`、`products` 均抛异常。

**替换演练**（WP-B′ 各消费方的契约测试，不在 WP-B）：在临时工作区里把生效树 / 词库 / 索引文件换到另一相对路径，快照、投影、索引校验器、题目分类器各自读到新路径；生效点数 = 生效树节点数，补充视图多出的节点不进生效读模型；附表属性只出现在补充读模型；PPT 导出携带非生效标记。

## 8. 不在本端口范围

- 各被登记文件的**内容**校验（树契约、索引、权重、词库视图、补充视图的超集关系）。
- 考试配置 `kaoyan_config.yaml` 的内容；它的 `subjects[].subject_id` 应 ⊆ 本文件 `subjects`，该交叉检查在消费方迁移时加。
- 台账 `SUBJECT_IDS`（含资料分类 `general`）、投影里的 cs408 特判等既有枚举：本文件定义"本工作区启用哪些考试科目"，**不会**因为新增本文件就让这些枚举自动消失；它们的收敛在各自模块的 WP 中处理。
- CLI 的 `--workspace` 参数：随 WP-B′ 各消费方迁移时逐个加，WP-B 不改 CLI。

## 9. 审阅记录（第 44 轮，gpt-6-sol）

| 意见 | 处理 |
|---|---|
| 索引只登记目录，多放一个 JSON 就会改变投影 | **采纳**：改为 `exam_indexes` 逐文件登记 |
| 工具读取的资料层、PPT 工作目录未登记；内嵌路径以何为根 | **采纳**：加 `materials.raw_root`、`products`；§2.3 规定内嵌路径相对 `Workspace.root` |
| "只从这里取路径"与显式 CLI 参数矛盾 | **采纳**：§1、§3.2 改为"注册表给默认，显式参数覆盖" |
| 预留 `availability`、`routes`；考试配置入口 | **采纳**：均为可选键 |
| "subjects 唯一定义处"表述过强 | **采纳**：改为"本工作区启用的考试科目"，§8 说明既有枚举不自动消失 |
| 路径语法不全（反斜杠、`C:x`、UNC、`.`、尾部 `/`）；文件/目录类型 | **采纳**：§2.2 重写，字段表标 F/D |
| 外部根 / 独立状态盘 | **部分采纳**：v1 保持自包含，用显式参数覆盖；外部根留 v2 |
| 符号链接 / junction 越界 | **采纳**：`require` 检查真实路径 |
| 缺失策略须由消费方定义，生产不得 skip | **采纳**：§4 |
| 显式来源失败不回退、空环境变量、最近者优先、`--workspace` 语法 | **采纳**：§3.1 |
| WP-B 不让旧 CLI 立即强制发现 | **采纳**：§3.2、§8 |
| 补充视图需要机器契约；禁止把附表拼到生效树；PPT 标注是下游验收 | **采纳**：§2.4 |
| 契约测试补边界、嵌套不可变、替换演练 | **采纳**：§7 |
| LF/CRLF 哈希断言 | **采纳**：§5、§7.7 |
