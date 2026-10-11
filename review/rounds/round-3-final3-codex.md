# 第三轮终审补 2：Codex 最终确认

## 裁决

**有条件通过。**

条件是：在把本轮验收基线定稿前，必须修正第 2 条中“对任意合法比例与预算，`abs(exact - int(total * ratio)) <= 1`”这一全称断言，并让测试按修正后的契约断言。该断言已有合同可接受的确定反例；问题在验收要求，不在当前精确实现，因此**不应回退到旧 float 乘法**。

就实现及应当冻结的精确语义而言，**阶段 1 已满足验收门槛：合同自洽、算法确定、不超预算**；但错误的第 2 条不能作为已经满足的验收依据。

## 事实、判断与范围

- 已确认事实：`ky/models.py::_scale_minutes` 实际计算 `(total_minutes * Fraction(str(ratio))) // 1`；soft quota、hard cap 和合同 hard-cap 检查均使用它。
- 已确认事实：`total=53, ratio=1/53` 时，十进制精确解释与二进制 float 值的精确解释均向下取整为 `0`，只有执行 binary64 乘法后才因舍入得到 `1.0`，进而 `int(...) == 1`。
- 我的判断：DSH 作废“必须与旧 float 全等”、保留精确实现的决定站得住；旧结果 `1` 是某次具体浮点运算的舍入产物，不是 `floor(total × ratio)` 的合理数学定义。
- 范围：本轮是最终验证，没有重新展开全仓审查；按最小范围原则只运行 `RatioScalingTest`、定向变异测试和独立探针，未运行 git，也未运行无必要的全套/冒烟测试。

## 三条替换要求的独立验证

### 1. 真实配置比例必须等价：通过

独立探针直接比较生产实现与 `int(total * ratio)`：

```text
ratio=0.45, total=1..20000: 0 不一致
ratio=0.60, total=1..20000: 0 不一致

加宽到 total=1..100000：
ratio=0.45: 0 不一致
ratio=0.60: 0 不一致
```

因此任务书规定的 `1..20000` 范围成立。

### 2. 差异有界：部分成立，但本条整体不成立

#### 成立的部分

`exact <= total * Fraction(str(ratio))` 永远成立，而不只是抽样成立。设

```text
P = total * Fraction(str(ratio))
exact = floor(P)
```

则按 floor 定义必有 `exact <= P < exact + 1`。比例经合同限制在 `[0, 1]` 且预算为正整数时，还可推出 `0 <= exact <= total`。

独立扫描也得到 0 个超越真实十进制乘积的案例；在日常域内同时得到 0 个“差异大于 1”的案例、最大差异为 1：

```text
80 个重建比例 × total=1..100000：8,000,000 例，差异 > 1 为 0，超越 0
80 个比例 × 14 个大预算：1,120 个 legacy 可计算例，超越 0
随机合法 float 比例 + 1..1020 bit 正整数预算：50,000 例，超越 0
```

其中 80 个比例按上一轮报告公开的 7 组构成与固定种子重建并去重：单科、`0.5/0.5000009`、`0.999999999/1e-9`、`1.0/1e-300`、`[1,2,3,5,8,13,21]/53`、64 科不规则权重、101 科等权重，再加入 `0.45/0.60`。上一轮报告没有保存 64 个随机数的完整序列，因此不能声称该子集逐位相同；但这不留下覆盖缺口：对 `total <= 100000` 可由 binary64 舍入界证明结论对**所有**合法 float 比例成立，而大预算反例直接使用上一轮 80 个比例中确定存在的 `1.0`。

日常域的全比例证明如下：对任意 binary64 `r in [0,1]`，能往返为 `r` 的 `str(r)` 所代表十进制值与 `r` 的绝对差不超过相邻浮点间隔的一半，在该区间上至多约 `2^-53`；`total <= 100000` 将它放大后仍远小于 1。`total` 本身可被 binary64 精确表示，`total*r <= 100000` 的乘法舍入误差同样远小于 1。故十进制精确乘积与 float 乘积相差小于 1，两者的非负 floor 最多相差 1。这个证明包含上一轮未逐项列出的 64 个比例。

#### 不成立的部分

`abs(exact - int(total * ratio)) <= 1` 不能量化到任意合同可接受预算。最小且清楚的公共合同反例是：

