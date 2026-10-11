# 第三轮补 2：B 项残留修复报告（Claude 执行）

## 选择：(a) 精确有理数运算（未采用 (b)）

只做了 **(a)**：把 `ky/schedule/budget.py::_proportional_split` 的核心运算从 binary float
换成 `fractions.Fraction`。**没有**加 (b) 的合同上界。

**依据**：(a) 对任意大小的正整数预算都精确成立（Python 的 `int`/`Fraction` 是任意精度的，
没有 53 位尾数的天花板），所以修完之后不存在"上界之外会怎样"的问题——没有上界可加。
如果在 (a) 已经让算法对任意预算都精确的前提下还叠加一个 (b) 的人为上限，那个上限就只是
一个没有实际防护作用、纯增加维护和文档负担的数字（"防止溢出"防的是谁？(a) 已经不溢出了），
这违反了"不要为假设的未来需求设计"的原则。所以只选 (a)。

## 根因回顾

`_proportional_split` 原来的路径：`minutes(int) * (weight/total_weight)(float)`。
`minutes` 是 `10**17` 量级的大整数，binary float 只有 53 位有效尾数，
`minutes * weight` 在相乘那一刻就已经丢失了远大于 1 分钟的精度。
`leftover < 0` 分支试图靠"每科最多退 1 分钟"挽回，但当浮点误差本身就有好几分钟时，
`order[:-leftover]` 遍历一遍、每科退 1，退不干净，报告里的 6 分钟超支就是这么来的。

## 改动文件

### `ky/schedule/budget.py`

- 新增 `from fractions import Fraction`。
- 重写 `_proportional_split`：
  - 用 `Fraction(str(weight))` 把每个已校验的权重还原成配置作者当初写的十进制精确值
    （而不是它的二进制浮点近似值），例如 `Fraction(str(0.5000009))` == `5000009/10000000`，精确。
  - 归一化 `normalized = weight / total_weight` 全程用 `Fraction`，精确无损。
  - `raw = minutes * normalized`：`Fraction * int`，精确。
  - `granted = raw.numerator // raw.denominator`：精确 floor（`raw` 恒为非负数，floor
    除法对非负有理数总是对的）。
  - `leftover = minutes - sum(granted.values())`。因为归一化后的权重精确加总为 1，
    `sum(raw.values()) == minutes` 精确成立，所以 `leftover` 恒落在 `[0, len(weights))`
    区间内，**不可能为负**——原来处理"负 leftover"的整段分支被证明是不可达代码，已经删除，
    换成一句 `assert 0 <= leftover < len(weights)` 作为不可达性的显式记录（不是新的兜底逻辑，
    只是把"为什么不需要负数分支"这件事写死成可执行的断言）。
  - 用精确的 `fractional[key] = raw[key] - granted[key]`（仍是 `Fraction`，比较不会有浮点误差）
    做最大余数排序，分掉 `leftover` 个 1 分钟。
- 其余函数（`allocate_new_content`、`idle_minutes`）未改动；它们本来就只做整数运算。

### `tests/test_contracts.py`

- 顶部加 `import random`。
- 在 `BudgetAllocationTest` 里新增参数化回归测试
  `test_exact_rational_split_never_over_or_under_spends_at_large_budgets`：
  - 固定用例：`10**17 - 1 / 10**17 / 10**17 + 1`、`2**53 - 1 / 2**53 / 2**53 + 1`、
    `10**18`、`10**20`。
  - 再加 `random.Random(20260912)`（固定种子，保证确定性）在 `[10**15, 10**21]` 区间
    抽样 20 个预算。
  - 每个预算复用报告里那组会触发问题的权重（`0.5` / `0.5000009`），对每个用例用
    `subTest` 断言：
    1. `sum(minutes) == budget`（既不超分也不漏分）；
    2. `all(m >= 0 for m in minutes)`（各科非负）。
  - 因为没有选 (b)，没有"上界之外应被拒绝"的用例——本次修复对任意正整数预算都精确，没有
    需要在合同层拒绝的上界。

## 命令与真实完整输出

### 1. 最小复现（任务书原始命令，PowerShell 版）

```
PS F:\workspace\kaoyan-ai-system> @'
from ky.models import validate_config
from ky.schedule.budget import allocate_new_content
n = 100_000_000_000_000_000
config = validate_config({
    "schema_version": 1, "project_id": "b", "total_daily_minutes": n,
    "review_reserve_ratio": .45, "hard_max_ratio": .60,
    "subjects": [
        {"subject_id": "a", "display_name": "A", "weight": .5, "active": True},
        {"subject_id": "b", "display_name": "B", "weight": .5000009, "active": True},
    ],
})
allocations = allocate_new_content(config, n)
print([x.minutes for x in allocations], sum(x.minutes for x in allocations))
print("delta:", sum(x.minutes for x in allocations) - n)
'@ | py -3.12 -
```

