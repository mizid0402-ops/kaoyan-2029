# 细则审查（只审规则，不审实现）：WP-G2b `tools/` 分层（C2）

遵守 `AGENTS.md`（"决策者细则先审再实现"；不跑全量；严重度按威胁模型）。本轮**没有实现**，请只审下面的规则与分类本身：
与 C2 原意是否一致、是否会破坏日常使用（重跑管线、测试、文档里的命令）、边界与反例。可在 `git archive 0c3b3e5` 上做只读探针。

## 背景

`docs/模块拆分与架构审查.md` C2：`tools/` 近 60 个脚本混杂（可复跑管线 / 一次性迁移 / 轮次脚本），无"重建流水线"定义；数据目录里放 `.py`。
建议是拆成 `tools/pipeline/`、`tools/migrations/`、`tools/archive/round-NN/`，并描述"原始资料 → 树 → 索引 → 权重 → 投影"的重建顺序。

决策者实测的约束：
- 51 个脚本用 `Path(__file__).resolve().parents[1]` 之类求仓库根；挪进子目录就指错。
- 多个脚本把**自己的路径写进产物**（`build_math1_tree.py`、`build_eng1_tree.py` 写进树文件头；`round24_build_weighted_tree.py` 写 `"generator"`；`build_408_deck_scaffold.py` 写 HTML 注释；`render_weight_manual.py` 在说明书里写 `aggregate_topic_weights.py` 的命令）。挪动它们会让重跑的产物与现有数据不再逐字节一致（`AGENTS.md` 11）。
- 测试以 `from tools.x import`、`sys.path.insert(ROOT/"tools")`、`ROOT/"tools/verify_tree.py"`、`git show <哈希>:tools/x.py` 引用约 20 个脚本；README、`docs/`、说明书里有大量 `py -3.12 tools/x.py` 命令。
- `data/structured_materials/cs408/` 下有两个已跟踪的 `.py`（`audit_round6.py`、`generate_tree_round6.py`）。

## 决策者拟定的规则（请审）

R1. **管线脚本不挪**，留在 `tools/` 顶层、文件名不变——保住文档命令、测试导入与写进产物的生成器路径。"管线" = 数据增长（新年份真题、新大纲、新一批打标、词汇、讲解）时还要重跑的构建 / 校验 / 变异测试脚本。
R2. **一次性迁移**（已执行、不再重跑）挪到 `tools/migrations/`；**历史探针 / 审计 / 轮次脚本**挪到 `tools/archive/`（不再按轮次分子目录，文件名本身已带轮次）。挪动用 `git mv`（保历史）。
R3. 被挪动的脚本**仍须能从新位置运行**：只改求仓库根的那一行（`parents[1]` → `parents[2]`）与 docstring 里的用法路径；**产物里写的生成器路径不改**（它记录的是当时生成数据的脚本，属历史事实）。被挪脚本的输出（在同一临时输入上）与挪动前逐字节一致，唯一允许的差异是 docstring 用法行。
R4. 被测试引用的脚本若属迁移 / 历史，测试随之改导入路径；`git show <固定哈希>:tools/x.py` 形式的基线**不改**（旧提交里就是旧路径）。
R5. 新增 `tools/README.md`：三类清单（每个脚本一行：做什么、属哪个模块 M 编号、何时运行），以及**重建顺序**（原始资料 → 树 → 索引 → 权重 → 投影 → 讲解，每步写命令与"什么时候需要重跑"）。不做 `ky rebuild` / Makefile（本轮只写清顺序；自动化等管线端口稳定后另议）。
R6. `data/structured_materials/cs408/*.py` 挪到 `tools/archive/`（它们是第 6 轮生成与审计 408 树的脚本），同 R3。
R7. `tools/dispatch/`（派发脚本）、`tools/__pycache__` 不动。

## 拟定分类（请逐条挑错）

**管线（不挪）**：`aggregate_topic_weights`、`apply_knowledge_weights`、`render_weight_manual`、`classify_questions`（M6）；`verify_408_index`、`build_408_index_v2`、`build_408_index`（v2 是否仍依赖 v1？请核）、`build_exam_indexes`（M5）；
`verify_tree`、`tree_source_support`、`build_math1_tree`、`build_eng1_tree`、`round22_extract`、`round24_build_weighted_tree`、`round24_validate_weighted_tree`、`round29_build_tree_split`、`round29_quote_locate`、`round29_validate_agreement`（M4 树与 408 多源树）；
`daily_words`、`build_eng1_vocabulary`、`verify_eng1_vocabulary`、`import_netem_source`、`verify_netem_source`、`netem_cross_validate`（M7 词汇）；
`build_408_deck_scaffold`、`extract_cs408_bundle`、`extract_408_question_text`、`extract_408_questions_from_html`、`verify_408_question_extraction`（M21 讲解）；
`fetch_evidence`（取证抓取）；`mutation_test_408_index`、`mutation_test_knowledge_weights`、`mutation_test_suite`、`mutation_test_verify_tree`（变异测试）。

**迁移（→ `tools/migrations/`）**：`migrate_vocab_delivery`（用户决定旧 15 条不迁移，脚本保留待归档）、`apply_round2_fixes`、`fix_eng1_provenance`、`register_round2_sources`、`register_408_source`、`register_408_quiz_pages`、`remove_408_reprints`、`restore_408_papers`。

**历史（→ `tools/archive/`）**：`audit_attachment`、`build_evidence_bundle`、`verify_evidence_bundle`、`verify_round3_findings`、`inspect_repos`、`list_tree_vocab`、`probe_exam_pdf`、`probe_outline`、`probe_pdf_text`、`probe_quiz_page`、`render_pdf_pages`、`render_staged_page`、`extract_exam_skeleton`、`round22_format`、`round22_probe`、`round22_verify`，以及 R6 的两个。

## 请重点查

1. 分类有没有放错：尤其"迁移 / 历史"里有没有其实还会重跑的（例如新年份真题登记是否要用 `register_408_source` / `probe_pdf_text` / `render_pdf_pages` / `extract_exam_skeleton`；2027 年真题约 2026-12 出现）；"管线"里有没有其实已被取代的（`build_408_index` v1）。
2. 被挪脚本之间、以及管线脚本对它们的导入（例如管线脚本 import 了某个将被挪走的脚本）。
3. R1 "管线不挪" 是否偏离 C2 太多；如果你认为应该连管线一起挪进 `tools/pipeline/`，给出如何处理生成器路径与文档命令的方案。
4. R3 的"逐字节对照"对不再能重跑的历史脚本（依赖已删除的缓存或联网）如何验收——建议的最低验收。

产物：`review/rounds/round-128-g2b-rules-sol-out.md`：逐条"同意 / 修改（给出改法）/ 反对（给出理由与反例）"，最后给出你建议的最终规则与分类。只写这一个文件。
