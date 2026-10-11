# WP-G1：测试缺资源跳过 + 数据文件行尾归一

## 完成情况

- 新增 `tests/_resources.py::require_path`。缺少文件时默认 `skipTest`，消息含缺失路径和重取提示；`KY_REQUIRE_RESOURCES=1` 时抛出断言失败。适用于测试方法和 `setUpClass`。
- 在实际读取或复制外部文件前接入检查。资源可用时仍运行原断言；没有改断言内容。
- 未搬测试目录。三层测试命名约定见“建议”。

## C1：资源依赖用例

| 测试文件与用例 | 缺失资源（重取方式） |
|---|---|
| `tests.test_eng1_vocabulary.English1VocabularyRegressionTests.test_verifier_deterministic_check_and_mutations` | `%TEMP%\kaoyan-probe\claude2\dl\bv_e1_2024.pdf`；按 `data/materials.yaml` 的 `eng1-paper-2024-bv` 重取 |
| `tests.test_round24_weighted_tree.WeightedTreeStructureTest.test_real_file_passes_validation` | `data/raw_materials/cs408/syllabus/archive408_408_outline_2026.html`；按 `data/materials.yaml` 或树的来源登记重取 |
| `tests.test_round24_weighted_tree.WeightedTreeStructureTest.test_real_file_alias_provenance_passes`、`MutationTest.test_fabricated_alias_text_is_rejected` | `%TEMP%\kaoyan-probe\ghsurvey\downloads\408_syllabus_2022.pdf`；按 2022 大纲来源登记重取 |
| `tests.test_exam_index.ExamIndexTest.test_contract_verifier_passes`、`test_hashes_match_the_registered_bytes`、`test_ledger_keeps_the_source_weak_and_unstructurable` | `data/raw_materials/cs408/past_papers_thirdparty/408_2024_paper_rebuild.pdf` 与 `data/raw_materials/cs408/quiz_pages/cs408_quiz_2024.html`；按 `data/materials.yaml` 对应资源 ID 重取 |
| `tests.test_exam_index.ExamIndexTest.test_rehost_restoration_round_trip` | `data/raw_materials/cs408/past_papers/408_2022_paper.pdf`（同一方法还会核验登记的其余重托管卷）；按 `data/materials.yaml` 重取 |
| `tests.test_tree_integrity.TreeIntegrityTest.test_recorded_sha256_matches_the_source_bytes`、`test_every_quote_ref_locates_in_its_declared_source`；`LedgerTierRegressionTest.test_transcript_sources_are_registered_and_local` | 例如 `data/raw_materials/transcripts/eol_cn/math_outline_2022_fulltext.html`、`data/raw_materials/transcripts/newdu_com/math1_outline_2026_fulltext.html`；按 `data/materials.yaml` / 树来源登记重取 |
| `tests.test_round29_quote_locate.LocateQuoteAgainstRealSourceTest`（类级 setup） | `data/raw_materials/cs408/syllabus/408_syllabus_2022.extracted.txt`；按 2022 大纲来源重新获取并抽取 |
| `tests.contract.test_exam_index_port.ExamIndexPortTests` 中使用 `_temporary_workspace` 的用例 | `data/raw_materials/cs408/quiz_pages/cs408_quiz_2026.html`；按 `data/materials.yaml` 对应来源登记重取。检查放在 fixture 的原始文件复制处 |
| `tests.test_verify_tree_shapes.VerifierMutationTest` 中调用 `_verify_mutation` 的用例 | CS408 树需要 `data/raw_materials/cs408/syllabus/archive408_408_outline_2026.html`；Math1 树需要登记的转录 HTML。检查放在验证器运行前 |
| `tests.test_round29_tree_split.MainTableVerifyTreeTest`、`MutationTest.test_corrupted_source_sha256_is_rejected_by_verify_tree` | 主表登记的 2026 CS408 HTML 与 2022 抽取文本；按 `data/materials.yaml` / 树来源登记重取 |
| `tests.test_round29_tree_split.ReproducibilityTest.test_build_is_deterministic_across_two_runs` | 构建器还需 2022 大纲 PDF 与 408 题库 JSON；按来源登记重取 |
| `tests.contract.test_knowledge_tree_port.KnowledgeTreePortContractTests.test_readers_accept_same_tree_with_deterministic_frequency` | `data/raw_materials/transcripts/eol_cn/math_outline_2022_fulltext.html`；按 `data/materials.yaml` / 树来源登记重取 |

元数据与纯结构测试未因缺资源而跳过。工作区没有 `data/raw_materials/`；两份历史探针 PDF 也不存在。

## C3：行尾与写入工具

**本 worktree 的 `--eol` 实测与任务书中的 54 文件基线不同。** 改动前，`data/` 与 `review/attach-audit/` 中按约定扩展名筛出的 103 个跟踪文本文件里，102 个是 `i/lf w/lf`；唯一异常为 `data/paper_shapes/cs408.yaml`（`i/crlf w/crlf`）。没有 54 个 `i/lf w/crlf` 文件。该文件只把 CRLF 改成 LF，`git diff --ignore-space-at-eol -- data/paper_shapes/cs408.yaml` 为空，内容未变。

