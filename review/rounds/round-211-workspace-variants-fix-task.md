# 任务书：包 B 最后一处（sol61 第 210 轮 M1，窗口 `luna-a` 续做）

报告 `review/rounds/round-210-variant-tables-review-sol61.md` 的 M1。只改 `tests/contract/test_workspace.py`。

`test_single_error_variant_table` 用 `name.startswith("double-error-")` 过滤退役变体，误退役了三条**单错误**输入：
`double-error-schema-before-supplementary`、`double-error-schema-before-products`、`double-error-schema-before-settings`
（这三个块本来可选，缺失不是错误，实际只有 `schema_version='2'` 一处错误；原 `expected_success=False`）。

- 把退役判断从"按名字前缀"改为**显式列出**要退役的变体名（照你第 209 轮报告里的退役清单，去掉这三条），三条回到正式表，按原期望断言 `ContractError`。
- 在临时 `ky/` 副本里做一处变异（例如让 `schema_version` 接受字符串 `'2'`），确认这三条变红；命令与结果写报告。临时文件放系统临时目录。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_workspace
```

## 报告

`review/rounds/round-211-workspace-variants-fix-luna.md`：改动、更新后的计数（从生成器实际统计）、变异结果、验收输出原文。
写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。
