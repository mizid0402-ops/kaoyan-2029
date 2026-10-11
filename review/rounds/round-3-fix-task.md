# 第三轮补：按 Codex 审查结论修复（Claude 执行）

## 你的处境

第三轮是**背对背**的：Codex 独立审查了阶段 1 代码，你做了自审。**你在自审时看不到 Codex 的报告**，
所以你的 A1–A6 全部是**你自己发现的另一批缺陷**，而 Codex 报的 4 个 MAJOR 你一条都没碰。

现在把两份报告合并，由你统一修复。

## 必须先读

1. `F:\workspace\kaoyan-ai-system\review\rounds\round-3-codex.md` —— Codex 的独立审查（裁决：**不通过**）
2. `F:\workspace\kaoyan-ai-system\review\rounds\round-3-claude.md` —— 你自己的自审报告
3. `F:\workspace\kaoyan-ai-system\tools\verify_round3_findings.py` —— **DSH 写的独立验证脚本**

## 当前已实测的状态（DSH 运行，不是推测）

```text
$ py -3.12 -m unittest tests.test_contracts tests.test_review_scheduler
Ran 56 tests in 0.296s
OK                                        # 你的自审修复有效，测试确实变多了

$ py -3.12 tools/verify_round3_findings.py
[FAIL] M1 unknown key in subject: accepted; floor defaulted to 0
[FAIL] M1 unknown key at root: accepted silently
[FAIL] M1 reviews root schema_version: root schema_version ignored; 1 items accepted
[FAIL] M2 unknown subject rejected: selected=('rv_ghost',)
[FAIL] M2 inactive subject rejected: selected=('rv_pol',)
[FAIL] M3 floor-vs-hardcap conflict: crash on a contract-valid config:
       review=72 new=48 -> ValueError: min_daily_minutes sum (60) exceeds the new-content budget (48)
[FAIL] M4 weight=nan rejected: accepted
[PASS] M4 weight=inf rejected
[PASS] M4 weight=-inf rejected
[FAIL] M4 review_reserve_ratio=nan rejected: accepted
[PASS] M4 review_reserve_ratio=inf rejected
[FAIL] B tolerance-sum overspend: allocated 2000001 for a 2000000 budget

3/12 checks passed                             # exit 1
```

**结论：Codex 的 4 个 MAJOR 全部仍然存在。你的 56 个测试没能覆盖它们——这正是"测试全绿 ≠ 验收通过"的实例。**

---

## 你的任务：修掉下面 4 项，直到 `tools/verify_round3_findings.py` 12/12 通过

### M1 —— 未知键 / 拼错键 / 根 schema_version 被静默忽略
**要求**：所有合同映射（config 根、每个 subject、reviews 根、每个 item、`schedule` 映射）都必须
**拒绝未知键**，并给出精确字段路径（例如 `subjects[0].min_daily_minute`）。
reviews 根节点的 `schema_version` 必须被读取并校验。
**注意**：`ky/contracts/__init__.py` 目前是空壳，`models.py` 的注释却声称"JSON Schema guards shape"——
要么真正落地 schema 校验，要么改掉那句不实注释并实现允许键集合校验。**不要留下与实现不符的注释。**

### M2 —— 复习条目的 `subject_id` 未与配置交叉校验
**要求**：参与调度的每个 `ReviewItem.subject_id` 必须**存在且 `active: true`**；否则带
`items[i].subject_id` 路径拒绝。
同时删掉 `_deficit_ratio` 里那个 `except Exception` —— 合同错误不能被降级成"无意见"。
提供一个显式的跨文档校验函数（例如 `validate_items_against_config(config, items)`），
由 `preflight` 在调度前调用；`select_daily_reviews` 入口也要防御（不能只靠调用方自觉）。

### M3 —— 保底分钟与复习硬上限冲突，合法配置在正常满载日崩溃
**要求**：先冻结语义，再一致实现。二选一，并在 `docs/` 之外（即代码注释 + 你的报告里）写清选了哪个、为什么：
- **(a) 保底优先**：复习的**有效硬上限**取 `min(review_hard_cap, total - floor_total)`，保证任何合同通过的配置都能出计划；
- **(b) 配置期拒绝**：`validate_config` 要求 `sum(active floors) <= total_daily_minutes - review_hard_cap_minutes()`，违反即带路径 `ContractError`。

