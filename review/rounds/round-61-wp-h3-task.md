# 任务书：WP-H3 卷面登记与出题单位（M5 真题索引 + M5′ 卷面形状，决议 D5 / D6）

先读仓库根 `AGENTS.md`（常驻规则，与本任务书冲突时以它的"验证范围"为准），再读：
`docs/阶段2.5-接缝收口.md` §七 D5 / D6 与 H3 行、`docs/模块地图.md` M5 / M5′ 行、`contracts/workspace.md`。

## 为什么做

2027 年真题约 2026-12 出现。现在加一年真题要改代码：`ky/exam/paper_shape.py` 的 `SHAPES` 常量写死每年卷面，
未知年份 `KeyError`；`tools/verify_408_index.py` 还写死了 math1 = 22 题、eng1 = 52 题的题型分段、
`ENUMS["subject_id"] = {cs408, math1, eng1}`、`subject in {"cs408", "math1"}` 的 A–D 规则、`if subject == "cs408"` 的分支。
另外，数学专业课等**各校自命题**的卷子同一科目不同学校不同，索引没有"出题单位"维度（D6）。

目标：**加一年 / 加一个出题单位的卷子 = 放索引文件 + 在卷面登记里加一段 + 注册表登记一行，不改代码。**

## 决策者已定的设计（照做；有更好的写法先在报告里提，不要自行改设计）

### 1. 卷面登记是数据文件，按科目登记（M5′，新端口 `contracts/paper_shape.md`）

- 注册表新增可选键 `reference.paper_shapes`：映射 科目 → 文件(F)，键 ⊆ `subjects`，未登记 = 该科暂无卷面登记。
  改 `contracts/workspace.md` §2.1 字段表与示例、`ky/workspace.py`、`tests/contract/test_workspace.py`（加这个键的正例与"未声明科目"负例）。
- 文件放 `data/paper_shapes/<科目>.yaml`（不要放进 `data/exam_questions/`，那里是索引目录）。本包建 `cs408.yaml`、`math1.yaml`、`eng1.yaml` 并登记。
- 格式（YAML，未知键一律拒绝并带路径，重复键 fail-closed——用项目已有的严格加载器，不要自己写）：

```yaml
schema_version: 1
kind: paper_shapes
subject_id: cs408
papers:
  - exam_year: 2024
    paper_source: national          # national 或出题单位代码 ^[a-z][a-z0-9]*$（如 xidian）
    question_count: 47
    sections:                       # 按题号连续覆盖 1..question_count，不重叠、不留空
      - numbers: [1, 40]
        question_type: single_choice
        marks_each: 2               # 可选：本段每题分值
        answer_letters: ABCD        # 可选：本段选择题答案只能取这些字母
      - numbers: [41, 47]
        question_type: comprehensive_application
        marks: {41: 13, 42: 10, 43: 13, 44: 10, 45: 7, 46: 8, 47: 9}   # 可选：逐题读到的分值
    answer_reader: csgraduates_quiz_dom   # 可选：独立重读答案的读取器名（见 §3）
    basis: "READ from ... "               # 必填、非空：这些数字怎么来的
```

- 段的分值三种写法**至多选一**：`marks_each`（整段同分）/ `marks` 映射（键必须恰好是本段题号）/ `marks: unverified`（来源有争议，索引里这些题的分值必须为 null）；都不写 = 卷面登记不约束分值。
- 同一文件内 `(exam_year, paper_source)` 不得重复；`subject_id` 必须等于它在注册表里登记的科目。
- 数值从现有来源**原样搬**，`basis` 原文照搬 `paper_shape.py` 里的英文说明（2023–2026 四年 cs408）。
  math1（2023–2026）与 eng1（2024–2026）只登记题量与题型分段（即校验器里现有的写死规则），**不要编分值**；
  它们的 `basis` 如实写"搬自 `tools/verify_408_index.py` 在 `924fb0e` 的写死规则（22 = 10 选择 + 6 填空 + 6 解答 / 52 = 40 + 5 + 5 + 2）"之类。
  cs408 的 `answer_letters: ABCD` 与 math1 选择段的 `answer_letters: ABCD` 同样是现有规则搬过来的。
- `ky/exam/paper_shape.py` 改为这份文件的加载器（模块头按 AGENTS.md 写明 M5′ 与规格），对外接口例如
  `load_paper_shapes(path, *, subject_id) -> PaperShapes`，`PaperShapes.get(exam_year, paper_source)` 找不到时抛 `ContractError`。
  **删除** `SHAPES` / `SHAPE_20xx` / `shape_for` 常量与函数，不留别名。

### 2. 索引加 `paper_source`（M5，新端口 `contracts/exam_index.md`）

- 把 `tools/verify_408_index.py` 现有的索引格式规则（允许键、枚举、禁止自由文本、`notes` 必须为 null、权重分布规则、来源哈希……）
  写成与语言无关的规格 `contracts/exam_index.md`；**规格只描述现有规则 + 本包新增的规则**，不借机放宽任何一条。
- 顶层新增可选键 `paper_source`：缺省 = `national`（现有 11 份索引都是统考，**不改这 11 份数据文件**）。
- `question_id` 必须等于：统考 `<科目>-<年份>-<两位题号>`；自命题 `<科目>-<出题单位>-<年份>-<两位题号>`。
  条目的 `subject_id` / `exam_year` 必须等于顶层。先核对现有 11 份是否全部满足；**有不满足的，停下来在报告里列出，不改数据**。
