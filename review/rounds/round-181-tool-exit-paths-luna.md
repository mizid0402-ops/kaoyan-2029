# 第 181 轮：两条旧异常路径改为契约式退出

## `probe_exam_pdf.py`：请求失败

`_download_pdf` 只捕获 `requests.RequestException`，并用私有 `_DownloadFailure` 传递异常类名。`main` 在下载汇总输出前把失败写到 stderr 并返回 1；不格式化异常对象，也不写目标文件。参数解析仍由 argparse 返回 2，非 PDF 响应原路径不变。

本机用绑定后关闭的 loopback 端口实测：

```text
改前：exit=1，stdout=b''
stderr 首行：Traceback (most recent call last):
stderr 末行：requests.exceptions.ConnectionError: HTTPConnectionPool(host='127.0.0.1', port=6256): Max retries exceeded with url: /unreachable.pdf (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x000002AC96F53E30>: Failed to establish a new connection: [WinError 10061] 由于目标计算机积极拒绝，无法连接。'))

改后：exit=1，stdout=b''
stderr：download failed: http://127.0.0.1:6793/unreachable.pdf (ConnectionError)\r\n
目标文件存在：False
```

子进程设置 `NO_PROXY` / `no_proxy` 为 loopback，且过滤 `requests` 模块的依赖版本警告，断言 stderr 完全等于契约行及 Windows 行结束符；测试只访问本地关闭端口，不访问互联网。

## `extract_exam_skeleton.py`：仓库外 JSON 路径

JSON 写入后，输出路径标签改为：仓库内沿用相对路径，仓库外使用 `str(out)`。JSON 内容与其他输出保持原逻辑。

以临时单页空 PDF 和系统临时目录输出文件实测：

````text
改前：exit=1，JSON_EXISTS=True
stdout 末尾：duplicate numbers: none
stderr 末尾：ValueError: 'C:\\Users\\Lenovo\\AppData\\Local\\Temp\\tmp9uriezgr\\structure.json' is not in the subpath of 'F:\\workspace\\kaoyan-ai-system'

改后：exit=0，stderr=b''
stdout 末行：index (structure only, no content) -> C:\Users\Lenovo\AppData\Local\Temp\tmp6pnbnzpl\structure.json
JSON：

```json
{
  "pdf": "C:\\Users\\Lenovo\\AppData\\Local\\Temp\\tmp6pnbnzpl\\single-page.pdf",
  "pages": 1,
  "question_start_count": 0,
  "number_range": null,
  "missing_numbers": [],
  "duplicate_numbers": [],
  "sections": [],
  "question_lines": []
}
```
````

改前 traceback 的前置 stdout 为单页统计、空章节、空题号统计；仓库外 JSON 在异常前已经写出。新测试逐字段比较 JSON，并检查最后一行与 stderr。

## 固定基线回归守护

`tests.test_tools_split_baseline` 中的 `probe_exam_pdf.py` 场景覆盖本地 PDF 与非 PDF 响应；`extract_exam_skeleton.py` 场景覆盖无 `--json` 的成功路径和缺失 PDF。没有场景覆盖本轮改变的请求异常或仓库外 JSON 路径，因此未改固定基线测试。其余路径仍固定比较 `24371ee`。

## 撤实现验证

两项均分别撤掉修复，设置 `PYTHONDONTWRITEBYTECODE=1`，清理 `tools/`、`tests/` 下 `__pycache__` 中的 `.pyc` 后运行对应测试。

1. 移除 `_download_pdf` 对 `requests.RequestException` 的捕获：

   ```text
   py -3.12 -m unittest tests.test_tool_exit_paths.ToolExitPathTests.test_probe_connection_failure_is_a_contract_exit
   FAILED (failures=1)
   ```

   测试在 stderr 精确相等断言处变红，实际内容恢复为带 `requests.exceptions.ConnectionError` 的 traceback。恢复后文件 SHA-256 为 `0218A9A64F279ABE5EADA690A189667F445163C0819FFEF0BB16EA1C90E1D7C2`。

2. 移除 `out.is_relative_to(ROOT)` 的仓库外分支，强制调用 `out.relative_to(ROOT)`：

   ```text
   py -3.12 -m unittest tests.test_tool_exit_paths.ToolExitPathTests.test_skeleton_json_outside_repository_uses_absolute_output_path
   FAILED (failures=1)
   ```

   测试在退出码断言处变红，实测返回 1。恢复后文件 SHA-256 为 `F4C90083DC1172C4C35E220F03DBEBAF925AEF3E73F21FD146097EEF8097D4C1`。

以上哈希与撤实现前记录值一致；两条新测试在恢复后通过。

## 验收

实际运行：

```text
py -3.12 -m unittest tests.test_tool_exit_paths tests.test_tools_split_baseline tests.test_tools_catalog
Ran 15 tests in 21.039s
OK (skipped=2)
```

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。

建议：本轮按约定不处理 `--name` 含路径分隔符或绝对路径的输入；若后续支持任意用户输入，可单独明确 staging 目录边界与文件名契约。
