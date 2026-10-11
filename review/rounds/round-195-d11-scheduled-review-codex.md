# 第 195 轮：D11 过期 scheduled 积压评审

结论：**FAIL**。R1–R3、R5–R9 的受检行为符合定稿；R4 的新增 preflight 文字有一处可见的方位错误，且没有放在定稿指定的冻结段。全量：未跑（按 AGENTS.md）。

评审只读工作区改动；运行和变异均在系统临时目录 `ky195-0f2ef9ce52ce45adbc97df79ec4254a1`。旧版由 `git archive 81285d2` 展开，新版由该归档复制本轮改动构成。设置了 `GIT_DIR` 指向仓库对象库和 `PYTHONDONTWRITEBYTECODE=1`。

## 必须改

### M1：R4 的新增说明把上方的 deferred 行称为“下方”

复现输入：用 `tests/fixtures/config/config-minimal.yaml` 和 `tests/fixtures/reviews/reviews-normal.yaml` 第一项，改为 `state=scheduled`、`due_date=2026-09-14`，在 `2026-09-15` 执行 `ky preflight --config config.yaml --items <该队列> --date 2026-09-15`。在隔离副本中实际返回 0，stdout 的顺序是：

```text
deferred           : 0  -> backlog 0 min
UNREACHABLE        : 1 ...
  - rv_math1_limit_0001 ... state=scheduled due 2026-09-14 overdue 1d
其中 1 项（8 分钟）为已过期的 scheduled ...；下方 deferred -> backlog 只计本次裁剪延期。
```

`deferred -> backlog` 实际在说明行**上方**，而且说明被打印在 `UNREACHABLE` 列表后，不在 R4 指定的冻结段。日常查看 preflight 的人会被错误指向不存在的下方字段；这属于用户可见输出与定稿细则不符。将说明放到冻结摘要处并使指向与实际布局一致，或至少修正方位并经决策者确认位置。此项不影响积压数值，但按 `AGENTS.md` 的“输出与规格不符”口径列必须改。

## 建议改

### S1：把三条已补做的 R5 对照固化到固定基线测试

当前 `tests/contract/test_freeze_scheduled_backlog.py::test_record_submit_and_resume_match_fixed_baseline_bytes` 的 record、submit 都在无注册工作区运行；resume 用空队列。它没有锁住正常注册队列触发冻结时的事件、submit 输出，也没有锁住非空 queued 积压的恢复文件。M12 / M15 亦无旧版运行结果断言。我用下面的同输入探针实际补齐了这些证据，**未发现回归**，因此缺测试本身列建议改，不另列必须改：

| 输入与对照 | 旧版 / 新版实测 |
| --- | --- |
| 取 `FreezePortContractTests._overdue_items(minutes=8)` 的 27 个 queued 项，注册队列后在 `2026-09-15` 执行 `ky resume`；同一运行根复位后换源码 | `(退出码, stdout, stderr)` 完全相同，均为 0、五行恢复摘要、空 stderr；队列 manifest、12 个改写的分片及 `data/plans/freeze/000001-resume--2026-09-15.yaml` 的 SHA-256 逐文件相同。恢复事件 SHA-256 均为 `4610293e85d36e80b2da16f3c21d122ef18837596bcb608b30f5dca52311bebc`。 |
| 同一注册队列，提交 `tests.contract.test_freeze_scheduled_backlog._empty_plan_mapping(config, DAY)` 至 `day-plan submit --plan plan.yaml --config config.yaml --workspace kaoyan.workspace.yaml --store data/plans` | 两版均退出 2，stdout 空，stderr 为 `contract violation: 已冻结，请先运行 ky resume` 加 CRLF；仅新增冻结事件，事件 SHA-256 均为 `0c82febf03f747406fd466a230ee864d5313a6a06c78c579b34e0ac60a3ac76e`。 |
| 同一 `reviews-normal.yaml`、`2026-09-15`，分别调用 M12 `count_review_items_by_subject`，再将计数与 M27 状态交给 M15 `status_to_mapping` | 两版 `(退出码, stdout, stderr)` 完全相同；两行 JSON 的合并 stdout SHA-256 均为 `10e1319cb533612f28aa3466e219cdf48742ecacaa780eaa7c66059cab31ec7c`，各科 backlog 为 10 / 4 / 8 分钟。 |

