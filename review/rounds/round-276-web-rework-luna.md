# 第 276 轮返工报告：M33 今日视图与 M16 本机网页

日期：2026-10-02

本轮中途被中断一次后续跑；最终验收在临时工作区隔离下完成。

## 修改文件

- `ky/today/record.py`、`ky/today/port.py`：阶段码、记录与补推进共用管线、单次配置读取。
- `ky/__main__.py`：恢复命令及 advance 路径复用 record 解析函数。
- `ky/pacing/port.py`、`ky/pacing/cli.py`：合并未报告周期计算，status 使用共享计算端口。
- `ky/web/server.py`、`ky/web/cli.py`：页面与 POST 路由拆分、日期注入、端口占用识别。
- `contracts/today.md`：说明网页提交 ID 校验；契约测试更新于 `tests/contract/test_today_port.py`、
  `tests/contract/test_web_port.py`。
- `tests/test_cli.py`：冻结失败注入改为 patch M33 共用锁存函数；第 275 轮其他文件见旧报告。

## 逐项整改

1. `record_loaded_event` 依据 `_latch_freeze` 返回的 bool 标记 `freeze_written`；CLI 与 M33 共用它，
   移除了 CLI 冻结 handler 特殊分支。
2. `event_written` 只追加一条可复制恢复命令，包含显式 store / review-store / config；显式
   `--workspace` 也保留，以确保显式注册表下的路径选择一致。
3. `day-plan advance` 调用 record 的工作区与 config 解析函数；CLI 和 `advance_recorded_day`
   共用 `advance_loaded_event`。
4. `record_day` 使用装配时读取的 config。网页不再先 `load_today`；可选
   `submitted_review_ids` 让 M33 校验包括 skip 在内的表单 ID，skip 不进入 outcomes。
5. `missing_report_cycles` 唯一实现位于 `ky/pacing/port.py`，今日视图与 pacing status 共用。
6. 网页按标题、冻结、时间、复习、记录、可用时间、复盘拆渲染；每个 POST 路由单独处理。
7. 缺题项显示“对照后：对 / 半对 / 错”；科目显示配置中文名；冻结列积压分钟和阈值；
   复盘列未报告周期并提示“请让 AI 出复盘报告”。`make_server` 可注入日期，默认仍取系统日。
8. `WinError 10013` 也按端口占用处理并提示更换端口。

## 提取函数

| 函数 | 模块 | 规格 |
|---|---|---|
| `calculate_preflight` | `ky/today/compute.py` | today §1(a) |
| `review_question_records`、`build_review_questions` | `ky/today/questions.py`、`ky/today/compute.py` | §1(b) |
| `missing_report_cycles`、`pacing_status_result` | `ky/pacing/port.py`、`ky/today/compute.py` | §1(c) |
| `record_loaded_event`、`advance_loaded_event`、`record_report_mapping` | `ky/today/record.py` | §1(d)、§4、§4.1 |
| `load_today`、`today_view_hash`、`record_day`、`advance_recorded_day` | `ky/today/port.py` | §2–§4.1 |
| `set_day_minutes` | `ky/availability/port.py` | today §5 / M26 |
| `make_server`、`web_main` | `ky/web/server.py`、`ky/web/cli.py` | web 全文 |

## 固定基线与覆盖

- 固定 `60a4fd2`，`fixed_source` 检查旧 CLI 函数身份；单个表驱动 `subTest` 在同一临时路径
  分别重置旧 / 新种子，对比退出码、stdout、stderr 和完整 `output_tree` 原始字节。
- `preflight`：注册表缺省文本 / JSON、无注册表显式 config/items、usage、urgent / 冻结阈值、
  锁存冻结日；`review-questions` 文本 / JSON（含改编题停用提示）；`pacing status`。
- `day-plan record`：显式 store/review-store、注册表缺省、JSON、空事件与输出文件树。
  单独推进失败对照断言 stdout / 文件树相同，stderr 只多恢复命令行。
- M33：哈希、拒绝不写、缺题 / 改编题 / 真题、课表命中 / null、路线阶段、未报告周期、
  两类部分失败阶段与持久文件、pending 视图、恢复后重放、CLI 与端口事件字节及队列一致。
- M16：回环线程服务、port 0、no-open 地址、占用端口退出 2、超限 400、跨午夜、两种失败页、
  unknown ID（包括 skip）、表单 C 两种结果；页面检查转义、中文科目、缺题选项、冻结和复盘字段。
- 临时数据均在系统临时目录。完整验收时以合成临时注册表隔离隐式发现；网页 today 注入默认语义不变。

## 验收、限制与建议

- 指定验收命令：`Ran 151 tests in 169.949s`，`OK`。
- 后续将冻结夹具规模改为按配置阈值推导：`Ran 10 tests in 28.302s`，`OK`；
  增加 submitted ID 校验与契约说明后，受影响模块：`Ran 18 tests in 32.046s`，`OK`。
- `git diff --check` 无输出；未发现连续问号乱码；新网页和契约测试代码行宽不超过 100。
- 全量未跑（按 `AGENTS.md`，由决策者提交前统一跑）；未提交。
- 未覆盖：网页并发压力、真实 timetable / route 文件端到端装配（映射测试使用合成对象）。
- 规格补充：网页需拒绝未知 skip ID，但 M33 的 outcomes 不含 skip；增加 `submitted_review_ids`
  供 `record_day` 写前校验。显式 `--workspace` 随恢复命令保留，以维持 record 路径选择。
- 安全登记同第 275 轮；未扩展 CSRF / 身份认证防护。

建议决策者提交前运行全量测试，并独立复审 M33 / M16；如需增强装配证据，可补合成
timetable 与 route 文件端到端夹具。
