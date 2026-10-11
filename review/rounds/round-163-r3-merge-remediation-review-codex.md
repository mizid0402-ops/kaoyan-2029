# WP-R3 合并键修复定点复审：FAIL

## 上轮阻断项

- **R3-M1 已解决。** `ky.models._StrictSafeLoader.construct_mapping` 对单个
  YAML merge 键不再提前调用 `construct_object`，交给父类展开。我用上轮同型的
  `rights` 合并键台账调用 `load_ledger`，得到 1 条有效资料。新增测试也覆盖了
  合并键加显式覆盖字段，以及普通字段重复声明的拒绝。

## 修复引入的直接回归

### R3-M2：重复的 merge 键被静默接受

- **严重度：MAJOR。位置：** `ky/models.py` 的
  `_StrictSafeLoader.construct_mapping`；看到 tag 为 `tag:yaml.org,2002:merge`
  就 `continue`，没有把该键纳入重复检查。
- **触发：** 在有效台账一条资料的 `rights` 映射中，把原有
  `status: official_public` 替换成连续两行
  `<<: {status: official_public}`。这是同一映射内重复写出的 `<<` 键。
- **实测：** `load_ledger(path, subject_ids={"cs408"})` 对单行和双行写法都返回
  1 条资料，双行没有报错。当前新增的“显式重复”测试只重复普通
  `review_index` 字段，未覆盖重复 merge 键。
- **预期：** `contracts/ledger.md` §2 规定 YAML 任一层映射的重复键以
  `LedgerError` 拒绝；第二个 `<<` 应被拒绝，同时单个 `<<` 应继续合法展开。
- **修复方向：** 扫描 merge tag 时把它作为已见键记录，第二次出现发出
  `_DuplicateKeyError`；仍让父类展开第一次 merge。补单个 merge 接受和重复
  merge 拒绝的定向回归。

## 验证与结论

- `py -3.12 -B -m unittest tests.test_ledger.LedgerFileReadingTest`：3 项通过。
- 独立临时台账探针：单个 `<<` 接受 1 条；重复 `<<` 仍接受 1 条，证实 R3-M2。
- 只读评审；未改源码、未跑全量测试。

**FAIL。** 上轮的单 merge 兼容性回归已修，但修复使重复键禁令出现缺口。
下一轮只需核对 R3-M2 和直接回归。
