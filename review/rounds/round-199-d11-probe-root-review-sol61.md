# 第 199 轮新版来源固定复审：PASS

对象：luna-c 第 198 轮，限于 scheduled 测试相对第 197 轮的改动及其它文件一致性。
日期：2026-09-30。固定旧版：`81285d26cec32762755cabf2f667203366ae83d2`。

**第 197 轮 M2：RESOLVED。必须改：无。** 本轮独立重跑原变异，遗留变量不再把新版
重定向到旧树；来源错配检查与真实 CLI 启动对照也通过。

## 必须改

无。

## 建议改

无新增建议。本轮只关闭 M2 及检查其直接影响，不重新扩展已确认的其它修正。

## 不改：核对结果

### 1. 原 M2 复现已被阻止

`_new_checkout()` 在 `tests/contract/test_freeze_scheduled_backlog.py:671` 恒返回 ROOT，
没有读取 `D11_PROBE_NEW_ROOT`。新版 ROOT 来自当前测试模块路径，不随该环境变量改变。

本轮在系统临时目录复制完整 `ky/` 与 `tests/`，排除缓存。临时 Git 对象库用 alternates
只读访问主仓库固定提交；另解出独立的真正 `81285d2` 旧树。只在当前副本做原定点变异：

```text
totals[item.subject_id][3] += item.estimated_minutes
→ totals[item.subject_id][3] += item.estimated_minutes + 1
```

保留 `D11_PROBE_NEW_ROOT=<独立旧树>`，设置 `PYTHONDONTWRITEBYTECODE=1`，在当前
临时副本内执行：

```text
py -3.12 -B -m unittest tests.contract.test_freeze_scheduled_backlog.FreezeScheduledBacklogTests.test_m12_m15_mappings_match_fixed_baseline_for_four_queue_shapes
```

实测退出 1，queued 子用例在**第 359 行**的旧新三元组断言变红，旧积压值 10、新值 11。
不是因为来源检查或归档失败，而是确实执行了当前变异代码并比较出输出差异：

```text
FAIL: test_m12_m15_mappings_match_fixed_baseline_for_four_queue_shapes (queue='queued')
line 359: self.assertEqual(old[0], new[0], case)
AssertionError: Tuples differ ... backlog_minutes 10 ... != ... backlog_minutes 11 ...
Ran 1 test in 4.536s
FAILED (failures=1)
```

恢复临时副本源码原始字节、仍保留该变量，再跑同一测试退出 0。恢复后
state_snapshot.py 与主仓库 SHA-256 均为：
`728350605792125a4b999ad66e710343ad9dfbbf5e22bf7708fb4f7d33877796`。
主工作区未做变异。

### 2. 来源断言对旧新两侧、两种探针都生效

`_paired_command` 和 `_run_checkout` 都调用 `:651` 的 `_checkout_command`；传入旧树时
expected 是旧树，传入新版时 expected 是 ROOT。两侧没有分用不同来源检查。
检查发生在执行 CLI / M12-M15 脚本之前：

```python
actual = Path(ky.__file__).resolve().parent.parent
assert actual == expected
```

独立负探针在干净临时 cwd 执行以下四格：

| 启动辅助传入 expected | 实际 PYTHONPATH | 执行形式 | 实测 |
|---|---|---|---|
| 旧树 | 当前工作区 | `-m ky preflight -h` | 退出 1，ky source mismatch，stdout 空。 |
| 旧树 | 当前工作区 | `-c` 输出标记脚本 | 退出 1，标记未执行。 |
| 当前工作区 | 旧树 | `-m ky preflight -h` | 退出 1，ky source mismatch，stdout 空。 |
| 当前工作区 | 旧树 | `-c` 输出标记脚本 | 退出 1，标记未执行。 |

示例错误确实报告两个不同来源：
`ky source mismatch: F:\workspace\kaoyan-ai-system != <临时旧树>`。
正常同源运行没有新增 stdout/stderr。

### 3. runpy 启动与真实 `py -m ky` 的实测

旧新两侧统一使用同一个 `_checkout_command`：CLI 先设置参数，再以
`runpy.run_module('ky.__main__', run_name='__main__', alter_sys=True)` 启动。
M12/M15 的 `-c` 脚本则在原脚本前添加来源断言，不经过 runpy。

本轮没有只比较“包装旧版与包装新版”。对真正旧树、真正当前树**分别**比较：

- 当前测试辅助产生的 `python -c <来源检查 + runpy>` 命令；
- 同一解释器的实际 `python -m ky ...` 命令（即 `py -3.12 -m ky` 选定的 Python 3.12）。

每次恢复同一 cwd、同一输入路径、全部输入原始字节；比较退出码/stdout/stderr，以及
整棵工作区相对文件名→bytes 映射。没有归一化输出或删除字段。输入与 R5 固化测试一致：
动态推导达到冻结阈值的纯 queued 注册队列、空 reviews 的完成事件、零分钟日计划。

