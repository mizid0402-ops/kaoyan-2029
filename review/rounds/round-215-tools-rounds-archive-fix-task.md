# 任务书：技术债包 C 返工 —— sol61 第 214 轮 M1 / M2 / m1 / m2（窗口 `luna-b` 续做）

报告 `review/rounds/round-214-tools-rounds-archive-review-sol61.md`，先读全文。纯移动、规则、测试断言、目录表都已确认成立，**不要动**。

## 要改

1. **M1**：`tools/validate_weighted_tree.py`、`tools/validate_supplementary_agreement.py` 直接作为脚本运行（仓库根目录下 `py -3.12 tools/<文件>`）在 import `ky` 时崩溃。
   照现有活动工具的做法，在 import `ky` 之前把仓库根加入 `sys.path`（并保留库模块需要的 `tools` 路径）。
   **加一条测试守住真实入口**：在 `tests/test_tool_exit_paths.py` 里用子进程、**不设 `PYTHONPATH`**、cwd 为仓库根，分别运行两个校验器的 `--help`（agreement 若无 `--help` 就跑其正常命令），断言退出 0、无 traceback。
2. **M2**：`tools/archive/round24_build_weighted_tree.py`、`tools/archive/round29_build_tree_split.py` 的 `ROOT` 按新层级改回**仓库根**（`parents[2]`），保持原输入 / 输出路径含义；
   修好它们对活动库模块与同为归档的 round24 builder 的 import。`tools/archive/round22_verify.py` 显式从归档的 `round22_extract` 读取历史路径常量。
   验证：新进程、不设 `PYTHONPATH`，`runpy.run_path(<文件绝对路径>, run_name='review_load')` 只加载不运行 main，三个都成功（照 sol 214 的方法；再对 `ab56529` 的原文件做同样加载作对比）。
   把这个"只加载"检查也写成一条测试（放 `tests/test_tools_catalog.py` 或 `tests/test_tool_exit_paths.py`，你定），覆盖 `tools/archive/` 下被本轮改过 import 的全部脚本。
3. **m1**：`round22_verify.py` 同时从归档 `round22_extract` 导入 `HTML`（它调用了 `extract_2026(HTML)`）。
4. **m2**：`tools/README.md` 给两个校验器写可复制的完整命令，写明 `--tree` 为必填。

## 不做的

不改校验规则、输出文字、退出码；不重跑历史构建；不改 `ky/`；不跑全量。临时文件放系统临时目录。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.test_tools_catalog tests.test_tool_exit_paths tests.test_round24_weighted_tree tests.test_round29_quote_locate tests.test_round29_tree_split
```

另外贴出：两条直接启动命令的实际输出；三个归档脚本只加载检查的结果（新 / 旧对比）。

## 报告

`review/rounds/round-215-tools-rounds-archive-fix-luna.md`。写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。含中文只用 `apply_patch`，写完查 `???`。
