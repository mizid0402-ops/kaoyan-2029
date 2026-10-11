# 第 196 轮 D11 scheduled 积压返工报告

基线固定为 `81285d2`（完整提交 `81285d26cec32762755cabf2f667203366ae83d2`）。未提交。

## 本轮修正

1. **M1 preflight 说明位置**：说明行从 `UNREACHABLE` 列表移入 `_preflight_print_summary` 的冻结状态输出段，紧随冻结状态行。去掉方位词，完整文本为：
   `其中 N 项（M 分钟）为已过期的 scheduled（M9 列为 unreachable），已计入冻结积压；deferred -> backlog 一行只计本次裁剪延期。`
   仅当冻结判定计入过期 `scheduled` 时输出。测试检查完整 UTF-8 行字节及紧随 `FROZEN` 行的位置；无过期 `scheduled` 的固定基线对照继续覆盖文本与 JSON。
2. **旧 `ResumePlan` 对照**：`git grep -n -E 'asdict\(.*plan|ResumePlan' -- tests` 只找到 `tests/contract/test_storage_ledger_split_baseline.py` 这一处整对象比较。先断言新计划 `scheduled_to_queued_count == 0`，只移除此新增键，再比较其余完整 dataclass 映射。输入与其它断言未改；这是纯 `queued` 输入下新字段的预期零值，保留全部旧字段的基线约束。
3. **规格**：`contracts/projection_status.md` 明确 M12 `count_review_items_by_subject` 复用 M27 `overdue_review_items`；M15 消费 M12 的结果。`contracts/freeze.md` 补足 R8：本规则只影响阈值；阈值以下的过期 `scheduled` 仍由 M9 列为 `unreachable`，可手动 `ky resume` 重排，且无锁存时 resume 也处理它们。
4. **固定基线探针**：新增探针取自 `git archive 81285d26cec32762755cabf2f667203366ae83d2`，并断言归档中的 M27 仍仅按 `queued` 判定，确保拿到的是旧实现。两边使用同一工作目录、相同相对路径和输入字节；每次调用前恢复输入快照；比较 `(退出码, stdout, stderr)` 原始字节与写后工作区完整相对路径/文件字节映射。
   - (a) 注册队列含非空纯 `queued` 积压：`ky resume` 文本/JSON × 预览/实写，逐项比较三元组与写后整棵工作区文件。
   - (b) 注册队列达到冻结阈值：`day-plan record` 文本/JSON 与 `day-plan submit --plan`，比较三元组与包含冻结事件的写后整棵工作区文件。
   - (c) M12 与 M15 四种队列形状：全 `queued`、空队列、`scheduled` 到期日为 D、`scheduled` 到期日为 D+1；比较 M12 `count_review_items_by_subject` 和 M15 `status_to_mapping(status_as_of(...))` 的序列化原始输出。
   - 积压项数按 `ceil(backlog_days × review_hard_cap_minutes / 每项分钟)` 从配置计算；科目与日期取测试配置/输入推导。
5. **测试辅助**：新测试模块不再导入 `FreezePortContractTests`。所需 CLI fixture 与积压项构造在新模块内以小型辅助函数提供，避免 unittest 重复收集测试类，也不跨模块调用私有辅助。

## 变异验证

每处变异前清理 `__pycache__`，并设置 `PYTHONDONTWRITEBYTECODE=1`；R5 变异仅修改临时副本中的 `ky/`，由 `D11_PROBE_NEW_ROOT` 指向副本，结束后删除副本。

1. **M1 位置断言**：临时把说明行移回 `UNREACHABLE` 输出之后，执行：
   `py -3.12 -c "import os,subprocess,sys; e=os.environ.copy(); e['PYTHONDONTWRITEBYTECODE']='1'; r=subprocess.run([sys.executable,'-B','-m','unittest','tests.contract.test_freeze_scheduled_backlog.FreezeScheduledBacklogTests.test_preflight_backlog_explanation_follows_freeze_status'],env=e); sys.exit(r.returncode)"`
   结果：失败；位置断言在 `tests/contract/test_freeze_scheduled_backlog.py` 的说明行切片比较处变红，冻结状态之后实际出现日期行。恢复说明行位置后验收通过。
2. **R5(a) resume 字节变异**：实际命令用 `py -3.12 -c "..."` 创建 `tempfile.mkdtemp()` 临时副本、复制 `ky/`、将该副本 `ky/freeze/resume.py` 中 `if plan.scheduled_to_queued_count:` 替换为 `if True:`，设置 `D11_PROBE_NEW_ROOT` 与 `PYTHONDONTWRITEBYTECODE=1`，再以 `subprocess.run([sys.executable, '-B', '-m', 'unittest', 'tests.contract.test_freeze_scheduled_backlog.FreezeScheduledBacklogTests.test_registered_freeze_and_nonempty_resume_match_fixed_baseline'], env=e)` 执行并清理临时目录。结果：失败于该测试第 302 行，正式执行后的工作区字节比较发现恢复事件多出 `scheduled_to_queued_count: 0`。
3. **R5(b) 冻结事件字节变异**：同样用 `py -3.12 -c "..."` 建立并清理临时 `ky/` 副本，在副本 `ky/__main__.py` 的 `record_status` 加入 `probe_mutation: True`，设置 `D11_PROBE_NEW_ROOT`、`PYTHONDONTWRITEBYTECODE=1`，运行与 (a) 相同的 unittest 测试。结果：失败于第 314 行，`record` 的写后工作区字节比较发现冻结事件多出该键。
4. **R5(c) M12/M15 结果变异**：同样用 `py -3.12 -c "..."` 建立并清理临时 `ky/` 副本，把副本 `ky/schedule/state_snapshot.py` 的 `totals[item.subject_id][3] += item.estimated_minutes` 改为 `... + 1`，设置 `D11_PROBE_NEW_ROOT`、`PYTHONDONTWRITEBYTECODE=1`，运行 `py -3.12 -B -m unittest tests.contract.test_freeze_scheduled_backlog.FreezeScheduledBacklogTests.test_m12_m15_mappings_match_fixed_baseline_for_four_queue_shapes`。结果：失败于第 375 行，`queued` 子用例的旧新 M12/M15 输出比较变红（积压分钟由 10 变为 11）。

