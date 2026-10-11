# 任务书：第 189 轮补完（窗口 `luna-c` 续做）

你在第 189 轮报告里如实列出了没做完的部分，谢谢。实现本身决策者看过、方向正确，**本轮只补证明与收紧测试**，
除第 4 条外不改 `ky/` 的行为。基线仍是 `81285d2`。

## 要补

1. **R5 固定基线对照**（任务书第 189 轮"测试"一节）：在同一日期 D、同一配置 / 事件 / 输入、该 D **没有**过期 `scheduled`
   （含：纯 `queued`、空队列、`scheduled` 在 D 与 D+1）时，比较 `81285d2` 旧版与当前版：preflight 文本与 JSON、`day-plan record`、
   `day-plan submit --plan`、`ky resume`（`--dry-run` 与正式执行，含 JSON）的 `(退出码, stdout, stderr)` 原始字节，以及写出的冻结 / 恢复事件与队列文件原始字节；
   M12 `count_review_items_by_subject` 与 M15 `status_to_mapping` 的结果。断言取到的确实是旧版（例如旧 `overdue_review_items` 只认 `queued`）。
   唯一允许的差异是 `-h` 帮助（见第 3 条），不要在这些对照里抹掉任何东西。
2. **R7 无写入矩阵**：停用科目、配置外科目各一，过期 `scheduled`、足以触发冻结，分别走
   `record`（有复习完成 / 无复习完成 / 显式 `--review-store` 指向另一存储）、`submit --plan`、`submit --from-staging`、`resume`：
   断言退出码 2、stderr 含修正提示、无 traceback，且冻结事件目录、日计划、完成记录、队列文件**逐字节未变**（写前后哈希对比）。
   `resume` 用既有全队列校验、`--from-staging` 用 M9 校验——用测试证明它们仍在写前拒绝。
3. **收紧 `tests/test_cli.py` 的 `-h` 对照**：现在只断言包含子串，太松。改为：新旧 stdout 在 `--freeze-backlog-days` 这一选项块之外逐字节相同，
   该选项块等于一段写在测试里的期望字节（新帮助文字的完整渲染）；退出码、stderr 逐字节相同。
4. **只在测试证明需要时才改代码**：若第 2 条发现 `submit --plan` 路径的 `ContractError` 没变成退出 2（或留下 traceback / 已写入），按 `record` 的做法修，
   报告写明改了什么。另外 `ky/__main__.py` 里 `--freeze-backlog-days` 的 `help=` 那一行超过 100 字符（`AGENTS.md` 行宽），拆成隐式拼接的两段字符串（输出不变）；
   `_freeze_status_for_workspace` 新加的 `queue=None` 参数补上类型注解。
5. **撤实现变异**（第 189 轮要求的三处）：R1 口径改回只数 `queued`；resume 不把 `scheduled` 改回 `queued`；R7 校验移到写冻结事件之后。
   设 `PYTHONDONTWRITEBYTECODE=1` 并清 `__pycache__`，报告写每处的命令、变红的测试与断言行，恢复后核对哈希。

测试都放进 `tests/contract/test_freeze_scheduled_backlog.py`（第 3 条在 `tests/test_cli.py`）。不写死科目 / 年份 / 数据量。

## 不做的

不改冻结阈值、锁存、事件格式、M9、月结；不动 `tools/`、`data/`；不跑全量。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_freeze_scheduled_backlog tests.contract.test_freeze_port tests.contract.test_resume_port tests.contract.test_review_clip_port tests.contract.test_state_snapshot_port tests.contract.test_projection_status tests.test_cli
```

## 报告

`review/rounds/round-194-d11-scheduled-complete-luna.md`：逐条写补了什么、对照覆盖清单、无写入矩阵结果、变异命令与结果、验收输出原文。
仍有未完成的，照第 189 轮那样如实写明。写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。含中文只用 `apply_patch`，写完查 `???`。
