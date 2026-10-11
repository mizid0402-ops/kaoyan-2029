# Round 128 Codex：WP-G2b `tools/` 分层细则审查

只审规则与分类。依据固定提交 `0c3b3e5` 的脚本、测试、文档；在系统临时目录展开 `git archive` 后作静态检查，并只运行两条 argparse 探针。未搬文件、未重建产物、未联网、未跑测试或变异测试。该提交有顶层 `tools/*.py` 58 个、`data/structured_materials/cs408/*.py` 2 个。

## 一、R1–R7

| 规则 | 判断 | 证据、边界与改法 |
| --- | --- | --- |
| R1 管线不挪 | **修改** | 本轮不挪现有顶层入口是合理的兼容取舍：README 与 `docs/` 中至少 52 处 `tools/x.py` 路径命中，测试有 `from tools.x import`、`ROOT / "tools"`，现有产物又记生成器路径。可是这只完成 C2 的**职责清单**，没有完成原报告建议的物理 `tools/pipeline/`（`docs/模块拆分与架构审查.md:445-446`）；不要写成“物理拆分已完成”。顶层再标 `active`、`pinned_reproducer`、`validation`、`acquisition`：变异测试是质量门禁，不是数据构建步骤；`round22_extract`、round24/29 等只复现固定的 2022/2026 输入，不能声称能建新大纲。等端口和生成器身份稳定后再单独评估物理迁移。 |
| R2 迁移与历史目录 | **修改** | `tools/migrations/` 只放仍被认可的一次性状态变更；`migrate_vocab_delivery.py` 从未执行且用户已决定“不迁”旧 15 条，应放 `tools/archive/`，README 明写**禁止对真实状态执行 `--apply`**。其余七个固定旧来源/旧决议的迁移脚本可入 migrations；`register_408_source.py:42-69` 钉死 2024 来源，`register_408_quiz_pages.py:40` 钉死 2023–2026，不能当 2027 登记器。扁平 archive 在当前文件名集合无碰撞，可以接受。`git mv` 本身并不在 Git 对象里保存“重命名”元数据；提交后用 rename diff 与 `git log --follow` 检查可追溯性，不把“保历史”当作 `git mv` 自动保证。 |
| R3 搬后可运行、最小改动 | **修改** | “一律 `parents[1]→parents[2]`”不成立：`data/structured_materials/cs408/audit_round6.py:11` 与 `generate_tree_round6.py:12` 现在是 `parents[3]`；搬至 `tools/archive/` 应变 `[2]`，搬至 `tools/` 顶层应变 `[1]`。此外 `round22_format.py:7-8` 将**自身目录**放入 `sys.path` 并裸导入顶层 `round22_extract`，`round22_verify.py:9` 也裸导入它；两者入 archive 后不改导入就失败。规则应允许为运行所需的仓库根、导入路径、用法/错误提示作**最小、逐项列明**的修改。既有产物里的历史生成器路径保持原字节；归档脚本只供历史回放，不得以旧路径声明新生成的正式产物。不能跑的历史脚本不强行承诺逐字节通过，见下文最低验收。 |
| R4 测试引用 | **修改** | `tests/test_migrate_vocab_delivery.py:16` 直接导入将被搬的模块，须改到归档新位置；固定哈希的 `git show 旧提交:tools/x.py` 当然保持旧路径。还须扫描并处理**非测试**可执行命令及当前路径叙述，例如 `docs/阶段1交付说明.md:164` 的 `tools/verify_round3_findings.py`、`docs/阶段2-数学一英语一知识树.md:27-34` 的多个迁移/审计脚本、`docs/模块地图.md:65` 的词汇迁移路径。历史叙述可以保留旧路径并标“当时路径”，当前可执行命令应改新路径；不要全局替换产物中的 provenance。 |
| R5 `tools/README.md` 与重建顺序 | **修改** | 同意逐脚本清单与本轮不做 `ky rebuild`/Makefile，但每行还应标 `active/pinned/archived/retired`、输入来源、写入目标、可复跑范围及缺资源时的前提。所拟直线“原始资料→树→索引→权重→投影→讲解”会误导：M15 投影同时要求生效/补充树、agreement、索引、权重、词汇库及注册表（`contracts/projection.md:10-22`）；M21 的 `extract_cs408_bundle.py:270-301` 读补充树、agreement 与索引，**不依赖投影**，应画成并行分支。`fetch_evidence.py:1-16` 只抓到证据库，不会按台账重建 `data/raw_materials`。2027 卷的来源确认、台账/卷面形状/索引登记目前仍有人工作业，不得把现有脚本清单描述成完整自动重建。README 的命令须按明确的当前范围核对，尤其 v2 用法错误见下文。`tools/dispatch/` 单列为排除范围或附索引，不能与“每个脚本”相矛盾。 |
| R6 两个数据目录脚本都归档 | **修改** | `audit_round6.py` 是固定 2026 来源审计，可归档；但 `generate_tree_round6.py:13-14,154` 是当前生效 `cs408/knowledge_tree.yaml` 的**唯一现存生成脚本**。若也称“不再重跑”的 archive，R5 的现有 403 树重建步骤就没有正式入口。建议移至顶层 `tools/generate_tree_round6.py`，标 `pinned_reproducer`：只复现当前已钉住的 2026 树，不宣传为新大纲生成器；根由 `[3]` 改 `[1]`。搬迁验收必须在临时工作区比较其输出与搬前输出及登记的有效树，并注意其 `OUT.write_text(...)` 未显式固定 LF，Windows 重跑可能产生行尾差异。若决策者坚持归档，则 README 必须明确“现有生效 403 树需运行归档回放脚本，且新大纲尚无通用构建器”，不能称这一环已由活跃管线覆盖。 |
| R7 dispatch 与 `__pycache__` | **同意** | `dispatch/` 是 M20 开发工具，与数据重建无关；`__pycache__` 不属于受跟踪脚本，保持忽略即可。R5 清单须说明该排除范围。 |

