# 第 272 轮任务书：`ky learn`（M32）+ 标记坏题 实现**初检**（gpt-6.1-sol，续 sol61-m17）

## 只做初检（用户 2026-10-01）

- 只核对两包是否落实 `contracts/review_intake.md` 与 `contracts/question_bank.md` §3（序号 01–99、未停用 ≤9）/ §6a，以及你第 269 轮 M1、M2；每项最多 1 个合成探针。
- 日常会入错队、写坏队列、选错题 / 崩溃的写"必须改"（附输入），其他一行进"留给最终大检查"。报告约 40 行。

## 范围（主仓库未提交改动）

- luna-b 270：`ky/review_intake/`、`ky/__main__.py` 的 `learn`、`tests/contract/test_review_intake_port.py`；报告 `review/rounds/round-270-intake-luna.md`。
- luna-a 271：`ky/question_bank/`、`ky/__main__.py` 的 `question-bank retire` / `review-questions`、`tests/contract/test_question_bank_port.py`；报告 `round-271-retire-luna.md`。
- 决策者已在真实工作区跑过 `ky learn --date 2026-10-02 --leaves-under math1.hs.ch01.requirements --dry-run`：列出 10 条、未建队列目录（不必复跑）。

## 验证

只跑 `py -3.12 -m unittest tests.contract.test_review_intake_port tests.contract.test_question_bank_port`，外加探针（系统临时目录，`PYTHONDONTWRITEBYTECODE=1`）。不跑全量。

## 输出

`F:\workspace\kaoyan-ai-system\review\rounds\round-272-intake-review-sol61.md`：PASS / FAIL；必须改；留给最终大检查。

## 禁止

不联网；只写这一份报告；不改其他文件；不读 `data/personal/` 与 gitignore 的学习状态。
