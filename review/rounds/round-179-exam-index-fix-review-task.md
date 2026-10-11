# 评审任务书：第 176 轮 —— 卷面契约合成来源页返工（你第 175 轮的 M1 / M2 / S1，窗口 `sol-main`）

请复审 `luna-c` 第 176 轮。任务书 `review/rounds/round-176-exam-index-synthetic-fix-task.md`，
实现报告 `review/rounds/round-176-exam-index-synthetic-fix-luna.md`，你上一轮报告
`review/rounds/round-175-exam-index-synthetic-review-codex.md`。

**本轮范围只有** `tests/contract/test_exam_index_port.py`（`git diff 58f44bc`）。
`tests/test_tools_split_baseline.py` 等是 `luna-a` 在做的第 178 轮，不在范围。

## 重点看

1. M1：缺资料时提示是否给出 `resource_id` 与恢复来源；与 `_copy_file(require_raw=True)` 口径一致。
2. M2：是否经 `ky.workspace` 公开接口枚举登记索引、没有新增年份 / 文件名字面量；有资料时每个
   "来源齐全"的登记索引都真的 `verify(...) == []`（含非 408 科目的索引——它们的答案读取器能否对真实资料通过？）。
3. **决策者注意到的一处**：实现报告里非严格模式的跳过提示首个缺失路径是 `408_2023_paper.pdf`，
   严格模式（`KY_REQUIRE_RESOURCES=1`）却是 `cs408_quiz_2023.html`——检查缺资源提示的内容与顺序是否确定
   （同一输入两次运行是否相同）；若因遍历集合导致不确定，按"必须改"还是"建议改"由你判断并说明理由。
4. S1：缺题 / 多题用例改 DOM 后哈希已同步，问题列表只剩题号覆盖类错误，且测试断言了这一点。
5. 自己做一次定点变异确认对应用例变红。

## 规则

只跑与结论直接相关的单个模块或单条命令，**不跑全量**；复现用系统临时目录，不写进仓库。
结论 PASS / FAIL，分"必须改 / 建议改 / 不改"，每条附可复现输入；安全类单列"安全登记"。

## 报告

`review/rounds/round-179-exam-index-fix-review-codex.md`。
