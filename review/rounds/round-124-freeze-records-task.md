# 任务书：冻结 / 恢复记录改为有序事件 + 原子不覆盖发布（sol 第 123 轮两个"必须改"）

先读仓库根 `AGENTS.md`，再读：`review/rounds/round-123-review-sol-out.md`（全文，复现输入都在里面）、`docs/阶段2.5-接缝收口.md` 的 D11、`contracts/freeze.md`、
`ky/storage/day_plan_store.py`（`write_freeze_record` / `write_resume_record` / `freeze_records` / `resume_records`、`_write_atomically`）、`ky/storage/route_store.py`（`_write_version` 的 `os.link` 不覆盖发布与身份核对）、
`ky/freeze/port.py`（`latch_active`）、`ky/freeze/resume.py`、`ky/__main__.py`（`_latch_freeze_if_needed`、`resume_main`、`day-plan record`）、`tests/contract/test_freeze_port.py`、`tests/contract/test_resume_port.py`。

你在主仓库 `F:\workspace\kaoyan-ai-system` 工作，只改上面列出的实现、规格与这两个测试文件。

## 决策者已定的设计（照做；有更好的写法先在报告里提）

1. **有序事件（修同日多轮）**：冻结 / 恢复记录改为 `<store>/freeze/<序号六位>-<freeze|resume>--<D>.yaml`，内容增加 `sequence`（整数，与文件名一致）与 `kind`；序号在**两类记录之间全局递增**（新序号 = 现有最大序号 + 1，从 1 开始）。
   - 读取：`freeze_events() -> tuple[FreezeEvent, ...]`（`sequence`、`kind`、`day`，按序号排序；文件名与内容的序号 / 类型 / 日期必须一致，放错位置或不一致即报错，照现有做法）。删除旧的按日期返回的 `freeze_records()` / `resume_records()`（不留别名，D7；仓库内无既有记录，无需迁移，调用方同步改）。
   - `latch_active(events)`：存在一条 freeze 事件 F，使得没有 resume 事件 R 满足 `R.sequence > F.sequence` 且 `R.day >= F.day`。同日"冻结 → 恢复 → 再冻结"因此能正确表示第二轮锁存。
   - 同日同类不再一律拒绝；"一次写入"改由序号保证：每个序号文件只写一次。
2. **原子不覆盖发布（修并发覆盖）**：事件文件的发布照 `route_store._write_version`：临时文件写入并重读校验后 `os.link(临时, 目标)`（目标已存在原子失败 → `StorageError`，消息说明"序号已被占用，请重试"），不回落 `os.replace`；临时文件在 `finally` 里删除。
3. **`ky resume` 的同日判断**改为基于事件：当且仅当 `latch_active` 或存在逾期项时才写 resume 事件；删去"当天已有 resume 记录就报错"的旧检查（同日多轮合法）。
4. **注册表不可用（sol 123 建议，决策者选择"写明 + 提示"）**：`day-plan record` 找不到可用注册表时照常记录，但在输出里提示"未找到可用的工作区注册表，未检查冻结锁存"；`contracts/freeze.md` 写明这时人工恢复的保证不适用。

## 测试（只写这些）

每条都要在撤回对应修复时变红（报告里写怎么验证的）：
- sol 123 的同日复现：9/15 冻结 → 同日 resume → 再达阈值 → `day-plan record` 成功且写出第二条冻结事件，preflight 为锁存冻结。
- `latch_active` 的序号与日期规则：同日 F1 < R < F2 仍锁存；R 序号在后但日期早于 F 不解除；多轮交替。
- 并发注入：patch `ky.storage.day_plan_store.os.link` 让另一写入方先占用目标 → 写入失败且对方文件字节不变。
- 事件文件名 / 内容不一致、放错目录均被读者拒绝。
- `ky resume` 同日第二轮能写第二条 resume 事件并解除第二轮锁存。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_freeze_port tests.contract.test_resume_port tests.test_day_plan_store tests.test_cli
```

## 报告

`review/rounds/round-124-freeze-records-luna.md`：每项落点、事件格式、撤修复验证、验收输出、建议。
写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。含中文的文件只用 `apply_patch` 编辑，写完查 `???`。
