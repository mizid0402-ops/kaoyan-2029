# Round 92 Codex 复审：`b120c71`

范围仅为第 90 轮 C1、C2、W2 及 `_registered_queue_path` 接入 `review-queue` 的影响。使用 `git archive b120c71` 建立系统临时副本，补入被忽略的 `data/raw_materials/` 和注册表要求的 `products` 空目录；所有探针与撤修复均在该副本执行。未跑全量测试。

| 项目 | 意见 | 证据、可复现输入与判断 |
|---|---|---|
| C1：缺省队列经 junction 越界 | **不改** | `ky/__main__.py:96-105,220-224,533-542`：`preflight`、`snapshot` 的缺省队列都经过 `workspace.write_target("state.review_queue")`。复用第 90 轮探针：临时注册表填 `state.review_queue: linked/queue`，`linked` 是指向工作区外的 junction，外部放合法分片队列；两条 CLI 均返回 2，报 `state.review_queue: resolves outside the workspace`。撤掉 preflight 的 helper 调用后，新 junction 测试从通过变为失败（实际读入外部队列并返回 0）。原复现已关闭。 |
| C2：登记目录被设成平铺文件 | **不改；测试建议改** | `ky/__main__.py:102-105` 对存在的目标检查 `is_dir()`；`contracts/workspace.md:108` 明定此键是 `ReviewShardStore` 根目录。复用第 90 轮探针：登记 `data/flat.yaml` 并放有效平铺队列，省略 `--items` 的 `preflight`、`snapshot` 现在都返回 2，报 `state.review_queue: expected a directory`。把 helper 的类型判断临时改成 `if False`，新增文件测试失败，故核心检查可被测试抓到；但仅把 `snapshot` 的缺省调用退回 `workspace.write_target(...)` 时，`snapshot` 又返回 0，而新增 `RegisteredQueueDefaultTest` 仍 2/2 通过。建议把文件型登记输入也对 `snapshot` 断言一次。 |
| `review-queue` 接入后的行为 | **不改；测试建议改** | `ky/__main__.py:954-963` 仅在省略 `--store` 时调用 helper，显式 `--store` 仍直接使用给定路径。临时登记 `data/flat.yaml`，文件写两行 `schema_version: 1` 与 `items: []`：`review-queue check --workspace <注册表>` 返回 2、报 `expected a directory`；再加 `--store <该文件>` 返回 0、输出 `OK queue references (0 items)`。合法登记分片目录的既有单测 `tests.contract.test_syllabus_migration_port.SyllabusMigrationCliTests.test_check_uses_registered_default_store` 通过。默认文件被拒符合目录契约，显式覆盖保持原行为。但撤掉 `review-queue` 分支的 helper 后，新增 `RegisteredQueueDefaultTest` 仍 2/2 通过；建议加一条文件型缺省队列的 `review-queue check` 断言。 |
| W2：`write_target` 允许键表驱动测试 | **建议改** | `tests/contract/test_workspace.py:496-514` 现逐个覆盖规格列出的六个允许键及两个禁止键；临时删去 `ky/workspace.py:194` 的 `staging` 映射，该测试报 `staging: not registered`，已关闭第 90 轮“删键仍绿”的缺口。断言只检查目标位于工作区内：临时把 `"staging": self.staging` 改成 `"staging": self.plans`，同一测试仍通过，不能抓错键映射。建议按登记值逐键断言返回路径，禁止键再核对错误字段。实现本身的六键集合与 `contracts/workspace.md:226-230` 一致。 |
| C4：未增加 `--review-store` 回归 | **不改** | 本提交未触及 `day-plan record` 的 `--review-store` 分支；第 90 轮该项是建议测试，并非阻断修复。继续列为后续可补的回归，不据此否决本提交。 |

定向验证：`py -3.12 -m unittest tests.contract.test_workspace` 为 22 项通过（1 项按条件跳过）；`py -3.12 -m unittest tests.test_cli` 为 40 项通过；上表的 `review-queue` 登记目录单测 1 项通过。所有撤修复只改系统临时归档并已还原。

**整体：PASS。** C1、C2 的原输入已被正确拒绝；余下问题是三个入口与键到路径映射的回归断言不够完整，建议补强测试。
