# WP-E2 决策者审查意见修复报告

## 逐条落点

1. **M12 快照序列化单一来源**：在 `ky/schedule/state_snapshot.py` 新增公开
   `snapshot_to_mapping(snapshot)`，同时更新 `__all__`。`snapshot_main` 和
   `ky/planner/port.py` 都使用该函数；删除 M19 原有 `_snapshot_payload` 副本。
   `contracts/state_snapshot.md` 与模块地图注明唯一来源。
2. **`write_target` 的现存目标类型检查**：`ky/workspace.py` 为四个目录键与两个文件键
   加入类型检查；目标尚不存在时保持原放行行为，类型错误携带登记键路径。
   删除 `ky/__main__.py` 的 `_registered_queue_path`，preflight、snapshot、review-queue
   默认队列均直接调用 `workspace.write_target("state.review_queue")`；M19 也直接使用该端口。
   `contracts/workspace.md` §4 补充类型规则。`tests/contract/test_workspace.py` 添加六个键的
   表驱动反类型用例，并保留决策者已有修改；`tests/test_cli.py` 覆盖 snapshot 与
   `review-queue check` 对错误队列类型均返回 2 并报告 `expected a directory`。
3. **包名**：将 M19 从 `ky/planning/` 移至 `ky/planner/`，同步 CLI、契约测试、规格和模块地图。
   `ky/schedule/planning.py` 保持不变。

## `snapshot --json` 固定基线对照

用 `git archive b120c71` 建立基线副本；基线 CLI 与当前 CLI 在同一个临时工作区、同一配置、
队列、日期及参数下分别执行 `snapshot --json`。两边退出码均为 0，stderr 均为空，stdout
逐字节相同：各 285 字节，SHA-256 均为
`dfcd077e283225190b8e38498885264540b8c781d9b39df4610ca8b7e883b5d0`。

## 验收

执行任务书列出的七模块命令：

```text
py -3.12 -m unittest tests.contract.test_planner_port tests.contract.test_workspace tests.test_cli tests.contract.test_state_snapshot_port tests.test_state_snapshot tests.test_day_plan_store tests.contract.test_syllabus_migration_port
```

结果：`Ran 137 tests in 22.020s`，`OK (skipped=1)`。

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。未提交。
