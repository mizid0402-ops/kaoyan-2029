# 任务书：WP-E1 CLI 从注册表取状态路径 + 写入目标的越界检查（M14 / M0）

先读仓库根 `AGENTS.md`，再读 `contracts/workspace.md`（§3.2 显式参数优先级、§4 存在性）、`ky/workspace.py`、`ky/__main__.py`、`docs/阶段2.5-接缝收口.md` WP-E 行。

## 为什么做

WP-E（规划者端口）的第一步。现在 `ky day-plan submit|record`、`ky month-close` 都**必传** `--store`，`ky preflight` / `ky snapshot` 必传 `--items`，
即使注册表已经登记了 `state.plans`、`state.review_queue`。另外，写入目标（`state.*`、`staging`、`projection`）不走 `require()`，
**没有统一的越界检查**：H5 第 83 轮就因为写入目标经 junction / 硬链接可能写到工作区外而各自补了一套判定（`tools/aggregate_topic_weights.py:_write_target`）。

## 决策者已定的设计

1. **M0 新公开接口** `Workspace.write_target(key) -> Path`：只接受 `state.review_queue`、`state.plans`、`state.availability`、`state.routes`、`staging`、`projection`；
   未登记（可选键未填）→ `not registered`；解析后的真实路径（`resolve(strict=False)`，跟随已存在部分的链接 / junction）落在 `Workspace.root` 外 → `resolves outside the workspace`；
   **不要求存在**、不创建任何东西。规格 `contracts/workspace.md` §4 写明，契约测试 `tests/contract/test_workspace.py` 补正例、未登记、junction 越界（照已有 junction 测试写法，无权限时 skip）。
2. **CLI 缺省路径**（`ky/__main__.py`）：
   - `day-plan submit|record`、`month-close` 的 `--store` 改为可选，缺省 `workspace.write_target("state.plans")`；这些子命令都接受 `--workspace`（没有的补上），注册表按现有 `find_workspace` 规则发现。
   - `preflight`、`snapshot` 的 `--items` 改为可选，缺省 `workspace.review_queue`（这是**读**：目录不存在时照现有 `load_review_queue` 的报错，退出 2）。
   - `--review-store` **保持显式、没有缺省**：它决定 `record` 是否推进复习队列，给缺省值会改变现有行为；在帮助文字里说明"不传则只记录完成事件"。
   - `review-queue` 子命令的缺省 `workspace.review_queue` 改走 `write_target("state.review_queue")`（它会写）。
   - 显式参数仍优先（`contracts/workspace.md` §3.2）。没有注册表且没给显式路径 → 契约错误，提示加 `--store` / `--items` 或 `--workspace`，退出 2。
3. 不改 `tools/aggregate_topic_weights.py`（它的目标是 `reference.topic_weights`，不在 `write_target` 范围内；在报告"建议"里写能否统一）。

## 不做的

不做 staging、输入包、RoutePlan 落盘、availability（E2–E4）。不改存储格式。

## 测试（只写这些）

- `tests/contract/test_workspace.py`：`write_target` 三类（正例、未登记、越界）。
- `tests/test_cli.py`：`day-plan record` 不传 `--store` 写到注册表 `state.plans`；`snapshot` 不传 `--items` 读注册表 `state.review_queue`；显式 `--store` 覆盖注册表；无注册表且无显式路径 → 退出 2 且提示。用临时工作区（照该文件已有的 `_question_workspace` 写法），**不要写仓库真实的 `data/plans`、`data/review_queue`**。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_workspace tests.test_cli tests.contract.test_state_snapshot_port tests.contract.test_syllabus_migration_port
```

## 报告

`review/rounds/round-88-wp-e1-luna.md`：落点、验收输出、建议。全量：未跑。不提交。含中文文件查 `???`。
