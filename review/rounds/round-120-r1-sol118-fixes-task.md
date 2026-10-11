# 任务书：修 sol 第 118 轮对 WP-R1 的 B3 / B5（冻结锁存 + 在最终计划对象上检查）与建议 B2

先读仓库根 `AGENTS.md`，再读：`review/rounds/round-118-review-sol-out.md`（全文，复现输入都在里面）、`docs/阶段2.5-接缝收口.md` 的 **D11**（已按 B5 修订为"锁存"，本包依据）、
`contracts/freeze.md`、`ky/freeze/port.py`、`ky/__main__.py`（preflight、`day-plan submit` / `record`、`_reject_submission_while_frozen`）、`ky/planner/port.py`（`_build_input_data`、`apply_human_plan`、`apply_staged_proposal`）、
`ky/storage/day_plan_store.py`（`DayPlanStore` 构造参数、`write_day_plan`、完成事件的一次写入写法）。

你在 worktree `F:\workspace\kaoyan-wt-r1fix`（分支 `stage25/r1fix`）里工作，只改这个目录。基线提交 = 本 worktree 起点（测试里写完整哈希，照 `AGENTS.md` 12a 断言取到的是旧版）。

## 决策者已定的设计（照做；有更好的写法先在报告里提）

### 1. 冻结锁存（B5，M13 + M27）

- **记录（M13，`DayPlanStore` 新方法）**：`write_freeze_record(day, status_mapping)` → `<store>/freeze/freeze--<D>.yaml`；`write_resume_record(day, mapping)` → `<store>/freeze/resume--<D>.yaml`（R2 的 `ky resume` 会调用它，本包只提供并测试）；
  两者都是**一次写入**（同一天第二次写拒绝，照完成事件），写前校验、临时文件重读校验再替换。只读：`freeze_records() -> tuple[date, ...]`、`resume_records() -> tuple[date, ...]`（只认存放在自己路径、文件名日期与内容一致的记录，照 `delivered_words` 的做法拒绝放错位置的文件）。
- **锁存判定（M27）**：`latch_active(freeze_days, resume_days) -> bool`：存在冻结日 F 使得没有 resume 日 R ≥ F。
  `assess_freeze(..., latched: bool = False)`：`frozen = latched or 达到阈值`（阈值规则不变，含"至少一个逾期项"）；`FreezeStatus` 增字段 `latched`（`freeze_to_mapping` 相应增加 `latched` 键——**只在冻结 payload 里**，未冻结输出不变）。
- **谁写冻结记录**：`day-plan record` 与 `day-plan submit` 在执行各自动作**之前**：若能找到注册表、登记了 `state.review_queue` 与 `state.plans`，且"达到阈值"为真而锁存不生效，就写当天的冻结记录（record 用事件的 `day`，submit 用计划的 `day`）。preflight / 输入包**不写**，只读记录参与判定。
- 写冻结记录后，`record` 照常推进队列（如实记录永远允许）；`submit` 拒绝。

### 2. 在最终计划对象上检查（B3）

- `DayPlanStore` 增加可选参数（例如 `freeze_gate: Callable[[date], None] | None`，与 `availability` 同样的注入方式）；`write_day_plan` 在 `check_invariants` 与 availability 上限之后、写任何文件之前调用它；`freeze_gate` 抛 `StorageError`（消息"已冻结，请先运行 ky resume"）即拒绝。临时文件重读时再按重读出的 `day` 调一次。
- CLI 删除 `_reject_submission_while_frozen` 的"先读一遍提案"，改为构造带 `freeze_gate` 的 store（gate 内部：读队列 → 读记录 → 必要时写冻结记录 → 判定）。这样检查对象就是 M19 解析后、真正要写的那个 `DayPlan`，文件被中途替换也无法绕过。
- 无注册表时不注入 gate（与现在一致，规格写明）。

### 3. 冻结时的文本（B2 建议，采纳）

冻结时 preflight 文本的 `review soft / hard` 行改为 `review soft / hard : 冻结期间不生效`，并且不打印 `timeline phase` 行；JSON 不变（`subject_review_quotas` 已不出现）。

### 4. 规格

`contracts/freeze.md` 改写"推导、不落盘"一节为锁存规则（记录格式、谁写、何时解除、preflight 只读）；删去 B3 相关的旧描述。

## 不做的

- 不做 `ky resume` 的重排（R2）；不把 `scheduled` 过期项计入积压（sol 118 B1 建议，另议）。

## 测试（只写这些，加在 `tests/contract/test_freeze_port.py`）

每条都要在撤回对应修复时变红（报告里写怎么验证的）：
1. **B5 回归**：sol 118 的输入——队列正好达阈值，冻结期间 `day-plan record --review-store` 记一条带核对结果的完成，积压降到阈值下；之后 preflight 仍报冻结（`latched: true`），`day-plan submit` 仍拒绝；写入 resume 记录后解除。
2. **B3 回归**：patch 让 M19 读到的提案与 CLI 第一次看到的不同（或直接构造带 gate 的 store 写冻结日计划）——冻结日计划被拒且不写；非冻结日正常写。
3. 记录：一次写入、放错位置拒绝、`latch_active` 的边界（R == F 解除、R < F 不解除、多次冻结 / 恢复交替）。
4. 冻结文本两行的新样式；未冻结文本与基线逐字节一致。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_freeze_port tests.test_day_plan_store tests.contract.test_planner_port tests.test_cli
```

## 报告

`review/rounds/round-120-r1-sol118-fixes-luna.md`（写在 worktree 里）：每项落点、记录格式、撤修复验证、验收输出、给 R2 的接口说明（`write_resume_record` 的参数与格式）。
写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。含中文的文件只用 `apply_patch` 编辑，写完查 `???`。
