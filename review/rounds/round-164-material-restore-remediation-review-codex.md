# M1 资料重取端口定点复审：PASS

## 上轮必须改项

- **M1 已解决。** 系统临时目录只在 `_restore_missing` 的实际下载路径创建。
  独立探针把 `TemporaryDirectory` 设为抛 `OSError("TEMP unwritable")`，
  `check_only=True` 仍返回 `needs_download`，未调用网络、未创建原始资料目录。
- **M2 已解决。** `urlsplit` 的 `ValueError` 转为本条 `invalid_url`；同时要求
  HTTP(S) URL 有主机名。用 `https://[broken` 后接有效条目，得到
  `[invalid_url, restored]`，后者正常落盘，前者没有目标文件。
- **M3 已解决。** `_download` 捕获 `HTTPException`，包括 `IncompleteRead`。
  中断响应后接有效条目得到 `[download_failed, restored]`，中断条目没有目标
  文件，后续条目正常落盘。

## 验证与结论

- `py -3.12 -B -m unittest tests.contract.test_material_restore_port`：7 项通过。
- 三个原失败探针在系统临时目录中重放，结果如上。
- 只读复审；未改源码、未联网、未跑全量测试。

**PASS。** 上轮三项阻断问题均有可复现证据闭环，未发现这些修复引入的直接回归。
上轮报告中的越界 junction / 符号链接路径问题仍按 `AGENTS.md` 威胁模型作安全登记，
不影响本次门禁结论。
