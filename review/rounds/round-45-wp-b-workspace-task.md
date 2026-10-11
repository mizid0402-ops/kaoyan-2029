# Round 45 任务书：WP-B 工作区注册表（实现）

你是本轮的**实现者**。Claude（决策者）与 gpt-6-sol（独立评审）审你的 diff。
**唯一依据：`contracts/workspace.md`**（已经过 gpt-6-sol 审阅，见 `review/rounds/round-44-workspace-spec-codex.md`）。
规格与本任务书冲突时以规格为准，并在报告里指出冲突。

## 要做的

1. **`kaoyan.workspace.yaml`**（仓库根）：内容照规格 §2 示例；`knowledge_trees.cs408` 指向 403 版 `knowledge_tree.yaml`（D1）。
   文件使用 LF 换行。
2. **`ky/workspace.py`**：规格 §6 的接口，全部行为照 §2–§5。
   - 复用 `ky.models` 里已有的严格 YAML 读取（拒绝重复键的 `_read_yaml_file` / `_StrictSafeLoader`）、`ContractError`、`_require_mapping`、`_reject_unknown_keys`，
     不要再复制一份（审查报告已指出这组辅助函数被复制了 4 次）。若需要把它们从私有改为模块内公开名，保持旧名可用。
   - 加载是纯读：不创建目录、不写文件。
   - 符号链接越界测试：Windows 上建 symlink 可能需要权限，建不了就 skip 并在 skip 理由里说明；可以尝试 junction（`mklink /J` 或 `_winapi.CreateJunction`）。
3. **`tests/contract/__init__.py` + `tests/contract/test_workspace.py`**：规格 §7 的全部 8 条（不含"替换演练"，那属于 WP-B′）。
   - 以加载函数为参数组织（例如 `LOADERS = [load_workspace]` + `subTest`），让替换实现能注册进来重跑。
   - 所有临时文件用 `tempfile`；测试 `KY_WORKSPACE` 时用 `unittest.mock.patch.dict(os.environ, …)`，不得泄漏到其他测试。
   - 确认 `py -3.12 -m unittest discover -s tests -t .` 能发现 `tests/contract/` 下的测试。

## 不做的

- **不迁移任何消费方**（快照、投影、词汇通道、tools 都不动）——那是 WP-B′，一个模块一个子包。
- 不改 `data/` 下任何文件，不改被登记文件的内容。
- 不给 CLI 加 `--workspace`（随 WP-B′ 各消费方迁移时加）；现有命令在没有注册表时的行为必须完全不变（规格 §3.2）。

## 验收

1. `py -3.12 -m unittest tests.contract.test_workspace -v` 全绿，逐条对应规格 §7。
2. `py -3.12 -m unittest tests.test_contracts tests.test_cli` 全绿（确认对 `ky.models` 的改动没有破坏旧行为）。
3. 全量 `py -3.12 -m unittest discover -s tests -t .`：只允许基线已知的 2 项失败
   （`test_eng1_vocabulary…test_verifier_deterministic_check_and_mutations`、`test_round24_weighted_tree…test_real_file_passes_validation`）。

## 产物

不要提交。报告写到 `review/rounds/round-45-wp-b-workspace-luna.md`：改了哪些文件、规格每一节对应的实现位置、§7 每一条对应的测试名、验收命令的实际输出摘要、你发现的规格歧义。
