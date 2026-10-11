# WP-E1：CLI 注册表默认路径与写入目标边界

## 落点

- `contracts/workspace.md`：补充显式参数优先级、CLI 注册表缺省值和 `write_target()` 的路径边界契约。
- `ky/workspace.py`：新增 `Workspace.write_target(key)`。仅接受 `state.review_queue`、
  `state.plans`、`state.availability`、`state.routes`、`staging`、`projection`；目标无需存在，
  不创建路径；真实路径越出工作区时拒绝。
- `ky/__main__.py`：`day-plan submit|record`、`month-close` 的 `--store` 可选，默认使用
  `write_target("state.plans")`；`preflight`、`snapshot` 的 `--items` 可选，默认读取
  `workspace.review_queue`；缺注册表时退出 2 并提示显式参数或 `--workspace`。上述命令支持
  `--workspace`。`review-queue` 缺省写入路径改用 `write_target("state.review_queue")`。
  `day-plan record --review-store` 仍无默认值，帮助文本说明省略时只记完成事件，不推进队列。
- `tests/contract/test_workspace.py`：覆盖已登记目标、不存在的可选键和越界 junction。
- `tests/test_cli.py`：覆盖 record 注册表默认路径、snapshot 注册表队列默认值、显式 `--store`
  覆盖、以及无注册表且无显式存储路径时的退出码和提示。用例均写入临时目录。

## 验收

执行：

```text
py -3.12 -m unittest tests.contract.test_workspace tests.test_cli tests.contract.test_state_snapshot_port tests.contract.test_syllabus_migration_port
```

输出：

```text
Ran 88 tests in 19.530s

OK (skipped=1)
```

全量：未跑（按 `AGENTS.md`，由决策者提交前统一跑）。含中文文件连续问号扫描无命中。

## 建议

- `tools/aggregate_topic_weights.py` 写入的是 `reference.topic_weights`，它不属于本轮 `write_target()`
  的允许键，因此不能直接统一到该接口。若以后要统一这类参考数据产物，应另行定义对应的写入端口和
  目标策略；本轮未修改该工具。
