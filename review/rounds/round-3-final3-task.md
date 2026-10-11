# 第三轮终审补 2：需求更正 + 最终确认（Codex 执行）

## 你上一轮的裁决与 DSH 的处理

你在 `round-3-final2-codex.md` 判 **FAIL**，理由是：DSH 的任务书要求"日常量级与旧 float 表达式完全等价"，
而你实测 **5,658/8,000,000 例不一致**（集中在 `1/53`、`2/53`、`3/53` 的浮点表示上）。

**这个发现是对的，而且很有价值。但 DSH 核实后认为：错的是那条需求，不是实现。** 理由如下（已实测）：

```text
total = 53, ratio = 1/53 存成 float 0.018867924528301886

  str 形式的最短十进制 = 9433962264150943/500000000000000000   < 1/53
  实际存储的二进制值   = 5438308983994561/288230376151711744   < 1/53

  53 × 十进制精确值 = 499999999999999979/500000000000000000  → floor 0
  53 × 二进制精确值 = 288230376151711733/288230376151711744  → floor 0
  int(53 * ratio)   = 1        ← 纯粹是 double 乘法把 53*ratio 向上舍入到 1.0
```

**两种"精确"解读都得到 0，只有 float 乘法得到 1。** 也就是说 `int(t * r)` 的值来自浮点舍入误差，
而契约写的是 `floor(total × ratio)`。所以：

- **保留精确实现**（DSH 决定，不由实现方推翻）；
- **原任务书那条"必须与旧 float 完全等价"的要求作废**，替换为下面三条更准确的不变量。

---

## 替换后的验收要求（本轮以这三条为准）

1. **真实配置比例必须等价**：`0.45` 与 `0.60` 在 `total = 1..20000` 全部与 `int(total * ratio)` 一致（实测 0 不一致）。
2. **差异有界**：对**任意**合法比例与预算，`abs(exact - int(total*ratio)) <= 1`，且
   `exact <= total * Fraction(str(ratio))`（即精确结果绝不超过"文档所写比例"的真实乘积）。
3. **已知差异必须被显式固化**：`total=53, ratio=1/53` → 精确值 0、旧 float 值 1，这条差异必须由测试
   **明确断言**（而不是被"允许 1 分钟偏差"的宽松断言掩盖）。

DSH 已按这三条改写了测试：`tests/test_contracts.py` 的 `RatioScalingTest` 现在是
`test_matches_the_float_product_across_the_everyday_range`（终止十进制比例）、
`test_matches_the_float_product_at_realistic_daily_budgets`、
`test_repeating_decimal_never_exceeds_the_true_product`、
**`test_float_multiplication_rounding_artifact_is_documented`（新增，固化 1/53 案例）**、
**`test_the_projects_own_ratios_are_unaffected`（新增，1..20000 全等）**、
`test_astronomically_large_budgets_stay_finite_and_positive`。
当前实测：`Ran 87 tests ... OK`，`13/13 checks passed`。

---

## 你的任务

1. **验证上面三条替换要求**是否真的成立（自己写探针，不要只跑测试）：
   - 第 1 条：确认 `0.45`/`0.60` 在你选定的日常范围内 0 不一致；
   - 第 2 条：**大范围**搜索是否存在 `abs(exact - legacy) > 1` 或 `exact > 真实乘积` 的反例
     （请覆盖你上一轮那 80 个比例，以及随机比例与大预算）；
   - 第 3 条：确认 `1/53` 案例确实被测试显式断言，并且把该断言的期望值改成别的东西时测试会红
     （变异测试，改完必须还原并给哈希）。

2. **判定 DSH 的决定是否站得住**：
   `floor(total × ratio)` 是否应当解释为"文档所写十进制比例的精确乘积"？
   如果你认为应当解释为"二进制 float 的精确乘积"或"float 乘法的结果"，请给出可操作的理由
   ——注意 `1/53` 案例下**两种精确解读都是 0**，只有 float 乘法是 1。
   如果你接受 DSH 的决定，请明说；如果你不接受，请给出**具体的、可执行的替代方案**。

3. **最终裁决**：`通过 / 有条件通过（条件：…） / 不通过`。
   若通过，请明确写出"阶段 1 已满足验收门槛：合同自洽、算法确定、不超预算"，
   并单列**仍然存在但不应阻塞**的已知限制。

4. 顺带确认：`_proportional_split` 里 `assert 0 <= leftover < len(weights)` 这个不变量在
   精确有理数下是否**永远**成立（给出推理或反例搜索）；以及它是否可以变成更明确的错误而不是 assert。

---

## 约束

- 用**中文**。输出到 `F:\workspace\kaoyan-ai-system\review\rounds\round-3-final3-codex.md`
- 只写这一个文件：不得修改 `ky/**`、`tests/**`、`tools/**`、`docs/**`、`review/**` 里的其他文件。
  变异改坏的代码**必须还原**并给哈希。
- 本机 `py` 启动器不回显输出，所有 Python 命令必须用 `py -3.12`。
- 不要执行 git。不要操作确认语。
- 最后用一句话回复：裁决 + 文件路径 + 三条替换要求的验证结果 + 是否接受 DSH 的决定 + 哈希。
