# 复审 + 评审：sol 99 修复（`0d106be`）与 WP-E3b（合并提交 `a256d36`）

遵守 `AGENTS.md`（不跑全量）。运行用 `git archive a256d36`（原始资料与 `products` 空目录照前几轮补）。

## A. 复审 `0d106be`（你第 99 轮的 F2 / S2 / S3 / S4）

范围：`git show 0d106be`；实现者报告 `review/rounds/round-101-e3a-sol99-fixes-luna.md`。C2（缺 `--plan` 文件退出 3）在 E3b 合并里由决策者修（`route_main` 先查文件再解析存储）。
请用你第 99 轮的原复现输入逐条重跑，并判断：manifest 解析是否仍有可绕过的结构；`os.link` 发布在 Windows 上的原子不覆盖与失败清理；回滚是否只删本次发布的文件；新测试撤修复是否变红。

## B. 评审 WP-E3b

范围：`git diff <合并提交>^1 <合并提交>`；任务书 `review/rounds/round-100-wp-e3b-task.md`；实现者报告 `review/rounds/round-100-wp-e3b-luna.md`。
决策者审查时改了：`_registered_route_store` 由比对错误消息改为看 `workspace.routes is None`；提案 YAML 读取抽成 `_load_proposal_mapping` 共用；删两个无用导入；C2。

请判断：
1. 信任边界：路线提案是否只能经 `staging/routes/` + 输入包 + 新鲜度检查落盘；`stage1_input_hash == input_hash` 的约束；`--plan` 拒绝 staging 路径（两种 submit）有无绕过（大小写、junction、相对路径、无注册表时的跳过规则）。
2. 路线输入包：字节稳定、按 `route--*--<hash12>` 查包的唯一性与越界检查、`kind` 校验、过期判定。
3. 日输入包 `route_plan`：无路线时与 `f0df351` 逐字节一致（对照测试是否真固定了旧版）；有路线时包络选取（月边界、范围外）；路线换版本使旧日提案过期是否与规格一致。
4. 两种 route submit 是否同一 apply 函数；日计划提案行为有无回归。
5. 新测试撤实现是否变红。

产物：`review/rounds/round-102-review-sol-out.md`，A、B 两部分每项"必须改 / 建议改 / 不改"附可复现输入，各自给 PASS / FAIL。只写这一个文件。
