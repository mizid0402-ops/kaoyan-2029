# 评审：WP-G3b 拆分 `validate_config` / `validate_review_item`（`e403b1e`）

遵守 `AGENTS.md`（不跑全量；严重度按威胁模型，安全类单列"安全登记"）。你上一轮（第 135 轮）审过同类的 G3a；本包照同一做法。
用 `git archive e403b1e`（补原始资料与 `products` 空目录），只在你自己的临时目录运行；`git show` 基线用 `GIT_DIR` 读对象。

依据：任务书 `review/rounds/round-138-wp-g3b-task.md`；实现者报告 `round-138-wp-g3b-luna.md`。

请查：
1. `validate_config`、`validate_review_item` 行为是否逐字节不变：合法结果全字段；非法输入异常类型 / 消息 / 路径；多处出错时先报哪一处。
2. 对照测试 `tests/contract/test_models_split_baseline.py`：基线固定、变体按规则生成且真覆盖各段与组合、每个变体的预期成功 / 失败是否标对（你上轮对 G3a 提过同样的问题）。
3. 顺带改的 `tests/contract/test_workspace_split_baseline.py` 是否落实了你第 135 轮的建议。
4. 拆出的函数是否各做一件事、命名是否名副其实。

产物：`review/rounds/round-139-review-sol-out.md`，"必须改 / 建议改 / 不改"附可复现输入，"安全登记"一节，最后 PASS / FAIL。只写这一个文件。
