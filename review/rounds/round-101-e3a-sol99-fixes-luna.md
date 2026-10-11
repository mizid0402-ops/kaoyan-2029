# Round 101：WP-E3a sol 99 必须改修复报告

## F2：超大整数权重

- 落点：`ky/schedule/planning.py` 的 `_parse_month()` 捕获 `math.isfinite()` 的
  `OverflowError`，转换为带原字段路径的 `RoutePlanError`。
- 回归测试：`test_rejects_subject_weight_integer_that_overflows_float` 输入 `10**1000`，
  断言路径为 `route_plan.months[0].subject_weights.subject`。
- 撤修复验证：临时撤去异常转换后单跑该测试，收到 `OverflowError: int too large to convert
  to float`，测试失败；随后恢复修复。

## S2：manifest fail-closed

- 落点：`ky/storage/route_store.py` 新增 `_manifest_mapping()`、`_parse_manifest_entry()`、
  `_parse_manifest()`；磁盘 manifest 读取和写入前读取当前 manifest 都经过同一解析器。解析器
  验证精确键、精确整数、非空 route_id、连续版本号、固定版本路径、摘要格式及 actor/input_hash
  类型。加载路线版本时另核对路线的 revision 和 route_id。
- 回归测试：`test_manifest_rejects_invalid_shape_order_and_route_identity` 覆盖布尔 schema、字符串
  revision、非映射条目、根外路径、断号和路线 route_id 错配，并检查字段路径。越界路径探针在
  根外创建了与 r1 同字节的文件。
- 撤修复验证：临时让 `_read_manifest()` 绕过 `_parse_manifest()` 后单跑该测试，出现 4 个失败
  和 1 个错误：布尔 schema 与越界路径未被拒绝、非映射条目泄出 `AttributeError`，类型/断号错误
  的字段路径不正确；随后恢复解析器。

## S3：manifest 失败回滚与孤儿版本恢复

- 落点：`ky/storage/route_store.py` 在 manifest 原子替换失败时删除本次发布的版本文件，再抛出
  原异常。检测到未登记的目标版本时，报错包含“未登记的版本文件，确认后手动删除”及文件路径。
- 规格：`contracts/route_plan.md` 写明 manifest 替换失败回滚；进程在版本发布后崩溃留下孤儿文件时，
  必须核实并手动删除后重试。
- 回归测试：`test_manifest_write_failure_rolls_back_version_and_allows_retry` patch manifest 写入抛出
  `OSError`，断言 r1 不残留且重试成功。`test_unregistered_version_file_requires_manual_removal`
  断言错误文案、路径、原字节不变，并断言不会进入发布步骤。
- 撤修复验证：临时撤去回滚后，回滚测试因 r1 文件仍存在而失败。临时撤去孤儿早期检查并 mock
  发布成功后，孤儿测试因未抛错而失败；随后恢复两项修复。

## S4：原子不覆盖发布

- 落点：`ky/storage/route_store.py` 临时版本校验后以 `os.link(temporary, final_path)` 发布；目标存在
  时报告未登记版本错误，其他硬链接错误转换为含原因的 `StorageError`，不回落到 `os.replace()`。
  发布前的存在检查只用于提前给出清晰错误，原子不覆盖由硬链接操作保证。
- 规格：`contracts/route_plan.md` 说明版本文件不可覆盖由硬链接原子发布保证；不支持硬链接的文件系统
  报错。与 S3 共用的孤儿版本手动恢复规则也已写入规格。
- 回归测试：`test_publish_does_not_replace_a_racing_target` 在发布调用时创建目标文件，断言提交报错且
  外部字节不变。
- 撤修复验证：临时将发布操作改回 `os.replace()` 后单跑该测试，因未抛 `StorageError` 而失败，
  且测试会发现外部目标被覆盖；随后恢复硬链接发布。

## 验收

```text
py -3.12 -m unittest tests.contract.test_route_plan_port tests.test_planning
Ran 31 tests in 1.233s
OK
```

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。

## 建议

无需追加实现建议。硬链接不受支持的文件系统会按契约拒绝版本发布；调用方可据错误原因选择受支持的
存储位置。
