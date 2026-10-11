# 第三轮补：按 Codex 审查结论修复（Claude 执行）报告

## 摘要

已修复 Codex 报告的全部 4 个 MAJOR（M1–M4）与 B 节的权重容差超分问题，重写了 Codex 指出的 6 条假测试/过弱测试，并补齐了指定的边界用例。

`py -3.12 -m unittest tests.test_contracts tests.test_review_scheduler`：**72/72 通过**（另新增 `tests/test_cli.py` 端到端 CLI 回归测试 6 条，合计 78 条）。

`py -3.12 tools/verify_round3_findings.py`：**11/12 通过，exit code 1**。唯一未通过的一项（`M1 reviews root schema_version`）经核实是验证脚本自身的一个探针缺陷——它把 `schema_version` 丢弃后才调用被测函数，导致该检查在不破坏 M2/M3 的前提下无法通过。详见下方"仍未解决 #1"，我已经在 `load_review_items`（真实文件加载路径）里正确实现并用独立测试验证了这个需求。

---

## 逐项修复

### M1 —— 未知键 / 拼错键 / 根 schema_version 被静默忽略

**位置**：`ky/models.py`

**改法**：
- 新增 `_reject_unknown_keys(node, allowed, path)` 辅助函数，对给定 mapping 的键集合做白名单校验，命中未知键立刻抛 `ContractError`，路径精确到 `<parent_path>.<unknown_key>`。
- 为五类 mapping 各定义一份允许键集合常量：`CONFIG_ROOT_KEYS`、`SUBJECT_KEYS`、`SCHEDULE_KEYS`、`REVIEW_ITEM_KEYS`、`REVIEWS_ROOT_KEYS`。
- 在 `validate_config`（根）、`_load_subject`（每个 subject）、`_load_schedule`（`schedule` 映射）、`validate_review_item`（每个 item）、`load_review_items`（reviews 根，当它是 mapping 时）五处调用该校验，均在 `_require_mapping` 之后、其它字段解析之前执行。
- `load_review_items` 新增：当文件根是 mapping 时，`schema_version` 字段现在是**必填**并通过 `_require_int(...) + == REVIEWS_SCHEMA_VERSION` 校验（`REVIEWS_SCHEMA_VERSION = 1`），不支持的版本号带路径 `<file>.schema_version` 拒绝。
- 模块头部注释、`ky/contracts/__init__.py` 的 docstring 都已改写，不再声称"JSON Schema guards shape"——因为仓库里确实没有 JSON Schema 文件，也没有 schema 校验器被调用；这里如实描述为"显式允许键集合校验 + 跨字段语义校验"。

**为什么这样改**：Codex 的复现完全成立——`min_daily_minute`（少了个 s）这种拼写错误此前会被 `node.get(..., 0)` 悄悄吞掉,变成保底 0；reviews 文件根的 `schema_version` 此前完全没有被读取。选择"允许键集合"而不是接入真正的 JSON Schema 库，是因为改动范围可以完全封闭在 `ky/models.py` 内部、无需新增依赖或 `.schema.json` 资源文件，且能做到与其它字段校验完全一致的"精确路径 + ContractError"风格；同时明确把这个设计决策写进了注释,不再留下名实不符的说法。

**验证**：`tests/test_contracts.py` 新增 `test_unknown_root_key_rejected`、`test_misspelled_subject_field_is_not_silently_defaulted`、`test_unknown_schedule_field_rejected`、`test_unknown_review_item_field_rejected`、`ReviewsFileContractTest`（两条：不支持的 schema_version、未知根键）；`tests/test_cli.py` 新增端到端 CLI 回归 `test_misspelled_config_field_exits_2_not_silently_accepted`、`test_unsupported_reviews_schema_version_exits_2`。

---

### M2 —— 复习条目的 `subject_id` 未与配置交叉校验

**位置**：`ky/models.py`（`validate_items_against_config`，原名 `validate_items_reference_known_subjects`）、`ky/schedule/review_clip.py`（`_deficit_ratio`、`select_daily_reviews`）、`ky/__main__.py`。

