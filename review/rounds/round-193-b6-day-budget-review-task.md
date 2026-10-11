# 评审任务书：第 192 轮 —— B6 漏改的 day-budget 基线测试（窗口 `sol-main`）

决策者提交 B6 前的全量发现 `tests/contract/test_day_budget_port.py` 两个 ERROR（固定旧版 `_build_input_data` 收到新 `KaoyanConfig`，
`AttributeError: ... total_daily_minutes`）。`luna-b` 第 192 轮只改了这个文件。任务书 `review/rounds/round-192-b6-day-budget-baseline-task.md`，
报告 `review/rounds/round-192-b6-day-budget-baseline-luna.md`。你在第 191 轮已 PASS 其余 B6 改动。

**本轮范围**：`git diff -- tests/contract/test_day_budget_port.py`。

## 重点看

1. 旧版视图只含旧字段、名字归一化只作用于旧版一侧（与你第 191 轮认可的 `test_planner_port.py` 做法一致）；新版原样比较。
2. 实现者的盘点命令只搜了 `_build_input_data` / `planner_input_data` / `git show`。请**自己**再找一遍：还有哪些测试把**当前**
   `KaoyanConfig`（或当前 `load_config` 的结果）交给**固定旧版**代码（`exec` 旧源码、`git show` 取旧文件后调用），
   漏网的会在全量里以同样的 `AttributeError` 出现——决策者全量只报了这一处，但请用静态检索确认。
3. 自己做一次撤修复变异确认变红。

## 规则

只跑与结论直接相关的单个模块或单条命令，**不跑全量**；复现用系统临时目录。结论 PASS / FAIL，分"必须改 / 建议改 / 不改"。

## 报告

`review/rounds/round-193-b6-day-budget-review-codex.md`。
