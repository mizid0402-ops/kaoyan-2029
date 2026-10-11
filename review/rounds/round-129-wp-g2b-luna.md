# WP-G2b `tools/` 分层与重建说明（C2）实施报告

## 放置结果

- 按 `round-128-g2b-rules-sol-out.md` 最终清单使用 `git mv` 搬迁：`tools/migrations/` 7 个脚本，`tools/archive/` 12 个脚本；`generate_tree_round6.py` 移至 `tools/` 顶层。顶层其余 40 个脚本留在原位，`tools/dispatch/` 未动。
- 新增 [tools/README.md](../../tools/README.md)，登记顶层、migrations、archive 的每个 Python 脚本；dispatch 单列为排除范围。依赖图包含来源/登记、有效与补充树、卷面形状与索引、编码/权重、投影，以及独立的 M21 分支，并记录年份限制和当前缺口。
- 新增 `tests/test_tools_catalog.py`。清单脚本路径从 README 脚本表解析，测试不写死脚本名或数量，并与三个目录的直接 `.py` 文件双向比较。
- 未建 `tools/pipeline/`。当前生成器路径和文档命令是兼容入口；生成器身份与端口稳定后再评估物理迁移。

## 搬迁脚本修改与逐项验收

固定旧版均从 `git show 0c3b3e5:<旧路径>` 读取作比较；旧提交的路径与内容没有修改。20 个搬迁脚本均通过 AST 解析。8 个具备 argparse 的脚本从新路径运行 `--help`，全部 exit 0；其余脚本没有 argparse，不支持 `--help`，没有强行运行。

