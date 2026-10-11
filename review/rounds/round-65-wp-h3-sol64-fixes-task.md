# 任务书：修复 sol 第 64 轮对 WP-H3（`2ebce6c`）的意见

先读 `review/rounds/round-64-review-sol-out.md`（每条都有复现输入）。遵守 `AGENTS.md`。H3 已提交，你在 master 工作区上改，不提交。

## 必须改

1. **M1 顶层固定字段必须存在**：`tools/verify_408_index.py` 对 `kind`、`calibration`（以及规格 `contracts/exam_index.md` 列为必需的其他顶层键——先核对规格，规格与现有 11 份索引一致的才算必需）缺失时必须报问题，不能因 `check_enum` 遇 `None` 返回而放过。
   sol 的复现：删 `calibration` + 把 `entries[0].answer_confidence` 改 `official` → 现在 `verify == []`。修后必须报"缺 calibration"。`paper_source` 仍是可选（缺省 `national`）。
   若规格里对"必需"的表述与现有数据冲突，停下来写进报告，不改数据。
2. **M2 小数分值比较**：卷面登记的 `marks_each` / `marks` 与索引的 `marks` / `marks_total` 做和与比较时用 `decimal.Decimal(str(value))`（或等价的精确十进制做法），不用浮点精确相等。
   sol 的复现：一段 1–3 题 `marks_each: 0.1`、索引每题 `0.1`、`marks_total: 0.3` → 现在误拒。修后通过。
   同时检查通用总分（`marks_total` 等于各题之和）那段也按同样方式比较。规格 `contracts/paper_shape.md` / `contracts/exam_index.md` 写一句比较按十进制值进行。

## 建议改（本轮一并做）

3. `ky/exam/paper_shape.py` 的未知键报告：键混有 int 与 str 时 `sorted` 抛 `TypeError`；改为按 `str` 排序后报 `ContractError`，路径带 `papers[i]....`。
4. 题号上限：`question_id` 是两位题号，规格写明每卷最多 99 题；加载器对 `question_count > 99` 报 `ContractError`。
5. 回归测试（`tests/contract/test_exam_index_port.py`，每条断言具体问题子串）：
   - cs408 选择题答案 `E` → 报 A–D 类问题；
   - 答案读取器读出的题号集合比卷面多 / 少一题 → 报题号集合问题（可用临时的答题页副本删掉一张卡片，或替换读取器结果——优先用真实读取器 + 临时文件）；
   - 缺 `calibration` 且声称 `official` → 报缺字段；缺 `kind` → 报缺字段；
   - `0.1 × 3 = 0.3` 通过；
   - 自命题卷**进投影**：D6 测试里建投影，断言学校卷的题号在投影里。
   `tests/contract/test_paper_shape_port.py`：混合类型未知键 → `ContractError`；`question_count: 100` → `ContractError`。
   不写数据量字面量。每条负例临时撤掉对应检查确认变红，再还原，写进报告。

## 不做的

- 不改 `ky/projection/`（重复 `question_id` 改成带路径的契约错误留给后续投影包）。
- 不改任何数据文件，不改 `tools/build_408_index_v2.py`。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_paper_shape_port tests.contract.test_exam_index_port tests.test_exam_index
py -3.12 tools/verify_408_index.py
py -3.12 tools/mutation_test_408_index.py
py -3.12 tools/mutation_test_knowledge_weights.py
```

## 报告

`review/rounds/round-65-wp-h3-sol64-fixes-luna.md`：逐条落点、撤检查变红记录、验收输出。全量：未跑。不提交。含中文文件查 `???`。