改动后再次检查：103 个文件均为 `w/lf`；102 个为 `i/lf w/lf`，`data/paper_shapes/cs408.yaml` 为 `i/crlf w/lf`（工作区已符合 LF，索引字节待决策者提交时更新）。未改 `.gitattributes`。

更新了会写入 `data/` 文本数据或 `review/attach-audit/` 的工具，使用 `newline="\n"`、LF 字节写入，或 CSV `lineterminator="\n"`：

- 权重与索引：`aggregate_topic_weights.py`、`apply_knowledge_weights.py`、`build_408_index.py`、`build_408_index_v2.py`、`build_exam_indexes.py`、`classify_questions.py`。
- 树、来源与登记：`build_math1_tree.py`、`build_eng1_tree.py`、`round24_build_weighted_tree.py`、`round29_build_tree_split.py`、`import_netem_source.py`、`apply_round2_fixes.py`、`fix_eng1_provenance.py`、`register_408_source.py`、`register_408_quiz_pages.py`、`register_round2_sources.py`、`remove_408_reprints.py`、`restore_408_papers.py`。
- 导出与审计：`extract_408_question_text.py`、`extract_408_questions_from_html.py`、`extract_cs408_bundle.py`、`extract_exam_skeleton.py`、`audit_attachment.py`、`build_evidence_bundle.py`。

`register_408_quiz_pages.py` 原有的 `print` 多缩进一级，导致该脚本无法解析；一并恢复到同一函数层级，保证登记写入工具可执行。

`test_write_bytes_match_fixed_baseline` 仍固定比较 `8f31a05`：基线和当前输出各自只把 `\r\n` 归一为 `\n` 后按字节比较，并断言当前输出不含 `\r`。另一个 `apply_knowledge_weights.py` 的固定基线用例也按同一 C3 行尾例外归一，避免预期的 LF 输出导致回归误报。

新增 `test_tracked_data_text_files_use_lf`：对 `git ls-files` 登记的 `data/` 下 `.json/.yaml/.yml/.md/.csv/.txt` 检查工作区字节不含 `\r\n`；非 Git 归档跳过。

### 哈希核对

跟踪的 `data/projections/kaoyan_projection.sqlite` 中 `projection_meta.inputs` 登记了 17 个文本输入（11 个题目索引、`topic_weights.json`、5 个知识树文件）的 SHA-256。17 个登记值都与当前 LF 文件字节不匹配；把当前 LF 内容模拟转换为 CRLF 后也都不匹配。因此证据不能把差异归因于换行，较可能是投影登记已过期。按任务要求没有改 SQLite 或哈希；应由决策者决定是否重建投影。

## 验收记录

- 定向命令 `py -3.12 -m unittest tests.test_data_manifest tests.contract.test_topic_weights_port tests.test_eng1_vocabulary tests.test_round24_weighted_tree`：`Ran 41 tests`，`OK (skipped=4)`，0 失败。跳过为上述英一 PDF 和 round-24 来源检查。
- 资源扩展复核 `tests.test_exam_index tests.test_tree_integrity tests.test_round29_quote_locate`：`Ran 22 tests`，`OK (skipped=8)`。
- 后续新增 guard 复核 `tests.contract.test_exam_index_port tests.test_verify_tree_shapes tests.test_round29_tree_split`：`Ran 49 tests`，`OK (skipped=31)`；`tests.contract.test_knowledge_tree_port`：`Ran 8 tests`，`OK (skipped=1)`。大量跳过来自同一个缺失的 2026 quiz HTML 或树来源文件，具体路径见上表与 skip 原因。
- 全量：已在干净克隆按本轮例外跑一次。克隆从 `F:\workspace\kaoyan-wt-g1` 建立；传入当时的已修改跟踪文件和 `_resources.py`，克隆设置 `core.autocrlf=false` 以保留索引字节。命令为 `py -3.12 -m unittest discover -s tests -t .`，结果 `Ran 696 tests in 139.870s`，`FAILED (failures=109, errors=20, skipped=13)`。
- 该次全量的 13 项跳过中，定向复核确认 12 项来自上述缺失资源（英一 1、round-24 3、exam-index 4、tree-integrity 3、round-29 quote 1）；另外 1 项的原因未由默认非 verbose 输出展示，无法从该次日志核实。
- 该全量发生在补上 exam-index fixture、树形变异、round-29 与 knowledge-tree port 的 guard 之前。随后这些受影响模块的定向复核均通过。依任务书“全量只跑一次”，没有重跑全量；所以**最终补充 guard 后的全量结果尚未验证，WP-G1 全量验收未能确认全绿**。

## 建议

- 后续按 `unit/`、`data/`、`env/` 命名测试层，标明无需外部材料的纯逻辑测试、依赖登记数据的测试、依赖本机/外部环境的测试；本包不移动目录。
- 由决策者决定是否重建投影数据库以刷新 17 个输入哈希；不应仅按换行推断旧哈希内容。
- 可以另行评估 `.gitattributes` 固定文本 `eol=lf`；本轮未改该策略。
