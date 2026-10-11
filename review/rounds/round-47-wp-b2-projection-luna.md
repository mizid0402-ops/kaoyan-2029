# Round 47：WP-B′2 Projection 实现记录

## 改动文件

- `ky/projection/__init__.py`：从工作区注册表解析、验证和读取来源；schema version 2；生效树与跨年补充视图分表；哈希元数据；原子写入投影。
- `ky/projection/__main__.py`：新增 `--workspace`，`--out` 覆盖注册表输出；契约和知识点错误输出为 exit 2。
- `ky/projection/serve.py`：默认数据库路径取注册表 `projection`；新增 `--workspace`；显式 `--database` 保持优先。
- `tests/test_projection.py`：改用仓库注册表；构建结果只写临时目录；树节点数从登记的生效树读取。
- `tests/test_projection_service.py`：适配新的 `build_projection(workspace, out)` 接口，更新版本断言。
- `tests/contract/test_projection_port.py`：新增 10 条替换端口、补充分离、输入指纹、失败保留、CLI 和快照一致性契约测试。
- `contracts/projection.md`：定义 schema version 2、输入、缺失策略、分离规则、视图、哈希和只读保证。
- `docs/projection.md`：更新 CLI 用法并指向投影契约。

未改 `data/`，没有重建仓库里的 `data/projections/kaoyan_projection.sqlite`。`tests/contract/__init__.py` 已存在且无需改动。工作区里其他已有改动与未跟踪文件保持原样。

## 表结构变化

| 结构 | 旧版 | schema version 2 |
|---|---|---|
| `knowledge_points` | 以硬编码 410 版 CS408 树为源；带 `source_support`、`source_count`、`evidence_tag` | 仅读注册表生效树；删除三项补充属性列；`tree_source` 保存注册键，如 `reference.knowledge_trees.cs408` |
| 补充视图 | 无独立表，附表属性拼入知识点 | 新增 `supplementary_views` 与 `supplementary_knowledge_points`；补充节点记录 `is_effective`，agreement 属性只落在补充表 |
| 便利视图 | `v_knowledge_points_by_subject`、`v_question_coverage` | 保留两者；新增只选 `is_effective=0` 的 `v_supplementary_not_effective` |
| 输入来源 | 目录 glob、模块路径常量，缺文件可跳过 | 只读注册文件；`inputs` 是相对工作区根的 POSIX 路径到 SHA-256 映射，另存 registry 哈希 |

## 规格落实位置

- workspace 来源、`require`/`require_all`、注册表默认输出：`ky/projection/__init__.py::build_projection`；CLI 发现与覆盖在 `ky/projection/__main__.py` 和 `ky/projection/serve.py`。
- 生效/补充树分离、超集与 agreement ID 集校验：`_read_tree`、`_read_agreement` 及 `build_projection` 生成 `kp_rows` / `supplementary_rows` 的部分。
- 严格解析 agreement、契约解析生效树：`_read_agreement` 使用 `ky.models._read_yaml_file`；`_read_tree` 使用 `ky.knowledge.load_knowledge_points`。
- 已登记输入缺失失败、旧投影保留：输入 `require` 与读取/内容校验在创建临时输出之前执行；数据库写完后才 `os.replace`。
- 仅登记索引、不 glob：`index_paths` 由 `workspace.exam_indexes` 和 `require_all` 产生。
- 输入指纹、workspace 哈希、按科目生效计数、补充视图名：`projection_meta` 写入部分。
- 表和视图字段、确定性、只读边界：`contracts/projection.md`。

## 替换端口测试对应关系

| 覆盖项 | 测试名 |
|---|---|
| 显式 `--workspace` / `--out` CLI | `test_projection_cli_uses_explicit_workspace_and_out` |
| 坏的显式 workspace 不回退 | `test_projection_cli_bad_explicit_workspace_does_not_fall_back` |
| 仓库 CS408 生效 403、补充 410 / 生效 403、7 个 legacy 节点、有效表无补充属性列 | `test_repository_effective_and_supplementary_separation` |
| 快照与投影各科生效节点计数一致 | `test_snapshot_counts_match_effective_projection_counts` |
| 树、索引、权重、词库换到其他相对路径，路径哈希随注册表变化 | `test_replacement_uses_new_registered_relative_paths_and_hashes` |
| 已登记索引缺失，旧投影字节不变 | `test_missing_registered_index_preserves_existing_output` |
| agreement 少一行 / 多一行违约 | `test_agreement_missing_row_is_rejected`、`test_agreement_extra_row_is_rejected` |
| 生效 ID 不在补充树中违约 | `test_effective_id_missing_from_supplement_is_rejected` |
| 同输入元数据/表内容确定，`inputs` 恰为本次登记来源集合 | `test_projection_content_and_inputs_are_deterministic_and_exact` |

