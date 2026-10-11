# 评审任务书：第 190 轮 —— B6 返工（你第 188 轮的 M1 与两条建议，窗口 `sol-main`）

请复审 `luna-b` 第 190 轮。任务书 `review/rounds/round-190-b6-rename-fix-task.md`，实现报告
`review/rounds/round-190-b6-rename-fix-luna.md`，你上一轮报告 `review/rounds/round-188-b6-rename-review-codex.md`。

**本轮范围**：`docs/模块拆分与架构审查.md`、`tests/contract/test_models_split_baseline.py`、`test_availability_port.py`、
`test_planner_port.py`、`test_freeze_port.py` 相对你第 188 轮所见版本的变化；并确认 `ky/`、`contracts/` 与第 188 轮一致。

## 重点看

1. M1：B6 原文与 `d692365` 逐字相同，"已处理"标注在其后，没有删其它文字。
2. 建议 1：名字替换只作用于旧版一侧；用你第 188 轮的变异确认现在会变红。
3. 建议 2：旧版视图只含旧字段；实现者说另加了"非字段属性访问器"（因为执行的旧入口会调用当前辅助函数）——
   判断这个访问器会不会让旧版悄悄读到新名、从而削弱"旧版收到的就是改名前模型"的证明。

## 规则

只跑与结论直接相关的单个模块或单条命令，**不跑全量**；复现用系统临时目录。
结论 PASS / FAIL，分"必须改 / 建议改 / 不改"。

## 报告

`review/rounds/round-191-b6-rename-fix-review-codex.md`。
