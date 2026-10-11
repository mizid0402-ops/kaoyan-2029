# 复审：`441654a`（你第 94 轮对 WP-E2 的 H1 / H2 / I1 与建议项）

遵守 `AGENTS.md`（不跑全量）。运行用 `git archive 441654a`（原始资料与 `products` 空目录照你前几轮做法补）。

范围：`git show 441654a`；实现者报告 `review/rounds/round-95-wp-e2-sol94-fixes-luna.md`。

决策者对 H1 的裁定（可以反驳）：本机单用户系统无法认证提案作者，`actor` 是审计声明；"AI 产物零特权"靠**谁能执行 apply**——
AI 进程只写 `staging/`，两种 `day-plan submit` 只由用户本人或其信任的编排者执行；staging 提案一律须带 `input_hash`，`input_hash: null` 只可能来自 `--plan`。见 `contracts/planner_port.md` 信任边界一节。

请判断：
1. H1：规格与实现是否一致；收紧后还有没有不经输入包、经 staging 写入的路径。
2. H2：`ky/storage/atomic.py` `replace_bytes` 是否关闭硬链接写穿；替换失败时的清理；与聚合工具原 `_replace_file` 行为是否等价。
3. I1：`preflight_to_mapping` 单一来源后 `ky preflight --json` 是否逐字节不变；输入包 `review_clip` 去掉内嵌 `config`、只保留顶层 `config` 的取舍。
4. I2 / E1 / S1 / M1 的规格措辞与 `schema_version` 精确整数校验。
5. 新测试撤修复是否变红。

产物：`review/rounds/round-96-review-sol-out.md`，每项"必须改 / 建议改 / 不改"附可复现输入，最后 PASS / FAIL。只写这一个文件。
