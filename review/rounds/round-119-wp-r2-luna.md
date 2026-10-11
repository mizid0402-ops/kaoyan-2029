# Round 119 — WP-R2 `ky resume`

## 改动文件

- `ky/schedule/completion.py`、`contracts/review_progress.md`：新增 `reset_for_relearning()`，只将
  间隔设为 1 天、重复次数清零；保留 mode、phase、ease、lapses。
- `ky/freeze/port.py`、`ky/freeze/__init__.py`：公开 `overdue_review_items()`，冻结判定与 resume
  共用 `state == "queued" and due_date < day` 口径。
- `ky/freeze/resume.py`：M27 纯函数重排、遗忘分层、366 天最早容量分配、放不下清单与唯一映射。
  阶段按科目配额；非阶段按 `scale_minutes(当天时长, review_reserve_ratio)` 共享容量；已排入当天的
  非逾期队列项先占容量。被重排项的 `defer_count` 清零，其他字段保留；间隔不增加有断言。
- `ky/__main__.py`：新增 `ky resume --date ... [--dry-run] [--json] [--config] [--workspace]`；配置缺省
  读取注册表，队列 manifest 缺失时为空队列；availability 和 route 使用已有 workspace 读取接口。
- `contracts/freeze.md`、`docs/模块地图.md`：记录 M27 resume 规则并更新 M10/M13/M14/M27 边界。
- `tests/contract/test_resume_port.py`：覆盖重学重置、分层边界、容量/顺序/确定性、未逾期不变、冻结解除、
  放不下标记及 CLI dry-run/正式执行/同日重复。

## 审计与队列提交顺序

正式执行先通过 `ReviewShardStore.write()` 写完整新队列，再用 `DayPlanStore.write_resume_record()` 写
`freeze/resume--<D>.yaml`。提交前会检查同日是否已有 resume 记录；`ReviewShardStore.write()` 原有的
schema-1 未证明历史保护仍然生效。无逾期项时不写任何文件。dry-run 只输出计划。

两个 store 间没有事务。若队列写入成功、审计记录写入失败，队列已重排，但旧冻结锁存可能仍有效；命令返回
契约错误。重试时由于队列无逾期项，按本包“无积压不写文件”的规则不会自动补记，需人工检查后通过审计记录
存储接口处理锁存。这是已知的残余恢复窗口。选择队列先写，是为了避免审计成功而队列提交失败时提前解除锁存。

## 验收

首次运行任务书指定模块并追加新模块：

```text
py -3.12 -m unittest tests.contract.test_freeze_port tests.test_completion tests.test_day_plan_store tests.test_cli tests.contract.test_resume_port
Ran 97 tests in 25.148s
OK
```

CLI 增加同日已存在审计记录的写前保护后，重跑受影响模块：

```text
py -3.12 -m unittest tests.test_cli tests.contract.test_resume_port
Ran 45 tests in 16.797s
OK
```

新契约测试对每条行为使用直接结果断言：移除 schedule 重置会破坏 interval/repetitions 断言；移除共享逾期筛选或
分层比较会破坏边界/层级断言；移除容量占用、逐科预算、排序或固定遍历会破坏排期/确定性断言；移除未逾期保留、
间隔断言或重排会破坏状态/冻结断言；撤掉 CLI 写入、dry-run 分支或无积压短路会破坏文件与审计断言。没有做
全量测试（按 AGENTS.md，由决策者提交前统一跑）。

## 建议

- M9 的既有 `unschedulable` 按 hard cap 分类，R2 的“放不下”按未来常规软容量/路线配额分类。超出常规配额但仍低于
  M9 hard cap 的项目，不保证随后一定进入 M9 的 `unschedulable` 桶。任务要求不改 M9，本包保留 R2 计划中的
  `unschedulable_review_ids` 提示；建议决策者确认是否要在后续契约中统一“放不下/需拆分”的术语。
- 如需消除跨 store 失败窗口，需要后续设计带事务/恢复语义的 M13 操作；本包未扩展存储协议。
