# 任务书：WP-F-a 状态来源读取端口（M13 + M26；WP-F 的第一块）

先读仓库根 `AGENTS.md`，再读：**`review/rounds/round-132-wp-f-rules-sol-out.md`（WP-F 细则审查；本包照它"建议的最终规则"第 2、5 条做）**、
`review/rounds/round-132-wp-f-rules-sol.md`（决策者原拟规则，已被上面修订）、`contracts/planner_port.md`（M13 provenance 一节）、`contracts/freeze.md`、`contracts/route_plan.md`、`contracts/availability.md`、
`ky/storage/day_plan_store.py`、`ky/storage/review_shards.py`、`ky/storage/route_store.py`、`ky/availability/port.py`。

你是固定窗口 `luna-c`，负责 WP-F 学习状态投影全线（F-a 读取端口 → F-b 投影 schema 3 → F-c 按日期查询端口），后面两块也会派到这个窗口，请记住本包的设计。
在主仓库 `F:\workspace\kaoyan-ai-system` 工作。另有两个实现者同时在做：`luna-b` 改 `tools/`、`docs/`、个别测试导入；`luna-a` 只改 `ky/workspace.py`。你**只改**下面列出的文件。

## 背景

WP-F 要把学习状态投影进 SQLite。投影不能自己解析状态 YAML，也不能"先用端口加载对象、再单独读文件算哈希"（两次读取可能不是同一时点，已知缺陷清单 2）。
所以各状态存储要提供一次读取就同时给出"解析好的对象 + 本次实际读到的每个文件的相对路径与原始字节 SHA-256"的公开只读端口。

## 要做的

1. **`DayPlanStore`（M13）**：新增一个公开只读方法，**一次遍历**整个存储，返回一个不可变结果对象，包含：
   - 每天的**当前版本**日计划（`DayPlan` ＋ 版本号 ＋ manifest 里记的来源字段：actor / input_hash 等，照 `contracts/planner_port.md` 的 provenance）；
   - 全部完成事件（按日期排序；位置校验与 `delivered_words` 相同：不在存储自己路径上的 `completion--*.yaml` 报错）；
   - 全部冻结 / 恢复事件（即 `freeze_events()` 的结果）；
   - `sources`：本次读到的每个文件（各月 manifest、当前版本计划文件、完成事件、冻结事件）相对存储根的 POSIX 路径 → 原始字节 SHA-256。**哈希必须来自解析所用的同一份字节**。
   - 每个月的 manifest 只读一次（不要循环调用 `load_day_plan`）；manifest 登记的 SHA-256 与文件不符照现有做法报错。旧版本计划文件、月结不进结果、不进 `sources`。
   - 存储根不存在 → 空结果（与现有空存储行为一致）。
2. **`ReviewShardStore`（M13）**：新增公开只读方法，返回队列项（与 `load()` 相同的对象与顺序）＋ `sources`（manifest 与每个分片的相对路径 → 同一份字节的 SHA-256）。
   **manifest 不存在 → 空队列、空 `sources`**（与 CLI 现有 `load() if manifest_path.exists() else ()` 口径一致）；manifest 存在但无效 / 分片不符 → 照 `load()` 报错。
3. **`RoutePlanStore`（M13）**：新增公开只读方法，返回当前路线（与 `current()` 相同，无路线为 `None`）＋ `sources`（manifest 与当前版本文件）。
4. **`availability`（M26）**：新增公开只读函数，返回与 `load_availability` 相同的 `Availability` ＋ 该文件的 SHA-256（同一份字节）。登记即必须有文件的规则不变。
5. **现有公开方法行为与输出不变**（可以抽共享私有辅助函数，但现有测试必须全过、错误消息与路径不变）。
6. **规格**：新写 `contracts/state_sources.md`：每个新方法的签名、返回形状、`sources` 的路径约定（相对各自存储根）、空 / 缺失 / 无效三种情况的行为、"哈希来自同一份字节"的保证。`docs/模块地图.md` 的 M13 / M26 两行补上新接口（只改这两行）。

## 不做的

- 不碰 `ky/projection/`（那是 F-b）；不做按日期查询（F-c）；不改写入路径；不做性能优化。
- 不改 `tools/`、`ky/workspace.py`、`ky/__main__.py`。
- 不补任务书没列的测试。

## 测试（只写这些）

新文件 `tests/contract/test_state_sources_port.py`：
- 对一个有多月计划（含同一天多个版本）、完成事件、冻结 / 恢复事件的临时存储：新方法返回的对象与现有 `load_day_plan` / `load_month_completions` / `freeze_events` 逐一相等；只含当前版本；`sources` 的每个哈希等于对应文件字节的 SHA-256，且不含旧版本文件与月结。
- 每个月 manifest 只读一次（计数被读取的 manifest 次数，不写死月份数）。
- 队列：有 manifest 时与 `load()` 相等且 `sources` 覆盖 manifest 与全部分片；无 manifest → 空；manifest 存在但分片字节被改 → 报错。
- 路线：无路线 → `None`；有两版时只给当前版本及其 `sources`。availability：哈希与字节一致；文件缺失报错。
- 放错位置的完成事件 → 报错。
每条撤实现时变红，报告写实际怎么撤、实际结果。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_state_sources_port tests.test_day_plan_store tests.test_storage tests.contract.test_route_plan_port tests.contract.test_availability_port tests.contract.test_freeze_port
```

## 报告

`review/rounds/round-133-wp-fa-luna.md`：各新接口签名与返回形状、`sources` 路径约定、每条测试的撤实现验证、验收输出、留给 F-b 的注意事项、建议。
写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。含中文的文件只用 `apply_patch` 编辑，写完查 `???`。
