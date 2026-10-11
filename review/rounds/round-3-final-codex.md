# 第三轮终审：B 项对抗性验证（Codex）

## 裁决

**通过（Gate: PASS）。**

B 项的精确有理数修复在本轮 6,528 个独立验证/分配用例中没有出现超分、漏分、负数、保底失守或意外异常；新增的大预算参数化测试能杀死人为注入的 1 分钟超分变异；规定单元测试、13 项独立验证及两条 M1–M4 回归变异抽查均符合预期。

**阶段 1 已满足验收门槛：合同自洽、算法确定、不超预算。**

这里的“通过”限于任务书定义的阶段 1、B 项与本轮覆盖域，不把未覆盖的无限输入域或业务权重合理性夸大为已证明。

## 范围与方法

- 完整阅读了本轮任务书、`round-3-fix2-claude.md`、上一轮复审报告、当前 `budget.py`、B 项参数化测试和 `verify_round3_findings.py`。
- 没有执行 git；探针均通过标准输入交给 `py -3.12 -`，并设置 `PYTHONDONTWRITEBYTECODE=1`，未创建探针文件。
- 只对变异目标作短暂修改；每次立即恢复，随后以目标测试和 SHA-256 双重确认。
- 扫描失败的定义是：合同接受后出现 `sum(allocation) > budget`、`sum(allocation) < budget`、任一科分钟为负、任一保底未满足或意外异常；合同拒绝用例则要求抛出带正确路径的 `ContractError`。

## 规定检查

### 单元测试

```text
py -3.12 -m unittest tests.test_contracts tests.test_review_scheduler
.........................................................................
----------------------------------------------------------------------
Ran 73 tests in 0.272s

OK
exit code = 0
```

### 独立验证

`py -3.12 tools/verify_round3_findings.py` 在变异前和全部恢复后各运行一次，结果均为：

```text
[PASS] M1 unknown key in subject
[PASS] M1 unknown key at root
[PASS] M1 reviews root schema_version
[PASS] M1 reviews unknown root key
[PASS] M2 unknown subject rejected
[PASS] M2 inactive subject rejected
[PASS] M3 floor-vs-hardcap conflict
[PASS] M4 weight=nan rejected
[PASS] M4 weight=inf rejected
[PASS] M4 weight=-inf rejected
[PASS] M4 review_reserve_ratio=nan rejected
[PASS] M4 review_reserve_ratio=inf rejected
[PASS] B tolerance-sum overspend

13/13 checks passed
exit code = 0
```

验证工具变异前、最终 SHA-256 均为：

```text
tools/verify_round3_findings.py
79EA37099FD8FCE405A42D2603576D37BD84C9BD0C82B883EE5B12A7037AF825
```

因此本轮没有改动审查方验证工具。

## B 项独立对抗扫描

### 用例构成与计数

固定种子为 `20260912`。总计 **6,528** 个用例，**0 失败**；其中 6,523 个是合同接受后的实际分配，5 个是预期的带路径拒绝。

| 组别 | 数量 | 覆盖 |
|---|---:|---|
| 预算 × 固定权重集 | 5,607 | 801 个不同预算 × 7 组权重；预算含 11 个指定固定点和 790 个随机大整数 |
| 随机不规则权重 | 500 | 科目数从 2、3、7、64 中抽取，权重由随机正整数归一化，预算随机到 `10^300` 量级 |
| 容差边界 | 8 | `1±1e-6` 的十进制写法、相邻可表示浮点数、远低于/高于容差 |
| 保底 | 13 | 7 个“保底和恰等于 `total-hard_cap`”边界；6 个保底后仍有余量、实际进入 Fraction 分配的用例 |
| 性能重复抽查 | 400 | 64 科目，`10^100` 与 `10^300` 各重复 200 次并同时复核三条分配不变量 |

801 个预算包括：`1`、`120`、`1440`、`2^53-1`、`2^53`、`2^53+1`、`2^63`、`2^64`、`10^17`、`10^100`、`10^300`；随机部分由 300 次 1–997 bit 整数、300 次 1–300 位十进制整数、200 次随机 `2^k±1/0` 生成，去重后与固定点合计 801 个。

7 组固定权重的 active 科目数分别为 1、2、2、2、7、64、101，包含：

- `[1.0]`；
- `[0.5, 0.5000009]`（和位于上侧容差内）；
- `[0.999999999, 1e-9]`；
- `[1.0, 1e-300]`；
- 7 科与 64 科不规则正权重；
- 101 科等权重。

