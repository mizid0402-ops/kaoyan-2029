# 任务：修复 408 索引验证器 + 把三科题目索引做到可交付

## 你的角色

你是**实现者**。另一个 agent（DSH）负责验证你的产出，它不复用你的验证工具，会自己另写探针从源文件字节重新推导。
所以要按"可被独立复现"的标准来写，而不是"跑绿就行"。

## 项目背景

项目根目录：`F:\workspace\kaoyan-ai-system`
- Python 必须用 `py -3.12`（本机 `py` 启动器不回显输出）
- 终端会吞中文：**结果写进 UTF-8 文件再用 read 工具读**，不要靠控制台回显判断
- 不要执行 git

### 项目铁律（违反即返工）

1. **索引只含元信息**：年份/题号/题型/分值/答案字母/页码行号/来源哈希。
   **题干、选项、解析原文一律不得写入任何文件。** 现有 `content_policy` 字段与
   `tools/verify_408_index.py` 的 schema 白名单都在强制这一点。
2. **不得把"推出来的数"和"读出来的数"混在一起**。这是本项目最关键的一条，见下面 §已知缺陷。
3. 来源必须登记进 `data/materials.yaml` 并 pin sha256；`load_ledger` 要能通过完整性校验。
4. 每个结论要能区分「我实测到了」与「我推断」。

## 当前状态（DSH 已实测，直接采信，不要重复劳动）

### 已完成并在仓库里
- `ky/exam/paper_shape.py` — **新建**，按年份记录 408 卷型（题量/选择题数/综合题分值），
  每条带 `basis` 说明数字是读来的还是推来的。
- `data/raw_materials/cs408/quiz_pages/cs408_quiz_{2023,2024,2025,2026}.html` — 已登记为
  `cs408-quiz-pages-2023-2026`，四个 sha256 见台账 notes。
- `tools/build_408_index_v2.py` — **新建**，从 quiz 页按 DOM 锚点提答案 + 从 `paper_shape` 取分值。
  已成功构建 2024：47 题、总分 150、40/40 答案。
- `tools/verify_408_index.py` — 已被 DSH 改成按年份参数化，**但现在跑不起来**（见下）。

### ⚠️ 两个必须修的问题

**问题 1：`tools/verify_408_index.py` 报 `ModuleNotFoundError: No module named 'ky'`**

该文件顶部原本有 `sys.path.insert(0, str(ROOT))`，DSH 在函数体内新增了
`from ky.ledger import load_ledger` 与 `from ky.exam.paper_shape import shape_for`，
但脚本直接运行时 `sys.path` 里没有项目根。请修好导入路径（放进函数内联 import 之前，
或把 import 提到模块顶部并确保 ROOT 已在 sys.path）。

**问题 2：`tests/test_exam_index.py` 2 条失败**

- `test_hashes_match_the_registered_bytes` 断言 `PAPER`/`ANSWER` 两个**旧的 2024 第三方 PDF**
  的 sha256 等于索引 `provenance.*.sha256`。但 2024 索引现在改用
  `cs408-quiz-pages-2023-2026` 作为答案来源，`provenance.answer.sha256` 已是 quiz 页的哈希。
  这条测试的**意图**是"索引记录的哈希 = 磁盘上被登记文件的哈希"，请按新来源改写，
  而不是把断言删掉了事。同样检查 `test_ledger_keeps_the_source_weak_and_unstructurable`
  是否还成立（它检查的是 2024 rebuild / answer scan 两条台账行，那两条仍在台账里，应仍成立）。

## ⚠️ 已知缺陷（DSH 实测发现，这是本次任务的存在理由）

原 `tools/build_408_index.py` 把综合题 70 分**平均摊派**成每道 10 分，注释里也承认是
`derived by rule, not read off a page`。DSH 把卷子渲染出来逐页读了，**实测值是**：

| 年 | 41 | 42 | 43 | 44 | 45 | 46 | 47 | 合计 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2024 | **13** | 10 | **13** | 10 | 7 | 8 | 9 | 70 |
| 2025 | 13 | 10 | 12 | 9 | 8 | 9 | 9 | 70 |

即 41 和 43 是 13 分、42 和 44 是 10 分，**不是每道 10 分**。
2024/2025 均已从卷面逐题读出并已写入 `ky/exam/paper_shape.py`。

