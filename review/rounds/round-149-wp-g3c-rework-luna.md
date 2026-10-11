# WP-G3c 返工报告

## 改动落点

- **M1**：`tests/test_cli_split_baseline.py` 的候选索引与权重夹具由 YAML 写入改为 `json.dumps` 写入合法 JSON。`record-needs-question` 断言 JSON 候选及其 `candidates` 均非空、没有 skip 字段；新增文本模式场景并断言确实打印 `temporary-question` 建议行。
- **M2**：新增 `record-advance-failure` 与 `record-freeze-write-failure`。测试对旧版和新版分别替换 `advance_review_queue`（抛 `ContractError`）及 `_latch_freeze_if_needed`（抛 `StorageError`），比较退出码、stdout、stderr，并断言完成事件文件分别已写入、未写入。所有 `record-*` 场景都检查完成事件文件状态；队列预检失败同样断言未写入。
- **M3**：新增 preflight 的 usage/config、config/policy、锁存冻结 JSON 场景；submit 的 registry/config 场景；record 的 registry/config、config/missing-done、queue-preflight/freeze、event/review-store 场景。场景均以固定基线 `b867ae7` 对照。
- **M4**：`_day_plan_record_advance_queue` 只推进队列，推进失败保留原错误输出并以退出码 2 结束；`_day_plan_record_query_candidates` 独立查询候选，`ContractError` 转为 skip 原因并继续输出。
- **S1**：record 步骤以私有 `_CliExit` 携带既有退出码；步骤成功时返回对应结果，不再把整数退出码与成功结果混合作为返回类型，也没有 `isinstance(..., int)` 分派。输出与退出码由字节对照覆盖。

## 拆分函数

| 函数 | 行数 | 职责 |
|---|---:|---|
| `_preflight_main` | 44 | 按原顺序解析日期、读 usage、加载上下文、构造策略、冻结判定、计算并输出 |
| `_preflight_parse_date` | 8 | 解析日期并保留 usage 错误输出 |
| `_preflight_read_usage` | 21 | 读取并验证 usage JSON |
| `_preflight_load_context` | 18 | 加载配置、队列、可选注册表与预算上下文 |
| `_preflight_policies` | 7 | 构造 review 与 freeze 策略 |
| `_preflight_freeze` | 9 | 读取锁存状态并评估冻结 |
| `_preflight_calculate` | 22 | 裁剪复习并计算新内容分配 |
| `_preflight_print_summary` | 32 | 输出 preflight 摘要 |
| `_preflight_print_review_lists` | 44 | 输出复习清单 |
| `_preflight_print_allocations` | 9 | 输出新内容分配及容量状态 |
| `day_plan_main` | 9 | 子命令解析与 submit/record 分派 |
| `_day_plan_submit` | 24 | submit 参数解析、注册表/配置加载及提交准备 |
| `_day_plan_submit_apply` | 18 | 解析计划来源、执行提交并输出结果 |
| `_day_plan_record` | 31 | 按固定顺序调用 record 步骤并统一处理 `_CliExit` |
| `_day_plan_record_workspace` | 12 | 解析存储路径及可选注册表 |
| `_day_plan_record_event` | 18 | 读取并解析完成事件 |
| `_day_plan_record_preflight` | 9 | 写入前预检队列引用 |
| `_day_plan_record_freeze` | 8 | 在事件写入前检查并锁存冻结 |
| `_day_plan_record_write` | 6 | 写入完成事件 |
| `_day_plan_record_advance_queue` | 10 | 推进复习队列，失败退出 2 |
| `_day_plan_record_query_candidates` | 17 | 查询出题候选，失败记录 skip 原因 |
| `_day_plan_record_output` | 14 | 组织 JSON 或文本输出 |
| `_day_plan_record_payload` | 20 | 组装 JSON 输出对象 |
| `_day_plan_record_print_queue` | 19 | 输出队列推进与建议摘要 |
| `_day_plan_record_print_suggestion` | 22 | 输出单条出题建议 |

其余列入拆分的纯输出辅助函数均为 2–5 行。以上拆分辅助函数均不超过约 60 行，主流程嵌套不超过三层。

## 对照场景类别与数量

固定旧版通过 `git show b867ae7:ky/__main__.py` 取得；测试断言基线中的 `day_plan_main` 超过 200 行，再以旧版模块入口与当前 CLI 分别执行。每次执行前重建场景目录和写入型存储，比较 `(退出码, stdout, stderr)` 原始字节。