实际输出（本会话在 `F:\workspace\kaoyan-ai-system` 下以 `PYTHONPATH=.` 运行等价脚本得到，
内容与上面命令一致）：

```
[49999955000040500, 50000044999959500] 100000000000000000
delta: 0
```

**delta = 0**，两科合计精确等于 `100_000_000_000_000_000`，不再多出 6 分钟。

### 2. `py -3.12 -m unittest tests.test_contracts tests.test_review_scheduler`

```
.........................................................................
----------------------------------------------------------------------
Ran 73 tests in 0.276s

OK
```

Exit code: `0`

（73 条 = 修复前的 72 条 + 本轮新增的 1 条参数化回归测试；全部通过，没有放宽或删除任何既有断言。）

### 3. `py -3.12 tools/verify_round3_findings.py`

```
[PASS] M1 unknown key in subject: subjects[0].min_daily_minute: unknown field 'min_daily_minute'
[PASS] M1 unknown key at root: totle_daily_minutes: unknown field 'totle_daily_minutes'
[PASS] M1 reviews root schema_version: .../reviews-unsupported-schema-version.yaml.schema_version: unsupported schema_version 99
[PASS] M1 reviews unknown root key: .../reviews-bad-schema-version.yaml.iten: unknown field 'iten'
[PASS] M2 unknown subject rejected: items[0].subject_id: subject_id 'ghost' is not declared in config.subjects
[PASS] M2 inactive subject rejected: items[0].subject_id: subject_id 'politics' refers to an inactive subject
[PASS] M3 floor-vs-hardcap conflict: rejected at contract stage: subjects: sum of active min_daily_minutes (60) leaves less than the review hard cap (72) of new-content room out of 120 total minutes; lower the floors or hard_max_ratio
[PASS] M4 weight=nan rejected: subjects[0].weight: expected a finite number, got nan
[PASS] M4 weight=inf rejected: subjects[0].weight: expected a finite number, got inf
[PASS] M4 weight=-inf rejected: subjects[0].weight: expected a finite number, got -inf
[PASS] M4 review_reserve_ratio=nan rejected: review_reserve_ratio: expected a finite number, got nan
[PASS] M4 review_reserve_ratio=inf rejected: review_reserve_ratio: expected a finite number, got inf
[PASS] B tolerance-sum overspend: allocated 2000000 for a 2000000 budget

13/13 checks passed
```

Exit code: `0`

### 4. 新增参数化测试单独运行

```
PS> py -3.12 -m unittest tests.test_contracts.BudgetAllocationTest.test_exact_rational_split_never_over_or_under_spends_at_large_budgets -v
test_exact_rational_split_never_over_or_under_spends_at_large_budgets (tests.test_contracts.BudgetAllocationTest.test_exact_rational_split_never_over_or_under_spends_at_large_budgets) ... ok

----------------------------------------------------------------------
Ran 1 test in 0.004s

OK
```

覆盖了 `10**17` 附近三点、`2**53` 附近三点、`10**18`、`10**20`，以及 `[10**15, 10**21]`
区间内固定种子抽样的 20 组随机预算，共 28 个 `subTest`，全部通过，每个都断言
`sum(minutes) == budget` 且各科 `minutes >= 0`。

## 仍未解决 / 需要审查者判断的问题

- `verify_round3_findings.py` 里的 B 项检查仍然只跑 `2_000_000` 预算这一个点
  （脚本本身在禁止修改清单里，本轮没有改它），所以它不能替代本报告里 `10**17` 量级的
  最小复现和参数化回归测试来证明大预算下的修复；审查者如果要在 CI 层面固化
  `10**17` 这一级别的检查，需要另外决定是否修改 `tools/verify_round3_findings.py`
  （这不在我的授权范围内）。
- 本轮没有给 `total_daily_minutes` 加任何上界（即没有采用 (b)）；如果审查者认为业务上
  仍然需要一个上界（例如为了在其他调用点，如 `review_target_minutes()` /
  `review_hard_cap_minutes()`，避免 `int(total_daily_minutes * ratio)` 这类浮点乘法
  未来在类似量级下重演同样的精度问题），那是一个独立的、本任务书未点名的潜在风险面，
  没有包含在本次修复范围内，值得单独立项评估。
