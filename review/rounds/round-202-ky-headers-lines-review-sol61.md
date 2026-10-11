# 第 202 轮：技术债包 D 独立评审（sol61-main）

结论：**PASS**。必须改：无。建议改：1 条报告说明。不改：见下文四项。

范围仅为 `git diff f52b8f6 -- ky` 的 12 个已有文件与新增
`ky/exam/__init__.py`。基线完整哈希为
`f52b8f6f2a6145e86970844278acf197184597d9`。未评审包 B 的 `tests/` 改动，
未修改实现或测试，未提交。已读 AGENTS.md、201 轮任务书与报告、技术债清单相关条目和 §9、
模块地图；按 code-review-gate 区分阻断缺陷与非阻断建议。

## 必须改

无。未发现本包引入的正常使用下行为回归、输出变化或规格归属错误。

## 建议改

### m1：实现报告注明 M5 是规格覆盖的例外（MINOR，非阻断）

201 轮报告的“25/25 有命中”是正确的文本检索结果，但不能据此理解成
“25 份规格均在自身 `ky/` 实现模块的头部有引用”。

复现输入：

```powershell
git grep -n 'exam_index.md' -- ky
Get-Content -Encoding UTF8 contracts/exam_index.md -TotalCount 5
rg -n 'M5 真题索引' docs/模块地图.md
```

唯一命中为 `ky/projection/__init__.py:36` 的已有注释：它引用索引
`paper_source` 的格式，是消费方引用，不是 M5 实现头。规格首段和模块地图均把 M5 实现指向
`tools/verify_408_index.py` 等工具及 `data/exam_questions/*.json`。
独立解析模块 docstring 后，结果为 24 份规格有头部引用，`exam_index.md` 没有。

建议报告补一句这个例外；不要把 M5 头部硬塞到 M15 投影模块。当前代码没有新添错误归属，
任务书也明确允许没有 `ky/` 实现的规格写明例外，因此不要求代码返工。
报告的 `git grep` 表还不包含未跟踪的新 `exam/__init__.py`；本轮探针已包含它。

## 不改

### N1：全部去 docstring 的 AST 相同；文档值与运行时消费已分别核验

独立探针位于系统临时目录：
`C:\Users\Lenovo\AppData\Local\Temp\round202_sol61_probe.py`。
复现命令：

```powershell
py -3.12 -B C:\Users\Lenovo\AppData\Local\Temp\round202_sol61_probe.py
```

探针对每个已有文件执行 `git show f52b8f6:<路径>`，并另用
`git archive f52b8f6 ky` 解到系统临时目录，断言两种取得方式的源码原始字节相等。
移除 Module / ClassDef / FunctionDef / AsyncFunctionDef 的首个字符串表达式，
比较 `ast.dump(..., include_attributes=False)`；不移除其他字符串或表达式。
新增文件单独断言基线不存在、剥离 docstring 后为完全空的 Module，未把任意 Git 失败当新文件。

| 文件 | 独立 AST 结果 | 文档值变化 |
|---|---|---|
| `ky/__main__.py` | 相同 | 无 |
| `ky/exam/__init__.py` | 新增，只有 docstring | 新包说明 |
| `ky/knowledge/knowledge_point.py` | 相同 | 无 |
| `ky/ledger/citations.py` | 相同 | 仅模块头 |
| `ky/ledger/material.py` | 相同 | 仅模块头 |
| `ky/models.py` | 相同 | 仅模块头 |
| `ky/projection/serve.py` | 相同 | 无 |
| `ky/schedule/completion.py` | 相同 | 无 |
| `ky/schedule/monthly_close.py` | 相同 | 无 |
| `ky/schedule/review_clip.py` | 相同 | 仅模块头 |
| `ky/storage/day_plan_store.py` | 相同 | 仅模块头 |
| `ky/storage/review_shards.py` | 相同 | 无 |
| `ky/workspace.py` | 相同 | 无 |

另外比较了完整文档值，而非仅剥离它们：`ky.__main__.__doc__` 的示例反斜杠续行
没有改变字符串；`MonthClose.utilisation` 的括号内相邻字符串仍被 Python 识别成 docstring，
property 的 `__doc__` 与旧版完全相同。两项均经新旧树真实导入再次断言。

以 `__doc__|getdoc|cleandoc|description=|utilisation` 搜索 `ky/`、`tests/`、`tools/`
的 Python 源码：未发现读取这五处变更模块头的代码。
`tools/` 的 `description=__doc__` 读取各工具自己的未改文档；`ky/` argparse 描述使用
显式字符串。CLI 对 `mc.utilisation` 的读取是属性数值，getter AST 和文档值均未变化。
模块头 `__doc__` 本身的变化属于本任务明文要求的规格说明补充，不能称为所有元数据不变；
它没有进入仓库现有用户输出路径。

原始输出对照使用同一个 Python 3.12 解释器、正常 `-m` 启动方式、相同环境，分别以旧树和
当前工作区为 cwd；清除 PYTHONPATH，设置 PYTHONDONTWRITEBYTECODE，未归一化输出。
结果如下，退出码全部为 0：

| 命令（均加 `py -3.12 -B`） | stdout 字节数（旧=新） | stderr 字节数（旧=新） | 原始字节比较 |
|---|---:|---:|---|
| `-m ky -h` | 805 | 0 | 相同 |
| `-m ky preflight -h` | 1681 | 0 | 相同 |
| `-m ky.projection.serve -h` | 659 | 0 | 相同 |
| `-m ky.storage.review_shards -h` | 181 | 220 | 相同 |

