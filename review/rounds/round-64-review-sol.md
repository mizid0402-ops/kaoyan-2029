# 评审：`2ebce6c` WP-H3 卷面登记与出题单位（M5 / M5′，决议 D5 / D6）

遵守 `AGENTS.md`（不跑全量）。运行用 `git archive 2ebce6c` 导到系统临时目录（缺 gitignore 的原始资料不计为提交缺陷，同前）。

背景：任务书 `review/rounds/round-61-wp-h3-task.md`、决策者审查意见 `round-63-wp-h3-fixes-task.md`、两份实现报告 `round-61-wp-h3-luna.md` / `round-63-wp-h3-fixes-luna.md`。
新规格：`contracts/paper_shape.md`、`contracts/exam_index.md`；`contracts/workspace.md` 新增 `reference.paper_shapes`。

重点：
1. **有没有变弱**：对照 `924fb0e` 的 `tools/verify_408_index.py` 与 `ky/exam/paper_shape.py`，找出旧版会拒绝、新版却接受的索引输入（例如 cs408 的 A–D 规则、2026 大题分值必须为 null、答案重读的题号集合、总分）。
2. **D5 / D6 验收是否真成立**：在临时工作区只加数据（新年份卷、`paper_source: <某校>` 的卷）能否通过校验并进投影；`question_id` 身份规则、`paper_source` 缺省为 `national` 是否有漏洞（例如自命题卷省略 `paper_source`、同一 `question_id` 跨统考 / 自命题撞车）。
3. 规格与实现是否一致；规格有没有没实现的条款，实现有没有规格没写的行为。
4. `tools/build_408_index_v2.py` 逐字节对照的做法是否可信（固定 `924fb0e`）。
5. 契约测试是否会在对应检查被撤回时变红。

产物：`review/rounds/round-64-review-sol-out.md`，每条"必须改 / 建议改 / 不改"附可复现输入，最后 PASS / FAIL。只写这一个文件。