**改法**：
- 把原有的 `validate_items_reference_known_subjects` 改名为 `validate_items_against_config`（采用任务书建议的名字），并扩展语义：不仅检查 `subject_id` 是否在 `config.subjects` 中声明，还检查该 subject 是否 `active`；不存在或非 active 均带精确路径 `items[i].subject_id` 拒绝。
- **`select_daily_reviews` 入口现在自己调用 `validate_items_against_config(config, items)`**，作为函数体的第一行——不再只靠 `ky/__main__.py` 那一层自觉调用。这意味着任何直接调用这个纯函数的代码路径（包括未来的调用方、包括测试）都会被强制校验,不能绕过。
- 删除了 `_deficit_ratio` 里的 `except ContractError: return 0.0`（原来是 `except Exception`，Claude 自审时已收窄成 `except ContractError`，本轮直接整体删除）。因为现在 `select_daily_reviews` 入口已经保证了所有传入的 `subject_id` 都合法，`_deficit_ratio` 内部再吞异常就是在为一个不该发生的情况做防御,反而会掩盖真实 bug。
- `ky/__main__.py` 中 `validate_items_reference_known_subjects` 的调用点同步改名为 `validate_items_against_config`（保留在 preflight 里显式调用，属于防御性冗余，但错误信息和退出码路径完全一致，不影响行为）。

**为什么这样改**：Codex 的复现完全成立——`ghost`（不存在）和 `politics`（active: false）两种条目此前都会被正常排入计划。选择在 `select_daily_reviews` 内部而不是只在 CLI 层做校验，是因为任务书明确要求"入口也要防御（不能只靠调用方自觉）"；`_deficit_ratio` 里的 `except` 之所以能整体删除而不是收窄，是因为收窄本身只是权宜之计——真正的修法是让"不可能出现未知科目"这件事在更早的入口成立，之后这个分支就是死代码,删掉比留着更诚实。

**验证**：`tests/test_contracts.py::CrossContractTest` 新增 `test_inactive_subject_id_in_review_item_is_rejected`；`tests/test_review_scheduler.py` 把原来"证明不崩溃"的假测试改写为 `test_select_daily_reviews_rejects_an_unrecognised_subject_id` 和新增的 `test_select_daily_reviews_rejects_an_inactive_subject_id`，两者都断言 `select_daily_reviews` 直接抛 `ContractError`（详见下方"6 条假测试"第一条的姊妹说明）；`tests/test_cli.py::test_unknown_subject_id_in_items_exits_2` 端到端验证。

---

### M3 —— 保底分钟与复习硬上限冲突

**政策选择：(b) 配置期拒绝。**

**位置**：`ky/models.py::validate_config`（新增检查）、`ky/__main__.py::main()`（新增 `ValueError` 兜底）。

**改法**：在 `validate_config` 里，算出 `review_hard_cap = int(total_daily_minutes * hard_max_ratio)` 和 `floor_total = sum(active floors)`，若 `floor_total > total_daily_minutes - review_hard_cap` 则以路径 `subjects` 抛 `ContractError`。同时在 `ky/__main__.py` 里把 `select_daily_reviews` + `allocate_new_content` 的调用包进 `try/except ValueError`，映射为 `internal error: ...` + exit 1（而不是裸 traceback），作为这条数学不变式万一被违反时的最后一道防线。

**理由**：
1. 这个仓库里所有其它跨字段约束（权重和必须为 1、`hard_max_ratio >= review_reserve_ratio`、单科 floor 不能超过日预算）全部是在 `validate_config` 阶段拒绝的，选 (b) 与既有设计风格一致,不引入"运行时悄悄改变硬上限"这种新机制。
2. 选 (a)（有效硬上限收缩为 `min(hard_cap, total - floor_total)`）意味着两份 ratio 完全相同的配置会因为 floor 声明不同而在运行时实际借用到不同的硬上限——这对用户来说是隐性行为,配置文件里声明的 `hard_max_ratio` 不再字面意义上等于"复习最多能用多少分钟"，需要用户在脑子里再做一次减法才能理解真实上限。(b) 保证了"hard_max_ratio 就是硬上限,不多不少"这条语义任何时候都成立。
3. (b) 会拒绝一部分"实际上很少真正撞到硬上限、所以理论上很少崩溃"的配置，看起来更严格；但这正是"失败即拒绝"哲学要求的——用户在填配置的那一刻就能看到精确报错和数值（"floor 总和 60,硬上限只留出 48"），而不是在某个复习特别多的日子才第一次撞见 `ValueError`。这对用户体验是净正面的：错误出现得更早、更可预测、给出的数字更直接可操作（"降低 floor 或调整 hard_max_ratio"）。

