# WP-G3c S1 + WP-G3h 工具拆分报告

## 第一部分：G3c S1（`ky/__main__.py`）

### 拆分落点

- 移除纯转发函数 `_snapshot_build`；`snapshot_main` 现在直接调用 `build_snapshot`。
- `snapshot_main` 共 42 行；参数、校验、输出和错误处理顺序不变。

### 对照测试

`CliG3cRemainderSplitBaselineTests` 固定使用 `24371ee`，断言旧版六个长函数仍在基线中；比较
`ledger`、`snapshot`、`route`、`resume`、`month-close`、`review-queue` 的退出码和原始 stdout /
stderr。`snapshot` 成功与失败路径均在对照内。

### 撤实现验证

临时将 `build_snapshot` 的 `today` 参数替换为 `date(1900, 1, 1)`，清除 `ky/` 与 `tests/`
下缓存的 `.pyc` 后运行：

```text
$env:PYTHONDONTWRITEBYTECODE='1'; py -3.12 -m unittest tests.test_cli_split_baseline.CliG3cRemainderSplitBaselineTests
```

实际结果：`Ran 2 tests`，`FAILED (failures=1)`。`snapshot-success` 的 JSON `as_of` 从旧版
`2026-09-28` 变为 `1900-01-01`，对照断言变红；随后恢复原参数。

### 验收

本节验收由下方完整指定验收命令覆盖；恢复后 `CliG3cRemainderSplitBaselineTests` 通过。

## 第二部分：WP-G3h（`tools/`）

### 拆分落点

所有新步骤均小于 60 行；拆分保留了原有校验、打印与写入顺序。

| 脚本与函数 | 行数 | 职责 |
| --- | ---: | --- |
| `render_weight_manual.py::_cs408_domains` | 15 | 生成 CS408 学科汇总段 |
| `render_weight_manual.py::_cs408_chapters` | 26 | 生成章节统计段 |
| `render_weight_manual.py::_cs408_fine_nodes` | 21 | 生成细粒度知识点统计段 |
| `render_weight_manual.py::section_cs408` | 8 | 按原顺序组装三个段落 |
| `extract_408_questions_from_html.py::_question_content` | 25 | 校验题型并提取题干、选项及警告 |
| `extract_408_questions_from_html.py::_extract_question` | 42 | 组装记录、状态和答案核对对象 |
| `extract_408_questions_from_html.py::_report_alignment` | 30 | 计算报告摘要与对齐指标 |
| `extract_408_questions_from_html.py::_build_extraction_report` | 43 | 按原字段顺序组装报告映射 |
| `verify_eng1_vocabulary.py::_verify_schema` | 18 | 校验必需表和列 |
| `verify_eng1_vocabulary.py::_verify_source_rows` | 49 | 校验元数据、停用词、词表及来源出现记录 |
| `verify_eng1_vocabulary.py::_verify_word_totals` | 19 | 校验单词计数和方向文本标志 |
| `verify_eng1_vocabulary.py::_verify_family_totals` | 12 | 校验词族计数 |
| `verify_eng1_vocabulary.py::_verify_metadata` | 21 | 校验汇总计数与来源哈希 |
| `verify_eng1_vocabulary.py::verify_database` | 18 | 按旧次序调度各项校验并关闭数据库 |
| `verify_netem_source.py::_verify_rank_sequence` | 10 | 校验 rank 连续性 |
| `verify_netem_source.py::_verify_entry_values` | 14 | 校验规范化词形和频次 |
| `verify_netem_source.py::_verify_reproducibility` | 24 | 与提交的无释义来源 JSON 逐项对照 |
| `verify_netem_source.py::verify_database` | 54 | 读取数据并按原次序调度校验 |
| `netem_cross_validate.py::_load_comparison_data` | 9 | 读取三组数据库数据并关闭连接 |
| `netem_cross_validate.py::_lemma_adjusted_coverage` | 14 | 计算词形差异和词元回收集合 |
| `netem_cross_validate.py::_cross_validation_lines` | 56 | 按原顺序生成完整报告行 |
| `verify_408_question_extraction.py::_verify_year_records` | 44 | 分年校验记录并输出各年统计 |
| `verify_408_question_extraction.py::_verify_record_summary` | 26 | 校验报告汇总、文本文件数和记录唯一性 |
| `verify_408_question_extraction.py::_verify_records` | 14 | 调用分年校验和汇总校验 |
| `extract_exam_skeleton.py::_read_structure` | 24 | 读取 PDF 并提取章节与题号结构 |
| `extract_exam_skeleton.py::_print_structure` | 26 | 打印结构报告并返回题号统计 |
| `extract_exam_skeleton.py::main` | 38 | 解析参数、检查路径并写可选 JSON |
| `probe_exam_pdf.py::_download_pdf` | 10 | 下载候选 PDF 并计算哈希 |
| `probe_exam_pdf.py::_inspect_pdf` | 6 | 汇总页数与前几页文字量 |
| `probe_exam_pdf.py::_print_download_summary` | 12 | 打印下载元信息 |
| `probe_exam_pdf.py::_print_pdf_metadata` | 8 | 打印 PDF 元数据 |
| `probe_exam_pdf.py::_print_marker_scan` | 12 | 扫描前两页的结构标记 |
| `probe_exam_pdf.py::main` | 50 | 调度下载、检查、打印和可选页面提取 |

