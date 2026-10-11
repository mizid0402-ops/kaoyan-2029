# 第 194 轮：D11 过期 scheduled 补充证明

## 本轮改动

1. 在 `tests/contract/test_freeze_scheduled_backlog.py` 加入固定基线 subprocess 对照。测试从
   `git archive 81285d26cec32762755cabf2f667203366ae83d2` 建隔离源码树，并验证旧版 M27 源码只选
   `queued`，确保执行的确是派发基线。
2. `preflight` 对照覆盖纯 queued、空队列、所有 scheduled 到期日为 D、所有 scheduled 到期日为
   D+1；逐一比较文本和 JSON 的退出码、stdout、stderr 原始字节。
3. 固定基线还比较了无注册工作区时 `day-plan record` 与 `day-plan submit --plan` 的退出码、
   stdout、stderr，以及 plans 目录全部文件字节；`ky resume` 空队列在 dry-run / 正式执行、文本 /
   JSON 四种组合下比较相同输出和 plans 目录文件。
4. R7 矩阵已覆盖从测试配置动态选取的 inactive 科目及动态生成的未配置科目。每个科目分别执行 record
  （无完成、有完成、有完成且显式 `--review-store` 指向另一队列）、submit --plan、submit
   --from-staging、resume。每条断言退出码 2、包含具体 inactive / not-declared 提示、没有
   traceback，并逐文件 SHA-256 比较操作前后的测试工作区快照。resume 全队列校验与 staging 的 M9
   拒绝路径都通过这些 CLI 用例实测。
5. `tests/test_cli.py` 现在把新旧帮助输出中 `--freeze-backlog-days` 选项块以外的 stdout 原始字节
   比较；完整新选项块与静态期望字节完全一致，退出码与 stderr 原始字节一致。
6. `ky/__main__.py` 的帮助字符串仅做隐式拼接，显示字节不变；`_freeze_status_for_workspace` 的
   队列参数现在标注为 `tuple[ReviewItem, ...] | None`。R7 测试未发现 submit --plan 的退出码、
   traceback 或写入缺陷，因此未改 CLI 行为。

## 当前仍未完成的对照

- 固定基线对照尚未覆盖 `ky resume` 对非空 queued backlog 的队列重排后原始字节，也未覆盖该场景
  写出的恢复事件字节。
- record / submit 的基线 CLI 对照使用无注册工作区输入，写出的完成 / 日计划文件字节已比对，
  但尚未比对冻结事件文件，也未在注册队列触发冻结的情况下比较 submit 输出。
- M12 `count_review_items_by_subject` 与 M15 `status_to_mapping` 尚未执行旧版 / 新版固定基线结果
  对照。本轮现有口径单测覆盖 M12/M27 一致性，但不替代这项基线证据。
- 以上未完成项不影响下面列出的已执行测试通过结论，但不能据此宣称完整满足任务书 R5。

## 撤实现变异

每处变异前执行以下命令清除仓库下生成的 `__pycache__`；每条 unittest 均由包装进程显式给测试
子进程设置 `PYTHONDONTWRITEBYTECODE=1`：

```text
py -3.12 -c "import pathlib,shutil; [shutil.rmtree(p) for p in pathlib.Path('.').rglob('__pycache__') if p.is_dir()]"
```

- R1：临时把 `overdue_review_items` 条件改回仅 `item.state == "queued"`；运行命令：

  ```text
  py -3.12 -c "import os,subprocess,sys; e=os.environ.copy(); e['PYTHONDONTWRITEBYTECODE']='1'; c=[sys.executable,'-m','unittest','tests.contract.test_freeze_scheduled_backlog.FreezeScheduledBacklogTests.test_strict_date_boundary_and_shared_backlog_accounting']; r=subprocess.run(c,env=e); sys.exit(r.returncode)"
  ```

  变红：该测试第 52 行，期望状态集合包含 `scheduled`，实际缺少它。
- R3：临时移除 resume 更新中的 `state="queued"`；运行命令：

  ```text
  py -3.12 -c "import os,subprocess,sys; e=os.environ.copy(); e['PYTHONDONTWRITEBYTECODE']='1'; c=[sys.executable,'-m','unittest','tests.contract.test_freeze_scheduled_backlog.FreezeScheduledBacklogTests.test_resume_converts_scheduled_without_revision_change']; r=subprocess.run(c,env=e); sys.exit(r.returncode)"
  ```

  变红：该测试第 75 行，期望 `queued`，实际仍为 `scheduled`。
- R7：临时将 `validate_items_against_config` 移到 `write_freeze_record` 之后；运行命令：

  ```text
  py -3.12 -c "import os,subprocess,sys; e=os.environ.copy(); e['PYTHONDONTWRITEBYTECODE']='1'; c=[sys.executable,'-m','unittest','tests.contract.test_freeze_scheduled_backlog.FreezeScheduledBacklogTests.test_record_rejects_invalid_scheduled_subject_before_any_write']; r=subprocess.run(c,env=e); sys.exit(r.returncode)"
  ```

  首个矩阵格在第 195 行文件快照哈希断言变红，观察到新增 freeze 事件。变异令后续子用例受到该
  非法写入影响而连带失败；修复测试隔离后，正常实现下矩阵通过。

变异均已撤销。恢复后 SHA-256：

```text
ky/freeze/port.py     573F1559E0DBE0B4DE98621CBE68C9067AE4A6B3C10766F47E24C15527901104
ky/freeze/resume.py   263424E6C1F9092602F00E8DF6B9BE563AF75A2E566E88345B205ECAD6222D0A
ky/__main__.py        B22342D08022C1E9F0A29FEE80163891E1B4A2E3849ED5C1C7AC4E39BA6F2065
```

## 指定验收

命令：

```text
py -3.12 -m unittest tests.contract.test_freeze_scheduled_backlog tests.contract.test_freeze_port tests.contract.test_resume_port tests.contract.test_review_clip_port tests.contract.test_state_snapshot_port tests.contract.test_projection_status tests.test_cli
```

原始输出：

```text
..............C:\Users\Lenovo\AppData\Local\Programs\Python\Python312\Lib\tarfile.py:2221: DeprecationWarning: Python 3.14 will, by default, filter extracted tar archives and reject files or modify their metadata. Use the filter argument to control this behavior.
  warnings.warn(
..........................................................................................
----------------------------------------------------------------------
Ran 115 tests in 71.590s

OK
```

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。未提交。指定文件未发现连续替换问号。