每个被接受用例都分别检查“不超分”“不漏分”“各科非负”；保底用例还逐科检查 `allocation >= min_daily_minutes`。结果均通过，故本轮没有 B 项分配反例需要列出。

### 容差边界的实际行为

| 权重 | 存储后的浮点和/偏差 | 实际结果 |
|---|---|---|
| `0.5, 0.499999` | `0.9999990000000001` / `9.999999999177334e-7` | 接受；在 `10^100` 预算下 delta `0` |
| `0.5, 0.500001` | `1.0000010000000001` / `1.000000000139778e-6` | 拒绝；路径 `subjects` |
| 下边界向内相邻浮点 | 偏差 `9.999999999177334e-7` | 接受；delta `0` |
| 下边界向外相邻浮点 | 偏差 `1.000000000139778e-6` | 拒绝；路径 `subjects` |
| 上边界向内相邻浮点 | 偏差 `9.999999996956888e-7` | 接受；delta `0` |
| 上边界向外相邻浮点 | 偏差 `1.000000000139778e-6` | 拒绝；路径 `subjects` |
| `0.4, 0.4` | 和 `0.8` | 拒绝；路径 `subjects` |
| `0.6, 0.6` | 和 `1.2` | 拒绝；路径 `subjects` |

所有拒绝均为 `ContractError: subjects: active subject weights must sum to 1.0 (...)`，没有裸异常。第二行不是分配超支反例，而是浮点容差边缘的分类现象；详见“非阻塞限制”。

### 保底

“保底和恰等于 `total - hard_cap`”覆盖总预算 `1`、`120`、`2^53-1`、`2^53+1`、`2^63`、`10^100`、`10^300`，`hard_max_ratio=0.6`。例如总预算 120 时，hard cap 为 72，新内容预算与保底和均为 48；分配精确为 48。

另对除总预算 1 外的 6 个规模设置了小于新内容预算的非零保底，使保底发放后仍进入 `Fraction` 余量路径。所有科目均至少得到自己的保底，且总和精确等于新内容预算。

### 性能

64 个不规则权重、预先完成合同校验后，连续调用 `allocate_new_content`：

```text
10^100：200 次共 0.199620 s，平均 0.998 ms/次
10^300：200 次共 0.207208 s，平均 1.036 ms/次
```

本机上从 `10^100` 增至 `10^300` 没有出现明显退化，未触及不可接受门槛。该计时不含配置解析/校验，也不能外推到远多于 101 个科目的规模。

## Fraction 构造来源与语义差异

已确认调用链：`ky/models.py:294` 先用 `_require_float` 校验并存储权重，`allocate_new_content` 从已验证的 `SubjectBudget.weight` 建立字典，`ky/schedule/budget.py:83` 才直接对每个该浮点值执行 `Fraction(str(weight))`。没有先算浮点归一化结果再转 Fraction。

`Fraction(str(weight))` 与 `Fraction(weight)` 通常不相等，例如：

```text
weight=0.1
Fraction(str(weight)) = 1/10
Fraction(weight)      = 3602879701896397/36028797018963968
```

这会改变极大预算下的具体分科数。例如权重 `[0.1, 0.2, 0.7]`、预算 `99_999_999_999_999_999`：

```text
Fraction(str(weight))： [10000000000000000, 20000000000000000, 69999999999999999]
Fraction(weight)：      [10000000000000001, 20000000000000001, 69999999999999997]
```

两者总和都精确等于预算；差异是“把权重解释为人可见的最短十进制”与“把权重解释为二进制 float 的精确值”之间的语义差异，不是超分/漏分。当前实现选择前者，结果确定且更符合常见 YAML 十进制权重的直觉，因此不阻塞本轮 B 项验收。

但代码注释中“重建配置作者当初写的十进制”并非对所有输入都严格成立：原始文本一旦转为 float 就不可恢复，例如 `float("0.100000000000000005")` 的值与 `str(...)` 都是 `0.1`。准确说法应是“重建已验证 float 的最短可往返十进制表示”。这是说明精度问题，不影响当前分配不变量。

## 变异测试

### B 项新增参数化测试

在 `ky/schedule/budget.py::_proportional_split` 返回前临时给排序首项额外增加 1 分钟，符合任务书允许的“引入至少 1 分钟误差”变异。运行：

