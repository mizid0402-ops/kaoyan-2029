# 第 247 轮：WP-M28c 实现记录

## 改动与做法

- `settings.pacing` 接入 preflight、M19 日输入包、resume、timetable show 和报告。各调用点把已登记设置的 `start` / `initial` 传给 M8；未登记时传 `None`。M19 在仅登记 pacing、未登记 availability / timetable 时仍输出含 `base_minutes` / `base_source` 的 availability 对象。
- 报告逐日按 M8 计算 `base` 与 `reference_minutes`，并在 `base.source_note` 标出三级来源。M19/报告所用输入仍由装配层传入；提交时用同一份 availability、timetable、route、config 对象做输入包 freshness 重算和护栏校验。
- 新增 `ky/pacing/input.py`，实现 pacing 输入包、M19 规范 JSON 哈希、`base_at(T)` 和 staging 路径包含检查。新增 `ky/pacing/submit.py`，实现方案形状 / 意图校验、七条新提交护栏、候选路线转换、写一次意图、正式发布和三状态恢复；`--dry-run` 覆盖全部分支。
- `RoutePlanStore.read_revision_context()` 单次读取 manifest 快照并返回 current revision 与目标修订的 actor、input hash、已验证路线。无 manifest 时提供空状态 `current_revision=0`，供“意图已发布、路线尚未发布”的恢复使用；原写端持锁后的 manifest 重读未改。
- 新增 `ky pacing status`，显示当前基数来源、下次复盘日和未出报告周期。preflight 提醒在文本模式写 stdout，在 JSON 模式写 stderr，以保持 JSON 正文原样。
- 同步 `contracts/pacing_review.md` 报告基数来源形状与 `contracts/route_plan.md` 读端口。新增测试覆盖固定基线、pacing-only availability、报告/输入/状态、七条护栏拒绝、提交与恢复状态、空路线存储读端口。

## 验收

按任务书运行：

```text
py -3.12 -m unittest tests.contract.test_pacing_port tests.contract.test_route_plan_port tests.contract.test_day_budget_port tests.contract.test_planner_port tests.contract.test_resume_port tests.contract.test_timetable_io_port tests.test_cli
```

结束输出原文：

```text
written: C:/Users/Lenovo/AppData/Local/Temp/tmpbu7echki/human-routes/route--r1.yaml (revision 1, sha256 639d58ce3a9ae3d84f2d8ac9d8c6992cf108233fe1e13c86f53865df0188c573)
written: C:/Users/Lenovo/AppData/Local/Temp/tmpbu7echki/data/routes/route--r1.yaml (revision 1, sha256 8c6b098c2939060156b7c6675e7f570ea6d33a5bc9c60794e4ba92e346b43c8c)

----------------------------------------------------------------------
Ran 159 tests in 114.850s

OK
```

`git diff --check` 通过。指定文件的 `???` 检查无命中。未提交。

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）

## 歧义与选择

- 本 worktree 没有 `ky/timetable_io.base_resolver`；实际 M8 解析端口是 `ky.schedule.budget.resolve_day_budget`。按任务书要求接入该现有端口，没有另造 resolver。
- `ky pacing submit` 的命令形式没有 `--config` 参数，因此 freshness 重算和护栏配置均使用 workspace 登记的 `settings.exam_config`；缺失 / 无效按契约错误处理。
- 恢复时缺少 routes manifest 视为 revision 0 的空路线状态；损坏或存在但无效的 manifest 仍按存储契约报错，不降级为空状态。
- JSON 模式的提醒写到 stderr，避免提醒行破坏原 JSON 输出流。

## 第 251 轮返工

### 逐项做法

- **C1**：摘要现在同时接收旧路线、方案、设置和输入包。新提交使用护栏校验返回的旧路线；恢复 / 历史应用从保存输入包的 `current_route` 取旧值，缺省路线的旧复习分钟显示 `-`。证据逐路径从 `report` 取值并用 `json.dumps(..., ensure_ascii=False)` 输出。摘要补齐阶段结束日、生效日期上限与来源、课表缩放三行；正式提交在发布意图前先打印摘要。切段 label 改为 `f"{phase.label} · 复盘 {cycle_end}"`，测试断言完整五种路线转换的旧段 / 命中段 / 后续段、重编号和 hash。
- **C2**：移除入口分流前的 pacing 登记门槛，把门槛留在新提交支路。恢复分支使用输入包中持久化的设置与路线，不加载当前设置文件；补 CLI 测试覆盖移除登记后 dry-run 与正式恢复。
- **C3**：恢复状态按指定文案输出。已生效分支区分历史应用并展示意图摘要；待恢复 dry-run 打印摘要和完整候选路线。正式新提交与恢复发布失败均保留原契约错误、追加重跑提示，意图文件不删除。
- **C4**：固定基线仍为 `636bd09`；身份测试同时断言旧 `ky/__main__.py` 含旧调用片段且不含接线片段、当前文件反向成立。补充 CLI 测试覆盖 exam_date 修改后的无路线恢复、跨日新鲜度拒绝、护栏拒绝零写入、已生效后的 r3 历史应用、待恢复 dry-run 三类文件字节保持，以及注册表驱动的 timetable / resume / preflight 设置接线与提醒出现 / 不出现。
- **C5**：更新 `ky/pacing/port.py`、`submit.py`、`input.py`、`cli.py` 模块头，标明 M28、规格和公开接口；submit 头明确 §6–§7。
- **补充规格与 CLI**：§4 已登记输入包 `settings` 的展平形状；报告来源变化提示已恢复 §3 原句 `报告生成后记录有变化，已保存的报告不变`。

