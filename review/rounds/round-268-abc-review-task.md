# 第 268 轮任务书：A + B + C 与 M31 改编题库 实现**初检**（gpt-6.1-sol，续 sol61-m17）

## 只做初检（用户 2026-10-01）

- 只核对三个包是否落实规格与你第 264 轮的 M1–M6；每项最多 1 个合成探针；不通读全部代码、不找新测试缺口、不评视觉。
- 日常会算错 / 崩溃 / 选错题的写"必须改"（附输入），其他一行进"留给最终大检查"。报告约 60 行。

## 范围（主仓库未提交改动）

- 包 C（luna-b 265）：`data/structured_materials/math1/knowledge_tree.yaml` 与 report、`ky/knowledge/tree_grammar.py`、`tests/test_data_manifest.py`；报告 `review/rounds/round-265-math1-items-luna.md`。
  抽查 3 条：一条错字修正（`math1.pr.ch21.requirements.item-03`）、一条确认变更（`math1.pr.ch15.requirements.item-03`）、一条普通条目，quote_ref 能否在各自来源定位。
- 题库（luna-a 266）：`ky/question_bank/`、`ky/review/check_questions.py`（`ancestor_fallback`、`include_details`）、`ky/__main__.py` 三个新命令、`ky/workspace.py`、`prompts/adapted_questions.md`；
  报告 `round-266-question-bank-luna.md`。重点：取题顺序（第三题能轮到）、每题一文件只写一次、无真题覆盖 `basis: syllabus`、非叶子可生成、`review-questions` 按档位给改编题 / 真题。
- 掌握度第二版（luna-c 267）：`ky/mastery/port.py`、`ky/schedule/planning.py`（路线 v4 `targets`）、`ky/pacing/port.py`、`ky/charts/`；报告 `round-267-mastery-v2-luna.md`。
  重点：真题门槛、阶段目标插值、无 targets 的路线字节不变。
- 规格：`contracts/question_bank.md`、`contracts/mastery.md`、`contracts/route_plan.md` 末节、`contracts/charts.md` §8、`contracts/workspace.md`。

## 验证

只跑：

```
py -3.12 -m unittest tests.contract.test_question_bank_port tests.contract.test_mastery_port tests.contract.test_route_plan_port
```

外加探针（系统临时目录，`PYTHONDONTWRITEBYTECODE=1`）。不跑全量。

## 输出

`F:\workspace\kaoyan-ai-system\review\rounds\round-268-abc-review-sol61.md`：PASS / FAIL；必须改；留给最终大检查。

## 禁止

不联网；只写这一份报告；不改其他文件；不读 `data/personal/`、`outputs/` 与 gitignore 的学习状态（可读 `data/raw_materials/transcripts/` 核对 C）。
