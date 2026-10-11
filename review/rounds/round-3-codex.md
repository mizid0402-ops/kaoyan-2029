# 第三轮独立代码审查

## 审查结论摘要

**裁决：不通过（Gate: FAIL）。**

现有 49 项测试全部通过，正常 preflight 返回 0，非法权重 fixture 返回 2；这些结果只能证明已覆盖样例能跑通。实际代码仍存在 4 个 MAJOR：preflight 没有执行其注释所声称的结构/未知字段校验、复习条目没有绑定到配置中的有效科目、合法配置可在复习达到硬上限后因保底分钟冲突而崩溃、`NaN` 可绕过数值合同并在计划阶段崩溃。因此阶段 1 尚未达到“合同自洽、算法确定、不超预算”的验收门槛。

## 实际审查与运行范围

- 已逐行阅读：`ky/models.py`、`ky/schedule/budget.py`、`ky/schedule/review_clip.py`、`ky/__main__.py`。
- 已逐行阅读：`tests/test_contracts.py`、`tests/test_review_scheduler.py`。
- 已阅读全部五个 fixture：三个 config YAML 和两个 reviews YAML。
- 已确认 `ky/contracts/__init__.py` 为空壳；`ky/` 下不存在 JSON Schema 文件，也不存在 preflight 调用 JSON Schema 校验器的路径。
- 未执行 git，未读取或修改 `F:\workspace\study`，未修改 `ky/**`、`tests/**`、`docs/**` 或其他文件。

实际命令与结果：

```text
py -3.12 -m unittest -v tests.test_contracts tests.test_review_scheduler
Ran 49 tests in 0.311s
OK
exit 0

py -3.12 -m ky preflight --config tests/fixtures/config/config-minimal.yaml \
  --items tests/fixtures/reviews/reviews-overloaded.yaml --date 2026-09-12
selected: 6 -> 54 min; backlog: 64 min; new content: 66 min
exit 0

py -3.12 -m ky preflight --config tests/fixtures/config/config-weights-not-closed.yaml \
  --items tests/fixtures/reviews/reviews-overloaded.yaml --date 2026-09-12
contract violation: subjects: active subject weights must sum to 1.0 (got 0.9)
exit 2
```

所有 Python 命令均使用 `py -3.12`；为遵守唯一输出文件约束，额外反例通过标准输入运行，且禁用了字节码写入。

## A. 阻断级缺陷

### M1 — preflight 会静默接受未知字段，声称的结构合同没有落到真实执行路径

- **严重级别：MAJOR**
- **位置：** `ky/models.py:229-257`（`_load_subject`）、`ky/models.py:260-330`（`validate_config`）、`ky/models.py:538-561`（`load_review_items`）、`ky/contracts/__init__.py:1-5`。
- **触发条件：** 配置作者把 `min_daily_minutes` 拼成很现实的 `min_daily_minute`，或 reviews 根节点携带不支持的 `schema_version`/任意未知字段。
- **实际后果：** `_load_subject` 只读取认识的键，却不拒绝未知键；拼错的保底字段被忽略并回落为默认值 0，计划因此少分保底分钟。reviews 根节点的 `schema_version` 也完全未读取。代码注释说“JSON Schema guards shape”，但真实包中没有 schema 文件，preflight 也没有 schema 调用，所以不存在另一道会拒绝这些输入的门。
- **最小复现：** 本轮一次性探针向唯一活跃科目传入 `min_daily_minute: 15`，`validate_config` 成功，实测输出为 `TYPO_ACCEPTED: floor=0`，没有 `ContractError`。
- **期望：** 未知键、拼错键和不支持的根 schema 版本必须在生成计划前失败，并携带精确字段路径。
- **修法：** 要么在所有 root/subject/item/schedule 映射上显式校验允许键集合，要么真正接入 `additionalProperties: false` 的 JSON Schema，并让 preflight 在语义转换前执行；reviews 根 `schema_version` 也必须校验。补一个字段拼写错误会 exit 2 的 CLI 回归测试。

### M2 — 复习条目没有校验科目是否存在且处于 active，错误科目会直接进入计划

