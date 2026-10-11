# WP-H4a 实施报告

## 改动文件

- `ky/workspace.py`、`kaoyan.workspace.yaml`：增加 `SyllabusVersions`、可选键解析、生效路径一致性检查、`effective_version()`；`require()` 可取版本树，`require_all()` 可取映射文件列表。
- `ky/knowledge/syllabus_mapping.py`：新增 M4 版本映射加载器。严格 YAML 解析、字段拒绝、版本登记校验，并通过 `load_knowledge_points()` 读取树，检查拆分、合并、删除、新增与未声明变化。
- `tools/verify_tree.py`：将 `syllabus_versions` 内登记的树纳入科目识别。
- `contracts/workspace.md`、`contracts/syllabus_mapping.md`、`docs/模块地图.md`：登记字段和新端口规格；说明 `cross_year_tree` 只表达生效树超集来源视图；缺口表改为 H4b 的队列迁移与参照完整性。
- `tests/contract/test_syllabus_mapping_port.py`、`tests/contract/test_workspace.py`、`tests/test_verify_tree_shapes.py`：添加任务要求的正负契约用例。
- `tests/contract/test_knowledge_tree_port.py`、`tests/contract/test_subject_onboarding.py`：更新临时工作区复制辅助逻辑，使版本树路径仍与生效树指针对齐。

## 大纲年份核对

- cs408：树头注明来源为 `archive408_408_outline_2026.html`，登记为 `"2026"`。树头将该来源标为唯一权威来源。
- math1：树头列出 2022 与 2026 两版转录，说明当前树含 2026 版内容；登记为 `"2026"`。来源等级是 trusted reprint，树内明确记录尚待纸质官方大纲逐条复核。
- eng1：树头列出 2026 版英语（一）大纲目录来源，并注明目前先用 2026 版推进；登记为 `"2026"`。来源等级同样是 trusted reprint，不等同于官方原件核验。

三科均只登记现有当前树和空 `mappings` 列表；没有新增或修改知识树文件。

## 验收

- `py -3.12 -m unittest tests.contract.test_syllabus_mapping_port tests.contract.test_workspace tests.contract.test_knowledge_tree_port tests.contract.test_subject_onboarding`：28 tests；映射、workspace 新用例、onboarding 均通过。1 个既有仓库注册表检查报错，1 个知识树读者用例失败，原因都是 worktree 缺少 `data/raw_materials/`：前者找不到 `materials.raw_root`，后者找不到 math1 树引用的源文件。另有 1 项按平台条件跳过。
- `py -3.12 -m unittest tests.test_verify_tree_shapes`：24 tests；14 项通过，10 个既有变异用例因缺少 `data/raw_materials/` 中的 cs408/math1 源文件而在预期树形断言前失败。新增的版本树科目识别用例通过。
- `py -3.12 -m unittest tests.contract.test_syllabus_mapping_port tests.contract.test_workspace.WorkspaceContractTests.test_syllabus_versions_effective_pointer_and_labels tests.test_verify_tree_shapes.TreeShapeUnitTest.test_syllabus_version_tree_is_registered_for_its_subject`：11 tests，全部通过。
- `py -3.12 tools/verify_tree.py data/structured_materials/cs408/knowledge_tree.yaml`：退出码 1；树结构通过，来源检查因 `data/raw_materials/cs408/syllabus/archive408_408_outline_2026.html` 缺失而失败。
- 未创建 `data/raw_materials/` 或链接，按任务书保留上述失败证据。
- `git diff --check` 通过；变更文件未发现问号乱码串。
- 全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。

## 建议

- H4b 接入时从 `workspace.syllabus_versions[subject]` 解析队列旧版与当前生效版，消费映射前再补队列知识点 ID 的参照完整性检查。
- 当前三科 2026 标签依据树文件头及其来源说明确认；其中 math1、eng1 的来源说明明确保留了非官方转录/目录的证据等级限制，后续不要把版本年份登记误读成来源已获官方原件复核。
