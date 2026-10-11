# Round 45 — WP-B 工作区注册表实现报告

## 变更文件

- `kaoyan.workspace.yaml`：按 `contracts/workspace.md` §2 登记当前工作区数据源，LF 换行；CS408 生效树登记为 `data/structured_materials/cs408/knowledge_tree.yaml`，实测为 403 条记录。
- `ky/workspace.py`：新增注册表数据类、发现/加载、结构和路径语法校验、只读映射、原始字节 SHA-256，以及延迟 `require` 检查。
- `tests/contract/__init__.py`：使 `tests.contract` 成为可发现包。
- `tests/contract/test_workspace.py`：以 `LOADERS` 参数化的 8 项替换实现契约。
- 本报告。

`ky.models`、消费方、CLI 和 `data/` 下登记内容均未修改。没有提交。

## 规格实现位置

| 规格 | 实现 |
|---|---|
| §1–§2.1 | 注册表样例在 `kaoyan.workspace.yaml`；字段白名单、类型、必填字段、科目及补充视图约束在 `ky/workspace.py` 的常量和 `load_workspace`。严格 YAML、重复键、映射检查复用 `ky.models._read_yaml_file`、`_require_mapping`、`_reject_unknown_keys` 与 `ContractError`。 |
| §2.2–§2.3 | `_registered_path` 校验 POSIX 相对路径并以注册表父目录构造绝对 `Path`；加载阶段不跟随链接。内嵌路径根按 `Workspace.root` 暴露。 |
| §2.4 | `_VIEW_ROLES` 和补充视图解析要求 `cross_year_tree` 具备且仅具备 `tree`、`agreement` 角色；不检查树内容或超集关系。 |
| §3.1 | `_absolute`、`_select_workspace`、`find_workspace` 实现显式值、`KY_WORKSPACE`、最近向上发现及命中失败不回退；相对值基于 cwd。 |
| §3.2、§8 | 未迁移消费方，也未改 CLI，现有命令行为保持原样。 |
| §4 | `Workspace.require` / `require_all` 检查登记、存在、文件/目录类型及 `resolve()` 后的工作区边界。写入目标 `state.*`、`staging`、`projection` 不进入 `require` 输入路径表。 |
| §5 | `load_workspace` 对注册表原始字节计算 SHA-256；不规范化换行。 |
| §6 | `SupplementaryView`、`Workspace` 为冻结 dataclass；路径映射用 `MappingProxyType`，索引列表与科目列表用 tuple。错误均为 `ContractError`。重复键错误由共享 YAML loader 检出，再映射到重复字段的点路径。 |
| §7 | `tests/contract/test_workspace.py` 中 `test_1_…` 至 `test_8_…` 对应 8 项契约（下表）。 |

## §7 契约项与测试名

| §7 | 测试 |
|---|---|
| 1 仓库注册表、403 树、11 个索引及已登记输入 require | `test_1_repository_registry` |
| 2 复制后路径随根移动、子目录发现 | `test_2_paths_are_relative_to_registry_even_from_child_directory` |
| 3 结构拒绝、未知/重复字段和字段路径 | `test_3_structure_rejections_report_contract_paths` |
| 4 路径语法拒绝 | `test_4_registered_path_syntax_is_rejected` |
| 5 懒检查、缺失/类型错误、越界链接及 require 接口错误 | `test_5_lazy_existence_type_and_symlink_checks` |
| 6 发现优先级、失败不回退、空环境变量、cwd 相对值、最近者 | `test_6_discovery_precedence_no_fallback_and_cwd_resolution` |
| 7 SHA-256 原始字节及 LF/CRLF 区别 | `test_7_sha256_tracks_original_bytes_including_line_endings` |
| 8 纯读与嵌套映射不可变 | `test_8_loading_is_pure_read_and_mappings_are_immutable` |

## 验收命令

- `py -3.12 -m unittest tests.contract.test_workspace -v`：`Ran 8 tests`，`OK (skipped=1)`。符号链接子用例因 Windows `WinError 1314`（当前账户没有创建符号链接的权限）跳过；skip 消息包含该原因。测试未创建 junction。
- `py -3.12 -m unittest tests.test_contracts tests.test_cli`：`Ran 92 tests`，`OK`。
- `py -3.12 -m unittest discover -s tests -t .`：全量运行 `Ran 450 tests in 99.211s`，`FAILED (failures=2, skipped=1)`。两个失败正是任务书列出的基线：
  - `tests.test_eng1_vocabulary.English1VocabularyRegressionTests.test_verifier_deterministic_check_and_mutations`：缺少 `C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\claude2\dl\bv_e1_2024.pdf`。
  - `tests.test_round24_weighted_tree.WeightedTreeStructureTest.test_real_file_passes_validation`：缺少 `C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\ghsurvey\downloads\408_syllabus_2022.pdf`。
- `git diff --check`：通过。`kaoyan.workspace.yaml` 实测 43 个 LF、0 个 CRLF。

全量运行后，契约测试第 8 项的目录快照进一步加强为同时记录目录项和文件字节；最终 `tests.contract.test_workspace` 重跑仍为 `Ran 8 tests`、`OK (skipped=1)`。该收尾改动只涉及测试断言，未改实现代码。

## 规格歧义 / 解释

没有发现必须更改规格才能实现的冲突。§7.1 的“每个 require/require_all 在本仓库都通过”若逐字包括写入目标，会与 §4 明确规定的 `state.*`、`staging`、`projection` 不走 `require` 冲突；本实现和测试按 §4 将该验收限定为已登记输入，写入目标只提供路径、不做存在性检查。

§4 将失败场景称作“四种情况”，其中路径类型有文件、目录两类，故表述上不是四个互斥的错误类别。实现依字段 F/D 返回相应类型错误；该文字歧义不影响接口行为。