- 其余字段不变。

### 3. 校验器按注册表 + 卷面登记校验（`tools/verify_408_index.py`）

- 文件名与 CLI 用法不变（测试、变异工具、`apply_knowledge_weights.py` 都引用它；改名留给 WP-G）。模块头 docstring 更新为 M5、两份规格。
- 去掉所有写死的科目：`subject_id` 的合法值 = 注册表科目；A–D 规则、题量、题型分段、分值、总分全部来自该索引对应的卷面登记
  `(科目, exam_year, paper_source)`。**注册表没给该科登记卷面文件，或文件里没有这一卷 → 报问题（FAIL），不是跳过。**
- 答案独立重读：卷面登记写了 `answer_reader` 时，按名字从校验器里一个小的读取器表（目前只有 `csgraduates_quiz_dom` → 现有 `extract_408_answers`）
  取读取器，读索引 `provenance.answer` 指向的登记文件；读出的题号集合必须等于带 `answer_letters` 的段的题号集合，逐题比对。
  未知读取器名 → 报问题。没写 `answer_reader` → 不重读（math1 / eng1 现状）。
- 已有的检查语义**不得变弱**：对现有 11 份索引，新旧校验器都应 `ALL INDEX FILES VERIFIED`；
  `py -3.12 tools/mutation_test_408_index.py` 与 `py -3.12 tools/mutation_test_knowledge_weights.py` 的每个变异仍被检出（报告里贴两者的汇总行）。

### 4. `tools/build_408_index_v2.py`

它 import 了 `shape_for`。改为经注册表读 `reference.paper_shapes.cs408`。按 `AGENTS.md` 11–12 条：
用 `git show 924fb0e:tools/build_408_index_v2.py`（**固定哈希，不要用 HEAD**）与新版在同一份临时输出目录上各跑 `--year 2023/2024/2025/2026`（`--out` 指向系统临时目录），
逐字节比较输出，把结果写进报告（缺原始资料跑不了就如实写，不要伪造）。**不要覆盖 `data/exam_questions/` 下的文件。**

## 不做的

- 不改 11 份索引数据文件、不改 `topic_weights.json`、不改知识树。
- 不给投影加 `paper_source` 列（`question_id` 已能区分；列留给后续包，写进报告"建议"）。不改 `ky/projection/`。
- 不改 M24（`ky/review/check_questions.py`）、不改 `tools/classify_questions.py`（若发现它们也写死了科目或卷面，列进报告）。
- 不给校验器改名、不挪到 `ky/` 里。
- 不做 H4（大纲多版本）、H5（权重流水线）。

## 测试（只写这些）

1. `tests/contract/test_paper_shape_port.py`（新）：加载器正例；负例各一条——未知键、段重叠、段留空 / 超出题量、
   `(年份, 出题单位)` 重复、`basis` 为空、`marks` 映射键与段题号不符、一段同时写两种分值、`subject_id` 与登记科目不符、非法出题单位代码。
2. `tests/contract/test_exam_index_port.py`（新）：在**临时工作区**里（照 `tests/contract/test_subject_onboarding.py` 的做法复制注册表与所需文件）：
   - **D5 验收**：复制一份现有 cs408 索引改成 2027 年（改年份与 `question_id`，provenance 保持可校验），在临时卷面文件里加 2027 一段并登记 → 校验通过；再用 `ky.projection` 建投影，2027 的题进了投影。**不改任何代码**。
   - **D6 验收**：同法造一份 `paper_source: xidian` 的卷子（`question_id` 带出题单位）+ 对应卷面段 → 通过；`question_id` 缺出题单位 → 失败。
   - 负例：卷面登记里没有这一卷 → 失败；科目没登记卷面文件 → 失败；题型与段不符 → 失败；`marks: unverified` 的段给了分值 → 失败；未知 `answer_reader` → 失败。
   - 期望值从注册表与被登记文件推导，**不写数据量字面量**（AGENTS.md 第 7 条）。
3. `tests/contract/test_workspace.py`：`reference.paper_shapes` 的正例与未声明科目负例。

## 验收（只跑这些模块 / 命令）

```
py -3.12 -m unittest tests.contract.test_paper_shape_port tests.contract.test_exam_index_port tests.contract.test_workspace tests.test_exam_index tests.contract.test_subject_onboarding tests.contract.test_projection_port tests.contract.test_check_questions_port tests.test_data_manifest
py -3.12 tools/verify_408_index.py
py -3.12 tools/mutation_test_408_index.py
py -3.12 tools/mutation_test_knowledge_weights.py
```

另外：`docs/模块地图.md` 的 M5、M5′ 两行改为指向两份新规格与新契约测试、可替换性与验收命令；§4 缺口表里 WP-H3 那行改写为剩余缺口（投影未单列 `paper_source` 等）。

## 报告

写到 `review/rounds/round-61-wp-h3-luna.md`：改了哪些文件、每条设计的落点、现有 11 份索引的 `question_id` 核对结果、
新旧校验器与两个变异工具的输出汇总、`build_408_index_v2.py` 逐字节对照结果、建议。
写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。含中文的文件写完查 `???`。
