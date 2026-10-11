# WP-H4a 第 68 轮修正报告

## 逐条落点

1. `ky/knowledge/syllabus_mapping.py`：将加载拆为 `_read_mapping_document`、`_parse_mapping_header`、`_load_version_tree_ids`、`_parse_changes`、`_parse_added` 和 `_validate_tree_coverage`。公开的 `load_syllabus_mapping()` 现在只编排这些步骤。
2. `ky/workspace.py`：新增 `_parse_syllabus_versions(reference, subject_set, knowledge_trees, root)`，并将版本路径和映射路径解析拆成小辅助函数。`require_all()` 先通过 `_registered_path_list()` 按键前缀取得路径元组，再统一区分“未登记”和“不是列表字段”。
3. `load_syllabus_mapping(path, workspace, *, subject_id)`：调用方必须提供映射文件登记所在科目；文件内 `subject_id` 不匹配时抛出 `ContractError`，路径为 `subject_id`。`contracts/syllabus_mapping.md` 同步记录参数和一致性要求；新增 cs408 映射被当作 alpha 科目加载的拒绝用例。

## 验收

执行任务书指定命令：

```text
py -3.12 -m unittest tests.contract.test_syllabus_mapping_port tests.contract.test_workspace tests.test_verify_tree_shapes.TreeShapeUnitTest.test_syllabus_version_tree_is_registered_for_its_subject
```

结果：Ran 25 tests；映射端口、workspace 新增用例和版本树识别用例通过；1 项按平台条件跳过。`test_workspace` 的仓库注册表完整性用例因 worktree 缺少 `data/raw_materials/` 报错：`materials.raw_root` 目录不存在。该目录是任务书说明未包含的 gitignore 数据，本轮没有创建目录或链接。

`git diff --check` 通过。变更文件未发现问号乱码串。全量：未跑。
