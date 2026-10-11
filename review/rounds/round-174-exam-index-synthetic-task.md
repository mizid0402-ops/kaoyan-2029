# 任务书：卷面契约 6 个用例改用合成来源页（sol 122 建议，窗口 `luna-c`）

先读 `AGENTS.md`（"数据会增长"第 7–8 条、"已知缺陷清单"第 8 条）与
`review/rounds/round-122-review-sol-out.md` 第 8 行（"六个 `require_raw=True` 用例的必要性"，含 sol 的可复现探针）。

另一个窗口 `luna-a` 正在改 `tools/` 与 `tests/test_tools_split_baseline.py`、
`tests/test_round24_weighted_tree.py`、`tests/test_round29_tree_split.py`，**不要碰**。
你只改 `tests/contract/test_exam_index_port.py`（需要的话可在同目录新建一个测试辅助文件）。

## 背景

`tests/contract/test_exam_index_port.py` 里用 `_temporary_workspace(require_raw=True)` 的六个用例
（`test_2027_national_paper_is_data_only_and_projected`、`test_custom_paper_source_is_required_in_question_ids`、
`test_answer_reader_rejects_one_missing_question`、`test_answer_reader_rejects_one_extra_question`、
`test_descriptive_fields_stay_optional`、`test_fractional_marks_sum_without_binary_rounding`）
需要**有效的来源字节**，但不需要仓库外那份 1.7 MB 的**原始** HTML。缺原始资料时（干净克隆）
它们全部跳过，端口契约因此在干净克隆里没人守。sol 122 已用一份约 4 KB 的合成 HTML 证明六个用例
可以 0 skip 通过。

## 要求

1. 在临时工作区里**生成最小合成来源页**（在测试运行时由代码生成，不往仓库里加二进制或 HTML 夹具文件），
   按 sol 122 的做法：每题一个 `<div class="explanation" id="explanation-choice-…"><span class="correct-answer-text">字母</span></div>`，
   字母取自临时索引；并把临时索引的 `provenance` / `locator` / `answer_sources` 与临时台账的
   SHA-256 / 大小**同步到合成文件**。合成页的题数、答案、ID **从临时索引推导**，不写死数量或年份（第 7–8 条）。
   读答案的结构以 `tools/verify_408_index.py` 实际解析的格式为准——去读它，不要猜。
2. 六个用例改用合成来源，**不再** `require_raw=True`，在缺原始资料时也实际运行。
   用例的断言意图不变：原来断言什么，现在仍断言同样的东西（错误路径、错误消息、`verify(...) == []` 等）。
   两个答案读取用例（缺一题 / 多一题）改为改动**合成页**的 DOM。
3. **真实网页字节的集成核验不丢**：新增（或保留）一个独立用例，仍用 `require_raw=True` 对真实原始 HTML
   走一次 `verify(...) == []`，缺资源时跳过并写明缺什么——即"端口契约用合成、真实资料单独核验"。
4. 其余用例、`_copy_workspace` 等辅助的现有行为不变；不改 `tools/`、`ky/`、`data/`。

## 自证

- 主仓库（有原始资料）跑一次验收命令。
- 再模拟缺原始资料：`git archive HEAD` 导出到系统临时目录（不补 `data/raw_materials/`），设
  `GIT_DIR=<主库 .git>`、`PYTHONDONTWRITEBYTECODE=1`，在归档里跑同一模块。六个用例必须**运行且通过**，
  只剩第 3 条的真实资料核验用例跳过。报告贴两次的 `Ran …` 行与跳过原因原文。
- 撤实现验证：把合成页里某一题的答案字母改错（或删掉台账哈希同步那一步），确认对应用例变红；
  报告写实际命令与实际结果，然后恢复。

## 不做的

- 不改被测代码；发现被测代码的问题写进报告"建议"一节。
- 不新增任务书未列的测试（第 3 条那一个除外）。
- 不跑全量测试。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_exam_index_port
```

## 报告

`review/rounds/round-174-exam-index-synthetic-luna.md`：改了什么、合成页如何从索引推导、
六个用例在两种环境下的结果、撤实现验证的实际命令与结果、验收输出原文。
写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。
含中文的文件**只用 `apply_patch` 编辑**，写完查 `???`。
