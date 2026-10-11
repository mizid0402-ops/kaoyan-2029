# 第三轮重审：Codex 独立复审

## 裁决

**不通过（Gate: FAIL）。**

M1、M2、M3、M4 均已修复，6 条被点名的测试也都能杀死对应变异；但是任务书明确要求一并修复的 B 项只在 2,000,000 分钟样例上变绿，在更大、仍能通过合同的预算上会再次超分。该问题是原 B 项同一根因的残留，不是无关扩展，因此当前门禁仍失败。

## 范围与方法

- 完整阅读了 `review/rounds/round-3-reaudit-task.md`、上一轮 Codex 报告、Claude 修复报告、当前验证脚本及 M1–M4/B 的实现与直接测试。
- 运行任务书指定的两个命令；所有 Python 命令均使用 `py -3.12`。
- 独立探针全部通过标准输入交给 `py -3.12 -`，未在仓库留下临时脚本。
- 变异只临时修改 `ky/models.py`、`ky/schedule/review_clip.py`、`ky/schedule/budget.py`；每次变异后立即恢复，并用目标测试和 SHA-256 双重确认。最终三个实现文件及两个测试文件的哈希均与变异前一致。
- 未执行 git。

## 验证脚本完整性检查

已逐行检查当前 `tools/verify_round3_findings.py`：

- 当前 SHA-256：`79EA37099FD8FCE405A42D2603576D37BD84C9BD0C82B883EE5B12A7037AF825`。
- 脚本共实际登记 13 个检查；不导入 `tests/**`，M1 的 reviews 根版本检查调用真实 `load_review_items`，B 项调用真实 `allocate_new_content`，没有发现通过 mock、跳过断言或固定输出伪造绿色结果的路径。
- 当前目录没有 `.git` 元数据（`Test-Path .git` 为 `False`），且任务明确禁止执行 git，所以无法作 git index/commit 基线比对。
- 已确认的时间与内容事实：Claude 的修复报告创建于 21:56:10，记录的是旧版 `11/12`；当前脚本最后修改于 21:57:03，并已改成修正 reviews schema 探针且新增 reviews 根未知键的 13 项版本。因本轮覆盖设定明确要求报告 `X/13`，这与当前审查方版本吻合。无法仅凭本地文件确认 21:57 的修改者身份，因此没有证据把这次审查方脚本更新归为 Claude 作弊。

## 规定检查的真实结果

```text
py -3.12 -m unittest tests.test_contracts tests.test_review_scheduler
........................................................................
----------------------------------------------------------------------
Ran 72 tests in 0.264s

OK
exit code = 0
```

```text
py -3.12 tools/verify_round3_findings.py
[PASS] M1 unknown key in subject: subjects[0].min_daily_minute: unknown field 'min_daily_minute'
[PASS] M1 unknown key at root: totle_daily_minutes: unknown field 'totle_daily_minutes'
[PASS] M1 reviews root schema_version: F:/workspace/kaoyan-ai-system/tests/fixtures/reviews/reviews-unsupported-schema-version.yaml.schema_version: unsupported schema_version 99
[PASS] M1 reviews unknown root key: F:/workspace/kaoyan-ai-system/tests/fixtures/reviews/reviews-bad-schema-version.yaml.iten: unknown field 'iten'
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
exit code = 0
```

## M1–M4 独立复核

### M1 — RESOLVED

- `ky/models.py:54-85,115-126` 为 config 根、subject、reviews 根、item、schedule 分别定义允许键集合并统一失败关闭。
- 独立探针逐处注入未知键，均携带精确路径拒绝：
  - config 根：`totle_daily_minutes`
  - subject：`subjects[0].min_daily_minute`
  - reviews 根：`...reviews-bad-schema-version.yaml.iten`
  - item：`items[0].mystery`
  - schedule：`items[0].schedule.mystery`
- `load_review_items` 对 reviews 根 `schema_version: 99` 以 `...schema_version` 路径拒绝。
- `ky/contracts/__init__.py:1-5` 与 `ky/models.py:3-11` 均明确说明采用显式允许键检查、没有独立 JSON Schema 层，注释与实现一致。

### M2 — RESOLVED

