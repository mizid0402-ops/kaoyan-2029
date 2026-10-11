# 第 211 轮：Workspace 变体过滤修正

## 改动

`tests.contract.test_workspace.WorkspaceContractTests.test_single_error_variant_table` 不再按 `double-error-` 前缀过滤，而是使用显式退役名称集合。以下三项从集合中移除并回到正式表：

- `double-error-schema-before-supplementary`
- `double-error-schema-before-products`
- `double-error-schema-before-settings`

三项均按生成器原始 `expected_success=False` 进入 `assertRaises(ContractError)` 分支。退役判定现在只匹配 19 个明确列出的组合错误顺序探针。

## 更新后的计数

由 `tests.contract.test_workspace._registry_variants` 实际运行统计：55 个变体，其中 36 个进入当前行为 `subTest`，19 个组合错误顺序探针退役。与第 209 轮相比，迁移数由 33 增至 36，退役数由 22 减至 19。

退役集合为：

```text
double-error-schema-before-schema_version
double-error-schema-before-subjects
double-error-schema-before-reference
double-error-schema-before-materials
double-error-schema-before-state
double-error-schema-before-staging
double-error-schema-before-projection
subject-before-reference
knowledge-before-syllabus
syllabus-before-exam-indexes
exam-indexes-before-paper-shapes
paper-shapes-before-weight-path
reference-before-supplementary
supplementary-before-materials
materials-before-products
products-before-settings
settings-before-state
state-before-staging
staging-before-projection
```

## 源码变异

使用系统临时目录中的 `round211_workspace_mutation_probe.py`，复制仓库 `ky/` 到 `TemporaryDirectory(prefix='round211-')`，只改副本 `workspace.py`：允许 `schema_version` 为字符串并将其转成整数。探针将副本置于 `sys.path` 前端，运行 `tests.contract.test_workspace.WorkspaceContractTests.test_single_error_variant_table`，没有在测试侧 patch 被测函数。

实际命令：

```powershell
py -3.12 $probePath
```

结果：整表用例失败 4 个子项。除原单错误 `schema-version-type` 外，三项新增回归输入也逐一失败：

```text
variant='double-error-schema-before-supplementary' ... ContractError not raised
variant='double-error-schema-before-products' ... ContractError not raised
variant='double-error-schema-before-settings' ... ContractError not raised
OPTIONAL_BLOCK_SCHEMA_MUTANT_CAUGHT=True
FAILED_CASES=double-error-schema-before-products,double-error-schema-before-settings,double-error-schema-before-supplementary
```

副本和探针脚本均在系统临时目录，运行后清理。

## 验收

命令：

```text
py -3.12 -m unittest tests.contract.test_workspace
```

输出原文：

```text
.......s................
----------------------------------------------------------------------
Ran 24 tests in 0.621s

OK (skipped=1)
```

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。未提交。
