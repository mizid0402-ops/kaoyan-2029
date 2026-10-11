# 评审：`84987e4` WP-D 词汇投放状态迁出参考库（M7 → M13，审查项 B2）

遵守 `AGENTS.md`（不跑全量）。运行用 `git archive 84987e4` 导到系统临时目录（缺 gitignore 原始资料照前做法复制；固定基线测试需要时设 `GIT_DIR`）。

背景：任务书 `review/rounds/round-85-wp-d-task.md`、实现报告 `round-85-wp-d-luna.md`。迁移工具尚未对真实 `state.plans` 执行 `--apply`（决策者待用户确认后执行）。

重点：
1. 参考库是否真的只读：任何路径（`daily_words`、`vocab_channel`、快照、迁移工具）还能不能写 `eng1_vocabulary.sqlite`；`mode=ro` 是否处处生效。
2. 已投放集合：以 `word_form` 为键、按词族排除（`daily_words`）与按词形排除（`preview_batch` / `remaining_pool`）两套口径是否会让同一状态下两处给出矛盾的结果；`delivered_words()` 对损坏的完成事件、非本存储布局文件的处理。
3. `daily_words` 与固定基线 `162a9e1` 的逐字节对照是否可信；Python 端分页排除（取代 SQL `NOT EXISTS`）在词族多、已投放多时是否仍与旧版一致；`--date` 参数是否还有用。
4. 迁移工具：日期分组、词序、已有事件拒绝、dry-run 不写；它写出的"只有 vocab、`reviews: []`"事件会不会妨碍用户当天之后再用 `day-plan record` 记录复习（完成事件每天只能写一次）。
5. 快照在没有注册表 / 目录不存在时的行为与规格一致否。
6. 契约测试撤修复是否变红。

产物：`review/rounds/round-86-review-sol-out.md`，每条"必须改 / 建议改 / 不改"附可复现输入，最后 PASS / FAIL。只写这一个文件。