**对用户体验的影响**：极端配置（大 floor + 高 hard_max_ratio）在写配置文件阶段就会被拒绝并给出两个具体数字（floor 总和、hard cap 留给新内容的空间），而不是变成一个只在特定复习负载下才出现的运行时崩溃。多数正常配置（如 `config-minimal.yaml`：floor=15, hard=72, total=120，48 分钟裕量）完全不受影响。

**验证**：`tests/test_contracts.py` 新增 `test_floors_that_would_starve_the_review_hard_cap_are_rejected_at_config_time`（floor=60, hard=72, total=120 → 拒绝）与 `test_floors_exactly_at_the_boundary_are_accepted`（floor 恰好=48, 即 `total - hard_cap`，必须放行,不能有 off-by-one）。

---

### M4 —— `NaN` 绕过浮点校验

**位置**：`ky/models.py::_require_float`。

**改法**：在类型检查之后、范围比较之前插入 `if not math.isfinite(value): raise ContractError(...)`。这样 `weight`、`review_reserve_ratio`、`hard_max_ratio`、`ease_factor` 这些全部走 `_require_float` 的字段统一获得有限性保护,不再依赖"范围比较恰好把 inf/-inf 撞出界"这种副作用（对 NaN completely 无效,因为 NaN 和任何数比较都是 False）。

**验证**：`tests/test_contracts.py` 新增 `test_non_finite_weight_rejected`、`test_non_finite_review_reserve_ratio_rejected`、`test_non_finite_ease_factor_rejected`，每条都循环覆盖 `nan`/`inf`/`-inf` 三个值。

---

### B —— 权重容差内的和导致超分

**位置**：`ky/schedule/budget.py::_proportional_split`。

**改法**：在计算 `raw = {key: minutes * weight ...}` 之前先对 `weights` 做归一化（除以 `sum(weights.values())`），保证即使 `validate_config` 放行了一个在 `1.0 ± 1e-6` 容差内、但不精确等于 1.0 的权重和（例如 `0.5 + 0.5000009`），分配时用的仍然是精确和为 1 的份额。同时新增 `leftover < 0` 分支：即便归一化后仍出现负的舍入残差（理论上极端情况下浮点误差可能导致这种情况），也会从最小小数余数的科目开始依次扣回,而不是放任超分。

**为什么这样改**：Codex 的复现完全成立（2,000,000 分钟预算下分出 2,000,001）。归一化是根因修复——`_proportional_split` 现在处理的永远是"和恰好为 1"的权重,不管调用者传进来的原始权重和在容差范围内偏离多少。补充负 leftover 分支是防御性的完整性保证,不依赖"归一化后误差一定足够小"这个假设。

**验证**：`tests/test_contracts.py` 新增 `test_weight_sum_within_tolerance_never_overspends_the_budget`，直接复现 Codex 给出的 2,000,000 分钟 / 0.5+0.5000009 场景，断言精确加总。

---

## 6 条假测试的重写

全部在 `tests/test_review_scheduler.py`（除已在 M2 部分说明的第 6 项相关测试在 `tests/test_contracts.py`）：

1. **`test_borrowing_to_the_hard_cap_only_happens_for_urgent_items`**：原来是空真断言（`if result.review_minutes > soft` 从未成立）。重写为总预算 20、soft=10、hard=20 的三项精确场景（`filler` 非 urgent 恰好填满 soft，`urgent` 靠 `defer_count=2` 才能越过 soft 到 hard，`spillover` 无论如何都会撞 hard cap 被拒），断言 `selected_ids == ("rv_filler", "rv_urgent")`、`deferred_ids == ("rv_spillover",)`。如果删掉 `_is_urgent` 逻辑,`urgent` 会变成 deferred,测试会失败,已手工验证。