既有投影回归与服务测试保留：`tests/test_projection.py`、`tests/test_projection_service.py`。

## 验收结果

1. `py -3.12 -m unittest tests.test_projection tests.test_projection_service tests.contract.test_projection_port tests.contract.test_state_snapshot_port tests.contract.test_workspace`：**Ran 49 tests, OK (skipped=1)**。skip 为 Windows 账户无法创建 symbolic link（WinError 1314）；工作区测试的 junction 越界分支已通过。
2. `py -3.12 -m ky snapshot --config tests/fixtures/config/config-minimal.yaml --items tests/fixtures/reviews/reviews-normal.yaml --date 2026-09-25 --json`：exit 0；JSON 中 `cs408.tree_total.count` 为 **403**，`politics.tree_total` 为 `null`。
3. `py -3.12 -m unittest discover -s tests -t .`：**Ran 474 tests, FAILED (failures=2, skipped=1)**。仅有任务书列明的两个基线失败：
   - `test_verifier_deterministic_check_and_mutations`：缺少 `C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\claude2\dl\bv_e1_2024.pdf`。
   - `test_real_file_passes_validation`：缺少 `C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\ghsurvey\downloads\408_syllabus_2022.pdf`。
4. `rg -n "parents\[2\]|safe_load" ky/projection`：exit 1、无匹配。
5. `git diff --check`：通过。

## 规格解释与歧义

- 规格要求 `reference.vocabulary_db` 经注册表必需，并要求 `inputs` 只记录实际读取文件，但没有说明投影是否要查询词库数据库内容。实现沿用旧投影语义：把词库作为必需依赖完整读取以记录 SHA-256，但不从中产生投影表。
- `supplementary_views` 的 meta 值采用按 `view_name` 排序后的 JSON 名称数组；规格规定名称列表但未写排序要求。排序让输出可复现。
- 显式 `--database` 与 `--workspace` 同时传入服务命令时，按数据源优先级直接用数据库文件，不加载无关注册表；仅默认数据库路径时才发现 workspace。这符合显式数据源覆盖注册表的优先级。


## 修复（sol FAIL 后）

> 注：本节原文由 gpt-6-luna 通过 PowerShell 5.1 here-string 管道写入，中文被编码成 `?` 丢失（见 AGENTS.md 编码规则）。
> 以下由 Claude 根据 diff 与本地测试重述。

- M1：每个登记输入只读一次字节，哈希与解析共用；新增 `ky.knowledge.load_knowledge_points_from_text`（`load_knowledge_points(path)` 读字节后调用它），
  `ky.models` 新增文本入口 `load_yaml_text`，复用同一个严格 loader。回归 `test_hash_and_projection_content_use_the_same_read_bytes`。
- M2：索引条目的 `locator`、`exam_year`、`marks` 等类型不符时以条目字段路径抛 `ContractError`，CLI exit 2。回归 `test_malformed_locator_is_a_contract_error_and_cli_exit_two`。
- M3：补充树节点 ID 的科目必须等于视图科目，否则在 `supplementary.<name>.files.tree.items[i].knowledge_point_id` 拒绝。回归 `test_supplementary_node_must_match_registered_view_subject`。
- 断言加强：仓库测试核对 7 个 legacy 节点完整 ID 集与 `tree_source` 精确键；替换演练改写被替换文件内容。
- D7：`build_projection` 拆成有名字的步骤，行宽 ≤ 100。
- luna 报告的验收：`tests.contract.test_projection_port tests.test_projection tests.test_knowledge_contract tests.test_state_snapshot` → Ran 44, OK；
  改测试后只重跑受影响模块（按 AGENTS.md）。全量未跑。
