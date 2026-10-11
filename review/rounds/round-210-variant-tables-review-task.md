# 评审任务书：技术债包 B —— 变体表整表迁移（第 209 轮，窗口 `sol61-main`，续你第 208 轮）

请复审 `luna-a` 第 209 轮：任务书 `review/rounds/round-209-variant-tables-task.md`（决策者把 R2 改为"整表迁移"），报告 `review/rounds/round-209-variant-tables-luna.md`，
你上一轮 `review/rounds/round-208-baseline-harness-gaps2-review-sol61.md`。范围：`tests/contract/test_config_port.py`、`tests/test_contracts.py`、`tests/contract/test_workspace.py`、`tests/_fixtures.py` 的第 209 轮改动。

## 重点看

1. 三张表的生成器与 `f52b8f6` 原生成器逐项一致（输入构造没改），期望取自原 `expected_success`，不是现跑抄结果。
2. 被退役的 103 个变体是否确实都是**多错误组合**（首错次序探针）；有没有单错误变体被误归入退役。你第 208 轮 R2-a/b/c 列出的每个具体变体，现在是否都在表里并按原期望断言。
3. 报告称原比较器对单错误变体没有固定 `ContractError.path` 期望——核对属实与否。
4. 第 207 轮被删的三个零散方法确实被整表覆盖。
5. 自己在临时 `ky/` 副本里再做一处变异（与实现者不同的字段）确认新表变红。

**若本轮 PASS，包 B 即可提交**：请在结论里同时确认你第 204、206、208 轮的全部必须改项都已关闭。

## 规则

只跑与结论直接相关的单个模块或单条命令，**不跑全量**；复现用系统临时目录。结论 PASS / FAIL，分"必须改 / 建议改 / 不改"。

## 报告

`review/rounds/round-210-variant-tables-review-sol61.md`。