最后一条的 runpy 警告在旧版也存在，stderr 完全相同，不是本包回归。
本轮未声称实跑所有业务命令；未改的执行 AST、文档消费排查与上述字节探针共同支持结论。

### N2：普通包的元数据改变符合任务；现有导入没有破坏

复现输入为上述探针的独立子进程：导入 `ky.exam.paper_shape` 和
`ky.exam.topic_weights`，再分别执行
`importlib.import_module('.paper_shape', 'ky.exam')` / `'.topic_weights'`，
断言绝对与相对导入取得同一对象，并断言模块实际文件来自各自传入的 checkout。

实测差异：旧版 `ky.exam` 的 loader 为 NamespaceLoader，`__file__` 为 None；
新版为 SourceFileLoader，`__file__` 指向新 init。
`pkgutil.iter_modules(ky.__path__)` 新版多发现 `exam`，其余列表相同；
`pkgutil.iter_modules(ky.exam.__path__)` 两侧均发现 `paper_shape`、`topic_weights`。
这些是把命名空间包变为普通包的真实、预期差异，不能说包发现行为完全不变。

仓库中未查到 pkgutil、extend_path、__path__、NamespaceLoader 或
submodule_search_locations 的消费代码；现有工具与测试使用具体子模块导入，
未发现依赖跨路径命名空间合并或旧 loader / file 元数据的调用。
新 init 不 re-export、不运行业务代码，M5′ / M6 归属和指向的公开接口模块正确。

针对真实卷面端口额外运行单个模块：

```text
py -3.12 -B -m unittest tests.contract.test_paper_shape_port
Ran 6 tests in 0.042s
OK
```

### N3：规格归属正确，未把消费方冒充自身实现

对照模块地图逐份检查；下表列自身实现位置，省略附带消费引用。新补的五处均在模块 docstring
中列出正确编号、规格及接口，所列接口实际存在。

| 规格 | 自身实现与模块归属 |
|---|---|
| availability.md | `ky/availability/port.py`，M26 |
| check_questions.md | `ky/review/check_questions.py`，M24 |
| citation_gate.md | `ky/ledger/citations.py`，M3（本轮补） |
| config.md | `ky/models.py`，M8（本轮补） |
| day_plan_store.md | `ky/storage/day_plan_store.py`，M13（本轮补；模型部分 M11） |
| exam_index.md | M5 在 tools / data，见建议 m1 |
| freeze.md | `ky/freeze/port.py`、`resume.py`，M27；存储 M13 |
| knowledge_tree.md | `ky/knowledge/knowledge_point.py`、`hierarchy.py`，M4 |
| learning_state_projection.md | `ky/projection/learning_state.py`，M15 |
| ledger.md | `ky/ledger/material.py`，M2（本轮补） |
| material_restore.md | `ky/acquisition/ledger_restore.py`，M1 |
| paper_shape.md | `ky/exam/paper_shape.py`，M5′；新包头同步引用 |
| planner_port.md | `ky/planner/port.py`，M19；存储 provenance M13 |
| projection.md | `ky/projection/__init__.py`、`learning_state.py`，M15 |
| projection_status.md | `ky/projection/status.py`，M15 |
| review_clip.md | `ky/schedule/review_clip.py`，M9（本轮补） |
| review_progress.md | `ky/schedule/completion.py`，M10；队列推进存储 M13 |
| route_plan.md | `ky/schedule/planning.py`，M11；预算 M8、裁剪 M9、存储 M13 |
| state_snapshot.md | `ky/schedule/state_snapshot.py`，M12 |
| state_sources.md | `ky/storage/` 的 day_plan_store / review_shards / route_store，M13；availability M26 |
| syllabus_mapping.md | `ky/knowledge/syllabus_mapping.py`，M4 |
| syllabus_migration.md | `ky/review/syllabus_migration.py`，M25 |
| topic_weights.md | `ky/exam/topic_weights.py`，M6；新包头同步引用 |
| vocabulary.md | `ky/schedule/vocab_channel.py`，M7 |
| workspace.md | `ky/workspace.py`，M0 |

复现输入：探针末段对全部 contracts/*.md 枚举，分别输出模块头命中与完整源码命中，
包含未跟踪的新 init；将对应路径与 `docs/模块地图.md` 的拼图表逐行对照。

### N4：折行可读性可接受

复现输入：`git diff f52b8f6 -- ky` 与探针对旧 / 新全部 `ky/**/*.py` 的行长统计。
实测超过 100 字符行数为 **55 → 0**，全源码没有连续三个问号的编码损坏标记。
状态转换表按转换与字段拆开，长函数签名按参数分行，异常文字使用相邻字面量拼接，
没有新添嵌套、辅助变量、多步骤单行或额外控制流程。
`review_shards._bucket` 的取哈希 / 切片 / 取模表达式仍是原表达式；只在调用参数边界换行。
CLI 文档示例的显式续行和 utilisation 的字符串表达式写法不如普通三引号常见，
但在硬行宽与保留原文档值两个要求下成立，不构成必须改或再拆函数的理由。

## 证据与验证范围

成功探针的原始帮助输出、stderr 和新旧导入 JSON 保留于：
`C:\Users\Lenovo\AppData\Local\Temp\round202-sol61-bvz0ui41`。
探针退出码 0，打印 `ALL CHECKS PASS`；本报告的测试次数只指独立运行的 6 条卷面端口测试，
不把实现者自报的 218 条计作本轮独立验证。

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。未新增仓库测试，未对包 B 作结论。

## 安全登记

本轮范围内没有新增需要登记的安全问题。