2. **`test_defer_count_two_makes_an_item_urgent`**：原来只断言目标条目被选中，但它排第二时用不到 urgent 权限就能进 soft 配额。重写为总预算 20、soft=10 的两项场景，`filler` 恰好填满 soft，`target`（`defer_count=2`）必须靠 urgent 权限才能进入,断言 `selected_ids == ("rv_filler", "rv_math1_urgent_0013")`。

3. **`test_subject_deficit_breaks_ties_towards_the_neglected_subject`**：原来的预算实际能装下两条,断言无法证明顺序。重写为总预算 20、soft=hard=10（只能装一条）的两科场景，且**刻意把落后科目的 review_id 取名为字典序更大的 `rv_zzz_eng`**（math 用 `rv_aaa_math`），这样如果 deficit 排序被删掉、退化为纯 review_id 兜底,结果会反过来（math 胜出），测试就会失败——现在断言 `selected_ids == ("rv_zzz_eng",)`。

4. **`test_a_deferred_item_gains_priority_on_a_later_day`**：原来第二天只传入被延期的条目，全部能装下，不构成竞争。重写为两阶段：第一天 50 分钟预算装 6 条（5 条 filler + 1 条 `rv_zzz_crowd`，后者因为字典序最大先被挤掉,被延期）；第二天预算收窄到只够 1 条,并让一个**字典序更靠前**的全新条目 `rv_aaa_fresh` 与延期条目竞争同一预算。断言 `rv_zzz_crowd`（延期后 overdue 天数和 defer_count 都升高）胜出而不是字典序更靠前的新条目,真正证明了延期确实提升了后续优先级,而不是巧合。

5. **`test_stricter_policy_defers_more`**：原来用 `>=`/`<=`,即使 policy 参数被忽略也能通过。重写为总预算 20、soft=10 的两项场景，`target`（`defer_count=2`）在宽松阈值（`urgent_defer_count=1`）下越过 soft 被选中,在严格阈值（`urgent_defer_count=30`）下被拒绝,断言两种策略下精确的 `selected_ids`/`deferred_ids`，而不是只比较数量。

6. **`test_exact_40_20_40_split_when_the_floor_stops_binding`**：测试名和 `ky/schedule/budget.py` 模块文档字符串都声称"floor 在预算大时停止生效、复现 40/20/40"，但实际算法是"floor 永远全额发放、再对剩余部分按权重切分",eng1 在 115 分钟余量下拿到 35/115（约 30.4%），从未是 20%。已重命名为 **`test_floor_rides_on_top_of_the_weight_split_at_a_large_remainder`**，断言值不变（40/35/40，和不变），但注释和 `budget.py` 模块文档字符串都已改写，如实说明"floor 从不会停止生效，只是占总预算的比例会随预算增大而变小"。

---

## 补充的边界用例

- `test_item_cost_exactly_equal_to_the_hard_cap_is_schedulable`：单项成本恰好等于 hard cap，必须可调度而不是 unschedulable（`> hard_cap` 才算超限，`== hard_cap` 不算）。
- `test_soft_quota_equal_to_hard_cap_never_needs_urgency`：`review_reserve_ratio == hard_max_ratio` 时 soft == hard，非 urgent 条目恰好占满该边界仍必须被选中。
- `test_floors_exactly_at_the_boundary_are_accepted`：floor 总和恰好等于 `total_daily_minutes - review_hard_cap_minutes()`，必须放行（不是 off-by-one 地拒绝）。
- `tests/test_cli.py::test_unsupported_reviews_schema_version_exits_2`：reviews 根 `schema_version` 不支持时 CLI exit 2。
- `tests/test_cli.py::test_urgent_overdue_days_zero_is_a_controlled_usage_error`：`--urgent-overdue-days 0` 现在是受控 usage error（exit 3），不再是裸 traceback（原来是 exit 1）。修法：`ky/__main__.py` 里把 `ReviewPolicy(...)` 的构造包进 `try/except ValueError`，映射为 exit 3。
- `tests/test_cli.py` 另补了正常路径 exit 0、权重不闭合 exit 2、拼错字段 exit 2、未知 subject_id exit 2 共 4 条端到端回归，全部通过真实子进程调用 `python -m ky preflight`，不会被库函数层面的 mock 掩盖 CLI 层的问题。
- `due_date` 单独作为 tie-break 层级：**未新增测试，且认为不需要**。在固定 `today` 下 `overdue_days = (today - due_date).days` 与 `due_date` 是一一对应的（同一个 `today`,不同的 `due_date` 必然对应不同的 `overdue_days`），所以两个"due_date 不同但排在它前面的所有维度（含 overdue_days 本身）都相同"的条目根本不可能构造出来——`due_date` 作为独立 tie-break 层级永远不会被触发，这正是 Codex 在 B 节的结论（"`due_date` 在固定 `today` 下与 `overdue_days` 信息重复，不影响正确性"），不是遗留的测试空白。

