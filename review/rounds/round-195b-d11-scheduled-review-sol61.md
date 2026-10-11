# 第 195b 轮独立评审：PASS

评审对象：luna-c 第 189 + 194 轮合并后的当前工作区。固定基线：
`81285d26cec32762755cabf2f667203366ae83d2`。评审日期：2026-09-30。

**必须改：无。** 三项自报缺失的 R5 对照由本轮独立探针补出了无差异证据；建议把探针转为
仓库内固定基线测试，但不因此阻止本包接受。PASS 只针对本实现包，不代替阶段 2.5 的总验收。

## 范围与方法

- 已读 `AGENTS.md` 全文、第 189 / 194 轮任务书及实现报告、定稿 D11 补充 R1–R9。
- 已逐文件检查 `git diff 81285d2` 的全部已跟踪改动及新增
  `tests/contract/test_freeze_scheduled_backlog.py`。安全报告的 S19 汇总改动也已对照当前登记表。
- 已追踪 record、直接 submit、staging submit、resume 的校验、异常出口和写入顺序，
  以及 M12/M15/M27 的统计调用关系。没有读取另一窗口的 `round-195-...-codex.md`。
- 应用 `code-review-gate` 的证据分级；严重度、测试范围与安全登记按本仓库 AGENTS.md。
- 实现和测试只读。变异在系统临时目录的副本上执行；本轮只向仓库新增本报告，不提交。

## 必须改

无。没有复现本次改动导致的正常使用错误、输出回归、先写后校验或 traceback。

## 不改：R1–R9 核对

| 细则 | 实现落点与可复现输入 | 结论 |
|---|---|---|
| R1 | `ky/freeze/port.py:68` 仅选择 queued/scheduled 且 due_date < D。新增模块的日期边界测试输入含 scheduled 在 D−1/D/D+1，以及 queued/retired/suspended 在 D−1。 | 通过；同日/未来 scheduled 不计，retired/suspended 不计。 |
| R2 | 阈值比较、空积压和锁存算法未改。日期边界测试用 `hard_cap × backlog_days` 的 scheduled 项验证等号；空元组不冻结。另执行既有“清空积压后解除锁存”单测。 | 通过；FreezeStatus/freeze_to_mapping 形状未改。 |
| R3 | `ky/freeze/resume.py:57` 复用 M27；赋新日期时设 queued，replace 未指定 revision。探针给 scheduled 构造“逾期恰等于 interval”和“interval+1”两项，并实际执行 resume。 | 通过；前者保留进度，后者重新学习；revision 不变，defer_count 清零。 |
| R4 | M12 在 `state_snapshot.py:109` 调用公开 overdue_review_items；M15 在 `status.py:222` 调用 M12，冻结判定调用 M27。新提示限于 unreachable 中存在过期 scheduled；没有复制 M12/M15 的积压条件。 | 通过；新条件探针验证三者分钟一致，M9 单测验证桶及延期行为。JSON 没有增加来源提示字段。 |
| R5 | 固定基线不是 HEAD。已有 preflight/record/submit/空 resume 对照加本轮三项独立对照，见下一节。 | 已测输入均一致；持久测试仍有覆盖缺口，列建议改 m1。 |
| R6 | `_assign_overdue_items` 保留间隔不增断言。新条件探针逐项检查 revision 相同、interval 不增、due_date ≥ D、defer_count 为零。 | 通过；重学可缩短间隔，不要求所有项的 interval 必须保持原值。 |
| R7 | `__main__.py:176` 仅加载一次注册队列，将同一 tuple 传给冻结判定，并在 `:181` 调用公开校验器，`:184` 才写冻结事件。record 在 `:1255` 捕获 ContractError；submit apply 已捕获；resume 全队列校验与 staging 的 M9 校验保留。 | 新模块的 12 个矩阵格通过，均退出 2、提示 inactive/not declared、无 traceback、全工作区文件哈希未变。 |
| R8 | 低于阈值只计积压，不改变 scheduled 的 M9 可达性。探针用两项过期 scheduled（总量低于阈值），确认 preflight 仍列 unreachable，手动 resume 可恢复。 | 行为通过；建议在 freeze 契约补明此句，见 m2。 |
| R9 | `_print_scheduled_conversion` 仅在转换数 > 0 且非 JSON 时打印；dry-run 用“将由”，实写用“已由”。JSON/恢复事件的条件字段在契约登记为本次计划的转换数。 | 低于阈值/达到阈值 × dry-run/实写 × 文本/JSON 共 8 格探针通过；queued 旧路径不出现新增文字或字段。 |

R7 的 12 格输入是：从 fixture 配置动态选 inactive 科目及动态生成配置外科目，各走 record
无复习完成、有复习完成、有完成且显式 review-store 为另一队列、submit --plan、
submit --from-staging、resume。注册队列均为过期 scheduled，总分钟足以触发冻结。
校验对象是注册队列，不是用显式 review-store 替代它。

R4 的文本条件不要求 `freeze.frozen == True`：低于阈值但已有过期 scheduled 时也确实计入了
冻结积压，打印来源说明符合定稿。“冻结积压”与 M9 的本次 deferred 仍是两种统计。