### 对照测试覆盖

新增 `tests/test_tools_split_baseline.py`，固定读取 `git show 24371ee:<脚本>`，并逐个断言旧长函数
达到原行数下界；HTML 提取器的两个旧长函数分别断言。执行了 16 组新旧输入对照，逐字节比较
退出码、stdout、stderr；手册、NETEM 报告、HTML 提取产物和探测 PDF 也比较输出文件字节。

- 校验工具：词库 / NETEM 数据成功路径、缺数据库失败；M21 验证器成功路径、参数错误路径。
- 手册与报告：生成手册、NETEM 报告成功；未知参数失败。
- PDF 骨架：有效 PDF 成功、缺失 PDF 失败。
- HTML 提取：注册数据提取成功并比较所有文件；未知参数失败。
- PDF 探测：本地 HTTP 服务提供有效 PDF 成功、非 PDF 内容失败；比较 staging 文件字节。
- `verify_eng1_vocabulary.py` 的成功路径需要登记的六份英语试卷。当前仓库缺少这些 PDF，测试依
  `tests/_resources.require_path` 跳过该成功场景；缺数据库的失败场景仍执行。

### 撤实现验证

临时把 `_cross_validation_lines` 的报告行返回值替换为空列表；先清空 `tools/` 与 `tests/`
的 `.pyc`，并禁用字节码读写，执行：

```text
$env:PYTHONDONTWRITEBYTECODE='1'; py -3.12 -m unittest tests.test_tools_split_baseline.ToolsSplitBaselineTests.test_file_producers_match_outputs_and_failures
```

实际结果：`Ran 1 test`，`FAILED (failures=1)`。NETEM 报告文件从原始多行内容变为单个换行，
产物字节对照失败；随后恢复 `return lines`。恢复后的对照测试通过。

### 验收

执行命令：

```text
py -3.12 -m unittest tests.test_cli tests.test_cli_split_baseline tests.test_tools_catalog tests.test_tools_split_baseline tests.test_deck_scaffold_split_baseline tests.contract.test_index_tree_verifiers_split_baseline
```

命令结束时的验收输出：

```text
----------------------------------------------------------------------
Ran 63 tests in 113.629s

OK (skipped=1)
```

相关既有测试：

```text
py -3.12 -m unittest tests.test_eng1_vocabulary tests.test_netem_source
....s.....
----------------------------------------------------------------------
Ran 10 tests in 6.153s

OK (skipped=1)
```

新对照独立运行：

```text
py -3.12 -m unittest tests.test_tools_split_baseline
s....
----------------------------------------------------------------------
Ran 5 tests in 10.026s

OK (skipped=1)
```

### 未拆脚本及理由

按本任务明确列出的 26 个 `active` / `validation` / `acquisition` 脚本扫描，改动的 8 个脚本中
原有 9 个超长函数已全部拆分；扫描后没有剩余函数超过约 60 行。其余列入扫描的 18 个脚本没有
超长函数，因此没有可拆的超长步骤：

`aggregate_topic_weights.py`、`apply_knowledge_weights.py`、`classify_questions.py`、
`daily_words.py`、`build_408_deck_scaffold.py`、`extract_cs408_bundle.py`、
`extract_408_question_text.py`、`import_netem_source.py`、`verify_408_index.py`、
`verify_tree.py`、`tree_source_support.py`、`probe_outline.py`、`probe_pdf_text.py`、
`list_tree_vocab.py`、`fetch_evidence.py`、`fetch_all_from_ledger.py`、
`render_pdf_pages.py`、`render_staged_page.py`。

按 `tools/README.md` 确认，`pinned_reproducer`、`migration`、`archived`、`retired` 脚本不在本轮
拆分范围内。这些脚本依赖固定历史输入或一次性状态，有的输出带时间信息；对其拆分收益有限，
而重放输出的对照风险较高。未修改这些脚本。

建议：补齐注册的英语试卷后，单独重跑被跳过的词库验证成功场景。M21 正文、覆盖信息和无命中
提示通过产物字节对照保持原样。

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）
