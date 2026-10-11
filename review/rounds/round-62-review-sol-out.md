# Round 62 Codex 复审：`ed456ec`

仅复审第 60 轮 C2 的两个探针、直接相关写入路径与两条 L1 建议。代码和测试来自 `git archive ed456ec` 的系统临时目录；未使用主工作区的 WP-H3 改动，未跑全量测试。

| 项目 | 判断 | 可复现输入、结果与证据 |
|---|---|---|
| C2 混合旧队列绕过 | **不改：原探针已关闭** | schema-1 队列含已复习 `rv1` 和未复习 `rv2`，尝试推进 `rv2`：现在 `_review_queue_plan` 在分类前按**整条队列**拒绝（`ky/storage/day_plan_store.py:391-399`）。重跑第 60 轮探针，先重放 `rv1` 报 `calculated_completion_ids`，再推进 `rv2` 也报同一违约；manifest 保持 schema 1，旧 `rv1` 不再获得重放机会。`tests.test_review_queue_advance` 18 项通过。 |
| C2 CLI 先写事件 | **不改：原探针已关闭** | 对含已复习项的 schema-1 队列运行 `ky day-plan record --review-store <旧队列> --done <事件>`：临时探针得到退出 2、`event_written=False`、队列 phase 仍为 1；`ky/storage/day_plan_store.py:328-333,391-399` 使预检先拒绝，`ky/__main__.py:659-674` 因而未写不可覆盖的事件。`tests/test_cli.py:724-764` 还断言无 traceback、日计划存储没有文件、队列文件逐字节未变。该模块 34 项通过。 |
| 公开写入路径 | **不改** | 同一混合旧队列，分别调用 `store.write(store.load())`、`write_review_queue(root, store.load())`、`store.upsert(rv3)`、`store.delete('rv2')`，均抛 `StorageError(calculated_completion_ids)` 且 manifest 字节未变。`write_review_queue`、`upsert`、`delete` 最终都调用 `write`（`ky/storage/review_shards.py:459-468,585-609`）；兜底有效。 |
| 私有 `_commit` 技术绕过 | **建议改** | 上述同一 schema-1 混合队列，**不调用** `upgrade_legacy_queue`，直接 `store._commit(store.load(), ())`：确实成功写出 schema-2 manifest；临时探针输出 `direct_commit 2 True`。`ky/storage/review_shards.py:470-476` 的 `_commit` 无旧历史检查，而升级入口在 628 行调用它。仓库当前只有受保护的 `write` 和显式升级这两处调用；`_commit` 不是契约公开端口，`AGENTS.md` 也禁止跨模块依赖私有接口。因此这是直接调用私有方法才触发的防误用缺口，不据此否定已授权的公开写入路径。建议将旧历史检查收进 `_commit`，由升级入口传明确确认参数，并补私有入口防误用测试。 |
| 显式升级边界 | **不改** | `upgrade_legacy_queue(store, acknowledge_unknown_history=False)` 在现有测试中拒绝；临时探针另确认：无 manifest → 报缺失且不创建根目录；schema 2 → 报 `schema_version`；空 schema-1 队列带确认 → 成为 schema 2、仍为 0 项；再次升级 → 报 `schema_version`。`ky/storage/review_shards.py:614-628` 先做确认、存在性、版本检查，再调用内部提交。这里的合法升级语义符合决策，问题仅是上一行的内部入口可绕过确认。 |
| 三条新增回归测试 | **建议改** | 混合队列测试 `tests/test_review_queue_advance.py:250-272` 分别检查预检、推进和 `upsert` 抛错及 manifest 原字节，撤掉任一相应防线会变红；CLI 测试 `tests/test_cli.py:724-764` 核实退出码和两个存储均未变，也足够强。两者没有直接调用 `_commit`，因而都未捕获本轮绕过。L1 诊断测试 `tests/test_ledger_cli.py:73-83` 只断言 stderr 含 `KY_WORKSPACE`；撤回上轮保留来源的修复会变红，但建议同时断言错误含所指定的 `missing.yaml` 路径，锁住真正的来源信息。 |
| L1 两条建议 | **不改** | `tests/test_ledger_cli.py:36-44` 从台账条目的科目集合推导 `--subjects`，并排除台账自有分类，已去掉写死的四个科目；`ky/__main__.py:297-303` 保留发现异常文本。临时归档的 `tests.test_ledger_cli` 6 项通过。`KY_WORKSPACE=<不存在的 missing.yaml>` 时，输出同时包含 `KY_WORKSPACE`、目标路径和补 `--subjects`/`--workspace` 的提示；未改变已定发现顺序。 |

## 整体结论：**PASS**

第 60 轮两个实际故障已修复，公开写入路径守住旧队列，显式升级的缺失、重复和空队列边界也符合既定取舍。私有 `_commit` 可被主动调用来绕过确认，建议加一道内部防误用检查；当前仓库没有经该入口绕过保护的受支持调用路径。
