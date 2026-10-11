# Round 139 Codex：WP-G3b 评审

## 范围与验证

固定提交 `e403b1e`。用 `git archive` 展开到系统临时目录，在副本中补入 `data/raw_materials`（47 个文件，73,005,384 字节）和注册表指向的 `review/408知识点树与真题` 空目录；所有探针及临时变异只在副本运行。`git show` 通过 `GIT_DIR` 读取固定 Git 对象。未跑全量，也未改主仓库实现。

`py -3.12 -m unittest tests.test_contracts tests.test_review_scheduler tests.contract.test_models_split_baseline tests.contract.test_workspace_split_baseline` → **104 项 OK**。临时变异后逐字节恢复 `ky/models.py`，并与 `git show e403b1e:ky/models.py` 比较确认相同；随后两个对照测试重跑 → **2 项 OK**。

## 必须改

### M1：对照测试未锁住跨校验段的首报顺序

位置：`tests/contract/test_models_split_baseline.py` 的 `_config_variants`、`_review_variants`。现有 119 个变体包括段内双错误，但没有让配置的 `review_policy` 与预算字段同时出错，也没有让复习项的日期与 `schedule` 同时出错；因此无法检测主函数调换这两段调用顺序，未满足任务书关于“多处出错时先报哪一处”和“组合”的对照要求。

可复现输入与实测：

1. 从 `config-minimal.yaml` 复制字典，设 `review_policy: {self_rating_mode: invalid}`、`project_id: 42`。固定旧版和提交版均先报 `ContractError`，路径 `review_policy.self_rating_mode`。在**临时副本**仅把 `validate_config` 中 `_config_self_rating_mode(root)` 与 `_config_budget_fields(root)` 的调用次序对调，首报改为 `project_id`，但运行 `py -3.12 -m unittest tests.contract.test_models_split_baseline` 仍 **1 项 OK**。
2. 从 `reviews-normal.yaml` 的首条 item 复制字典，设 `due_date = introduced_on - 1 天`、`schedule = []`。固定旧版和提交版均先报 `items[0].due_date`。在临时副本仅把 `_review_item_dates` 与 `_load_schedule` 的调用次序对调，首报改为 `items[0].schedule`，同一对照测试仍 **1 项 OK**。

最小修法：按 fixture 规则生成跨相邻段的双错误样本，至少覆盖上述两对；继续比较固定旧版与新版的异常类型、完整消息及路径，并保留明确的失败预期。建议一并加入 `validate_config([], source="fixture-config")` 和 `validate_review_item([], index=0, source="fixture-review")`：两者旧新版目前分别同报 `fixture-config: expected a mapping, got list` 与 `items[0]: expected a mapping, got list`，但现有变体全部从映射种子复制，根映射校验的类型错误尚未进入对照。

## 建议改

| 项 | 可复现输入与理由 |
| --- | --- |
| 辅助函数名称更贴近职责 | `ky/models.py` 的 `_config_budget_fields` 从 `project_id` 一直解析到预算比例并返回四元组，`project_id` 不属于预算；`_review_item_identity` 还解析 `title`。在配置种子上仅把 `project_id` 改为 `42`，报错来自名为“budget”的函数。建议将名称改为能涵盖这些字段的名称，或在保持检查顺序的前提下分出短函数；这是可读性建议，不影响本轮行为门禁。 |
| 对照测试可明确检查变体名唯一 | 当前 `_config_variants` 与 `_review_variants` 分别产生 62、57 个唯一名称，本轮探针确认没有碰撞。后续按规则扩充时，可断言名称唯一，以免同名 `subTest` 难以定位；本轮不阻断。 |

## 不改

| 项 | 可复现输入与证据 |
| --- | --- |
| 提交版的合法结果与非法错误 | `test_models_split_baseline.py` 从固定 `b97f3ac:ky/models.py` 加载旧模块，并用 AST 断言旧 `validate_config` 超过 90 行。原样配置与首条复习项比较 dataclass 的所有字段；非法结果比较异常类型名、`str(exc)` 和 `path`，再断言新版异常是 `ContractError`。除上述缺少的跨段组合外，现有生成样本均与旧版一致，104 项定向测试通过。本轮另手工比较“策略+项目 ID”“科目 ID+权重”“日期+schedule”“类别+日期”四组双错误，旧新版的首报异常完全相同。未发现实现行为回归。 |
| 变体来源与成功/失败标注 | 配置种子生成 62 个、复习项种子生成 57 个变体；科目 ID、科目数量及字段集合取自 fixture 和旧版常量，没有写死当前科目。逐个运行现版后，62 个配置变体确为 **6 成功 / 56 失败**，57 个复习项变体确为 **3 成功 / 54 失败**；名称均唯一。测试对每例断言预期成功或失败，且失败须为契约错误。 |
| 第 135 轮 G3a 建议 | `tests/contract/test_workspace_split_baseline.py` 已把每个变体标为预期成功/失败，并断言新版结果符合标注。以归档注册表生成的 55 个变体中，缺失 `supplementary`、`products`、`settings` 的 3 个标成功，其他 52 个标失败；加原样种子共 56 组。`py -3.12 -m unittest tests.contract.test_workspace_split_baseline` 通过。 |
| 拆分边界与顺序 | `validate_config` 依次调用根、schema、策略、预算、科目、唯一性、活跃权重、分钟下限和预算可行性检查；`validate_review_item` 依次校验标识、类别、耗时、日期、schedule、延后次数、反馈与词汇批次上限。新辅助函数均短于约 60 行，没有增加跨模块私有依赖。原有 `schedule` 解析继续调用 `_load_schedule`。命名建议如上，不构成行为缺陷。 |

## 安全登记

本轮未发现仅靠恶意构造、内部文件篡改或精确并发交错才触发的新增安全问题。

## 结论

**FAIL。**实现行为在已测输入及手工跨段探针中与固定旧版一致；对照测试仍会放过会改变双错误首报位置的段间顺序回归。补足 M1 的变体后，只需重跑本包任务书指定的定向模块。
