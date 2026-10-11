# WP-E2 第 94 轮意见修复报告

## 修改落点

涉及文件：`README.md`、`contracts/planner_port.md`、`docs/模块地图.md`、`ky/planner/port.py`、`ky/schedule/review_clip.py`、`ky/__main__.py`、`ky/storage/atomic.py`、`tools/aggregate_topic_weights.py`、`tests/contract/test_planner_port.py`。

1. **H1 信任边界**：`contracts/planner_port.md` 新增信任边界，说明本机无调用者认证，AI 进程只写 `staging/`，由用户本人或信任的编排者执行两种 `day-plan submit`；`actor` 是审计声明，不是认证。`--plan` 作为用户直接通道，写入 `human/null`。所有 staging 提案（包括 `actor: human`）现在都必须提供合法 `input_hash`，并新增缺哈希负例。README 硬不变量②后新增指向该节的一句话。
2. **H2 原子替换**：新增 M13 公共函数 `ky/storage/atomic.py:replace_bytes(path, data)`，用同目录临时文件和 `os.replace` 替换目录项，避免打开已有 inode 写入、进而写穿硬链接。M19 输入包与 `tools/aggregate_topic_weights.py` 改用该函数。`DayPlanStore._write_atomically` 保留：它除原子替换外还接收并执行重读校验回调，语义和签名不同。契约测试建立 staging 目标到临时目录外文件的硬链接，确认输入包生成后外部原字节未变；硬链接不可用时按要求 skip。
3. **I1 预检载荷**：在 M9 `ky/schedule/review_clip.py` 新增公开 `preflight_to_mapping()`，CLI 和 M19 共用，输出包含 `subject_allocation`。输入包的 `review_clip` 放完整预检载荷，但去掉载荷中的简版 `config`；完整、经验证的 `KaoyanConfig` 只保留在输入包顶层 `config`，避免同时暴露两种配置形状。模块地图同步 M9、M13 行。
4. **I2 过期语义**：规格明确过期表示规划者可见的输入包内容变化；源数据变化若不改变包内容则不触发，例如不入包的复习项标题、解析时丢弃的 YAML 注释/格式。
5. **E1 并发边界**：规格声明检查在存储写入前执行，与写入不属于同一事务；并发变化可能发生在检查之后，因此不保证写入瞬间的新鲜度。
6. **S1 版本类型**：提案 `schema_version` 现在要求精确 `int` 且值为 1，布尔值被拒；新增 `true` 负例。
7. **M1 来源范围**：规格说明 `day_plan_provenance(day)` 只返回当前版本的来源；历史版本来源不保留，尽管版本化计划文件仍在。

## 固定基线输出对照

从固定提交 `8f31a05` 用 `git archive` 解出旧版，与当前工作区分别运行 `ky preflight --json`。两次使用同一临时目录中的配置、复习输入、日期和工作目录。

| 版本 | 退出码 | stdout 字节数 | SHA-256 |
|---|---:|---:|---|
| `8f31a05` | 0 | 1282 | `d365b5f2059e36eee6e149a2bcaa11388198a5e753c13aa3dafef6f52b78d9c4` |
| 当前工作区 | 0 | 1282 | `d365b5f2059e36eee6e149a2bcaa11388198a5e753c13aa3dafef6f52b78d9c4` |

原始 stdout 字节完全相同（`byte_equal=True`），stderr 为空。预检 JSON 的映射逻辑因此迁移到公开函数后仍与固定基线逐字节一致。

## 撤修复确认

每次仅在内存工作区临时移除一项防护，执行对应单测后立即恢复代码。三次探测均按预期以失败退出 1：

- H1：临时允许 staging 中 `input_hash: null`，`test_human_staging_proposal_requires_input_hash` 失败，错误为未抛出预期的 `ContractError`。
- S1：临时恢复普通 `schema_version != 1` 比较，`test_boolean_schema_version_is_rejected` 失败，`true` 被接受且未抛预期错误。
- H2：临时将输入包写回 `target.write_bytes(...)`，`test_input_package_replaces_hard_link_without_writing_through` 失败，工作区外硬链接内容被改写为输入包。

每项撤修复后都已还原；后续验收在完整修复状态运行并通过。

## 验收

```text
py -3.12 -m unittest tests.contract.test_planner_port tests.test_cli tests.test_day_plan_store tests.contract.test_topic_weights_port tests.test_review_scheduler tests.test_contracts
Ran 192 tests in 21.393s
OK
national.json: write=0 unchanged=0 missing=1 rejected=0 single_node=0 spread=0
   - missing from topic_weights.json: cs408-2023-01
school.json: write=1 unchanged=0 missing=0 rejected=0 single_node=1 spread=0
TOTAL write=1 unchanged=0 missing=1 rejected=0 single_node=1 spread=0
```

```text
py -3.12 tools/aggregate_topic_weights.py --check
topic_weights.json matches registered batches (numeric equality, no tolerance; 0.0 == -0.0)
```

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。未提交。

## 建议

如果以后需要抵御同一用户会话内的并发写入，应另行定义 staging 和状态存储的写锁/条件提交端口；本次按决议只记录过期检查与写入之间的竞态边界，没有改变比较方式。
