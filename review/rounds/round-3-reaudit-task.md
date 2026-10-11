# 第三轮重审：复审修复结果（Codex 执行）

## 背景

你在 `round-3-codex.md` 里的裁决是 **不通过**，提出 4 个 MAJOR（M1–M4）+ B 节若干边界问题 + 7 条假测试。

Claude 随后做了**一轮无效修复**：它当时看不到你的报告（背对背），只修了自己发现的 A1–A6，
测试从 49 涨到 56 条且全绿，但你的 M1–M4 **一条都没修**。

DSH 写了独立验证脚本 `tools/verify_round3_findings.py` 坐实了这一点（当时 3/12 通过）。

之后 DSH 把你的报告交给 Claude 并要求它按你的结论修复。**现在它报告已修完。你的任务是独立验证它到底修没修好。**

---

## 你的任务

### 1. 先自己跑，不要相信任何声称

```powershell
cd F:\workspace\kaoyan-ai-system
py -3.12 -m unittest tests.test_contracts tests.test_review_scheduler
py -3.12 tools/verify_round3_findings.py
```

（本机 `py` 启动器**不回显子进程输出**，必须用 `py -3.12`。）

**硬约束：`tools/verify_round3_findings.py` 是审查方的验证工具，不是实现方可以改的测试。
逐行检查它的 git 状态/内容是否被改过，确认它仍然是 DSH 写的原版。若被改动，判为作弊并直接不通过。**

### 2. 逐项独立复核 M1–M4 与 B

不要只看 `verify_round3_findings.py` 变绿就放过。**自己另写探针**（可以用
`py -3.12 -c "..."` 或临时脚本，但**不要**把这些临时文件留在仓库里；如果留了，必须说明并在报告里注明）。
至少覆盖：

- **M1**：未知键在 **config 根 / subject / reviews 根 / item / schedule** 五处是否都被拒？
  reviews 根的 `schema_version` 是否校验？错误信息是否带精确路径？
  `ky/contracts/__init__.py` 与 `ky/models.py` 里关于"JSON Schema guards shape"的注释是否与实现一致？
- **M2**：未知科目、inactive 科目是否都被拒？`_deficit_ratio` 的宽泛 `except` 是否已移除？
  跨文档校验函数是否真的被 `preflight` 调用（而不是只在测试里被调用）？
  `select_daily_reviews` 入口是否能被绕过（直接传 `subject_id="ghost"` 是否仍会入计划）？
- **M3**：Claude 选了 (a) 保底优先还是 (b) 配置期拒绝？验证其选择在**所有**合同通过的配置下都不崩：
  特别测试"复习恰好占满硬上限 + 保底总和接近总预算"的组合，以及 `new_learning_minutes` 为 0 的情形。
- **M4**：`.nan` / `.inf` / `-.inf` 在 `weight`、`review_reserve_ratio`、`hard_max_ratio`、
  `schedule.ease_factor` 上是否全部带路径拒绝？**注意 `inf` 之前是被范围比较偶然挡住的**，
  确认现在是真的有显式有限性检查（把范围检查临时放宽也应能挡住，或者读代码确认 `isfinite` 存在）。
- **B**：2,000,000 分钟预算 + 权重和 1.0000009 是否还能超分？请**遍历多个预算规模**找其他超分点。

### 3. 复核被点名的 6 条假测试

对 `test_borrowing_to_the_hard_cap_only_happens_for_urgent_items`、
`test_defer_count_two_makes_an_item_urgent`、
`test_subject_deficit_breaks_ties_towards_the_neglected_subject`、
`test_a_deferred_item_gains_priority_on_a_later_day`、
`test_stricter_policy_defers_more`、
`test_exact_40_20_40_split_when_the_floor_stops_binding`

逐条判定：**现在是否真的会在对应实现被破坏时失败？**
方法是**变异测试**：临时把对应逻辑改坏（例如让 `_is_urgent` 恒返回 `True`、
删掉 deficit 排序项、让 policy 参数被忽略），跑该测试，确认它会红。改坏后**必须还原**。
报告里给出每条测试的变异结果（`变异点` / `是否变红` / `还原确认`）。

**如果某条测试仍然是空真或过弱，明确指出并给出应改成什么。**

### 4. 裁决

给出 `通过 / 有条件通过（条件：…） / 不通过`。
如果仍有 MAJOR，列出精确的：
`位置(文件:行)` / `触发条件` / `最小复现命令或代码` / `实际输出` / `修法`。

---

## 输出

- 写入 `F:\workspace\kaoyan-ai-system\review\rounds\round-3-reaudit-codex.md`
- 用**中文**。
- 只写这一个文件：**不要修改** `ky/**`、`tests/**`、`tools/**`、`docs/**`、`review/**` 中的其他文件。
- 不要执行 git。
- 不要写操作确认语。最后用一句话回复：裁决 + 文件路径 + `verify_round3_findings` 的 X/12 与 exit code + 变异测试几条变红。