## 二、分类逐组核对

以下只改明确列出的归类；未列出的原拟归类保持。类别是**放置位置**，顶层各脚本仍须在 README 标明适用年份及是否仅供固定版本回放。

| 原拟分类 | 判断 | 最终归类与依据 |
| --- | --- | --- |
| 管线：`build_408_index.py` | **修改** | → `tools/archive/`。它只生成 2024，且把 70 分的七道大题平均摊为 10 分（`tools/build_408_index.py:35-54,90-93`）；v2 文件头已明确指出这个错误（`tools/build_408_index_v2.py:5-9`）。v2 没有 import v1；静态导入图和源码都没有依赖。将 v1 继续列作可复跑管线会给出错误分值。 |
| 管线：`build_408_index_v2.py`、`build_exam_indexes.py` | **修改**（位置不变） | 留顶层但标 **pinned_reproducer**，不是通用新年份构建器。实跑 `py -3.12 tools/build_408_index_v2.py --year 2027` 报 `invalid choice: 2027`；`build_exam_indexes.py:22-83` 的年份、文件路径与答案表也逐年硬编码。v2 docstring `:19` 却叫用户运行 v1 的 `--year 2024`，而实跑 v1 报 `unrecognized arguments: --year 2024`。README 必须改用 v2 的真实命令，并明确 2027 要通过 M5 数据登记与验证，不能直接套旧 builder。 |
| 管线：`round22_extract`、round24/29 系列 | **修改**（位置不变） | 留顶层以保现有依赖和回放入口，但标“2022/2026 固定输入的树回放”，不是新大纲流水线。`round22_extract.py:17-20` 固定来源；`round24_build_weighted_tree.py:3-25` 固定旧树与 2022 PDF；`round29_build_tree_split.py:1-32` 固定补充树。且 round24 的 `generated_at` 用 `datetime.now`（`:660`），round29 同样如此（`:211`），不能宣称重跑必与现有产物逐字节一致。 |
| 迁移：`migrate_vocab_delivery.py` | **修改** | → `tools/archive/`，标 `retired/unexecuted`，不进入重建命令。现有测试导入随路径调整；保留测试不等于授权执行真实迁移。 |
| 历史：`probe_exam_pdf`、`probe_outline`、`probe_pdf_text`、`render_pdf_pages`、`render_staged_page`、`extract_exam_skeleton` | **修改** | → 顶层“采集前诊断/辅助管线”。这些分别接受 URL、任意 HTML、`--dir`、`--pdf`、暂存 PDF、`--pdf`（各脚本的 argparse 见 `:35-55` 附近），可在 2027 的候选卷/新大纲上**重新使用**；但 `extract_exam_skeleton` 是 408 特定的题号/节标题模式，新卷格式变化须人工复核，不能当普适解析器。`probe_exam_pdf` 会联网，重建说明须把它列为需明确来源许可的可选采集步骤，不是自动重取。 |
| 历史：`list_tree_vocab.py` | **修改** | → 顶层辅助工具。它按树中已有 ID 打印词汇供题目分类模式使用（`:1-10,27-39`）；未来更新分类器仍可用。当前 `TREE` 固定 403 文件（`:24`），README 应写明“仅当前 CS408 树”，后续需从生效登记取树才可泛化。 |
| 历史：其余九个 | **同意** | `audit_attachment`、`build_evidence_bundle`、`verify_evidence_bundle`、`verify_round3_findings`、`inspect_repos`、`probe_quiz_page`、`round22_format`、`round22_probe`、`round22_verify` → `tools/archive/`。它们依赖特定轮次主张、固定 URL/年份、已忽略的 `cache/evidence` 或本机 `%TEMP%/kaoyan-probe`；`probe_quiz_page.py:25-30` 仅列 2023–2026。round22 的两个裸导入须按 R3 修。 |
| 迁移：其余七个 | **同意** | `apply_round2_fixes`、`fix_eng1_provenance`、`register_round2_sources`、`register_408_source`、`register_408_quiz_pages`、`remove_408_reprints`、`restore_408_papers` → `tools/migrations/`，只供钉住的历史状态回放/审计，不用于新年份。 |
| 数据目录两个 `.py` | **修改** | `audit_round6` → `tools/archive/`；`generate_tree_round6` → 顶层 `tools/` 的固定版本树回放入口，理由见 R6。 |

