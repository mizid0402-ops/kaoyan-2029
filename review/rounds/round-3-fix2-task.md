# 第三轮补 2：修复 B 项残留（Claude 执行）

## 复审结果（Codex 独立复核，非推测）

Codex 已完成重审，结论：**M1–M4 全部 RESOLVED**，6 条被点名的测试经**变异测试**验证 6/6 真的会变红
（它把实现改坏→确认测试红→再还原并用 SHA-256 核对哈希）。这部分做得好，保留。

**但 B 项未彻底修复，裁决仍为不通过。**

---

## 必须修的缺陷

### B（残留，MAJOR）—— 合同允许的大预算下仍然超分

- **位置**：`ky/schedule/budget.py`（浮点归一化 + 取整 + leftover 回收）
- **触发条件**：`total_daily_minutes = new_content_minutes = 100_000_000_000_000_000`，
  两个 active 科目权重 `0.5` 与 `0.5000009`（这个和在你新加的容差归一化下是合法的）。
- **实际输出**：两科分别 `49_999_955_000_040_503` 与 `50_000_044_999_959_503`，
  合计 `100_000_000_000_000_006`，**比预算多 6 分钟**。
- **根因**：大整数乘以归一化后的 binary float 产生多分钟舍入误差；
  `leftover < 0` 分支的 `order[:-leftover]` 最多遍历科目列表一次、每科只减 1，
  因此无法回收绝对值大于科目数的负 leftover。
- **更广证据**：Codex 扫了 5,724 组大数组合，**5,345 组加总不精确**。边界示例：

  ```text
  budget=2000000                  delta=0
  budget=100000000                delta=0
  budget=1000000000000000         delta=0
  budget=10000000000000000        delta=0
  budget=100000000000000000       delta=6     ← 从这里开始崩
  ```

### 最小复现（Codex 原始命令，你必须先自己复现）

```powershell
cd F:\workspace\kaoyan-ai-system
@'
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
a = allocate_new_content(config, n)
print([x.minutes for x in allocations], sum(x.minutes for x in allocations))
'@ | py -3.12 -
```

（本机 `py` 启动器不回显输出，**必须用 `py -3.12`**。）

---

## 修法（二选一，可以同时做，但必须说清选了哪些）

Codex 给出的两条路径：

- **(a) 换成精确有理数运算**：不要用 binary float 算任意大整数预算的最大余数。
  把已校验的权重按 `str(weight)` 构造 `fractions.Fraction`，用整数 `divmod` 算各科 floor 与精确余数，
  再按精确余数分配。**关键：必须完整处理任意大小的正/负 leftover，不能保留"每科最多调整 1"的隐含假设。**
- **(b) 给 `total_daily_minutes` 加合同上界**：一个有明确依据、可证明安全的整数上界。
  如果选 (b)，你必须：
  1. 在 `validate_config` 里带上界校验，错误带精确路径 `total_daily_minutes`；
  2. 说明上界的**选择依据**（不能只写"防止溢出"——要说清它覆盖什么、排除了什么）；
  3. 仍然保证**上界之内所有**预算与合法权重组合都精确加总。

---

## 必须补的回归测试

把 B 项那个测试**参数化**，至少覆盖：

```text
10**17 附近、2**53 附近、你选定的上界边界值、上界内随机抽样若干
```

每个用例同时断言三条：
1. **不超分**：`sum(allocations) == budget`
2. **不漏分**：同上（`==` 同时保证两个方向）
3. **各科分钟非负**：`all(a.minutes >= 0)`

再补一个**上界之外**的用例：确认它被合同拒绝（如果选了 (b)）。

---

## 硬约束（与上一轮相同，这次不得违反）

- 允许修改：`ky/**`、`tests/**`。
- **禁止修改**：`review/**`、`docs/**`、`README.md`、`tools/verify_round3_findings.py`，
  以及 `F:\workspace\study` 下的任何文件。不要执行 git。
- 不要为了变绿而放宽既有断言或删除测试。
- 报告写入：`F:\workspace\kaoyan-ai-system\review\rounds\round-3-fix2-claude.md`

## 报告必须包含

- 你选了 (a) 还是 (b)（或两者），**选择依据**；
- 改动的文件与具体改法；
- **真实完整输出**：
  - `py -3.12 -m unittest tests.test_contracts tests.test_review_scheduler`（含 exit code）
  - `py -3.12 tools/verify_round3_findings.py`（含 X/13 与 exit code）
  - 上面那段 `100_000_000_000_000_000` 最小复现的输出（必须 delta=0）
  - 你新加的参数化测试的输出
- 仍未解决 / 需要审查者判断的问题。
