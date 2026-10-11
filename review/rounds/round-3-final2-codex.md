# 第三轮终审补：DSH 收尾改动确认（Codex）

## 裁决

**不通过（Gate: FAIL）。**

极端量级修复本身有效，规定检查全部通过，旧实现变异也能被现有测试杀死；但是任务书要求的日常量级精确等价并未成立。对上一轮 7 组权重进行完整比对后，8,000,000 个用例中有 **5,658 个不一致**。这是合法配置可达的一分钟配额回退，会改变复习硬上限，属于本次修复直接引入且仍未解决的 MAJOR。

## 审查范围与代码结论

- `ky/models.py::_scale_minutes` 使用 `(total_minutes * Fraction(str(ratio))) // 1`；`review_target_minutes()`、`review_hard_cap_minutes()` 和 `validate_config()` 的 hard-cap 合同检查均已接入该函数。
- `ky/schedule/review_clip.py::_deficit_ratio` 使用 `Fraction(str(weight)) * total_daily_minutes * 7` 计算目标，再把已经归一化的有理数差额比转为 `float`。
- 这两处改动消除了大整数先转二进制浮点所导致的 `OverflowError`/`inf` 路径；但 `Fraction(str(ratio))` 的十进制取整语义并不总与旧式浮点乘法取整相同。
- 没有执行 git。所有探针都通过标准输入交给 `py -3.12 -`，并设置 `PYTHONDONTWRITEBYTECODE=1`；除本报告外未保留探针文件。

## 规定检查

```text
py -3.12 -m unittest tests.test_contracts tests.test_review_scheduler tests.test_cli
Ran 85 tests in 1.412s
OK
exit code = 0
```

任务书记录的 DSH 基线是 79 项，但当前实际发现并运行了 85 项；这里以当前命令的真实输出为准。

```text
py -3.12 tools/verify_round3_findings.py
13/13 checks passed
exit code = 0
```

因此，先前已通过的现有回归与 13 项独立检查没有退化；但这些绿灯没有覆盖任务书新增的全部日常等价要求。

## 阻塞发现

### M1 — 日常量级并非与旧 float 表达式完全等价

- **严重度：** MAJOR
- **位置：** `ky/models.py:293-302`，调用点 `KaoyanConfig.review_target_minutes()`、`KaoyanConfig.review_hard_cap_minutes()` 与 `validate_config()`。
- **触发条件：** 合法配置 `total_daily_minutes=53`，`review_reserve_ratio=hard_max_ratio=1/53`（存储浮点为 `0.018867924528301886`），单个 active 科目权重 `1.0`、保底 `0`。
- **实际结果：** 配置被合同接受；新实现的 soft/hard 均为 `0`。
- **旧行为/任务期望：** `int(53 * (1/53)) == 1`，故任务书要求的精确等价应得到 soft/hard `1`。
- **影响：** 这是公共配置可达路径，不是只把“科目权重”误传给私有函数的假设路径。硬上限从 1 分钟变为 0 分钟时，一分钟复习项也无法进入计划，排课行为发生实际变化。
- **更广证据：** 见下一节的 5,658 个不一致用例；差异均为新实现比旧实现少 1 分钟。
- **最小修复方向：** 在任务书冻结的日常范围保留旧浮点取整结果，并在浮点转换/乘法不再安全时切换到无溢出的精确路径；或者由产品明确修改“日常行为必须等价”的契约。不能继续同时声称 `Fraction(str(ratio))` 对所有日常合法比例都与旧表达式完全一致。
- **应补回归：** 至少加入 `total=53/106/159` 与 `ratio=1/53、2/53、3/53` 的精确等价断言，并覆盖公共 `validate_config -> review_target_minutes/review_hard_cap_minutes` 路径。

## 日常量级精确性等价扫描

### 方法

1. 用上一轮相同的固定种子 `20260912` 重建 7 组权重：1 科、容差上沿 2 科、`1e-9` 2 科、`1e-300` 2 科、`[1,2,3,5,8,13,21]/53`、64 科固定随机权重、101 科等权重。
2. 将上述标量去重，并加入实际 review 配额调用点使用的 `0.45`、`0.60`，得到 **80 个唯一比例**。
3. 对每个比例遍历 `total=1..100000`，逐例比较 `_scale_minutes` 的表达式 `(total * Fraction(str(ratio))) // 1` 与旧表达式 `int(total * ratio)`；另对发现差异的三个比例直接调用 `_scale_minutes` 重跑全范围确认。

