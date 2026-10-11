# 复审：sol 第 118 轮 B3 / B5 修复（冻结锁存、最终计划对象上的冻结检查）

遵守 `AGENTS.md`（不跑全量）。范围：R1 修复的合并提交 `1ae4d1f` 与实现提交 `8440699`；运行用 `git archive 1ae4d1f`（照前几轮补原始资料与 `products` 空目录）。
依据：`docs/阶段2.5-接缝收口.md` 的 D11（已按你第 118 轮 B5 修订为"锁存"）；任务书 `review/rounds/round-120-r1-sol118-fixes-task.md`；实现者报告 `review/rounds/round-120-r1-sol118-fixes-luna.md`；规格 `contracts/freeze.md`。
决策者审查时改了：`day-plan record` 里实现者用错误消息文本判断"找不到注册表"，改为沿用 record 既有的宽容（取不到注册表就不写锁存、照常记录），规格补写。

请用你第 118 轮的原复现输入重跑：
1. **B5**：正好达阈值 → 冻结期间 `day-plan record --review-store` 记一条带核对结果的完成 → 积压降到阈值下 → preflight 仍冻结（`latched: true`）、submit 仍拒绝 → 写 resume 记录后解除。另查：多次冻结 / 恢复交替、R == F、R < F；记录放错位置、日期不符、重复写入。
2. **B3**：你原来的"CLI 检查后、M19 重读前替换提案文件"探针（`--plan` 与 `--from-staging` 两种）——现在检查在 `DayPlanStore.write_day_plan` 的最终对象与临时文件重读上。
3. **锁存写入方的边界**：`record` 在无注册表 / 无效注册表时不写锁存（决策者的取舍，可以反驳：这让"注册表坏了时记录完成可能间接解冻"成为可能——评估风险）；`submit` 在无注册表时不检查（原规格）。
4. 冻结文本两行；未冻结输出与基线逐字节一致。
5. 新测试撤实现是否变红。

产物：`review/rounds/round-123-review-sol-out.md`，每项"必须改 / 建议改 / 不改"附可复现输入，最后 PASS / FAIL。只写这一个文件。
