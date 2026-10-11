# 评审任务书：技术债包 B 返工（第 205 轮，窗口 `sol61-main`，续你第 204 轮）

请复审 `luna-a` 第 205 轮：任务书 `review/rounds/round-205-baseline-harness-gaps-task.md`，报告 `review/rounds/round-205-baseline-harness-gaps-luna.md`，
你上一轮 `review/rounds/round-204-baseline-harness-review-sol61.md`。范围：`git diff f52b8f6 -- tests` 中第 205 轮新增 / 修改的部分。

## 重点看

1. M1–M5：新测试的输入与期望是否确实照 `f52b8f6` 里的原输入 / 原期望（逐条对照），不依赖旧版，且你第 204 轮给出的 M1、M3 变异现在会让它们变红。
2. M2 的故障注入：替换 `_latch_freeze_if_needed` / `advance_review_queue` 的方式在子进程里确实生效（不是注入失败后测试恰好通过）。
3. 实现者自查新增的 4 个 CLI 场景（`route show --revision 0`、`snapshot` 缺配置、review-queue check / migrate）是否是真缺口、断言是否恰当。
4. 被删 8 个文件里还有没有你第 204 轮未抽到、而本轮自查也漏掉的独一份现有行为断言——请把第 204 轮"不改与去向抽查"之外剩下的条目再扫一遍。
5. 实现者报告称变异探针曾放在 `review/rounds/` 下、运行后删除：确认仓库里没有遗留。

## 规则

只跑与结论直接相关的单个模块或单条命令，**不跑全量**；复现用系统临时目录。结论 PASS / FAIL，分"必须改 / 建议改 / 不改"。

## 报告

`review/rounds/round-206-baseline-harness-gaps-review-sol61.md`。