| 新路径 | 本脚本最小修改（行号为新文件） | 验收 |
| --- | --- | --- |
| `tools/migrations/apply_round2_fixes.py` | 30：仓库根 `parents[1]→parents[2]` | AST 通过；根解析到仓库根；无 `--help`；真实账本输出未实测，脚本会改写数据，仅供固定历史迁移。 |
| `tools/migrations/fix_eng1_provenance.py` | 23：根 `parents[1]→parents[2]` | AST、根检查通过；无 `--help`；固定来源/缓存输出未实测，避免真实状态写入。 |
| `tools/migrations/register_round2_sources.py` | 24：用法路径改为 migrations；35：根 `parents[1]→parents[2]` | AST、根检查、`--help` 通过；固定缓存/附件注册输出未实测。 |
| `tools/migrations/register_408_source.py` | 20：用法路径；31：根 `parents[1]→parents[2]` | AST、根检查、`--help` 通过；固定 2024 来源注册输出未实测。 |
| `tools/migrations/register_408_quiz_pages.py` | 19：用法路径；30：根 `parents[1]→parents[2]` | AST、根检查、`--help` 通过；固定网页来源注册输出未实测。 |
| `tools/migrations/remove_408_reprints.py` | 19–20：用法路径；31：根 `parents[1]→parents[2]` | AST、根检查、`--help` 通过；没有执行删除操作，真实数据输出未实测。 |
| `tools/migrations/restore_408_papers.py` | 1、27–28：用法/关联脚本路径；38：根 `parents[1]→parents[2]`。108 的生成 history/provenance 字符串保持原样 | AST、根检查、`--help` 通过；未联网或写真实数据，输出未实测。 |
| `tools/archive/build_408_index.py` | 24：用法路径；35：根 `parents[1]→parents[2]`；73：缺来源提示路径 | AST、根检查、`--help` 通过；固定 2024 PDF 输入与输出未在临时副本重建，历史回放。 |
| `tools/archive/migrate_vocab_delivery.py` | 14：根 `parents[1]→parents[2]` | AST、根检查、`--help` 通过。固定基线与新版在两份系统临时目录用相同 SQLite/工作区夹具运行 `--apply`：exit code、stdout、stderr、两份事件文件逐字节一致；没有写真实状态。 |
| `tools/archive/audit_attachment.py` | 18：根 `parents[1]→parents[2]` | AST、根检查通过；无 `--help`；依赖历史抓取缓存及附件，输出未实测。 |
| `tools/archive/build_evidence_bundle.py` | 33：根 `parents[1]→parents[2]`。155 的产物 provenance 字符串保持原样 | AST、根检查通过；无 `--help`；依赖固定审计输入，未写仓库审查产物，输出未实测。 |
| `tools/archive/verify_evidence_bundle.py` | 16：用法路径；27：根 `parents[1]→parents[2]` | AST、根检查、`--help` 通过；历史证据包未作为夹具运行，输出未实测。 |
| `tools/archive/verify_round3_findings.py` | 5：用法路径；17：根 `parents[1]→parents[2]` | AST、根检查、`--help` 通过；针对固定历史主张的验证输出未实测。 |
| `tools/archive/inspect_repos.py` | 7：用法路径；15：根 `parents[1]→parents[2]` | AST、根检查通过；无 `--help`；依赖历史缓存，输出未实测。 |
| `tools/archive/probe_quiz_page.py` | 11：用法路径；23：根 `parents[1]→parents[2]` | AST、根检查、`--help` 通过；依赖缓存网页/本地证据，输出未实测。 |
| `tools/archive/round22_format.py` | 7：`sys.path` 从自身目录改为仓库 `tools/`，使裸导入顶层 `round22_extract` 可用 | AST 通过；无 `--help`/仓库根变量；与 `round22_extract` 导入成功；输入及输出在固定本机临时路径，输出未实测。 |
| `tools/archive/round22_probe.py` | 6：根 `parents[1]→parents[2]` | AST、根检查通过；无 `--help`；依赖固定 2022/2026 文件和本机临时输入，输出未实测。 |
| `tools/archive/round22_verify.py` | 9：在裸导入 `round22_extract` 前将仓库 `tools/` 加入 `sys.path` | AST 通过；无 `--help`/仓库根变量；与 `round22_extract` 导入成功；固定本机临时路径的输出未实测。 |
| `tools/archive/audit_round6.py` | 11：根 `parents[3]→parents[2]` | AST、根检查通过；无 `--help`；固定来源审计输出未实测。 |
| `tools/generate_tree_round6.py` | 12：根 `parents[3]→parents[1]`；155–156：写文件显式使用 `newline="\n"`（C3 允许的唯一产物字节差异来源） | AST、根检查通过；在系统临时目录重跑；产物与登记树不一致，详见下一节；登记树未修改。 |

除表中所列之外，未改迁移脚本逻辑、参数、历史产物路径或 provenance。Round22 两个导入模块已从归档目录动态导入通过。脚本名/旧路径扫描确认活跃顶层工具没有对被迁脚本的 Python 导入依赖。

## `generate_tree_round6.py` 临时对照

将新脚本和其固定输入 HTML 复制到系统临时工作区，以临时工作区为根生成文件，再与仓库登记树按原始字节比较；没有以仓库目录作为输出路径。

| 项目 | 结果 |
| --- | --- |
| 生成器 exit code | 0 |
| 临时生成文件 | 255,213 字节 |
| 登记文件 | 291,692 字节；SHA-256 `fc369b440e2d51383586373844e3edf2cc89729e170d3d2249c777c7bb7a9d4e` |
| 逐字节相同 | **否** |
| 已观察的差异 | 登记树含脚本输出没有的文件头说明，以及 `scope`、`frequency`、transition 时间、`supersedes` 等人工/后处理字段。统一 diff 为 8,265 行；首段差异从登记文件的说明头开始。 |

该差异不是行尾差异。根据任务书保留差异报告、不改现有树。重建器生成的 403 节点结构不能直接覆盖登记树；覆盖前需单独确定如何保留登记树的人工标注及状态元数据。

## 文档与测试引用扫描/变更

