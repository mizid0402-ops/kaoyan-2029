# Round 125 Codex 独立评审：有序冻结事件与 `ky resume`

评审基于 `git archive 08d416a` 的系统临时目录，补入本机原始资料和空 `products/`；对照 `a1ba242`、两份任务书、`contracts/freeze.md` 与 D11。只跑定向模块和探针，未跑全量。以下“必须改”只用于日常使用会遇到的问题；并发与内部文件篡改单列安全登记。

## 1. 有序事件与锁存

| 项目 | 意见 | 证据及可复现输入 |
| --- | --- | --- |
| 同日多轮 | **不改** | 在临时工作区写 27 个各 8 分钟、9 月 14 日到期的项，依次写 9 月 15 日 `freeze`、`resume`，同日执行一条带核对结果的 `day-plan record --review-store`：退出 0，事件成为 `(1,F),(2,R),(3,F)`，`preflight --json` 的 `freeze.latched=true`；同日再执行 `ky resume --date 2026-09-15`：退出 0，追加 `(4,R)`，preflight 无 `freeze`。另以锁存的空队列提交合法零分钟计划，`day-plan submit --plan` 退出 2，未写计划文件。实现见 `ky/__main__.py:143-159,475-499`、`ky/freeze/port.py:50-60`；`tests/contract/test_freeze_port.py:362-377,478-501` 与 `tests/contract/test_resume_port.py:176-214` 分别锁住部分路径。第二轮的完整 CLI 串联尚未写成一条测试，建议补在现有契约测试中。 |
| 事件读取及路径 | **不改** | `DayPlanStore.freeze_events()` 递归读取 YAML、按序号排序并拒绝重复序号；`_read_freeze_event()` 核对内容中的序号、类型、日期与预期路径（`ky/storage/day_plan_store.py:529-599`）。现有测试把文件放进子目录、改文件名日期、改内容序号，均断言拒绝（`tests/contract/test_freeze_port.py:411-438`）。重复序号也已用临时探针证实报 `StorageError: duplicate freeze event sequence`；类型不符会被负载形状或路径核对拒绝。 |
| 锁存判定 | **不改** | `R.sequence > F.sequence` 且 `R.day >= F.day` 才能解除 F（`ky/freeze/port.py:50-60`），与 `contracts/freeze.md:60-64` 一致。`F(9/15,1),R(9/14,2)` 仍锁存；`F(9/15,1),R(9/15,2),F(9/15,3)` 也仍锁存；之后追加 `R(9/15,4)` 才解除。见 `tests/contract/test_freeze_port.py:440-461` 与上述实际 CLI 探针。 |
| **回填恢复日的虚假成功** | **必须改** | 正常回填输入：在空队列、9 月 15 日已有冻结事件时执行 `ky resume --date 2026-09-14 --workspace <注册表>`。实际退出 **0**，写入 `(2,resume,9/14)`，文本声称“积压已清空，已解除冻结”；随后的 9 月 15 日 `preflight --json` 仍为 `freeze.latched=true`。`--dry-run` 同样声称正式执行会解除冻结。原因是 `resume_main` 只检查 `latched`，无逾期时直接写事件和成功提示（`ky/__main__.py:480-496`），却没有检查该事件能否解除现有 F。带逾期项时 `ky/__main__.py:497-499` 还会先改队列再留下无效恢复事件。用户用 `--date` 回填是正常操作，这不是并发或恶意输入。最小修法：在**任何队列写入前**，若存在未解除且日期晚于请求日的 F，退出 2 并给出该冻结日；同时补无逾期、带逾期、dry-run 三个断言。较晚日期重跑能恢复，所以并非永久卡死，但当前成功提示是错误的。 |

## 2. `ky resume` 重排与提交顺序

| 项目 | 意见 | 证据及可复现输入 |
| --- | --- | --- |
| 分层、进度与配额 | **不改** | `ky/freeze/resume.py:47-109` 只取 queued 且严格逾期项，按“逾期天数 > 当前间隔”分层、旧到期日和 ID 排序；`ky/schedule/completion.py:150-152` 只把间隔置 1、重复数置 0，ease、lapses、phase 不变。`tests/contract/test_resume_port.py:72-140` 覆盖等号边界、原项不变、阶段分科配额、共享软配额、366 天放不下。另用手填当日 0 分钟探针：1 分钟逾期项排到次日、间隔不变；用当日已到期项占满软配额探针：逾期项排到次日、已到期项不变。容量计算见 `ky/freeze/resume.py:116-175`、`ky/schedule/budget.py:89-128`。 |
| dry-run、重复及故障重试 | **不改** | `tests/contract/test_resume_port.py:142-214` 断言 dry-run 不改 manifest/事件、正式运行后同日无事可做不追加记录，以及有锁存但无逾期仍可写恢复事件。另对 `write_resume_record` 注入一次 `StorageError`：首次退出 2，队列已无逾期、锁存仍在；再次运行退出 0，事件从 `[freeze]` 变为 `[freeze,resume]`，锁存解除。这符合 `contracts/freeze.md:99-103` 的队列先于审计事件提交次序。 |
| 放不下的项 | **不改** | 搜索范围为 D 起 366 日；无可用日期时把到期日设 D 并列入 `unschedulable_review_ids`（`ky/freeze/resume.py:75-87,149-175`）。`tests/contract/test_resume_port.py:119-140` 以 10000 分钟的项验证该分支。此处“放不下”不保证 M9 一定把每一种原因都标成“需拆分”；现有 CLI 自身已输出放不下 ID。如要承诺 M9 的具体提示，建议另写端口级断言。 |

