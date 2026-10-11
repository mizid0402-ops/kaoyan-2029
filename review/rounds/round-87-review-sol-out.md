# Round 87 Codex 复审：`7529ce9`

范围：只审 `git show 7529ce9` 对第 86 轮 M1/M2 与建议项的处理。用 `git archive 7529ce9` 解到系统临时目录，按前法补齐 Git 忽略的原始资料；探针和撤修复变异只写临时归档。未跑全量，未碰真实学习状态。下列行号指 `7529ce9`。

| 检查 | 意见 | 证据与可复现输入 |
|---|---|---|
| M1 原复现 | **不改：原输入已关闭** | `ky/storage/day_plan_store.py:624-633` 解析事件后比对 `event_path` 与 `_completion_event_path(event.day)`。把同一份由 `write_completion_event(day=2026-09-10, delivered_words=[alpha])` 生成的合法 YAML，分别移至 `state/misc/completion--junk.yaml` 和 `state/2026-09/completion--2026-09-11.yaml`：两者实测均抛含 `not at its store path` 的 `StorageError`，不再计入 `alpha`。`StorageError` 继承 `ContractError` (`:88`)，所以快照 CLI 的现有捕获也涵盖此错；无需另加异常类型。 |
| M1 路径覆盖范围 | **必须改** | 新规格 `contracts/state_snapshot.md:53-55` 明说“其他位置”的 `completion--*.yaml` 都是契约违规；实现只遍历 `root.glob("*/completion--*.yaml")` (`ky/storage/day_plan_store.py:624`)。同一份合法 YAML 单独放在 `state/completion--2026-09-10.yaml`，或 `state/2026-09/day_plans/completion--2026-09-10.yaml`，`delivered_words()` **均正常返回空集**，没有拒绝，也丢掉了 `alpha`。这仍是 M1 的静默状态遗漏。最小修法是发现根目录下所有符合该文件名模式的候选，再沿用当前“必须等于存储标准路径”的校验；补根目录和多层目录回归。若决策者只打算检查直属月份目录，需收窄规格，但这会允许放错位置的完成记录无声失效。 |
| M1 合法同目录文件 | **不改** | 在 `2026-09` 下保留标准完成事件，同时放入 `day_plans_manifest.yaml`、`month_close.yaml` 哨兵文件，`delivered_words()` 实测仍只返回 `{'alpha'}`。扫描模式只匹配 `completion--*.yaml`；存储自己的其他月文件不会误伤。 |
| M2 原复现 | **不改：PASS** | `ky/__main__.py:511-515` 增加捕获 `CompletionError`。定向运行 `tests.contract.test_state_snapshot_port.StateSnapshotWorkspaceCliTests.test_corrupt_completion_event_is_a_contract_violation`：在标准事件路径写 `not: a completion event`，断言 CLI 返回 2、含 `contract violation:`、无 `Traceback` (`tests/contract/test_state_snapshot_port.py:248-269`)，通过。临时撤去该捕获，单测变红。 |
| `--date` 与固定基线 | **不改** | `tools/daily_words.py:125-132` 已删除无作用参数；直接传 `--date 2026-09-25` 实测被 `argparse` 拒绝。`tests/test_eng1_vocabulary.py:111-211` 仍钉 `162a9e1` Git blob，旧工具收到 `--date=2098-01-01` 等日期，新工具不传日期；旧库预置的是 2097 年已投放词，故三个 2098 日期均走旧工具的“新批次”分支，与新工具的状态集合可比。新输出只剔除新增 `vocab:` 片段后按原始字节与旧 stdout 比，库哈希也核对；固定基线单测在临时归档 1/1 通过。日期参数本身的删除没有专门断言：临时恢复一个无作用 `--date` 参数后该基线单测仍绿，建议加一条拒绝旧参数的 CLI 断言，但不影响字节对照的可信度。 |
| R2 说明 | **不改** | `contracts/state_snapshot.md:56-57` 明确 `remaining` 是可选关系的词形行数，而 `daily_words` 投放的是词族；与 `contracts/vocabulary.md` 的行计数及第 86 轮 `work` / `worked` 等反例一致。这里“不可互相换算”宜理解为不能直接拿两项计数互作余量；措辞足够清楚。 |
| R3、R5 取舍 | **不改** | R3 的跨 500 行测试未收录，但第 86 轮已用前 550 个词族实测新旧随后 20 项相同；这是一条可保留的测试建议，不是本提交阻断项。R5 真实迁移后同日不能再记复习的事实仍成立；`docs/阶段2.5-接缝收口.md:36,97` 与 `交接文档.md:76` 已记录用户决定不迁移旧 15 条，故不再作为本次放行条件。迁移工具若将来启用，仍需重新评估该限制。 |
| 回归测试撤修复 | **建议改** | 定向模块 `tests.test_day_plan_store` 19/19、`tests.contract.test_state_snapshot_port` 11/11，通过；固定基线单测 1/1。临时把 M1 的路径比较改成恒假，新 M1 单测红（2 个子用例）；把 M2 的 `CompletionError` 捕获撤去，新 M2 单测红。现有 M1 测试 (`tests/test_day_plan_store.py:231-246`) 只覆盖 `*/completion--*.yaml` 已能发现的两个位置；它对上面的根目录、多层目录漏检仍绿，应补相应输入。 |

**整体：FAIL。** M1/M2 原复现都已关闭，且正常月文件未受影响；但 M1 新规格覆盖的根目录及多层目录完成事件仍被静默忽略，放行前需要闭合该扫描范围。
