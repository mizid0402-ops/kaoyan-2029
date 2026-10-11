# 第 173 轮：WP-G3h M1 / M2 返工报告

## M1：对照测试可在干净归档独立运行

### 改动与覆盖

`tests/test_tools_split_baseline.py` 中原本把 NETEM、M21 成功与参数失败放在同一测试内，现把依赖登记产物的成功用例单独拆开：

| 场景 | 结果 | 覆盖方式 |
| --- | --- | --- |
| `test_html_extraction_success_uses_temporary_product_root` | 成功 | 通过工作区代理仅把已登记的 products 根替换为系统临时目录，仍运行原 `_configure_workspace`；两版 CLI 三元组及临时目录下每个产物文件原始字节相等。输入 HTML 年份从注册索引读取，不写死；每个路径经 `require_path` 检查。 |
| `test_html_extraction_argument_failure_needs_no_external_inputs` | 成功 | `--unknown` 参数失败与固定基线比较，退出码为 2，不加载工作区或外部资料。 |
| `test_question_extraction_verifier_success_when_products_are_registered` | 主仓成功；归档中单独跳过 | 只检查本场景所需的登记 `questions_index.json`；缺失时用 `require_path` 提示可运行 `tools/extract_408_questions_from_html.py` 生成。NETEM 等用例在不同测试方法内照常运行。 |
| `test_verifier_and_report_tools_match_fixed_baseline` | 成功 | 保留数据库校验、NETEM 成功 / 缺库和两个参数错误对照，不再包含依赖产品目录的 M21 成功路径。 |
| `test_eng1_verifier_success_matches_when_registered_papers_are_present` | 按资源单独跳过 | 所有注册英语真题 PDF 均通过 `require_path` 检查。 |

检查了整份测试文件中的外部路径：英语来源 PDF、M21 原始 HTML、M21 登记产物和 round24 来源缓存都有 `require_path`；NETEM / 英语数据库及临时 PDF 由仓库数据或测试构造，不依赖未登记的 gitignore 文件。HTML 成功路径的输出目录为临时目录，没有读取登记产物目录。

### 干净归档自证

从固定的当前 `HEAD`（`58f44bc`）运行 `git archive --format=zip --output=<系统临时目录>.zip HEAD`，展开后覆盖本轮三个实现 / 测试文件；只复制本机恢复的 `data/raw_materials/cs408/quiz_pages/*.html` 与登记来源 A HTML，并建立空的 `review/408知识点树与真题` 目录。没有复制该登记目录下的任何产物。环境设置为 `GIT_DIR=F:\workspace\kaoyan-ai-system\.git`、`PYTHONDONTWRITEBYTECODE=1`、`PYTHONUTF8=1`，执行：

```text
py -3.12 -m unittest -v tests.test_tools_split_baseline
Ran 11 tests in 12.557s
OK (skipped=3)
```

归档中的三个跳过原因原文：

```text
missing resource: C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\claude2\dl\bv_e1_2024.pdf; restore the registered English exam PDFs from the acquisition source
missing resource: C:\Users\Lenovo\AppData\Local\Temp\g3h-m1-archive-f6d9ce94f5f04ad389423d81733b5dc1\review\408知识点树与真题\questions\questions_index.json; generate registered products with tools/extract_408_questions_from_html.py
missing resource: C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\ghsurvey\downloads\408_syllabus_2022.pdf; restore the registered CS408 source listed in data/materials.yaml
```

主仓库同一模块复跑：

```text
py -3.12 -m unittest -v tests.test_tools_split_baseline
Ran 11 tests in 14.537s
OK (skipped=2)
```

主仓库的两个跳过原因原文：

```text
missing resource: C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\claude2\dl\bv_e1_2024.pdf; restore the registered English exam PDFs from the acquisition source
missing resource: C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\ghsurvey\downloads\408_syllabus_2022.pdf; restore the registered CS408 source listed in data/materials.yaml
```

主仓库存在 M21 登记产物，因此验证器成功场景通过。

## M2：拆分 round24 / round29 独立校验器

固定基线为 `58f44bc`。对照测试从 `git show 58f44bc:tools/<文件>` 读取旧源，并通过 AST 断言两版旧 `validate` 均不少于 70 行。

### 拆分落点

