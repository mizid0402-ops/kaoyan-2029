# 任务书：第 196 轮再返工 —— sol61 第 197 轮 M2（窗口 `luna-c` 续做）

报告 `review/rounds/round-197-d11-scheduled-fix-review-sol61.md`，先读 M2 与"返工束"。其余部分已确认修好，**不要动**。
只改 `tests/contract/test_freeze_scheduled_backlog.py`。

## 要改

- `_new_checkout()` 去掉 `D11_PROBE_NEW_ROOT` 环境变量重定向：常规测试的新版**固定**为本测试模块所在的 `ROOT`。
  （变异验证改为在完整的临时 checkout 里运行测试，让 `ROOT` 自然指向那个副本；需要 Git 对象时给临时副本设 alternates 或 `GIT_DIR`，照 sol 197 的复现方法。）
- 新版子进程里断言实际导入的 `ky` 来自该 `ROOT`（例如检查 `ky.__file__` 所在目录），让来源错配时直接失败而不是静默通过。

## 自证

照 sol 197 的复现：临时完整副本里把 `ky/schedule/state_snapshot.py` 的积压累加改成 `+ 1`，**并**在环境里设 `D11_PROBE_NEW_ROOT` 指向另一份 `81285d2` 旧树，
运行 `tests.contract.test_freeze_scheduled_backlog.FreezeScheduledBacklogTests.test_m12_m15_mappings_match_fixed_baseline_for_four_queue_shapes`——必须失败（不得 OK）。
恢复源码后在主仓库只跑两条 R5 对照测试通过。报告写实际命令与结果。

## 不做的

不改 `ky/`、`contracts/`、其它测试；不跑全量。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_freeze_scheduled_backlog
```

## 报告

`review/rounds/round-198-d11-probe-root-fix-luna.md`。写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。
