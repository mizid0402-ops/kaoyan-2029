# WP-G3b 拆分验证报告

## 改动

只拆分 `ky/models.py` 中的 `validate_config`、`validate_review_item`，新增固定基线对照测试，
并按顺带要求更新 G3a workspace 对照测试。公开函数签名、其他实现函数和契约文档未改。

配置校验按原顺序调用：根映射与未知键、schema、复习策略、预算字段及比例关系、科目解析、
科目 ID 唯一性、活跃科目、活跃权重和、单科分钟下限、总预算可行性，最后组装 `KaoyanConfig`。

复习项校验按原顺序调用：标签与映射、标识字段、granularity/state、单次耗时、日期与先后、
schedule、defer_count、last_quality/self_rating、vocabulary_batch 限制，最后组装 `ReviewItem`。

拆出函数（本轮 AST 统计行数）：

| 函数 | 行数 | 职责 |
|---|---:|---|
| `_config_root` | 4 | 校验根映射和未知字段 |
| `_config_schema_version` | 5 | 校验 schema 版本 |
| `_config_self_rating_mode` | 9 | 校验复习策略 |
| `_config_budget_fields` | 31 | 解析预算值并检查比例关系 |
| `_config_subjects` | 7 | 校验科目列表并解析档案 |
| `_check_unique_subject_ids` | 8 | 拒绝重复科目 ID |
| `_active_subjects` | 5 | 取得活跃科目并拒绝空集 |
| `_check_active_weight_total` | 6 | 校验活跃权重总和 |
| `_check_subject_minimums` | 10 | 校验单科分钟下限 |
| `_check_floor_room` | 13 | 校验科目下限与复习硬上限能否共存 |
| `validate_config` | 23 | 按原序编排校验并组装结果 |
| `_review_item_label` | 2 | 生成复习项错误路径前缀 |
| `_review_item_identity` | 11 | 校验复习项标识字段 |
| `_review_item_categories` | 14 | 按序校验 granularity 与 state |
| `_review_item_estimated_minutes` | 11 | 校验单次耗时及上限 |
| `_review_item_dates` | 21 | 解析日期并检查先后关系 |
| `_review_item_feedback` | 18 | 校验质量分与自评 |
| `_check_vocabulary_minutes` | 6 | 校验词汇批次耗时限制 |
| `validate_review_item` | 33 | 按原序编排校验并组装结果 |

所有新拆出的校验函数均不超过约 60 行；主函数只做编排和结果组装。

## 固定基线对照

`tests/contract/test_models_split_baseline.py` 使用 `git show b97f3ac:ky/models.py`，并断言
旧版 `validate_config` 超过 90 行，再将旧实现作为独立模块加载。合法结果递归比较 dataclass
字段；非法输入比较异常类型名、`str(exc)` 和 `path`。每个种子及变体均显式带有成功/失败预期，
失败预期还断言新实现抛出 `ContractError`。

- 配置种子产生 62 个变体：6 个预期成功，56 个预期失败。覆盖根字段缺失、科目字段缺失、
  策略字段、类型错误、边界与 NaN/Inf、布尔冒充整数、未知键、重复科目、活跃权重不闭合、
  比例倒置、预算下限冲突和两处同时出错的顺序探针。
- 复习项种子产生 57 个变体：3 个预期成功，54 个预期失败。覆盖每个复习项字段缺失、每个
  schedule 字段缺失、类型错误、范围与 NaN、未知键、日期先后颠倒、枚举错误、词汇批次耗时
  及标识/类别/日期的多错误顺序组合。
- 总计 119 个变体和 2 个原始种子。科目 ID 和科目数量由 fixture 数据读取；测试不固定其值。

G3a 的 `tests/contract/test_workspace_split_baseline.py` 现在也给每个变体标注并断言预期状态：
55 个变体中，`supplementary`、`products`、`settings` 缺失这 3 个预期成功，其余 52 个预期失败。
加上合法原始种子，共比较 56 个输入。

## 撤修改验证

临时将 `_review_item_categories` 中 granularity 与 state 的检查顺序对调，运行：

```text
py -3.12 -m unittest tests.contract.test_models_split_baseline
```

结果：`Ran 1 test`，`FAILED (failures=1)`，失败变体为 `review-category-order-probe`。
基线先报 `items[0].granularity`，临时版本先报 `items[0].state`，对照按异常消息和路径变红。
随后已恢复原检查顺序。

## 验收

执行命令：

```text
py -3.12 -m unittest tests.test_contracts tests.test_review_scheduler tests.contract.test_models_split_baseline tests.contract.test_workspace_split_baseline
```

结果：`Ran 104 tests in 1.586s`，`OK`。

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。

## 建议

本轮未发现需要扩大到其他模块的改动；按仓库规则由决策者在提交前统一运行全量测试。