| 文件 | 新函数及职责 | `validate` 行数 |
| --- | --- | ---: |
| `round24_validate_weighted_tree.py` | `_validate_node_identity` 识别 / 去重 ID；`_validate_node_status_and_scope` 校验状态与范围；`_validate_node_sources` 校验来源数；`_validate_node_weight` 校验证据标签与权重；`_validate_node_aliases` 校验别名形状；`_validate_baseline_ids` 对照基线树；`_validate_sources_registry` 检查来源文件与摘要。 | 20 |
| `round29_validate_agreement.py` | `_validate_identity` 识别 / 去重 ID；`_validate_item_schema` 检查字段集合；`_validate_item_values` 校验关系、证据、支持度与计数；`_validate_derived_support` 独立重算支持度；`_validate_aliases` 校验别名形状；`_validate_missing_agreement_ids` 检查主表中缺失的附表 ID。 | 20 |

辅助函数均少于 60 行。原循环内检查顺序、继续条件、错误追加顺序与消息保持不变；模块仍独立读取输出数据，不导入构建器的内部状态。

### 对照场景

| 场景 | 结果 | 断言 |
| --- | --- | --- |
| `test_round24_success_matches_fixed_baseline` | 本机因登记来源 B 缺失而跳过；归档同样只跳过此场景 | 检查固定登记 weighted tree 的 CLI 三元组与 `validate` 返回值；来源路径逐项走 `require_path`。 |
| `test_round24_status_error_matches_fixed_baseline` | 成功 | 临时 JSON 副本将首项状态改为 `approved`；比较新旧 CLI 三元组和错误列表，并断言输出含 `status=approved is forbidden`。 |
| `test_round29_success_matches_fixed_baseline` | 成功 | 比较固定登记附表的 CLI 三元组和 `validate` 返回值。 |
| `test_round29_source_support_error_matches_fixed_baseline` | 成功 | 临时 JSON 副本将首项 `source_support` 改为 `0.42`；比较新旧 CLI 三元组和错误列表，并断言输出含 `source_support=0.42`。 |

### AST 全范围扫描

按 `tools/README.md` 状态扫描了 32 个 `active`、`validation`、`acquisition` 脚本；方法以 `ast.parse` 读取每个脚本，逐个函数计算 `end_lineno - lineno + 1`。未发现超过 60 行的函数。每个文件的最大函数行数如下：

| 状态 | 脚本（该脚本最大函数行数） |
| --- | --- |
| active | `aggregate_topic_weights.py` 51；`apply_knowledge_weights.py` 58；`render_weight_manual.py` 56；`classify_questions.py` 33；`daily_words.py` 53；`import_netem_source.py` 47；`build_408_deck_scaffold.py` 39；`extract_cs408_bundle.py` 56；`extract_408_question_text.py` 38；`extract_408_questions_from_html.py` 53。 |
| validation（1/2） | `verify_408_index.py` 46；`verify_tree.py` 40；`tree_source_support.py` 15；`round24_validate_weighted_tree.py` 20；`round29_validate_agreement.py` 30；`verify_eng1_vocabulary.py` 60；`verify_netem_source.py` 58；`netem_cross_validate.py` 56；`verify_408_question_extraction.py` 60。 |
| validation（2/2） | `probe_outline.py` 32；`probe_pdf_text.py` 44；`extract_exam_skeleton.py` 38；`list_tree_vocab.py` 14；`mutation_test_408_index.py` 33；`mutation_test_knowledge_weights.py` 41；`mutation_test_suite.py` 30；`mutation_test_verify_tree.py` 27。 |
| acquisition | `fetch_evidence.py` 33；`fetch_all_from_ledger.py` 27；`probe_exam_pdf.py` 50；`render_pdf_pages.py` 48；`render_staged_page.py` 35。 |

### 撤实现验证

临时把 `_validate_derived_support` 中 `if derived != source_support` 改为 `if derived == source_support`。设置 `PYTHONDONTWRITEBYTECODE=1`，先删除 `tools/` 与 `tests/` 下已有 `__pycache__/*.pyc`，再运行：

```text
py -3.12 -m unittest tests.test_tools_split_baseline.ValidatorSplitBaselineTests.test_round29_source_support_error_matches_fixed_baseline
```

实测退出码 1：`test_round29_source_support_error_matches_fixed_baseline` 在 `tests/test_tools_split_baseline.py:461` 的 `self.assertEqual(errors[0], errors[1])` 失败；错误列表出现 408 条额外的不匹配错误。随后恢复为 `!=`，并通过最终验收。

### 验收

实际运行：

```text
py -3.12 -m unittest tests.test_tools_split_baseline tests.test_tools_catalog tests.test_round24_weighted_tree tests.test_round29_tree_split
Ran 39 tests in 35.216s
OK (skipped=5)
```

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。

建议：round24 的成功路径依赖本机来源缓存；缺缓存时当前环境只能验证无外部资料的失败分支。若需覆盖成功分支，按 `data/materials.yaml` 恢复登记来源后重跑该测试。