- **严重级别：MAJOR**
- **位置：** `ky/models.py:449-535`（只校验 `subject_id` 是非空字符串）、`ky/schedule/review_clip.py:126-139`（未知科目异常被吞掉并返回落后率 0）、`ky/schedule/review_clip.py:195-217`（照常排序和入选）。
- **触发条件：** review item 的 `subject_id` 为配置中不存在的 `ghost`，或为存在但 `active: false` 的 `politics`。
- **实际后果：** 两种条目都会被视为正常到期复习，消耗当天预算；与此同时新内容分配只面向 active subjects。计划因此包含无法归属的科目，或给明确停用科目排任务。
- **最小复现：** 使用现有 120 分钟配置构造各一个 10 分钟、当天到期的条目，本轮实测得到：

  ```text
  SUBJECT_ghost: selected=('rv_ghost',)
  SUBJECT_politics: selected=('rv_politics',)
  ```

- **期望：** 所有参与调度的 review item 必须引用配置中存在且 active 的科目；否则失败即拒绝，并指出 `items[i].subject_id`。
- **修法：** 在 preflight 完成 config/items 加载后做跨文档校验，或在 `select_daily_reviews` 入口做显式验证；移除 `_deficit_ratio` 对未知科目的宽泛 `except Exception`，不要把合同错误降格成“无意见”。补 unknown 和 inactive 两条回归测试。

### M3 — 合法配置的保底分钟与复习硬上限可能互相冲突，正常 preflight 路径会在最后一步崩溃

- **严重级别：MAJOR**
- **位置：** `ky/models.py:315-321`（只逐科比较保底与总预算）、`ky/schedule/review_clip.py:189-217`（复习可独立占满硬上限）、`ky/schedule/budget.py:82-87`（事后才拒绝保底总和）、`ky/__main__.py:123-125`（该 `ValueError` 未捕获）。
- **触发条件：** 总预算 120、soft/hard 为 0.45/0.60、两个 active 科目各保底 30 分钟；这份配置能通过 `validate_config`。当天有三个 urgent 项，成本 30、30、12 分钟。
- **实际后果：** 裁剪器合法选满 72 分钟，只剩 48 分钟新内容；随后 `allocate_new_content` 发现保底总和 60 大于 48，抛出未捕获 `ValueError`。这是正常业务状态触发的崩溃，不是非法调用者绕过模型。
- **最小复现：** 本轮实测输出：

  ```text
  FLOOR_CONFLICT: review=72 new=48
  FLOOR_CONFLICT_EXCEPTION: ValueError: min_daily_minutes sum (60) exceeds the new-content budget (48)
  ```

- **期望：** 任何已被合同接受的配置和已验证条目都应产生不超过总预算的确定计划，不应在 CLI 组装结果时崩溃。
- **修法：** 先冻结语义再选一种一致实现：若硬上限和所有保底必须同时可兑现，则配置校验应要求 `sum(active floors) <= total_daily_minutes - review_hard_cap_minutes()`；若保底优先级更高，则裁剪器的有效硬上限必须限制为 `total - floor_total`。无论选哪种，错误都应在带字段路径的合同阶段暴露，并补“复习恰好占硬上限”的端到端回归测试。

### M4 — `NaN` 能绕过所有浮点范围与权重闭合校验，随后使计划崩溃并破坏全序前提

- **严重级别：MAJOR**
- **位置：** `ky/models.py:106-120`（`_require_float`）、`ky/models.py:239-249`、`ky/models.py:273-287`、`ky/models.py:309-313`、`ky/models.py:427`。
- **触发条件：** YAML 使用 PyYAML 可解析的 `.nan`，例如某 active subject 的 `weight: .nan`，或 ratio/ease factor 为 `.nan`。
- **实际后果：** 与 `NaN` 的 `<`、`>`、`<=` 比较都为 false；`abs(total_weight - 1.0) > tolerance` 也为 false，所以合同接受它。权重为 NaN 时，预算切分在 `int(NaN)` 崩溃；ratio 为 NaN 时，soft/hard 分钟计算同样崩溃；若进入排序，NaN 也不再提供可靠的可比较排序键。
- **最小复现：** 本轮实测 `validate_config` 接受单科 `weight=float('nan')`，随后得到：

  ```text
  NAN_ACCEPTED: weight=nan
  NAN_EXCEPTION: ValueError: cannot convert float NaN to integer
  ```

- **期望：** 所有合同浮点值必须为有限数；`.nan`、`.inf`、`-.inf` 均应以精确路径抛出 `ContractError`。
- **修法：** `_require_float` 转换后先执行 `math.isfinite(value)`，再做范围比较；对 weight、ratio、ease factor 各补非有限值回归测试和 CLI exit 2 测试。

## B. 逻辑与边界

### 排序键是否真的是全序

