# Round 46 任务书：WP-B′1 状态快照迁移到工作区注册表（M12）

你是实现者（续 WP-B 的会话，你已熟悉 `ky/workspace.py`）。只动 M12 状态快照这一个模块及其 CLI 入口。
依据：`contracts/workspace.md`（尤其 §3.2 优先级、§4 缺失策略、§7 替换演练）、`docs/阶段2.5-接缝收口.md` D1。

## 先读：WP-B 已提交（f3539b8），决策者审查时改了你的实现

- `require()` 不再接受 `state.*`（写入目标，规格 §4）；
- `require("reference.exam_indexes.X")` 现在报 "use require_all"；
- 经 `--workspace` / `KY_WORKSPACE` 选中时，错误信息不再重复字段路径；
- 新增 junction 版越界测试（Windows 无需特权）。
请先 `git show f3539b8 -- ky/workspace.py` 看一眼再开工。

## 要做的

1. **`ky/schedule/state_snapshot.py`**
   - 删除 `REPO_ROOT` 与 `conventional_tree_path`（不留兼容别名——它就是要消灭的约定式拼接）。
   - `build_snapshot(...)` 新增关键字参数 `workspace: Workspace | None = None`。数据源优先级（规格 §3.2）：
     - 树：显式 `tree_paths` > `workspace.knowledge_trees`；
     - 词库：显式 `vocab_db` > `workspace.vocabulary_db`；
     - 两者都没给时，`build_snapshot` **不自己发现注册表**，而是违约（`ContractError`，说明需要 `tree_paths`/`vocab_db` 或 `workspace`）。发现注册表是 CLI 的事，库函数保持"调用方给什么读什么"。
   - 缺失策略（规格 §4，写进 docstring）：
     - config 里的科目在注册表中**未登记树** → `tree_total=None`（合法，例如 politics）；
     - **已登记但文件缺失 / 类型错 / 越界** → `ContractError`（用 `workspace.require(...)`）；不再静默给 None。
     - 词库：已登记但缺失 → `ContractError`。显式 `vocab_db` 指向缺失文件时，保持现有行为（`vocab=None`），并在 docstring 写明这是显式覆盖的语义。
   - 交叉检查：给了 `workspace` 时，config 的每个 `subject_id` 必须 ∈ `workspace.subjects`，否则 `ContractError`（字段路径 `subjects[i].subject_id`）。
   - 不再 `from ky.schedule.vocab_channel import DEFAULT_DB`（词汇通道自己的迁移是 WP-B′3，别碰 `vocab_channel.py`）。
2. **`ky/__main__.py` 的 `snapshot` 子命令**：加 `--workspace`（语法 `ky snapshot … --workspace X`）。
   - 按规格 §3.1 发现注册表（显式 > `KY_WORKSPACE` > 向上查找），发现失败 → `contract violation: …` exit 2。
   - `--vocab-db` 仍覆盖注册表。
   - 其他子命令不动。
3. **规格 `contracts/state_snapshot.md`**（四件套之"规格"）：输入（注册表的哪些键、显式覆盖、缺失策略）、`--json` 输出的字段表（照现有 payload：`as_of / days_to_exam / subjects[] / vocab`，逐字段类型与含义，`tree_total` 为 null 的条件）、只读保证、不做推荐（`DoesNotPrescribeTest` 的约束）。
4. **测试**
   - 改 `tests/test_state_snapshot.py`：去掉 `conventional_tree_path`，改用仓库注册表 `load_workspace(REPO_ROOT / "kaoyan.workspace.yaml")`；只读测试的被监视文件改为从注册表取。
   - 新增 `tests/contract/test_state_snapshot_port.py`，含**替换演练**：在临时目录建一个工作区（注册表 + 把某科的树复制到**另一个相对路径**），快照读到新路径；
     把 cs408 指向 403 版时 `tree_total.count == 403`，指向补充视图的 410 版时为 410（证明"换树 = 改一行"）；已登记但缺失 → 违约；未登记 politics → `tree_total is None`；
     config 科目不在注册表 → 违约；显式 `tree_paths`/`vocab_db` 覆盖注册表。
   - CLI：`ky snapshot` 在仓库根不传 `--workspace` 仍 exit 0（向上发现）；`--workspace <坏路径>` exit 2 且不回退；`KY_WORKSPACE` 生效。
   - 所有临时文件用 `tempfile`，环境变量用 `mock.patch.dict`。

## 不做的

- 不动投影、词汇通道、tools、`data/`；不动其他 CLI 子命令。

## 验收

1. `py -3.12 -m unittest tests.test_state_snapshot tests.contract.test_state_snapshot_port tests.test_cli tests.contract.test_workspace` 全绿。
2. `py -3.12 -m ky snapshot --config tests/fixtures/config/config-minimal.yaml --items tests/fixtures/reviews/reviews-normal.yaml --date 2026-09-25 --json`：cs408 的 `tree_total.count` 为 403，exit 0。
3. 全量：只允许基线已知的 2 项失败。
4. `grep -rn "parents\[2\]" ky/schedule/state_snapshot.py` 无结果。

## 产物

不要提交。报告：`review/rounds/round-46-wp-b1-snapshot-luna.md`（改动文件、每条验收的实际输出摘要、规格歧义）。
