# 第 275 轮实现报告：M33 今日视图与 M16 本机网页

日期：2026-10-02

本轮中途被中断一次后续跑；中断发生在验收模块运行过程中。

## 修改文件

- `ky/today/__init__.py`：导出 M33 四个公开接口。
- `ky/today/compute.py`：预检、复习出题与 M28 状态计算。
- `ky/today/questions.py`：从已加载题库、完成事件与题目索引构造 M31 复习题映射。
- `ky/today/record.py`：复用的完成事件持久化、队列推进管线及 CLI 报告映射。
- `ky/today/port.py`：今日视图装配、视图哈希、记录和补推进端口。
- `ky/availability/port.py`、`ky/availability/__init__.py`：新增并导出 `set_day_minutes`。
- `ky/pacing/cli.py`：`pacing status` 调用共享状态映射计算。
- `ky/web/__init__.py`、`ky/web/cli.py`、`ky/web/server.py`：M16 页面、HTTP 服务和命令。
- `ky/__main__.py`：预检 / 出题 / 记录 CLI 改用共享计算；增加 `day-plan advance` 与 `web`。
- `contracts/availability.md`：M26 接口说明指向 `today.md` §5。
- `docs/模块地图.md`：登记 M16、M33。
- `docs/安全风险登记.md`：按 M16 §7 登记无 CSRF / 身份认证的本机 POST 风险为 S20。
- `README.md`：增加网页与补推进命令。
- `tests/contract/test_today_port.py`、`tests/contract/test_web_port.py`：M33 / M16 契约与基线测试。

## 提取的计算 / 管线

| 函数 | 模块 | 对应规格 |
|---|---|---|
| `calculate_preflight` | `ky/today/compute.py` | M33 §1(a)：M9 结果、分配和预检 JSON 映射 |
| `review_question_records`、`build_review_questions` | `ky/today/questions.py`、`ky/today/compute.py` | M33 §1(b)：M31 `reviews` 记录列表 |
| `pacing_status_result` | `ky/today/compute.py` | M33 §1(c)：基数、下次复盘和未报告周期映射 |
| `record_loaded_event` | `ky/today/record.py` | M33 §1(d)、§4：冻结锁存、写事件、推进队列 |
| `record_report_mapping` | `ky/today/record.py` | M33 §1(d)：`day-plan record` 报告映射 |
| `load_today`、`today_view_hash` | `ky/today/port.py` | M33 §2–§3.2 |
| `record_day`、`advance_recorded_day` | `ky/today/port.py` | M33 §4–§4.1 |
| `set_day_minutes` | `ky/availability/port.py` | M33 §5 / M26 |
| `make_server`、`web_main` | `ky/web/server.py`、`ky/web/cli.py` | M16 全文 |

## 基线与验收

- 基线测试通过 `fixed_source` 固定到 `60a4fd2`，并断言旧源码包含旧版预检与出题入口；使用 `compare_runs` 按退出码、stdout、stderr 原始字节比较。
- 本轮固定基线样例覆盖：显式 `--config` / `--items`、指定日期的 `preflight --json`；输入文件来自基线提交并在新旧进程间共用。
- **尚未纳入固定基线对照的分支**：工作区缺省、`--usage`、冻结与 urgent 参数、冻结日、显式 store 的 record、`review-questions` 文本 / JSON、`pacing status`、写入文件字节及推进失败恢复提示。既有 `tests.test_cli` 通过，但不能替代这些分支相对 `60a4fd2` 的逐字节证据。
- 首次按任务书完整验收命令运行：`Ran 139 tests in 145.370s`，`OK`。
- 后续改动仅涉及 M33 / M16 端口、网页渲染和对应契约测试；按最小范围重跑：`Ran 8 tests in 5.773s`，`OK`。
- 全量测试未运行；未提交。
- `git diff --check` 无输出；本轮编辑文件未见连续问号乱码。

## 契约测试覆盖

- M33：身份字段影响 `view_hash`、无课表与冻结锁存映射、M26 规范重写 / 越界 / 删除不存在项拒绝、过期哈希与未知 review ID 写前拒绝、空记录拒绝、已记录读取、补推进重复调用。
- M16：线程启动的 `ThreadingHTTPServer`、`--port 0` 实际本机绑定、GET 今日页、题干 / 选项 / 答案 HTML 转义、可用分钟 POST、记录 POST、重复提交拒绝、未知表单字段拒绝。
- 本轮新增的契约测试仅在系统临时目录建数据。
- 限制说明：既有 `tests.test_cli` 的 `run_cli` 子进程以仓库根为 cwd，部分显式 `--config` / `--items` 用例仍会走工作区发现；首次基线对照也曾在仓库根执行并观察到预算受当前注册表影响。该用例只跑只读 `preflight`，但不能据此保证未读取真实 `data/plans/`、`state.routes`、课表或可用时间文件。之后已把新增基线对照移到临时 cwd；不再重跑该既有模块。

## 实现备注

- 网页只使用标准库 HTTP 服务和普通表单；没有 JavaScript，CSS 内联并响应系统浅 / 深色设置。
- HTTP 服务固定绑定 `127.0.0.1`；`ThreadingHTTPServer` 允许请求并发处理，所有 POST 从读表单到完成写入持同一把模块级锁。
- POST 只接受表单编码，拒绝重复字段、未知字段和超过 64 KiB 的请求体；契约拒绝返回 400，未预料错误写 stderr 并返回简短 500 页面。
- 网页数据每个 GET 重新经 `load_today` 读取；未读投影，也没有服务端缓存。
- 表单写入只调用 M26 `set_day_minutes` 与 M33 记录 / 补推进端口；失败页按 `stage` 属性处理部分持久化状态。
- CLI `day-plan record` 保留原来的参数读取和打印分支，冻结 / 写事件 / 推进与 M33 调用同一个 `record_loaded_event` 管线。
- 所有本轮新增测试工作区建于系统临时目录；新增固定基线子进程也在临时 cwd 运行。

## 规格待补证 / 建议

1. 目前 `record_day` 的实际复习题成功写入、部分完成、冻结后事件写失败、事件已写但队列推进失败，尚缺 M33 / M16 契约测试覆盖；应补写阶段故障注入和队列状态断言。
2. `load_today` 的缺题 / 改编题 / 真题映射、课表命中与不命中、路线阶段、未报告周期尚未在本轮测试逐项固定。
3. M16 的 `--no-open` 命令路径、端口占用退出码 2、请求体上限、跨午夜拒绝及部分失败页面尚未直接测试。
4. §6 要求的 CLI 基线分支矩阵较大；建议增加共用临时工作区下的旧版 / 新版逐字节运行矩阵，特别包含 `review-questions`、`pacing status` 和 `day-plan record` 文件树对照。
5. M33 §3 要求 `reviews` 与 `review-questions --json` 的列表完全一致，同时 §3.2 规定缺题哈希使用 `recall_vs_notes` / `null`；实现保持列表原样，哈希与记录事件在计算时应用该缺省值。
6. `record_day` 返回与 `day-plan record` 相同形状的报告映射；补推进端口返回 `advanced` 与推进 / 重放 ID，网页据此显示完成或无需重放。
7. 安全类按威胁模型仅登记、不扩展防护；S20 已加入安全风险表。