对 **经 `load_review_items`/`validate_review_items` 校验且所有浮点有限** 的集合，排序键最终落到唯一的 `review_id`，所以不同合法条目可形成确定全序；`due_date` 在固定 `today` 下与 `overdue_days` 信息重复，但不影响正确性。类型相同优先级也会继续比较自评和 ID。

该结论有两个边界：一是 M4 的 NaN 会破坏浮点比较前提；二是 `select_daily_reviews` 公开接受任意 `ReviewItem` 列表，本身不检查重复 ID。若调用者绕过批量校验，两个同 ID 但成本不同的对象可得到相同排序键，Python 稳定排序会使结果依赖输入顺序。真实 preflight 路径会拒绝重复 ID，因此第二点是接口防御不足，不单独升级为阻断项。

### 软/硬配额及“成本大于剩余额度”

实现的实际语义清楚且与第 3 条文字相符：

- `used + cost <= soft`：任何 due 条目可选。
- `soft < used + cost <= hard`：只有 urgent 可选。
- `used + cost > hard`：无论是否 urgent 都延期。
- `cost > hard`：进入 `unschedulable`。

因此，一个 10 分钟非 urgent 项在软配额只剩 6 分钟时会延期；循环仍继续，后续 4 分钟低优先级项可能入选。这是“按优先级依次尝试装入”的确定性贪心裁剪，不是“高优先级装不下就停止”。如果产品意图是不允许低优先级绕过一个装不下的高优先级项，当前实现就不符；任务书现有文字没有明确禁止这种回填，所以本轮不把它判成缺陷，但必须补测试冻结该语义。

### 保底与权重顺序

代码确实永远先加保底，再把全部余量按原始权重分配。它的结果不是“先按总预算权重算目标，再只给不足科目补到 floor”。例如现有 115 分钟用例得到 40/35/40，而不是 46/23/46；英语最终占约 30.4%。所以 `budget.py:13-18` 所说“预算大时 floor stops binding、复现 40/20/40”以及测试名 `test_exact_40_20_40_split_when_the_floor_stops_binding` 都不准确。实现与任务书第 2 条的字面算法一致，但这个算法会让有 floor 的科目在所有预算规模下持续额外获配，用户必须明确接受该政策。

### 浮点比较与精确加总

除 M4 外，`WEIGHT_TOLERANCE=1e-6` 与“精确加总”存在理论冲突。配置可接受权重和为 `1.0000009`；由于 `_proportional_split` 只处理正 `leftover`，不回收负差，在合同未限制的大预算下会超分。本轮实测总预算 2,000,000 时分出 2,000,001，超 1 分钟。日常 120 分钟不会触发这一整数边界，因此它不是现实配置下的独立 MAJOR，但第 2 条“结果一定精确加总”按当前无上界合同并非恒真。修复可在分配前归一化有限正权重，或用固定精度/整数权重并同时处理正负舍入差。

### 日期边界

`due_date <= today`，所以到期日当天纳入；`today - due_date` 使用 `date`，不存在时区或午夜边界；逾期 3 天以 `>= 3` 进入 urgent，边界清楚。`datetime` 对象会截断为 date，但字符串时间戳不会被 `_parse_date` 接受，行为虽不对称，在 YAML 日期合同限定为 `YYYY-MM-DD` 时不构成缺陷。当前合同没有约束 `last_reviewed_on <= due_date/today`，可能接纳未来复习记录；任务书未给出这项跨字段语义，本轮只列为待补规格，不据此阻断。

### CLI 错误边界

`--urgent-overdue-days 0` 是明确的非法 CLI 参数，但 `ReviewPolicy` 在 `ky/__main__.py:119-122` 的合同异常捕获区之外构造。本轮实测出现 traceback 并返回 1，而模块头部宣称 usage error 返回 3。它失败关闭、不会生成错误计划，因此列为非阻断接口缺陷；应由 argparse 直接限制为正整数，或捕获 `ValueError` 并返回 3。

## C. 与“已实现算法语义”1–7 的逐条对照

