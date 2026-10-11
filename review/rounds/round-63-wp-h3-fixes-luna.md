# WP-H3 决策者审查意见修复报告

## 修改落点

1. `tools/verify_408_index.py` 将卷面检查拆为取记录、逐题核对、总分核对、独立重读答案等辅助函数；`_verify_paper_shape` 现为 10 行。读取器登记表是模块常量 `ANSWER_READERS`，并注明新增来源格式需增加读取器并在卷面登记写入名称。
2. `ky/exam/paper_shape.py` 删除 `PaperRecord` 的 `choice_count`、`choice_marks_each`、`essay_marks` 属性。`tools/build_408_index_v2.py` 通过本地辅助函数从登记段计算选择题号与综合应用题分值。
3. `marks_each` 与 `marks` 映射现在接受有限正数（整数或浮点数，排除布尔值）；`contracts/paper_shape.md` §3 同步。契约测试包含 `0.5` 正例，以及 `0`、负数和 YAML `.nan` 负例。
4. `tests/contract/test_exam_index_port.py` 按 D5 新年份、D6 出题单位及各缺陷场景拆成独立测试，共用临时工作区辅助函数。每个负例都检查针对该缺陷的错误信息子串。
5. `tools/verify_408_index.py` 模块说明保留“字符串必须取自枚举集合”的原约束，仅将答案字母说明改为 A–G，并由登记卷面分段进一步收窄。
6. `contracts/exam_index.md` 与 `contracts/paper_shape.md` 标题后补充模块、实现文件和契约测试路径。

## 负例检查撤除验证

逐项临时撤除对应检查，运行对应单测；六项均以断言缺少目标缺陷信息而失败。随后恢复校验器，并确认其文本恢复一致。

| 临时撤除的检查 | 单测结果 |
|---|---|
| question_id 必须含自命题单位 | `test_custom_paper_source_is_required_in_question_ids` 失败；缺少预期 `cs408-xidian-2026-01` 问题 |
| 必须存在对应 `(exam_year, paper_source)` 卷面记录 | `test_index_without_registered_paper_record_fails` 失败；未产生“no paper shape recorded”问题 |
| 科目必须登记卷面文件 | `test_subject_without_registered_shape_file_fails` 失败；问题列表为空 |
| 题型必须匹配卷面分段 | `test_question_type_must_match_registered_section` 失败；没有题型不匹配问题 |
| `marks: unverified` 段的索引分值必须为空 | `test_unverified_section_rejects_recorded_marks` 失败；没有未核实分值问题 |
| 登记的答案读取器必须存在 | `test_unknown_answer_reader_fails` 失败；没有未知读取器问题 |

## 固定基线构建器对照

从固定提交 `924fb0e` 读取旧版 `tools/build_408_index_v2.py` 与旧版 `ky/exam/paper_shape.py`，和当前构建器在同一系统临时目录分别生成 2023–2026 输出；逐文件原始字节比较均一致，未写入 `data/exam_questions/`。

| 年份 | 对照 | 字节数 | 新版输出 SHA-256 |
|---:|---|---:|---|
| 2023 | BYTE IDENTICAL | 44703 | `01198a6b058a664734f8904f92ab57fde536cae16e621fcac8ff1b6013d7c46c` |
| 2024 | BYTE IDENTICAL | 44747 | `fe447e56d575b83a121e69eeb660dc22b19c84647c54105332b15b257ba8e919` |
| 2025 | BYTE IDENTICAL | 44705 | `4d79cec15d073350f6897c37ba610282744d80eabecb9f569ed038f8604180d4` |
| 2026 | BYTE IDENTICAL | 45011 | `f2a46794e65285557c1f06b798ab0dc67bfcedd844e7c4fd97406d78274527b7` |

## 验收

- 指定 unittest 命令：`Ran 43 tests ... OK (skipped=1)`。
- `py -3.12 tools/verify_408_index.py`：`ALL INDEX FILES VERIFIED`。
- `py -3.12 tools/mutation_test_408_index.py`：`all 8 mutations rejected; real index untouched`。
- `py -3.12 tools/mutation_test_knowledge_weights.py`：`all 6 mutations rejected; real index untouched`。
- `git diff --check`：通过。
- 含中文改动文件连续问号扫描：无命中。
- 全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。不提交。

## 建议

- 投影目前仍未单列 `paper_source`；后续可在投影契约包中评估增加该列，现有 `question_id` 已包含出题单位。
- `tools/build_408_index_v2.py` 仍是 CS408 专用采集适配器；`tools/classify_questions.py` 仍有 CS408 专用映射，均在本工作包边界外。
