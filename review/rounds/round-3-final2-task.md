# 第三轮终审补：DSH 收尾改动的确认（Codex 执行）

## 背景

你上一轮（`round-3-final-codex.md`）裁决 **PASS**，但在"非阻塞限制"第 2 条写了：

> **没有总预算上界。** 本轮实际验证到 `10^300`，没有验证更大整数；同时
> `review_target_minutes`、`review_hard_cap_minutes` 和合同中的 hard-cap 计算**仍使用 float 比例**。

DSH 据此做了一次**收尾探测**，发现这条"非阻塞限制"实际上**破坏了 CLI 的对外契约**：

```text
# 修复前
total_daily_minutes = 10^309 及以上
→ validate_config 内部 int(total * 0.60) 抛 OverflowError
→ preflight 打印 traceback，exit code = 1
→ 与 __main__.py 头部声明的「0 = 成功 / 2 = 合同违规 / 3 = 用法错误」不符
```

这不是"未覆盖的输入域"，而是**已声明的契约被违反**，因此 DSH 直接做了收尾修复（改动很小，已纳入版本）：

### 改动清单（DSH 执行）

| 文件 | 改动 |
|---|---|
| `ky/models.py` | 新增模块级 `_scale_minutes(total_minutes, ratio)`，用 `Fraction(str(ratio))` 精确计算 `floor(total × ratio)`；`review_target_minutes()`、`review_hard_cap_minutes()` 与 `validate_config` 内的 `review_hard_cap` 三处全部改用它。新增 `from fractions import Fraction`。 |
| `ky/schedule/review_clip.py` | `_deficit_ratio` 的 `target` 计算改用 `Fraction(str(weight)) * total * 7`。原 float 形式在极大预算下要么 `OverflowError`，要么**静默饱和成 `inf`**——后者会悄悄破坏优先级排序而不是报错，比崩溃更糟。新增 `from fractions import Fraction`。 |

### DSH 的实测结果（修复后）

```text
py -3.12 -m unittest tests.test_contracts tests.test_review_scheduler tests.test_cli
Ran 79 tests in 1.200s
OK                                                       # exit 0

py -3.12 tools/verify_round3_findings.py
13/13 checks passed                                      # exit 0

total_daily_minutes = 10^308 / 10^309 / 10^400 / 10^3000
→ 全部 ACCEPTED，hard_cap > 0，soft > 0，无异常

preflight（10^400 的配置）
→ exit code = 2，stderr 无 traceback                    # 契约恢复

preflight 走完整调度（10^400 + 正常复习队列）
→ total_daily_minutes 401 位
→ review_minutes=18, hard_cap 正确计算, new_learning_minutes 正确
→ selected=('rv_math1_limit_0001', 'rv_cs408_tree_0002')
```

---

## 你的任务：确认这次收尾没有破坏任何已通过的东西

1. **读改动**：`ky/models.py` 的 `_scale_minutes` 与三处调用点；`ky/schedule/review_clip.py` 的 `_deficit_ratio`。
2. **跑规定检查**（本机 `py` 启动器不回显输出，**必须用 `py -3.12`**）：
   ```powershell
   cd F:\workspace\kaoyan-ai-system
   py -3.12 -m unittest tests.test_contracts tests.test_review_scheduler tests.test_cli
   py -3.12 tools/verify_round3_findings.py
   ```
3. **独立验证精确性等价**：对**日常量级**（1…100000 分钟、以及你上一轮用过的权重集合），
   确认 `_scale_minutes` 的结果与旧 float 表达式 `int(total * ratio)` **完全一致**。
   这是本次改动最大的风险：如果精确化让日常量级的 soft/hard 配额发生了偏移，就会悄悄改变排课行为。
   请给出**不一致的用例数**（期望 0），以及你比对的方法。
4. **独立验证极端量级**：构造 `10^309`、`10^400`、`10^3000` 以及与 `float` 最大有限值相关的边界，
   确认三种结局都是**干净的**：要么接受并给出非负有限配额，要么抛带路径的 `ContractError`；
   **不允许出现 traceback、`OverflowError`、`inf`、`NaN` 或负数配额**。
   特别检查 `_deficit_ratio` 在极大预算下返回的 ratio 是否为有限的合理值（不是 `inf`/`nan`）。
5. **变异测试**：把 `_scale_minutes` 改回 `int(total * ratio)`，确认存在测试会变红吗？
   **如果没有任何测试能杀死这个变异，明确指出"这是一条未被测试保护的修复"，并给出应该补什么测试。**
   变异后**必须还原**，并给出还原后的 SHA-256。
6. **裁决**：`通过 / 有条件通过（条件：…） / 不通过`。

---

## 约束

- 用**中文**。
- 输出到 `F:\workspace\kaoyan-ai-system\review\rounds\round-3-final2-codex.md`
- 只写这一个文件：不得修改 `ky/**`、`tests/**`、`tools/**`、`docs/**`、`review/**` 里的其他文件。
  变异测试改坏的代码**必须还原**并给哈希。
- 不要执行 git。
- 最后用一句话回复：裁决 + 文件路径 + 日常量级一致性比对结果 + 极端量级结果 + 变异是否变红 + 文件哈希。