## 三项缺失 R5 对照的独立实测

探针脚本：`C:\Users\Lenovo\AppData\Local\Temp\d11-sol61-probe.py`。
本次结果：`C:\Users\Lenovo\AppData\Local\Temp\d11-sol61-evidence-3w2_eu12\results.json`；
该目录还保存新旧 stdout/stderr 原始字节、M12/M15 映射字节及变异失败日志。
临时证据可能被系统清理，以下输入与方法同时记录在报告中。

复现命令（脚本保留时）：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
py -3.12 -B C:\Users\Lenovo\AppData\Local\Temp\d11-sol61-probe.py
```

探针使用 `git archive 81285d26cec32762755cabf2f667203366ae83d2` 解出整个旧源码树，
断言旧 M27 源码包含 `item.state == "queued"`。子进程分别用旧树/当前工作区作为唯一
PYTHONPATH，在同一个临时 cwd、同一个文件路径、同一个输入快照上运行；每次运行前恢复
全部输入文件字节。比较 `(returncode, stdout, stderr)` 和整棵临时工作区的相对文件名→原始
字节映射，不归一化日期、路径、提示、换行或事件。SHA-256 仅用于记录，实际断言用 bytes。

### 1. 非空 queued 积压的 resume

输入使用 `FreezePortContractTests.setUp()` 注册表与配置。D 为该 fixture 的 2026-09-15；
以首个复习项为模板，状态 queued、due_date=D−1、estimated_minutes=8、review_id 唯一，
项数为 `ceil(FreezePolicy.backlog_days × config.review_hard_cap_minutes() / 8)`，从配置推导。
此输入无 scheduled。执行：

```text
py -3.12 -B -m ky resume --date 2026-09-15 --config config.yaml
  --workspace kaoyan.workspace.yaml [--dry-run] [--json]
```

文本/JSON × 预览/实写四种组合，新旧均退出 0，stdout/stderr 逐字节一致。
预览全部文件未变；实写后的完整队列（manifest、新旧分片文件）及恢复事件逐文件逐字节一致，
且实际断言存在 resume 事件，不是两个“没有写入”之间的空对照。

实写共同摘要：

```text
data/review_queue/manifest.yaml
60d706df2d795fbe293e366e80b0b0f2ef097a595f6d519211cf26fa146a6f52
data/plans/freeze/000001-resume--2026-09-15.yaml
4610293e85d36e80b2da16f3c21d122ef18837596bcb608b30f5dca52311bebc
```

### 2. 注册队列触发冻结时的 record / submit

注册表、D、纯 queued 阈值队列与上一项相同。record 输入为 schema_version=2、day=D、
reviews=[]；submit 输入为 `_empty_plan_mapping(config, D)`：可用分钟与各项分钟为零，
subject_minutes 从配置的 active_subjects 推导。执行：

```text
py -3.12 -B -m ky day-plan record --done done.yaml --config config.yaml
  --workspace kaoyan.workspace.yaml [--json]
py -3.12 -B -m ky day-plan submit --plan plan.yaml --config config.yaml
  --workspace kaoyan.workspace.yaml
```

record 文本/JSON 均退出 0，确实写出冻结事件和完成记录；submit 均退出 2，确实写出冻结
事件、提示先运行 ky resume、没有提交日计划。三格的新旧退出码、stdout、stderr、整棵
工作区所有文件字节均一致。三格的冻结事件共同摘要：

```text
data/plans/freeze/000001-freeze--2026-09-15.yaml
0c82febf03f747406fd466a230ee864d5313a6a06c78c579b34e0ac60a3ac76e
```

### 3. M12 / M15 固定基线结果

输入由 `ProjectionStatusTests.setUp()` 生成：配置、同一 D、既有计划/完成/冻结恢复序列、
availability 和 route，先建立同一份 SQLite 投影供新旧只读。此 fixture 的 D 为运行日，
本次为 2026-09-30；比较期间 D 固定，没有分别取两次日期。
分别将队列改为以下四类，再重建投影：

- 全 queued（保留 fixture 的 D−1/D/D+1 分布）。
- 空队列。
- 全 scheduled、due_date=D。
- 全 scheduled、due_date=D+1。

隔离子进程断言 `ky.__file__` 位于指定源码树，分别调用：
`count_review_items_by_subject(items, D)` 与
`status_to_mapping(status_as_of(the_same_projection, D, config))`。
M12 dataclass 映射和 M15 完整映射统一序列化为固定参数 JSON 后比较原始字节；四类均一致，
退出码与 stderr 也一致。未删除任何字段来获得相等。另用全过期 scheduled 的新条件验证
M12/M15/M27 积压分钟总和相等。

**实测结论：三项均未出现差异。** 这证明上述输入的 R5 行为；有限探针不等于穷举所有输入。
结合改动分支与调用关系，本轮没有发现仍需阻断的旧路径回归。

## 定点变异

在临时目录复制当前 `ky/` 和 `tests/`，排除 `__pycache__` / `*.pyc`；主工作区未被变异。
移除 `_assign_overdue_items` 中 replace 的 `state="queued"` 参数，其余保持不变。
设置 `PYTHONDONTWRITEBYTECODE=1`，并用 `-B` 执行：

```text
py -3.12 -B -m unittest tests.contract.test_freeze_scheduled_backlog.
  FreezeScheduledBacklogTests.test_resume_converts_scheduled_without_revision_change
