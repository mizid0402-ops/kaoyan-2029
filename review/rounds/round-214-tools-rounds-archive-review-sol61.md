# 第 214 轮：技术债包 C 独立评审（sol61-main）

结论：**FAIL**。函数和校验规则迁移成立，三份测试的断言未变，目录表一致；
但两个活动校验器的常规脚本启动失败，三个归档模块也出现新的加载失败。
需要修复这两组导入 / 根目录适配，不要求修改校验规则或重跑历史构建结果。

范围：`git diff ab56529 -- tools tests` 与新增 tools 文件。固定基线完整哈希为
`ab56529b3fa90244f4febe305338e5414ef197b3`。已读任务书、实现报告及有关技术债规则，
应用 code-review-gate 和 AGENTS.md。未修改实现或测试、未提交；本报告是唯一仓库写入。
全量未跑。

## 必须改

### M1：两个活动校验器直接按脚本启动均在导入阶段崩溃（MAJOR）

位置：`tools/validate_weighted_tree.py:20`、`tools/validate_supplementary_agreement.py:33`。

仓库根目录实际运行：

```powershell
py -3.12 -B tools/validate_weighted_tree.py --help
py -3.12 -B tools/validate_supplementary_agreement.py
```

均退出 1，stderr 为 traceback，最后一行为：

```text
ModuleNotFoundError: No module named 'ky'
```

新增 `from ky.workspace import load_workspace` 位于 ROOT / sys.path 引导之前；
后面的引导还只加入 ROOT/tools，没有加入仓库 ROOT。
直接执行文件时 sys.path 的脚本目录是 tools，无法据此找到其同级 ky。
测试提前加入仓库根或通过 unittest 导入模块，掩盖了真实入口的问题。

这不是允许的“weighted CLI 必填 --tree”变化：连 --help 都尚未进入 argparse，
agreement 的正常命令也没有读到注册表。属于日常运行的新增 traceback。
修法：照现有活动工具，在导入 ky 前确定并加入仓库根；保留库工具所需 tools 路径。
复验两条直接启动命令，不能仅从已有导入环境调用 main。

### M2：归档后的根目录 / 同级导入适配断链（MAJOR）

| 文件 | 新失败及原因 |
|---|---|
| tools/archive/round24_build_weighted_tree.py | ROOT 仍为 parents[1]，现在得到仓库/tools，插入 tools/tools；新进程仅加载时找不到 cs408_outline_extract。 |
| tools/archive/round29_build_tree_split.py | 同样 ROOT 错位，且 from archive import round24_build_weighted_tree 找不到 archive 包。 |
| tools/archive/round22_verify.py | 只插入仓库/tools 后仍使用裸 from round22_extract import PDF；原顶层文件已删除，新位置位于 archive，按文件加载时找不到它。 |

可复现：在系统临时目录的新进程中，不设置 PYTHONPATH，使用
`runpy.run_path(<上述绝对文件路径>, run_name='review_load')`，只加载、不运行 main。
前两项分别报 No module named cs408_outline_extract / archive，第三项报
No module named round22_extract。

独立从 `git archive ab56529 tools` 检出到系统临时目录，对原两个顶层 builder 和原
archive/round22_verify.py 做完全相同的只加载操作：**三个全部成功**。
因此不是历史原材料缺失造成的旧问题，而是本轮移动 / import 适配引入的回归。

在已有 tools 导入环境下，两个 builder 虽能导入，ROOT 也实测为
`F:\workspace\kaoyan-ai-system\tools`，使源码 / 输出路径从仓库/data 变成 tools/data。
这还会令 ReproducibilityTest 的 require_path 检查错误位置；报告不能把由此产生的 skip
一律归为历史资料缺失。

修法：两个新归档 builder 按新的目录层级恢复仓库根，保持原输入 / 输出路径的含义；
verify 显式从归档模块读取其历史路径常量。归档之间依赖允许，不需要活动代码反向依赖归档。
只要求按原方式加载和路径保持，不要求重新生成历史数据。

## 建议改

### m1：verify 的机械调用适配还缺 HTML 来源（MINOR）

`tools/archive/round22_verify.py` 新增 `extract_2026(HTML)`，但文件只 import PDF，
没有定义 / import HTML。即使加载问题修好，执行到该行也会 NameError。
本轮明确不要求归档脚本重跑出结果，不将它单独作为额外阻断；建议在同一机械适配里
从归档 extract 模块导入 HTML，避免这次路径显式化引入未定义变量。

### m2：给新校验命令补一行可复制用法（MINOR）

README 已在 weighted 行标 --tree，但没有完整示例，也没明确写 required。
建议写出 `py -3.12 tools/validate_weighted_tree.py --tree <weighted-tree.yaml>` 和
agreement 的直接命令，方便旧调用者迁移。无需留旧名转发 stub。

## 不改：纯移动与规则核对