1. **失败即拒绝：不符合。** 已覆盖的缺失值、类型、范围和权重 0.9 会产生带路径的 `ContractError`，非法 fixture 的 preflight 也确实 exit 2；但未知字段会被静默忽略（M1），NaN 会绕过范围校验（M4），非法 policy 则 traceback/exit 1。该声称只能算部分实现。
2. **先保底、再按权重最大余数分配且不丢分钟：部分符合。** 常规有限权重和现实预算下顺序、确定 tie-break、加总都正确；M3 表明调度前未为保底预留容量，容许已验证输入在分配阶段崩溃；容差接受的超大预算还可多分 1 分钟。因此“总能精确加总”的无条件声称不成立。
3. **指定全序及软/硬裁剪：条件符合。** 对由真实 loader 产生、科目有效、浮点有限、ID 唯一的 items，键顺序与声明完全一致，软/硬判断也正确；M2/M4 说明这些必要前提没有在组合合同上封闭。
4. **延期保留 due_date、只增加 defer_count、无写回：符合。** `with_deferral` 完整复制其余字段；输入对象冻结且不被修改，现有测试对此有有效断言。
5. **超大条目进 unschedulable，导入时拒绝大于 30 分钟：符合。** 30 分钟条目在小硬上限配置中进入 `unschedulable`；31 分钟以上在导入时拒绝。`backlog_minutes` 不包含 unschedulable，分类没有混淆。
6. **self_rating 仅作末级业务 tie-break：符合。** 它位于类型优先级之后、最终唯一化用的 `review_id` 之前，不修改日期、间隔、质量，也不参与 due 过滤。这里的“最后一级”只能理解为最后一个业务优先级；真正 tuple 最后一项仍是 `review_id`，与任务书列出的键一致。
7. **零写入/不接生产/不调用 AI：按窄义部分符合。** 已审代码没有写文件、没有生产项目创建和 AI 调用，也没有硬编码访问 study 工作区；但 CLI 对 `--config`、`--items`、`--usage` 接受任意路径，`_read_yaml_file`/`Path.read_text` 没有阻止位于 `F:\workspace\study` 下的路径。故“不会主动或默认触碰生产区”成立；若按“不论调用参数如何都绝不读取该目录”的字面强保证，则不成立。是否需要路径隔离必须由契约明确，当前代码不能宣称强保证。

## D. 测试有效性

### 有效覆盖

权重闭合、ratio 倒置、重复 ID、日期先后、schedule mode/phase、单项 30 分钟限制、延期不改原对象、硬上限不被已知 fixture 超过、未来/retired/suspended 过滤、输入逆序结果一致等测试都具有实际断言价值。49 项通过是真实证据，但它们集中在 happy path 和同一组 fixture。

### 假测试或明显过弱的测试

1. `test_borrowing_to_the_hard_cap_only_happens_for_urgent_items` 是真空测试。现有 overloaded fixture 实测恰好停在 soft=54，`if result.review_minutes > soft` 为 false，主体断言一次都不执行；即使借用逻辑完全损坏也会通过。
2. `test_defer_count_two_makes_an_item_urgent` 只断言该条目被选中。它排序第二，在累计 20 分钟时就已进入 soft 额度，无需 urgent 权限；删掉 `_is_urgent` 仍会通过。
3. `test_subject_deficit_breaks_ties_towards_the_neglected_subject` 的注释说预算只容纳一个 10 分钟条目，但实际 soft 是 54，两个条目都被选。`assertIn('rv_tie_eng', selected)` 不能证明 eng 排在 math 前；删掉 deficit 排序仍可能通过。
4. `test_a_deferred_item_gains_priority_on_a_later_day` 第二天只传入三个前日延期项，三项共 30 分钟全部能放入；断言“全部入选”不证明它们相对新到期项提升了优先级。
5. `test_stricter_policy_defers_more` 使用 `>=`/`<=`，允许严格和宽松策略结果完全相同；把 policy 参数忽略掉仍可能通过。应构造必须跨 soft、且只因阈值不同而分流的单条反例并断言精确 ID。
6. `test_exact_40_20_40_split_when_the_floor_stops_binding` 验证的是“固定加 15 后再对余量分权重”的当前实现，期待值 40/35/40 本身并非 40/20/40。它锁定实现细节，却没有证明测试名和注释声称的 floor 停止生效。
7. `test_allocation_is_deterministic` 和 `test_repeated_selection_is_byte_identical` 只是同进程、同输入重复调用；它们能防随机性，但不能单独证明全序。后者有逆序测试补强，仍缺多排列、重复键及 NaN 反例。

### 缺失的关键反例（建议新增，至少以下 8 条）

以下使用现有测试 helper 的简写；其中 1–4、6 的失败行为已在本轮用一次性探针实际复现，5 和 7 可直接由代码路径确定，8 的 CLI 行为已实际运行。

