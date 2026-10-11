# 第 153 轮 · WP-S3 日计划 / 存储写入规格（实现者报告）

执行模型：Claude Opus 5.5（实现者）
日期：2026-09-27
任务：补写 M11 `DayPlan` 与 M13 `DayPlanStore` 的端口规格与契约测试；**不改行为**。

## 1. 改动文件

| 文件 | 状态 | 说明 |
|---|---|---|
| `contracts/day_plan_store.md` | 新增 | M11 DayPlan / M13 DayPlanStore 端口规格 |
| `tests/contract/test_day_plan_store_port.py` | 新增 | 11 条契约测试，全部针对当前代码通过 |
| `review/rounds/round-153-ws3-specs-opus.md` | 新增 | 本报告 |

未改动任何实现文件；未碰 `ky/__main__.py`、`ky/projection/`、`docs/模块地图.md`。变异测试结束后
`ky/storage/day_plan_store.py` 与 `ky/schedule/longitudinal.py` 的哈希与改动前一致（见 §4）。

## 2. 规格摘要（`contracts/day_plan_store.md`）

- §1 DayPlan 字段表、派生量、`check_invariants` 的 7 条规则（返回全部违规）与"不检查"清单。
- §2 目录布局：`<root>/YYYY-MM/{day_plans_manifest.yaml, day_plans/<日>--v<N>.yaml,
  completion--<日>.yaml, month_close.yaml}` 与 `<root>/freeze/`。
- §3 日计划文件格式与 `parse_day_plan` 的缺省值、错误路径。
- §4 `write_day_plan` 的 7 步：不变量 → 可用时间上限 → 冻结门 → 按日版本号（只看 manifest）→
  临时文件重读并重跑 1–3 步后 `os.replace` → manifest（schema 2、按日期排序、6 个键）→ WriteReport；
  冻结门每次成功写入恰调用两次；孤儿版本文件与无锁并发的现状。
- §5 读接口（`load_day_plan` 摘要核对、`load_month`），来源与 `read_state_sources` 引用他处。
- §6 完成事件与月结：路径、只写一次、重读、`load_month_completions` / `delivered_words` 语义。
- §7 冻结 / 重启事件只写本模块补充（载荷必须是映射、错误路径），其余指向 `contracts/freeze.md`。
- §8 三个原子写辅助的对照表（`_write_atomically`、`_write_once_atomically`、`replace_bytes`）。
- §9 `preflight_review_queue` / `advance_review_queue` 的函数层约定（检查顺序、隐式 completion ID、
  replayed / late / needs_check、单次提交）与 CLI `day-plan record` 的调用顺序；D8′ 规则指向
  `contracts/review_progress.md`。
- §10 出入表，§11 契约测试与验收命令。

不重复的内容：`read_state_sources` 形状（state_sources.md）、`actor` / `input_hash` 与
`day_plan_provenance`（planner_port.md）、冻结事件格式与锁存（freeze.md）、可用时间文件（availability.md）、
完成事件字段与 D8′（review_progress.md）。

## 3. 出入（以代码为准，详见规格 §10）

