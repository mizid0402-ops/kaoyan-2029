# WP-G3c：拆分 CLI 超长函数

## 改动

只改了 `ky/__main__.py` 中 `_preflight_main`、`day_plan_main` 的实现并增加私有步骤函数；新增固定基线对照测试 `tests/test_cli_split_baseline.py`。测试从 `b867ae7:ky/__main__.py` 载入旧入口，并断言旧版 `day_plan_main` 超过 200 行。

### 函数清单

行数为当前源文件中的函数行数。

| 函数 | 行数 | 职责 |
| --- | ---: | --- |
| `_preflight_main` | 44 | 依次编排参数、日期、usage、配置/队列/注册表、冻结、裁剪、输出 |
| `_preflight_parse_date` | 8 | 解析日期并维持 usage 错误返回 |
| `_preflight_read_usage` | 21 | 读取并校验 usage JSON |
| `_preflight_load_context` | 18 | 加载配置、队列、注册表、availability、route 与预算 |
| `_preflight_policies` | 7 | 构造复习与冻结策略 |
| `_preflight_freeze` | 9 | 读取冻结锁存并评估冻结状态 |
| `_preflight_calculate` | 22 | 计算复习裁剪与新内容分配 |
| `_preflight_print_summary` | 32 | 输出预算、冻结与时间线摘要 |
| `_preflight_print_review_lists` | 33 | 输出复习队列各状态列表 |
| `_preflight_print_allocations` | 9 | 输出新内容分配及容量状态 |
| `day_plan_main` | 9 | 校验 action 并分派 submit / record |
| `_day_plan_submit_parser` | 16 | 构造 submit 参数解析器 |
| `_day_plan_submit` | 24 | 加载注册表、availability、配置并构造存储端口 |
| `_day_plan_submit_apply` | 18 | 校验计划来源、应用提交并输出结果 |
| `_day_plan_record_parser` | 17 | 构造 record 参数解析器 |
| `_day_plan_record` | 32 | 按原顺序编排 record 各步骤 |
| `_day_plan_record_workspace` | 12 | 单次处理可选/必需注册表与计划存储路径 |
| `_day_plan_record_event` | 18 | 读取 YAML 并解析完成事件 |
| `_day_plan_record_preflight` | 10 | 写入前预检 review queue |
| `_day_plan_record_freeze` | 9 | 冻结状态锁存 |
| `_day_plan_record_write` | 6 | 写入完成事件 |
| `_day_plan_record_advance` | 34 | 推进队列并收集出题建议 |
| `_day_plan_record_output` | 14 | 分派 JSON / 文本输出 |
| `_day_plan_record_payload` | 17 | 组装 JSON 结果 |
| `_day_plan_record_print_queue` | 17 | 输出队列推进摘要与跳过原因 |
| `_day_plan_record_print_suggestion` | 15 | 输出单条出题建议 |

拆分保持配置读取、队列预检、冻结锁存、完成事件写入、队列推进与出题建议的先后顺序。私有辅助函数均不超过 60 行。

## 对照覆盖

共 28 组旧版/新版 CLI 调用，逐字节比较 `(returncode, stdout, stderr)`；每轮旧版与新版分别重建场景目录和写入存储。

- Preflight：12 组，含正常文本/JSON、满载、违规配置、usage 缺失/非 JSON/非法值、无注册表、无效注册表、冻结锁存/阈值、日期与 usage 同时非法的首报顺序探针。
- `day-plan submit`：6 组，含人工计划、staging 成功，过期输入包，冻结拒绝，staging 路径拒绝，手填单项上限。
- `day-plan record`：10 组，含默认/显式 store、review store 有无、无注册表/无效注册表/有效注册表、出题核对建议、队列预检失败、JSON/文本输出。

## 撤修改验证

临时将 `_preflight_main` 中日期解析与 usage 读取顺序对调，运行：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; py -3.12 -m unittest tests.test_cli_split_baseline.CliSplitBaselineTests.test_preflight_cli_bytes_match_fixed_baseline
```

结果：失败，`preflight-order-probe` 比较到新版先报 `--usage file is not valid JSON`，旧版先报 `--date must be an ISO date`。退出码 1。随后恢复原调用顺序。该变异运行禁用了 bytecode 缓存。

## 验收

执行：

```text
py -3.12 -m unittest tests.test_cli tests.test_cli_split_baseline tests.contract.test_freeze_port tests.contract.test_planner_port
```

结果：`Ran 91 tests in 52.704s`，`OK`。期间曾发现出题建议文本空格差异并修复；修复后指定验收通过。

中文文件检查：`rg -n '\?\?\?' ky/__main__.py tests/test_cli_split_baseline.py review/rounds/round-144-wp-g3c-luna.md` 无匹配。

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。

## 建议

提交前由决策者统一运行全量测试。建议后续 CLI 拆分沿用固定提交基线与 stdout/stderr 字节对照，重点覆盖多个输入错误同时出现时的首报顺序。