原拟管线中未明确改动位置的脚本（M6 的四个、M5 的 `verify_408_index`、M4 的建树/校验、M7 的六个、M21 的五个、`fetch_evidence`、四个变异测试）位置不变；README 须分别区分构建、验证、日常操作、采集和固定版本回放。特别是 `daily_words` 是日常操作，变异测试是门禁，二者都不应被描述为“生成下一层数据”。

## 三、跨脚本依赖与最低验收

**导入图。** AST 静态检查发现顶层内部导入包括 `apply_knowledge_weights → verify_408_index`、`round24_build/validate → round22_extract`、`round29_build → round24_build + round29_quote_locate + tree_source_support`、`round22_format/verify → round22_extract` 等。按上述最终归类，活跃顶层脚本没有依赖拟迁走的模块；归档中的 `round22_format/verify` 反向依赖顶层模块，必须修 import。静态图不保证覆盖动态 `subprocess` 或文档命令，因此搬迁前再搜脚本名字符串、`sys.path`、`Path(__file__)` 与固定基线引用。

**历史脚本的最低验收（修改 R3）。** 先保存固定提交 `0c3b3e5` 的旧脚本作比较：

1. 对所有迁走文件：AST 解析、从新路径加载或运行 `--help`（仅支持该参数的脚本）、核实 `ROOT` 指向仓库根，并做导入图/路径引用扫描；不把“文件存在”当作能运行。
2. 有可重建本地夹具的脚本：在两份**系统临时**工作区给旧、新脚本相同输入，逐字节比较退出码、stdout/stderr 中稳定内容及生成文件；只放过已明确说明的 docstring/用法路径差异。测试可能需把 `GIT_DIR` 指向固定基线，但不能改旧哈希路径。
3. 依赖已删除缓存、硬编码本机临时路径或网络的脚本（例如 `build_evidence_bundle.py:33-35`、`round22_format.py:11-12`、`restore_408_papers.py:121-127`）：不联网、不伪称“逐字节一致”。能造最小本地夹具就造；否则完成静态/导入/无副作用路径检查，并逐项标“输出未实测、仅供历史回放”。既有跟踪数据与产物不得被重写；对需真实重放的脚本另立受控任务。固定版本建树器还须与登记数据哈希对照，避免把“新旧脚本输出相同”误当“与当前生效树相同”。

