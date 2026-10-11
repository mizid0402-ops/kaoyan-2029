# Round 135 Codex 评审：G2a 复审、WP-G3a、WP-G2b

## 范围与方法

分别用 `git archive` 展开 `458f1ea`、`0f9689d`、`b90dc70` 到系统临时目录；运行、探针和生成的缓存均在临时副本中。固定旧版对照所需的 `git show` 仅通过 `GIT_DIR` 读取 Git 对象。按注册表建立了 `review/408知识点树与真题` 空目录。归档不含未跟踪的 `data/raw_materials` 原始资料；遵守“不读写主仓库工作区”，没有从主工作区复制，因此依赖这些字节的历史生成器未重放，不能把实现者报告中的哈希对照当成本轮独立实测。没有跑全量。

## 一、G2a 复审（`458f1ea`）：**PASS**

| 项 | 判断 | 复现输入与结果 |
| --- | --- | --- |
| M1：省略 `--store` 仍读两次注册表 | **不改，已解决** | 在归档运行 `py -3.12 -m unittest tests.test_cli.DayPlanCliTest.test_record_without_store_reads_the_registry_once`，通过。该测试用有效注册表、带复习完成事件、显式 `--workspace` 且省略 `--store`，patch 计数为 `load_workspace=1`、`find_workspace=0`，事件落在登记的 `state.plans`。`ky/__main__.py` 的 record 分支复用同一个 `Workspace` 取存储目标、冻结状态和出题候选；显式 `--store` 分支仍通过 `_optional_workspace` 加载可选注册表。 |
| M2：后台 serve 地址被缓冲 | **不改，已解决** | 在归档内启动真实 `py -3.12 -m ky.projection.serve --database <临时空 SQLite> --port <临时空闲端口>`，重定向 stdout 至临时文件。端口已连接、进程仍存活时，文件已包含 `serving: http://127.0.0.1:<端口>/`；`ky/projection/serve.py` 的打印设了 `flush=True`。定向缓冲流测试 `tests.test_projection_service.ProjectionServiceTest.test_address_is_flushed_before_datasette_takes_over` 通过。 |
| G3 建议：默认 preflight 与逐行帮助 | **不改，已落实** | `ky/__main__.py:1374` 缺省分派调用 `SUBCOMMANDS["preflight"][0](args_in)`；`tests/test_cli.py:307-312` 把表中每个格式化后的帮助行与 `stdout.splitlines()` 逐行比较。输入 `py -3.12 -m ky -h` 由相同表打印。 |

验证：设置 `GIT_DIR` 指向仓库 Git 对象后，`py -3.12 -m unittest tests.test_cli tests.test_projection_service` → **52 项 OK**。第一次未设置 `GIT_DIR` 时，7 个固定旧版 `git show` 子用例因归档没有 `.git` 报错；环境补齐后全部通过，这不是产品缺陷。

## 二、WP-G3a（`0f9689d`）：**PASS**

| 项 | 判断 | 复现输入与结果 |
| --- | --- | --- |
| 解析顺序、所有字段与错误合同 | **不改** | 在归档设置 `GIT_DIR`，运行 `py -3.12 -m unittest tests.contract.test_workspace tests.contract.test_workspace_split_baseline` → **24 项 OK，2 跳过**（缺未跟踪原始资料、当前账户不能创建 symlink）。对照测试用固定 `fa9e11c:ky/workspace.py`，断言旧 `load_workspace` 超过 150 行；对合法种子递归比较 dataclass 全字段，对异常比较类型、消息及 `path`。源码中 `_parse_document` 保持版本→科目→reference→supplementary→materials→products→settings→state→staging→projection 顺序；reference 内部也按旧次序调用。跨段双错误探针及真题索引内“未知科目/值类型”探针覆盖先报位置。各辅助函数职责单一，`load_workspace` 只作选择、一次读字节、解析和组装。 |
| “55 个非法变体”表述 | **建议改** | 用测试文件的 `_invalid_registry_variants(seed)` 逐个调用新版 `load_workspace`，共生成 55 个变体，但 `missing-top-level-supplementary`、`missing-top-level-products`、`missing-top-level-settings` 均成功加载：这三个键本就是可选项。实际是 **52 个非法变体、3 个合法缺省变体，加原样种子共 56 组**。对照本身仍有效；建议修正实施报告计数，并在测试中明确断言各变体预期成功或失败，防止以后某个“非法”样本意外变为合法而测试继续绿。 |

测试变体从当前注册表的顶层键、首个科目和登记路径推导，没有钉死科目数；覆盖 `syllabus_versions`、`paper_shapes`、`weight_batches` 以及多处同时出错。实现者报告所述交换 `_parse_exam_indexes` 两项检查会使优先级探针变红；本轮未改实现去重复该撤改试验。

