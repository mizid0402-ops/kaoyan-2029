# Round 113 — WP-E5b 时间线复习分钟生效

## 改动文件

- `ky/schedule/budget.py`：M8 `DayBudget`、`resolve_day_budget()`、`hard_review_cap_minutes()` 与精确有理数最大余数缩放。
- `ky/schedule/review_clip.py`：M9 分科配额裁剪、配额/已用分钟结果字段，以及仅在给定配额时输出新增 JSON 键。
- `ky/models.py`：将精确分钟缩放公开为 `scale_minutes()`，供 M8/M9 共用；既有内部调用保持原实现。
- `ky/__main__.py`：M14 preflight 按已发现工作区加载已登记当前路线；复用 M8 预算；阶段文本行仅在有配额时出现。
- `ky/planner/port.py`：M19 `_build_input_data()` 复用 M8 预算，并将可用时间来源、floor policy、路线配额传入裁剪。
- `contracts/route_plan.md`、`contracts/availability.md`、`contracts/planner_port.md`、`docs/模块地图.md`：补齐 D10 生效规则、共享缩放端口和模块说明。
- `tests/contract/test_day_budget_port.py`：WP-E5b 的 6 项端口契约测试。
- `tests/contract/test_planner_port.py`：路线测试夹具为每个当前在考科目提供分钟，保持其余既有样例值。

## 设计落点

1. **M8 当日预算**：`resolve_day_budget()` 先复用 M26 `resolve_daily_minutes()` 选择总时长和来源，再查找日期命中的半开阶段。没有路线/没有命中阶段返回 `subject_review_quotas=None`。命中时检查未知 ID、在考科目缺项、未启用科目正数；未知/缺项错误带 `route.phases[i].review_minutes.<id>` 路径，缺项消息使用任务书指定中文。路线配额超过当日硬上限时以 `Fraction` 精确缩放，余数相同时按科目 ID 排序。
2. **共享硬上限与 M9 裁剪**：`hard_review_cap_minutes()` 调用公开 `scale_minutes()`，M8 与 `select_daily_reviews()` 共用这一硬上限函数。传入配额时普通项须同时符合科目配额和全天硬上限；`_is_urgent` 紧急项可超本科配额，但仍受全天硬上限约束。`unschedulable` 原判定不变。配额存在时 `soft_target_minutes` 为配额和，并输出 `subject_review_quotas`、`subject_review_minutes`；配额为 `None` 时 `ClipResult.summary()` 不增加键。
3. **M14/M19 调用**：两者调用同一 `resolve_day_budget()`。仅 `total_source == "availability"` 时传 `daily_minutes_override` 并用 `floor_policy="drop_when_short"`。preflight 从发现到的注册表读取 `state.routes` 当前版本；阶段文本为 `timeline phase     : <序号> <标签> (<id>=<分钟> ...)`，科目按 ID 排序。M19 的 `review_clip` 继续由共用 `preflight_to_mapping()` 生成，并删去 `config`。
4. **规格**：RoutePlan 合同记录 D10 的阶段边界、配额校验、紧急规则、硬上限缩放、消费者和文本格式；availability 与 planner port 合同注明合并行为和共享输出。

## 固定基线逐字节对照

测试固定使用任务起点提交 `20f4391e2bce55a86d42fbd9bd48708d1177cd42`，不使用 `HEAD`。测试通过 `git show <固定哈希>:<文件>` 读取旧版，并先断言旧版源码含旧解析调用且不含 `resolve_day_budget`，防止取到新版冒充基线。对“无路线”及“注册路线但当天在时间线外”两种输入，使用同一配置、复习队列、日期和注册表分别运行旧/新 preflight，原始 stdout、stderr（含 JSON 与文本）逐字节比较；planner 输入包分别由旧/新 `_build_input_data()` 构造，再用其正式规范序列化函数比较完整 UTF-8 JSON 字节。

## 测试及撤回检查

- `test_unconstrained_clipping_matches_fixed_baseline_bytes`：固定基线断言及原始字节比较；完整撤回 M8 新 API 会使测试模块导入失败。单独撤回 M14/M19 的新调用可能仍保留旧路径字节，因此该测试的直接目标是无配额路径的零差异；消费者功能由下列第 5、6 项覆盖。
- `test_phase_quotas_gate_regular_items_and_allow_urgent_borrowing`：断言零配额普通项延期、其余普通项按配额入选、紧急项可借用且不超硬上限；撤回分科判断或紧急规则会使断言失败。
- `test_oversized_quotas_scale_to_hard_cap_deterministically`：断言总和等于硬上限、重复解析一致，并钉住等余数按 ID 决胜；撤回缩放或排序规则会失败。
- `test_availability_total_and_route_quotas_resolve_independently`：preflight 与输入包同时断言手填总时长、阶段缩放配额和一致的 `review_clip`；撤回任一消费者传递会失败。
- `test_invalid_route_subject_minutes_are_preflight_contract_errors`：缺项、未知 ID、未启用科目正数均断言退出码 2、契约错误且无 traceback；撤回对应校验/CLI 处理会失败。
- `test_planner_review_clip_matches_preflight_with_phase_quotas`：有阶段配额时断言输入包 `review_clip` 等于 preflight JSON 去掉 `config` 后的对象；撤回 M19 路线配额集成会失败。

## 验收输出

```text
py -3.12 -m unittest tests.contract.test_route_plan_port tests.contract.test_availability_port tests.contract.test_planner_port tests.test_review_scheduler tests.test_contracts tests.test_cli
Ran 198 tests in 28.928s
OK

py -3.12 -m unittest tests.contract.test_day_budget_port
Ran 6 tests in 3.630s
OK

git diff --check
OK
```

含中文文件的连续问号检查未发现异常。全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。未提交。

## 建议

- 无新增建议。测试夹具因 D10 的“每个在考科目必填”约束扩充为配置驱动的全部在考科目；其余原有数学/英语配额保持不变。