结果：

```text
总用例数：8,000,000
不一致用例数：5,658
出现不一致的比例数：3

ratio=1/53 的浮点表示 0.018867924528301886：1,886 例
ratio=2/53 的浮点表示 0.03773584905660377 ：1,886 例
ratio=3/53 的浮点表示 0.05660377358490566 ：1,886 例
```

首组反例：

```text
total=53,  ratio=0.018867924528301886: 新=0, 旧=1
total=53,  ratio=0.03773584905660377 : 新=1, 旧=2
total=53,  ratio=0.05660377358490566 : 新=2, 旧=3
total=106, ratio=0.018867924528301886: 新=1, 旧=2
```

三个比例都在每个 `53` 的倍数处出现一次偏差，直到 100000 各有 1,886 例。实际默认策略比例 `0.45`、`0.60` 在 `1..100000` 内各自为 **0 不一致**，但这不足以满足任务书对上一轮权重集合的完整等价要求，也不能排除其他合法配置比例。

## 极端量级独立验证

共验证 10 个预算点：`10^308`、`int(sys.float_info.max)`、其 `+1`、`+2^970-1`、`+2^970`、`2^1024-1`、`2^1024`、`10^309`、`10^400`、`10^3000`。

每个预算都走过 `validate_config`、soft/hard 配额、`_deficit_ratio` 和包含一个到期复习项的完整 `select_daily_reviews`：

```text
接受：10/10
失败：0
配额约束：0 <= soft <= hard <= total，10/10 成立
完整调度：selected=('rv_only',)，review_minutes=10，
          new_learning_minutes=total-10，10/10 成立
```

对每个预算以七日用量 `0`、`total`、`7*total`、`10*total` 检查 `_deficit_ratio`，结果恒为：

```text
[1.0, 0.8571428571428571, 0.0, -0.42857142857142855]
```

四个值均有限且符合 `(target-actual)/target` 的含义，没有 `inf`、`NaN` 或异常。全部 soft/hard/new-learning 配额均为非负整数；未出现 traceback、`OverflowError` 或负数配额。

旧 float 路径在本次边界组中从 `int(sys.float_info.max) + 2^970` 开始抛 `OverflowError`，当前精确路径在相同输入上正常接受。

另用 `10^400` 构造“科目保底等于总预算、与 0.60 hard cap 冲突”的非法配置，真实子进程执行 preflight：

```text
exit code = 2
stderr 包含带路径的 contract violation: subjects: ...
stderr 无 Traceback、无 OverflowError
```

因此，任务书要求的极端量级“接受并给出干净配额，或以带路径 ContractError 拒绝”已经满足。

## 变异测试与恢复

将 `ky/models.py::_scale_minutes` 临时改回：

```python
return int(total_minutes * ratio)
```

只运行最小直接测试：

```text
py -3.12 -m unittest \
  tests.test_contracts.RatioScalingTest.test_astronomically_large_budgets_stay_finite_and_positive -v

Ran 1 test
FAILED (failures=1, errors=1)
exit code = 1
```

该测试在 `10^308, ratio=1.0` 检出配额大于总预算，并在后续极大整数处触发 `OverflowError`。所以**极端量级收尾修复有自动化测试保护，变异会变红**。

不过，现有严格等价测试只覆盖 `0.45、0.60、0.05、0.99、0.01、1.0、0.75、0.125`；对重复小数仅以 `1/3` 为例并允许 1 分钟偏差，因此没有保护本轮新增的“上一轮权重集合必须完全等价”要求，M1 才会在整套测试全绿时仍然存在。

变异已还原；恢复后同一目标测试 `OK`，exit code `0`。变异前与恢复后的 SHA-256 完全一致：

```text
ky/models.py
548A2DB6FEFA5B8A455B809168B6BE84ED156553F3684296CDCBF68CF69E5770
```

## Gate 结论

- 先前 BLOCKER/MAJOR 与规定回归：通过。
- 极端量级干净失败/接受：通过。
- 旧实现变异是否被杀死：是。
- 日常量级精确等价：**失败，5,658/8,000,000 不一致**。
- 未解决阻塞项：M1。

**Gate: FAIL / 不通过。**
