# 评审：四个已合并 master 的提交

遵守 `AGENTS.md`（不跑全量；主工作区另有 luna 在改 `ky/__main__.py` 等，需要跑测试时用 `git archive <提交>` 导到临时目录再跑相关单模块）。

1. `c234b9a`：知识点读写权限拆分 + `contracts/knowledge_tree.md`（你第 47 轮 D1 的修复）。
2. `8cf3676`：台账 CLI——你第 52 轮 H2 的 M1/M2。
3. `a7f7606`：WP-C2——D8′（每次复习都计算，`completion_id` 只算一次，与队列原子提交）与 D9（严格 / 宽松两档；**两档共同底线：自评永远不能拉长间隔**）。决议原文见 `docs/阶段2.5-接缝收口.md` §七。
4. `9f242e8`：M24 核对出题（新模块，`contracts/check_questions.md`）。

每个提交：对照规格与决议找"规格写了实现没做 / 测试断言太弱 / 新漏洞"，给可复现输入。
产物：`review/rounds/round-57-review-sol-out.md`，每条 "必须改 / 建议改 / 不改"，四个提交分别 PASS / FAIL。
