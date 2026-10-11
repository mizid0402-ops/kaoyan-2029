# Round 58 WP-H1 实现报告

## 改动

只修改了测试：把当前数据版本的精确数量集中到 `tests/test_data_manifest.py`；其余被测测试保留结构、来源和行为验证，数量关系改为从实际条目推导。没有改数据文件或被测实现。

| 被改断言 | 原值 | 处理方式 |
| --- | --- | --- |
| `test_tree_integrity.py::test_math1_shape_is_locked` | subject 3、chapter 22、section 44、节点 69 | 移入数据清单 `test_knowledge_tree_shape_counts`，继续锁住各 scope 数和总数；原测试保留 subject 标题与章节子结构检查。 |
| `test_tree_integrity.py::test_eng1_shape_is_locked` | section 13、item 11、节点 24 | 移入同一清单测试；原测试保留结构树语义和必需节点 ID 检查。 |
| `test_round24_weighted_tree.py::test_node_count_and_baseline_relation_are_locked` | 节点 410；kept 403、new_vs_baseline 7 | 精确值移入清单 `test_weighted_tree_counts`；原测试改为比较关系字段声明数与实际条目数。 |
| `test_round24_weighted_tree.py::test_weighted_tree_ids_are_a_superset_of_the_baseline_tree` | 相对 baseline 多 7 个 ID | 移入清单关系计数；原测试改为检查差集恰好等于标注为 `new_vs_baseline` 的 ID 集合。 |
| `test_round24_weighted_tree.py::test_evidence_tag_distribution_is_locked`、`test_ocr_risk_aliases_preserve_the_uncorrected_source_b_text` | tag 数量为 315、65、7、8、8、7；OCR 风险节点 8 | 分布移入清单 `test_weighted_tree_counts`；原测试保留 tag 集合、计数自洽与 OCR 标记存在性检查。 |
| `test_tree_source_support.py` | 恰有 410 个节点 | 移入加权树清单快照；逐条重算每个节点权重及零 mismatch 检查保留。 |
| `test_netem_source.py` | words 3409 行；指定 source_entries 5530 行 | 移入清单 `test_netem_database_counts`；原测试仍逐条检查来源词项不含释义字段。 |
| `test_exam_index.py::test_shape_and_marks` | 47 题；题号 1..47；单选/综合题 (40, 7) | 数量和题型分布移入清单 `test_registered_exam_index_counts`，按工作区登记顺序锁定所有索引；连续题号改为相对实际长度检查，题型分类数之和与实际条目数相等。总分 150 保留为试卷规格值。 |
| `test_exam_index.py::test_knowledge_point_weights_shape` | 47 条均有权重分布 | 数量移入注册索引清单；原测试改为要求每道实际索引题都有分布。 |

清单快照现锁定：按工作区注册表与树语法选择的 Math1/Eng1 树形计数、加权树总数/关系/tag 分布、词库两表行数，以及所有已登记索引按注册顺序的题数/题型/权重分布。数据合法增长时应只调整该清单中的对应快照值。

## 验证

- `py -3.12 -m unittest tests.test_data_manifest tests.test_exam_index tests.test_netem_source tests.test_round24_weighted_tree tests.test_tree_integrity tests.test_tree_source_support`：运行 53 项；因 worktree 缺少 `data/raw_materials/`（以及加权树 B 源引用的临时下载文件），出现 583 个断言失败和 3 个错误，均涉及原始来源文件无法读取或验证。按任务书未修改这些测试。
- `py -3.12 -m unittest tests.test_data_manifest`：5 项通过。
- `git diff --check`：通过。
- 六个修改后的测试文件与报告未发现连续问号替换字符。
- 全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。