扫描范围：`tests/`、`ky/`、`tools/`、`README.md`、`docs/`、`contracts/`。按脚本名及路径、Python 导入、`sys.path`、仓库根路径字符串检索；没有把旧字符串全局替换进产物 provenance。

| 文件 | 改动 |
| --- | --- |
| `tests/test_migrate_vocab_delivery.py` | 导入改为 `tools.archive.migrate_vocab_delivery`。 |
| `tests/test_exam_index.py` | 两处历史迁移命令仍保留旧路径，并标注“当时路径”。 |
| `docs/阶段1交付说明.md` | 历史说明和脚本清单保留旧路径并标“当时路径”；历史示例区的可执行验证命令改为 `tools/archive/verify_round3_findings.py`。 |
| `docs/阶段2-数学一英语一知识树.md` | 六处旧路径属于当时工具清单，保留路径并加“当时路径”。 |
| `docs/模块地图.md` | M7 实现入口更新至 `tools/archive/migrate_vocab_delivery.py`，标明已退役及禁止真实状态 `--apply`。 |
| `docs/模块拆分与架构审查.md` | M4 当前工具位置更新为 `tools/archive/audit_round6.py` 与 `tools/generate_tree_round6.py`。 |
| `tools/build_408_index_v2.py` | docstring 的错用 v1 命令改为 v2 的 `--year 2024` 命令；只改用法行。 |
| 被迁移的工具 | 用法/错误提示路径和根目录/导入路径修改见上表。保留 `tools/archive/build_evidence_bundle.py:155` 的生成 provenance 和 `tools/migrations/restore_408_papers.py:108` 的历史 detail 字符串。 |

扫描后仍出现的旧路径均属上述历史记录或产物 provenance；没有未更新的当前工具导入或当前命令。``git show 0c3b3e5:tools/x.py`` 基线引用未改。

## 清单撤改验证

临时用 `apply_patch` 删除 `tools/README.md` 中 `tools/render_weight_manual.py` 的一行，再运行 `py -3.12 -m unittest tests.test_tools_catalog`：exit 1，断言报告磁盘集合比清单集合多 `tools/render_weight_manual.py`。随后立即用 `apply_patch` 恢复该行，最终测试通过。测试从 README 表格读脚本清单，新增磁盘 `.py` 同样会使集合不一致而失败。

## 验收结果

- `py -3.12 -m unittest tests.test_tools_catalog tests.test_migrate_vocab_delivery`：**Ran 3 tests，OK**。
- 迁移脚本 AST：20/20 通过。
- argparse `--help`：8 个支持该参数的迁移脚本 exit 0；不支持 argparse 的 12 个未强行运行。
- 仓库根：18 个脚本路径表达式均解析到本仓库根；`round22_format` 与 `round22_verify` 无根变量，其对顶层 `round22_extract` 的导入通过。
- 固定基线输出对照：词汇迁移脚本 fixture 的 stdout、stderr、exit code、写出事件文件均逐字节一致。其他 18 个脚本未输出对照：包括会改动真实数据的迁移、依赖网络/历史缓存或固定本机临时路径的历史脚本，以及固定树生成器（该脚本已单独做临时重建并发现上述内容差异）。未把这些结果描述为字节一致。
- 引用扫描：迁移导入、当前命令、历史路径及 provenance 处理见上一节。
- `py -3.12 -m unittest discover ...` 全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。

## 建议

1. 先人工确认 `generate_tree_round6.py` 当前重建产物与登记树之间的元数据差异应如何处理；本轮未修改登记树或生成逻辑。
2. 保持 `tools/pipeline/` 物理拆分为后续议题，并在生成器路径兼容边界及重建端口稳定后再评估。

本轮仅修改任务书允许的文件。工作区另有 `ky/__main__.py`、`ky/projection/serve.py`、`ky/workspace.py`、`tests/test_projection_service.py` 的修改状态，未纳入或改动这些文件；其他未跟踪内容也保持原样。未提交。