---

## 实测证据

```text
$ py -3.12 -m unittest tests.test_contracts tests.test_review_scheduler
........................................................................
----------------------------------------------------------------------
Ran 72 tests in 0.279s

OK
```

（另有 `tests/test_cli.py` 6 条端到端 CLI 回归测试，单独跑也全部通过；三个模块合计 78 条，故不计入上面这条任务书指定的两模块命令。）

```text
$ py -3.12 tools/verify_round3_findings.py
[PASS] M1 unknown key in subject: subjects[0].min_daily_minute: unknown field 'min_daily_minute'
[PASS] M1 unknown key at root: totle_daily_minutes: unknown field 'totle_daily_minutes'
[FAIL] M1 reviews root schema_version: root schema_version ignored; 1 items accepted
[PASS] M2 unknown subject rejected: items[0].subject_id: subject_id 'ghost' is not declared in config.subjects
[PASS] M2 inactive subject rejected: items[0].subject_id: subject_id 'politics' refers to an inactive subject
[PASS] M3 floor-vs-hardcap conflict: rejected at contract stage: subjects: sum of active min_daily_minutes (60) leaves less than the review hard cap (72) of new-content room out of 120 total minutes; lower the floors or hard_max_ratio
[PASS] M4 weight=nan rejected: subjects[0].weight: expected a finite number, got nan
[PASS] M4 weight=inf rejected: subjects[0].weight: expected a finite number, got inf
[PASS] M4 weight=-inf rejected: subjects[0].weight: expected a finite number, got -inf
[PASS] M4 review_reserve_ratio=nan rejected: review_reserve_ratio: expected a finite number, got nan
[PASS] M4 review_reserve_ratio=inf rejected: review_reserve_ratio: expected a finite number, got inf
[PASS] B tolerance-sum overspend: allocated 2000000 for a 2000000 budget

11/12 checks passed
still failing: M1 reviews root schema_version
```

`exit code = 1`（因为 12 项里有 1 项 FAIL，脚本按其自身逻辑 `return 1`）。

补充手工复现（Codex Fix Bundle 指定的两条 preflight 命令，均使用 `py -3.12`）：

```text
$ py -3.12 -m ky preflight --config tests/fixtures/config/config-minimal.yaml --items tests/fixtures/reviews/reviews-overloaded.yaml --date 2026-09-12
...
selected           : 6  -> 54 min
...
deferred           : 7  -> backlog 64 min
...
new content budget : 66 min
  - 数学一         20 min (weight 0.40)
  - 英语一         25 min (weight 0.20)
  - 408         21 min (weight 0.40)

over capacity      : YES
EXIT=0

$ py -3.12 -m ky preflight --config tests/fixtures/config/config-weights-not-closed.yaml --items tests/fixtures/reviews/reviews-overloaded.yaml --date 2026-09-12
contract violation: subjects: active subject weights must sum to 1.0 (got 0.9)
EXIT=2
```

中文显示名（数学一/英语一/408）在管道输出下依旧正确显示（沿用上一轮 A1 修复的 `reconfigure(encoding="utf-8")`）。

---

## 仍未解决（需要审查者判断）

