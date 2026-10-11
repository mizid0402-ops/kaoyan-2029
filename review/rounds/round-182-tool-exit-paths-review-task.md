# 评审任务书：第 181 轮 —— 两条旧异常路径改为契约式退出（你第 172 轮建议 S1，窗口 `sol-main`）

请评审 `luna-a` 第 181 轮。任务书 `review/rounds/round-181-tool-exit-paths-task.md`，
实现报告 `review/rounds/round-181-tool-exit-paths-luna.md`。

**本轮范围**：`tools/probe_exam_pdf.py`、`tools/extract_exam_skeleton.py`（`git diff e318a54`）与新增
`tests/test_tool_exit_paths.py`。本轮是**有意改变输出**，但只限任务书写明的两条路径。

## 重点看

1. probe：只捕获 `requests.RequestException`，其它异常不被吞；失败时 stderr 恰为一行、不含对象地址、
   退出 1、stdout 空、不写目标文件。超时、DNS 失败等其它 `RequestException` 子类是否同样走这条路径。
2. skeleton：仓库外 `--json` 退出 0、打印绝对路径；仓库内 `--json` 的输出与 `e318a54` 逐字节相同
   （`tests/test_tools_split_baseline.py` 未覆盖仓库内 `--json`，请自己做一次新旧对照）。
3. 两个脚本其它路径与固定基线 `24371ee` 仍逐字节相同（`tests.test_tools_split_baseline` 原样通过、未被改动）。
4. 新测试不联网、在干净归档里能跑；自己做一次撤修复变异确认变红。
5. 这个修法有没有让日常使用里的某种情况变差（例如 HTTP 错误码、代理环境）。

## 规则

只跑与结论直接相关的单个模块或单条命令，**不跑全量**；复现用系统临时目录，不写进仓库。
结论 PASS / FAIL，分"必须改 / 建议改 / 不改"，每条附可复现输入；安全类单列"安全登记"。

## 报告

`review/rounds/round-182-tool-exit-paths-review-codex.md`。
