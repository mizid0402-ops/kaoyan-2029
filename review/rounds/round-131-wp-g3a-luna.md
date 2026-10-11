# WP-G3a 拆分 `load_workspace` 报告

## 改动

只调整 `ky/workspace.py`，并新增固定基线对照测试。公开接口和 `contracts/workspace.md` 未改。
解析顺序保持为：版本、科目、reference（knowledge trees、syllabus versions、exam indexes、paper shapes、单路径）、supplementary、materials、products、settings、state、staging、projection。

拆出及编排函数（行数按本轮文件统计）：

| 函数 | 行数 | 职责 |
|---|---:|---|
| `_parse_subjects` | 42 | 校验科目档案并生成科目与档案 |
| `_parse_knowledge_trees` | 20 | 解析有效知识树并校验科目和语法声明 |
| `_parse_exam_indexes` | 28 | 校验真题索引列表、科目及重复路径 |
| `_parse_syllabus_versions`（既有） | 31 | 解析版本树与映射登记 |
| `_parse_paper_shapes` | 10 | 解析卷面登记并校验科目 |
| `_parse_reference_paths` | 24 | 解析权重、词库和台账路径 |
| `_parse_reference` | 22 | 依固定次序编排 reference 子段 |
| `_parse_supplementary` | 27 | 解析补充视图及文件角色 |
| `_parse_materials` | 6 | 解析资料根目录 |
| `_parse_products` | 7 | 解析产品目录 |
| `_parse_settings` | 6 | 解析设置路径 |
| `_parse_state` | 19 | 解析状态写入路径 |
| `_parse_output_targets` | 4 | 解析 staging、projection |
| `_parse_document` | 28 | 校验顶层版本并依次调用注册表各段 |
| `_workspace_from_parts` | 28 | 从解析结果组装 `Workspace` |
| `_add_selection_context` | 7 | 保留显式选择来源的错误上下文 |
| `load_workspace` | 16 | 选择文件、读一次字节、解析、组装并保留错误包装 |

## 对照测试

`tests/contract/test_workspace_split_baseline.py` 从固定提交 `fa9e11c` 执行
`git show fa9e11c:ky/workspace.py`，断言基线 `load_workspace` 超过 150 行，再作为独立模块加载。
测试以仓库 `kaoyan.workspace.yaml` 为种子，按已有键、科目和登记生成 **55 个非法变体**，并与合法种子共 **56 个对照输入**。不固定科目名或数据条数。

55 个非法变体包括：

- 10 个顶层键缺失；
- 6 个 schema、类型、未知键、非法科目 ID、档案类型错误；
- 3 种路径错误：越界段、反斜杠、绝对路径；
- 8 种 `syllabus_versions` 错误；
- 3 种 `paper_shapes` 错误；
- 2 种 `weight_batches` 错误；
- 1 个真题索引内“未声明科目 + 值类型错误”的顺序探针；
- 10 个逐个顶层键缺失并叠加另一项错误的优先级组合（schema 类型错误，或 schema 缺失与 subjects 类型错误）；
- 12 个跨注册表相邻段同时出错的优先级组合。

合法输入递归比较新旧 `Workspace` 的全部字段；非法输入比较异常类型、`str(exc)` 和 `path`。
新旧实现分别加载，因此测试按 dataclass 字段比较值，不直接比较不同模块创建的类实例。

## 撤修改验证

临时将 `_parse_exam_indexes` 中“科目已声明”与“索引值为列表”两项检查对调，运行：

```text
py -3.12 -m unittest tests.contract.test_workspace_split_baseline
```

结果：**失败**，唯一失败变体为
`exam-index-unknown-subject-before-value-type`。基线先报
`subject is not declared`，临时修改后新实现先报 `expected a list`，异常消息和路径比较因此变红。
随后已恢复原顺序。

## 验收

执行命令：

```text
py -3.12 -m unittest tests.contract.test_workspace tests.contract.test_workspace_split_baseline
```

结果：`Ran 24 tests in 1.193s`，`OK (skipped=1)`。

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。

## 建议

本轮未发现需要扩大到其他模块的改动；提交前按仓库规则由决策者执行全量测试。
