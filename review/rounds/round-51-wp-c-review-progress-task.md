# Round 51 任务书：WP-C 复习推进端口（M10，决议 D3）

你是实现者，在**独立的 git worktree**（分支 `stage25/wp-c`）里工作；主工作区另有一个 luna 会话在改别的文件，互不影响。
先读仓库根 `AGENTS.md`（全部规则适用：D7 可读性、不写数据字面量、编码、只跑点名模块、输出不变规则）。
依据：`docs/阶段2.5-接缝收口.md` §七 D3、README 硬不变量③、`docs/评审结论与实施契约.md` §4.3。

## 背景

`ky/schedule/completion.py` 现在用完成事件里的 `quality`（0–5，**自评**）决定间隔、ease 和到期日。
硬不变量③：自评不能改到期日、不能提高质量分。用户决议 D3（选 a）：**复习完成只认有锚点的核对结果**。

## 要做的

1. **规格 `contracts/review_progress.md`**（先写）：
   - 完成事件 schema_version **2** 的复习条目：`review_id`、`completed_on`、`check`（`past_question` 真题 / `exercise` 练习题 / `recall_vs_notes` 默写后对照 / `none` 未核对）、
     `outcome`（`correct` / `partial` / `incorrect`；`check=none` 时必须缺省）、可选 `question_ref`（字符串，如 `cs408-2023-1`）、可选 `self_rating`（四档，只记录）。
   - **推进规则**：`check ≠ none` → 按固定映射 `correct→4, partial→3, incorrect→1` 得到推进用质量分，走现有阶梯 + SM-2（阶梯与公式不变）；
     `check = none`（纯自评）→ 记为"做过"：**不改 phase、ease、repetitions、lapses、interval_days**，`due_date = completed_on + 当前 interval_days`，`last_reviewed_on` 更新。
     `self_rating` 的取值对结果**没有任何影响**（严格版：自评"不会"也不缩短）。
   - **旧事件（schema_version 1，带 `quality`）**：仍可解析（历史记录写一次、不可改）；推进时一律按 `check = none` 处理——自评分不再有推进权。在规格里写明这是有意的语义变更及理由（D3）。
   - `ReviewAlgorithm` 端口：`advance(item, completion) -> ReviewItem` 的 Protocol，映射表是它的一部分；默认实现 = 现有阶梯 + SM-2 + 上述映射。替换者（如将来换 FSRS）只实现这个 Protocol。
2. **实现**：`ky/schedule/completion.py`——`ReviewCompletion` 改为 `check` / `outcome` / `question_ref` / `self_rating`（保留读取 v1 的路径）；抽出 `ReviewAlgorithm` Protocol 与默认实现；`advance_review_item` 委托给默认实现（保持函数名，调用方不用改）。
   `ky/storage/day_plan_store.py` 的幂等判断（第 284–340 行附近，现按 `review_id + completed_on + quality`）改为按新字段；`ky/__main__.py` 的 `day-plan record` 不需要改接口，确认能读 v2。
3. **测试**：
   - 改 `tests/test_completion.py`、`tests/test_review_queue_advance.py`、`tests/test_day_plan_store.py`、`tests/test_monthly_close.py` 中构造 `ReviewCompletion` 的地方。
   - 新增 `tests/contract/test_review_progress_port.py`（以算法实现为参数，`ALGORITHMS = [DefaultReviewAlgorithm()]`）：
     **不变量③守护**——对同一复习项，`check=none` 时遍历全部 `self_rating` 取值，结果完全相同且 phase/ease/interval 不变；
     有核对时三种 outcome 的推进方向正确（correct/partial 推进、incorrect 重置为 1 天并计 lapse）；v1 旧事件按未核对处理；`due_date > completed_on` 恒成立。
   - 期望值从被测对象推导，不写与数据版本相关的字面量（阶梯天数来自模块常量）。

## 不做的

- 不改阶梯天数、SM-2 公式、裁剪核（`review_clip.py`）；不改词汇进度（`VocabProgress`）；不动投影、快照、tools、`ky/workspace.py`、`ky/projection/`、`ky/knowledge/`、`ky/models.py`（主工作区正在改这些）。
- 不提交。

## 验收

`py -3.12 -m unittest tests.test_completion tests.test_review_queue_advance tests.test_day_plan_store tests.test_monthly_close tests.test_cli tests.contract.test_review_progress_port`。全量不跑。
写完检查改动文件无 `???`。

## 产物

报告 `review/rounds/round-51-wp-c-luna.md`（用 `apply_patch` 写）：改动、规格要点、每条验收的实际输出摘要、规格歧义、D7 自查（行宽、函数长度）。
