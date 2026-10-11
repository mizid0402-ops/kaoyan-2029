# 卷面索引合成来源页验证报告

## 改动

只修改了 `tests/contract/test_exam_index_port.py`。六个原先要求原始 HTML 的用例现在在临时工作区生成合成来源页；另有一个独立用例用 `require_raw=True` 对真实 2026 来源页执行 `verify(...) == []`，资料缺失时会明确报告缺少的注册来源路径。

合成来源辅助函数从本次临时索引中读取有答案的题号、答案和 question_id。每题生成解析器实际识别的 `explanation-choice-<16 位十六进制摘要>-<题号>` DOM 卡片，摘要由该题 question_id 计算。随后将来源文件写到索引登记资源的临时路径，并同步临时索引的 provenance、locator、answer_sources，以及台账中的 SHA-256 和字节数。没有固定题数或年份。缺一题 / 多一题用例直接删除 / 追加合成页中的 DOM 卡片。

## 主仓库验收

命令：

```text
py -3.12 -m unittest tests.contract.test_exam_index_port
```

恢复撤实现探针后再次执行的验收输出：

```text
................
----------------------------------------------------------------------
Ran 16 tests in 7.655s

OK
```

## 缺原始资料归档验证

使用 `git archive --format=zip ... HEAD` 导出到系统临时目录，确认 `data/raw_materials` 不存在；将当前修改后的 `tests/contract/test_exam_index_port.py` 复制进归档。设置 `GIT_DIR` 为主仓库 `.git` 目录、`PYTHONDONTWRITEBYTECODE=1`，在归档目录执行：

```text
py -3.12 -m unittest tests.contract.test_exam_index_port -v
```

输出中的关键行：

```text
RAW_DIR_PRESENT=False
test_real_raw_page_verifies_when_available (...) ... skipped 'missing resource: C:\\Users\\Lenovo\\AppData\\Local\\Temp\\round174-exam-index-db548b50aa5a4f42bfc57ff4be4ac3b2\\data\\raw_materials\\cs408\\quiz_pages\\cs408_quiz_2026.html; real registered answer HTML is required for integration verification'
----------------------------------------------------------------------
Ran 16 tests in 7.250s

OK (skipped=1)
```

其余 15 个用例均实际运行并通过；唯一跳过项是要求真实来源 HTML 的集成核验。

## 撤实现验证

临时将最小题号对应的合成答案改成另一个合法字母，执行：

```text
py -3.12 -m unittest tests.contract.test_exam_index_port.ExamIndexPortTests.test_2027_national_paper_is_data_only_and_projected
```

实测结果为失败，`verify` 指出了索引答案与来源 DOM 不符：

```text
F
AssertionError: Lists differ: ["cs408-2027-01: answer 'A' != source 'B'"] != []
Ran 1 test in 0.445s
FAILED (failures=1)
```

随后恢复了答案生成逻辑，并重新运行上面的验收命令，结果为 `OK`。

## 建议

未发现需要报告的被测代码问题。

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。