R5 三条临时副本变异使用的实际 `py -3.12 -c` 命令如下（每条命令最后删除临时目录）：

```text
py -3.12 -c "import os,pathlib,shutil,subprocess,sys,tempfile; base=pathlib.Path(tempfile.mkdtemp()); checkout=base/'copy'; shutil.copytree(pathlib.Path('ky'),checkout/'ky'); f=checkout/'ky/freeze/resume.py'; s=f.read_text(encoding='utf-8'); assert 'if plan.scheduled_to_queued_count:' in s; f.write_text(s.replace('if plan.scheduled_to_queued_count:', 'if True:', 1),encoding='utf-8'); e=os.environ.copy(); e['D11_PROBE_NEW_ROOT']=str(checkout); e['PYTHONDONTWRITEBYTECODE']='1'; r=subprocess.run([sys.executable,'-B','-m','unittest','tests.contract.test_freeze_scheduled_backlog.FreezeScheduledBacklogTests.test_registered_freeze_and_nonempty_resume_match_fixed_baseline'],env=e); shutil.rmtree(base); sys.exit(r.returncode)"
py -3.12 -c "import os,pathlib,shutil,subprocess,sys,tempfile; base=pathlib.Path(tempfile.mkdtemp()); checkout=base/'copy'; shutil.copytree(pathlib.Path('ky'),checkout/'ky'); f=checkout/'ky/__main__.py'; s=f.read_text(encoding='utf-8'); q=chr(34); old='record_status = {**freeze_to_mapping(status), '+q+'latched'+q+': True}'; new='record_status = {**freeze_to_mapping(status), '+q+'latched'+q+': True, '+q+'probe_mutation'+q+': True}'; assert old in s; f.write_text(s.replace(old,new,1),encoding='utf-8'); e=os.environ.copy(); e['D11_PROBE_NEW_ROOT']=str(checkout); e['PYTHONDONTWRITEBYTECODE']='1'; r=subprocess.run([sys.executable,'-B','-m','unittest','tests.contract.test_freeze_scheduled_backlog.FreezeScheduledBacklogTests.test_registered_freeze_and_nonempty_resume_match_fixed_baseline'],env=e); shutil.rmtree(base); sys.exit(r.returncode)"
py -3.12 -c "import os,pathlib,shutil,subprocess,sys,tempfile; base=pathlib.Path(tempfile.mkdtemp()); checkout=base/'copy'; shutil.copytree(pathlib.Path('ky'),checkout/'ky'); f=checkout/'ky/schedule/state_snapshot.py'; s=f.read_text(encoding='utf-8'); old='totals[item.subject_id][3] += item.estimated_minutes'; new='totals[item.subject_id][3] += item.estimated_minutes + 1'; assert old in s; f.write_text(s.replace(old,new,1),encoding='utf-8'); e=os.environ.copy(); e['D11_PROBE_NEW_ROOT']=str(checkout); e['PYTHONDONTWRITEBYTECODE']='1'; r=subprocess.run([sys.executable,'-B','-m','unittest','tests.contract.test_freeze_scheduled_backlog.FreezeScheduledBacklogTests.test_m12_m15_mappings_match_fixed_baseline_for_four_queue_shapes'],env=e); shutil.rmtree(base); sys.exit(r.returncode)"
```

以上三条 R5 变异均在临时副本中完成并清理；M1 源码变异已恢复。工作树中的实现未保留探针变异。

## 验收

实际命令：

```text
py -3.12 -m unittest tests.contract.test_freeze_scheduled_backlog tests.contract.test_freeze_port tests.contract.test_resume_port tests.contract.test_review_clip_port tests.contract.test_state_snapshot_port tests.contract.test_projection_status tests.contract.test_storage_ledger_split_baseline tests.test_cli
```

验收输出原文：

```text
.C:\Users\Lenovo\AppData\Local\Programs\Python\Python312\Lib\tarfile.py:2221: DeprecationWarning: Python 3.14 will, by default, filter extracted tar archives and reject files or modify their metadata. Use the filter argument to control this behavior.
  warnings.warn(
........
.....................................................................................
.................
----------------------------------------------------------------------
Ran 111 tests in 70.498s

OK
```

`git diff --check` 通过；`git grep` 的 `ResumePlan` 整对象旧新比较清单仅有上述一处。连续问号检查无命中。全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。

## 未完成

本轮任务列出的实现、规格、固定基线对照、定点变异与验收均已完成；没有剩余未完成项。
