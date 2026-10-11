# 任务书：WP-H4a 决策者审查意见（续你第 66 轮在本 worktree 的改动）

设计落点都对，下面是可读性（D7）与一处校验缺口。只动列出的文件，不改数据文件。遵守 `AGENTS.md`。

## 必须改

1. `ky/knowledge/syllabus_mapping.py` 的 `load_syllabus_mapping` 约 95 行。拆成有名字的辅助函数，例如：读文件与表头（版本、科目、basis）、
   解析 `changes`、解析 `added`、两棵树的覆盖检查（未声明删除 / 无来源新节点）。公开函数本身只做编排。
2. `ky/workspace.py`：`load_workspace` 里新加的 `syllabus_versions` 解析块提成 `_parse_syllabus_versions(reference, subject_set, knowledge_trees, root)` 辅助函数（行为不变）。
   `require_all` 现在的 `subject` / `paths` 分支交织难读：改成"先按键前缀找到路径元组（exam_indexes 或 syllabus mappings），找不到再判 not registered / not a path list"的直线结构，可用一个小辅助函数。
3. 映射文件与登记位置一致：映射文件登记在 `reference.syllabus_versions.<科目>.mappings` 下，其 `subject_id` 必须等于这个 `<科目>`。
   给 `load_syllabus_mapping` 加关键字参数 `subject_id`（调用方传登记科目），不等 → `ContractError`，路径 `subject_id`。规格 `contracts/syllabus_mapping.md` 同步一句；
   契约测试加一条负例（把一份 cs408 的映射当成另一科的映射加载）。

## 不做的

同第 66 轮任务书。

## 验收（只跑这些；缺 `data/raw_materials/` 导致的既有失败照旧如实记录）

```
py -3.12 -m unittest tests.contract.test_syllabus_mapping_port tests.contract.test_workspace tests.test_verify_tree_shapes.TreeShapeUnitTest.test_syllabus_version_tree_is_registered_for_its_subject
```

## 报告

`review/rounds/round-68-wp-h4a-fixes-luna.md`：逐条落点、验收输出。全量：未跑。不提交。含中文的文件查 `???`。
