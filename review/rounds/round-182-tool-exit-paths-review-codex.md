# 第 182 轮评审：工具异常路径契约式退出

## 结论

**FAIL。** 两处目标逻辑在新测试所设环境中工作，仓库内 `--json` 与 `e318a54` 逐字节一致，原固定基线测试也通过；但 `probe_exam_pdf.py` 的新测试专门过滤了 `requests` 警告。本机不设该过滤的日常命令在连接失败时向 stderr 打出三行，违反任务书的“stderr 恰为一行”。

范围仅为 `git diff e318a54 -- tools/probe_exam_pdf.py tools/extract_exam_skeleton.py` 与新增 `tests/test_tool_exit_paths.py`。用 `git archive e318a54` 展开系统临时树，只复制这三个待审文件；测试、独立探针和变异均在临时树运行。全量：未跑（按 AGENTS.md）。

## 必须改

### M1：真实 CLI 的请求失败 stderr 仍有两行依赖警告

位置：`probe_exam_pdf.py::_download_pdf` 内的 `import requests` 先触发本机 `RequestsDependencyWarning`；新测试在子进程环境设置 `PYTHONWARNINGS="ignore::Warning:requests"`，因而没有检测实际 CLI 输出。捕获 `RequestException` 后的应用错误行正确，但整个 stderr 不符合本轮要求。

复现：在临时归档中用 `socket.bind(("127.0.0.1", 0))` 取得端口后立即关闭，清除 `PYTHONWARNINGS`，设置 `NO_PROXY=no_proxy=127.0.0.1,localhost`，运行 `py -3.12 tools/probe_exam_pdf.py --url http://127.0.0.1:<关闭端口>/unreachable.pdf --name real-stderr-review182.pdf`。实测退出 **1**、stdout `b''`、目标文件不存在，但 stderr 是三行：

```text
...\site-packages\requests\__init__.py:113: RequestsDependencyWarning: urllib3 (2.2.2) or chardet (7.6.0)/charset_normalizer (3.3.2) doesn't match a supported version!
  warnings.warn(
download failed: http://127.0.0.1:<关闭端口>/unreachable.pdf (ConnectionError)
```

请先让新测试不通过环境变量隐藏这类实际 stderr，再用明确、局部的方式保证请求失败只输出契约行，或由决策者明确调整“一行”契约。不要扩大 `except` 到非 `RequestException`。这不是恶意输入：本机现有 Python 依赖组合与普通断网/地址错误就能触发。

## 建议改

无。

## 不改

- **请求异常捕获范围正确。** 只在临时探针中把 `requests.get` 分别改为抛 `Timeout`、`ConnectionError`、`TooManyRedirects`、`ProxyError`、`HTTPError`：每次 `main()` 均返回 1，stdout 空，应用 stderr 只有 `download failed: https://example.invalid/x.pdf (<类名>)`，目标文件不存在，未包含异常对象地址。改为抛普通 `ValueError` 时该异常向外传播，未被吞。以上模拟请求未联网；实际新测试只访问关闭的 loopback 端口，在其警告过滤环境中 `Ran 2 tests ... OK`。
- **HTTP 状态与代理没有新回归。** 本地 HTTP 服务器返回 `404` 和文本 `404 not found`，旧新脚本在相同输入下均退出 1、打印 `NOT a PDF payload — stopping here`、暂存相同字节，完整 `(退出码, stdout, stderr, 文件字节)` 相等。代码仍未对状态码调用 `raise_for_status()`；若 `requests.get` 因代理抛 `ProxyError`，上面的模拟证明它走契约失败行。代理返回的 HTTP 响应则沿用旧内容检查路径。
- **仓库外 JSON 的限定变更。** 用临时单页 PDF、仓库外绝对 `--json` 路径重放 `e318a54` 旧版与新版：两版写出的 JSON 原始字节相同（本次 237 字节）；旧版随后 `ValueError`、exit 1，新版 exit 0、stderr 空、stdout 末行打印输出文件绝对路径。新增测试逐字段核对 JSON，单跑为 `ok`。
- **仓库内 JSON 逐字节不变。** 同一单页 PDF 与归档内绝对 `--json` 路径，旧新分别运行后比较 `(退出码, stdout, stderr, JSON 原始字节)`：完全相等，均 exit 0、stdout 304 字节、stderr 0，JSON SHA-256 均为 `f0c043bef20eb5846d5b4fde00c12db5f38ce3cee0176361cf3617fba98d65ed`；stdout 末行仍为相对路径 `index (structure only, no content) -> <归档内相对路径>`。
- **其它固定基线路径及撤修复验证。** `tests/test_tools_split_baseline.py` 相对 `e318a54` 未改；干净归档运行该模块为 `Ran 12 tests in 12.941s`、`OK (skipped=4)`，其中本地 PDF / 非 PDF、skeleton 无 `--json` 成功与缺 PDF 路径实际通过，跳过项均为缺外部资料或登记产物。`tests.test_tools_catalog` 为 `Ran 1 test ... OK`。只在临时副本把 `except requests.RequestException` 改成 `except ValueError`，probe 新测试在 stderr 精确比较处 `FAILED (failures=1)`；把 skeleton 的 `out.is_relative_to(ROOT)` 条件强制为真，外部 JSON 新测试在退出码断言处 `FAILED (failures=1)`。两次均从待审工作区重复制脚本，临时副本哈希恢复一致，且设置 `PYTHONDONTWRITEBYTECODE=1`。

## 安全登记

本轮未发现需按恶意输入、手工篡改内部文件或精确竞态新增登记的问题。M1 是正常环境中的命令输出不符，按日常问题列入必须改。
