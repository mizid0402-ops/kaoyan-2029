# 任务书：WP-G1 测试缺资源时跳过 + 数据文件行尾归一（M22 / 数据写入工具；审查项 C1、C3）

先读仓库根 `AGENTS.md`，再读：`docs/阶段2.5-接缝收口.md` §六（基线）与 C1 / C3 两行、`docs/模块拆分与架构审查.md` C1 / C3 条目、`tests/test_data_manifest.py`、
`tests/contract/test_topic_weights_port.py` 的 `test_write_bytes_match_fixed_baseline`、`tools/aggregate_topic_weights.py`、`tools/apply_knowledge_weights.py`。

你在 worktree `F:\workspace\kaoyan-wt-g1`（分支 `stage25/g1`）里工作，只改这个目录。**本轮例外（AGENTS.md 开头的约定）：验收需要在干净克隆上跑一次全量**，见"验收"。

## 为什么做

1. **C1**：本机全量基线长期"只有 2 项已知失败"——两项都读 `%TEMP%\kaoyan-probe` 下早已被系统清掉的 PDF；干净克隆（没有 gitignore 的 `data/raw_materials/`）会有更多用例因缺资源而**失败**。
   目标：缺外部资源的用例**跳过并写明缺什么**，不再失败；这样"全绿"才有意义，回归判断不必再人工剔除已知失败。
2. **C3**：`.gitattributes` 为 `* -text`；54 个数据文件 index 为 LF、本机工作区为 CRLF（`git ls-files --eol` 可见），原因是部分写入工具在 Windows 用文本模式写。
   同一份数据在不同机器字节不同，哈希与对照会漂。目标：**仓库里的数据文件一律 LF，写入工具显式写 LF**。

## 决策者已定的设计（照做；有更好的写法先在报告里提，不要自行改设计）

### 1. 缺资源跳过（C1）

- 新增一个小的测试辅助（例如 `tests/_resources.py`，公开函数 `require_path(testcase_or_none, path, why)` 或装饰器），资源不存在时 `skipTest` / `skipUnless`，原因写明**缺哪个路径、从哪里取**（例如"按 `data/materials.yaml` 重取"）。
- 找出所有依赖以下资源的用例并接上它：`data/raw_materials/` 下的文件、`%TEMP%` / 系统临时目录里预置的探针文件、本机特定绝对路径。**只改"读不到资源就失败"的那一步**，不改断言内容。
- 环境变量 `KY_REQUIRE_RESOURCES=1` 时把这些跳过变回失败（给以后要严格校验资料完整性的场景用）；缺省为跳过。写进 `tests/_resources.py` 的 docstring。
- 不新建目录分层、不搬测试文件（unit / data / env 三层作为命名约定写进报告的"建议"，本包不做搬迁）。

### 2. 行尾归一（C3）

- 规范：仓库跟踪的数据文本文件（`data/` 与 `review/attach-audit/` 下被 `git ls-files --eol` 标为 `w/crlf` 的那些）一律 **LF**。
- 这 54 个文件的 index 本来就是 LF；**你的 worktree 是按 index 检出的，里面它们已经是 LF**（请用 `git ls-files --eol` 确认并写进报告）。主仓库工作区的 CRLF 由决策者合并后按 index 字节还原，你不用处理。**不改任何数据内容**。
- 找出写这些文件的工具（至少 `tools/aggregate_topic_weights.py`、`tools/apply_knowledge_weights.py`，其余用 `rg` 找写 `data/` 的调用），改为**显式写 LF**（字节写入或 `newline="\n"`）。
  **这是对 `AGENTS.md` 第 11 条的明文例外**：这些工具的输出在 Windows 上由 CRLF 变为 LF，其余字节必须不变。
  - `test_write_bytes_match_fixed_baseline`（`8f31a05` 基线）改为：两边输出各自把 `\r\n` 换成 `\n` 后按字节比较——**只放过换行这一种差异**，并断言当前工具输出不含 `\r`。
  - `tools/aggregate_topic_weights.py` 里 sol 96 加的 `os.linesep` 注释改写为新规范的理由（引用 C3 / WP-G1）。
- 新增守护测试（放 `tests/test_data_manifest.py` 或新文件）：`git ls-files` 列出的 `data/` 下文本文件（按扩展名 `.json .yaml .yml .md .csv .txt`）工作区字节不含 `\r\n`；非 git 环境（归档）跳过。
- 若有测试或登记数据记录了这些文件的 sha256（例如投影、清单测试），核对它们记的是 LF 字节；如果记的是本机 CRLF 字节，在报告里列出，**不要**自行改登记哈希，由决策者决定。

## 不做的

- 不整理 `tools/` 目录（G2）、不拆大函数（G3）、不碰 `Claude outputs/`、`review/` 下用户自己的教材目录（用户的未跟踪目录）。
- 不改 `.gitattributes`（改成 `text eol=lf` 会让 git 在检出时转换，属另一种方案，写进"建议"即可）。

## 验收

1. 定向：`py -3.12 -m unittest tests.test_data_manifest tests.contract.test_topic_weights_port tests.test_eng1_vocabulary tests.test_round24_weighted_tree`（后两个是原来的 2 项已知失败，现应为跳过并写明原因）。
2. **本轮例外的全量**：在系统临时目录做一个干净克隆（`git clone F:\workspace\kaoyan-wt-g1 <临时目录>`；你的改动先在分支上临时提交或用 `git stash`/补丁带过去，报告里写清做法；**不要把临时提交留在分支上**——做完用 `git reset --soft` 还原为未提交状态），
   在克隆里跑 `py -3.12 -m unittest discover -s tests -t .`，目标 **0 失败 0 错误**（跳过数与原因汇总写进报告）。只跑这一次；不要在 worktree 里跑全量。

## 报告

`review/rounds/round-115-wp-g1-luna.md`（写在 worktree 里）：接上跳过的用例清单（文件、用例、缺的资源）；归一的文件统计与前后 `--eol` 对比；改了哪些写入工具；干净克隆全量结果（`Ran` 行、跳过汇总）；登记哈希核对结果；建议。
写"全量：已在干净克隆按本轮例外跑一次"。不提交。含中文的文件只用 `apply_patch` 编辑，写完查 `???`。