```python
# 1. 未知和 inactive 科目必须失败，而不是进入 selected。
ghost = make_item("rv_ghost", subject_id="ghost")
politics = make_item("rv_politics", subject_id="politics")
with self.assertRaises(ContractError):
    validate_items_against_config(self.config, [ghost, politics])

# 2. 拼错的可选字段不能静默回落为默认值。
raw = base_config_mapping()
raw["subjects"][1].pop("min_daily_minutes", None)
raw["subjects"][1]["min_daily_minute"] = 15
with self.assertRaises(ContractError) as ctx:
    validate_config(raw)
self.assertIn("min_daily_minute", ctx.exception.path)

# 3. 所有非有限浮点值均须拒绝并给精确路径。
for bad in (float("nan"), float("inf"), float("-inf")):
    raw = base_config_mapping()
    raw["subjects"][0]["weight"] = bad
    with self.assertRaises(ContractError):
        validate_config(raw)

# 4. 合法配置不能在复习占满 hard cap 后才发现保底不可兑现。
config = config_with(total=120, hard=.60, floors={"math1": 30, "eng1": 30})
result = select_daily_reviews(config, [urgent(30), urgent(30), urgent(12)], TODAY)
self.assertEqual(result.review_minutes, 72)
self.assertEqual(sum(a.minutes for a in allocate_new_content(config, 48)), 48)

# 5. 精确冻结跨 soft 的语义：非 urgent 不能跨，urgent 可以跨，但都不能越 hard。
result = select_daily_reviews(config_100_soft50_hard80, ordered_items, TODAY)
self.assertEqual(result.selected_ids, ("old-45", "small-fill-5", "urgent-25"))
self.assertEqual(result.deferred_ids, ("nonurgent-cross-10",))
self.assertEqual(result.review_minutes, 75)

# 6. tolerance 内被接受的权重也绝不能超预算。
config = config_with(total=2_000_000, weights={"a": .5, "b": .5000009})
alloc = allocate_new_content(config, 2_000_000)
self.assertEqual(sum(x.minutes for x in alloc), 2_000_000)  # 当前为 2_000_001

# 7. 真正证明 deficit tie-break：soft 只能容纳一个，并断言顺序/精确集合。
config = config_20_soft10_hard10
result = select_daily_reviews(config, [math_item, eng_item], TODAY,
                              seven_day_usage={"math1": 400, "eng1": 0})
self.assertEqual(result.selected_ids, ("rv_tie_eng",))
self.assertEqual(result.deferred_ids, ("rv_tie_math",))

# 8. CLI 非法 policy 应是受控 usage error，不应 traceback。
completed = subprocess.run(["py", "-3.12", "-m", "ky", "preflight", ..., 
                            "--urgent-overdue-days", "0"], capture_output=True, text=True)
self.assertEqual(completed.returncode, 3)  # 当前实测 returncode == 1
self.assertNotIn("Traceback", completed.stderr)
```

还应补：reviews 根 `schema_version` 不支持时 exit 2、inactive subject 带非零 floor 的合同定义、同优先级全部字段逐级 tie-break、soft/hard 恰好等于边界、单项等于 hard cap、重复执行跨进程 JSON 字节一致性。

## E. 裁决

**不通过。**

理由不是“还可以写更多测试”，而是存在已实际复现的验收级失败：真实 preflight 路径能静默吞掉拼错字段；无效/停用科目能进入计划；已通过合同的配置能在正常满载日崩溃；NaN 能绕过合同并破坏预算计算。只有修复 M1–M4、为每项加入直接回归测试，并重新跑最小范围的两个 unittest 模块及正常/非法/保底冲突 preflight 后，才可进入下一轮复审。

## Fix Bundle

仅修复以下阻断项，不做无关重构：

1. **M1：** 将结构/未知键/schema version 校验接入真实 preflight 路径；拼错保底字段必须 exit 2。
2. **M2：** 组合校验 review `subject_id` 必须存在且 active；unknown/inactive 均须带路径拒绝。
3. **M3：** 冻结 floor 与 review hard cap 的优先关系，使所有合同通过的配置在满硬上限时仍可生成计划，或提前以合同错误拒绝。
4. **M4：** 对全部合同浮点值执行 `isfinite` 校验，NaN/Inf 必须 exit 2。

修复后最小验证范围：

```text
py -3.12 -m unittest -v tests.test_contracts tests.test_review_scheduler
py -3.12 -m ky preflight --config tests/fixtures/config/config-minimal.yaml --items tests/fixtures/reviews/reviews-overloaded.yaml --date 2026-09-12
py -3.12 -m ky preflight --config tests/fixtures/config/config-weights-not-closed.yaml --items tests/fixtures/reviews/reviews-overloaded.yaml --date 2026-09-12
```

并增加只覆盖 M1–M4 的回归用例；无需先跑更大的测试集。
