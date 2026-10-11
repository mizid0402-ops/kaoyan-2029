# 细则审查任务书：D11 补充 —— 过期 `scheduled` 项计入冻结积压（窗口 `sol-rules`）

**只审细则本身**（与用户选项是否一致、边界与反例、会不会和已有决议冲突），不写代码、不审实现。
先读 `AGENTS.md`（"决策者细则先审再实现"、"评审严重度"）、`docs/阶段2.5-接缝收口.md` D11 一节、
`contracts/freeze.md`、`contracts/review_clip.md`（`unreachable` 一行）、`contracts/review_progress.md`、
`ky/freeze/port.py`、`ky/freeze/resume.py`，以及你第 118 轮报告 `review/rounds/round-118-review-sol-out.md` 第 19 行（B1 原文）。

## 用户决定（2026-09-29）

你在第 118 轮 B1 指出：已过期的 `scheduled` 项在 M9 是 `unreachable`（永远选不上），但冻结只数 `queued`，
所以大量卡住的项不会触发冻结、新内容照排。决策者给用户三个选项（保持现状 / 计入积压 / 另加修复提示或停排规则），
**用户选了"计入积压"**。

## 决策者事实核查

`git grep '"scheduled"' -- ky` 显示：**当前没有任何代码把复习项状态写成 `scheduled`**；它是队列 schema 允许的状态
（`VALID_REVIEW_STATES`），只能来自手工编辑、导入或将来的模块（例如路线图 ④ 课表协同把某项钉到某天）。
M9 对它的处理：`due_date > today` 为 `scheduled_ahead`，否则 `unreachable`。请核实这一点。

## 决策者细则（待审）

- **R1 逾期口径**：M27 `overdue_review_items(day, items)`（冻结判定与 `ky resume` 共用）改为
  `state in {"queued", "scheduled"}` 且 `due_date < day`。`suspended`、`retired` 仍不计；
  当天到期（`due_date == day`）的 `scheduled` 不算逾期（与 `queued` 一致；M9 仍把它列为 `unreachable`，不变）。
- **R2 冻结判定**：阈值、锁存、事件格式、`FreezeStatus` / `freeze_to_mapping` 字段**都不变**；`overdue_minutes`、
  `overdue_count` 自然包含这类项。不新增输出字段（M9 的 `unreachable` 已单独列出卡住的项）。
- **R3 `ky resume`**：过期 `scheduled` 项与过期 `queued` 项**同样分层、同样摊开**（逾期天数 > 当前 `interval_days` 为
  可能遗忘，退回 M10 起点、不计 lapse、不改 ease；否则保留进度），并且**状态改为 `queued`**、`revision + 1`
  （与重排写队列的既有做法一致）。理由：它原先被钉的那天已经过去，钉住已无意义；若不改回 `queued`，
  重排后的新到期日仍会被 M9 判为 `unreachable`，而且下一次判定仍算逾期 → 恢复后立即再冻结。
- **R4 不变的部分**：M9 裁剪、`scheduled_ahead`、`unreachable` 的定义与输出不变；M12 快照 / 月结的逾期统计
  （`ky/schedule/state_snapshot.py` 只数 `queued`）**本轮不改**——请判断这会不会造成"冻结说有积压、快照说没有"的口径分裂，
  以及是否应当一并改。
- **R5 无此类项时输出不变**：队列里没有过期 `scheduled` 项时，preflight / record / submit / resume 的输出与事件
  与改动前逐字节一致（实现包用固定提交哈希对照证明）。
- **R6 方向**：只让复习提前或不变，不拉长任何间隔（D9 / D11 既有约束）。

## 请重点审

1. R1–R3 是否忠实于用户选的"计入积压"，有没有漏掉的状态组合（例如 `scheduled` 且进度已满、已退役科目、迁移后的项）。
2. R3 把 `scheduled` 改回 `queued` 是否与 `contracts/review_progress.md` 的状态机或 M25 队列迁移冲突；
   有没有更小的改法能避免"恢复后立即再冻结"。
3. R4：快照 / 月结与冻结口径不一致是否属于"必须改"。
4. 当前无生产者写 `scheduled`：这条细则是否仍值得现在实现（用户已决定做；若你认为有风险，写明，由决策者转交用户）。
5. 给出你认为实现包必须覆盖的边界测试清单。

## 规则

只读，不跑全量；需要复现只跑单个模块或单条命令，临时文件放系统临时目录。
结论 PASS / FAIL（针对细则），分"必须改 / 建议改 / 不改"，每条附理由或反例。

## 报告

`review/rounds/round-186-d11-scheduled-rules-review-codex.md`。
