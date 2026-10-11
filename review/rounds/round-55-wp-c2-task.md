# Round 55 任务书：WP-C2 复习次数不设上限（D8′）+ 自评两档（D9）

你是实现者，在独立 worktree（分支 `stage25/wp-c2`，基于 master `aa78883`）。先读仓库根 `AGENTS.md`，再读 `docs/阶段2.5-接缝收口.md` §七 的 **D8′、D9**（用户决议，已定）。
主工作区另有会话在改 `ky/knowledge/`、`ky/projection/`、`ky/schedule/state_snapshot.py`、`tools/`——**这些文件你一律不碰**。

## 1. D8′：每次复习都计算，同一条记录只算一次（M10 / M13）

- **撤销** D8：删除"每项每完成日最多推进一次""同日不同结果冲突""早于上次即跳过"的逻辑与规格段落。
- 每条完成记录有稳定的 `completion_id`：完成事件条目可显式写 `completion_id`（字符串）；未写时取 `"{event.day}#{index}"`（一个完成日只有一个完成事件文件，所以唯一）。
- 队列存储记住已计算过的 `completion_id`，**与队列在同一次提交里原子写入**：建议放进分片 manifest（`review_shards` 的 manifest 新增字段，schema 版本 +1；
  旧 manifest 没有该字段时视为空集）。再次遇到已记录的 ID → 报告 `replayed`，不推进、不写。
- 比上次更早的完成记录（补录）**照样计算**：按到达顺序作用在当前状态上；`last_reviewed_on = max(旧值, completed_on)`，不倒退；报告里标为 `late`（仍算推进）。
- `day-plan record --review-store`：写入前预检只保留"未知 review_id"与"事件内重复 completion_id"两类错误。
- `contracts/review_progress.md` 删掉 D8 段，写 D8′；`ReviewQueueAdvanceReport` 字段按新语义调整（`advanced` / `replayed` / `late`）。

## 2. D9：自评两档（M8 配置 + M10 算法）

- 考试配置（`ky/models.py` 的 `KaoyanConfig`）新增**可选**段 `review_policy: {self_rating_mode: strict | lenient}`，缺省 `strict`；未知值 → `ContractError`。
- 算法按档位处理**未核对**（`check: none`）的完成：
  - `strict`：现状（不改 phase / ease / interval，按当前间隔顺延）。
  - `lenient`：自评 `unknown`（不会）→ `interval_days = 1`；`vague`（模糊）→ `interval_days = max(1, interval_days // 2)`；二者都**不改** phase、ease、repetitions、**不计 lapse**。
    自评 `basic` / `fluent`（基本会 / 熟练）或无自评 → 同 strict（**绝不拉长**），并在推进结果里标记 `needs_check = True`，由上层去出题（见 M24，另一个会话在做，本轮不接入）。
- 有核对结果的完成：两档完全相同（现状）。
- `ReviewAlgorithm` 端口：档位作为算法的构造参数或 `advance()` 的输入（在规格里写清），`LadderSm2Algorithm(self_rating_mode=...)`。
- 规格 `contracts/review_progress.md` 增加 D9 一节（表格：两档 × 自评四档 × 有无核对）。四档自评的英文取值以代码现有 `VALID_SELF_RATINGS` 为准。

## 3. 测试

- `tests/contract/test_review_progress_port.py`：**两档共同底线**——任何自评在任何档位下都不会让 `interval_days` 或 `due_date` 超过"不带自评的同一完成"的结果；
  strict 下四档自评结果相同；lenient 下 unknown / vague 按上表缩短、basic / fluent 与 strict 相同且 `needs_check`。
- D8′：同日两次不同完成都推进；同一 `completion_id` 重放不推进；补录（更早日期）推进且 `last_reviewed_on` 不倒退；进程在写 manifest 前中断（用 mock 让写入抛错）时，队列与已计算 ID 集都不变。
- 配置：`review_policy` 缺省为 strict、非法值被拒。
- 期望值从被测对象推导，不写数据字面量。

## 验收

在本 worktree：`py -3.12 -m unittest tests.test_completion tests.test_review_queue_advance tests.test_day_plan_store tests.test_storage tests.test_contracts tests.test_cli tests.contract.test_review_progress_port tests.test_review_scheduler`。
全量不跑。无 `???`。报告 `review/rounds/round-55-wp-c2-luna.md`（`apply_patch`）。不提交。