- `ky/models.py:671-693` 的 `validate_items_against_config` 分别拒绝未知和 inactive 科目，独立探针均得到 `items[0].subject_id`。
- `ky/__main__.py:129-135` 的 preflight 明确调用该函数；用 mock 让该调用抛出带哨兵信息的 `ContractError`，实测 preflight 返回 2 且 stderr 含 `cross: sentinel-preflight-call`，证明不是只在测试里调用。
- `ky/schedule/review_clip.py:192` 在 selector 入口再次调用跨文档校验。直接向 selector 传 `ghost` 或 inactive `politics` 均被拒，不能绕过。
- `ky/schedule/review_clip.py:128-141` 的 `_deficit_ratio` 已无宽泛 `except`。

### M3 — RESOLVED

Claude 选择的是 **(b) 配置期拒绝**。`ky/models.py:386-401` 要求：

```text
sum(active floors) <= total_daily_minutes - review_hard_cap_minutes()
```

独立验证结果：

- 遍历 16 个总预算与 7 个 hard ratio，共 112 组“保底取允许边界、复习恰好填满 hard cap”的合同有效配置；selector 与 allocator 均无崩溃，复习、新内容、分科分配三项加总一致。
- `total=120, hard=0.60, floor=48`：`review=72, new=48, allocated=48`。
- 保底接近总预算的 `total=120, hard=0.01, floor=119`：`review=1, new=119, allocated=119`。
- `new_learning_minutes=0` 的 `total=120, hard=1.0, floor=0`：`review=120, new=0, allocated=0`。
- 同一 120/.60 配置把 floor 提到 49 时，在配置阶段以路径 `subjects` 拒绝。

### M4 — RESOLVED

- `ky/models.py:161-180` 在任何范围比较前显式执行 `math.isfinite(value)`。
- 独立探针对 `weight`、`review_reserve_ratio`、`hard_max_ratio`、`items[0].schedule.ease_factor` 分别注入 `nan`、`inf`、`-inf`，共 12 个组合全部以各自精确路径拒绝。
- 将 `WEIGHT_TOLERANCE` 在进程内临时放宽为 `inf` 后，`weight=nan` 仍由有限性检查拒绝，证明不是依赖范围比较偶然挡住。

## B — UNRESOLVED（MAJOR）

严重级别：**MAJOR**。虽然该预算远超实际日常规模，但任务明确要求对多个预算规模寻找其他超分点，且现行合同没有 `total_daily_minutes` 上界；“所有通过合同的输入均精确加总”仍是本轮明确验收条件。

- **位置：** `ky/schedule/budget.py:63-80`（浮点归一化、取整和 leftover 回收），调用点 `ky/schedule/budget.py:109`。
- **触发条件：** `total_daily_minutes = new_content_minutes = 100_000_000_000_000_000`，两个 active 科目权重为 `0.5` 和 `0.5000009`。该配置通过 `validate_config`。
- **实际输出：** 两科分别得到 `49_999_955_000_040_503` 与 `50_000_044_999_959_503`，总和 `100_000_000_000_000_006`，比预算多 6 分钟。
- **期望：** 输出总和必须精确等于 `100_000_000_000_000_000`。
- **根因：** 大整数乘归一化后的 binary float 时产生多分钟舍入误差；`leftover < 0` 分支的 `order[:-leftover]` 最多遍历一次科目列表，每科只减 1，无法回收绝对值大于科目数的负 leftover。
- **更广证据：** 低至 100,000,000 的 25,050 组扫描无异常；把预算扩展到 `2^53`、十进制幂及最高约 `10^308` 后，5,724 组组合中有 5,345 组加总不精确。简单边界输出为：

  ```text
  budget=2000000                  delta=0
  budget=100000000               delta=0
  budget=1000000000000000        delta=0
  budget=10000000000000000       delta=0
  budget=100000000000000000      delta=6
  ```

