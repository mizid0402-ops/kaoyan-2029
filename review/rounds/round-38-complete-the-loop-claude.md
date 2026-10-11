# round-38 补齐报告：残项 A（完成事件→推进复习队列）+ 残项 B（monthly_close 计划 vs 实际）

实施者：Claude Sonnet 5（high）。

---

## 0. 开工前

### 0.1 `git status`（开工前，逐字）

```
On branch master
Main branch (you will usually use this for PRs): main

Status:
(clean)
```

（工具自带的会话开头快照；我另外手动确认了一次，见下方 `git log`。）

```
$ git status
On branch master
nothing to commit, working tree clean

$ git log --oneline -5
6ffc5f2 docs: task book for closing the two residual stage-2 gaps
e42c0d5 docs: record final commit hash in round-37 stage-2 report
879f00b feat(stage2): guardrail hole fixes, daily-minutes override, RoutePlan/snapshot, day-plan store, completion state machine
c971e53 docs: stage-2 implementation task book, plus both independent reviews
265d39d docs: stage-2 feasibility brief for three-way review
```

工作区干净，前置提交与任务书描述一致。

### 0.2 测试基线

```
$ py -3.12 -m unittest discover -s tests -q
----------------------------------------------------------------------
Ran 398 tests in 111.807s

OK
```

与任务书声明的 **398 tests / OK** 一致。

### 0.3 四个文件的开工前 SHA-256

| 文件 | 开工前 SHA-256 |
|---|---|
| `ky/schedule/monthly_close.py` | `d3e6b8498236c0f52d3ea478f90adb33fd485e75e910e85f1b42a79221b42e83` |
| `ky/__main__.py` | `4fcdff8ca2265e448d4d16db126f7474ad7144ff057d459adf9398b5b8ce5615` |
| `ky/storage/day_plan_store.py` | `4734d39440876e84fd8a17aae3287fc0f262bf281f1a18b57893d98b80a9e16b` |
| `ky/schedule/completion.py` | `c2af75ac3a70eca893e32ceb5ebe9549413b57fc1fbb6c60d3f933ec887e5402` |

（用 `py -3.12 -c "hashlib.sha256(...)"` 实测，非推断。）

### 0.4 收工后 SHA-256（供对照）

| 文件 | 收工后 SHA-256 | 是否改动 |
|---|---|---|
| `ky/schedule/monthly_close.py` | `4d8950aba536c6257bcc3f97686358952ebb691c2940eb35515fbae97e5afd7f` | 改了（残项 B） |
| `ky/__main__.py` | `d06b70ed3eb52ffc9da11b1ad98b631706e4b7f056046408cff639d6e3fabeec` | 改了（残项 A 的 CLI 接线 + 残项 B 的 CLI 输出） |
| `ky/storage/day_plan_store.py` | `af1e9a2284705fcda7383fde95286ece804c19d49f4add00c1fb673747f5aa34` | 改了（残项 A 的核心接线 + 残项 B 的持久化） |
| `ky/schedule/completion.py` | `c2af75ac3a70eca893e32ceb5ebe9549413b57fc1fbb6c60d3f933ec887e5402` | **未改**（`advance_review_item` 本身是对的，round-37 已验证过 17 个测试，本轮只是接上它，不改它） |

---

## 1. 残项 A 怎么打通的：完成事件 → 推进 ReviewItem → 写回复习队列

### 1.1 具体调用链

