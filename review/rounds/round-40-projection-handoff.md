# 交接：③ 只读 Web 投影（前一段由主控做了一半，交由你接手）

> 执行者：Codex（gpt-5.6-sol, high）。**主控审查。**
> 项目：`F:\workspace\kaoyan-ai-system`（已有 git，最新提交 `0e080b4`）

---

## 1. ③的目标

按项目阶段顺序（不可跳）：① 知识树与真题 ✅冻结 → ② 24 个月计划 ✅收尾 →
**③ 本机只读 Web 投影（SQLite 可重建投影）** ← 本任务。

**架构决策**：投影是**从文件可重建的**，服务是**只读的**。
`data/projections/*.sqlite` 是**派生物，不是真相源**；真相源仍是 `data/` 下的 YAML/JSON/词库。

---

## 2. 主控已经做完的部分（可采信，但请复核）

### 2.1 装了依赖

```
datasette    0.65.4   （sqlite-utils 一并装了）
```
**注意**：`sqlite_utils` 没有 `__version__` 属性（别用 `--version` 之类去判断它）。

### 2.2 新建了投影构建器

| 文件 | 作用 |
|---|---|
| `ky/projection/__init__.py` | `build_projection(out=DEFAULT_OUTPUT) -> dict` |
| `ky/projection/__main__.py` | `py -3.12 -m ky.projection [--out PATH] [--json]` |

**读入**（**只读，不写回**）：
- 三棵树：`cs408/knowledge_tree_multisource.yaml`、`math1/knowledge_tree.yaml`、`eng1/knowledge_tree.yaml`
- `cs408/knowledge_tree_agreement.yaml`（一致性附表）
- `data/exam_questions/*.json`（11 份索引）
- `data/review_weights/topic_weights.json`
- `data/english_vocabulary/eng1_vocabulary.sqlite`（**只取哈希记录，不导入其表**）

**产出**：`data/projections/kaoyan_projection.sqlite`（约 368 KB）

**表**：`knowledge_points`(503) / `exam_questions`(432) / `question_knowledge_weights`(1059) /
`topic_weights`(79) / `projection_meta`(10)
**视图**：`v_knowledge_points_by_subject` / `v_question_coverage`

**实测数字**：
```
kp_by_subject    {"cs408": 410, "eng1": 24, "math1": 69}   ← 与 config 的三科一致
kp_by_scope      {"chapter": 46, "item": 261, "section": 173, "subject": 23}
kp_by_tree_status {"extracted": 503}                        ← 如实，无一个 approved
q_by_year        {"2023": 69, "2024": 121, "2025": 121, "2026": 121}
权重行零孤儿     1059 条全部能对应到真实知识点
```

**确定性实测**：连续两次构建，**内容哈希完全相同**（`ef9e5a14…`）。
实现方式：所有表按稳定键排序写入；**刻意不写时间戳**（否则两次构建不一致）；
`projection_meta.inputs` 记录 17 个输入文件的 sha256。

### 2.3 主控自己修掉的两个错（你要知道，别再犯）

1. **`_subject_of` 一开始把 cs408 的 domain 段当科目**
   → `cs408.ds` / `cs408.co` / `cs408.os` / `cs408.cn` 被当成四个科目，
   投影与 config、与复习调度器都不一致。
   **修法**：`subject_id` 一律返回 `cs408`，domain 另存 `domain` 列。
   **已有回归测试锁死**（`test_cs408_domain_is_a_separate_column_not_a_subject`）。

2. **`v_question_coverage` 视图写错**
   → 它写 `COUNT(DISTINCT exam_year)`，但 `exam_year` 不在权重表上。
   **修法**：JOIN `exam_questions`。

### 2.4 新写了测试（**已写但未提交、未跑**）

`tests/test_projection.py`，5 个测试类：
`ProjectionShapeTest` / `TreeStatusHonestyTest` / `DeterminismTest` /
`MasterDataGapsStayVisibleTest`。

**你的第一件事就是跑它**：`py -3.12 -m unittest tests.test_projection -v`

---

## 3. 你要做的

### 3.1 先复核主控的产出（**不要默认它对**）

