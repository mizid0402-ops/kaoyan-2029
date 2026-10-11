# 评审：WP-G3d（`9cb8132`）＋ 复审 G3c（`b43eb1f`）

遵守 `AGENTS.md`（不跑全量；严重度按威胁模型，安全类单列）。你审过 G3a–G3c。用 `git archive 9cb8132`（补原始资料与 `products` 空目录；`git show` 基线用 `GIT_DIR`），只在你自己的临时目录运行；调换变异时设 `PYTHONDONTWRITEBYTECODE=1` 并清 `__pycache__`。
依据：任务书 `review/rounds/round-148-wp-g3d-task.md`；实现者报告 `round-148-wp-g3d-luna.md`。

请照你第 146 轮对 G3c 的查法：
1. 新旧（`ec832c7`）在所有路径上的返回值 / 问题列表次序 / 输出 / 退出码是否逐字节一致；实跑两个校验器对仓库登记数据的输出对比。
2. 对照测试 `tests/contract/test_index_tree_verifiers_split_baseline.py`：变体是否按意图构造（例如嵌套赋值有没有把列表项整体替换）、是否覆盖每类检查；按主函数里**可独立调换的相邻步骤**逐对调换，列出哪些仍绿。
3. 失败 / 提前退出分支（`verify_tree` 的来源阶段、引用阶段提前退出）是否被对照锁住。
4. 拆出的函数是否各做一件事、名副其实。

## 另：G3c 复审（`b43eb1f`）

你第 146 轮 M1–M4 与 S1。实现者报告 `review/rounds/round-149-wp-g3c-rework-luna.md`（含 12 对相邻步骤调换表）。请重放你 146 轮的全部探针（出题成功路径、推进失败 / 冻结写入失败的事件状态、双错误首报、冻结 JSON），并看 `_CliExit` 的用法是否清楚、没有吞掉不该吞的异常。

产物：`review/rounds/round-150-review-sol-out.md`，G3d 与 G3c 分节，"必须改 / 建议改 / 不改"附可复现输入，"安全登记"，各给 PASS / FAIL。只写这一个文件。
