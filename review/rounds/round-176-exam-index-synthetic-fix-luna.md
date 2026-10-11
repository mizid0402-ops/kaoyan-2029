# 第 174 轮返工报告：M1 / M2 / S1

## 改动

只修改了 `tests/contract/test_exam_index_port.py`。

- **M1**：真实资料用例缺资源时，提示现在包括来源 `resource_id` 和台账记录的 `storage.url`。同文件 `_copy_file(require_raw=True)` 使用相同的恢复提示。恢复来源按 `data/materials.yaml` 中的 URL 获取。
- **M2**：通过 `load_workspace()` 的公开 `Workspace.exam_indexes` 映射枚举所有登记索引，用 `load_ledger()` 解析来源记录。每个引用来源均有本地文件的索引都在独立 `subTest(index=...)` 中调用 `verify(...) == []`。没有可核验索引时，通过 `require_path` 跳过，并列出索引路径、来源 `resource_id` 和恢复 URL。没有固定索引年份或文件名。
- **S1**：把合成页生成与来源哈希同步拆开。缺题 / 多题用例改完 DOM 后重新同步来源字节、台账大小和 SHA-256、provenance、locator、answer_sources；然后显式断言错误列表不含 `disk hash != index hash`。

## 主仓库验收

命令：

```text
py -3.12 -m unittest tests.contract.test_exam_index_port
```

恢复撤实现探针后的验收输出：

```text
................
----------------------------------------------------------------------
Ran 16 tests in 8.419s

OK
```

## 无原始资料归档

用 `git archive --format=zip ... HEAD` 导出到系统临时目录，确认 `data/raw_materials` 不存在；只把当前修改后的测试模块复制进归档。设置 `GIT_DIR=<主仓库 .git>`、`PYTHONDONTWRITEBYTECODE=1` 后，在归档中运行：

```text
py -3.12 -m unittest tests.contract.test_exam_index_port -v
```

输出：

```text
RAW_DIR_PRESENT=False
test_real_raw_page_verifies_when_available (...) ... skipped 'missing resource: C:\\Users\\Lenovo\\AppData\\Local\\Temp\\round176-exam-index-5965a538419140a48a56dc590b676012\\data\\raw_materials\\cs408\\past_papers\\408_2023_paper.pdf; no registered index has all answer sources locally available; selected records and recovery sources: data/exam_questions/408_index_2023.json: restore resource_id cs408-paper-2023 from data/materials.yaml storage.url https://www.xit.edu.cn/_upload/article/files/c1/ce/26986f79493495bbaacba9738587/ac8ae739-b5ab-4d8e-b5cf-441525833872.pdf; data/exam_questions/408_index_2023.json: restore resource_id cs408-quiz-pages-2023 from data/materials.yaml storage.url https://www.csgraduates.com/study_methods/408quiz/2023/; data/exam_questions/408_index_2024.json: restore resource_id cs408-paper-2024-rebuild from data/materials.yaml storage.url https://raw.githubusercontent.com/neville-studio/408-exam-paper/main/papers-rebuild/2024.pdf; data/exam_questions/408_index_2024.json: restore resource_id cs408-quiz-pages-2024 from data/materials.yaml storage.url https://www.csgraduates.com/study_methods/408quiz/2024/; data/exam_questions/408_index_2025.json: restore resource_id cs408-quiz-pages-2025 from data/materials.yaml storage.url https://www.csgraduates.com/study_methods/408quiz/2025/; data/exam_questions/408_index_2025.json: restore resource_id cs408-paper-2025 from data/materials.yaml storage.url https://www.xit.edu.cn/_upload/article/files/c1/ce/26986f79493495bbaacba9738587/d9fce855-72bd-4e00-9a48-5d4ec5ef6f72.pdf; data/exam_questions/408_index_2026.json: restore resource_id cs408-quiz-pages-2023-2026 from data/materials.yaml storage.url https://www.csgraduates.com/study_methods/408quiz/2026/; data/exam_questions/math1_index_2023.json: restore resource_id math1-exam-2023-qihang from data/materials.yaml storage.url https://www.qihang.cn/; data/exam_questions/math1_index_2024.json: restore resource_id math1-exam-2024-ztbu from data/materials.yaml storage.url https://www.kaoyan.cn/; data/exam_questions/math1_index_2025.json: restore resource_id math1-exam-2025-ztbu from data/materials.yaml storage.url https://www.kaoyan.cn/; data/exam_questions/math1_index_2026.json: restore resource_id math1-exam-2026-kaoyan from data/materials.yaml storage.url https://www.kaoyan.cn/; data/exam_questions/eng1_index_2024.json: restore resource_id eng1-paper-2024-bv from data/materials.yaml storage.url https://www.bilibili.com/; data/exam_questions/eng1_index_2024.json: restore resource_id eng1-answer-2024-eol from data/materials.yaml storage.url https://www.eol.cn/e_html/gk/kaoyan/2024ky/english.shtml; data/exam_questions/eng1_index_2025.json: restore resource_id eng1-answer-2025-lazynote from data/materials.yaml storage.url https://english-exam.lazynote.cn/kaoyan/paper/2025-english-one/; data/exam_questions/eng1_index_2025.json: restore resource_id eng1-paper-2025-bv from data/materials.yaml storage.url https://www.bilibili.com/; data/exam_questions/eng1_index_2026.json: restore resource_id eng1-answer-2026-static from data/materials.yaml storage.url https://static.kaoyan.cn/; data/exam_questions/eng1_index_2026.json: restore resource_id eng1-paper-2026-bv from data/materials.yaml storage.url https://www.bilibili.com/'
----------------------------------------------------------------------
Ran 16 tests in 7.556s

OK (skipped=1)
```

随后在同一归档中设置 `KY_REQUIRE_RESOURCES=1`，运行同一模块：

```text
py -3.12 -m unittest tests.contract.test_exam_index_port -v
```

真实资料用例变为失败，模块结果：

```text
test_real_raw_page_verifies_when_available (...) ... FAIL
AssertionError: missing resource: C:\Users\Lenovo\AppData\Local\Temp\round176-exam-index-5965a538419140a48a56dc590b676012\data\raw_materials\cs408\quiz_pages\cs408_quiz_2023.html; no registered index has all answer sources locally available; selected records and recovery sources: ...
Ran 16 tests in 7.541s
FAILED (failures=1)
STRICT_EXIT_CODE=1
```

## 撤实现验证

临时移除缺题用例在 DOM 修改后的 `_synchronize_synthetic_source_hashes(...)` 调用，运行：

```text
py -3.12 -m unittest tests.contract.test_exam_index_port.ExamIndexPortTests.test_answer_reader_rejects_one_missing_question
```

新加的断言按预期失败，错误列表中有 provenance 哈希错误，同时保留题号覆盖错误：

```text
AssertionError: True is not false : ['$.provenance.paper: disk hash != index hash ...', '$.provenance.answer: disk hash != index hash ...', '$: answer reader yielded question numbers [2, ... , 40], expected [1, ... , 40]', "cs408-2026-01: answer 'A' != source None"]
Ran 1 test in 0.431s
FAILED (failures=1)
```

随后恢复同步调用，并重跑主仓库验收，结果为 `OK`。

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。