```
CLI: py -m ky day-plan record --done <event.yaml> --store <day-plan-store> --review-store <queue-root>
  ky/__main__.py::day_plan_main() "record" 分支
    │
    ├─ parse_completion_event(raw)                          -- 解析完成事件（round-37 既有）
    │
    ├─ [新增] 若给了 --review-store 且 event.reviews 非空：
    │     ReviewShardStore(args.review_store).load()         -- 只读，先检查所有 review_id 是否存在
    │     若有未知 id → 打印 guardrail violation，exit 2，   -- 此时还没写任何东西
    │       什么都不写（既不写 completion event，也不动队列）
    │
    ├─ DayPlanStore(args.store).write_completion_event(event) -- round-37 既有：把事件写成历史记录
    │
    └─ [新增] advance_review_queue(review_store, event)      -- ky/storage/day_plan_store.py 新函数
          │
          ├─ review_store.load()                              -- 读出当前整条队列（ReviewShardStore，round-37 之前就有，
          │                                                       但一直没人在“完成”路径上调用它的写入）
          ├─ 对每个 ReviewCompletion：
          │     - review_id 不在队列里 → 已在上一步拦截，这里理论上不会再触发
          │       （但函数自身也做了这个检查，所以直接单独调用这个函数做测试时同样安全）
          │     - item.last_reviewed_on == completion.completed_on
          │       and item.last_quality == completion.quality
          │         → 判定为“已经应用过的重放”，跳过，不再次推进（幂等）
          │     - 否则 → advance_review_item(item, completion)  -- ky/schedule/completion.py 既有纯函数（round-37），
          │                                                        本轮完全没有改动
          └─ review_store.write(全部条目)                      -- ReviewShardStore 自己的原子写路径（round-37 之前就有），
                                                                   不是另造的写法
```

### 1.2 关键设计决定

- **失败关闭（fail closed）在写任何东西之前**：CLI 层先用 `review_store.load()` 做一次只读的存在性检查，
  任何一个 `review_id` 不在队列里，就连 `write_completion_event` 都不调用——避免出现“completion event 说某项复习发生了，
  但队列没跟着动”这种孤儿记录。
- **幂等的判定标准**：`item.last_reviewed_on == completion.completed_on and item.last_quality == completion.quality`。
  选择这个而不是“同一天有没有写过 completion event”的原因是：`DayPlanStore.write_completion_event` 本身对同一天是
  write-once（第二次写同一天会被拒绝），这在 CLI 整体流程里已经保证了“同一天不会被记录两次”；但任务书明确要求
  **直接对 `advance_review_queue` 这个函数本身**验证幂等（可以脱离 CLI、脱离 DayPlanStore 单独调用两次），所以幂等性
  必须做在这一层，而不能依赖上层的 write-once 语义。
- **写回用的是 `ReviewShardStore.write()`**，不是新造的写路径——满足任务书“用 ReviewShardStore 既有的写路径，不要另造一套”。
  `write()` 内部会重新跑 `validate_review_items`，所以“推进后的项仍必须通过 `validate_review_item`”这条是自动满足的，
  不是我额外加的检查。
- `--review-store` 是**可选**参数。不给它，`day-plan record` 的行为与 round-37 完全一致（只写 completion event，
  不碰任何队列）——这是为了不破坏 round-37 已有的 CLI 回归测试
  `test_record_completion_event_and_duplicate_day_is_rejected`（它提交了一个带 `rv1` 复习的事件，但没有配套的复习队列）。
  **这意味着“打通”目前是 opt-in 的：调用方必须显式传 `--review-store` 才会真的推进队列。** 我认为这是必要的取舍
  （见下方“没有把握的地方”第 1 条），因为强制要求队列存在会让所有不关心复习、只想记录词汇进度的 `day-plan record`
  调用全部失败。

### 1.3 代码改动位置

- `ky/storage/day_plan_store.py`：新增 `ReviewQueueAdvanceReport`（dataclass）与 `advance_review_queue()`（函数），
  新增 `DayPlanStore.load_month_completions()`（供残项 B 用）。
- `ky/__main__.py`：`day_plan_main()` 的 "record" 分支新增 `--review-store` 参数与上述接线逻辑。
- `ky/schedule/completion.py`：**未改动**（哈希前后一致，见 0.4）。

---

## 2. 残项 B 怎么改的：monthly_close 计划 vs 实际

### 2.1 选择：新增可选参数，而不是新增函数

`close_month()` 新增一个**关键字可选参数** `completions: Sequence[CompletionEvent] | None = None`。

