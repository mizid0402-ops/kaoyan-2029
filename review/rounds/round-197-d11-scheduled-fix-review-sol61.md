# 第 197 轮 D11 补充返工复审：FAIL

对象：luna-c 第 196 轮当前工作区；固定基线
`81285d26cec32762755cabf2f667203366ae83d2`。日期：2026-09-30。

第 195 轮 M1 的说明位置错误、旧 ResumePlan 对照失败、两处规格文字均已修好。
三项 R5 对照也已固化，并在本轮正常环境下通过。
**仍有一项必须改：新版源码路径可被继承环境变量静默替换，实测能让有回归的当前副本通过。**

## 范围

已读第 196 轮任务书、实现报告、两份第 195 轮报告及 AGENTS.md 相关规则。
按返工复审检查 `git diff 81285d2` 全部改动和新增 scheduled 测试，重点验证本轮新增部分。
未修改实现或仓库测试；变异仅在系统临时目录。没有全量测试或提交。

上一轮我没有核实新增说明的实际打印位置，漏掉了另一位评审的 M1；本轮已用真实 CLI 输出
验证位置与文字，不沿用上一轮对这部分输出的判断。

## 必须改

### M2 — 环境变量能把新版对照静默改为旧版对照

严重度：MAJOR，测试验收来源缺陷。
位置：`tests/contract/test_freeze_scheduled_backlog.py:659` 的 `_new_checkout()`，
及 `:269` / `:326` 两条新增基线测试中的新版子进程。

```python
def _new_checkout() -> Path:
    return Path(os.environ.get("D11_PROBE_NEW_ROOT", str(ROOT)))
```

**已确认事实：** 未设置该变量时，默认值是测试模块所在当前工作区 ROOT；本轮宿主环境中
该变量不存在，专项 10 条正常通过。设置变量时，函数无条件使用该路径，既不确认与 ROOT
相同，也不验证该树是不是被评审的新版。`_paired_command` 把它作为子进程 PYTHONPATH，
子进程也没有对实际导入源码的身份作断言。

**独立复现：** 在临时目录复制当前 `ky/` 与 `tests/`（排除缓存），使该副本本身成为测试
ROOT；给临时 Git 对象库设置 alternates，只读使用主仓库对象，以便测试继续执行固定
`git archive 81285d2`。另外解出一份真正旧版归档，断言旧 M27 仍只有 queued 判定。
在当前副本的 `ky/schedule/state_snapshot.py` 唯一一处积压累加制造变异：

```text
totals[item.subject_id][3] += item.estimated_minutes
→ totals[item.subject_id][3] += item.estimated_minutes + 1
```

随后在这个当前副本内执行同一测试名：

```text
py -3.12 -B -m unittest tests.contract.test_freeze_scheduled_backlog.FreezeScheduledBacklogTests.test_m12_m15_mappings_match_fixed_baseline_for_four_queue_shapes
```

| 同一变异副本，只有环境不同 | 实测 |
|---|---|
| 移除 D11_PROBE_NEW_ROOT，正常使用副本 ROOT | 退出 1；queued 子用例在第 375 行失败，积压 10 与 11 的输出字节不同。 |
| D11_PROBE_NEW_ROOT 指向另外解出的 81285d2 旧树 | 退出 0；四类队列全部通过，当前副本仍保留加 1 变异。 |
| 恢复源码，移除 D11_PROBE_NEW_ROOT | 退出 0。 |

第二格是**旧对旧**，并非新对新。旧侧始终由固定归档产生，其源码断言没有失效；失效的是
新版来源约束。不能以“旧树已被确认”推导“两侧一定是被评审的旧/新代码”。
环境变量也可以指向其它过期副本，让该副本替代当前工作区。

**分类理由：** 这不是已发现的产品运行错误，也不是声称本次干净环境验收是假通过。
这是本轮为固化 R5 新引入的测试入口缺陷，有确定的变异漏检证据，违反“对被评审当前版本
与固定旧版作对照”的验收要求。变量可随正常 Shell/测试子进程环境继承；是否在用户日常
环境中遗留，本轮没有证据。它无需攻击、并发或篡改仓库内部数据就能绕过当前代码，故列
必须改，不移入安全登记。

**最小修正：** 正常固定基线测试的新版明确绑定 ROOT，移除任意环境路径重定向。
变异仍可在完整临时 checkout 中执行，令测试模块的 ROOT 自然指向那个临时 checkout；
需要读取基线对象时由独立变异脚本提供 Git 对象库，不让常规测试暗中换被测对象。
如果保留专用变异入口，必须与常规验收分开，常规运行遇到替换变量不能静默换树后报通过。

回归要求：临时当前副本有上述变异时，即使继承变量指向旧树，常规测试仍应测试当前副本并
失败，或明确拒绝错误环境；不能得到旧对旧的 OK。之后恢复源码并运行受影响的两条 R5
测试即可，无需全量。

## 建议改

无新增建议。上一轮 m1 的三项测试固化、避免重复收集 TestCase 和 m2 的规格修正已落实；
新版来源缺陷单独列为上述 M2，不把其余已通过的修正重新打开。

## 不改：已修好及已验证部分

### 第 195 轮 M1：RESOLVED，实际打印顺序已确认

输入使用 `config-minimal.yaml`，复习项从 `reviews-normal.yaml` 第一项构造，D 为其到期日
加 3 天（本次 2026-09-15）。项数从配置阈值推导：
`ceil(backlog_days × review_hard_cap_minutes / estimated_minutes)`；均为 scheduled、D−1
到期。执行真实 `py -3.12 -B -m ky preflight --config config.yaml --items items.yaml --date D`。