- **最小复现代码：** 将下列代码通过标准输入交给 `py -3.12 -`：

  ```python
  from ky.models import validate_config
  from ky.schedule.budget import allocate_new_content

  n = 100_000_000_000_000_000
  config = validate_config({
      "schema_version": 1,
      "project_id": "b",
      "total_daily_minutes": n,
      "review_reserve_ratio": .45,
      "hard_max_ratio": .60,
      "subjects": [
          {"subject_id": "a", "display_name": "A", "weight": .5, "active": True},
          {"subject_id": "b", "display_name": "B", "weight": .5000009, "active": True},
      ],
  })
  allocations = allocate_new_content(config, n)
  print([x.minutes for x in allocations], sum(x.minutes for x in allocations))
  ```

- **修法：** 不要用 binary float 计算任意大整数预算的最大余数。可把已校验权重转为精确有理数（例如按 `str(weight)` 构造 `Fraction`），用整数 `divmod` 计算各科 floor 与余数，再按精确余数分配；或者为预算设置明确、合理且经过证明的合同上界。无论选择哪种，还必须完整处理任意大小的正/负 leftover，不能用“每科最多调整 1”隐含假设。
- **回归测试：** 将 `test_weight_sum_within_tolerance_never_overspends_the_budget` 参数化，至少加入 `10**17` 与 `2**53` 附近的若干预算，并同时断言“无超分、无漏分、各科分钟非负”。

## 6 条点名测试的变异结果

| 被复核测试 | 变异点 | 是否变红 | 还原确认 |
|---|---|---:|---|
| `test_borrowing_to_the_hard_cap_only_happens_for_urgent_items` | `_is_urgent` 恒为 `False` | 是；期望 `("rv_filler", "rv_urgent")`，实际仅 `("rv_filler",)`，exit 1 | 恢复后单测 exit 0；`review_clip.py` 哈希恢复 |
| `test_defer_count_two_makes_an_item_urgent` | 删除 defer-count 紧急判定，只保留 overdue 判定 | 是；目标项落入 deferred，exit 1 | 恢复后单测 exit 0；`review_clip.py` 哈希恢复 |
| `test_subject_deficit_breaks_ties_towards_the_neglected_subject` | `_deficit_ratio` 恒为 `0.0` | 是；实际选 `rv_aaa_math` 而非 `rv_zzz_eng`，exit 1 | 恢复后单测 exit 0；`review_clip.py` 哈希恢复 |
| `test_a_deferred_item_gains_priority_on_a_later_day` | `with_deferral` 把 due_date 推后一天且不增加 defer_count，使延期不再提升优先级 | 是；第二天实际选 `rv_aaa_fresh`，exit 1 | 恢复后单测 exit 0；`models.py` 哈希恢复 |
| `test_stricter_policy_defers_more` | selector 忽略传入 policy，始终用默认策略 | 是；严格策略仍选中 `rv_target`，exit 1 | 恢复后单测 exit 0；`review_clip.py` 哈希恢复 |
| 原 `test_exact_40_20_40_split_when_the_floor_stops_binding`，现已诚实重命名为 `test_floor_rides_on_top_of_the_weight_split_at_a_large_remainder` | allocator 不从总预算扣除 floor 就切 remainder | 是；math 实际 46、期望 40，exit 1 | 恢复后单测 exit 0；`budget.py` 哈希恢复 |

结论：**6/6 均会在对应实现被破坏时变红，不再是空真或仅比较弱不等式的测试。** 第 6 条已通过重命名纠正原先错误语义，复核的是其替代测试。

最终还原哈希：

```text
ky/models.py                    59939A2198DC21559CF95AB5E079A9FC945B732FC1A2AF8719C08F68755FB99E
ky/schedule/review_clip.py      2F2FA2098E4EA4F39B02959D68CC93C14D4BC4F2D8944EA121FE2289F49D39D6
ky/schedule/budget.py           9539A056BF441ED76DECF8E57B923DDCC5AB5B35A43833F00139D9129646800D
tests/test_contracts.py         1C8B2DEC47CC84993C6772C64EA48901E30171823A26B4667873B1714FB8B221
tests/test_review_scheduler.py  8CFD818677FB19D2297F570275C086E03DA195BBD3CCB06E12C132D3DD4CAEBD
```

## Gate Decision

**FAIL / 不通过。**

M1–M4 已解决且 6 条测试有效，但 B 项在合同允许的大预算下仍然超分，必须修复任意大整数下的精确分配，或为预算加上明确且可证明安全的合同上界，才能通过本轮复审。
