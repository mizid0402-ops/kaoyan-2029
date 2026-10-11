# 第 216 轮：技术债包 C 返工复审（sol61-main）

结论：**PASS，包 C 可提交。** 第 214 轮 M1、M2、m1、m2 全部关闭。

已读第 215 轮任务书、实现报告、第 214 轮评审及 AGENTS.md，应用 code-review-gate。
本轮限定入口、归档加载与路径、README 和新增测试；对此前通过的规则与断言作定点复核。
未修改实现或测试、未提交；仓库内仅新增本报告。全量未跑。

## 必须改

无。

## 建议改

无新增项。此前 m1 / m2 已落实。

## 不改：修复核验

### M1：真实脚本入口

独立子进程删除环境变量 PYTHONPATH，cwd 为仓库根，运行以下命令；没有依赖 unittest 的
父进程导入环境。两者退出码均为 0，stderr 均为空。

```powershell
py -3.12 -B tools/validate_weighted_tree.py --help
py -3.12 -B tools/validate_supplementary_agreement.py
```

实际 stdout：

```text
usage: validate_weighted_tree.py [-h] --tree TREE

Validate a CS408 weighted tree

options:
  -h, --help   show this help message and exit
  --tree TREE
```

```text
VALID: 410 agreement entries, 0 errors
```

410 是当前登记数据的实测输出，不是新增的固定数量断言。
两个入口均先把 ROOT 和 ROOT/tools 加入 sys.path，再 import ky.workspace。
新增正式方法 `ToolExitPathTests.test_tree_validators_start_without_pythonpath` 在当前工作区
执行通过（1 test，1.434s），确实覆盖上述两个入口并检查退出码、无 traceback。

### M2：归档加载及原路径含义

重新用 `git archive ab56529 tools` 解包旧版到系统临时目录。新旧各在独立子进程、无
PYTHONPATH 的环境下执行 `runpy.run_path(绝对路径, run_name='review_load')`，不执行 main。

| 当前文件（tools/archive/ 下） | ab56529 的对应文件 | 旧 / 新退出码 | 路径核对 |
|---|---|---|---|
| round24_build_weighted_tree.py | tools/round24_build_weighted_tree.py | 0 / 0 | ROOT 为各自 checkout 根；全部全局 Path 常量含义一致 |
| round29_build_tree_split.py | tools/round29_build_tree_split.py | 0 / 0 | ROOT 为各自 checkout 根；全部全局 Path 常量含义一致 |
| round22_verify.py | tools/archive/round22_verify.py | 0 / 0 | PDF、OUT 与旧版一致；HTML 来自归档 extractor |

路径比较只把各自 checkout 根替换为 CHECKOUT 标记；其余相对路径和机器临时路径原样比较。
round24 的 SOURCE_A_PATH、SOURCE_B_PATH、BASELINE_TREE_PATH、OUT_TREE_PATH、
EVIDENCE_OUT_PATH、SOURCE_C_PATH，以及 round29 的 MAIN_TREE_PATH、AGREEMENT_PATH、
SOURCE_A_PATH、SOURCE_B_RAW_PATH、SOURCE_B_TEXT_PATH、SOURCE_C_PATH 均通过比较。
没有把输入 / 输出文件名或临时目录部分抹掉。

新增正式方法 `ToolsCatalogTests.test_moved_archive_modules_load_in_fresh_process` 在当前
工作区通过（1 test，1.678s）。它覆盖第 215 轮的三个修复对象，子进程逐个加载，无缓存
模块共享；对有 ROOT 的两个 builder 断言其等于当前 checkout。
另复用第 214 轮探针确认 round22_format、round22_extract、round29_quote_locate 也均加载成功，
六个相关归档模块全部退出 0、stderr 为空。未重跑历史构建。

### m1 / m2

`round22_verify.py` 已从 `archive.round22_extract` 同时导入 HTML、PDF；
`extract_2026(HTML)` 的输入为原仓库相对路径
`data/raw_materials/cs408/syllabus/archive408_408_outline_2026.html`，没有未定义名称。

README 已给两个校验器完整的 `py -3.12 tools/...` 命令，weighted 示例带树路径，紧接着
明确说明 --tree 必填。目录一致性正式方法通过（1 test，0.002s）。

## 独立定点变异：两条新增测试均变红

在系统临时 checkout 复制 tools、ky、注册表及 agreement 所需的两份登记文件。
调用仓库现有正式测试方法，仅将测试模块的 ROOT 指向临时 checkout；没有改测试断言、
没有 patch 被测函数。未变异副本中，两条方法均先通过。

| 临时副本源码变异 | 执行的正式方法 | 实测结果 |
|---|---|---|
| 从 validate_weighted_tree.py 删除 `sys.path.insert(0, str(ROOT))` | test_tree_validators_start_without_pythonpath | FAILED (failures=1)，weighted 子场景退出 1，ModuleNotFoundError: No module named 'ky'；agreement 子场景仍通过 |
| 恢复上一变异，再将归档 round24 builder 的 ROOT 从 parents[2] 改回 parents[1] | test_moved_archive_modules_load_in_fresh_process | FAILED (failures=1)，round24 子场景退出 1，ModuleNotFoundError: No module named 'cs408_outline_extract' |

这两次失败来自正式测试的退出码断言，说明测试能挡住原入口 / 根路径回归。
第一份探针在测试已正确变红后，因额外搜索错误文字时未处理 unittest 对 bytes 的引号转义，
自身证据检查失败；读取原 stderr 核实后用后续脚本完成检查与第二次变异。
这不是测试假通过，也没有因此修改仓库测试。

## 第 214 轮已通过部分的定点复核

复用第 214 轮固定 ab56529 探针，当前结果仍为：

- helper 的 key、clean_display、keymap、locate_quote、HTML 提取及 flatten 同输入字节一致。
- weighted 校验原树及 approved + 空 sources 场景，错误列表及 main 输出字节一致；
  原始来源文件读取阶段仍按前轮探针隔离，不声称完整历史 PDF 重放。
- agreement 成功及 source_support=0.42 错误场景，错误列表、退出码和 stdout / stderr 字节一致。
- quote helper 和 agreement 全部函数 AST 相同；outline / weighted 的差异函数集合仍只有
  第 214 轮已确认的显式路径、局部变量及 CLI 适配部分。
- test_round24_weighted_tree、test_round29_quote_locate、test_round29_tree_split 的所有
  assert 语句与 assert* 调用 AST 仍与固定基线逐项相同。

`git diff --check -- tools tests` 通过。没有重跑实现者的五模块验收或全量测试。

## 安全登记

无新增项。

## 复现与证据

系统临时脚本：

```powershell
py -3.12 -B "$env:TEMP/round216_probe.py"
py -3.12 -B "$env:TEMP/round216_mutation_continue.py"
py -3.12 -B "$env:TEMP/round214_probe.py"
py -3.12 -B -m unittest tests.test_tools_catalog.ToolsCatalogTests.test_catalog_matches_tracked_tool_directories
```

第一份脚本保留上述证据检查失败，后续脚本使用其临时副本与 stderr 完成变异验证。
证据目录：

```text
C:\Users\Lenovo\AppData\Local\Temp\round216-sol61-_kxlqrhv
C:\Users\Lenovo\AppData\Local\Temp\round214-sol61-77pru3ya
```

第一个目录保存两条直接命令的 stdout / stderr、三对新旧加载和路径值、正式测试正常执行、
两次变异的 stdout / stderr，以及旧版解包和临时源码副本。
临时探针未写入仓库；包 C 可提交。
