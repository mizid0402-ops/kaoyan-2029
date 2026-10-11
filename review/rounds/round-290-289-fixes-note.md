# 第 290 轮：复验 289 两条必须改 —— 决策者验证记录

## 发生了什么（要如实记）

`gpt-6-luna`（窗口 `luna-fix-289`）按第 290 轮任务书改了代码，但**派发在 19:16 挂死**：
原始日志 0 字节、3 小时只有 4 秒 CPU、无 API 活动，**没有产出作者报告**。决策者按纪律停掉该派发链，
然后**以磁盘上的改动为对象**逐条复核（下面的数字都是复验时实跑出来的，不是作者自述）。

## M1 / MAJOR：记录写入不再重复读取旧来源

改动：`ky/storage/day_plan_store.py:529-535` 把已加载来源传给 `review_store.write(...)`；
`ky/storage/review_shards.py` 给 `ReviewQueueStateSources` 增加 `_manifest` / `_groups`
（与 items 同一次解析），`ReviewShardStore.write(..., source_state=None)` 与
`_read_previous_groups(source_state)` 命中该分支时不再重开文件；schema-1 历史检查也改用已加载状态。
`source_state` 是可选关键字参数，旧调用方行为不变。

**复验证据（用 sol 289 自己的探针，未改一行）**：

```text
C-M1 record reads {'config.yaml': 1, 'state/review_queue/manifest.yaml': 1,
 'state/review_queue/shards/math1--b04--0000--v1.yaml': 1,
 'state/review_queue/shards/math1--b12--0000--v1.yaml': 1,
 'state/plans/2026-10/completion--2026-10-01.yaml': 1, 'trees/tree.yaml': 1,
 'weights/topic_weights.json': 1, 'indexes/questions.json': 1,
 ... 另有 4 个 .tmp（写完重读校验，按任务书不算输入重复读取）}
```

修复前是"旧 manifest 与两个旧分片各 3 次"。现在每个输入各 1 次。

## M2 / 验收必改：基线例外收窄到"只允许原因占位符变化"

改动：`tests/contract/test_today_port.py:609-640` 的 `_assert_only_retire_hint_differs` 现在断言
`new_line == old_line.replace("--reason <原因>", '--reason "替换为原因"', 1)`，并要求旧行里该片段恰好出现一次；
不再只查子串、不再整行替换。

**复验证据（sol 289 的反例：同时改占位符与日期）**：

```text
AssertionError: b'...为原因" --date 2099-01-01\r\n' != b'...为原因" --date 2026-10-01\r\n'
```

修复前这个反例被静默放过，现在被拒。

## 验收

```text
py -3.12 -m unittest tests.contract.test_today_port tests.contract.test_day_plan_store_port
 tests.test_review_queue_advance tests.contract.test_freeze_port tests.contract.test_resume_port
Ran 65 tests in 52.807s
OK
```

全量：由决策者在提交前跑（见提交信息）。

## 遗留

- 本轮的**作者报告缺失**（派发挂死）。两个缺陷都用 sol 289 的原始探针复验过，
  但独立复验一轮仍应做——已排进下一轮 sol 派发（与前端规格评审同一轮）。
- 机制教训：长派发要加看门狗（原始日志 10 分钟不增长就停掉重派），不要靠等。
