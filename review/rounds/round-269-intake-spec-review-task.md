# 第 269 轮任务书：学完入队（M32）+ 标记坏题 规格**初检**（gpt-6.1-sol，续 sol61-m17）

## 背景

用户问"没学过怎么判断设置对不对"时，决策者发现：系统没有"学完一个知识点 → 入复习队列"的入口；改编题也没有"标记坏题"。用户选先补这两个缺口再试运行。

## 只做初检（用户 2026-10-01）

只审规格本身，不写代码、不跑测试；必须改附反例；其他一行进"留给最终大检查"；报告约 40 行。范围：

1. `contracts/review_intake.md`（新，M32）全文：校验顺序与"一条都不写"、`review_id` 规则、新项字段与现有 `ReviewItem` 校验（`ky/models.py`）及 `ReviewShardStore.write()` 是否兼容、空队列首次写入、`--leaves-under`。
2. `contracts/question_bank.md` §6a（停用文件、取题跳过、全部停用的处理、与 §5 "向上查找"组的关系）。

## 输出

`F:\workspace\kaoyan-ai-system\review\rounds\round-269-intake-spec-review-sol61.md`：PASS / FAIL；必须改；留给最终大检查。

## 禁止

不联网；只写这一份报告；不改其他文件；不读 `data/personal/` 与 gitignore 的学习状态。
