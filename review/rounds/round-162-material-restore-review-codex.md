# M1 资料重取端口独立评审：FAIL

## 范围与验证

检查 `contracts/material_restore.md`、`ky/acquisition/ledger_restore.py`、
`tools/fetch_all_from_ledger.py`、`tests/contract/test_material_restore_port.py`，以及
工具说明和模块地图的 M1 登记。只运行新契约测试模块（5 项通过）和系统临时目录中的
定向探针；没有真实联网、修改仓库源码或运行全量测试。

## 必须改

### M1：`--check` 仍依赖可写的系统临时目录

- **严重度：MAJOR。位置：** `restore_materials` 一进入函数就执行
  `with tempfile.TemporaryDirectory(...)`，包括 `check_only=True` 分支。
- **触发与实测：** 让临时目录创建抛 `OSError("TEMP unwritable")`，传入一条缺失的
  有效本地资料并设置 `check_only=True`；函数直接抛 `OSError`，既没有返回
  `needs_download`，也没有逐项结果。此时网络回调无需调用，目标目录也不存在。
- **预期：** `--check` 不创建临时文件或目录；在系统临时目录不可写时仍能完成
  只读检查。仅真正下载时才分配暂存位置。
- **回归测试：** 在 `check_only=True` 下把 `TemporaryDirectory` 替换为会报错的
  回调，断言仍返回 `needs_download` 且无网络、无写入。

### M2：畸形但可登记的 URL 中断整批结果

- **严重度：MAJOR。位置：** `restore_materials` 的
  `urlsplit(storage.url).scheme`，位于单条结果的错误处理之外。
- **触发与实测：** `storage.url="https://[broken"` 可通过现有 M2 台账校验；
  以该条和随后一条有效资料调用 `restore_materials`，`urlsplit` 抛
  `ValueError("Invalid IPv6 URL")`，函数没有返回，后续条目没有处理。
- **预期：** 该条返回 `invalid_url`，后续条目照常处理。无主机名的 HTTP(S)
  URL 也应归入 `invalid_url`，不能到下载时才报 `download_failed`。
- **回归测试：** 畸形 URL 与正常后续条目组合，断言每条都有结果且后者能恢复。

### M3：下载流中断时未隔离 `IncompleteRead`

- **严重度：MAJOR。位置：** `_download` 仅捕获 `HTTPError`、`OSError`、
  `ValueError`；`http.client.IncompleteRead` 属于 `HTTPException`，不是
  `OSError`。
- **触发与实测：** 注入一个 HTTP 200 响应，其 `read()` 抛
  `IncompleteRead(b"", 4)`；`restore_materials` 原样抛该异常，后续资料未处理。
- **预期：** 该条返回 `download_failed`，无目标文件落盘，并继续处理后续条目。
- **回归测试：** 模拟中途断流后紧跟一条正常响应，断言两条状态与目标文件。

## 已确认行为

- 正常缺文件且下载字节大小、SHA-256 均正确时，通过同卷临时文件和
  `os.link` 发布；已有正确文件只核验，已有错误文件不覆盖。
- HTTP 非 200、错误哈希、超额字节和一般 `OSError` 在现有 5 项契约测试中
  未产生目标文件；后续条目在这些受控错误下继续处理。
- 路径检查会把目标解析到 `materials.raw_root` 下；目标越界返回
  `invalid_path`。CLI 从注册表和台账决定条目、目标及 URL，`provenance.source_url`
  不充当下载回退地址。模块地图与工具说明同目前实现一致。

## 安全登记

`_target` 只确认目标在解析后的 `raw_root` 内，未再确认 `raw_root` 本身解析后位于
工作区根内；CLI 也未调用 `Workspace.require("materials.raw_root")`。需人为放置
越界 junction / 符号链接才会使表面上位于工作区内的登记目录解析到外部，依
`AGENTS.md` 威胁模型记为安全项，本轮不作阻断。

## 门禁结论

**FAIL。** M1–M3 都是日常环境或手写输入下可达的错误路径，违反只读检查或
逐项错误隔离承诺。修复后只需定点复审这三项及直接回归。
