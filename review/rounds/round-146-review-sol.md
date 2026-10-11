# 评审：WP-G3c 拆分 CLI 两个超长函数（`8c86fbf`）

遵守 `AGENTS.md`（不跑全量；严重度按威胁模型，安全类单列）。你审过同类的 G3a / G3b。用 `git archive 8c86fbf`（补原始资料与 `products` 空目录；`git show` 基线用 `GIT_DIR`），只在你自己的临时目录运行。
做调换变异时设 `PYTHONDONTWRITEBYTECODE=1`（或每次清 `__pycache__`）。

依据：任务书 `review/rounds/round-144-wp-g3c-task.md`；实现者报告 `round-144-wp-g3c-luna.md`。

请查：
1. `_preflight_main`、`day_plan_main`（submit / record）所有调用的退出码与 stdout / stderr 是否与 `b867ae7` 逐字节一致，尤其多处出错时先报哪一处、record 各失败分支（事件已写而队列未推进等）。
2. 对照测试 `tests/test_cli_split_baseline.py`：基线固定、28 组场景是否真覆盖任务书列的分支；按主函数里相邻步骤逐对调换，哪些调换测试仍绿。
3. 决策者注意到的可读性问题：若干步骤函数返回"元组或退出码 2"的混合类型（例如 `_day_plan_record_workspace`），请判断是否会让调用方误用、是否应改成更清楚的形状（建议改即可，除非会导致日常错误）。
4. 拆出的函数是否各做一件事、名副其实。

产物：`review/rounds/round-146-review-sol-out.md`，"必须改 / 建议改 / 不改"附可复现输入，"安全登记"，最后 PASS / FAIL。只写这一个文件。
