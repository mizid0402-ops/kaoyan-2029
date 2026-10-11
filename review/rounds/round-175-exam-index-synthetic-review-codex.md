# 第 175 轮评审：卷面契约合成来源页

## 结论

**FAIL。** 六个改造用例在没有原始资料的干净归档中均实际运行并通过，合成页也确实触发答案比对和来源哈希核对；但新增真实资料用例的缺资源提示没有给出恢复来源，且新增了固定年份的索引路径，未满足本轮明示的资源提示要求与 `AGENTS.md` 第 8 条。

范围仅为 `git diff 58f44bc -- tests/contract/test_exam_index_port.py`。用 `git archive 58f44bc` 建系统临时目录，只复制本轮测试文件；未修改仓库源码，也未评第 173 轮文件。全量：未跑（按 AGENTS.md）。

## 必须改

### M1：真实资料缺失时只说明用途，没有说明恢复来源

位置：`test_real_raw_page_verifies_when_available` 中的 `require_path(..., "real registered answer HTML is required for integration verification")`。它给出缺失路径，却没有告诉使用者按哪份登记记录或来源重新取得文件；本轮要求缺资料时“跳过并写明路径与恢复来源”。同文件原有 `_copy_file(require_raw=True)` 已使用“按 `data/materials.yaml` 中对应的来源记录重新获取”，而新用例的预检查使该提示无法执行。登记项 `cs408-quiz-pages-2023-2026` 在 `data/materials.yaml` 中有 `storage.url` 和预期 SHA-256，可据此给出恢复线索。

复现：在仅包含 `git archive 58f44bc` 加本轮测试文件的临时树中，不补 `data/raw_materials`，设 `GIT_DIR=<主仓库 .git>`、`PYTHONDONTWRITEBYTECODE=1`，运行 `py -3.12 -m unittest tests.contract.test_exam_index_port.ExamIndexPortTests.test_real_raw_page_verifies_when_available -v`。实测 `skipped 'missing resource: ...\\data\\raw_materials\\cs408\\quiz_pages\\cs408_quiz_2026.html; real registered answer HTML is required for integration verification'`，路径有了，恢复来源没有。请在提示中指向 `data/materials.yaml` 对应 `resource_id` 的 `storage.url` 或明确的备份恢复办法。设 `KY_REQUIRE_RESOURCES=1` 重跑，实测 `FAILED (failures=1)`，同一缺资源消息变为 `AssertionError`；这一失败模式本身正确。

### M2：新增真实资料用例写死 2026 索引路径

位置：新用例首行 `ROOT / "data/exam_questions/408_index_2026.json"`，末尾又固定从临时树读取同一路径。这是本轮新增的年份字面量；`AGENTS.md` 第 8 条规定不得新增写死的科目 ID、年份或学校，应从注册表或数据文件取。它也使这个新用例始终只核验 2026，即使登记表新增别的年份的真实答题页。

复现：查看 `git diff 58f44bc -- tests/contract/test_exam_index_port.py` 中的 `test_real_raw_page_verifies_when_available`；把新的真实来源索引登记到 `kaoyan.workspace.yaml` 的 `reference.exam_indexes` 后，单跑该测试，执行路径仍固定打开 `408_index_2026.json`。请从登记索引中选取有本地答案来源、且适合该集成核验的记录，并在缺资源提示中给出被选记录；合成页辅助本身已按临时索引生成，无需改动。

## 建议改

**S1：缺题、多题用例可在改 DOM 后同步来源哈希，以单独锁定读取器。** 在临时归档给 `verify` 加只读打印包装，单跑 `test_answer_reader_rejects_one_missing_question` 与 `test_answer_reader_rejects_one_extra_question`，两者均为 `OK`，问题列表都包含 `answer reader yielded question numbers`；前者读到 `2..40`（期望 `1..40`），后者读到 `1..41`（期望 `1..40`）。两者列表开头还各有 `$.provenance.paper` 与 `.answer` 的 `disk hash != index hash`，因为 `_mutate_answer_source` 改 DOM 后未更新哈希。这一哈希不符在旧测试的原始页变异中也存在；验证器未提前退出，读取器断言仍确实执行，因此不阻断本轮。若希望测试只因题号覆盖出错，可在 DOM 变异后同步该临时来源的哈希及相关字段。

## 不改

- **干净归档的六个用例：**不补原始资料，执行 `py -3.12 -m unittest tests.contract.test_exam_index_port -v`，实测 `Ran 16 tests in 6.936s`、`OK (skipped=1)`。六个改造用例逐项均为 `ok`；唯一跳过的是新增真实页用例。合成页辅助遍历本次临时索引中有答案的条目，用 `number`、`answer`、`question_id` 生成卡片及 ID 摘要，没有固定题数或年份。独立探针在当前登记输入上读到 40 张卡、4,697 字节；`extract_408_answers` 的映射与索引有答案的条目逐项相等，台账 `storage.sha256` / `byte_size`、索引全部 `provenance.sha256`、`locator.paper_sha256` 与 `answer_sources[].sha256` 均等于生成文件的实际摘要/大小。这些数字只是本次实测，测试辅助没有写成固定期望。
- **成功断言不是空页误过：**只在临时树把合成卡片的答案改为 `G`，单跑 `test_2027_national_paper_is_data_only_and_projected`，实测 `FAILED (failures=1)`，首项为 `cs408-2027-01: answer 'A' != source 'G'`，合计 40 项答案不符。恢复后只停掉 `provenance` 的哈希同步，单跑同一用例，实测再次 `FAILED (failures=1)`，包含 `$.provenance.paper: disk hash != index hash`、`$.provenance.answer: disk hash != index hash` 与 `locator hash != provenance hash`。两次变异后都从工作区重新复制测试文件，临时文件哈希与工作区相同；未用旧 `.pyc`（`PYTHONDONTWRITEBYTECODE=1`）。
- **原断言意图：**六个用例保留原有的 `verify(...) == []`、题号拒绝、投影结果及字段可选性断言；缺题/多题实际到达答案读取器。与 `58f44bc` 逐段比对，仅把来源页准备和对应 DOM 变异改为合成资料；其余原有用例行为未改。
- **真实资料路径：**干净归档缺页时跳过；补入登记的真实 `cs408_quiz_2026.html`（SHA-256 `880b98bd99afb98f8c5352acfcf273aad0baf044b2f04e86e027e7d119f2de3a`）后，单跑新增用例为 `Ran 1 test ... OK`，整模块为 `Ran 16 tests in 7.621s`、`OK`，无跳过。M1/M2 仅涉及提示及新增测试的资料选择，不否定真实页确已由 `verify(...) == []` 核验。

## 安全登记

本轮未发现需另行登记的恶意输入、手工篡改内部文件或精确竞态问题。M1 是日常缺资料时的恢复提示，M2 是数据增长规则，均不属安全项。