```text
total = 2**54 + 2 = 18014398509481986
ratio = 1.0

validate_config: ACCEPTED
exact  = 18014398509481986
legacy = int(total * 1.0) = 18014398509481984
abs(exact - legacy) = 2
```

根因是把大整数转换为 binary64 已经丢失整数位；并不需要重复小数才会触发。更大范围结果为：

```text
80 个比例 × 14 个大预算：
  legacy 可计算 1,120 例
  差异 > 1：574 例
  最大差异为 293 位整数

随机 50,000 例：
  差异 > 1：47,238 例
  最大差异为 292 位整数
```

合同又没有预算上界，所以还有无法定义该比较的合法输入：

```text
total=10**309,  ratio=0.45  -> exact 正常；legacy 抛 OverflowError
total=10**400,  ratio=0.60  -> exact 正常；legacy 抛 OverflowError
total=10**3000, ratio=1/53  -> exact 正常；legacy 抛 OverflowError
```

因此，第 2 条作为一个合取要求是**不成立**的，现有测试也没有证明该全称命题：`test_repeating_decimal_never_exceeds_the_true_product` 只覆盖一个比例和 `1..3000`，且其“不超越”断言比较的是 float 乘积，不是任务书写明的 `Fraction(str(ratio))` 精确乘积。

#### 可执行替代方案

把第 2 条拆成下面两条，不改生产算法：

1. 通用精确合同：对任意合同接受的 `total, ratio`，断言
   `exact == floor(total * Fraction(str(ratio)))`，并断言
   `exact <= total * Fraction(str(ratio)) < exact + 1` 及 `0 <= exact <= total`。
2. 旧行为兼容合同只保留有产品意义且已验证的范围：`ratio in {0.45, 0.60}`、`total=1..20000` 时与 `int(total * ratio)` 完全一致。其他比例/大预算不再承诺与旧浮点运算相差至多 1；保留第 3 条的已知差异测试即可。

测试上应把 80 个固定比例、随机比例和大预算用于第 1 项精确有理数断言；同时把现有“不超越”比较的右侧改为 `total * Fraction(str(ratio))`。这样测试的是冻结后的合同，而不是再次把 float 乘法当权威。

### 3. `1/53` 已知差异显式固化：通过

`tests/test_contracts.py::RatioScalingTest::test_float_multiplication_rounding_artifact_is_documented` 明确断言：

```text
_scale_minutes(53, 1/53) == 0
int(53 * (1/53)) == 1
decimal exact floor == 0
binary-float exact floor == 0
```

我把第一条期望临时从 `0` 变异为 `1`，只运行该目标测试：

```text
AssertionError: 0 != 1
Ran 1 test in 0.001s
FAILED (failures=1)
exit code = 1
```

恢复后同一测试为 `OK`、exit code `0`。这证明该差异不是被“允许偏差 1”的宽松断言掩盖。

## 对 DSH 语义决定的判断

**接受 DSH 的决定。**

理由如下：

1. `floor(total × ratio)` 是数学/业务合同，通常应对一个确定的比例值做精确乘法再 floor；binary64 乘法的中间舍入不应反过来定义合同。
2. `1/53` 案例中，`Fraction(str(ratio))` 与 `Fraction(ratio)` 两种精确解释均得到 0，说明旧值 1 不能以“float 本身也是精确值”为理由保留。
3. 当前实现对任意长度的 Python 正整数保持确定、无 float 溢出的配额计算；回退旧实现会重新引入已确认的 `OverflowError` 和大整数精度问题。

需要把术语说准：当前实现精确表达的是“**已解析 float 的最短可往返十进制字符串**”，不一定保留 YAML 原始词法。例如作者写入比 binary64 精度更长的小数时，解析为 float 后原始尾数已经丢失。对当前 `0.45/0.60` 配置这不产生差异，因此不阻塞；若产品将来要求严格忠于 YAML 原始十进制文本，应在解析层使用 `Decimal`/自定义 YAML 数字构造器，并让模型携带该精确值，而不是修改 `_scale_minutes` 去猜原始文本。

独立复算 `1/53`：

