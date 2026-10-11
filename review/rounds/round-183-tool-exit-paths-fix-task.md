# 任务书：第 181 轮返工 —— sol 182 M1（窗口 `luna-a` 续做）

sol 第 182 轮判 **FAIL**，报告 `review/rounds/round-182-tool-exit-paths-review-codex.md`，先读全文。
两个脚本的改动本身已确认正确，**不要改 `tools/`**。只改 `tests/test_tool_exit_paths.py`。

## 决策者裁定（sol 182 M1）

本机 `import requests` 会因依赖版本组合打出 `RequestsDependencyWarning`（两行），这在 probe 的**所有**路径上都出现、
改动前就有，是 Python 环境的输出，不是工具的输出。契约"stderr 恰为一行"指**工具自己**写的内容；
环境在 import 时发出的第三方警告**原样放行**，工具里**不**压制它（压制会隐藏真实的环境问题）。

## 要改

1. 保留测试里只针对 `requests` 模块的警告过滤（`PYTHONWARNINGS=ignore::Warning:requests`）下的"stderr 恰为契约行"断言，
   但在测试里写一句注释说明为什么过滤（环境依赖警告、见本轮裁定），不要写成"为了让测试通过"。
2. **新增**一个不设任何警告过滤的子场景（清掉继承来的 `PYTHONWARNINGS`）：断言退出码 1、stdout 为空、目标文件不存在、
   stderr 不含 `Traceback`、stderr **最后一个非空行**恰为 `download failed: <url> (ConnectionError)`、
   且该契约行在 stderr 中只出现一次。不要按警告文字去逐行剔除 stderr（不从文本倒推结构）。
3. 其它测试不动。

## 撤实现验证

临时撤掉 `probe_exam_pdf.py` 的 `except requests.RequestException`（只在临时副本或事后恢复），确认新增的无过滤子场景变红；
报告写实际命令与结果，恢复后核对哈希。

## 不做的

不改 `tools/`、`ky/`、`data/`；不跑全量。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.test_tool_exit_paths tests.test_tools_split_baseline
```

## 报告

`review/rounds/round-183-tool-exit-paths-fix-luna.md`。写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。
不提交。含中文只用 `apply_patch`，写完查 `???`。
