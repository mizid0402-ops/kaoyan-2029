# Round 51 修复：WP-C（sol 判 FAIL：M1 幂等 / M2 自评排序）

续同一会话，同一 worktree。依据 `review/rounds/round-51-wp-c-review-sol-out.md`（含复现步骤）。遵守 `AGENTS.md`。

## 决策者决议 D8（写进 `contracts/review_progress.md`）

**每个复习项每个完成日最多推进一次。** 队列推进规则：
- `completed_on` 早于该项 `last_reviewed_on` → 跳过，报告为 `out_of_order`，不推进、不改任何字段（旧事件在新事件之后重放属于这种）。
- `completed_on` 等于 `last_reviewed_on` 且推进结果相同（同一核对结果）→ 跳过，报告为 `replayed`。
- `completed_on` 等于 `last_reviewed_on` 但结果不同 → **冲突**，抛 `StorageError`（或专用子类），字段路径指向该条目。
- `ky day-plan record --review-store`：在写入不可覆盖的完成事件**之前**做同样的冲突预检，冲突时 exit 2 且事件与队列都不落盘。
- 规格写明 D8 的理由（间隔复习：同日重复不产生间隔价值）与"核对结果是用户对照答案后的声明，系统信任该声明，`question_ref` 可选"这一信任边界。

## 要做的

1. **M1**：按 D8 改 `ky/storage/day_plan_store.py` 的推进与幂等判断；注释只描述实际判据。回归：sol 的三个复现（旧事件在新事件后重放、同日同质不同引用、同日异质冲突）+ CLI 冲突预检不落盘。
2. **M2**：`last_self_rating` 是**允许更新的排序元数据**：推进时 completion 带 `self_rating` 就写入，不带则保留旧值；它不影响 schedule / due_date / last_quality。
   改规格；契约测试改为断言四档自评下 schedule、due_date、last_quality 相同，另断言 `last_self_rating` 被写入且裁剪核（`select_daily_reviews`）的排序确实读到它。
3. **可读性（sol 建议）**：outcome→质量映射只放在算法里（`LadderSm2Algorithm` 提供 `progress_quality(completion)` 之类的公开方法），`ReviewCompletion` 不再自带映射；队列的判断通过算法取质量。契约测试补 4/3/1 精确映射与一个 SM-2 边界断言。

## 验收

在本 worktree：`py -3.12 -m unittest tests.test_completion tests.test_review_queue_advance tests.test_day_plan_store tests.test_cli tests.contract.test_review_progress_port tests.test_review_scheduler`。全量不跑。无 `???`。
报告追加到 `review/rounds/round-51-wp-c-luna.md` 末尾（"## 修复（sol FAIL 后）"，用 `apply_patch`）。不提交。