| 编号 | 现象 | 建议分类 |
|---|---|---|
| D1 | 完成事件与月结"只写一次"= `exists()` 后 `os.replace`，不是 `os.link`（AGENTS 已知缺陷 1） | 安全登记 |
| D2 | `parse_day_plan` 拒绝未加引号的 YAML 日期 `day: 2026-09-15`（route / availability 都接受）；非法日期字符串抛 `ValueError`，`day-plan submit` 出 traceback（已实测：`day: "2026-13-01"` → `ValueError: month must be in 1..12`，退出码 1） | **建议必须改**（日常手写会碰到） |
| D3 | `parse_day_plan` 不检查数值类型：字符串分钟 → `check_invariants` 抛 `TypeError`（traceback，已实测）；布尔 / 浮点被接受并落盘 | **建议必须改** |
| D4 | 日计划 manifest 不校验 schema / 条目键（`KeyError`）；`load_day_plan` 当前文件缺失抛 `FileNotFoundError`（`read_state_sources` 已在 sol 136 M1 改为 `StorageError`） | 安全登记（需篡改 / 删除内部文件） |
| D5 | `write_day_plan` 不校验 `actor` / `input_hash`，`RoutePlanStore` 会校验 | 登记 |
| D6 | 孤儿版本文件被下一次同日写入 `os.replace` 覆盖；`RoutePlanStore` 对孤儿拒绝 | 可接受，记录差异 |
| D7 | `load_day_plan` 同一文件读两次（摘要 / 解析）；`day-plan record` 预检与推进各读一次队列（AGENTS 已知缺陷 2） | 安全登记 |
| D8 | `load_month_completions` 不核对文件名与事件日期 | 安全登记 |
| D9 | 模块内"CompletionEvent -> ReviewShardStore"注释仍写"同日同质量重放 / 不同质量拒绝"（已被 D8′ 取代）；模块 docstring 称全部经 `os.replace`，冻结事件实为 `os.link` | 文档过时 |
| D10 | `contracts/freeze.md`"在每次文件提交前"运行冻结门；实际只在版本文件发布前（两次），manifest 替换前不调用 | 措辞差异 |
| D11 | 模块地图 M13 验收命令不含新契约测试 | 见 §6 替换文本 |

D2 / D3 是本轮唯一属于"日常使用会碰到"的问题；按任务书"不改行为"未修，也未写测试把它们钉住
（钉住缺陷会妨碍日后修复）。建议另开小工作包：`parse_day_plan` 接受 `date` 标量、把
`ValueError` 与非整数（含布尔）字段转为 `StorageError` 并带字段路径。

## 4. 变异测试

方法：脚本逐条对实现文件做一处字符串替换（先断言替换点唯一），以 `PYTHONDONTWRITEBYTECODE=1` 只跑对应的一条
测试，`finally` 中写回原始字节并比较 SHA-256。全部 11 条变红，全部逐字节恢复。

| # | 文件 | 变异 | 目标测试 | 结果 |
|---|---|---|---|---|
| M1 | `day_plan_store.py` | manifest `days` 去掉 `sorted(...)` | `test_versions_count_per_day_and_manifest_entries_are_sorted_and_exact` | 红（failures=1） |
| M2 | 同上 | `_day_plan_mapping` 删去 `schema_version` 行 | `test_plan_file_uses_the_documented_fields_and_parses_back` | 红（failures=1） |
| M3 | 同上 | `parse_day_plan` 删去 `_unknown(...)` | `test_parse_day_plan_defaults_and_field_paths` | 红（failures=1） |
| M4 | 同上 | `load_day_plan` 摘要比较改为 `if False:` | `test_load_day_plan_rejects_a_current_file_that_no_longer_matches_its_digest` | 红（failures=1） |
| M5 | `longitudinal.py` | `no active subjects` 的 `v.append` 改为 `pass` | `test_store_without_subject_weights_rejects_every_plan` | 红（failures=1） |
| M6 | `day_plan_store.py` | 冻结门移到 `check_invariants` 结果判断之前 | `test_invariants_then_availability_run_before_the_freeze_gate` | 红（failures=2） |
| M7 | 同上 | `_reread` 删去冻结门调用 | `test_gate_failure_on_the_temp_reread_publishes_nothing` | 红（failures=1） |
| M8 | 同上 | 完成事件文件名前缀 `completion--` → `completion-` | `test_completion_events_and_month_close_live_in_their_month_directory` | 红（failures=1） |
| M9 | 同上 | 删去冻结载荷 `isinstance(mapping, Mapping)` 检查 | `test_freeze_and_resume_payloads_must_be_mappings` | 红（errors=2，`ValueError`） |
| M10 | 同上 | 隐式 completion ID `#` → `:` | `test_implicit_completion_id_is_day_and_index_and_preflight_writes_nothing` | 红（failures=1） |
| M11 | 同上 | 预检中"未知 review_id"检查移到"重复 completion ID"之前 | `test_duplicate_completion_id_is_reported_before_an_unknown_review_id` | 红（failures=1） |

