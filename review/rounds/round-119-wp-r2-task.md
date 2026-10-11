# 任务书：WP-R2 `ky resume`——按遗忘程度分层重排积压（M27 / M10 / M13 / M14，决议 D11）

先读仓库根 `AGENTS.md`，再读：`docs/阶段2.5-接缝收口.md` 的 **D11**（本包依据）与 D10 补充、`contracts/freeze.md`、`contracts/review_progress.md`、`contracts/route_plan.md`（生效规则）、`contracts/availability.md`、
`ky/freeze/port.py`、`ky/schedule/completion.py`（`_advance_checked_schedule` 的失败分支、`ReviewSchedule`）、`ky/schedule/budget.py`（`resolve_day_budget`）、`ky/schedule/review_clip.py`（`_sort_key` 仅作参考）、
`ky/storage/review_shards.py`（`ReviewShardStore.write`、旧版队列保护）、`ky/storage/day_plan_store.py`（完成事件的一次写入写法）、`ky/__main__.py`（`review-queue` 子命令的写法）。

你在 worktree `F:\workspace\kaoyan-wt-r2`（分支 `stage25/r2`）里工作，只改这个目录。

## 为什么做

D11：积压过多时系统冻结（R1 已做）。用户准备好后手动 `ky resume`，系统"根据已学的内容重新安排"：逾期太久的可能已遗忘，退回起点先复习；逾期不久的保留进度；全部按之后每天的常规复习配额摊开，**不会一天压满**。重排后积压清零，R1 的冻结自然解除（冻结是由队列推导的）。

## 决策者已定的设计（照做；有更好的写法先在报告里提，不要自行改设计）

### 1. 退回起点（M10，`ky/schedule/completion.py` 公开函数）

`reset_for_relearning(schedule: ReviewSchedule) -> ReviewSchedule`：返回 `interval_days=1`、`repetitions=0`，**`mode`、`phase`、`ease_factor`、`lapses` 不变**（与核对失败分支相比：不计 lapse、不降 ease，因为这不是核对结果，D3 / D11）。在 `contracts/review_progress.md` 补一节。

### 2. 重排计划（M27，新文件 `ky/freeze/resume.py`，纯函数）

`plan_resume(day, config, items, *, availability, route) -> ResumePlan`：
- 逾期项 = `state == "queued"` 且 `due_date < day`（与 `assess_freeze` 同口径，复用同一判定，不要各写一份）。其余项原样不动。
- 分层：`(day - due_date).days > schedule.interval_days` → **可能遗忘**（schedule 用 `reset_for_relearning`）；否则 **逾期不久**（schedule 不变）。
- 摊开：从 `day` 起逐日求当天常规复习容量——`resolve_day_budget` 命中阶段时按**各科**配额（每科独立容量），否则当天软配额（`scale_minutes(当日总时长, review_reserve_ratio)`，全科共享）；再减去当天已有的、非逾期、`queued` 且 `due_date == 当天` 的项占用的分钟（它们本来就排在那天）。
  顺序：先可能遗忘、后逾期不久；各层内按原 `due_date` 升序、再按 `review_id`。每项放到**最早**的、该科（或共享）剩余容量 ≥ 成本的一天。
  成本超过任何一天可能容量的项（或 366 天内都放不下的）：放在 `day` 当天并在计划里标出（它们在裁剪时会进 `unschedulable` 提示拆分），不无限搜索。
- 被重排的项：`due_date` = 分配日，`defer_count = 0`（重新开始），`last_reviewed_on`、`state` 等其余字段不变。**任何项的 `interval_days` 都不得变大**（写成断言）。
- `ResumePlan` 包含：每项 `review_id`、层级、旧 / 新到期日、是否退回起点；汇总（两层数量、最后一个分配日、放不下的项）。有一个 `resume_plan_to_mapping()` 作为 JSON 形状唯一来源。

### 3. 执行与审计（M13 + M14）

- `ky resume --date D [--dry-run] [--json] [--config C] [--workspace W]`：队列取注册表 `state.review_queue`（没有 manifest = 空队列，与 R1 一致），配置缺省取注册表 `settings.exam_config`，availability / route 照 preflight 的取法。
- `--dry-run`：只打印计划，什么都不写。
- 正式执行：先把完整新队列构造好并通过 `ReviewShardStore.write` 的全部校验；再用 R1 修复包（第 120 轮）已提供的 `DayPlanStore.write_resume_record(day, mapping)` 写**一次性**审计记录 `freeze/resume--<D>.yaml`——它同时**解除冻结锁存**（D11 修订版）。mapping 用 `resume_plan_to_mapping()` 的结果。
  两步的失败顺序与原子性按现有存储能力做到最好，在报告里写清楚"审计记录写失败时队列已写"这类窗口怎么处理（建议：先写审计记录、后写队列；队列写失败则审计记录标明未生效，或者你有更好的做法先在报告里提）。
- 没有逾期项：打印"没有需要重排的积压"，退出 0，不写任何文件。
- 旧版队列（含未证明历史）照现有规则拒绝写入。

### 4. 规格与地图

`contracts/freeze.md` 增 `ky resume` 一节（分层规则、容量来源、顺序、放不下的项、审计记录、`--dry-run`）；`contracts/review_progress.md` 增 `reset_for_relearning`；`docs/模块地图.md` M27 / M10 / M13 行更新。

## 不做的

- 不改冻结判定（R1）、裁剪算法、紧急规则；不改 `advance_review_item` 等既有推进语义。
- 不自动触发 resume；不写冻结标记。

## 测试（只写这些，放 `tests/contract/test_freeze_port.py` 或新 `tests/contract/test_resume_port.py`）

每条都要在撤回对应实现时变红（报告里写怎么验证的）：
1. `reset_for_relearning`：只改 `interval_days` 与 `repetitions`。
2. 分层边界：逾期天数等于 / 大于 `interval_days`。
3. 摊开：没有哪一天（或哪一科）超出常规容量；可能遗忘先于逾期不久；已排在当天的非逾期项占用被扣除；阶段配额下按科独立；确定性（两次相同）。
4. 不变式：没有任何项的 `interval_days` 变大；未逾期项原样；重排后 `assess_freeze` 在 D 当天为不冻结。
5. CLI：`--dry-run` 不写文件；正式执行写队列与审计记录；同日第二次 resume 为无积压、不写；放不下的项被标出。
不写数据量字面量。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_freeze_port tests.test_completion tests.test_day_plan_store tests.test_cli
```

另加你的新测试模块（若新建）。worktree 没有 `data/raw_materials/`；缺资源的用例现在会跳过（G1）。

## 报告

`review/rounds/round-119-wp-r2-luna.md`（写在 worktree 里）：改了哪些文件、每条设计的落点、审计与队列写入的顺序和失败窗口、验收输出、建议。
写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。含中文的文件只用 `apply_patch` 编辑，写完查 `???`。