**理由**：
1. 任务书要求“既有调用方不许破坏”。`close_month` 已有两处调用（`ky/__main__.py::month_close_main`、
   `ky/storage/day_plan_store.py` 内部无直接调用，但被多个测试直接调用）全部使用关键字参数调用，新增一个默认为
   `None` 的关键字参数对它们零影响——不需要改一行既有调用代码。
2. 新增函数（比如 `close_month_with_actuals()`）会导致两个函数维护两套几乎相同的月度汇总逻辑（日期去重、
   guardrail 校验、residue 计算……），或者退化成“新函数内部调用旧函数再补字段”，徒增一层不必要的间接。
   既然“计划”和“实际”本质上是同一次月度汇总的两个视角，用同一个函数、同一次遍历产出更直接。
3. `MonthClose` 本身也只新增字段（`actual_*`、`vocab_delivered_vs_planned`），没有删除或重命名任何既有字段，
   `_MONTH_CLOSE_KEYS`（`day_plan_store.py`）用 `frozenset` 白名单校验，我把新字段加进了白名单，
   旧格式的 `month_close.yaml`（没有这些新字段的键）在 `_month_close_from_mapping` 里用 `.get(key, 默认值)`
   读取，读旧文件不会报错，新字段落回“未提供”的默认值（`actual_data_available=False`，其余 `None`）。

### 2.2 “计划 vs 实际”的具体字段

| 字段 | 含义 | 来源 |
|---|---|---|
| `actual_data_available` | 本次调用是否传了 `completions`（哪怕传的是空列表也算“传了”） | 新 |
| `days_with_completion_events` | 落在本月内的 completion event 天数 | 新，来自 `CompletionEvent.day` |
| `actual_reviews_completed` | 本月完成的复习条目总数 | 新，来自 `CompletionEvent.reviews` |
| `actual_vocab_delivered_words` | 本月投递（展示）给学习者的单词总数 | 新，来自 `CompletionEvent.vocab.delivered_words` |
| `actual_vocab_practiced_words` | 本月实际练习过的单词总数 | 新，**与上一行分开统计，绝不相加** |
| `vocab_delivered_vs_planned` | `actual_vocab_delivered_words - vocab_items_introduced`（既有的“计划新词数”字段） | 新，差额 |
| `vocab_items_introduced`（既有字段，未改） | 计划新学多少词 | 既有，来自 `DayPlan.vocab_new_items` |

**「无完成事件的月份」的区分**：`completions=None`（调用方压根没问）→ `actual_data_available=False`，
所有 `actual_*` 字段是 `None`（不是 0）；`completions=[]` 或传了列表但月内一条都没有 → `actual_data_available=True`，
`actual_*` 字段是真实的 `0`，并且会在 `notes` 里追加一条 `"0 completion events recorded for this month -- a measured
zero, not missing data"`。这是任务标准 4 的直接实现：**"0" 和 "不知道" 是两个不同的状态，不能互相冒充。**

**`vocab_delivered_vs_planned` 的诚实声明**：这个差额不是严格意义上的同类对比——`vocab_items_introduced`
只统计"计划新学的词"，而 `delivered_words` 可能包含之前已经学过、这次又拿出来复习展示的词。我在
`MonthClose` 的字段注释和 `close_month` 的 docstring 里都写明了这一点，没有假装它是精确的对账。

### 2.3 代码改动位置

- `ky/schedule/monthly_close.py`：`MonthClose` 新增 6 个字段；`close_month()` 新增 `completions` 参数与对应逻辑。
- `ky/storage/day_plan_store.py`：`_MONTH_CLOSE_KEYS` / `_month_close_mapping` / `_month_close_from_mapping`
  三处同步补上新字段（否则会被静默丢弃，写盘再读回来就丢数据了）；新增 `DayPlanStore.load_month_completions()`。
- `ky/__main__.py`：`month_close_main()` 调用 `store.load_month_completions()` 并传给 `close_month`，
  JSON payload 与人类可读输出都补上新字段。

---

## 3. 9 条标准的实际输出

### 标准 1（端到端推进，读回队列可见 due_date 已变）

