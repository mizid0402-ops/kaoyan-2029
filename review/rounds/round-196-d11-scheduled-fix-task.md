# 任务书：D11 补充返工（窗口 `luna-c` 续做）

第 195 轮两位评审并行审了你第 189 + 194 轮的合并结果：`review/rounds/round-195-d11-scheduled-review-codex.md`（FAIL）与
`review/rounds/round-195b-d11-scheduled-review-sol61.md`（PASS，两条建议）。另外决策者提交前全量发现一处失败。先读两份报告。
基线仍是 `81285d2`。

## 要改

1. **preflight 说明行（195 M1）**：现在打印在 `UNREACHABLE` 列表之后，并写"下方 deferred -> backlog"，而 `deferred -> backlog` 那一行实际在它**上方**。
   把这行挪到 preflight 文本里**打印冻结状态的那一段**（`_preflight_print_summary` 里冻结相关输出处），措辞**不用方位词**，
   直接写"`deferred -> backlog` 一行只计本次裁剪延期"之类。触发条件不变（冻结判定计入了过期 `scheduled`）。
   测试断言这一行的完整字节及它所在的位置（紧随冻结状态输出）；无过期 `scheduled` 时逐字节不变的对照继续成立。
2. **全量失败**：`logs/fullsuite/full-20260930-091634.log`：
   `tests.contract.test_storage_ledger_split_baseline.StorageLedgerSplitBaselineTests.test_resume_schedule_matches_fixed_baseline_d11_boundary`
   比较 `dataclasses.asdict(old_plan) == dataclasses.asdict(new_plan)`，新 `ResumePlan` 多了 `scheduled_to_queued_count`。
   这是本包有意加的字段。改该测试：先断言新计划的 `scheduled_to_queued_count == 0`（输入全是 `queued`），再只去掉**这一个键**后比较其余全部字段；
   不改它的输入与其它断言。报告说明理由。再用 `git grep -n "asdict(.*plan\|ResumePlan" -- tests` 查其它把整个 `ResumePlan` 与旧版比较的地方，一并处理并列出。
3. **规格文字（195b m2）**：`contracts/projection_status.md` 第 20 行把 `count_review_items_by_subject` 说成 M27 的——改为真实调用链：
   M12 `count_review_items_by_subject` 复用 M27 `overdue_review_items`。`contracts/freeze.md` 补 R8："本规则只影响阈值；低于阈值时过期 `scheduled` 仍在 M9 列为
   `unreachable`，可手动 `ky resume` 重排（无锁存时也会处理它们）。"
4. **R5 探针固化为测试（195 S1 / 195b m1）**：把两份报告里补做的三项固定基线对照写进 `tests/contract/test_freeze_scheduled_backlog.py`：
   (a) 注册队列、非空纯 `queued` 积压下 `ky resume`（文本 / JSON × 预览 / 实写）的三元组与写后整棵工作区文件字节；
   (b) 注册队列达到阈值时 `day-plan record`（文本 / JSON）与 `day-plan submit --plan` 的三元组与写后文件字节（含冻结事件）；
   (c) M12 `count_review_items_by_subject` 与 M15 `status_to_mapping(status_as_of(...))` 在全 `queued` / 空 / `scheduled` 于 D / D+1 四类队列下的新旧结果字节。
   输入从配置推导（项数 = `ceil(backlog_days × review_hard_cap_minutes / 每项分钟)`），不写死数量；旧版取自 `git archive 81285d2` 并断言确为旧版。
   195b 报告的探针方法（同一 cwd、同一路径、每次运行前恢复输入字节、按原始字节比较）照做。
5. **不要 import `FreezePortContractTests` 这个 `TestCase` 类**（两位评审都指出它会被 unittest 在新模块里重复收集）：只复用需要的数据构造——
   若要复用的是它的私有辅助，按 `AGENTS.md` 不跨模块用私有名：把需要的构造在新模块里写一份小的辅助函数，或提到 `tests/contract/` 下一个共享的公开测试辅助模块。

## 撤实现验证

第 1 条：把说明行挪回原位置，确认位置断言变红；第 4 条任选 (a)(b)(c) 各一处在临时副本里制造一个旧新差异，确认对应测试变红。
报告写实际命令与结果，恢复后核对哈希。

## 不做的

不改 R1–R9 的行为；不改 M9、月结、冻结阈值 / 锁存 / 事件格式；不动 `tools/`、`data/`；不跑全量。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_freeze_scheduled_backlog tests.contract.test_freeze_port tests.contract.test_resume_port tests.contract.test_review_clip_port tests.contract.test_state_snapshot_port tests.contract.test_projection_status tests.contract.test_storage_ledger_split_baseline tests.test_cli
```

## 报告

`review/rounds/round-196-d11-scheduled-fix-luna.md`：逐条写改了什么、说明行前后对照、`asdict` 处理清单、新增测试覆盖、变异命令与结果、验收输出原文。
有未完成的如实写明。写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。含中文只用 `apply_patch`，写完查 `???`。