| 对照 | 独立结论 |
|---|---|
| round22_extract → cs408_outline_extract | key、clean_display、subject_chunks、flatten、compare 的函数 AST 相同。extract_2022 / extract_2026 的差异仅为显式路径参数及 Path 转换；tree_reverse_check 另有局部变量展开 / 改名。归一化这些明确适配后，计算正文 AST 相同。 |
| round29_quote_locate → cs408_quote_locate | 两个函数及 SourceTextLengthChangedError 类 AST 相同；keymap、定位及长度变化错误的实测结果相同。 |
| weighted validator | 校验辅助函数和 validate 的检查项、调用顺序、消息 AST 未变。load_doc 去掉固定默认；alias provenance 从 doc.sources_registry.B.path 取源路径；main 加必填 --tree。这些是本任务明确允许的路径 / 调用变化。 |
| agreement validator | 全部函数 AST 相同。路径全局值改从 supplementary.cs408_multisource.files 取；当前注册表得到的 tree / agreement 与原路径相同。 |
| 三个测试文件 | test_round24_weighted_tree、test_round29_quote_locate、test_round29_tree_split 的每个 assert 语句及 assert* 调用 AST 逐项一致。diff 仅改变 import、load_doc 显式路径及 weighted main 参数。 |
| tree_source_support | 本轮只有指向归档 builder 的 docstring 描述调整，计算代码不变。 |

没有只凭 AST 相同便宣称入口可用：M1 / M2 是实际启动 / 加载探针发现的问题。

## 一次性新旧字节对照

使用 tests._baseline_harness.fixed_source 读取固定 ab56529 的原文件，独立加载旧模块，
与当前活动模块运行同一输入。原代码来自删除前路径，不使用 HEAD。
调用 compare_results 比较 returncode、stdout / stderr 的原始 UTF-8 bytes；
库值 / 错误列表以同一 JSON 编码比较 bytes。

| 实测场景 | 结果 / 限制 |
|---|---|
| key / clean_display / keymap / locate_quote | 包括中文、全角字符、I/O OCR 形式、空串；输出 bytes 相同。ß 的 casefold 长度变化均抛相同消息。 |
| extract_2026 / flatten | 系统临时 HTML 含科目、章节、节、列表条目；实际 HTML 解析结果 bytes 相同。 |
| extract_2022 / compare / tree_reverse_check | 同一临时输入、受控 PdfReader 提供四科章节文本，覆盖提取后的语法与计算；临时树包含命中 / 无命中条目，结果 bytes 相同。这不是历史 PDF 解码重放。 |
| weighted validate / main | 当前加权树原样及 approved+空 sources，错误列表 / 顺序相同；另在临时真实 source-registry 文件上分别验证 CLI 成功 0 与失败 1，stdout / stderr bytes 完全相同。 |
| agreement validate / main | 当前登记文件成功场景、source_support=0.42 的错误场景；错误列表、退出 0 / 1 与 stdout / stderr bytes 相同。 |

历史 PDF 原文件缺失；weighted CLI 对照隔离了 validate_alias_provenance 原文件读取阶段，
不能把以上成功对照说成完整历史源材料重放。该函数的 AST 差异已单独核对为路径参数适配。
没有修改仓库数据，也没有新增常驻迁移对照测试。

## 文档、目录与依赖方向

git grep 旧六个文件名后，README.md 和 docs/模块地图.md 没有旧名命令。
剩余命中主要为 docs/技术债与整改清单.md 的改动前现状、docs/archive 的历史审查记录、
归档脚本内部历史说明和旧测试 docstring。没有发现仍指导用户运行旧两个 validator 的
活动用法文档；历史审计文字应保留，不因文件改名删除。

AST 导入扫描覆盖**当前磁盘中的新增未跟踪文件**及 ky 全部 Python 文件：
活动 tools 顶层和 ky 没有 import archive。归档之间的 import 属允许方向，
M2 要修的是其可加载性。不能只用 git grep 排除新增未跟踪文件后便宣称全通过。

tools/README.md 与实际 tools / migrations / archive Python 目录一致，
`py -3.12 -B -m unittest tests.test_tools_catalog`：1 test，0.002s，OK。
机器路径已留在归档 / migration，README 给新归档条目和 register_round2_sources 加了说明；
两个新库和校验器没有原本的机器缓存常量。

固定历史源码断言也独立执行：
`tests.test_cs408_lecture_pipeline.Cs408LecturePipelineTest.test_outputs_match_pre_migration_templates_with_only_allowed_changes`
为 1 test，1.785s，OK，仍从其固定 PRE_MIGRATION_COMMIT 读取源码。
首次调用误写类名 LecturePipelineTest，只产生 loader error；纠正完整类名后通过，
未把那次调用算作测试缺陷。

## 复现与证据

系统临时脚本均可用 py -3.12 -B 运行：

- `$env:TEMP\round214_probe.py`：库 / validator 字节对照、三份测试断言 AST、归档新进程加载。
- `$env:TEMP\round214_more.py`：明确适配后的正文 AST、受控提取计算、ROOT 值、活动导入扫描与真实脚本启动失败。
- `$env:TEMP\round214_weight_cli.py`：weighted 成功 / 失败两条原始 CLI 字节对照。
- `$env:TEMP\round214_archive_baseline.py`：原基线三个文件的相同只加载操作全部成功。

证据目录分别为：

```text
C:\Users\Lenovo\AppData\Local\Temp\round214-sol61-8inuhvxh
C:\Users\Lenovo\AppData\Local\Temp\round214-more-nme_yoj0
C:\Users\Lenovo\AppData\Local\Temp\round214-cli-hcba0_7m
C:\Users\Lenovo\AppData\Local\Temp\round214-archive-old-9bjrftfd
```

未重跑实现者的 50 条验收，仅运行与结论直接相关的目录模块、单个 pipeline 方法与探针。
git diff --check -- tools tests 通过。全量未跑；无新增安全登记。