```
$ py -3.12 -m unittest tests.test_review_queue_advance.EndToEndAdvanceTest \
      tests.test_cli.DayPlanCliTest.test_record_with_review_store_advances_the_queue_end_to_end -v
test_due_date_and_interval_actually_change_in_the_reloaded_queue ... ok
test_multiple_reviews_in_one_event_all_advance ... ok
test_record_with_review_store_advances_the_queue_end_to_end ... ok

Ran 3 tests in ...
OK
```

手工 CLI 复现（真实跑了一遍，不是伪造的示例）：

```
$ py -3.12 -m ky day-plan record --config tests/fixtures/config/config-minimal.yaml \
      --done tmp_demo/done.yaml --store tmp_demo/store --review-store tmp_demo/review-queue
written: tmp_demo/store/2026-09/completion--2026-09-12.yaml (sha256 3fa6ddc6...)
review queue advanced: 1 item(s) (skipped as already-applied: 0)

$ py -3.12 -c "... ReviewShardStore('tmp_demo/review-queue').load()[0] ..."
due_date: 2026-09-14 interval_days: 2 phase: 1 last_reviewed_on: 2026-09-12
```

队列在磁盘上被一个**新的 `ReviewShardStore` 实例**重新读回（不是复用内存里的对象），`due_date` 从
`2026-09-12` 变成了 `2026-09-14`（fixed_bootstrap 阶梯 phase 0→1，间隔 2 天），证明写回是真实、持久化的。

### 标准 2（重复提交幂等）

```
$ py -3.12 -m unittest tests.test_review_queue_advance.IdempotencyTest -v
test_repeated_application_never_double_doubles_the_interval ... ok
test_same_completion_applied_twice_leaves_the_queue_identical_to_applying_once ... ok

Ran 2 tests in ...
OK
```

其中一个测试专门验证：连续 6 次提交同一个完成事件，`interval_days` 与只提交一次时完全相同（不是"翻倍再翻倍"）；
另一个测试验证第二次提交时 `manifest.yaml` 的字节**完全没有变化**（不仅内容相同，连版本号都没跳）。

### 标准 3（未知 review_id 报错且队列不变）

```
$ py -3.12 -m unittest tests.test_review_queue_advance.UnknownReviewIdTest \
      tests.test_cli.DayPlanCliTest.test_record_with_review_store_and_unknown_review_id_exits_2_and_writes_nothing -v
test_empty_queue_and_a_review_completion_is_also_unknown_id ... ok
test_one_bad_id_among_several_good_ones_writes_nothing_for_any_of_them ... ok
test_unknown_id_raises_and_touches_nothing ... ok
test_record_with_review_store_and_unknown_review_id_exits_2_and_writes_nothing ... ok

Ran 4 tests in ...
OK
```

用整棵目录树的 SHA-256（`_tree_hash`，与 round-37 `test_day_plan_store.py` 同款手法）做前后对比，
不只是"字段没变"，而是**目录里一个字节都没变**。也验证了"一个事件里好 id 和坏 id 混在一起"时，
好的那个也不会被单独推进——要么全部生效，要么全部不生效。

### 标准 4（推进后仍通过契约校验，quality 0..5）

```
$ py -3.12 -m unittest tests.test_review_queue_advance.ContractRevalidationTest -v
test_full_quality_sweep_round_trips_through_the_queue ... ok

Ran 1 test in ...
OK
```

这条本质上是自动满足的：`advance_review_queue` 写回用的是 `ReviewShardStore.write()`，
它内部本来就会对全部条目跑 `validate_review_items`；测试额外又对 `load()` 读回来的结果单独跑了一次
`validate_review_item`，双重确认 quality 0/1/2/3/4/5 全部不会产出违反契约的项。

### 标准 5（两处残项的变异测试 + 还原哈希）

见第 4 节，两处都做了。

### 标准 6（close_month 既有调用方不破坏；计划与实际分别呈现）

