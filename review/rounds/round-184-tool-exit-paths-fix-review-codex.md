# 第 184 轮评审：工具异常路径返工

## 结论

**PASS。** 第 182 轮 M1 所涉“一行”契约已有决策者明确裁定：只计工具自己的输出，导入时第三方发出的环境警告原样放行。第 183 轮仅补测试；实测过滤和无过滤两种环境均满足各自断言，撤掉请求异常捕获后新增用例变红。

范围：`tests/test_tool_exit_paths.py`；另核对两支工具未变化。以 `git archive e318a54` 展开系统临时目录，只复制这三个待审文件后验证，未改仓库源码。全量：未跑（按 AGENTS.md）。

## 必须改

无。

## 建议改

无。接受本轮裁定：导入 `requests` 时发出的依赖版本警告早于工具错误处理，且旧版也会发出；原样放行能保留环境诊断信息。工具仍需保证自己只输出一条契约错误，现有定点测试及独立实跑已证实这一点。

## 不改

- **改动范围与旧版一致性。** 对比第 182 轮留存的临时副本，`tools/probe_exam_pdf.py` SHA-256 均为 `0218A9A64F279ABE5EADA690A189667F445163C0819FFEF0BB16EA1C90E1D7C2`，`tools/extract_exam_skeleton.py` 均为 `F4C90083DC1172C4C35E220F03DBEBAF925AEF3E73F21FD146097EEF8097D4C1`。`tests/test_tool_exit_paths.py` 相比第 182 轮只增加了过滤原因注释及无过滤用例；`tests/test_tools_split_baseline.py` 对 `e318a54` 无改动。
- **过滤场景。** `test_probe_connection_failure_is_a_contract_exit` 在子进程设置 `PYTHONWARNINGS=ignore::Warning:requests`，仅以 `requests` 为模块前缀过滤警告，仍要求 stderr 原始字节恰为一条 `download failed: <url> (ConnectionError)` 加平台换行。注释说明隔离的是导入时的环境警告，并指向下方无过滤场景。以关闭的 `127.0.0.1` 端口为输入，在临时归档运行 `py -3.12 -m unittest tests.test_tool_exit_paths.ToolExitPathTests.test_probe_connection_failure_is_a_contract_exit -v`，结果 `ok`。
- **无过滤场景。** 新增 `test_probe_connection_failure_passes_through_environment_warning` 从子进程环境显式 `pop("PYTHONWARNINGS", None)`，不读取警告文字来剔除 stderr 行。相同关闭端口输入下，它断言 exit 1、stdout `b''`、目标文件不存在、stderr 无 `Traceback`、最后一个非空行恰为契约行，且该行只出现一次。临时归档运行对应单条用例为 `ok`。另以未过滤的独立 CLI 探针实跑，观测 exit 1、stdout `b''`、stderr 共三行：前两行是本机 `RequestsDependencyWarning`，末行 `download failed: http://127.0.0.1:7133/unreachable.pdf (ConnectionError)`；这与裁定一致。
- **撤修复变异。** 仅在临时副本把 `except requests.RequestException as exc:` 换成 `except ValueError as exc:`，设置 `PYTHONDONTWRITEBYTECODE=1`，运行 `py -3.12 -m unittest tests.test_tool_exit_paths.ToolExitPathTests.test_probe_connection_failure_passes_through_environment_warning -v`，结果 `FAILED (failures=1)`：第 91 行 `assertNotIn("Traceback", stderr)` 发现未捕获的 `requests.exceptions.ConnectionError` traceback。恢复临时副本后，探针 SHA-256 回到上述 `0218...D7C2`；临时树未出现 `__pycache__`。
- **相关回归。** 在同一干净归档运行 `py -3.12 -m unittest tests.test_tool_exit_paths tests.test_tools_split_baseline -v`：`Ran 15 tests in 19.831s`、`OK (skipped=4)`。三条本轮异常路径测试和旧固定基线中无需外部资料的用例实际运行；四项因缺原始资料或登记产物而明确跳过，未记作通过。

## 安全登记

本轮未发现需新增登记的恶意输入、手工篡改或精确竞态问题。