| 各侧实跑命令 | 启动方式间实测 |
|---|---|
| preflight 文本、JSON、帮助 | 三元组与全部文件字节一致，退出 0。 |
| preflight 未知选项错误 | stderr 原始字节一致，退出 2。 |
| record 文本、JSON，含冻结事件与完成记录 | 三元组与全部文件字节一致，退出 0。 |
| submit --plan 触发冻结拒绝 | 三元组与冻结事件字节一致，退出 2。 |
| 非空 queued resume：文本/JSON × 预览/实写 | 四格三元组与全部文件字节一致，退出 0。 |

共 11 类 × 旧新两侧 = **22 项启动方式对照，全部通过**。

另在旧树/新树的临时副本中把 `ky/__main__.py` 替换为只打印启动元数据、随后
`SystemExit(7)` 的探针，分别用真实 `-m` 和本辅助启动。两侧均观察到：

- argv[0] 是该树 `ky/__main__.py` 的相同绝对路径；后续参数完全保留，不是字面量 `ky`。
- `__name__ == '__main__'`，`__package__ == 'ky'`。
- `__spec__.name == 'ky.__main__'`，`__spec__.origin` 与 `__file__` 为相同模块路径。
- 退出码均为 7，stdout/stderr 逐字节一致。实际 CLI 的 0/2 退出码也均保留。

本机 Python 3.12 的 `Lib/runpy.py` 中，`alter_sys=True` 临时替换 argv[0] 为模块 origin，
与 `-m` 所用 `_run_module_as_main` 设置 argv[0] 的方式吻合；`ky/__main__.py` 保留
`raise SystemExit(main())`，包装器未截获该退出。

两种机制仍有实现区别：`-m` 使用现有主模块命名空间，run_module 使用临时主模块；来源
断言失败或未捕获异常时包装器可以增加错误栈帧。本轮结论针对上述受检 CLI/契约路径，
不声称任意 Python 程序完全等价。当前入口没有依赖这些差别，实测未改变被比较的字节或
使 R5 脱离真实用户命令。

### 4. 第 197 轮其它修正保持不变

用本轮之前保留的第 197 轮临时完整 `ky/`、`tests/` 快照逐文件比较原始字节（排除缓存），
文件集合相同，唯一差异为 `tests/contract/test_freeze_scheduled_backlog.py`。
因此 preflight 位置实现、M12/M27 行为、ResumePlan 单键零值断言及其它测试均未变。

contracts/docs 的当前 Git 规范化内容与第 197 轮所见 diff 的新 blob 标识一致：

```text
contracts/freeze.md             8255ba9
contracts/projection_status.md  f4f4943
contracts/state_snapshot.md     98518aa
docs/阶段2.5-接缝收口.md        68b0cf4
docs/阶段2.5-安全报告.md        34e81a9
```

这些文档没有第 197 轮原始字节快照；这里确认的是 Git 内容一致，不把它夸大成对历史换行
字节的比较。两处规格修正及 D11 细则内容保持不变。

测试文件差异仅是启动调用统一到辅助、增添来源检查、固定新版 ROOT。队列输入、阈值项数
推导、三元组/文件字节断言、单键 asdict 处理、旧源码断言均未放宽；没有重新导入其它
TestCase 类。

## 实际验证与证据

```text
py -3.12 -B -m unittest tests.contract.test_freeze_scheduled_backlog.FreezeScheduledBacklogTests.test_registered_freeze_and_nonempty_resume_match_fixed_baseline tests.contract.test_freeze_scheduled_backlog.FreezeScheduledBacklogTests.test_m12_m15_mappings_match_fixed_baseline_for_four_queue_shapes
Ran 2 tests in 12.221s — OK

py -3.12 -B -m unittest tests.contract.test_freeze_scheduled_backlog.FreezeScheduledBacklogTests.test_preflight_backlog_explanation_follows_freeze_status tests.contract.test_freeze_scheduled_backlog.FreezeScheduledBacklogTests.test_preflight_bytes_match_fixed_baseline_without_overdue_scheduled
Ran 2 tests in 6.652s — OK
```

以上设置 `PYTHONDONTWRITEBYTECODE=1`。独立临时探针：
`C:\Users\Lenovo\AppData\Local\Temp\d11-199-sol61.py`，命令
`py -3.12 -B C:\Users\Lenovo\AppData\Local\Temp\d11-199-sol61.py`。
证据目录：`C:\Users\Lenovo\AppData\Local\Temp\d11-199-sol61-ij8qp4e0`，包含
results.json、四条来源错配 stderr、原 M2 变异失败日志。临时证据可能被系统清理，关键
输入与方法已记入本报告。

`git diff --check` 通过。没有新增安全登记。未修改实现/仓库测试，未提交。
全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。

最终门禁：**PASS**。第 197 轮唯一阻断 M2 已关闭，未发现修复引入的新阻断。
