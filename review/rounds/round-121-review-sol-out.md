# Round 121 Codex 独立评审：WP-G1（C1 / C3）

范围：`682d1f4`（含 `f30588d`）、`eec49ae`、`31a25c1`。验证环境为 Windows、`py -3.12`；干净克隆固定在 `31a25c1`，命令为 `git -c core.autocrlf=false clone --no-hardlinks . <系统临时目录>`，检出后本地配置 `core.autocrlf=false`。仅做了一次全量测试；以下其他运行均为单条测试或只读检查。临时克隆在测试和撤回探针后均恢复为干净状态。

## 1. C1：资源跳过

| 项 | 意见 | 证据与可复现输入 |
| --- | --- | --- |
| C1-1：过早跳过卷面格式契约测试 | **必须改** | `tests/contract/test_exam_index_port.py:24-33,54-65,105-112`：所有 `_temporary_workspace()` 用例先复制 2026 索引登记的原始资料，`_copy_file` 对缺失资料调用 `require_path(None, ...)`。因此干净克隆里该类有 **18 个 skip 记录**，包括纯格式错误检查 `test_missing_kind_is_reported`（:299-305）、`test_null_calibration_or_kind_is_rejected`（:307-318）等；这些断言没有走到 `verify`。复现：`py -3.12 -m unittest tests.contract.test_exam_index_port.ExamIndexPortTests.test_missing_kind_is_reported` 得 `skipped=1`；在临时克隆的单测进程里仅令 `_copy_file` 对 `data/raw_materials/` 不预复制、其他复制照旧，同一测试为 `OK`。说明缺资源不是这条断言的必要前提，违反“只在读外部资源那一步跳过”。应把原始资料复制/检查延迟到确实使用答案读取或来源校验的用例；缺资源环境也要运行纯格式断言。`KY_REQUIRE_RESOURCES=1` 使这些用例失败，不能替代默认环境下的有效覆盖。 |
| C1-2：其他跳过路径、跟踪数据 | **不改** | 干净克隆 `git ls-files -z -- data/raw_materials` 为 0 条。全量日志 47 个跳过记录中，46 个由 `missing resource:` 触发：42 个路径在 `data/raw_materials/`，3 个是 `%TEMP%/kaoyan-probe/` 的旧探针，1 个是 gitignore 的 `products.cs408_lecture_workspace`；另 1 个是账户缺少创建 symlink 的权限（junction 用例仍运行）。未见受跟踪的树、索引、台账、权重被当作缺资源跳过。`eec49ae` 的 `tests/contract/test_workspace.py:215-233` 只对白名单 `materials.raw_root`、`products.*` 放宽存在性，其余键仍 `workspace.require`。不过产品目录跳过提示统一说“按 data/materials.yaml 重取原始资料”，恢复指引不准确，见建议。 |
| C1-3：严格开关与撤回探针 | **不改** | `tests/_resources.py:15-30` 在路径缺失时，仅 `KY_REQUIRE_RESOURCES=1` 改抛 `AssertionError`。干净克隆单跑 `tests.test_exam_index.ExamIndexTest.test_hashes_match_the_registered_bytes`：默认 skip；设置该变量后 `FAIL`，报缺失 PDF；`tests.contract.test_workspace.WorkspaceContractTests.test_1_repository_registry` 严格模式产生 raw_root、products 两个失败子用例。另在临时克隆的单测进程中把 `require_path` 置为无操作：前一哈希测试由 skip 变为 `FAIL: rebuilt paper missing`；`tests.test_round24_weighted_tree.WeightedTreeStructureTest.test_real_file_passes_validation` 由 skip 变为 `FAIL`，列出缺少的 A/B 来源。两处撤回均变红。严格开关不影响那个 symlink 权限 skip，因为它不是缺资源跳过。 |
| C1-4：干净克隆验收 | **不改** | 唯一一次 `py -3.12 -m unittest discover -s tests -t . -v`：**`Ran 706 tests in 142.656s`，`OK (skipped=47)`，0 failure / 0 error**。日志抽查覆盖原始 PDF/HTML、`%TEMP%` 探针、产品目录及 symlink 权限。运行测试的子进程退出码为 0；随后汇总脚本打印含中文的日志时遇到本机 GBK 终端编码错误，未改变测试结果。这里的“全绿”须与 C1-1 的无谓跳过一起解读。 |

## 2. C3：LF 与输出对照

