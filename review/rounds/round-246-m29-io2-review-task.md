# 第 246 轮任务书：WP-IO2 实现评审（合并后状态）（gpt-6.1-sol，续 sol61-m18）

## 范围

主工作区正在进行的合并（`git merge --no-ff --no-commit wip/io2`，尚未提交）：luna-c 的 IO2（ics 导入、日历导出、公用预览；实现者报告 `review/rounds/round-237-m29-io2-luna.md`，
任务书 `review/rounds/round-237-m29-io2-task.md`），以及决策者在合并时做的整合：
- 解决 `ky/__main__.py` 与 IO3（`import-pdf`）的子命令冲突；`import-pdf` 加 `--config`；
- M28b 已合并（`daily_base_minutes` 改为按日期 / 路线 / 复盘设置解析）：新增公开 `base_resolver(workspace, config)`（读一次路线、逐日取基数），
  预览与导出改为逐日基数（原实现用一个配置基数套整个区间）；
- `import-pdf` 改用公用 `preview_lines`，删去 PDF 模块自己的网格函数；
- `tests/contract/test_timetable_io_port.py` 末尾新增 `TimetableIOBaseResolverTests`。
用 `git diff --cached` 与 `git diff` 看改动（合并暂存区 + 工作区）。

## 请判断

1. 是否符合 `contracts/timetable_import.md` §4、§6、§7 与第 225–227 轮你列出的细节（尤其 §4 的 12 步顺序、本地日期口径、覆盖规则、`DURATION`、有限展开；
   §6 课程事件合并条件、UID 身份组、`TRANSP`、空选择、确定性字节、隔离与只写一次发布）。
2. 实现者自选的四处歧义是否合理。
3. 决策者的整合改动是否正确（逐日基数、`import-pdf` 预览、冲突解决）；有无把 IO3 或 M28b 的行为改坏。
4. `AGENTS.md` 已知缺陷与 D7；测试是否有实质断言（sol 225 §二表格与 226 的 N3 / N5 是否都有用例）。
5. 依赖：`pyproject.toml` 新增三项是否与规格 §7 一致。

## 输出

`review/rounds/round-246-m29-io2-review-sol61.md`：PASS / FAIL；必须改（附可复现输入）/ 建议改 / 不改；安全登记单列。

## 禁止

不联网；只写这一份报告；不修改其他文件；不读仓库外文件；报告里不写个人数据。只跑相关单个模块或单项，不跑全量。