## 四、建议采用的最终规则

本轮按 **兼容优先的三种放置位置** 执行：现有顶层入口保留，顶层再按 `active / pinned_reproducer / validation / acquisition` 标状态；只搬已完成的一次性迁移和真正的历史脚本；退役但未执行的词汇迁移入 archive；两个数据目录脚本分流如上。每次搬迁同时处理根目录计算、裸导入、测试导入、当前文档命令与帮助文本，固定哈希基线和旧产物 provenance 不变。README 用**带前提和缺口的依赖图**描述当前重建：来源确认/登记 →（生效与补充树、卷面形状与索引）→ 编码批次/权重 → 投影；讲解在补充树与索引齐备后独立运行。对 2027 明写当前 builder 的年份限制，以及尚无通用新大纲建树/按台账重取全部原始资料的入口。

这能解决 C2 的混杂和可发现性，但 `tools/pipeline/` 物理拆分及完整自动重建仍属**未完成**，不应在阶段台账里记为完全收口。

### 最终放置清单（以下省略 `.py`）

- **`tools/` 顶层，41 个：** `aggregate_topic_weights`、`apply_knowledge_weights`、`render_weight_manual`、`classify_questions`、`verify_408_index`、`build_408_index_v2`、`build_exam_indexes`、`verify_tree`、`tree_source_support`、`build_math1_tree`、`build_eng1_tree`、`generate_tree_round6`、`round22_extract`、`round24_build_weighted_tree`、`round24_validate_weighted_tree`、`round29_build_tree_split`、`round29_quote_locate`、`round29_validate_agreement`、`daily_words`、`build_eng1_vocabulary`、`verify_eng1_vocabulary`、`import_netem_source`、`verify_netem_source`、`netem_cross_validate`、`build_408_deck_scaffold`、`extract_cs408_bundle`、`extract_408_question_text`、`extract_408_questions_from_html`、`verify_408_question_extraction`、`fetch_evidence`、`probe_exam_pdf`、`probe_outline`、`probe_pdf_text`、`render_pdf_pages`、`render_staged_page`、`extract_exam_skeleton`、`list_tree_vocab`、`mutation_test_408_index`、`mutation_test_knowledge_weights`、`mutation_test_suite`、`mutation_test_verify_tree`。
- **`tools/migrations/`，7 个：** `apply_round2_fixes`、`fix_eng1_provenance`、`register_round2_sources`、`register_408_source`、`register_408_quiz_pages`、`remove_408_reprints`、`restore_408_papers`。
- **`tools/archive/`，12 个：** `build_408_index`、`migrate_vocab_delivery`、`audit_attachment`、`build_evidence_bundle`、`verify_evidence_bundle`、`verify_round3_findings`、`inspect_repos`、`probe_quiz_page`、`round22_format`、`round22_probe`、`round22_verify`、`audit_round6`。