```
$ py -3.12 -m unittest tests.test_monthly_close.TestMonthlyCloseActualVsPlanned \
      tests.test_cli.MonthCloseCliTest tests.test_day_plan_store.MonthCloseWriteOnceTest -v
test_completions_outside_the_month_are_excluded ... ok
test_no_prescriptive_or_next_month_fields_leak_in_with_actuals ... ok
test_no_prescriptive_public_names_in_the_module ... ok
test_standard_1_no_completions_argument_behaves_exactly_as_before ... ok
test_standard_2_plan_and_actual_are_both_present_and_the_difference_reconciles ... ok
test_standard_3_delivered_and_practiced_are_never_summed ... ok
test_standard_4_zero_completion_events_is_a_measured_zero_not_missing_data ... ok
test_invalid_month_exits_3 ... ok
test_planned_and_actual_are_both_reported_and_reconcilable ... ok
test_reads_back_committed_day_plans_and_writes_nothing ... ok
test_actual_vs_planned_fields_round_trip ... ok
test_missing_month_close_loads_as_none ... ok
test_month_close_without_completions_round_trips_actuals_as_unavailable ... ok
test_second_write_is_rejected_not_overwritten ... ok
test_write_then_read_back ... ok

Ran 15 tests in ...
OK
```

手工 CLI 复现：

```
$ py -3.12 -m ky month-close --config tests/fixtures/config/config-minimal.yaml --store tmp_demo/store2 --year 2026 --month 9
month              : 2026-09
days planned/total : 1/30 (29 unplanned)
available/allocated: 120/90 min (utilisation 75.0%)  -- PLANNED, not actual
by channel         : {'knowledge': 60, 'vocab': 30, 'phrase': 0}
vocab introduced   : 15  -- PLANNED new items
overshoot          : 0 day(s), 0 min
unused / backlog   : 30 / 0 min (0 backlog day(s))
actual reviews done: 0  (1 day(s) with a completion event)
actual vocab       : delivered 3, practiced 1  (kept separate, not summed)
delivered vs planned new-items: -12
  note: 29 day(s) had no plan and were left as-is
ok                 : True
```

"计划新学 15 个" 与 "实际投递 3 个、实际练习 1 个" 分别出现，且 `delivered(3) - planned(15) = -12`
可以直接从上面两行核对出来，没有被合并成一个数。

### 标准 7（全绿，测试数 > 398）

```
$ py -3.12 -m unittest discover -s tests -q
----------------------------------------------------------------------
Ran 419 tests in ~105-135s（三次实测分别为 111.8s / 133.5s / 104.2s / 110.4s，机器负载导致的正常波动）

OK
```

**398 → 419，新增 21 个测试。**（`tests/test_review_queue_advance.py` 9 个 + `test_cli.py` 新增 4 个
+ `test_day_plan_store.py` 新增 2 个 + `test_monthly_close.py` 新增 6 个 = 21。）

### 标准 8（禁用函数名扫描 0 命中）

```
$ py -3.12 -m unittest tests.test_completion.DoesNotPrescribeTest \
      tests.test_day_plan_store.DoesNotPrescribeTest \
      tests.test_monthly_close.TestMonthlyCloseActualVsPlanned.test_no_prescriptive_public_names_in_the_module -v
test_no_prescriptive_public_names (test_completion.DoesNotPrescribeTest) ... ok
test_no_prescriptive_public_names (test_day_plan_store.DoesNotPrescribeTest) ... ok
test_no_prescriptive_public_names_in_the_module (test_monthly_close.TestMonthlyCloseActualVsPlanned) ... ok

Ran 3 tests in 0.000s
OK
```

`ky.schedule.completion`、`ky.storage.day_plan_store`、`ky.schedule.monthly_close` 三个模块的公开名字
（`__all__` / `dir()`）与相关 dataclass 字段名，对 `recommend*/suggest*/default*/optimal*/next_month_*`
前缀扫描，0 命中。

