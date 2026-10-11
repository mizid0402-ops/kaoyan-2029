# 第 275 轮任务书：⑥ 前端首版实现（M33 今日视图 + M16 本机网页）（gpt-6-luna，luna-a）

## 背景

用户 2026-10-02 定 ⑥ 首版：本机小服务、"看 + 少量表单"、首版只做"今天"页。规格已经 sol 第 273 / 274 轮审过：
`contracts/today.md`（M33）、`contracts/web.md`（M16）。**规格是唯一依据**；与本任务书冲突时以规格为准，并在报告里指出。
先读仓库根 `AGENTS.md`（D7 可维护性、验证范围、编码、已知缺陷清单、迁移不得改变输出）。

## 要做的事（按顺序，每步做完再做下一步）

1. **提取公开计算函数**（`contracts/today.md` §1 (a)–(d)）：从 `ky/__main__.py` 的 `_preflight_*`、`review_questions_main` 相关辅助、
   `_day_plan_record_*`，以及 `ky/pacing/cli.py` 的 `pacing_status_main` 里提出"已加载上下文 → 结果"的函数，放进**非 CLI 模块**
   （新模块 `ky/today/` 或各自所属模块，选一个并在报告说明理由）；CLI 只保留参数、加载、打印，改为调用它们。
   **CLI 输出必须与固定基线 `60a4fd2` 逐字节一致**（§6 列出的全部分支），写成对照测试（`tests/_baseline_harness.py` 的 `fixed_source` /
   `compare_runs`；固定哈希、断言取到的是旧版；按原始字节比较，不用正则抹文字）。唯一允许的差异：§4.1 推进失败分支多出的提示行。
2. **M33 端口**：`load_today`、`today_view_hash`、`record_day`、`advance_recorded_day`（§2–§4.1），以及 CLI `ky day-plan advance`。
3. **M26 写入** `set_day_minutes`（§5），更新 `contracts/availability.md` 的接口一节（一句话指向 today.md §5）。
4. **M16 网页** `ky/web/` 与 `py -3.12 -m ky web`（`contracts/web.md` 全文）：只用标准库；服务端渲染、内联 CSS、无 JS；全部数据文字 HTML 转义；
   `ThreadingHTTPServer` + POST 进程内锁；只绑 127.0.0.1。页面样式朴素清楚即可（深浅色、手机宽度），不要做花哨设计。
5. **登记**：`docs/模块地图.md` 加 M16、M33 两行（规格 / 实现 / 登记键 / 可替换性 / 验收命令）；README 用法加 `ky web` 与 `ky day-plan advance` 各一行。

## 测试（只写这些）

- `tests/contract/test_today_port.py`：§3 映射字段（含无课表、冻结、缺题、已记录、未推进几种状态）；`view_hash` 规则；`record_day` 写前拒绝各分支不写文件；
  部分完成后 `advance_recorded_day` 可重复调用；`set_day_minutes` 规则；第 1 步的固定基线对照。
- `tests/contract/test_web_port.py`：`contracts/web.md` §6 列出的条目（线程里起服务，`--port 0`、`--no-open`，测试后 shutdown/join）。
- 临时工作区一律放系统临时目录；**不得**读写真实的 `data/personal/`、`data/review_queue/`、`data/plans/`、`data/routes/`。
- 测试不得把数据量写成字面量（`AGENTS.md` 第 7 条）。

## 验收（只跑这些模块）

```
py -3.12 -m unittest tests.contract.test_today_port tests.contract.test_web_port tests.test_cli tests.contract.test_question_bank_port tests.contract.test_pacing_port tests.contract.test_availability_port tests.contract.test_freeze_port tests.contract.test_resume_port
```

全量：不跑（按 `AGENTS.md`，由决策者提交前统一跑）。怀疑影响了其他模块时在报告列出模块名。

## 报告

`F:\workspace\kaoyan-ai-system\review\rounds\round-275-web-impl-luna.md`：改了哪些文件；提取后的函数清单（名字、所在模块、对应规格条目）；
对照测试覆盖的分支；验收命令输出的 `Ran …` 行；与规格不一致或规格没写清的地方；建议。约 80 行。

## 禁止

- 不提交；不跑全量；不联网；不改任务书没点名的模块行为；不删除任何用户可见文字（`AGENTS.md` 第 13 条）。
- 含中文的文件只用 `apply_patch` 或 UTF-8 `.py` 脚本写，不用 here-string 管道；写完查 `???`。
- 不读 `data/personal/` 与 gitignore 的学习状态。
