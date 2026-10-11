# 任务书：修复 sol 第 73 轮对 WP-H4b（`4701bdc`）的意见

先读 `review/rounds/round-73-review-sol-out.md`（每条有复现输入）。遵守 `AGENTS.md`。H4b 已提交，你在主工作区改，不提交。
另有一个 worktree `../kaoyan-wt-h5` 在做别的包，不要碰。

## 必须改

1. **M1**：`resolve_mapping_chain` 先做重复边与环检查，**再**处理 `from == to` 返回空链。补 sol 的两个交叉输入（重复边 + 同版本请求；成环图 + 同版本请求）为负例。
2. **M2**：`review-queue` 省略 `--store` 时取 `workspace.review_queue`（写入目标，不走 `require()`；见 `contracts/workspace.md` §4）。补 check 与 migrate 各一条不传 `--store` 的正例。

## 决策者改定的规则（同时做）

3. **合并去重的优先级**改为：先保留 `state == "queued"` 的项；都不是 queued 时再按原规则；同档内按到期日最早，再按 `review_id` 字典序。
   理由：`suspended` 不进任何复习桶、过期 `scheduled` 只报 unreachable，只按到期日选会让合并后的知识点没有可执行的复习线（sol 第 73 轮）。
   规格 `contracts/syllabus_migration.md` 同步；补 sol 的两个输入（suspended 早到期 vs queued 晚到期；过期 scheduled vs queued）为精确测试，断言留下的是 queued 那项。

## 建议改（本轮一并做）

4. `_find_paths` 找到第二条路径即停（端口不变），不再枚举全部路径。
5. `migrate --apply` 遇到空链：打印明确的"无需迁移（from == to）"，**不写库**（manifest 版本不变），退出 0。补测试。
6. CLI 摘要注明各组可重叠（一项可同时在 renamed / merged / retired），规格同步一句。
7. 多步迁移测试补断言子项 `review_id` 与 `revision`；dry-run 测试的快照同时记录目录（空目录也算），证明目录树完全不变。

## 不做的

不改 `ky/knowledge/syllabus_mapping.py`、`ky/storage/`、`ky/workspace.py`。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_syllabus_migration_port tests.test_cli
```

每条新负例临时撤掉对应修复确认变红，再还原，写进报告。

## 报告

`review/rounds/round-75-wp-h4b-sol73-fixes-luna.md`：逐条落点、撤检查记录、验收输出。全量：未跑。不提交。含中文文件查 `???`。