- 跑 `tests/test_projection.py`，有失败就修（**可能是测试写错，也可能实现有错，自己判断**）
- 独立复核 §2.2 那几个数字：**自己查一遍**，别信我转述
- 复核确定性声明：**自己连续构建两次、比对内容哈希**

### 3.2 补主控没做的部分

| # | 待办 | 说明 |
|---|---|---|
| **A** | **把只读服务做成可复现的一条命令** | 主控是手工跑的 `py -3.12 -m datasette <db> --port 8001`。要固化成一个**脚本或文档化命令**，并明确**必须只读**（datasette 默认允许写，要显式设成不可变：`--immutable` 或等价设置） |
| **B** | **验证"违规写入被拒"** | 黑盒：起服务 → 尝试经 HTTP 写 → **必须失败**。这是"只读"的**证据**，不是声明 |
| **C** | **把依赖写进 `pyproject.toml`** | 现在 `pyproject.toml` **没有声明任何 dependencies**。至少声明 `datasette`、`sqlite-utils`、`pyyaml`、`pypdf`（按实际 import 清点） |
| **D** | **补投影重建的自动化测试** | 已有 `DeterminismTest`，但要确保它在**全新环境**（删掉投影文件后）也能重建成功 |
| **E** | **说明 Windows 文件占用问题** | 主控实测：**datasette 运行时投影文件被锁，重建会 `PermissionError [WinError 32]`**。要在文档/脚本里写明"重建前先停服务"，或让构建器**写到临时文件再替换**并给出友好错误 |

### 3.3 完成标准（缺一不可）

| # | 标准 |
|---|---|
| 1 | `py -3.12 -m unittest discover -s tests -q` **全绿**（当前基线 **419**，加上 `test_projection.py` 后应更多） |
| 2 | `py -3.12 -m ky.projection` 可重建；**连续两次内容哈希相同** |
| 3 | 只读服务**一条命令可起**，且**实测经 HTTP 写入被拒** |
| 4 | 投影里 `kp_by_tree_status` **仍只有 `extracted`**（不得出现 `approved`） |
| 5 | 408 2026 的 7 题、数学一 2025 的 4 题 **`marks` 仍为 NULL**（**不得填猜测值**） |
| 6 | `pyproject.toml` 声明了依赖 |
| 7 | 变异测试：把"只读"改成可写 → 标准 3 必须变红 → 还原 → **给前后哈希** |
| 8 | **`data/` 下已有的树、索引、词库一个字节未改**（投影文件是新增，允许） |

### 3.4 报告

写 `review/rounds/round-40-projection-codex.md`，含：
1. 复核主控产出的结果（哪几条复现了、哪几条复现不出、哪几条你认为是错的）
2. 待办 A–E 各自怎么做的
3. 8 条标准的**实际输出**（原始命令 + 结果）
4. 变异测试结果 + 还原哈希
5. 起服务的**确切命令**与"如何确认它是只读的"
6. 「我实测到了」vs「我推断」
7. 没有把握的地方至少 3 条

---

## 4. 纪律

- **可改/可新建**：`ky/projection/**`、`tests/**`、`pyproject.toml`、`review/rounds/**`、
  `data/projections/**`（新增投影文件）、`docs/**`（若要写服务文档）
- **禁止改**：`data/structured_materials/**`、`data/exam_questions/**`、
  `data/review_weights/**`、`data/english_vocabulary/**`、`data/materials.yaml`、
  `tools/**`、`review/408知识点树与真题/**`
- **不许为了让测试通过而放宽验证**
- **不许把 NULL 的 marks 填成猜测值**
- 本机**没有 `rg`**，用 Glob/Grep 或 `Get-ChildItem -Recurse`
- 必须用 `py -3.12`
- 终端吞中文：结果写 UTF-8 文件再用 read 工具读
- **Windows 环境**：datasette 会把投影文件锁住；重建前先停服务
- **改完 `git add -A && git commit`**（不要 push）

最后用一句话回复：复核结果 + A–E 完成情况 + 8 条标准过了几条 + 测试数 + 提交哈希 + 报告路径。