| 项 | 意见 | 证据与可复现输入 |
| --- | --- | --- |
| C3-1：24 个工具 diff | **不改** | `git diff 682d1f4^1 682d1f4 -- tools` 逐个核对：`aggregate_topic_weights` 去掉 `os.linesep` 替换；`extract_cs408_bundle` 的 CSV `lineterminator="\n"`；其余写入点增加 `newline="\n"`，伴随必要的调用排版，未见数据计算、筛选、模板文字或台账分支变化。逐个文件为：`aggregate_topic_weights.py`、`apply_knowledge_weights.py`、`apply_round2_fixes.py`、`audit_attachment.py`、`build_408_index.py`、`build_408_index_v2.py`、`build_eng1_tree.py`、`build_evidence_bundle.py`、`build_exam_indexes.py`、`build_math1_tree.py`、`classify_questions.py`、`extract_408_question_text.py`、`extract_408_questions_from_html.py`、`extract_cs408_bundle.py`、`extract_exam_skeleton.py`、`fix_eng1_provenance.py`、`import_netem_source.py`、`register_408_quiz_pages.py`、`register_408_source.py`、`register_round2_sources.py`、`remove_408_reprints.py`、`restore_408_papers.py`、`round24_build_weighted_tree.py`、`round29_build_tree_split.py`。`register_408_quiz_pages.py:146` 的写入仍在原 `if` 内。`data/paper_shapes/cs408.yaml` 提交前后分别有 114 / 0 个 CRLF，双方按 CRLF→LF 归一后原始字节相等。 |
| C3-2：LF 守护范围 | **建议改** | `tests/test_data_manifest.py:25-44` 通过 `git ls-files -z -- data` 取受跟踪文件、筛 `.json/.yaml/.yml/.md/.csv/.txt`、拒绝 CRLF；无 Git 索引时跳过，符合任务书给这条测试的明确范围。干净克隆实数为 `data/` 95 个文本文件，均无 `\r`。不过任务书的 LF 规范还包括 `review/attach-audit/` 的 8 个受跟踪文本文件，守护测试未覆盖。反例：在临时克隆给 `review/attach-audit/context.md` 的首个 LF 注入 CRLF，单跑该守护测试仍 `OK`；恢复后工作区干净。建议把这 8 个路径也纳入守护范围，避免 `tools/audit_attachment.py`、`build_evidence_bundle.py` 将来回退时漏检。当前 8 个文件均为 LF，所以不是现有产物错误。 |
| C3-3：LF 撤回与三处固定基线 | **不改** | 临时克隆将 `data/paper_shapes/cs408.yaml` 首个 LF 改 CRLF，单跑 `tests.test_data_manifest.DataManifestTest.test_tracked_data_text_files_use_lf` 得 `FAILED (failures=1)`，恢复后为 `OK`。`tests/contract/test_topic_weights_port.py:419-438,510-527` 两处对照各自固定 `8f31a05`、`11cda18`，旧/新仅 CRLF→LF 后按字节比较，当前写出另断言无 `\r`；两条单测通过。临时克隆分别把当前两个工具的 `indent=2` 改为 `indent=4`，各自单测都 `FAILED (failures=1)`，恢复后干净。`tests/test_cs408_lecture_pipeline.py:24,243-280` 固定 `762786f`，只给文本扩展名归一 CRLF，其余仍按字节比较；全量中该对照测试通过，且 `:438-467` 已含删去“练习指向”行后必须失败的探针。原有针对补充视图/列的许可变换不是本提交新增。 |
| C3-4：AGENTS 第 11 条例外 | **不改** | `round-115-wp-g1-task.md`“行尾归一”明确允许受跟踪数据文本写出的 Windows CRLF→LF；`AGENTS.md` 第 11 条要求的其他输出字节未获得放宽。本提交的工具 diff 与三处对照仅引入 CRLF 归一，`tests/test_cs408_lecture_pipeline.py:244-248` 对未跟踪产品文件也归一，是为同一生产线新旧文件比对，**不等于**允许任意内容差异；删正文仍会失败。CSV 在非 Windows 上也会从 `csv` 默认 CRLF 改为 LF，属于任务书明定的 LF 结果。 |

## 3. 投影重建与数量

| 项 | 意见 | 证据与可复现输入 |
| --- | --- | --- |
| P1：投影哈希与行数 | **不改** | 在 `31a25c1` 干净克隆以 SQLite 只读方式读 `data/projections/kaoyan_projection.sqlite` 的 `projection_meta.inputs`，JSON 含 **18** 条；逐条用对应文件当前字节重算 SHA-256，`missing=[]`、`hash_mismatch=[]`。表行数与 meta 相符：`knowledge_points=496`（cs408 403、math1 69、eng1 24），`supplementary_knowledge_points=410`，`exam_questions=432`（登记的 11 份索引），`question_knowledge_weights=1059`。前三组与 `tests/test_data_manifest.py:46-66,68-91,135-158` 的树/索引清单一致；1059 是投影表及 meta 实测值，清单测试本身没有对这个数做断言。`git ls-files --eol -- data review/attach-audit` 在该克隆均为 `i/lf w/lf`。未重建投影。 |

## 4. 建议与总判定

- **建议改**：`tests/contract/test_workspace.py:229` 对 `products.*` 的缺失原因改为生成/恢复产品目录的准确提示；当前“按 data/materials.yaml 重取原始资料”适合 raw_root，不适合产品目录。
- **整体 FAIL**：C3 与投影重建的现有数据验收通过；C1 的“全量 0 失败”数字成立，但 18 个卷面契约跳过记录中包含不依赖外部资源的格式断言。先收紧这一跳过边界，再复核干净克隆的有效覆盖。未就缺少原始资料的真实性能/来源校验作通过判断。