无论选哪个，**已被合同接受的配置 + 已验证的条目，都不允许在 CLI 组装结果时抛异常**。
`__main__.py` 里 `allocate_new_content` 的调用现在没有任何捕获，这也是崩溃路径的一部分。

### M4 —— `NaN` 绕过所有浮点校验
**要求**：所有合同浮点值必须 `math.isfinite`；`.nan` / `.inf` / `-.inf` 全部带路径拒绝。
注意 `inf`/`-inf` 现在只是因为撞上了范围比较才被拒，`nan` 三个比较全为 false 所以漏网——
必须显式加有限性检查，而不是依赖范围比较的副作用。

### B 项（Codex 在 B 节提出，一并修）
**权重容差内的和（1.0000009）会导致超分**：`_proportional_split` 只处理正 `leftover`，不回收负差。
在 2,000,000 分钟预算下实测分出 2,000,001。修法：分配前把权重归一化，或同时处理正负舍入差，
保证**任何**通过合同的输入都精确加总，不超预算。

---

## 同时必须做的（这是 Codex D 节的裁定，也是本次最重要的教训）

Codex 指出你的测试里有 **7 条假测试/过弱测试**，其中这几条必须重写：

1. `test_borrowing_to_the_hard_cap_only_happens_for_urgent_items` —— 空真：`if result.review_minutes > soft`
   为 false，主体断言从未执行。**必须构造真正跨过 soft 配额的用例**。
2. `test_defer_count_two_makes_an_item_urgent` —— 该条目排在第二，累计 20 分钟时就进了 soft 配额，
   删掉 `_is_urgent` 也会通过。**必须让该条目成为"只有 urgent 才能入选"的那一条**。
3. `test_subject_deficit_breaks_ties_towards_the_neglected_subject` —— 实际 soft=54，两条都被选，
   断言无法证明顺序。**必须把预算压到只容得下一条，并断言精确集合与顺序**。
4. `test_a_deferred_item_gains_priority_on_a_later_day` —— 次日只传入延期的三条，全都能装下，
   不证明优先级提升。**必须让新到期项与延期项竞争同一份有限预算**。
5. `test_stricter_policy_defers_more` —— 用 `>=`/`<=`，允许两者结果相同。**必须构造只因阈值不同而
   分流的反例，并断言精确 review_id**。
6. `test_exact_40_20_40_split_when_the_floor_stops_binding` —— 期待值 40/35/40 本身不是 40/20/40，
   测试名与注释在说谎。**改名或改断言，让名称与事实一致**。

另外补上 Codex 要求的边界用例：soft/hard 恰好等于边界、单项恰好等于 hard cap、
同优先级下逐级 tie-break、review 根 schema_version 不支持时 exit 2、
`--urgent-overdue-days 0` 应是受控 usage error（exit 3）而不是 traceback（exit 1）。

---

## 约束

- 允许修改：`F:\workspace\kaoyan-ai-system\ky\**`、`F:\workspace\kaoyan-ai-system\tests\**`、
  `F:\workspace\kaoyan-ai-system\tools\**`（只在需要时）。
- **禁止修改**：`review/**`、`docs/**`、`README.md`，以及 `F:\workspace\study` 下的任何文件。
- 不要执行 git。
- 本机 `py` 启动器**不回显子进程输出**，所有 Python 命令**必须用 `py -3.12`**。
- 报告写入：`F:\workspace\kaoyan-ai-system\review\rounds\round-3-fix-claude.md`

## 报告必须包含

- **逐项修复**：M1/M2/M3/M4/B + 6 条假测试，每项给 `位置` / `改法` / `为什么这样改`。
- **M3 的政策选择**：你选了 (a) 还是 (b)，理由是什么，对用户体验的影响是什么。
- **实测证据**：贴出 `py -3.12 -m unittest tests.test_contracts tests.test_review_scheduler` 与
  `py -3.12 tools/verify_round3_findings.py` 的**真实完整输出**（含 12/12 计数与 exit code）。
  如果仍有未通过项，**如实写明**，不要修改脚本让它变绿——`tools/verify_round3_findings.py` 是
  审查方的验证工具，**不允许修改**（这一条是硬约束）。
- **仍未解决**：你没能修掉的，以及需要用户或审查者决定的问题。