- **preflight：15 个场景**：正常文本、正常 JSON、满载、非法配置、usage 缺失/非 JSON/非法值、无注册表、无效注册表、冻结锁存、冻结达阈值、冻结锁存 JSON、日期/usage 双错、usage/配置双错、配置/策略双错。
- **day-plan submit：7 个场景**：`--plan` 成功、`--from-staging` 成功、过期输入、冻结拒绝、staging 路径拒绝、单项上限拒绝、注册表/配置双错。
- **day-plan record：17 个场景**：默认存储（含/不含 review）、显式存储、无注册表、注册表缺失/无效、无效注册表默认存储、配置/缺失 done 双错、注册表/配置双错、普通成功、JSON 候选成功、文本候选成功、队列预检失败、队列推进注入失败、冻结锁存写入注入失败、队列预检/冻结双错、完成事件解析/review-store 双错。
- **合计：39 个调用场景**。所有变体均对照固定基线；record 场景另断言完成事件文件是否存在。

## 相邻步骤顺序变异

每项均对当前步骤调用顺序做交换，清理 `ky/` 与 `tests/` 下的 `__pycache__`/`.pyc`，设置 `PYTHONDONTWRITEBYTECODE=1` 后运行对应对照测试。以下变异均按预期变红（测试进程退出码 1）：

| 相邻步骤 | 捕获场景 | 实际观察 |
|---|---|---|
| preflight 日期解析 / usage 读取 | `preflight-order-probe` | 旧版报日期错误，变异版报 usage JSON 错误 |
| preflight usage 读取 / 上下文加载 | `preflight-usage-config-order` | 旧版先报 usage JSON 错误，变异版先报配置错误 |
| preflight 上下文加载 / 策略校验 | `preflight-config-policy-order` | 旧版先报配置错误，变异版先报策略 usage 错误 |
| preflight 冻结字段加入 / JSON 输出 | `preflight-freeze-latched-json` | JSON 字节不同，变异版缺少应有的 freeze 字段 |
| preflight 摘要 / 复习清单 | `preflight-normal-text` | stdout 行序不同 |
| preflight 复习清单 / 分配输出 | `preflight-normal-text` | stdout 行序不同 |
| submit 注册表/存储解析 / 配置加载 | `submit-registry-config-order` | 先报的无效注册表与配置错误不同 |
| record 注册表/存储解析 / 配置加载 | `record-registry-config-order` | 先报的无效注册表与配置错误不同 |
| record 配置加载 / 完成事件解析 | `record-config-missing-done` | 退出码及 stderr 不同：配置错误与缺少 done 文件 |
| record 完成事件解析 / review-store 构造 | `record-event-review-store-order` | 完成事件错误与注入的构造失败输出不同 |
| record 队列预检 / 冻结检查 | `record-queue-preflight-freeze-order` | 先报队列引用错误与注入冻结错误不同 |
| record 冻结检查 / 完成事件写入 | `record-freeze-write-failure` | 变异版在失败时已创建完成事件，状态断言失败 |

变异通过临时源代码重排注入，运行后恢复源文件。分组测试命令分别为：

```text
PYTHONDONTWRITEBYTECODE=1 py -3.12 -m unittest tests.test_cli_split_baseline.CliSplitBaselineTests.test_preflight_cli_bytes_match_fixed_baseline
PYTHONDONTWRITEBYTECODE=1 py -3.12 -m unittest tests.test_cli_split_baseline.CliSplitBaselineTests.test_day_plan_submit_cli_bytes_match_fixed_baseline
PYTHONDONTWRITEBYTECODE=1 py -3.12 -m unittest tests.test_cli_split_baseline.CliSplitBaselineTests.test_day_plan_record_cli_bytes_match_fixed_baseline
```

每项变异前后均清理 `ky/` 与 `tests/` 下的 `__pycache__`/`.pyc`。各项观察到测试退出码 1；未变异的对照测试通过。

## 验收

运行命令：

```text
py -3.12 -m unittest tests.test_cli tests.test_cli_split_baseline tests.contract.test_freeze_port tests.contract.test_planner_port
```

结果：`Ran 91 tests in 59.646s`，`OK`。

独立针对测试：`py -3.12 -m unittest tests.test_cli_split_baseline`，`Ran 3 tests in 26.870s`，`OK`。

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。

## 建议

目前对照覆盖记录了调用顺序、错误输出与存储副作用。后续若再拆 CLI 步骤，沿用固定提交基线，并保留注入失败时的写入状态断言。
