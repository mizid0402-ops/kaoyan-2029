# 任务书：WP-G2b `tools/` 分层与重建说明（C2）

先读仓库根 `AGENTS.md`（全部规则都适用，尤其 11–13、12a"输出不变"与编码规则），再读：
**`review/rounds/round-128-g2b-rules-sol-out.md`（全文；本任务的规则与放置清单以它第四节"建议采用的最终规则"与"最终放置清单"为准）**、
`review/rounds/round-128-g2b-rules-sol.md`（决策者原拟规则，已被上面那份修订）、`docs/模块拆分与架构审查.md` 的 C2、`docs/模块地图.md`、`contracts/projection.md`。

你在主仓库 `F:\workspace\kaoyan-ai-system` 工作。可改：`tools/` 下的脚本（仅限下述最小修改）、新增 `tools/README.md`、引用被挪脚本的测试的导入路径、
`README.md` 与 `docs/` 里**指向被挪脚本的当前可执行命令**、`docs/模块地图.md` 的相关行、`data/structured_materials/cs408/` 下两个 `.py` 的挪出。不改 `交接文档.md`（决策者改）。

## 要做的

1. **放置**（用 `git mv`）：照 sol 最终放置清单——`tools/migrations/` 7 个、`tools/archive/` 12 个（含 `data/structured_materials/cs408/audit_round6.py`）、
   `data/structured_materials/cs408/generate_tree_round6.py` → `tools/generate_tree_round6.py`；其余 40 个顶层脚本原地不动。`tools/dispatch/` 不动。
2. **被挪脚本的最小修改**（逐项列进报告）：只改运行所需的——求仓库根的那一行（按新深度，**逐个核对**原来是 `parents[1]` 还是 `[3]`）、
   裸导入顶层模块所需的 `sys.path`（`round22_format`、`round22_verify` → `round22_extract`）、docstring / 帮助 / 错误提示里的**本脚本用法路径**。
   **产物里写的生成器路径、provenance 字符串一律不改**（历史事实）。其他任何逻辑不改。
3. `generate_tree_round6.py` 是现行 403 树唯一的生成脚本：若它用 `write_text` 未固定行尾，**允许**改为显式 LF 写入（C3：数据文件一律 LF），报告写明；这是本任务唯一允许的产物字节差异来源。
4. **`build_408_index_v2.py` docstring** 里叫用户运行 v1 `--year 2024` 的用法行改为 v2 的真实命令（只改 docstring）。
5. **`tools/README.md`**：
   - 每个脚本一行（顶层、`migrations/`、`archive/` 全部；`dispatch/` 单列为排除范围）：状态（`active` / `pinned_reproducer` / `validation` / `acquisition` / `migration` / `archived` / `retired`）、所属模块（`docs/模块地图.md` 编号）、输入、写入目标、何时运行、可复跑范围与缺资源时的前提。
   - **重建依赖图**（不是直线）：来源确认 / 登记 →（生效与补充树、卷面形状与索引）→ 编码批次 / 权重 → 投影；讲解（M21）在补充树与索引齐备后独立运行。每步写命令。
   - 明写缺口：现有 408 / 数学一 / 英语一 builder 的年份限制（例如 v2 不接受 2027）、2027 年真题要走 M5 数据登记与校验而不是套旧 builder、尚无通用新大纲建树器、尚无"按台账重取全部原始资料"的入口、`migrate_vocab_delivery` 已退役**禁止对真实状态执行 `--apply`**。
   - 写明 C2 的物理 `tools/pipeline/` 拆分**未做**及原因（生成器路径与文档命令兼容），留待端口稳定后另议。
6. **测试与文档引用**：扫描 `tests/`、`ky/`、`tools/`、`README.md`、`docs/`、`contracts/` 里对被挪脚本的引用（导入、`sys.path`、`Path(...)`、命令、脚本名字符串）。
   测试导入改到新位置；`git show <固定哈希>:tools/x.py` 基线**不改**；文档里的**当前可执行命令**改新路径，**历史叙述**保留旧路径并注"（当时路径）"。报告列出每处改动。

## 不做的

- 不挪顶层 40 个脚本；不建 `tools/pipeline/`；不做 `ky rebuild` / Makefile；不改任何脚本的逻辑、参数、产物内容（上面第 3 条除外）。
- 不重跑任何会写 `data/` 的脚本到真实仓库路径（对照只在系统临时目录做）；不联网。
- 不改 `交接文档.md`、`review/rounds/` 下的历史报告。

## 测试（只写这一个）

`tests/test_tools_catalog.py`：`tools/README.md` 的清单与磁盘上 `tools/`、`tools/migrations/`、`tools/archive/` 的 `.py` **双向一致**（每个文件都登记、每个登记都存在）；清单从 README 表格读出，**不在测试里写死脚本名或数量**。
撤掉 README 的一行或多放一个文件时变红（报告写实际怎么撤、实际结果）。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.test_tools_catalog tests.test_migrate_vocab_delivery
```
外加所有**被你改了导入路径的测试模块**（逐个列名跑，不跑全量）。

另按 sol 报告第三节"最低验收"逐个检查被挪的 20 个脚本：AST 解析；从新路径运行 `--help`（支持的）；核实求得的仓库根正确；导入图与路径引用扫描；
能造本地夹具的，在两份系统临时目录里用固定提交 `0c3b3e5` 的旧版与新版跑同一输入，逐字节比较；依赖网络 / 已删缓存 / 本机临时路径的，标"输出未实测、仅供历史回放"。
`generate_tree_round6.py`：临时目录重跑，产物与仓库里登记的 `data/structured_materials/cs408/knowledge_tree.yaml` 逐字节比较（报告写结果；不一致先报告，不要改树）。

## 报告

`review/rounds/round-129-wp-g2b-luna.md`：放置结果、每个被挪脚本的改动行与验收结果（表格）、文档 / 测试引用改动清单、`generate_tree_round6` 对照结果、撤修改验证、验收输出、建议。
写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。含中文的文件只用 `apply_patch` 编辑，写完查 `???`。
