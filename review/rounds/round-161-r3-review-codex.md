# WP-R3 独立评审：FAIL

## 范围

复核主工作区未提交的 `contracts/config.md`、`contracts/day_plan_store.md`、
`contracts/ledger.md`、`ky/models.py`、`ky/ledger/material.py`、
`ky/storage/day_plan_store.py` 及对应 5 个测试文件。重点是非 UTF-8 台账、重复 YAML
键、手写日期与分钟、`subject_minutes: []`、错误路径和正常输入兼容性。
未检查同时进行的 C5、C1 与 G3d 文件；未改动仓库源码、未提交、未跑全量。

## 必须改

### R3-M1：严格 YAML 读取使原本有效的合并键台账失效

- **严重度：MAJOR。** 合法的手写台账原先可读，现在读取时报受控错误。
- **位置：** `ky/ledger/material.py` 的 `_read_ledger_yaml` 改为调用
  `ky.models.load_yaml_text`；该模块 `_StrictSafeLoader.construct_mapping` 在
  `super().construct_mapping` 展开 YAML merge 键以前，对 `<<` 的键节点调用
  `construct_object`，触发 `ConstructorError`。
- **触发：** 用 `tests.test_ledger.local_material()` 生成一条有效资料，将其
  `rights.status: official_public` 写成语义相同的
  `rights: {<<: {status: official_public}, ...}`。这没有重复声明字段，只是正常的
  YAML 合并写法。
- **实测：** `yaml.safe_load` 解析后交给 `validate_ledger` 可得到 1 条有效资料；
  当前 `load_ledger` 报 `LedgerError: invalid YAML: could not determine a constructor
  for the tag 'tag:yaml.org,2002:merge'`。该输入在改动前的
  `yaml.safe_load -> validate_ledger` 路径成立。
- **预期：** 继续接受没有重复显式字段的 YAML 合并键；对真正重复写出的键仍报
  `LedgerError`，防止后写值静默覆盖。
- **修复方向：** 在严格 loader 中识别 merge 键节点，不提前对其调用
  `construct_object`；保留显式键的重复检查，并让父类完成 merge 展开。为合并键
  正例和显式重复键反例补定向回归测试。

## 已确认符合要求

- 非 UTF-8 台账与普通重复键均转为带文件路径的 `LedgerError`；CLI 退出 2，没有
  traceback。共享 YAML 解析器现为 `ky.models` 的公开 `load_yaml_text`。
- 配置的非字符串未知键先于字符串未知键报告，`.path` 保持字符串；根层与科目
  层新增测试均通过。
- `parse_day_plan` 接受 YAML 日期标量；非法日期字符串、字符串/布尔/浮点分钟数、
  `subject_minutes: []` 均以字段路径上的 `StorageError` 拒绝。CLI 实测非法日期
  和字符串分钟数退出 2，未写存储目录。
- 实际 `data/materials.yaml` 经旧 `yaml.safe_load` 和新 `load_yaml_text` 解析所得
  对象相同，当前 49 条资料不受此回归影响。

## 验证

- WP-R3 新增的定向用例：12 项通过。
- 原有资料台账契约类与端口模块：56 项通过。
- 相关差异的 `git diff --check` 通过。
- 合并键兼容性探针：旧解析与语义校验通过；新 `load_ledger` 失败。
- 全量测试未跑，遵守 `AGENTS.md` 最小验证要求。

## 门禁结论

**FAIL。** R3-M1 是正常手写 YAML 在本轮改动后无法读取的可复现回归。修复并通过
定向测试后，只需复审此项及直接回归。
