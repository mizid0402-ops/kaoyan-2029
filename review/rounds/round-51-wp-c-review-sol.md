# 评审：WP-C 复习推进端口（分支 stage25/wp-c，提交 88474d4，尚未合并 master）

遵守 `AGENTS.md`（不跑全量）。用 `git show 88474d4` 审；若要运行测试，在 `F:\workspace\kaoyan-wt-wp-c` 里跑相关单模块（主工作区有别的会话在改注册表）。
1. 对照 `contracts/review_progress.md` 与决议 D3 / 硬不变量③：纯自评（`check: none`）在任何 `self_rating` 下是否都不改 phase / ease / interval；有核对时映射与阶梯是否正确；v1 旧事件是否一律按未核对处理。
2. 队列重放的幂等键（完成日 + 映射质量）是否会造成重复推进或漏推进的实际场景；给出最小修法（若 `ReviewItem` 需要新字段，说明代价）。
3. 从 D7 可读性角度指出最该改的地方（若有）。
产物：`review/rounds/round-51-wp-c-review-sol-out.md`，每条 "必须改 / 建议改 / 不改"，给 PASS / FAIL。