（第一次写 `monthly_close` 的扫描测试时用了 `dir(module)` 而不是 `module.__all__`，
被 `collections.defaultdict`（模块内部导入的标准库名字，不是本模块的公开 API）误判为 `default*` 命中，
改成扫描 `module.__all__` 后修复——这是一个我自己写错又自己修好的测试 bug，如实记录在此，
不代表 `close_month` 本身存在命名问题。）

### 标准 9（词库哈希仍为 839d48be…，不得触碰）

```
$ py -3.12 -c "print(hashlib.sha256(open('data/english_vocabulary/eng1_vocabulary.sqlite','rb').read()).hexdigest())"
839d48be37d7716b1a12da04e3e2293868ee379b6e09a13dd198dae5498d0e2c
```

与冻结值完全一致。本轮从未以写模式打开过这个文件（唯一涉及它的测试
`tests/test_monthly_close.py::TestVocabDatabaseStaysFrozen` 是 round-37 遗留的既有测试，本轮未改动，
且它本身也全程只读该文件）。

---

## 4. 两处变异测试的结果 + 还原哈希

### 4.1 残项 A：把"写回队列"那一步去掉

在 `ky/storage/day_plan_store.py::advance_review_queue()` 里把

```python
write_report = review_store.write(by_id.values())
```

改成

```python
# MUTATION (round-38 residual A proof): "write back" deliberately skipped here.
write_report = None
```

（保留 `advanced`/`skipped` 列表计算不变，只切掉真正的写入。）

```
$ py -3.12 -m unittest tests.test_review_queue_advance tests.test_cli -v
...
FAIL: test_due_date_and_interval_actually_change_in_the_reloaded_queue
FAIL: test_multiple_reviews_in_one_event_all_advance
FAIL: test_same_completion_applied_twice_leaves_the_queue_identical_to_applying_once
FAIL: test_record_with_review_store_advances_the_queue_end_to_end
----------------------------------------------------------------------
Ran 31 tests in 6.384s
FAILED (failures=4)
```

**4 个测试如预期变红。** 还原后：

```
mutated hash 未单独记录（改动本身很小，未在变异态下取哈希）；
恢复后重新计算：
restored: af1e9a2284705fcda7383fde95286ece804c19d49f4add00c1fb673747f5aa34
expected before (0.3 节记录的开工前哈希经本轮改动后的"目标终态"哈希，
                  即 0.4 节里的收工后哈希): af1e9a2284705fcda7383fde95286ece804c19d49f4add00c1fb673747f5aa34
一致。
```

`git diff --stat` 确认还原后与变异前相比只有本轮新增的 108 行改动（不多不少），没有残留的变异代码：

```
ky/storage/day_plan_store.py | 108 +++++++++++++++++++++++++++++++++++++
1 file changed, 108 insertions(+)
```

### 4.2 残项 B：把"消费 CompletionEvent"那一步去掉

在 `ky/schedule/monthly_close.py::close_month()` 里把

```python
if completions is not None:
```

改成

```python
# MUTATION (round-38 residual B proof): CompletionEvent consumption deliberately disabled.
if False and completions is not None:
```

```
$ py -3.12 -m unittest tests.test_monthly_close tests.test_cli tests.test_day_plan_store -v
...
FAIL: test_completions_outside_the_month_are_excluded
FAIL: test_standard_2_plan_and_actual_are_both_present_and_the_difference_reconciles
FAIL: test_standard_3_delivered_and_practiced_are_never_summed
FAIL: test_standard_4_zero_completion_events_is_a_measured_zero_not_missing_data
FAIL: test_planned_and_actual_are_both_reported_and_reconcilable (test_cli)
FAIL: test_reads_back_committed_day_plans_and_writes_nothing (test_cli)
FAIL: test_actual_vs_planned_fields_round_trip (test_day_plan_store)
----------------------------------------------------------------------
Ran 73 tests in 5.798s
FAILED (failures=7)
```

**7 个测试如预期变红**（覆盖单元测试、CLI 测试、存储往返测试三个层面）。还原后：

```
restored: 4d8950aba536c6257bcc3f97686358952ebb691c2940eb35515fbae97e5afd7f
expected (收工后哈希): 4d8950aba536c6257bcc3f97686358952ebb691c2940eb35515fbae97e5afd7f
一致。
```

