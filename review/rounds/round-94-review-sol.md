# 评审：`8f31a05` WP-E2 规划者端口（新模块 M19，审查项 A5，README 硬不变量②）

遵守 `AGENTS.md`（不跑全量）。运行用 `git archive 8f31a05`（原始资料与 `products` 空目录照你前几轮做法补）。

背景：任务书 `review/rounds/round-91-wp-e2-task.md`、决策者意见 `round-93-wp-e2-fixes-task.md`、实现报告 `round-91-wp-e2-luna.md` / `round-93-wp-e2-fixes-luna.md`；新规格 `contracts/planner_port.md`。

重点：
1. **硬不变量②是否真的成立**：能否构造一条路径让 AI 提案绕过 staging / 输入包 / 过期检查直接写入（例如把 AI 提案伪装成 `--plan`、`actor: human` 的提案带假 `input_hash`、staging 里的 junction / 硬链接、提案或输入包在校验与写入之间被换）。
2. **输入包确定性**：规范化序列化规则是否真能让同一输入产出相同字节（浮点、日期、集合顺序、`asdict(config)` 的字段顺序）；哪些与规划无关的变化会误触"过期"，哪些真实变化却不会触发。
3. **过期检查**的比较对象是否正确（`--config` 不同、注册表变化、同日多次生成）。
4. M13 manifest schema 2 的兼容规则：旧条目读取、新写入、同日多版本时来源记录的是哪一版。
5. `write_target` 新增的类型检查与 `require()` 口径是否一致；对 E1 的行为有无回退。
6. `snapshot_to_mapping` 单一来源后 `ky snapshot --json` 是否确实不变。
7. 契约测试撤实现是否变红。

产物：`review/rounds/round-94-review-sol-out.md`，每条"必须改 / 建议改 / 不改"附可复现输入，最后 PASS / FAIL。只写这一个文件。
