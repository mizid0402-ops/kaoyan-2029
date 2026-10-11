# Round 49 任务书：WP-B′4 tools 去写死路径（M5/M6 校验器 + M21 PPT 生产线）

你是实现者（续同一会话）。先重读仓库根 `AGENTS.md`：D7 可读性、数据增长（不写数据量 / 科目 / 年份字面量）、编码规则（不要用 here-string 管道写中文）都适用。
这些 PPT 工具是 **408 专用适配器**（D6：科目专用的采集 / 内容脚本不需要通用化），只做路径迁移与非生效标注，不要泛化到其他科目。依据：`contracts/workspace.md` §2.3（内嵌路径相对 `Workspace.root`）、§2.4（补充视图消费规则 2、3）、§3、D1。
两个子模块分开处理，报告里也分两节。

## A. M5/M6：读生效数据的流水线工具

- `tools/verify_408_index.py`（第 118 行附近按约定拼 `knowledge_tree.yaml`、另读台账与索引）和 `tools/classify_questions.py`（第 38 行 `TREE`）：
  改为从注册表取生效树、台账、真题索引清单（`reference.exam_indexes`，不再 glob 目录）；加 `--workspace` 参数；原有显式参数仍覆盖。
  内嵌资料路径相对 `workspace.root` 解析。
- 验收：`py -3.12 tools/verify_408_index.py` 仍输出 `ALL INDEX FILES VERIFIED`；`tests/test_exam_index.py` 等现有测试不回归。

## B. M21：408 讲解 PPT 生产线（5 个写死 `F:\workspace\kaoyan-ai-system` 的工具）

`tools/build_408_deck_scaffold.py`、`tools/extract_408_questions_from_html.py`、`tools/extract_408_question_text.py`、`tools/extract_cs408_bundle.py`、`tools/verify_408_question_extraction.py`：

1. 删除 `Path(r"F:\workspace\kaoyan-ai-system")`，改为 `load_workspace(...)`（加 `--workspace`）：
   资料层用 `materials.raw_root`，PPT 工作目录用 `products.cs408_lecture_workspace`（`require`），真题索引用 `reference.exam_indexes["cs408"]`。
2. `extract_cs408_bundle.py` 读的是补充视图（410 树 + 附表）：改为从 `supplementary.cs408_multisource.files.{tree,agreement}` 取；
   **导出的 `tree_flat.csv` 增加 `is_effective` 列**（该 ID 是否在注册表 cs408 生效树中）和 `view_name` 列；导出元数据写明补充视图名与 `description`（规格 §2.4 规则 2、3）。
3. `build_408_deck_scaffold.py`：遇到 `is_effective = false` 的节点，讲解单元里必须带可见标注（例如标题后缀"【补充：非当年考纲，legacy_only_pending】"），不得与生效节点无差别列出。
4. 这些工具的输出目录 `review/408知识点树与真题/` 被 gitignore；**不要实际运行会覆盖该目录内容的构建**。
   用临时工作区（注册表 + 最小树/附表/索引样本）写测试，证明：路径来自注册表、`is_effective` 列正确、7 个 legacy 节点被标注。放在 `tests/test_cs408_lecture_pipeline.py`。
   如果某个工具是纯一次性抽取、无法在无原始资料时测试，就只做路径迁移 + `--help` 能运行的冒烟测试，并在报告里说明。

## 不做的

- 不改 `data/` 与 `review/408知识点树与真题/` 下任何文件；不动其他 `ROOT = Path(__file__).parents[1]` 形式的工具（它们可移植，归档与分层是 WP-G）。

## 验收

1. `grep -rn "F:\\\\workspace\|F:/workspace" tools/*.py` 无结果。
2. `py -3.12 tools/verify_408_index.py` → `ALL INDEX FILES VERIFIED`。
3. 新增测试与 `tests.test_exam_index` 全绿；全量**不跑**（按仓库根 `AGENTS.md`，由决策者提交前统一跑）。

## 产物

不要提交。报告：`review/rounds/round-49-wp-b4-tools-luna.md`。