```
ky/schedule/monthly_close.py | 61 +++++++++++++++++++++++++++++++++++++++++++-
1 file changed, 60 insertions(+), 1 deletion(-)
```

还原后重新跑了一次全量测试套件（见第 3 节标准 7 的最后一次 419/OK），确认恢复彻底、没有交叉污染其它模块。

---

## 5. `tools/daily_words.py` 旧路径是否仍会改词库哈希（实测）

**实测结论：会。**

`tools/daily_words.py` 的 `--db` 默认值就是 `data/english_vocabulary/eng1_vocabulary.sqlite`（真实冻结文件），
且脚本在非 `--reset` 模式下，如果当天（`--date`）还没有投递记录，会执行
`INSERT INTO delivery_log(...)`并 `conn.commit()`；`--reset` 模式则会 `DELETE FROM delivery_log`。

我做了一次**不触碰真实文件**的实测：把真实数据库复制到一个临时文件，对副本跑
`tools/daily_words.py --db <副本> --date 2099-01-01 --count 10`（选一个从未出现过的日期，
确保会真的走 INSERT 分支而不是"当天已投递，直接读旧记录"这条空跑路径）：

```
real db hash before (must be untouched): 839d48be37d7716b1a12da04e3e2293868ee379b6e09a13dd198dae5498d0e2c
scratch copy hash before:                839d48be37d7716b1a12da04e3e2293868ee379b6e09a13dd198dae5498d0e2c
[脚本正常输出 10 组词，returncode 0]
scratch copy hash after:  2b287a92f20e320afa60f9121ef9a88391d8ef92f9c2772d34e4c2d5fff171e8
copy changed: True
real db hash after (must match before): 839d48be37d7716b1a12da04e3e2293868ee379b6e09a13dd198dae5498d0e2c
real db untouched: True
```

**所以结论是**：只要有人不带 `--db` 参数直接跑 `py tools/daily_words.py`（或带 `--reset`），
真实词库文件的字节、进而它的 SHA-256，**依然会被改变**。当前"冻结"完全依赖"新系统绕开了这条旧路径"
（round-37/round-38 都改走 `DayPlanStore` 的 `CompletionEvent.vocab` 记录投递情况），
而不是这条旧脚本被物理禁止执行——`tools/daily_words.py` 本身没有任何只读锁、权限检查或路径白名单
阻止它写真实文件。这与任务书 §4 的描述完全吻合，本轮按要求**没有改动** `tools/**`。

---

## 6.「我实测到了」vs「我推断」

**我实测到了：**
- 开工前 `git status` 干净、398 测试基线、四个文件的开工前哈希。
- 残项 A 的端到端效果：CLI 手工跑一遍 `day-plan record --review-store`，读回队列看到 `due_date`/`interval_days`
  真的变了（不是只看函数返回值）。
- 残项 A 的幂等性：连续提交 6 次同一事件，`interval_days` 不变；第二次提交后 `manifest.yaml` 字节不变。
- 残项 A 的失败关闭：未知 `review_id` 时，用整棵目录树哈希确认了"一个字节都没写"。
- 残项 B 的端到端效果：CLI 手工跑一遍 `month-close`，肉眼看到"计划 15 / 实际投递 3 / 实际练习 1 / 差额 -12"
  四个数字分别出现在输出里。
- 419 个测试全绿（多次独立运行，含变异恢复后的最终确认跑）。
- 两处变异测试：mutate → 测试真的变红（4 个 / 7 个）→ 还原 → 哈希比对一致。
- `tools/daily_words.py` 会改词库哈希：用副本实测，returncode 0、副本哈希变了、真实文件哈希没变。
- 禁用函数名扫描 0 命中（三个模块分别跑了对应的扫描测试）。
- 词库真实文件哈希本轮全程未变，跟冻结值 `839d48be...` 完全一致。

