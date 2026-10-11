# 评审：G2a 复审 + WP-G3a + WP-G2b

遵守 `AGENTS.md`（不跑全量；严重度按"评审严重度与威胁模型"，安全类单列"安全登记"）。这是新开的评审窗口 `sol-main`，此前的评审在另一个窗口做，相关报告都在 `review/rounds/`。
每个包用对应提交的 `git archive`（照前几轮补原始资料与 `products` 空目录）；只在你自己的临时目录运行，不读写主仓库工作区。

## 1. G2a 复审：`458f1ea`

你（上一评审窗口）第 130 轮 `review/rounds/round-130-review-sol-out.md` 的两个"必须改"：M1 不带 `--store` 时注册表读两次、M2 serve 地址行未刷新。修法见提交信息。
请用原复现输入重跑 M1、M2，并查 G3 建议（缺省 preflight 从表取入口、帮助测试逐行）。

## 2. WP-G3a：`0f9689d`（拆分 `load_workspace`）

任务书 `review/rounds/round-131-wp-g3a-task.md`、实现者报告 `round-131-wp-g3a-luna.md`。重点：行为是否逐字节不变（合法注册表的 `Workspace` 全字段、非法输入的异常消息 / 路径 / **多处出错时先报哪一处**）；
对照测试 `tests/contract/test_workspace_split_baseline.py` 的基线是否固定、变体是否真覆盖各段与组合、是否按规则生成而非写死科目；拆出的函数是否各做一件事。

## 3. WP-G2b：`b90dc70`（`tools/` 分层）

规则：上一评审窗口第 128 轮 `round-128-g2b-rules-sol-out.md`；任务书 `round-129-wp-g2b-task.md`；实现者报告 `round-129-wp-g2b-luna.md`；提交信息写了决策者的改动（三个树生成器都归档，因为**没有脚本能重现任何一棵登记树**，且它们直接写登记路径）。
重点：每个被挪脚本从新位置能否运行（仓库根、导入）、产物 provenance 未改；`tools/README.md` 的清单与依赖图是否属实（尤其"重建"说法、年份限制、禁止对仓库运行的警告）；测试与文档引用是否全部更新、历史叙述是否标了"当时路径"；
决策者"树生成器全部归档"的取舍是否合理（可以反驳）。

## 产物

`review/rounds/round-135-review-sol-out.md`：三个包分节，每项"必须改 / 建议改 / 不改"附可复现输入；"安全登记"一节；每个包各自给 PASS / FAIL。只写这一个文件。
