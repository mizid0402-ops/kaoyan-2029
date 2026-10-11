# 定向复审：sol 第 121 轮 C1-1（卷面契约测试过早跳过）与建议

遵守 `AGENTS.md`。范围只限本轮修复提交 `6826280`。**本轮例外同第 121 轮**：可在干净克隆（`git -c core.autocrlf=false clone`）跑一次全量。

决策者处理：
1. `_copy_file` / `_copy_workspace` / `_temporary_workspace` 增加 `require_raw`（缺省 False）：缺省时缺失的原始资料**不复制也不跳过**；只有读源字节的用例传 `require_raw=True`，缺资料时才跳过。
   哪些用例需要原始资料是实测定的：在干净克隆按新夹具跑，失败的 6 个用例（`test_2027_national_paper_is_data_only_and_projected`、`test_custom_paper_source_is_required_in_question_ids`、`test_answer_reader_rejects_one_missing_question`、`test_answer_reader_rejects_one_extra_question`、`test_descriptive_fields_stay_optional`、`test_fractional_marks_sum_without_binary_rounding`）标 `require_raw=True`。
   干净克隆该模块：15 项、OK（跳过 8，原 18）；有原始资料的主仓库：15 项全通过。
2. 建议 C3-2：LF 守护测试也检查 `review/attach-audit/`。
3. 建议：产品目录缺失时的提示改为"本机产品工作区，由对应生产线工具生成或从备份恢复"。

请判断：仍被跳过的 6 个用例是否确实离不开源字节（例如试着给它们换最小替身，看能否不依赖原始资料就覆盖同一断言——能的话算"建议改"）；其余用例在缺资料时是否真的执行到了 `verify`；守护测试撤回是否变红；干净克隆全量结果。

产物：`review/rounds/round-122-review-sol-out.md`，每项"必须改 / 建议改 / 不改"，最后 PASS / FAIL。只写这一个文件。
