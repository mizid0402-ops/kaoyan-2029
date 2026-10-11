# 第 276 轮任务书：⑥ 前端首版返工（续 luna-a 第 275 轮）

决策者审了你第 275 轮的 diff 与报告。报告如实列出的缺口要补齐，另有几处代码问题。规格仍以 `contracts/today.md`、`contracts/web.md` 为准。

## 必须改：代码

1. **阶段码误判**：`ky/__main__.py` 的 `record` 给 `record_loaded_event` 传了 `freeze_handler=lambda: _latch_freeze_if_needed(...)`，
   而 `record_loaded_event` 只要 handler 返回就把 `freeze_written` 设为真——当天没触发冻结、完成事件写失败时会被误报为 `freeze_written`。
   改为 handler 返回"是否真的写了冻结事件"（bool），并删掉为 CLI 单独保留的 handler 分支，CLI 与 M33 用同一个锁存函数。
2. **恢复提示行**（today.md §4.1）：`record` 在 `event_written` 失败时多打印一行可复制的 `py -3.12 -m ky day-plan advance --date D …`，
   **带齐本次实际使用的 `--store` / `--review-store` / `--config`**（显式给了才带；缺省来自注册表的不带）。其余输出不变。
3. **`day-plan advance` 的路径规则**必须与 `record` 完全相同：复用 `record` 现有的工作区 / `--store` / `--config` 解析函数，不另写一套。
   CLI 与 `advance_recorded_day` 共用一个"已加载事件 + 配置 + 目标队列 → 推进"的函数（today.md §4.1 第一条）。
4. **同一份数据只读一次**（`AGENTS.md` 已知缺陷 2）：`record_day` 在 `load_today` 之外又 `load_config` 一次——改为由 `load_today` 的同一次读取提供
   （可在内部返回装配上下文，公开映射不变）；网页 `/record` 处理里先 `load_today` 再交给 `record_day` 又读一遍——删掉网页侧那次，未知 `review_id` 由 `record_day` 报。
5. **不复制已有函数**：`ky/today/port.py::_missing_report_cycles` 与 `ky/pacing/cli.py::missing_report_cycles` 相同；只保留一份（放到 M28 非 CLI 模块或 `ky/today/compute.py`），两处都调用它。
6. **可读性（D7）**：`ky/web/server.py` 的 `_render`（约 115 行）与 `do_POST`（约 85 行、四层嵌套）拆成有名字的辅助函数（每段页面一个、每个 POST 路由一个）；
   全部新文件行宽 ≤ 100；不用分号把多条语句写在一行（`minutes = None; msg = ...`、`...; return`）。
7. **页面补齐**（web.md §3）：复盘段列出未出报告的周期并提示"请让 AI 出复盘报告"；缺题项选项文字为"对照后：对 / 半对 / 错"；
   科目显示配置里的中文名（`display_name`），不显示 ID；冻结段显示积压分钟与阈值（字段名已核对：`overdue_minutes`、`threshold_minutes`）。

## 必须补：测试（只写这些）

- **固定基线 `60a4fd2` 逐字节对照矩阵**（today.md §6）：在**同一份临时工作区**（复制最小注册表与数据，含队列、配置、可选课表 / 路线 / 复盘设置）里分别跑旧版（`git archive 60a4fd2`）与新版，
  比较退出码、stdout、stderr，以及写命令产生的**文件树字节**（`output_tree`）。至少覆盖：
  `preflight`（已登记工作区缺省 / 无注册表显式 `--config --items` / `--usage` / `--freeze-backlog-days` 与 `--urgent-*` / 冻结日；文本与 `--json`）；
  `review-questions`（文本与 `--json`，含一条改编题以出现停用提示行）；`pacing status`；
  `day-plan record`（显式 `--store --review-store`、注册表缺省、`--json`、空事件）。
  写成表驱动的一个测试（`subTest`），断言基线取到的确是旧版。推进失败分支是唯一允许的差异：单独一个测试，断言新版恰好多出恢复提示行、其余字节相同。
- **M33**：带复习项的成功记录（事件字节与 `day-plan record --done` 写出的相同、队列推进相同）；`freeze_written`（注入完成事件写失败且当天首次冻结）与 `event_written`（注入推进失败）
  两种部分失败的阶段码与留下的文件；部分失败后 `advance_recorded_day` 推进、再调用全为重放；`load_today` 的缺题 / 改编题 / 真题三种 `reviews`、课表命中与 null、路线阶段、未报告周期。
- **M16**：`--no-open` 命令路径（打印地址）、端口占用退出 2、请求体超限 400、跨午夜（注入"今天"）记录被拒、两种部分失败页面、表单 C 的 `advanced` / `already_advanced`。
  "今天"可通过 `make_server` 的可选参数注入（不改公开语义：缺省取系统日期）。

## 验收（只跑这些模块）

```
py -3.12 -m unittest tests.contract.test_today_port tests.contract.test_web_port tests.test_cli tests.contract.test_question_bank_port tests.contract.test_pacing_port tests.contract.test_availability_port tests.contract.test_freeze_port tests.contract.test_resume_port
```

## 报告

`F:\workspace\kaoyan-ai-system\review\rounds\round-276-web-rework-luna.md`：逐条写上面每一项怎么改的；对照矩阵的分支清单；验收 `Ran …` 行；仍未覆盖的地方。约 60 行。

其余规则同第 275 轮任务书（不提交、不跑全量、不联网、编码规则、不读个人数据）。