```

上面是便于阅读的折行，实际为一个完整测试名。原始失败：

```text
line 75, in test_resume_converts_scheduled_without_revision_change
    self.assertEqual(changed.state, "queued")
AssertionError: 'scheduled' != 'queued'
Ran 1 test in 0.002s
FAILED (failures=1)
```

变异退出 1；恢复原文件字节后同一条测试退出 0。恢复后副本与当前实现的 resume.py 摘要均为：
`263424e6c1f9092602f00e8df6b9be563af75a2e566e88345b205ecad6222d0a`。
本轮独立确认一处变异；没有把实现者自报的三处变异当成本轮亲测结果。

## 建议改

### m1 — 将缺失对照和 scheduled 正常 CLI 路径固化为测试

严重度：非阻断。位置：`tests/contract/test_freeze_scheduled_backlog.py:148`。
可复现输入就是上文三项基线探针及 R3/R9 的 scheduled 输入。
当前基线测试的 record/submit 没有注册表，resume 是空队列且仅比较 plans，不能自动守住
非空队列/恢复事件、冻结事件或 M12/M15 的回归。scheduled 实写/预览、遗忘边界与提示的
新增分支也主要由本轮探针验证，适合纳入该模块。

分类依据：本轮要求自己补探针并判断测试缺口是否阻断，而 AGENTS.md 第 12 条允许把对照
写成测试或记入报告。本报告已有固定基线、真实运行、原始产物比较和可复现输入，未观察到
日常使用的行为回归，因此不把“尚未固化”直接等同于“必须改”。它仍是未来维护的测试缺口，
不能宣称第 194 轮的原有自动化测试已完整满足最初任务书。

### m2 — 修正契约的模块归属并补明 R8

严重度：非阻断的文档准确性问题。
复现：读取 `contracts/projection_status.md:20`，现文字称使用“M27 的
count_review_items_by_subject”，但实际接口属于 M12，M12 再复用 M27 overdue_review_items。
建议改成这条真实调用链。

读取 `contracts/freeze.md` 的 resume 段，虽已登记 queued/scheduled 与条件 JSON 字段，
尚未明写任务书第 6 条要求的“低于阈值仍为 unreachable，可手动 resume”说明。
复现输入为上文低于阈值的两项过期 scheduled；行为本轮通过，定稿 docs 中也已有 R8，
故属契约文字补全，不是需要返工的运行缺陷。

## 安全登记

没有发现本补充引入的新安全项。新增 R7 校验全体 overdue candidates（含 queued）是收紧
科目校验；配置外/停用科目的内部非法 queued 数据不作为正常旧路径兼容性要求。

`docs/阶段2.5-安全报告.md` 的额外改动把既有 S19 纳入汇总，与当前
`docs/安全风险登记.md` 的 19 项及各状态数量一致。S19 的触发是另一写者在分片发布/清理窗口
插入，可能覆盖或误删同名分片；修法为原子不覆盖发布与仅清理本次文件。它已有登记且并非
本补充引入，按 AGENTS.md 安全范围保留，不开返工轮。本轮未重复执行并发攻击探针。

## 实际验证

```text
py -3.12 -B -m unittest tests.contract.test_freeze_scheduled_backlog
Ran 20 tests in 26.325s — OK
```

注意此模块 import 了 FreezePortContractTests，unittest 也收集其 13 条；新增类本身为
7 条，不能把输出中的 20 条都说成新增 scheduled 专项测试。R7 子用例矩阵包含在这 7 条中。

```text
py -3.12 -B -m unittest tests.test_cli.CliLegacyOutputTest
Ran 1 test in 2.894s — OK

py -3.12 -B -m unittest tests.contract.test_resume_port.ResumePortContractTests.test_resume_clears_a_latch_when_nothing_is_overdue
Ran 1 test in 0.922s — OK

py -3.12 -B -m unittest tests.contract.test_review_clip_port.ReviewClipPortTests.test_scheduled_item_due_today_is_unreachable tests.contract.test_review_clip_port.ReviewClipPortTests.test_scheduled_buckets_keep_input_order tests.contract.test_review_clip_port.ReviewClipPortTests.test_deferral_changes_nothing_but_defer_count
Ran 3 tests in 0.005s — OK
```

以上均显式设置 `PYTHONDONTWRITEBYTECODE=1`。另有 11 格缺失基线对照、1 格新条件
M12/M15/M27 一致性、8 格 scheduled CLI 和 1 处变异/恢复，由临时探针执行。
`-h` 对照已断言选项块外 stdout 完全相同，退出码/stderr 相同，新选项块等于完整期望字节。
未在其他旧路径对照里消除帮助差异。

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。没有读取并行窗口报告，没有修改实现。

**最终门禁：PASS。** m1/m2 为建议改；本轮证据范围内无必须改项。
