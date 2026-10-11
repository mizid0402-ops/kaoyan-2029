# 任务书：WP-E2 决策者审查意见（续你第 91 轮在主工作区的未提交改动）

决策者已审第 91 轮，设计落点正确。以下三处要改。遵守 `AGENTS.md`，不提交。
工作区里 `tests/contract/test_workspace.py` 的改动是决策者的，不要回滚；第 2 条你会在同一文件里加测试，改在它旁边即可。

## 必须改

1. **快照序列化只保留一份**（D7）：`ky/planning/port.py` 的 `_snapshot_payload` 复制了 `ky/__main__.py` `snapshot_main` 里 `payload = {...}` 的同一段映射，两份会各自漂移。
   在 M12（`ky/schedule/state_snapshot.py`）提供公开函数（例如 `snapshot_to_mapping(snapshot) -> dict`），CLI 与 M19 都用它；**`ky snapshot --json` 的输出必须逐字节不变**（用固定基线 `b120c71` 的 CLI 在同一临时工作区对比，写成测试或写进报告）。
   `contracts/state_snapshot.md` 注明这个函数是 JSON 形状的唯一来源。
2. **`Workspace.write_target` 核对已存在目标的类型**：规格 `contracts/workspace.md` §2.1 给每个键标了 F（文件）/ D（目录）。目标**已存在**时，类型不符 → `ContractError`（`expected a file` / `expected a directory`，路径为键名），与 `require()` 同一口径；不存在时照旧放行。
   然后删掉 `ky/__main__.py` 的 `_registered_queue_path`，缺省队列直接用 `workspace.write_target("state.review_queue")`（行为不变：`tests.test_cli.RegisteredQueueDefaultTest` 必须照旧通过）；M19 读队列同样只用 `write_target`。
   `tests/contract/test_workspace.py` 补：每个键类型不符的负例（表驱动，F 键放目录、D 键放文件），规格 §4 同步一句。
3. **包名**：`ky/planning/` 改名为 `ky/planner/`（避免与 M11 的 `ky/schedule/planning.py` 混淆）；规格、模块地图、导入同步。

## 同时补（sol 第 92 轮测试建议，改 `tests/test_cli.py`）

4. 注册表把 `state.review_queue` 登记成文件时：`snapshot`（不传 `--items`）与 `review-queue check`（不传 `--store`）各断言一次退出 2 且含 `expected a directory`。

## 不做的

不做 E3 / E4；不改提案格式、过期检查、manifest 格式。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_planner_port tests.contract.test_workspace tests.test_cli tests.contract.test_state_snapshot_port tests.test_state_snapshot tests.test_day_plan_store tests.contract.test_syllabus_migration_port
```

## 报告

`review/rounds/round-93-wp-e2-fixes-luna.md`：逐条落点、`snapshot --json` 逐字节对照结果、验收输出。全量：未跑。不提交。含中文文件查 `???`。
