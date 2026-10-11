# 评审：WP-B′ 收尾（f00259c、e5c929b）

遵守仓库根 `AGENTS.md`（不跑全量，只跑相关单模块）。
1. `git show f00259c`：B′4 tools 迁移。重点：`tests/test_cs408_lecture_pipeline.py` 的新旧输出对照是否真能抓到"删掉用户可见输出"（试着在临时副本里删一行模板，看测试是否失败）；归一化是否只放过任务书允许的三类差异。
2. `git show e5c929b`：P4（契约测试去字面量）与 V1（词汇关系形状）是否修好；`_ProjectionRows` 重构是否保持"先解析、后写库"。
产物：`review/rounds/round-50-review-sol-out.md`，每条 "必须改 / 建议改 / 不改"，两个提交分别 PASS / FAIL。
