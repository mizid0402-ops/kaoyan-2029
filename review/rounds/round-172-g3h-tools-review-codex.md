# 第 172 轮评审：G3c S1 收尾与 WP-G3h

## 结论

- **G3c S1：PASS。** `_snapshot_build` 已删除，`snapshot_main` 直接调用 `build_snapshot`；固定基线与成功/失败输出均通过。
- **WP-G3h：FAIL。** 八个已拆工具在可运行输入上未见新旧输出差异，但新增对照测试在规定的干净归档中失败；README 列为 `validation` 的两支长校验器仍未处理。

评审只纳入 `ky/__main__.py`、`tests/test_cli_split_baseline.py`、八个改动工具及 `tests/test_tools_split_baseline.py`。`ky/schedule/`、存储、台账、冻结、采集等并行包未纳入结论。用 `git archive 24371ee` 建两份系统临时树，新实现仅复制本轮 11 个文件；两树补相同原始资料和 `products` 空目录。全量：未跑（按 AGENTS.md）。

## 必须改

### G3h-M1：对照测试依赖未归档的登记产物，干净归档下失败

位置：`tests/test_tools_split_baseline.py` 的 `test_html_extraction_matches_products_and_argument_failure` 与 `test_verifier_and_report_tools_match_fixed_baseline`。`git archive 24371ee` 没有登记的 `review/408知识点树与真题` 目录（`git ls-files` 对该目录返回 0 个文件），而注册表把 `products.cs408_lecture_workspace` 指向它。HTML 场景虽将最终输出重定向到临时目录，仍先调用原 `_configure_workspace`，要求登记目录存在；验证器场景直接读取其 `questions/questions_index.json`。两处都没有为缺资源调用 `tests._resources.require_path`，也没有构造所需的临时登记产物。

复现：在只补原始资料与空 `products` 的临时归档中，设 `GIT_DIR=<主库 .git>`、`PYTHONDONTWRITEBYTECODE=1`，运行 `py -3.12 -m unittest tests.test_tools_split_baseline`。实测 `Ran 5 tests`、`FAILED (failures=2, skipped=1)`；上述两场景均 exit 1，旧/新 traceback 分别包含旧/新脚本行号，三元组断言失败。直接运行旧、新 HTML 脚本也都报 `products.cs408_lecture_workspace: registered directory does not exist`。把工作区已有的 330 个登记产物文件复制到**两份临时树**后，只重跑该模块，结果 `Ran 5 tests ... OK (skipped=1)`。因此这不是已拆代码的内容回归，却使要求的固定基线门禁不能从提交的文件独立运行。

请让 HTML 成功测试在临时注册表/目录中准备所需的空产物根；验证器成功测试应先构造可验证的临时产物，或在确实依赖外部登记产物时用 `require_path` 标明缺失路径与恢复来源并跳过。不能把缺产物触发的 traceback 比较当作成功/失败行为对照。

### G3h-M2：按 README 状态扫描，仍有两支 `validation` 校验器超过 D7 长度界

位置：`tools/round24_validate_weighted_tree.py::validate`、`tools/round29_validate_agreement.py::validate`。任务书要求按 `tools/README.md` 状态扫描 `active`、`validation`、`acquisition`，并拆出超过约 60 行的函数；README 将这两支明确列为 `validation`，其中 round29 还校验当前登记的 supplementary tree / agreement。它们虽以 `round*` 命名，却不是 README 标注的 `pinned_reproducer`。任务书的逐名清单遗漏它们，与“按状态判断”不一致；不能仅凭文件名前缀默认为历史重放生成器。

复现：对 README 中状态为上述三类的脚本逐个 `ast.parse`，用 `end_lineno - lineno + 1` 计函数长度。实测改动后的八个脚本没有超过 60 行的函数；仅剩 `round24_validate_weighted_tree.py::validate = 76` 行、`round29_validate_agreement.py::validate = 78` 行。两文件 `git status --short -- tools` 均无改动。请按 README 状态补拆并固定基线对照；若决策者认定它们应归历史范围，先明确修改分类与任务边界，尤其说明 round29 当前登记附表的校验由谁承担。

## 建议改

**S1：记录两个旧版就有的异常路径，另包决定契约。** `probe_exam_pdf.py --url http://127.0.0.1:1/unreachable.pdf` 在旧/新均 exit 1 并打印 `requests.exceptions.ConnectionError` traceback；堆栈行号、辅助函数帧和连接对象地址使 stderr 不可能作为稳定基线。`extract_exam_skeleton.py --pdf <有效 PDF> --json <仓库根外的绝对路径>` 在旧/新均先写 JSON，再于 `out.relative_to(ROOT)` 抛 `ValueError` traceback。两项均非本轮拆分引入；若要修正常使用下的网络/输出路径错误，应在明确允许改变旧输出的独立任务中制定契约。本轮把它们与已确认的重构回归分开。

## 不改：已验证的基线、职责和字节输出

### 固定基线与 S1

`tests/test_tools_split_baseline.py` 固定 `BASELINE = "24371ee"`，对八脚本共九个旧长函数作 AST 长度下界断言；`CliG3cRemainderSplitBaselineTests` 固定 `baseline_commit = "24371ee"`，对 CLI 的六个旧长函数逐个断言。均通过 `git show 24371ee:<文件>` 取旧实现，没有以 `HEAD` 作基线。若提交后改用 `HEAD`，长度断言将读到拆短的新版而失败；当前固定提交满足 `AGENTS.md` 第 12a 条。

