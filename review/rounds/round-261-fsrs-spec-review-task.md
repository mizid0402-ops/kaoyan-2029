# 第 261 轮任务书：FSRS 接管复习时间 + M30 修订 规格**初检**（gpt-6.1-sol，续 sol61-m17）

## 背景

用户看了第一周模拟实验后，改选"接 FSRS，并且让 FSRS 接管复习时间"。决策者据此写了规格，你第 259 轮的 M1–M3 也已改进 `contracts/mastery.md`。

## 只做初检（用户 2026-10-01）

只审规格本身，不写代码、不跑测试；必须改附反例；其他一行进"留给最终大检查"；报告约 50 行。范围：

1. `contracts/review_progress.md` 末节"FSRS 算法"：开关、参数（按天、无学习步、`maximum_interval=180`、关扰动）、核对→评分映射、`fsrs` 模式字段与合法性、
   阶梯→FSRS 切换、未核对完成、D11 退回起点。重点：**自评能否经任何路径改变 FSRS 记忆状态或拉长间隔**；与现有 `ReviewItem` 校验（`ky/models.py` 的 schedule 校验、`interval_days` 1..180）
   与 M9 裁剪 / D8′ 只算一次 / D11 是否冲突；按 `py-fsrs` 6.x 真实 API（已装在本机：`py -3.12 -c "import fsrs, inspect; ..."` 可查）能否这样还原卡片。
2. `contracts/config.md` §2.3 新键 `algorithm`；`contracts/workspace.md` `features: weighted_mastery`；`contracts/learning_state_projection.md` 新列。
3. `contracts/mastery.md` 第 259 轮 M1–M3 是否已解决，以及 §2 改按 FSRS 稳定度后是否自洽。

## 输出

`F:\workspace\kaoyan-ai-system\review\rounds\round-261-fsrs-spec-review-sol61.md`：PASS / FAIL；必须改；留给最终大检查。

## 禁止

不联网；只写这一份报告；不改其他文件；不读 `data/personal/` 与 gitignore 的学习状态。
