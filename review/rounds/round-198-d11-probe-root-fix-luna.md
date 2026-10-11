# 第 198 轮 D11 R5 新版来源固定报告

## 改动

仅修改 `tests/contract/test_freeze_scheduled_backlog.py`。`_new_checkout()` 现在恒返回模块 `ROOT`，不再读取 `D11_PROBE_NEW_ROOT`。新版基线子进程在执行 CLI 或 M12/M15 探针前，会校验 `Path(ky.__file__).resolve().parent.parent` 与传入 checkout 相等；来源错配会在子进程内直接断言失败。

固定基线调用统一通过带来源断言的启动辅助执行。CLI 使用 `runpy` 启动 `ky.__main__` 并保留参数；`-c` 探针在原脚本前插入同一校验。输出流保持原样，因此旧新 stdout/stderr 的原始字节对照仍有效。常规新版始终由 `ROOT` 指定；旧版仍由固定提交归档取得。

## 自证

按 sol61 第 197 轮方法建立了当前工作树的完整临时副本；在副本 `ky/schedule/state_snapshot.py` 中仅把
`totals[item.subject_id][3] += item.estimated_minutes` 改成 `... += item.estimated_minutes + 1`。
给临时副本的 `.git/objects/info/alternates` 指向主仓库对象库，并以该副本为 `GIT_DIR`，使测试仍能从固定提交执行 `git archive 81285d2`。另将 `D11_PROBE_NEW_ROOT` 指向单独解出的 `81285d2` 旧树，设置 `PYTHONDONTWRITEBYTECODE=1`。

临时副本内执行的测试命令：

```text
py -3.12 -B -m unittest tests.contract.test_freeze_scheduled_backlog.FreezeScheduledBacklogTests.test_m12_m15_mappings_match_fixed_baseline_for_four_queue_shapes
```

结果不是 OK：退出码 1，`queued` 子用例在 M12/M15 输出断言失败，旧值 backlog 为 10 分钟、变异值为 11 分钟；测试进程路径显示加载的是临时 checkout。该测试没有受 `D11_PROBE_NEW_ROOT` 重定向到旧树。副本由临时目录上下文清理，主仓库源码未参与变异。

恢复到主仓库后，只重跑两条 R5 对照测试：

```text
py -3.12 -m unittest tests.contract.test_freeze_scheduled_backlog.FreezeScheduledBacklogTests.test_registered_freeze_and_nonempty_resume_match_fixed_baseline tests.contract.test_freeze_scheduled_backlog.FreezeScheduledBacklogTests.test_m12_m15_mappings_match_fixed_baseline_for_four_queue_shapes
```

输出：

```text
..
----------------------------------------------------------------------
Ran 2 tests in 12.073s

OK
```

任务验收命令：

```text
py -3.12 -m unittest tests.contract.test_freeze_scheduled_backlog
```

输出：

```text
.C:\Users\Lenovo\AppData\Local\Programs\Python\Python312\Lib\tarfile.py:2221: DeprecationWarning: Python 3.14 will, by default, filter extracted tar archives and reject files or modify their metadata. Use the filter argument to control this behavior.
  warnings.warn(
........
.
----------------------------------------------------------------------
Ran 10 tests in 31.254s

OK
```

`git diff --check` 通过；指定测试文件没有超 100 字符的代码行。未改 `ky/`、`contracts/` 或其它测试，未提交。全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。