**我推断（未逐行实测，基于代码走查）：**
- `ReviewShardStore.write()` 内部对"未变化的 shard 保留原文件名不重写"的行为（用于我判断幂等测试里
  `manifest.yaml` 字节不变是"设计如此"而非巧合）——我看了 `review_shards.py` 的 `write()` 源码逻辑，
  但没有对这条路径本身补一个变异测试去验证"如果这个优化被去掉会怎样"，因为这是 round-37 遗留代码，
  不在本轮改动范围内。
- `advance_review_item` 在 sm2_lite 模式下的 ease_factor/interval 计算公式本身的合理性——round-37 已经
  对它做过 17 个单元测试，本轮完全复用、未改动，我信任那批测试的覆盖，没有重新逐条推导公式。
- CLI 进程级别的两次写（`DayPlanStore.write_completion_event` 与 `ReviewShardStore.write`）之间**不是**
  跨进程原子的——如果机器在两次写之间断电，可能出现"completion event 写成功了，队列没写"的中间态。
  这一点我在设计时判断过（见 1.2），但没有写一个专门模拟"两次写之间崩溃"的测试去验证具体后果，
  是基于代码审查的推断，不是实测。

---

## 7. 没有把握的地方（至少 3 条）

1. **`--review-store` 做成可选参数是否真正满足"打通"的精神。**
   任务书原话是"完成事件必须真正推进复习队列"，但我最终的实现是：只有调用方显式传了 `--review-store`
   才会推进；不传就退回 round-37 的"只记录不推进"状态。这是为了不破坏 round-37 已有的、不带复习队列的
   CLI 回归测试。但从"任务书要害"的角度看，如果生产环境里的调用脚本忘记加这个参数，队列依然会是死的——
   我打通了"管道"，但没有强制"通电"。是否应该把这个参数改成必填（同时更新那条既有测试去配一个队列），
   我没有把握哪个更符合主控的预期，选择了侵入性更小的方案。

2. **`vocab_delivered_vs_planned` 这个差额字段是否会被误读为"精确对账"。**
   我在代码注释、docstring、报告里反复强调了它不是同类对比（`vocab_items_introduced` 只算新词，
   `delivered_words` 可能包含旧词复习），但字段本身摆在那里、又是一个具体的整数，使用方如果不看文档，
   很容易把它当成"这个月单词计划完成率"来用。我没有把握这种"报告了但容易被误用"的风险是否应该
   用更笨拙但更难误读的方式表达（比如干脆不产出这个差额字段，只给两个原始数字让调用方自己算）。

3. **`load_month_completions` 按文件名字符串排序是否在所有情况下等价于按日期排序。**
   文件名格式是 `completion--YYYY-MM-DD.yaml`，ISO 日期字符串的字典序恰好等于时间顺序，所以目前是对的；
   但这是一个隐式假设（依赖 `_completion_event_path` 里 `day.isoformat()` 的具体格式），如果未来这个命名
   格式被改掉而没人想起这个排序依赖，会静默排错序（多数调用方目前只是把它们求和，顺序其实不影响结果，
   但我没有把握未来是否会有依赖顺序的调用方）。

4.（额外一条）**`review_store.load()` 在完成事件的 review 列表为空、但 `--review-store` 参数给了的情况下
   完全不会被调用**（`if review_store is not None and event.reviews:` 两个条件都要满足）。这意味着如果
   `--review-store` 指向一个格式已经损坏的队列目录，只要这次提交的完成事件不包含任何复习条目，
   这个损坏会被完全掩盖、不会报错。我认为这是合理的（没有理由因为一次纯词汇记录就去校验一个跟这次操作
   无关的队列完整性），但没有把握这与"尽早暴露问题"的一般工程原则是否冲突。

---

## 8. 一句话总结

残项 A（完成事件→推进复习队列）与残项 B（monthly_close 计划 vs 实际分离）均已打通并接线到 CLI；
9 条标准全部实测通过（9/9）；测试数从 398 增至 **419**（全绿）；提交哈希 `0cd4843`；
报告路径 `review/rounds/round-38-complete-the-loop-claude.md`。
