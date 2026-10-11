# 评审任务书：第 183 轮 —— 工具异常路径返工（你第 182 轮 M1，窗口 `sol-main`）

请复审 `luna-a` 第 183 轮。任务书 `review/rounds/round-183-tool-exit-paths-fix-task.md`（含**决策者对 M1 的裁定**：
"stderr 恰为一行"指工具自己的输出；环境在 import 时发出的第三方警告原样放行、工具不压制），
实现报告 `review/rounds/round-183-tool-exit-paths-fix-luna.md`，你上一轮报告 `review/rounds/round-182-tool-exit-paths-review-codex.md`。

**本轮范围**：`tests/test_tool_exit_paths.py`；并确认 `tools/probe_exam_pdf.py`、`tools/extract_exam_skeleton.py`
与你第 182 轮审过的版本相同。

## 重点看

1. 新增无过滤子场景是否真的不隐藏环境警告（继承的 `PYTHONWARNINGS` 被清掉），并按裁定断言：
   无 traceback、契约行为最后一个非空行且只出现一次、退出 1、stdout 空、不写文件。
2. 有过滤的精确断言是否只过滤 `requests` 模块的警告，注释说明了原因。
3. 自己做一次撤修复变异确认无过滤子场景变红。
4. 若你认为裁定本身不合理，写明理由与替代方案（按"建议改"），由决策者转交用户。

## 规则

只跑与结论直接相关的单个模块或单条命令，**不跑全量**；复现用系统临时目录，不写进仓库。
结论 PASS / FAIL，分"必须改 / 建议改 / 不改"，每条附可复现输入；安全类单列"安全登记"。

## 报告

`review/rounds/round-184-tool-exit-paths-fix-review-codex.md`。
