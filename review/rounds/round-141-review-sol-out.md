# WP-F-a 修复复审：PASS

## 范围与验证

- 用 `git archive 255073b` 在独立临时目录解包；原始资料从第 136 轮的临时副本补入，并建 `products/` 空目录。只从 Git 对象库读取提交差异，未读取或运行主仓库工作区。
- 复审范围是第 136 轮 M1、M2，及本次直接改动的 `ky/storage/day_plan_store.py`、`review_shards.py`、`route_store.py`、`ky/availability/__init__.py` 和新增契约测试；没有重新扩展为全仓审查。
- `py -3.12 -m unittest tests.contract.test_state_sources_port`：**12 项通过**。未跑全量（按 `AGENTS.md`，由决策者提交前统一跑）。

## 必须改

**无。**第 136 轮两个阻断项均已修复。

### M1 — 已修复：当前计划文件缺失

**可复现输入：**在系统临时目录用 `DayPlanStore.write_day_plan()` 写入 `2026-09-15`，删除返回的 `WriteReport.path`，保留该月 manifest，然后调用 `read_state_sources()`。

**实际结果：**现在抛 `ky.storage.day_plan_store.StorageError`，消息以 `cannot read registered day plan:` 开头；`exc.path` 精确等于缺失版本文件的 POSIX 形式路径（`.../2026-09/day_plans/2026-09-15--v1.yaml`）。不再漏出原始 `FileNotFoundError`。修复只包住新端口读取当前计划字节的 `OSError`；旧 `load_day_plan()` 未被改动。

### M2 — 已修复：普通文件占用存储根

**可复现输入：**在系统临时目录建普通文件 `plans`，分别作为 `DayPlanStore`、`ReviewShardStore`、`RoutePlanStore` 的根，调用各自 `read_state_sources()`。

**实际结果：**三个端口均抛各自的 `StorageError`（共同基类为 `ContractError`），消息均为 `store root is not a directory`，`exc.path` 均是该根路径的 `as_posix()`。三个端口的错误消息与路径形式一致，不再返回空存储。

## 建议改

**无本次新增建议。**第 136 轮 S1 已通过 `ky/availability/__init__.py` 导出新函数和结果类型。S2 关于 F-b 聚合 `sources` 时加命名空间，仍属 F-b 的实现约束，不阻断本包。

## 不改（已核实）

- **根不存在仍为空：**同一探针用不存在的根分别调用三个端口，计划得到空 `plans/completions/freeze_events/sources`，队列得到空 `items/sources`，路线得到 `route=None` 和空 `sources`。这与 `contracts/state_sources.md` 的缺失根语义一致。
- **兼容边界：**修复差异没有改 `freeze_events()`、`load_day_plan()`、`load()`、`current()` 或 `load_revision()` 的实现路径；新增判断仅在三个 `read_state_sources()` 入口，新增 `OSError` 转换仅在日计划新端口。未发现修复引入的旧接口行为变化。
- **错误路径：**三个 M2 错误的 `exc.path` 都是存储根；M1 的 `exc.path` 是实际缺失的当前版本文件。Windows 的底层 `OSError` 文本在 M1 消息内另含系统原生反斜杠路径，但契约错误的结构化路径与其余端口一样使用 POSIX 形式；这与队列/路线既有的底层读失败消息形式一致。

探针在临时目录运行。最初用日计划模块的 `StorageError` 捕获三个存储的异常，未捕获队列模块自己的同名子类；改用共同的 `ContractError` 后，上述路径与消息断言全部通过。这是探针异常类型选择错误，不是实现失败。

## 安全登记

第 136 轮关于手工篡改日计划 manifest 路径的风险已并入 `docs/安全风险登记.md` S8。本次修复未改该路径解析，也未发现需要新增的安全登记项；按仓库单用户本机威胁模型，S8 不计本轮门禁。

## 门禁结论

**PASS。**M1、M2 的原始复现输入均得到预期契约错误，缺失根语义保持不变，定向契约测试通过。
