# 第 179 轮复审：卷面契约合成来源页返工

## 结论

**PASS。** 第 175 轮 M1、M2 已解决；S1 的缺题/多题用例不再混入来源哈希错误，撤同步变异使新增断言变红。实现报告所述非严格与严格模式“首个缺失文件不同”，在同一归档输入上未复现：本轮四次进程运行的首个文件和顺序一致。unittest 的不同显示方式只能解释反斜杠的转义差异，不能解释文件名差异；实现报告当时产生不同文件名的具体原因暂无法确认。

仅评 `git diff 58f44bc -- tests/contract/test_exam_index_port.py`。用 `git archive 58f44bc` 建系统临时目录，只复制此待审测试文件；未改仓库源码，未评第 178 轮文件。全量：未跑（按 AGENTS.md）。

## 必须改

无。

## 建议改

**S1：若希望锁定完整问题列表，可收紧缺题/多题的断言。** 现有用例断言存在 `answer reader yielded question numbers` 且不存在 `disk hash != index hash`，足以证明本轮要消除的无关哈希错误；它们没有断言除此之外只出现哪几条错误。定点打印 `verify` 的实际列表：多一题只有题号集合错误；缺一题有题号集合错误，另有 `cs408-2026-01: answer 'A' != source None`。后者是同一张答案卡缺失引发的逐题答案比对，不是来源哈希或其他独立失败。若将“只剩题号覆盖类”严格定义为仅一条集合错误，这与当前验证器的正常双重报告不相容；建议保留这两类预期并在测试中明确断言允许的列表形状，避免以后混入其他问题时仍通过。

复现：在下述临时归档中，仅单跑 `test_answer_reader_rejects_one_missing_question` 与 `test_answer_reader_rejects_one_extra_question`，以只读包装打印 `verify(path, workspace, materials)` 的返回值；两项均 `OK`，问题项分别为 2 条与 1 条，均无 `disk hash != index hash`。

## 不改

- **M1 恢复提示：** `_source_recovery_hint` 使用台账记录的 `resource_id` 与 `storage.url`；新增真实页用例和原有 `_copy_file(require_raw=True)` 都走此提示。无原始资料归档运行 `py -3.12 -m unittest tests.contract.test_exam_index_port -v`，实测 `Ran 16 tests in 8.338s`、`OK (skipped=1)`。唯一跳过的真实页用例提示列出各索引、缺失路径、resource ID 与恢复 URL；六个合成页用例实际为 `ok`。
- **M2 公开接口与真实核验：** 新用例由 `load_workspace(...).exam_indexes` 枚举索引，再用 `load_ledger` 查来源；该新增路径不含固定年份或索引文件名。把本机 47 个原始资料文件复制到同一临时归档后，`test_real_raw_page_verifies_when_available` 为 `Ran 1 test ... OK`，模块为 `Ran 16 tests in 10.966s`、`OK`。只读调用计数探针证实真实页用例实际调用 `verify` **11 次且每次返回 `[]`**：408 四份、数学一四份、英语一三份；非 408 索引并未被跳过。没有可用索引时才调用 `require_path` 跳过；部分可用时逐个 `subTest(index=...)` 核验可用项。
- **提示顺序稳定：** 在同一无原始资料的归档内，分别以未设和设 `KY_REQUIRE_RESOURCES=1` 的条件把真实页用例各运行两次。非严格两次退出 0、严格两次退出 1；各模式提取出的完整缺资源消息在两次进程运行间原始字符相同。四次的首个缺失路径均为 `data/raw_materials/cs408/past_papers/408_2023_paper.pdf`。遍历登记索引沿 `Workspace.exam_indexes` 的稳定顺序，单索引的资源 ID 又经 `sorted(source_ids)` 排序。实现报告中严格模式的 `cs408_quiz_2023.html` 与本次同输入复现不符；`skipped '...'` 行的双反斜杠只是字符串表示形式，不会使 paper PDF 变成 quiz HTML。
- **S1 哈希同步与变异：** 缺题/多题在 DOM 改动后调用 `_synchronize_synthetic_source_hashes`，同步临时来源字节、台账 SHA-256/大小及索引 `provenance`、`locator`、`answer_sources`。两项实际问题列表均无哈希错误。只在临时副本撤掉这两个用例的同步调用，设 `PYTHONDONTWRITEBYTECODE=1`，单跑 `test_answer_reader_rejects_one_missing_question`，实测 `FAILED (failures=1)`：新增 `assertFalse` 检出 `$.provenance.paper` 与 `.answer` 的 `disk hash != index hash`。随后从工作区重复制文件，临时文件 SHA-256 与待审版相同。

## 安全登记

本轮未发现需按恶意输入、手工篡改内部文件或精确竞态登记的新问题。
