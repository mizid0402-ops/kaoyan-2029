# 第 183 轮：tool exit paths 修正

## M1

仅更新 `tests/test_tool_exit_paths.py`。保留带
`PYTHONWARNINGS=ignore::Warning:requests` 的精确 stderr 断言，并注明这是为了隔离
导入 `requests` 时由本机依赖版本组合发出的环境警告；无过滤子场景负责验证该警告仍原样
通过。工具实现没有压制警告，也没有改动。

新增 `test_probe_connection_failure_passes_through_environment_warning`：子进程环境显式清除
继承的 `PYTHONWARNINGS`，访问刚关闭的 loopback 端口，不联网。断言退出码为 1、stdout 为空、
目标文件不存在、stderr 不含 `Traceback`，契约行是最后一个非空行且仅出现一次；不从 stderr
中过滤警告行。

### 撤实现验证

临时移除 `tools/probe_exam_pdf.py` 中的 `except requests.RequestException`，设置
`PYTHONDONTWRITEBYTECODE=1` 并清理 `tools/`、`tests/` 下的 `.pyc` 后运行：

```text
py -3.12 -m unittest tests.test_tool_exit_paths.ToolExitPathTests.test_probe_connection_failure_passes_through_environment_warning
```

结果：`FAILED (failures=1)`；新增用例在 `tests/test_tool_exit_paths.py` 的
`assertNotIn("Traceback", stderr)` 处失败，观测到 `Traceback`。恢复捕获后
`tools/probe_exam_pdf.py` SHA-256 为
`0218A9A64F279ABE5EADA690A189667F445163C0819FFEF0BB16EA1C90E1D7C2`，与变异前一致。

### 验收

实际运行：

```text
py -3.12 -m unittest tests.test_tool_exit_paths tests.test_tools_split_baseline
```

原始输出：

```text
...s........s..
----------------------------------------------------------------------
Ran 15 tests in 23.548s

OK (skipped=2)
```

两个跳过来自固定基线测试里登记产物或原始资料缺失时的 `require_path` 场景；恢复提示
分别指向运行 `tools/extract_408_questions_from_html.py` 生成登记产物，以及从 acquisition
source 恢复登记的英语真题 PDF。其余不依赖这些资料的对照均运行。

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。
