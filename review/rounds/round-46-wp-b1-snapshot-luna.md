# Round 46 — WP-B′1 状态快照迁移报告

## 改动文件

- `ky/schedule/state_snapshot.py`：删除 `REPO_ROOT` 和 `conventional_tree_path`；增加 `workspace` 参数、注册表输入优先级、缺失策略和配置科目交叉检查。移除对 `vocab_channel.DEFAULT_DB` 的隐式依赖。
- `ky/__main__.py`：只为 `snapshot` 子命令增加 `--workspace`，经 `load_workspace` 发现注册表；保留 `--vocab-db` 覆盖。
- `contracts/state_snapshot.md`：补充 M12 端口输入、输出 JSON 字段、只读与不推荐约束。
- `tests/test_state_snapshot.py`：从仓库注册表加载路径；文件和目录只读监视路径均从注册表取得；调用快照时传入 `workspace`。
- `tests/contract/test_state_snapshot_port.py`：临时工作区替换演练及 CLI 发现/失败不回退测试。
- 本报告。

未改投影、词汇通道、tools、`data/` 或其他 CLI 子命令；没有提交。开始实现前已查看 `git show f3539b8 -- ky/workspace.py`，据此使用已审阅的 `Workspace.require()` 和 `load_workspace()` 行为。

## 规格对应

- `contracts/workspace.md` §3.2：库函数不发现注册表，显式树映射/词库路径优先于工作区相应键。
- §4：已登记的树和词库通过 `workspace.require()` 检查；未登记树可以为 `None`；写入目标仍未纳入快照读取。
- §7 替换演练：临时注册表将 CS408 生效树切换到另一相对路径，并用补充树演示从 403 切换到 410。
- D1：仓库默认注册表仍指向 403 节点生效树；示例 CLI 输出也读到 403。

## 验收结果

1. `py -3.12 -m unittest tests.test_state_snapshot tests.contract.test_state_snapshot_port tests.test_cli tests.contract.test_workspace`：`Ran 58 tests`，`OK (skipped=1)`。跳过的是 Windows symlink 权限用例，原因 `WinError 1314`；其它状态快照、CLI、工作区契约项通过。
2. `py -3.12 -m ky snapshot --config tests/fixtures/config/config-minimal.yaml --items tests/fixtures/reviews/reviews-normal.yaml --date 2026-09-25 --json`：exit 0；输出 `as_of=2026-09-25`，CS408 `tree_total.count=403`、`tree_status=extracted`，politics 的 `tree_total=null`；词汇计数 `delivered=15`、`remaining=3137`。
3. `py -3.12 -m unittest discover -s tests -t .`：`Ran 460 tests in 106.339s`，`FAILED (failures=2, skipped=1)`。仅两个任务书列明的基线失败：
   - `tests.test_eng1_vocabulary.English1VocabularyRegressionTests.test_verifier_deterministic_check_and_mutations`：缺少 `%TEMP%\kaoyan-probe\claude2\dl\bv_e1_2024.pdf`。
   - `tests.test_round24_weighted_tree.WeightedTreeStructureTest.test_real_file_passes_validation`：缺少 `%TEMP%\kaoyan-probe\ghsurvey\downloads\408_syllabus_2022.pdf`。
4. `rg -n "parents\[2\]" ky/schedule/state_snapshot.py`：无匹配。

替换演练还验证了：改变临时注册表中的 CS408 树路径后分别读到 403 / 410；已登记但缺失的树按 `reference.knowledge_trees.cs408` 抛 `ContractError`；未登记 politics 为 `None`；注册表科目集合之外的 config 科目按 `subjects[3].subject_id` 失败；显式树与词库参数覆盖注册表。

CLI 检查：根目录不传 `--workspace` 时向上发现并 exit 0；坏的显式 `--workspace` exit 2 且不回退；设置 `KY_WORKSPACE` 后读到临时注册表的 410 节点树。

## 规格歧义与实现选择

1. `tree_paths` 是映射参数，而“显式 `tree_paths` > `workspace.knowledge_trees`”没有说明两者都存在且映射不完整时按科目回退还是整体覆盖。本实现把显式映射视作本次调用的完整树来源；映射未包含的科目没有树，不再从注册表补齐。
2. 规格只明确“两者都没给”时必须报错，没有定义无 `workspace` 但只提供树或只提供词库的行为。本实现按数据源独立处理：未显式提供的另一类来源不自动发现，也不猜默认位置；对应树/词库为 `None`。CLI 会先发现工作区，因此 CLI 不走该库函数的部分显式输入模式。
