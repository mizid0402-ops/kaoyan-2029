# 评审：WP-H2 科目档案（00398b0）+ WP-C 修复（57dc49c，已合并 5e1f2ff）

遵守 `AGENTS.md`（不跑全量，只跑相关单模块；主工作区另有 luna 在改 `ky/knowledge/`，若测试受其中间态影响请注明）。
1. `git show 00398b0`：对照 `contracts/workspace.md` §2.5。重点：`verify_tree` 的科目解析（生效登记 → 补充视图登记 → 显式 `--subject`，冲突报错）是否正确；新科目演练 `tests/contract/test_subject_onboarding.py` 是否真证明"只改数据"；台账 / 投影 / 快照对 v2 档案的使用。
2. `git show 57dc49c`：你第 51 轮 M1/M2 是否修好；决议 D8（每项每完成日最多推进一次；早于上次 → out_of_order 跳过；同日同质 → replayed；同日异质 → 冲突，CLI 写入前预检）是否实现一致、有无新漏洞。
产物：`review/rounds/round-52-h2-wpc-review-sol-out.md`，每条 "必须改 / 建议改 / 不改"，两个提交分别 PASS / FAIL。
