# 第 222 轮：WP-T2 课表接入与 CLI

## 改动文件

- `ky/availability/port.py`、`ky/availability/__init__.py`：M26 增加 `DerivedDailyMinutes` 协议；`DailyMinutes.source` 增加 `timetable`；解析优先级为手填单日（含 0）→ 课表结果（含 0）→ 调用方基数。M26 不导入 M18。
- `ky/schedule/budget.py`：M8 增加 `daily_base_minutes(config)`，本包返回 `config.default_daily_minutes`；`resolve_day_budget(..., timetable=None)` 将同一基数传入 M26；`DayBudget.total_source` 支持 `timetable`。函数说明 M28 将在基数函数扩展路线与设置优先级。
- `ky/__main__.py`：preflight 加载一次日历并交给 M8；冻结分支仍优先使用 0 与 `drop_when_short`；课表来源时在 `daily budget` 下一行打印学期、周、星期、follow 目标、大节、空闲分钟和待确认节次。新增 `timetable show` / `check` CLI。
- `ky/planner/port.py`：M19 一次加载日历并传入 M8；`availability` 字段在 availability 或 timetable 任一登记时输出解析结果，课表未覆盖的日期输出 `config` 来源。
- `ky/freeze/resume.py`：`plan_resume(..., timetable=None)` 沿候选日搜索链向 M8 传同一 provider；`ky/__main__.py` 的 resume 上下文只构造一次日历。
- `contracts/availability.md`、`contracts/route_plan.md`、`contracts/planner_port.md`：同步协议、来源优先级、日基数、裁剪来源和 M13 硬上限说明。
- `tests/contract/test_availability_port.py`：覆盖三层优先级、手填 0、课表 0、课表 `None` 回落。
- `tests/contract/test_day_budget_port.py`：覆盖课表分钟与阶段配额按硬上限缩放；覆盖 preflight 的课表 override、冻结优先、学期外 config/strict；包含固定提交对照测试。
- `tests/contract/test_planner_port.py`：覆盖仅登记课表时的课表来源与学期外 config 来源。
- `tests/contract/test_resume_port.py`：验证同一 provider 在多个候选日参与预算解析。
- `tests/contract/test_day_plan_store_port.py`：验证课表推算分钟不成为 M13 存储硬上限，手填值仍生效。
- `tests/test_cli.py`：覆盖课表网格、日期展示、未登记/学期外展示、周次和学期用法错误、check 冲突与待确认列表、候选档案独立校验、契约错误退出码及 preflight 详情行。

本轮没有修改 `ky/timetable/`、投影、`kaoyan.workspace.yaml`、真实数据、`docs/模块地图.md` 或 README。工作区同时存在此前 WP-T1 的课表注册表改动；本轮沿用该接口。`git diff` 对 `ky/timetable/calendar.py` 与 `tests/contract/test_timetable_port.py` 无已跟踪差异，因为这两个文件在当前工作树是未跟踪文件；已直接核实其当前函数签名：`timetable_for_workspace(workspace)`，日历方法的 `base_minutes` 为必填参数，没有改回上一轮 config 接口。

## 固定提交逐字节对照

在 `tests/contract/test_day_budget_port.py` 使用 `tests/_baseline_harness.py`：`fixed_source` 固定读取 `e381792` 并断言旧版 `ky/availability/port.py` 中 `resolve_daily_minutes` 的参数含 `config: KaoyanConfig`；测试通过 `git archive e381792 ky` 解出完整旧版 `ky/`，以旧包 `PYTHONPATH` 运行。对同一临时工作区逐条比较 preflight 文本、preflight `--json`、`planner-input --kind day`、`resume --dry-run` 的 return code、stdout、stderr 与全部工作区文件原始字节。对照通过，未对字节做归一化。

## 验收

任务书指定命令：

```text
py -3.12 -m unittest tests.contract.test_timetable_port tests.contract.test_availability_port tests.contract.test_day_budget_port tests.contract.test_planner_port tests.contract.test_resume_port tests.contract.test_freeze_port tests.contract.test_route_plan_port tests.contract.test_day_plan_store_port tests.test_cli
```

该命令输出原文摘要：

```text
Ran 176 tests in 63.248s

OK
```

最后修改 CLI 展示行及错误用例后，受影响模块复跑输出原文：

```text
Ran 74 tests in 37.401s

OK
```

复跑命令：

```text
py -3.12 -m unittest tests.test_cli tests.contract.test_day_budget_port
```

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。乱码占位符检查与 `git diff --check` 无输出。

## 歧义选择

- `timetable show` 的 `--config` 设为必填，与规格 §8“与 preflight 相同的取法”一致；`check --school FILE` 在解析后直接校验候选文件，不查工作区注册表，即使命令带有无效 `--workspace` 也不会读取它。
- `check` 对每条可判定的课程冲突输出一行，待确认节次按学期汇总；规格要求列出这些信息但未钉死输出文案与排序，采用课表文件顺序及节次升序。
- 每周网格的列顺序采用周一至周日，最后分钟行按相同顺序输出；课程单元使用 `/` 分隔。规格定义了网格内容，未规定具体字符排版。
- `daily_base_minutes` 目前只返回 config 默认值；路线与设置优先级没有提前实现，留待 M28 按其规格落地。
