# WP-H3 第 64 轮审查意见修复报告

## 规格核对与修改落点

1. **顶层必需字段**：`contracts/exam_index.md` 的对象形状列出所有允许顶层键，并仅声明 `paper_source` 可选；据此明确写出除 `paper_source` 外全部必需。逐项检查注册表当前列出的 11 份索引，均含有 `schema_version`、`kind`、`exam_year`、`subject_id`、`question_count`、`marks_total`、`answer_source_coverage`、`calibration`、`provenance`、`content_policy`、`verified_facts`、`unverified_facts`、`entries`，与规格一致，无冲突。`tools/verify_408_index.py` 新增必需键检查；缺字段错误带字段路径。`paper_source` 仍可缺省为 `national`。
2. **十进制分值**：`tools/verify_408_index.py` 用 `Decimal(str(value))` 比较分段逐题分值、卷面登记总分和索引通用总分；非法或非有限索引分值不参与总和且会报告问题。两份规格说明十进制比较。新回归构造三题、每题 `0.1`、总分 `0.3` 的临时索引与卷面登记，验证通过。
3. **卷面加载器**：`ky/exam/paper_shape.py` 对混合类型未知键按 `str` 排序，仍以 `ContractError` 返回 `papers[i]...` 字段路径；卷面题量超过 99 时在 `papers[i].question_count` 报错。`contracts/paper_shape.md` 明确每卷 1–99 题。
4. **回归覆盖**：`tests/contract/test_exam_index_port.py` 新增 A–D 答案边界、独立读取题号少一与多一、缺 `calibration` 并声称 `official`、缺 `kind`、0.1 小数总分及自命题卷进入投影的场景。答案题号测试在临时工作区副本上删改真实答题页卡片，并调用真实读取器。`tests/contract/test_paper_shape_port.py` 新增混合类型未知键和 100 题负例。

## 撤检查变红验证

各负例单独运行，并临时撤掉对应检查；所有测试均变红。撤检后，源码文件逐字节恢复。

| 临时撤掉的检查 | 负例及撤检结果 |
|---|---|
| cs408 分段答案字母约束 | `test_cs408_choice_answer_rejects_e` 失败；目标 A–D 错误缺失，仅剩答案源不一致问题 |
| 独立答案题号集合相等（缺卡） | `test_answer_reader_rejects_one_missing_question` 失败；目标题号集合问题缺失，仅剩摘要不匹配与逐题来源差异 |
| 独立答案题号集合相等（多卡） | `test_answer_reader_rejects_one_extra_question` 失败；目标题号集合问题缺失，仅剩摘要不匹配 |
| 所有固定顶层键必需（临时将 `calibration` 移出必需集合） | 缺 `calibration` 且声称 `official` 的测试失败；问题列表为空 |
| 所有固定顶层键必需（临时将 `kind` 移出必需集合） | 缺 `kind` 的测试失败；问题列表为空 |
| 未知键的字符串安全排序 | 混合键测试失败；旧排序导致 `TypeError`，而非预期 `ContractError` |
| `question_count <= 99` | 100 题测试失败；撤掉上限后未抛 `ContractError` |

## 验收输出

- `py -3.12 -m unittest tests.contract.test_paper_shape_port tests.contract.test_exam_index_port tests.test_exam_index`：`Ran 28 tests ... OK`。
- `py -3.12 tools/verify_408_index.py`：`ALL INDEX FILES VERIFIED`。
- `py -3.12 tools/mutation_test_408_index.py`：`all 8 mutations rejected; real index untouched`。
- `py -3.12 tools/mutation_test_knowledge_weights.py`：`all 6 mutations rejected; real index untouched`。
- `git diff --check`：通过。
- 含中文文件连续问号扫描：无命中。
- 全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。未修改数据文件、投影实现或构建器；未提交。