## 3. `day-plan record` 的注册表提示

| 项目 | 意见 | 证据及可复现输入 |
| --- | --- | --- |
| 无注册表与有注册表 | **不改** | 在临时工作区给 `record` 显式 `--store`、不存在的 `--workspace` 与 `reviews: []` 完成事件：文本与 JSON 均退出 0，文本额外一行警告，JSON 含 `freeze_latch_warning`；换为有效注册表，JSON 不含该键。分支只在 `workspace is None` 时添加（`ky/__main__.py:993-998,1090-1111`），与 `contracts/freeze.md:38-43` 的取舍一致。注册表不可用时锁存不保证存在，风险已列入 `docs/安全风险登记.md` S10；建议在操作说明里把恢复前先修注册表写得更醒目。 |

## 4. 测试强度

| 项目 | 意见 | 证据及可复现输入 |
| --- | --- | --- |
| 定向运行 | **不改** | 归档内 `py -3.12 -m unittest tests.contract.test_freeze_port`：13 项 OK；`tests.contract.test_resume_port`：5 项 OK；`tests.test_day_plan_store`：19 项 OK。未运行全量。 |
| 撤修复探针 | **不改** | 在内存中把测试模块的 `latch_active` 临时替换为“只比较日期、不比较序号”，`test_latch_active_resume_boundaries_and_multiple_cycles` 变为 1 个失败；把发布辅助临时替换为旧 `os.replace` 写法，`test_link_race_does_not_overwrite_the_other_writer` 也变为 1 个失败。两处回归测试能在相应修复撤回时变红。 |
| 缺失的断言 | **建议改** | 现有 `test_same_day_resume_then_refreeze_is_an_ordered_second_cycle` 到第二次冻结即结束（`tests/contract/test_freeze_port.py:478-501`）；无注册表警告亦无直接回归断言。尤其上述回填恢复日输入现返回 0，新增测试应断言拒绝且队列、事件字节不变；这项随“必须改”修复一起做。 |

## 安全登记（不计入 FAIL）

| 现象与触发条件 | 影响 | 可能修法 |
| --- | --- | --- |
| **同序号、不同事件文件名可双双发布。** 两个进程都在 `ky/storage/day_plan_store.py:525-527` 读到下个序号 1，一个写 `000001-freeze--2026-09-15.yaml`，另一个写 `000001-resume--2026-09-16.yaml`。因为 `os.link` 的目标路径不同，后者不会撞上 `FileExistsError`。临时探针用 `patch.object(DayPlanStore, '_next_event_sequence', return_value=1)` 模拟第二写者的过期读，两个发布都成功。 | 下次 `freeze_events()` 报 `duplicate freeze event sequence`，冻结检查与恢复命令都无法正常继续，需人工清理；所以 `docs/安全风险登记.md` S9 中“后者失败需重跑、不丢数据”只对**同名目标**成立。该竞态需要两个写者恰好交错，依本轮威胁模型不作为必须改。 | 用跨进程序号锁，或先按纯序号建立唯一的原子占位，再发布含类型/日期的事件；同时定义崩溃后占位恢复。 |
| **注册表不可用时不写冻结锁存。** 显式 `--store` / `--review-store` 仍可记录并推进队列，但会只有警告；若积压因此降到阈值以下，后续可能不经手动 resume 解冻。 | D11 的手动重启保证在这个已记录的例外路径上不成立；这是 `docs/安全风险登记.md` S10，当前实现按决策者取舍保留。 | 以后可用显式状态存储路径检查/写入锁存，或要求先恢复注册表。 |

## 结论

**第 124 轮有序事件：PASS；WP-R2：FAIL；整体 `08d416a`：FAIL。** 唯一阻断项是回填日期的 `ky resume` 可能报告“已解除冻结”并写入状态，实际锁存仍生效。并发撞号问题只作安全登记，不影响本轮 PASS/FAIL 判定。
