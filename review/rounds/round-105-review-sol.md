# 定向复审：sol 第 102 轮 A1 / A2 / B2 / B4 与 B5 / B6 的修复

遵守 `AGENTS.md`（不跑全量）。范围只限修复提交 `79623ee`（`git show 79623ee`；运行用 `git archive 79623ee`，照前几轮补原始资料与 `products` 空目录）。
实现者报告 `review/rounds/round-104-sol102-fixes-luna.md`。决策者审查时删了只做转发的 `_ensure_staging_target`，并去掉 `_validate_input_package` 里与新辅助函数重复的旧越界检查（错误消息保留）。

请用你第 102 轮的原复现输入逐条重跑并判断：
1. A1：回滚前的身份核对（`st_dev` / `st_ino`）在 Windows 上是否可靠；核对失败时不删、原异常照抛；规格对剩余窗口的表述。
2. A2：写入前来源校验与 manifest 读取是否同一函数；拒绝时一字节不写。
3. B2：`find_workspace` 区分"找不到"与"找到但无效"（含 `KY_WORKSPACE`）；两种 `submit --plan` 都 fail-closed。
4. B4：写包 / 查包（日、路线）与提案路径是否都经 `_resolve_staging_path` 的两步检查；junction 用例。
5. B5 / B6：诱饵跳过规则与规格一致；路线换版使旧日提案过期的测试。
6. 新测试撤修复是否变红。

产物：`review/rounds/round-105-review-sol-out.md`，每项"必须改 / 建议改 / 不改"附可复现输入，最后 PASS / FAIL。只写这一个文件。