### 验收

运行命令：

```text
py -3.12 -m unittest tests.contract.test_pacing_port tests.contract.test_route_plan_port tests.contract.test_day_budget_port tests.contract.test_resume_port tests.test_cli
```

终端结束输出原文：

```text
written: C:/Users/Lenovo/AppData/Local/Temp/tmpbu7echki/human-routes/route--r1.yaml (revision 1, sha256 639d58ce3a9ae3d84f2d8ac9d8c6992cf108233fe1e13c86f53865df0188c573)
written: C:/Users/Lenovo/AppData/Local/Temp/tmpbu7echki/data/routes/route--r1.yaml (revision 1, sha256 8c6b098c2939060156b7c6675e7f570ea6d33a5bc9c60794e4ba92e346b43c8c)

----------------------------------------------------------------------
Ran 159 tests in 114.850s

OK
```

`git diff --check` 通过；本轮改动文件 `rg -n '\?\?\?'` 无命中。

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）

### 第 251 轮最终验收补记

- **C1**：新提交摘要以旧路线为参照；恢复摘要从保存输入包读取旧路线、设置与报告证据。证据逐路径输出 JSON 值，缺旧路线时显示 `-`，并显示阶段失效边界、较早的考试日期上限及课表缩放说明。成功提交测试断言摘要先于 `submitted:`；意图发布失败注入也确认摘要已先输出。切段 label 与规格一致，并断言了保留段、命中段、后续段、重编号和 `stage1_input_hash`。
- **C2**：`settings.pacing` 门槛仅在新提交分支检查。CLI 测试移除登记后，dry-run 不写文件，正式恢复发布已保存候选；恢复过程更改当前 `exam_date`，候选终点仍取保存包中的值。
- **C3**：已生效的正式与 dry-run 输出均断言历史应用状态且不发布；待恢复 dry-run 对意图及路线文件字节做前后比较并打印完整路线；路线发布注入 `StorageError` 后返回 2、保留意图并输出重跑提示。
- **C4**：旧版身份测试固定 `636bd09`，同时断言该版本含旧调用、不含新接线，而当前文件相反。CLI 测试覆盖跨日 freshness 拒绝、零写入护栏、注册表驱动的 timetable/resume/preflight 接线及提醒出现/消失。
- **C5**：更新 `port.py`、`submit.py`、`input.py`、`cli.py` 模块头；规格登记输入包 `settings` 的展平形状及 §6.2 文案。报告来源变化提示恢复为 §3 原句。

验收命令首次执行时有一项测试夹具错误：

```text
ERROR: test_report_cli_saved_report_repeat_and_exit_codes (tests.contract.test_pacing_port.PacingCliContractTests.test_report_cli_saved_report_repeat_and_exit_codes)
NameError: name 'RoutePlanStore' is not defined
Ran 117 tests in 106.860s
FAILED (errors=1)
```

补上测试导入后，按 AGENTS.md 只重跑受影响模块；最终输出原文：

```text
py -3.12 -m unittest tests.contract.test_pacing_port
.课表不覆盖此日
...........
----------------------------------------------------------------------
Ran 12 tests in 14.801s

OK
没有需要重排的积压
正在恢复提交
effective_from: 2026-10-16
base: 180 -> 180
review_minutes.cs408: - -> 20
review_minutes.eng1: - -> 20
review_minutes.math1: - -> 20
调整在 2028-12-23 日阶段结束后失效
生效日上限：2028-12-23（取自设置 exam_date）
有课表的日子，M8 仍会按当日容量缩放复习配额
rationale: adjust
evidence: report.cycle.end = "2026-10-15"
已完成上次中断的提交
```

首次组合运行中的其余四个验收模块均执行完毕；组合运行唯一失败项已在上述受影响模块重跑通过。`git diff --check` 通过；指定文件 `rg -n '\?\?\?'` 无命中。不提交。

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）