## 三、WP-G2b（`b90dc70`）：**FAIL**

| 项 | 判断 | 复现输入与结果 |
| --- | --- | --- |
| G2b-M1：重建步骤给出的命令不能完成对应步骤 | **必须改** | `tools/README.md` 的步骤 2 写 `py -3.12 tools/build_exam_indexes.py`。在归档原样运行，退出 1，提示必须传 `--subject`、`--year`，没有生成索引。步骤 3 的 `classify_questions.py --help`、`apply_knowledge_weights.py --help` 和步骤 5 的 `build_408_deck_scaffold.py --help` 都只是打印帮助后退出，不会产生该步骤所述产物；例如分类器的帮助列明必需 `--pdf --year --out`。任务书明确要求“每步写命令”。请给出可执行的带参数示例（输出写临时目标或明确提示何时会改登记数据）；需要人工输入的地方用清楚的占位符，并把 `--help` 仅列为查参方式。位置：`tools/README.md` 重建依赖图下步骤 2、3、5。 |
| G2b-M2：408 v2 支持年份写错 | **必须改** | `tools/README.md` 清单行和“Current gaps and limits”写“only 2024–2026”；实际 `py -3.12 tools/build_408_index_v2.py --help` 显示 `--year {2023,2024,2025,2026}`，源码 `:46-69,286` 也为 2023 配了来源与选项。`--year 2027` 确实被拒绝。请把可接受年份写为 2023–2026，并说明各年仍需对应原始文件、台账、卷面形状；不要把本轮归档缺失的原始资料误写成程序不支持 2023。位置：`tools/README.md` v2 清单行及限制段。 |
| 脚本搬迁、导入与 provenance | **不改** | `git diff --find-renames=30% --unified=1 b90dc70^ b90dc70 -- '*.py'` 显示 7 个 migrations、15 个 archive 脚本的逻辑未改；差异是根目录深度、round22 两个裸导入的 `sys.path`、自身用法文字，以及 round6 生成器明确 LF 写入。`py -3.12 -m compileall -q tools/archive tools/migrations` 通过；8 个真正支持 argparse 的被挪脚本从新路径运行 `--help` 均 exit 0。`round22_format/verify` 从新位置指向顶层 `round22_extract`；历史产物中的 `tools/build_math1_tree.py` 等 provenance 原字节保留。依赖缺失原始资料/缓存、会写登记路径的脚本未作输出字节对照，不能据此宣称逐脚本产物已独立证明相同。 |
| 树生成器三者归档 | **不改，取舍合理** | `generate_tree_round6.py`、`build_math1_tree.py`、`build_eng1_tree.py` 都写登记树路径，后两者仅在 `--write` 时写；README 明示不得在仓库运行。决策者和实现者报告分别记录：round6 生成 255,213 字节而登记树 291,692 字节，数学一/英语一 dry-run 哈希也不等于登记树。本轮静态核实归档 round6 输出结构缺少登记树现有字段，并核实目标路径直接指向登记树；缺原始资料，未独立重算三个哈希。把这些有覆盖风险的旧生成器归档、将登记树标为当前事实来源，比继续称它们为可重建入口合理。README 对“不能重建”的主张应保留此实测来源与当前限制。 |
| 清单、引用、依赖图与测试 | **不改（受上面两项文档问题限制）** | `py -3.12 -m unittest tests.test_tools_catalog tests.test_migrate_vocab_delivery tests.test_exam_index` → **12 项 OK，4 跳过**。清单测试双向核对磁盘 `.py` 与 README 行；旧路径扫描在 `tests/`、`ky/`、`tools/`、`README.md`、`docs/`、`contracts/` 命中均为标了“当时路径”的历史叙述，或需保持字节不变的产物 provenance。依赖图把 M21 与投影分开，说明了台账重取与新大纲建树缺口、未完成 `tools/pipeline/` 物理拆分，并禁止真实状态运行词汇迁移 `--apply`。这些判断不证明缺失资料下的历史脚本输出。 |

## 安全登记

本轮没有新增仅在恶意输入、并发交错或篡改内部文件时触发的问题。上一轮登记的 G2a 双读交错窗口随单次加载一并消除；不另开安全返工。

## 门禁结论

- **G2a PASS**：M1、M2 与 G3 建议均复现通过。
- **WP-G3a PASS**：固定旧版对照及定向契约测试通过；计数修正属建议。
- **WP-G2b FAIL**：先修 README 的不可执行重建命令和 408 v2 年份错误；不要求重开树生成器归档取舍。
