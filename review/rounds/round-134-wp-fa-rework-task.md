# 返工：WP-F-a 决策者审查意见（同一窗口 `luna-c` 续做）

你上一轮（`review/rounds/round-133-wp-fa-luna.md`）的接口形状与空 / 缺失语义都对，保留。决策者审 diff 发现下面几处要改，**只改这几处**，范围与文件限制同上一轮任务书。

## 必须改

1. **冻结事件校验写了两份**：`DayPlanStore._read_freeze_sources` 把 `_read_freeze_event` 的约 25 行校验整段复制了。改为一个"从已读字节解析并校验一条事件"的私有函数，`_read_freeze_event`（`freeze_events()` 用）与 `_read_freeze_sources` 都调用它；错误消息与路径不变。
2. **日计划 manifest 解析写了两份、且不按存储布局找**：`_read_current_plans` 复制了 `_load_day_plans_manifest` 的条目规整逻辑，并用 `rglob` 按文件名收集任何位置的 `day_plans_manifest.yaml`。
   - 把 `_load_day_plans_manifest` 拆成"读字节"与"从字节解析条目"两步，两处共用后一步。
   - 只读存储自己布局下的 manifest：`<root>/<YYYY-MM>/day_plans_manifest.yaml`（`_month_dir` 的格式）。其他位置的同名文件 → `StorageError`（与"放错位置的完成事件报错"同一规则），报告里写明。
   - 顺带：完成事件也按同一布局判定，保持现有"不在自己路径上即报错"。
3. **路线版本校验写了两份**：`RoutePlanStore.read_state_sources` 复制了 `_load_entry` 的哈希 / revision / route_id 校验。把 `_load_entry` 与 `_read_manifest` 拆出"从已读字节校验"的私有函数，`current()` / `load_revision()` 与 `read_state_sources()` 共用；现有错误消息不变。
4. **队列重复 `review_id` 检查写了两份**：`load()` 与 `read_state_sources()` 各有一份循环。抽一个私有函数共用（或让两者共用同一个带 `sources` 的内部读取，`load()` 保留"缺 manifest 报错"的现有行为）。

## 测试补强（只加这些）

上一轮的撤实现验证是"把整个新方法换成不可调用值"，证明不了具体性质。补：
- **每个来源文件只读一次**：在 `tests/contract/test_state_sources_port.py` 里对四个新接口分别计数 `Path.read_bytes` / `read_text` 等实际读取，断言 `sources` 里的每个文件恰好被读一次（这同时锁住"每月 manifest 读一次"与"哈希来自解析所用的同一份字节"）。
- 放错位置的 `day_plans_manifest.yaml` → 报错。
- 撤修改验证请**定点变异**并写实际结果：①在某个接口里对同一文件多读一次 → 计数测试变红；②让日计划枚举接受任意位置的 manifest → 新测试变红；③把 1–4 任一处共用函数里的一项校验删掉 → 原有或新测试变红（写明是哪条）。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_state_sources_port tests.test_day_plan_store tests.test_storage tests.contract.test_route_plan_port tests.contract.test_availability_port tests.contract.test_freeze_port
```

## 报告

追加写到 `review/rounds/round-134-wp-fa-rework-luna.md`：每项改动落点、共用函数清单、变异验证实际结果、验收输出。
写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。含中文的文件只用 `apply_patch` 编辑，写完查 `???`。