```text
ratio float repr = 0.018867924528301886
Fraction(str(ratio)) = 9433962264150943/500000000000000000
Fraction(ratio)      = 5438308983994561/288230376151711744

53 × decimal = 499999999999999979/500000000000000000 -> floor 0
53 × binary  = 288230376151711733/288230376151711744   -> floor 0
53 × float   = 1.0                                    -> int 1
```

## `_proportional_split` 的 leftover 不变量

在函数的受支持输入域（`minutes > 0`、非空且全为正的已校验权重）内，
`assert 0 <= leftover < len(weights)` **永远成立**。

证明：令正规化后的精确权重为 `q_i`，则 `q_i > 0` 且 `Σq_i = 1`。令
`x_i = minutes * q_i`，于是 `Σx_i = minutes`。函数先给每科
`floor(x_i)`，所以：

```text
leftover
= minutes - Σfloor(x_i)
= Σ(x_i - floor(x_i))
```

每项小数余数都在 `[0,1)`，共 `n=len(weights)` 项，故
`0 <= leftover < n`；`leftover` 又是整数，所以等价于 `0 <= leftover <= n-1`。

额外交叉探针覆盖 10,050 组，科目数取 `1/2/3/7/64/101`，含容差上沿、`1e-300` 极小权重、随机正权重、最高 300 位预算；结果为 0 个不变量/加总/非负失败，实际最大 leftover 为 94（101 科）。

可以把 assert 改成更明确、在 `python -O` 下也不会消失的内部错误：

```python
if not 0 <= leftover < len(weights):
    raise RuntimeError(
        f"internal exact-rational invariant violated: leftover={leftover}, "
        f"subjects={len(weights)}"
    )
```

这属于非阻塞的防御性改进：当前合法路径已有严格证明，不是可达的业务输入错误，故不应包装成 `ContractError`。

## 自动化验证与恢复哈希

```text
py -3.12 -m unittest tests.test_contracts.RatioScalingTest -v
Ran 8 tests in 0.664s
OK
exit code = 0

变异后的单目标测试：FAILED，exit code = 1
恢复后的单目标测试：OK，exit code = 0
```

所有 Python 命令均使用 `py -3.12`，并设置 `PYTHONDONTWRITEBYTECODE=1`。没有执行 git。

变异前后 SHA-256 相同，确认已恢复：

```text
tests/test_contracts.py          9FE238DF2C3EE9FFBA4FC1977B9ECED61390219BD460C78829DF1D5DCB8424D6
ky/models.py                     548A2DB6FEFA5B8A455B809168B6BE84ED156553F3684296CDCBF68CF69E5770
ky/schedule/budget.py            15BEEC2A191DF445F14764F802B984FC2BD32CCF9D784E0C5A516A61EE2CD1C1
ky/schedule/review_clip.py       C7DEA4109C1E594340F79EB5CCFFEDE91E55412AC9B97CE79EF7C06F0C07B0F2
```

## 仍然存在但不应阻塞的已知限制

1. `Fraction(str(float))` 冻结的是解析后 float 的规范十进制，不是任意 YAML 原始数字词法；当前项目比例不受影响。
2. `ky/models.py::_scale_minutes` 的 docstring 仍泛称“日常预算与 float product bit-identical”，已被 `1/53` 反例推翻；应在后续把措辞收窄为当前项目比例及明确范围，但不影响执行结果。
3. 合同没有预算上界；任意精度保证的是算术正确性，不是无限输入的时间/内存资源保证。
4. `_proportional_split` 的 assert 在优化模式会被移除；改为显式 `RuntimeError` 更利于将来的内部回归诊断，但当前不变量在合法输入下不可达失败。

## Gate 结论

- 上一轮 M1（旧 float 全等要求）：**RESOLVED**，经授权作废，`1/53` 判断独立复核成立。
- 替换要求 1：**通过**。
- 替换要求 2：**不通过其全称差异界；不超真实乘积部分通过**。
- 替换要求 3：**通过，且变异会红、文件已恢复**。
- DSH 保留精确实现的决定：**接受**。
- 实现侧未发现需要回退或阻塞阶段 1 的 BLOCKER/MAJOR；尚需修正的是验收规范与对应测试。

**Gate：有条件通过；条件为采用上面的第 2 条替代方案后再冻结验收文本。**