恢复核对：每条变异后 `day_plan_store.py` 恢复为 `cea44a4c320e…`、`longitudinal.py` 恢复为
`6c6063c7774e…`；运行前后 `Get-FileHash` 对比均为 True；`git status` 仅显示新增文件。

## 5. 测试输出

```text
py -3.12 -m unittest tests.contract.test_day_plan_store_port tests.test_day_plan_store
    tests.contract.test_freeze_port tests.contract.test_state_sources_port
.......................................................
----------------------------------------------------------------------
Ran 55 tests in 8.901s

OK
```

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。

测试取数：科目 ID 与权重来自 `tests/fixtures/config/config-minimal.yaml` 的在考科目，复习项来自
`tests/fixtures/reviews/reviews-normal.yaml`（复习日取第一项的 `due_date`）；没有数据量字面量。
日期常量只用于构造临时存储里的记录。新测试不与 `tests/test_day_plan_store.py`、
`tests/test_review_queue_advance.py`、`tests/test_longitudinal.py` 及三份既有契约测试重复。

怀疑受影响的模块：无（未改实现）。

## 6. 模块地图替换文本（`docs/模块地图.md` §3）

M11 行：

```text
| M11 路线 / 日计划 / 月结 | 可变时间线（阶段起止 + 各科复习分钟）、日计划模型与护栏（`DayPlan`、`check_invariants`）、月度对账 | `contracts/route_plan.md`、`contracts/day_plan_store.md` §1 | `ky/schedule/planning.py`（mapping / parser）、`longitudinal.py`、`monthly_close.py` | `state.routes` | A：RoutePlan 格式可独立替换；映射函数是 YAML / JSON 唯一形状来源；DayPlan 字段与护栏规则已成文 | `py -3.12 -m unittest tests.contract.test_route_plan_port tests.test_planning tests.test_longitudinal tests.contract.test_day_plan_store_port tests.contract.test_workspace tests.test_cli` |
```

M13 行：

```text
| M13 学习状态存储 | 队列 / 日计划 / RoutePlan / 完成事件 / 月结 / 冻结重启审计的原子落盘；提供避免写穿硬链接的 `replace_bytes()`；可查询投放词形并集及来源 | `contracts/day_plan_store.md`（DayPlanStore 布局、写入护栏顺序、只写一次记录、原子写辅助、队列推进入口）、`contracts/state_sources.md`、`contracts/planner_port.md` §M13 provenance、`contracts/freeze.md`；ReviewShardStore manifest schema 2 记录 `calculated_completion_ids`；RoutePlanStore 为每个 revision 保留来源 | `ky/storage/`（`atomic.py`、`day_plan_store.py`、`review_shards.py`、`route_store.py`） | `state.review_queue`、`state.plans`、`state.routes` | **A**（WP-D 迁出已投放词状态；WP-E2 来源审计；WP-F-a 状态来源读取；WP-S3 DayPlanStore 写入规格） | `py -3.12 -m unittest tests.contract.test_day_plan_store_port tests.test_day_plan_store tests.test_review_queue_advance tests.contract.test_state_sources_port tests.contract.test_route_plan_port tests.contract.test_planner_port tests.contract.test_topic_weights_port` |
```

## 7. 建议

1. D2 / D3 另开工作包修（见 §3），届时把 `parse_day_plan` 的日期 / 数值类型行为写进规格 §3 并补测试。
2. D1、D4、D7、D8 汇入 `docs/安全风险登记.md`。
3. D9 的过时注释可在下次触碰 `day_plan_store.py` 时顺带更新（纯注释，不改输出）。
