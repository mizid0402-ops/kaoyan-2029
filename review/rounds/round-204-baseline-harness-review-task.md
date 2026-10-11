# 评审任务书：技术债包 B —— 迁移对照测试收敛并退役（第 200 + 203 轮，窗口 `sol61-main`）

请评审 `luna-a` 第 200、203 轮：任务书 `review/rounds/round-200-baseline-harness-task.md`、`review/rounds/round-203-baseline-harness-continue-task.md`；
报告 `review/rounds/round-200-baseline-harness-luna.md`、`review/rounds/round-203-baseline-harness-continue-luna.md`。
背景与用户决定：`docs/技术债与整改清单.md` P1、§6、§7、§9（用户 2026-09-30 选"收敛并退役"）。

**范围只有 `tests/`**：`git diff f52b8f6 -- tests` 与新增 `tests/_baseline_harness.py`、`tests/_fixtures.py`、`tests/test_baseline_harness.py`、
`tests/contract/test_index_tree_verifiers.py`、`tests/test_question_extraction.py`。`ky/` 的改动是包 D（你第 202 轮已 PASS），不在范围。

## 重点看（这是一次删测试的改动，最要紧的是"没有丢掉现有行为的保护"）

1. **(b) 去向表逐条抽查**：报告称"已有等价"的，打开被指向的测试方法，确认它真的断言了同一件事（同类输入、同一期望），不是只沾边。
   至少抽查 10 条，其中必须包括：CLI record / submit 失败时"不写完成事件 / 不写计划"、`--check` 只读不联网、讲解模板小节与"无命中不等于不考"提示
   （第 49 轮事故，`AGENTS.md` 第 11–13 条）、round24 / round29 校验器的成功与错误路径、workspace 注册表拒绝的错误路径。发现没有真等价的，列必须改。
2. **迁移到新位置的断言**：确实不依赖旧版、在当前工作区实际运行（不是恒 skip）；`tests/contract/test_index_tree_verifiers.py` 的方法名仍叫
   `..._match_fixed_baseline`，而旧新对照已去掉——名实不符按 `AGENTS.md` 可读性判断。
3. **harness**：只接受固定哈希、拒绝 `HEAD`；旧版身份判别确实生效；`test_baseline_harness` 的变异证明是否真的证明了"原文件能抓到的变异，harness 实例也能抓到"。
   它从固定提交 `f52b8f6` 读取改写前的测试文件——这个依赖是否稳当。
4. **辅助收敛**：`tests/_fixtures.py` 的 `LegacyConfigView` / `git_source` 被四个契约测试直接引用、无兼容别名；这四个契约测试的**断言一行没改**（逐文件核对 diff）。
5. 被删的 8 个文件里有没有**不是对照**、而是独一份的现有行为测试被误删。
6. 自己做至少一处定点变异，确认对应保留 / 迁移测试变红。

## 规则

只跑与结论直接相关的单个模块或单条命令，**不跑全量**；复现用系统临时目录。结论 PASS / FAIL，分"必须改 / 建议改 / 不改"。

## 报告

`review/rounds/round-204-baseline-harness-review-sol61.md`。
