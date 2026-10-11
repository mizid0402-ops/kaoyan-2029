# Round 124：冻结 / 恢复有序事件与原子不覆盖发布

## 改动落点

- `ky/storage/day_plan_store.py`：新增 `FreezeEvent` 事件读取 `freeze_events()`；freeze / resume
  共用全局序号；读者校验文件位置及序号、类型、日期；写入先校验临时 YAML，再用
  `os.link(temp, target)` 原子不覆盖发布，并核对发布前后文件身份。目标序号已占用时抛出
  `StorageError`，提示“序号已被占用，请重试”。序号分配用操作系统文件锁串行化，避免不同类型
  的并发事件重复取到同一序号。旧 `freeze_records()` / `resume_records()` 已删除。
- `ky/freeze/port.py`、`ky/freeze/__init__.py`：新增 `FreezeEvent`；`latch_active(events)` 仅在
  存在 freeze 事件且没有序号更大、日期相同或更晚的 resume 事件时返回真。
- `ky/__main__.py`：preflight、record、submit 和 resume 全部按事件读取锁存状态；resume 仅在
  锁存有效或有逾期项时追加事件，移除当日已有 resume 拒绝；注册表不可用时 record 仍可写，
  JSON / 文本输出提示未检查冻结锁存。
- `ky/planner/port.py`：同步 M19 调用点，避免已删除的日期读取 API 留在调用链中。此文件未在
 任务书列举的路径中，但删除旧 API 后这是唯一遗漏的直接调用方；不改会导致 M19 输入构建报错。
- `contracts/freeze.md`：记录事件格式、全局序号、不覆盖发布、同日多轮和注册表不可用边界。
- `tests/contract/test_freeze_port.py`：增加同日再冻结 CLI 复现、序号 / 日期 latch 规则、文件
  内容与路径校验、并发占位不覆盖测试；原日期记录断言迁为事件断言。
- `tests/contract/test_resume_port.py`：覆盖同日第二轮 resume 写入并解除第二轮锁存。

## 事件格式

事件文件位于 `<store>/freeze/`，命名为 `<序号六位>-<freeze|resume>--<YYYY-MM-DD>.yaml`。
内容包含 `schema_version: 1`、整数 `sequence`、`kind`、`day` 和对应的 `status` 或
`resume` 映射。序号从 1 开始，在两类事件间全局递增。读取结果按序号排序；重复序号、放错
目录，以及文件名和内容字段不一致均报 `StorageError`。

## 撤回修复敏感性

- 同日 freeze → resume → 达阈值：测试要求 `day-plan record` 成功、写出第三个有序事件，且
  preflight 报告 `freeze.latched`。恢复旧的按日唯一文件行为会在第二次 freeze 写入时报错，
  因而测试失败。
- latch 序号与日期边界：测试直接区分“同日 F1 < R < F2”、“后序号但早日期的 R”以及跨日
  多轮交替。恢复旧日期数组签名后，单参数调用即失败；恢复只按日期解除也会违背这些断言。
- 并发占位：测试在链接发布前放入对方 sentinel 字节，要求写入报“序号已被占用，请重试”，
  并逐字节确认 sentinel 未改变。恢复 `os.replace` 后不会抛出预期异常，且目标内容会被覆盖。
- 文件名 / 内容校验：测试分别把合法事件复制到嵌套目录、改文件名日期、改内容序号，三种情况
  均要求读者拒绝。旧日期读者 API 已删除，旧存储形状不能满足 `freeze_events()` 契约。
- resume 同日第二轮：测试在第一轮解除后写入同日第二次 freeze，再执行 `ky resume`，要求新增
  第二个 resume 事件并解除锁存。恢复“当日已有 resume 即拒绝”检查会使命令返回错误。

以上是按测试断言与旧行为逐项对照的撤修复敏感性核对；没有额外运行全量 mutation 测试套件。

## 验收

执行：

```text
py -3.12 -m unittest tests.contract.test_freeze_port tests.contract.test_resume_port tests.test_day_plan_store tests.test_cli
```

输出：`Ran 78 tests in 22.903s`，`OK`。

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。未提交。

## 建议

- `docs/阶段2.5-接缝收口.md` 的 D11 仍写旧的按日期文件名和解除规则。本任务限定该文档只读，建议后续由决策者更新决议记录，避免它与 `contracts/freeze.md` 不一致。
- 本轮序号分配增加持久的隐藏锁文件 `.sequence.lock`；事件读者只扫描 YAML，不把该锁文件当作事件。后续若存储迁移需搬运冻结目录，应保留锁文件的同目录并发语义，或统一更新写入策略。