第 167 轮临时快照与当前 `ky/__main__.py` 的差异只有删除 `_snapshot_build` 和将其调用改为直接 `build_snapshot(...)`；`tests/test_cli_split_baseline.py` 与第 167 轮字节相同。`snapshot_main` 旧提交 90 行、当前 42 行。临时归档运行 `py -3.12 -m unittest tests.test_cli_split_baseline.CliG3cRemainderSplitBaselineTests`：2 项 OK；另独立重放 `snapshot-success` 得旧新 `(0, stdout 1094 字节, stderr 0)`、`snapshot-missing-config` 得 `(2, stdout 0, stderr 118 字节)`，两组三元组原始字节相同。

### 工具逐文件行数与拆分职责

以下为亲自对旧/新归档做的 AST 扫描；文件总行数含空行和注释。新辅助各承担内容提取、校验、报告计算、读取、打印或下载等实际步骤，没有只转发参数的辅助。

| 脚本 | 文件总行数旧→新 | 主目标函数旧→新 | 新版最大函数 |
| --- | ---: | --- | ---: |
| `render_weight_manual.py` | 301→308 | `section_cs408` 66→8 | 56 |
| `extract_408_questions_from_html.py` | 638→658 | `_extract_question` 62→42；`_build_extraction_report` 62→43 | 53 |
| `verify_eng1_vocabulary.py` | 249→264 | `verify_database` 132→18 | 60 |
| `verify_netem_source.py` | 208→233 | `verify_database` 83→54 | 58 |
| `netem_cross_validate.py` | 129→154 | `main` 71→11 | 56 |
| `verify_408_question_extraction.py` | 336→355 | `_verify_records` 69→14 | 60 |
| `extract_exam_skeleton.py` | 138→146 | `main` 84→38 | 38 |
| `probe_exam_pdf.py` | 119→146 | `main` 81→50 | 50 |

`git status --short -- tools` 只列上述八个脚本；`tools/README.md` 未改，`pinned_reproducer`、`migration`、`archived`、`retired` 脚本均未改。M2 说明两支 `round*` 校验器的状态与文件名前缀冲突应如何裁定。

### 输出实测

- **权重说明书：**两版分别从同一登记输入生成完整 `--out` Markdown，均 exit 0，stdout/stderr 原始字节相同；文件均为 12,671 字节，SHA-256 均为 `daab438c0389beeb4f2450a8745ad6e9a717e0f9d1aef30ff2a9002e673f664b`。与归档中的登记 `docs/知识点权重说明书.md`（12,672 字节）逐行比较，只有第 3 行的运行时提交标记/日期不同（临时归档无 `.git`，生成器写“未知”）；第 4 行起章节、汇总、表格及正文原始字节相同。旧版也产生同一差异；没有用归一化代替旧新原始字节比较。
- **408 HTML 提取：**补登记产物目录后，旧/新 CLI 成功路径均 exit 0，打印 `records=188 deck_units=116` 及四个年度提取汇总，stdout/stderr 相同。两版写后的完整登记产物树各 330 个文件，每个相对路径及文件原始字节相同；其中生成的题目文本、题目索引、提取报告、deck 映射均逐文件比较。与工作区已登记版本存在旧版也有的行尾/报告字段差异，未当作本轮回归。
- **NETEM 报告：**独立运行两版 `netem_cross_validate.py`，stdout/stderr 相同，完整 23 行报告逐字节相同，文件 2,167 字节，SHA-256 为 `289cb0d3623425b2ad3546246264648963589e5b60d3a6b4ab88c242d51a6a72`。
- **其余工具：**`extract_exam_skeleton.py --pdf <单页空 PDF> --head 0 --json <归档内临时路径>` 两版 exit 0、stdout 306 字节、stderr 0、JSON 257 字节且原始字节相同；`verify_netem_source.py` 登记数据库两版 exit 0、stdout 88 字节；`verify_408_question_extraction.py` 在补齐登记产物后两版 exit 0、stdout 297 字节；`verify_eng1_vocabulary.py` 缺数据库两版 exit 1、stdout 139 字节，登记数据库但缺来源 PDF 两版 exit 1、stdout 3,538 字节；以上 stderr 均空且各组三元组字节相同。`probe_exam_pdf.py --name missing-url.pdf` 两版 exit 2、stdout 0、stderr 177 字节且相同；新增测试中的本地 HTTP 有效 PDF / 非 PDF 场景亦通过。

`verify_eng1_vocabulary.py` 的**成功路径未验证**：其 `source_paths()` 要求的第一份外部文件是 `C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\claude2\dl\bv_e1_2024.pdf`；`tests._resources.require_path` 将该场景明确标成 skipped，不能计作成功通过。补产物后的 `py -3.12 -m unittest tests.test_tools_split_baseline` 为 `Ran 5 tests ... OK (skipped=1)`。

## 安全登记

本轮未发现需按恶意输入、手工篡改内部文件或精确竞态新增登记的安全问题。上述缺产物的门禁失败与旧有网络/路径异常均属于普通资源和参数路径，不归入安全登记。
