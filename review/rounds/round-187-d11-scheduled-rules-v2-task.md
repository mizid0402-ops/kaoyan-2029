# 细则复审任务书：D11 补充 v2 —— 过期 `scheduled` 计入积压（窗口 `sol-rules`，续第 186 轮）

你第 186 轮判细则 FAIL（`review/rounds/round-186-d11-scheduled-rules-review-codex.md`），M1–M3 决策者全部采纳，
两条建议也采纳。下面是修订后的细则 v2。**只审细则**，重点看 M1–M3 是否已被正确吸收、有没有引入新问题。

## 细则 v2

- **R1 逾期口径（不变）**：一个共享的公开判定"逾期复习项" = `state in {"queued", "scheduled"}` 且 `due_date < D`。
  `suspended`、`retired`、`due_date >= D` 的 `scheduled` 不计。M27 冻结判定与 `ky resume` 用它。
- **R2 冻结判定（不变）**：阈值、等号、空积压不冻结、锁存、事件格式、`FreezeStatus` / `freeze_to_mapping` 字段不变；
  `overdue_minutes` / `overdue_count` 自然包含过期 `scheduled`。
- **R3 `ky resume`（改）**：过期 `scheduled` 与过期 `queued` 同样分层、同样摊开（逾期天数 > `interval_days` 为可能遗忘，
  M10 `reset_for_relearning`，不计 lapse、不改 ease；否则保留进度），被赋予新到期日时**状态改为 `queued`**，
  **`revision` 保持原值**，其它字段按 D11 既有重排处理（`contracts/freeze.md` 的"其他字段不变"改为"除状态 `scheduled → queued` 外不变"）。
  理由：原钉日已过；若仍为 `scheduled`，新到期日当天会被 M9 判为 `unreachable`，永远选不上。
- **R4 当前积压同一口径（改，吸收 M1）**：
  - M12 公共计数端口的 `backlog_minutes` 改用 R1 判定；M15 按日期查询复用该端口，随之同口径。`due_today` 仍只数 `queued && due_date == D`。
    同步 `contracts/state_snapshot.md`、`contracts/projection_status.md` 的字段说明。
  - M9 `ClipResult.backlog_minutes`（本次裁剪延期的分钟）**会计定义不变**，M9 两个 `scheduled` 桶不变。
  - 为免"冻结积压 216 / 本次延期 0"被误读：**仅在冻结判定里确有过期 `scheduled` 被计入时**，preflight 文本冻结段多打印一行，
    说明其中 N 项（M 分钟）为已过期的 `scheduled`（M9 列为 `unreachable`），已计入冻结积压；JSON 不加字段。
    无此类项时文本逐字节不变（R5）。
  - 月结（`monthly_close`）累加的是已存日计划自己声明的 `backlog_minutes`，**不是**当前队列统计，不改；规格里写明这一区别即可。
- **R5 旧路径不变（不变）**：队列中没有过期 `scheduled` 时，preflight 文本 / JSON、record、submit、resume 与事件、
  快照 / 投影状态输出与固定提交哈希的旧版逐字节一致。
- **R6 方向（改，吸收 M2）**：冻结与重排**不增加任何项的 `schedule.interval_days`**；已过去的到期日可以被移到 D 或之后（日历上变晚是恢复安排的必然结果）。
- **R7 停用 / 配置外科目（新增，吸收 M3）**：在会写冻结事件的入口（`day-plan record` / `submit` 的冻结锁存）与 `ky resume`
  （写队列或恢复事件）处，于**任何写入之前**，用既有公开校验器（`ky.models.validate_items_against_config` 或其公开等价物）
  核对本次新纳入的过期 `scheduled` 候选；配置外或已停用科目报契约错误（退出 2），提示先修正或迁移队列。
  不静默忽略，不先锁存后失败。`retired` / `suspended` 项不因这项检查被纳入。
- **R8 说明限度（新增，采纳建议）**：规格写明本规则只把过期 `scheduled` 计入**阈值**；低于阈值时它们仍在 M9 列为
  `unreachable`，可手动 `ky resume` 重排（无锁存时 `ky resume` 也会处理它们）。
- **R9 resume 提示（采纳建议，限新条件）**：`ky resume`（含 `--dry-run`）**仅当**有 `scheduled → queued` 的项时，文本多打印一行
  "其中 N 项由 scheduled 转为 queued"；JSON 若要体现，只能在该条件下出现，且不得暗示整个队列都已转为 `queued`。无此类项时输出不变。

## 请重点审

1. M1–M3 是否被正确吸收；R4 的"仅新条件多一行"是否足以消除误读，又不破坏 R5。
2. R7 的检查位置：`record` / `submit` / `resume` 现在在写入前是否已经跑了会拒绝停用科目项的校验（如果已经拒绝，R7 只需要测试证明，不需要新代码）——请核实并写明。
3. M15 按日期查询端口的准确名字与规格文件（`contracts/projection_status.md` 是否就是它）。
4. 还有没有别处按"逾期 = queued && due < D"统计（例如 `ky/schedule/state_snapshot.py`、`ky/projection/`、`ky/planner/`），需要一并改或明确不改。

## 规则

只读，不跑全量；结论 PASS / FAIL（针对细则），分"必须改 / 建议改 / 不改"。

## 报告

`review/rounds/round-187-d11-scheduled-rules-v2-review-codex.md`。
