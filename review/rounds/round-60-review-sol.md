# 复审：`9dd2382`（你第 57 轮六个阻断项的修复）

遵守 `AGENTS.md`（不跑全量；只跑与结论直接相关的单个模块或单条命令）。
主工作区此刻可能有其他改动；需要运行时用 `git archive 9dd2382` 导到系统临时目录再跑。
归档里没有 Git 忽略的 `data/raw_materials/`，缺原始资料导致的失败不计为提交缺陷（同第 57 轮做法）。

范围：只看 `git show 9dd2382`。你第 57 轮报告是 `review/rounds/round-57-review-sol-out.md`，
实现者报告是 `review/rounds/round-59-sol57-fixes-luna.md`。

逐项判断 K1 / L1 / C1 / C2 / Q1 / Q2：

1. 你的原复现输入现在是否被正确拒绝或处理；
2. 修复是否引入新漏洞或新的兼容问题（例如 L1 的注册表向上发现是否会找到"错的"注册表、
   C2 的 `upgrade_legacy_queue` 是否可能被绕过或重复升级、Q1 的重复判定是否跨科目误伤）；
3. 回归测试的断言是否足够强（能否在修复被撤回时变红）。

两条决策者已定、不需再议的取舍（见 `交接文档.md` §A.3）：
- C2：旧版（schema 1）队列可读；已复习过的项拒绝推进，需 `upgrade_legacy_queue(..., acknowledge_unknown_history=True)` 显式升级（仓库尚无真实队列）。
- L1：只给 `--ledger --root` 时 cwd 向上找注册表 → 台账目录向上找 → 都没有则报错要求 `--subjects`。
  可以指出这条规则的实现缺陷，但不必再论证规则本身。

产物：`review/rounds/round-60-review-sol-out.md`，每项"必须改 / 建议改 / 不改"，
附可复现输入；最后给 `9dd2382` 整体 PASS / FAIL。只写这一个文件。