```text
py -3.12 -m unittest tests.test_contracts.BudgetAllocationTest.test_exact_rational_split_never_over_or_under_spends_at_large_budgets -v
Ran 1 test
FAILED (failures=28)
exit code = 1
```

28/28 个参数化预算均以“实际总和 = budget + 1”变红。恢复后同一目标测试 `OK`，exit code `0`。因此该测试确实能杀死至少 1 分钟的超分变异，不是空真。

恢复后的哈希与变异前一致：

```text
ky/schedule/budget.py
15BEEC2A191DF445F14764F802B984FC2BD32CCF9D784E0C5A516A61EE2CD1C1
```

### 上一轮 6 条测试中的两条抽查

1. `test_borrowing_to_the_hard_cap_only_happens_for_urgent_items`
   - 变异：`_is_urgent` 恒返回 `False`。
   - 结果：期望 `("rv_filler", "rv_urgent")`，实际 `("rv_filler",)`；测试失败，exit code `1`。

2. `test_subject_deficit_breaks_ties_towards_the_neglected_subject`
   - 变异：`_deficit_ratio` 恒返回 `0.0`。
   - 结果：期望 `("rv_zzz_eng",)`，实际 `("rv_aaa_math",)`；测试失败，exit code `1`。

两次变异恢复后合并重跑目标测试：`Ran 2 tests ... OK`，exit code `0`。第一次抽查起初误写了测试类名，得到 unittest loader error；该次不计作变异证据，上述结果来自纠正为真实类 `ReviewClippingTest` 后的执行。

最终哈希与变异前一致：

```text
ky/schedule/review_clip.py
2F2FA2098E4EA4F39B02959D68CC93C14D4BC4F2D8944EA121FE2289F49D39D6
```

## 非阻塞的已知限制

1. **浮点容差边缘并非十进制对称。** 数学十进制意义上的 `0.5 + 0.500001 = 1 + 1e-6` 在二进制求和后略超容差而被拒；相邻的上边界内浮点则被接受。它失败关闭并携带 `subjects` 路径，不会造成错误分配，但 `budget.py` 中“接受 `1.0 +/- WEIGHT_TOLERANCE`”的自然语言比实际浮点合同更绝对。若产品要求十进制边界严格对称，应在合同解析层保留 Decimal/原始标量语义，而不是只改分配器。
2. **没有总预算上界。** 本轮实际验证到 `10^300`，没有验证更大整数；同时 `review_target_minutes`、`review_hard_cap_minutes` 和合同中的 hard-cap 计算仍使用 float 比例。不能把 `_proportional_split` 的任意精度性质外推成整个系统对无限大整数都已验证。
3. **输入域边界。** 扫描只覆盖公共 `validate_config -> allocate_new_content` 路径，不覆盖绕过合同直接向私有 `_proportional_split` 传零和、负数、NaN 或非 float 权重；这些不是受支持调用。
4. **规模边界。** 正确性覆盖到 101 个 active 科目，性能定量到 64 科；没有覆盖数万或更多科目的排序时间与内存压力。
5. **权重解释。** `Fraction(str(float))` 采用最短十进制解释；在天文数字预算下，它和二进制精确解释的分科绝对差可被放大。当前合同没有要求二进制解释，且两种解释都保持精确总额，所以本轮不据此阻塞。

## 最终完整性与 Gate

最终哈希：

```text
tools/verify_round3_findings.py  79EA37099FD8FCE405A42D2603576D37BD84C9BD0C82B883EE5B12A7037AF825
ky/schedule/budget.py            15BEEC2A191DF445F14764F802B984FC2BD32CCF9D784E0C5A516A61EE2CD1C1
ky/schedule/review_clip.py       2F2FA2098E4EA4F39B02959D68CC93C14D4BC4F2D8944EA121FE2289F49D39D6
tests/test_contracts.py          BC1FCABEA89691469F5B29DA77C965A4064D9CCBD0416A5CAF27964030D22428
tests/test_review_scheduler.py   8CFD818677FB19D2297F570275C086E03DA195BBD3CCB06E12C132D3DD4CAEBD
```

没有未解决的 BLOCKER 或 MAJOR。上述容差边缘、注释精度、上界和未覆盖规模均为非阻塞限制；它们没有推翻本轮实际覆盖域内的合同拒绝路径、确定性或预算守恒。

**Gate: PASS / 通过。**
