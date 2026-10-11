# 第 189 轮：D11 过期 scheduled 积压实现记录

## 实现落点

- R1 / 第 1 条：`ky/freeze/port.py` 的 `overdue_review_items` 以 `due_date < D` 且状态为
  `queued` 或 `scheduled` 选择积压项；冻结状态 docstring 与 `contracts/freeze.md` 已同步。
- R2、R8 / 第 6 条：阈值仍用原容量乘数与大于等于比较；空积压不冻结；`unreachable` 和手动
  `ky resume` 的边界仍保留。细则写入 `contracts/freeze.md`。
- R3 / 第 2 条：`ky/freeze/resume.py` 使用共享判定，将重排项设为 `queued`，不改 `revision`，
  并沿用原间隔重置及分层规则。只在转换数大于零时，JSON / 恢复事件映射含
  `scheduled_to_queued_count`（本次计划的转换数）；终端预览与执行分别说明“将由”与“已由”。
  选择字段是为了让 JSON 和恢复事件能审计实际计划；字段按新条件出现，旧条件映射不变。
- R4 / 第 4 条：M9 `unreachable` 列表后，仅当冻结判定纳入积压且其中有过期 scheduled 时，
  输出其数量、分钟数、M9 桶以及 deferred 数仅指本次裁剪延期的解释。JSON 未新增字段。
  帮助文字由 `freeze when queued overdue reviews reach this many configured review-cap days`
  改为 `freeze when overdue queued or scheduled reviews reach this many configured review-cap days`。
  `unreachable` 注释已同步修正。
- R5：新测试确认固定基线 commit 中的旧判定确实只匹配 queued；**本轮未完成任务书要求的
  同日旧版/新版 preflight、record、submit、resume、M12、M15 全套逐字节及写入字节对照**。
- R6：恢复后新到期日可等于 D 或晚于 D；`interval_days` 不增加，既有重排逻辑保持。
- R7 / 第 5 条：record / submit 的新冻结事件写入之前，对同一份已读注册队列中的过期候选调用
  `validate_items_against_config`。record 捕获 `ContractError` 并转为退出 2。resume 既有全队列校验未改。
  **停用 / 配置外科目跨 record、submit --plan、submit --from-staging、resume 的无写入矩阵本轮未补齐。**
- 第 3 条：M12 通过 M27 的公开判定计 `backlog_minutes`，`due_today` 不变；M15 继续复用 M12 与
  M27。三个接口 schema 均未升版。同步了 `contracts/state_snapshot.md` 与
  `contracts/projection_status.md`。

## 定点测试

新增 `tests/contract/test_freeze_scheduled_backlog.py` 覆盖 D−1 / D / D+1、queued 与 scheduled
混合、retired / suspended 排除、冻结阈值等号与空积压、M12 / M27 口径、resume 转 queued、
revision 保持与条件 JSON 字段，以及 BASELINE 中旧 M27 判定的来源确认。
更新 `tests/contract/test_freeze_port.py` 的旧 queued-only 预期。更新 `tests/test_cli.py`，仅对
两个 preflight 帮助入口断言允许的帮助差异，其他 CLI 字节对照仍严格比较。

未覆盖任务书列出的完整 R5 基线端到端对照、锁存后清空、遗忘边界与迁移后 scheduled、resume
实际 CLI dry-run / 写入事件和提示的全矩阵，以及 R7 各入口停用 / 配置外科目与全无写入证明。
因此当前测试通过不代表这些验收边界已证明。

## 验收

执行命令：

```text
py -3.12 -m unittest tests.contract.test_freeze_scheduled_backlog tests.contract.test_freeze_port tests.contract.test_resume_port tests.contract.test_review_clip_port tests.contract.test_state_snapshot_port tests.contract.test_projection_status tests.test_cli
```

最近一次执行结果：

```text
Ran 98 tests in 41.769s
OK
```

额外定点检查 `py -3.12 -m unittest tests.contract.test_freeze_scheduled_backlog tests.test_cli.CliLegacyOutputTest`：

```text
Ran 4 tests in 2.655s
OK
```

首次完整验收曾遇到三项预期变化断言：新 backlog 测试错误地期望 D 日 scheduled 属于 due_today、
freeze_port 仍期望 queued-only、以及帮助文字字节基线。修正对应断言后定点检查通过。

任务书要求的三处撤实现变异（R1 回退、resume 不转 queued、R7 校验后移）**未执行**；没有可报告的
变异失败行。固定基线仅验证了 `81285d26cec32762755cabf2f667203366ae83d2` 的旧源码确实存在 queued-only
判定，未进行所要求的所有旧 / 新运行产物比较。

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。未提交。
