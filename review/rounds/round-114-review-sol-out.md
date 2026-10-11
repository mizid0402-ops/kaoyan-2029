# Round 114 Codex 独立评审：WP-E5b

范围：`git diff 653e63b^1 653e63b`（含实现提交 `1df327c`）；运行环境为 `git archive 653e63b` 的系统临时目录，补入本机 `data/raw_materials/`、创建空 `products/`，固定基线测试通过 `GIT_DIR` 指向原仓库。只运行相关模块。

## 1. `resolve_day_budget`（不改）

`ky/schedule/budget.py:61-126` 用 `resolve_daily_minutes` 取得手填或配置总时长，阶段判断为 `start <= day < end_exclusive`；按配置在考科目验证未知、缺项和未启用科目正数，错误路径为 `route.phases[i].review_minutes.<id>`。超额时以 `Fraction` 做最大余数分配，同余数按 ID 排序；M8 与 M9 共用 `hard_review_cap_minutes`（`ky/schedule/review_clip.py:322`）。归档探针构造两段 `[9/15,9/17)`、`[9/17,9/19)`：9/14、9/19 无配额，9/15、9/16 命中 0 段，9/17、9/18 命中 1 段。手填 0/60/120 分钟且阶段各科 50 分钟时，配额和与裁剪硬上限分别同为 0/36/72。`tests/contract/test_day_budget_port.py:186-254` 也覆盖同余数、无效科目与手填缩放。

## 2. 分科裁剪及 D10 细则（建议改）

实现符合已定细则：`ky/schedule/review_clip.py:347-369` 对普通项同时查本科已用和全天硬上限，紧急项只受全天硬上限约束，入选后仍记入本科实际已用；`unschedulable_cap = max(config cap, today cap)` 未变（同文件 `:325`）。原有会计桶检查仍在 `:398-418`。现有测试 `tests/contract/test_day_budget_port.py:160-184` 验证零配额普通项延期、紧急项借用及全日上限。

**规则风险，非实现偏差**：若 A 科持续有排在前面的紧急积压，A 可每天占满全日硬上限，B 科即使有正配额也持续延期。建议在后续决议中明确是否容许长期借用，以及是否需要借用债务或连续挤占提示；本提交不应擅自改变 D10 排序。

另一个端口错误分类建议修：直接调用 `select_daily_reviews(config, (), day, subject_review_quotas={"math1": "2"})`，`ky/schedule/review_clip.py:324` 先 `sum()`，在 `:334-339` 的 `ContractError` 校验前抛出 `TypeError`。归档中已复现。已存储的路线经 `parse_route_plan` 拒绝此值，因此不是正常 CLI 路径；将逐项校验移到求和前可使公开端口一致地报带路径契约错误。测试应断言错误类型和 `subject_review_quotas.math1`。

## 3. 无路线／时间线外逐字节保持（不改）

`tests/contract/test_day_budget_port.py:26,120-158` 固定旧版 `20f4391e2bce55a86d42fbd9bd48708d1177cd42`，先断言取到的旧源码确含 `resolve_daily_minutes` 且不含新解析器；分别在“未登记路线”和“已登记路线但当天在范围外”比较新旧 `preflight` 的 JSON、文本原始 stdout/stderr 和退出码，并用正式规范序列化比较完整日输入包字节。归档运行该模块 6/6 通过。此对照对两种要求场景有效；旧源码调用的其他模块仍是归档版本，因此它不是整个旧版依赖树的冻结测试。

## 4. 有配额时 JSON、输入包和文本（**必须改**）

静态路径上，`ClipResult.summary()` 仅在配额非 `None` 时增加两个键（`ky/schedule/review_clip.py:164-167`）；`preflight` 与 M19 都调用 M8 及共用 `preflight_to_mapping`，文本阶段行按 ID 排序（`ky/__main__.py:265-333`）。`tests/contract/test_day_budget_port.py:203-224,256-270` 的静态快照比较通过。

但 **M19 两次读取当前路线，可能产出自相矛盾的输入包**：`ky/planner/port.py:45` 取一次供配额裁剪，同文件 `:78,82-87` 经 `_route_plan_for_day` 再取一次供 `route_plan.phase`。归档探针以 `patch.object(RoutePlanStore, "current", side_effect=[r1, r2])` 模拟两次读取间发布新修订：r1 各在考科目 0 分钟，r2 各 20 分钟。`planner_input_data()` 成功返回，但 `review_clip.subject_review_quotas == {"cs408": 0, "eng1": 0, "math1": 0}`，同时 `route_plan.phase.review_minutes == {"math1": 20, "eng1": 20, "cs408": 20}`。这破坏单一输入包的路线与裁剪一致性，哈希仍会为该矛盾包生成。最小修法：在 `_build_input_data` 中只取一次 `RoutePlan`，把同一对象交给预算解析和 `_route_plan_for_day` 的映射构造；增加两次读取诱饵测试，要求最多读取一次、两字段来自同一修订。

文本虽符合新增行规格，`ky/__main__.py:318-321` 在配额生效时仍把 `soft_target_minutes` 后标成配置 `review_reserve_ratio`，例如阶段配额和为 30、配置比率为 0.45 时显示 `30 / 72 min (ratio 0.45 / 0.6)`。这是展示误导，建议另行改为标明阶段配额来源，不影响本轮阻断判断。

## 5. `scale_minutes` 与依赖方向（不改）

`ky/models.py:41,371-385,541` 将原私有函数直接改为公开 `scale_minutes`，M8、M9、配置验证与本包改过的测试同步；归档 `rg -n '_scale_minutes' --glob '!review/**' --glob '!docs/**' --glob '!data/**' .` 无残留调用。依赖为 `review_clip → budget → availability/planning/models`，未见反向导入；相关模块能正常导入，归档单跑 `tests.test_review_scheduler` 38/38、`tests.contract.test_planner_port` 28/28。

## 6. 回归测试强度（建议改）

归档单跑 `tests.contract.test_day_budget_port` 6/6。撤回普通项本科配额判断（临时把 `if subject_review_quotas is not None and not urgent` 改为恒假）后，`test_phase_quotas_gate_regular_items_and_allow_urgent_borrowing` 确实变红：零配额普通项错误入选；恢复原文件后不留修改。固定基线测试也有旧源码身份断言，强度足以抓住无路线／范围外输出回退。缺少第 4 项“两次路线读取”的诱饵测试、阶段首尾日断言，以及公开裁剪端口的非法配额类型断言；建议随对应修复补齐，毋须扩展为全量测试。

## 结论

**FAIL**。核心分科规则及固定基线对照成立，但 M19 的双次路线读取能把不同修订混进同一个日输入包；修复并锁住该一致性后可复审。未跑全量测试（按 `AGENTS.md`）。
