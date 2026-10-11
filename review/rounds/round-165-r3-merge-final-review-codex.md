# WP-R3 合并键定点复审：PASS

## 上轮必须改项

- **R3-M2 已解决。** `ky.models._StrictSafeLoader.construct_mapping` 为同一映射
  中的 merge tag 记录独立哨兵。单个 `<<` 仍交父类展开；第二个 `<<` 抛
  `_DuplicateKeyError`，由公开解析入口转为带文件路径的 `LedgerError`。
- 新增的台账读取测试同时覆盖单个 merge 加显式覆盖、普通键重复，以及
  merge 键重复。此前有效的单 merge 写法保持可读。

## 验证

- `py -3.12 -B -m unittest tests.test_ledger.LedgerFileReadingTest`：3 项通过。
- 独立重放上轮台账探针：单个 `<<` 得到 1 条有效资料；同层两个 `<<` 被拒绝，
  `LedgerError.path` 为台账文件路径，消息包含 `duplicate field '<<'`。
- 只读复审；未改源码、未跑全量测试。

**PASS。** 上轮重复 merge 键缺口已封闭，单 merge 兼容性保持正常；没有发现
本次修复直接引入的回归。