本次 stdout 的真实顺序：

```text
project            : kaoyan-2029
FROZEN             : 积压 216 分钟 ≥ 3 天复习上限 216 分钟；今天不排任务，准备好后运行 ky resume
其中 27 项（216 分钟）为已过期的 scheduled （M9 列为 unreachable），已计入冻结积压；deferred -> backlog 一行只计本次裁剪延期。
date               : 2026-09-15
daily budget       : 120 min
review soft / hard : 冻结期间不生效

due items          : 0
selected           : 0  -> 0 min
deferred           : 0  -> backlog 0 min
UNREACHABLE        : 27 (state makes them unselectable -- fix the state)
```

说明完整 UTF-8 行匹配，紧随 FROZEN 行，没有“上方/下方”。独立另跑低于阈值的一项过期
scheduled，仍在摘要中打印说明，符合“触发条件不变”；这种情况下没有 FROZEN 行可跟随。
纯 queued、scheduled 到期 D、到期 D+1 三类输入均无说明，且与固定旧树退出码/stdout/stderr
逐字节一致。原位置错误没有残留。

### ResumePlan 全对象对照：RESOLVED

`tests/contract/test_storage_ledger_split_baseline.py:153` 先取新计划 asdict，
断言 `scheduled_to_queued_count == 0`，随后只 pop 这一键，再比较完整旧映射。
diff 未改变两个 queued 输入（遗忘分界 interval / interval+1）、availability 或其它断言。
定点执行该测试通过。`git grep -n -E 'asdict\(.*plan|ResumePlan' -- tests` 未发现另一处
需要同样处理的整计划旧新对照。没有扩大归一化范围。

### 两处规格文字：RESOLVED

`contracts/projection_status.md:20` 已写清 M12 count_review_items_by_subject 复用 M27
overdue_review_items，M15 使用 M12 结果。
`contracts/freeze.md` 阈值段已补明低于阈值 scheduled 仍由 M9 列为 unreachable、可手动
resume、无锁存时也处理。没有重新改变 R1–R9 的行为。

### 三项 R5 与测试收集：主体已落实，受 M2 限制

- `test_registered_freeze_and_nonempty_resume_match_fixed_baseline` 覆盖非空纯 queued
  resume 文本/JSON × 预览/实写，以及达到阈值的 record 文本/JSON、submit --plan。
- `test_m12_m15_mappings_match_fixed_baseline_for_four_queue_shapes` 覆盖 queued、空、
  scheduled 在 D / D+1，实际调用 M12 以及 status_to_mapping(status_as_of(...))。
- `_extract_baseline` 用固定完整哈希 git archive，并断言旧 M27 queued-only、排除新判定。
- `_paired_command` 每次恢复同一 cwd、同一路径和输入字节；返回三元组以及完整相对路径→
  bytes 文件映射。两条测试直接比较 bytes，没有删除输出字段或抹掉路径/换行。
- 不再导入 FreezePortContractTests；模块本轮仅收集自身 10 条测试，没有重复收集该类。

以上在没有替换变量时通过。不能因此宣称任意继承环境下也固定测试当前版本，原因见 M2。

## 实际命令与证据

常规环境，设置 `PYTHONDONTWRITEBYTECODE=1`：

```text
py -3.12 -B -m unittest tests.contract.test_freeze_scheduled_backlog
Ran 10 tests in 29.683s
OK

py -3.12 -B -m unittest tests.contract.test_storage_ledger_split_baseline.StorageLedgerSplitBaselineTests.test_resume_schedule_matches_fixed_baseline_d11_boundary
Ran 1 test in 0.332s
OK
```

独立 preflight/变异/错误环境探针脚本：
`C:\Users\Lenovo\AppData\Local\Temp\d11-197-sol61.py`。
复现命令：`py -3.12 -B C:\Users\Lenovo\AppData\Local\Temp\d11-197-sol61.py`。
成功完成的证据目录：
`C:\Users\Lenovo\AppData\Local\Temp\d11-197-sol61-4dawjvm8`，含各 preflight stdout 原始
字节、`results.json` 及 `mutant-default-root.stderr` / `mutant-env-points-old.stderr`。
临时文件可能被系统清理，输入、变异和运行方法已在上文记录。

定点变异默认环境的原始结论：

```text
FAIL: test_m12_m15_mappings_match_fixed_baseline_for_four_queue_shapes (queue='queued')
line 375: self.assertEqual(old[0], new[0], case)
AssertionError: Tuples differ ... backlog_minutes 10 ... != ... backlog_minutes 11 ...
Ran 1 test in 13.572s
FAILED (failures=1)
```

仅更改覆盖变量后，同一变异副本：`Ran 1 test in 4.438s; OK`。
恢复原字节后的临时 state_snapshot.py 与主工作区均为 SHA-256：
`728350605792125a4b999ad66e710343ad9dfbbf5e22bf7708fb4f7d33877796`。
主工作区实现没有被变异。`git diff --check` 通过。

安全登记：没有新增安全项；M2 是验收测试来源约束，不是安全攻击模型。
全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。未提交。

## 返工束

只修 M2：将正常 R5 测试的新版绑定当前 ROOT，避免任意继承环境静默替换源码。
用上述“当前副本积压 +1、覆盖变量指向固定旧树”复现，修后不得再得到 OK；恢复源码后
只跑两条新增 R5 对照。保留说明位置、单键 asdict 修正、规格文字和字节比较，不做无关重构。

最终门禁：**FAIL**，仅 M2 阻断。