复现方式：在 `git archive 81285d2` 的旧树与复制本轮改动的新树内，分别以同一模板队列启动上述命令；每次执行前恢复同一运行根，逐字节比较三元组及写后文件 SHA-256。探针脚本位于系统临时目录 `probe195.py`，未写入仓库。建议把这三个输入移入固定哈希对照测试，避免将来修改重新打开 R5 缺口。另：新测试模块直接导入 `FreezePortContractTests`，`unittest` 发现时会顺带运行该类测试；建议只复用数据/辅助而不导入 `TestCase` 类。

## 不改：已核实的路径

- **R1、R2、R8**：M27 公开 `overdue_review_items` 仅选 `queued` / `scheduled` 且 `due_date < D`；D 当日和 D+1 的 scheduled、retired、suspended 均不计。阈值仍是 `backlog_days × review_hard_cap_minutes`，有项目时等号冻结，空积压不冻结，低于阈值仍可手动 resume。`freeze_to_mapping`、事件与锁存字段未改。
- **R3、R6、R9**：同一过期 scheduled 项的 CLI dry-run 返回 0，队列仍为 scheduled、无事件，文字为“其中 1 项将由 scheduled 转为 queued”；正式运行返回 0，队列变 queued、revision 保持 1、间隔仍为 3 天，写一条 resume 事件，文字为“其中 1 项已由 scheduled 转为 queued”。代码沿用既有遗忘分界和摊开排序，并断言间隔不增；条件 JSON 字段只在转换数大于零时加入。无过期 scheduled 的固定基线 resume 对照及上述非空 queued 探针均逐字节相同。
- **R4 的数据口径**：M12 调用 M27 公开判定计 `backlog_minutes`，`due_today` 仍只数 queued；M15 继续复用 M12/M27，投影 schema 未改。M9 的选择、延期分钟与月结代码未改。preflight JSON 未增加字段；无过期 scheduled 的文本/JSON 固定基线用例通过。`-h` 仅允许的选项块经测试逐字节核对。
- **R7**：`_latch_freeze_if_needed` 先加载一次注册队列，把同一对象送入冻结判定和公开科目校验，校验在冻结事件写入之前。新增矩阵对停用及配置外科目覆盖 record（无/有完成及独立 `--review-store`）、直接 submit、staging submit、resume；均退出 2，无 traceback，操作前后工作区文件 SHA-256 相同。record 已捕获 `ContractError`。本次隔离运行 `py -3.12 -m unittest tests.contract.test_freeze_scheduled_backlog -q`：20 tests，OK；相关 M12/M15/resume 三模块：20 tests，OK。
- **撤实现验证**：仅在临时新版把 `overdue_review_items` 改回 queued-only，运行 `py -3.12 -m unittest tests.contract.test_freeze_scheduled_backlog.FreezeScheduledBacklogTests.test_strict_date_boundary_and_shared_backlog_accounting -q`，退出 1，第 52 行失败：`scheduled` 缺于实际状态集合。恢复后 `ky/freeze/port.py` SHA-256 为 `573F1559E0DBE0B4DE98621CBE68C9067AE4A6B3C10766F47E24C15527901104`。

## 安全登记

本轮未发现新增的恶意输入、手工篡改或精确竞态风险。R7 的同对象校验避免了本工作包内“判定后重读队列”的裂缝；外部进程在校验与写事件之间改写注册文件仍属需精确竞态的威胁，不作为本轮必须改。
