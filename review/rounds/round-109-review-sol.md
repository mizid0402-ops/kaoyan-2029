# 定向复审：sol 第 107 轮 F1 / C1 / C2 / T1 的修复（WP-E4）

遵守 `AGENTS.md`（不跑全量）。范围只限修复提交（`git log -1 --format=%h -- ky/schedule/budget.py`），运行用 `git archive <该提交>`（照前几轮补原始资料与 `products` 空目录）。
任务书 `review/rounds/round-108-sol107-fixes-task.md`（含决策者定的 C1 / C2 规则）；实现者报告 `review/rounds/round-108-sol107-fixes-luna.md`。

请用你第 107 轮的原复现输入逐条重跑，并判断：
1. F1：混合类型顶层键报带路径的契约错误，CLI 退出 2。
2. C1：`floor_policy="drop_when_short"` 只在来源为 `availability` 时启用；缺省 strict 行为不变；放弃保底后分配之和等于预算、`floor_minutes` 为 0；0 / 30 分钟的 preflight 与输入包都能生成。这条规则本身是否合理（可以反驳）。
3. C2：`unschedulable` 以配置硬上限判定，当日上限只导致延期；无 override 时 `select_daily_reviews` 结果逐字节不变。
4. T1：文本输出断言与固定基线；规格对"发现无效注册表时 preflight 退出 2"的说明。
5. 新测试撤修复是否变红。

产物：`review/rounds/round-109-review-sol-out.md`，每项"必须改 / 建议改 / 不改"附可复现输入，最后 PASS / FAIL。只写这一个文件。