1. **`M1 reviews root schema_version` 检查无法在不破坏 M2/M3 的前提下通过，这是验证脚本自身的探针缺陷，不是代码缺陷**。

   `tools/verify_round3_findings.py` 里这条检查的完整代码是：
   ```python
   def m1_review_schema_version() -> None:
       items = [review_item("rv_x", 10)]
       payload = {"schema_version": 99, "items": items}
       try:
           from ky.models import validate_review_items  # noqa: F401
           items2 = validate_review_items(payload["items"])   # <-- 只传了 payload["items"]
           ...
   ```
   它构造了一个带 `schema_version: 99` 的 `payload`，但调用 `validate_review_items` 时只传了 `payload["items"]`（已经被拆包的纯列表），`schema_version=99` 这个信息在这次调用里根本没有被传递,函数不可能感知到它的存在。而 `payload["items"]` 本身是一条完全合法的 review item（用 verify 脚本自己的 `review_item()` builder 生成，字段齐全、无未知键、无非法值），所以 `validate_review_items` 对它的校验永远不会失败——这与函数是否实现了 schema_version 校验无关，纯粹是因为调用者没有把 schema_version 传进去。

   我验证过：**如果**改成让 `validate_review_items` 强制要求输入必须是"带 `schema_version` 的根 mapping"而不能是裸列表，这条检查确实会因为"expected a mapping, got list"而抛 `ContractError`、从而"通过"——但这会直接让 `tools/verify_round3_findings.py` 自己的 `m2_unknown_subject`、`m2_inactive_subject`、`m3_floor_conflict` 三个检查在其**未被 try/except 包裹的** `validate_review_items(...)` 调用处直接抛出未捕获异常，导致整个脚本崩溃、连"X/12 checks passed"这行汇总输出都打不出来——这比现在的"11/12"更差，也违反了"不修改验证脚本"这条硬约束背后的精神（我不能为了讨好一个探针而破坏另外三个探针依赖的既有函数契约）。

   真正的 M1 诉求——"reviews 根节点的 `schema_version` 必须被读取并校验"——我在 `load_review_items`（真实文件加载路径，也是 `ky/__main__.py` 和所有 CLI 使用者的入口）里已经完整实现,并且用两条独立测试验证：
   - `tests/test_contracts.py::ReviewsFileContractTest::test_unsupported_reviews_schema_version_is_rejected`（直接用临时文件构造 `schema_version: 99`，断言 `ContractError`，路径含 `schema_version`）
   - `tests/test_cli.py::test_unsupported_reviews_schema_version_exits_2`（端到端 CLI 级别，真实 `python -m ky preflight` 子进程，断言 exit 2）

   `validate_review_items`（不带 "load" 前缀的那个函数）从设计上就是"验证一段**已经在内存里的** item mapping 列表"，不代表一份完整的 reviews 文件,这个层级本来就不该有 schema_version 概念——这与 `validate_config` 不同（`validate_config` 从一开始就要求 `schema_version` 存在,因为它对应的输入永远是"一份完整配置"这个概念,不存在"裸列表" vs "完整文件"两种输入形态的区分）。这是仓库里已经存在的设计不对称（`load_review_items` 处理文件、`validate_review_items` 处理内存列表），我认为合理,只是这条验证脚本探针没有考虑到这个区分,错误地对内存层级的函数做了本该对文件层级做的检查。

   **建议**：如果审查者认为这条检查的意图仍然成立，需要修改的是 `tools/verify_round3_findings.py`（改成调用 `load_review_items` 并传入一个真实临时文件,或者把 `validate_review_items` 也改造成能接收完整 payload），而不是修改 `ky/` 下已经正确实现的契约——但按任务书的硬约束我不能改这个脚本，所以如实报告在这里，交由审查者判断。

2. **`ITEM_TYPE_PRIORITY` 的排序方向本身是否正确**（上一轮自审 A5 遗留）：本轮未改动，仍然只是描述性注释与代码一致，排序方向本身（`error_pattern` 排在 `concept`/`procedure`/`question_pattern` 之后）是否符合产品意图仍需用户或 `docs/评审结论与实施契约.md` 明确拍板。

3. **`state: "scheduled"` 的语义**（上一轮自审遗留）：本轮未改动。`ReviewItem.is_due()` 仍然只把 `queued` 当作可能到期，`scheduled` 状态条目对调度器完全不可见,没有测试覆盖，也没有 fixture 使用它。需要用户明确这是有意设计还是遗漏。

---

*本报告涉及的代码改动全部在 `ky/**` 与 `tests/**` 范围内；未修改 `review/**`、`docs/**`、`README.md`、`tools/verify_round3_findings.py`，未触碰 `F:\workspace\study`，未执行任何 git 操作。*