**2026 不可采信**：`cs408_quiz_2026.html` 标的 `本题满分` 自相矛盾——
Q41 标 13 但小分 4+8=12；Q44 标 15 但小分 1+2+4+2=9；Q47 无小分；
标称合计 72 → 全卷 80+72=152，超出官方 150 分。**2026 的卷子不在手上**，
所以 `paper_shape.py` 里 2026 的 `essay_marks` 是 `None`，`build_408_index_v2.py`
遇到 `None` 会拒绝构建。**不要为了让它跑通而编一组数字填进去。**

**2023 同样未读**：`essay_marks=None`。2023 卷的扫描件在
`data/raw_materials/cs408/past_papers/408_2023_paper.pdf`（8 页，无文本层，纯图）。
本机**没有 OCR**（无 tesseract/poppler），但已装 `pypdfium2`，可以把页面渲染成 PNG
再用视觉读取。DSH 已用这个方法读出 2024/2025。

## 你要交付什么

### 第一优先：修好上面两个问题，让 `188 tests OK` 且 `verify_408_index.py` 通过

### 第二优先：把三科题目索引做到"可交付"

交付物 = 每年的 `data/exam_questions/` 下的索引 JSON，字段沿用现有 schema
（如果需要扩展字段，**先改 `verify_408_index.py` 的白名单并说明理由**）。

**408**（`subject_id: cs408`）
- 2024：已完成，只需保证测试通过。
- 2025：卷面综合题分值已读出（见上表）。请渲染
  `data/raw_materials/cs408/past_papers/408_2025_paper.pdf` 核对，
  确认 DSH 读的 13/10/12/9/8/9/9 无误，然后构建索引。
- 2023：渲染 `408_2023_paper.pdf`，**逐页读出**综合题分值并写进 `paper_shape.py`，再构建。
- 2026：卷子不在手上。**不要编数字。** 保持 `None`，在报告里写明缺什么才能补。

**数学一**（`subject_id: math1`，需新增 subject_id 到验证器枚举）
- 每年 22–23 题：选择题 10 + 填空题 6 + 解答题 7。
- 文本源已在 `%TEMP%\kaoyan-probe\verify\`：
  `math1_2023_qihang.pdf`、`math1_2024_kmf.pdf`、`math1_2024_ztbu.pdf`、
  `math1_2025_juying.pdf`、`math1_2025_ztbu.pdf`、`math1_2026_faiusr.pdf`、`math1_2026_kaoyan.pdf`
- 多源交叉：`math1_2025_ztbu`/`juying`/`2026_kaoyan` 题号 1–22 连续；
  `2023_qihang` 缺 21；`2024_kmf` 混入噪声 `0`。
- `【答案】` 标记数：`2024_ztbu` 与 `gh_2024_answer.md` 各 22 个（最全）；
  `2023_qihang`/`2025_*`/`2026_*` 各 16 个。
- **分值不要平均摊派**：从卷面读出。

**英语一**（`subject_id: eng1`）
- 文本源：`%TEMP%\kaoyan-probe\claude2\dl\bv_e1_{2024,2025,2026}.pdf`（14 页，原生文本层 31k–35k 字符）
  与 `lazy_e1_{2024,2025,2026}.pdf`（12 页，转排版）。
- 答案：`2026` 有（`codex2\eng1_2026_qihang.pdf` 有解析、`eng1_2026_static_answer.pdf` 有 45 个答案标记）；
  **2024/2025 的答案目前是缺的**，需要你去找并核实，找不到就如实写"缺"。

## 硬性要求

1. **每个分值、每个答案字母都要能追到出处**。索引里不要出现没有任何来源支撑的数字。
2. 拿不准的数字：写 `None` 并在报告里说明，**不要猜**。
3. 新来源要登记进台账（pin sha256，`load_ledger` 通过）。
4. 改任何被测代码后，`py -3.12 -m unittest discover -s tests -q` 必须全绿。
5. **写变异测试**证明你的新校验真的会红（改坏一个分值/一个答案字母，验证器必须报错），
   并在报告里给出变异前后文件哈希证明已还原。

## 报告

写入：`F:\workspace\kaoyan-ai-system\review\rounds\round-7-index-codex.md`

必须包含：
- §修了什么（逐条对应上面两个问题）
- §每年索引的构建结果（题量、总分、答案覆盖率）
- §**每一处分值的出处**（哪个文件哪一页读到的）
- §「我实测到的」vs「我推断的」分开列
- §**没有把握的地方**，至少 3 条，每条具体
- §变异测试结果 + 还原哈希

最后用一句话回复：改了哪些文件 + unittest 结果 + verify_408_index 结果 + 每年索引题量/总分 + 报告路径。
