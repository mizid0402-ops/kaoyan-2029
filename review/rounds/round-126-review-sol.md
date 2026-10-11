# 复审：sol 第 125 轮"回填恢复日"修复

遵守 `AGENTS.md`（不跑全量；严重度按威胁模型，安全类单列"安全登记"）。运行用 `git archive d8decae`（照前几轮补原始资料与 `products` 空目录）。

决策者直接修了你第 125 轮唯一的"必须改"（改动不到 20 行）：
- M27 新增公开 `unresolved_freezes(events)`，`latch_active` 改为它非空；
- `ky resume`：若有未解除的冻结事件日期晚于 `--date`，在写队列 / 事件之前退出 2，提示"冻结发生在 <日期>，恢复日期不能早于它；请用 --date <日期> 或更晚"（dry-run 同样）；
- `contracts/freeze.md` 两处、`docs/安全风险登记.md` S9 按你的安全登记更正；
- 新测试 `tests/contract/test_resume_port.py::test_resume_dated_before_an_unresolved_freeze_is_rejected`（无逾期 / 有逾期 × dry-run / 正式，退出 2、队列与事件文件不变）。

请用你第 125 轮的原复现输入重跑，并查：多条未解除冻结日期不同时取最晚一条是否正确；`--date` 等于冻结日仍能解除；已解除的旧冻结（日期晚于 D）不应阻止。
你第 125 轮的两条"建议改"（同日 CLI 串联补到第二次 resume、无注册表警告的直接断言）决策者未做，你已手工验证过；如认为必须补请说明理由。

产物：`review/rounds/round-126-review-sol-out.md`，"必须改 / 建议改 / 不改"附可复现输入，"安全登记"一节，最后 PASS / FAIL。只写这一个文件。
