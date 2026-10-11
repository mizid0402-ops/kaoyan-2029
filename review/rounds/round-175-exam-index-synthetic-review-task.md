# 评审任务书：第 174 轮 —— 卷面契约 6 个用例改用合成来源页（窗口 `sol-main`）

请评审 `luna-c` 第 174 轮的改动。任务书 `review/rounds/round-174-exam-index-synthetic-task.md`，
实现报告 `review/rounds/round-174-exam-index-synthetic-luna.md`。这条建议是你在第 122 轮提的
（`review/rounds/round-122-review-sol-out.md` 第 8 行）。

**本轮评审范围只有** `tests/contract/test_exam_index_port.py`（`git diff` 对 `58f44bc`）。
工作区里 `tools/round24_validate_weighted_tree.py`、`tools/round29_validate_agreement.py`、
`tests/test_tools_split_baseline.py` 是另一个窗口在做的第 173 轮，**不在本轮范围**，不要评它们。

先读 `AGENTS.md`（"评审严重度与威胁模型"、"数据会增长"第 7–8 条）。

## 重点看

1. 六个用例在**缺原始资料**的干净归档里是否真的运行并通过（不是被跳过），断言意图与改前一致——
   尤其 `verify(...) == []` 的用例是否真的走到了答案比对与来源哈希核对，而不是因为合成页"恰好空"而通过。
2. 合成页的题号 / 答案 / ID 是否从临时索引推导，没有写死数量、年份（第 7–8 条）；
   台账 SHA-256 / 大小与索引 `provenance` / `locator` / `answer_sources` 是否全部同步。
3. 缺一题 / 多一题两个用例是否仍然测的是答案读取器的拒绝，而不是别的检查先失败。
4. 新增的真实资料核验用例 `test_real_raw_page_verifies_when_available`：有资料时真的核验真实页，
   缺资料时跳过并写明路径与恢复来源；`KY_REQUIRE_RESOURCES=1` 时变成失败。
5. 撤实现验证：自己做一次定点变异（例如合成页某题答案改错、或台账哈希不同步），确认对应用例变红。

## 规则

- 只跑与结论直接相关的单个模块或单条命令，**不跑全量**。
- 复现用系统临时目录（`git archive 58f44bc` + 复制本轮文件），不写进仓库。
- 结论写 PASS / FAIL，分"必须改 / 建议改 / 不改"，每条附可复现输入；安全类单列"安全登记"。

## 报告

`review/rounds/round-175-exam-index-synthetic-review-codex.md`。
