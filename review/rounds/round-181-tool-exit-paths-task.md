# 任务书：两条旧异常路径改为契约式退出（sol 172 建议 S1，窗口 `luna-a` 续做）

先读 `review/rounds/round-172-g3h-tools-review-codex.md` 的"建议改 S1"与 `AGENTS.md`
（"迁移 / 重构不得改变输出"第 11–13 条、"评审严重度"）。两个脚本都是你在 G3h 里拆过的。

本轮**有意改变输出**，但只限下面两条路径；两个脚本的其它所有路径输出必须逐字节不变。

## 要改

### 1. `tools/probe_exam_pdf.py`：下载失败不再抛 traceback

现状：`--url` 连不上（连接拒绝、DNS 失败、超时、重定向过多等）时，`requests.get` 抛出的异常直接变成 traceback，
退出码 1；stderr 含行号与对象地址，不稳定。断网或网址写错是日常会碰到的情况。

改为：`_download_pdf` 里只捕获 `requests.RequestException`（不要吞别的异常），然后：
- 向 **stderr** 打印一行：`download failed: <url> (<异常类名>)`，例如
  `download failed: http://127.0.0.1:1/x.pdf (ConnectionError)`。**不要**把异常对象的 `str()` 打出来（含对象地址，不稳定）。
- 退出码 **1**（与"NOT a PDF payload"同级：运行期失败；2 留给参数错误）。
- **不写**目标文件（下载失败时 staging 下不得出现 `--name` 指定的文件；`STAGE` 目录本身已存在或被建出都可以）。
- stdout 为空。

用"有名字的辅助 + 返回值 / 小异常类"表达失败均可，照文件现有风格选一种，`main` 保持在 60 行以内。

### 2. `tools/extract_exam_skeleton.py`：`--json` 指向仓库外时不再先写后崩

现状：`--json <仓库外绝对路径>` 时 JSON 已正确写出，随后 `out.relative_to(ROOT)` 抛 `ValueError` traceback，退出 1。

改为：打印那一行时，仓库内的路径照旧打印相对路径，仓库外的打印绝对路径——与同一函数里
`"pdf"` 字段 `pdf.relative_to(ROOT).as_posix() if pdf.is_relative_to(ROOT) else str(pdf)` 的写法一致。
退出码 0。仓库内 `--json` 的输出逐字节不变。

## 测试

新增 `tests/test_tool_exit_paths.py`，只覆盖这两条：

- probe：起一个本地必然连不上的地址（例如绑定后立即关闭的本地端口），断言退出码 1、stdout 为空、
  stderr 恰为上面那一行、staging 下没有生成 `--name` 文件。**不联网**。用临时 `--name`，测试后清理。
- skeleton：用测试里现生成的单页 PDF（参照 `tests/test_tools_split_baseline.py::_pdf_bytes`，可以复制那几行，
  不要 import 那个测试模块的私有名），`--json` 指向系统临时目录（仓库外），断言退出码 0、JSON 文件内容正确、
  stdout 末行是 `index (structure only, no content) -> <该绝对路径>`、stderr 为空。

**回归守护**：`tests/test_tools_split_baseline.py` 把这两个脚本的其它成功 / 失败路径与固定基线 `24371ee`
逐字节比较，**必须原样通过、不许改**。若它有场景恰好覆盖了上面两条被改的路径，停下来在报告里说明，不要自己改那个测试。

## 撤实现验证

分别撤掉两处修复（probe 的捕获、skeleton 的仓库外分支），设 `PYTHONDONTWRITEBYTECODE=1` 并清 `__pycache__`，
确认新测试对应用例变红；报告写实际命令与结果，然后恢复。

## 不做的

- 不改其它错误路径、其它脚本、`tools/README.md`、`ky/`、`data/`。
- 不处理 `--name` 含路径分隔符 / 绝对路径的情况（畸形输入，不在本轮；若你认为有日常风险，写进报告"建议"）。
- 不跑全量。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.test_tool_exit_paths tests.test_tools_split_baseline tests.test_tools_catalog
```

## 报告

`review/rounds/round-181-tool-exit-paths-luna.md`：两处各改了什么（附改前 / 改后的实际输出原文）、
新测试覆盖、撤实现验证的命令与结果、验收输出原文。写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。
不提交。含中文只用 `apply_patch`，写完查 `???`。
