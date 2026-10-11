# 第 278 轮：M33 / M16 第二次返工

## 改动

- `ky/__main__.py`：恢复提示基于本轮解析的 `store_path`、队列对象、`config_path` 和 `workspace.source`。
  注册表通过环境或向上发现时也固定传入实际注册表路径；命令不会重新选来源。
- `tests/contract/test_today_port.py`：新增注册表默认存储路径、队列推进失败用例，断言提示包含三条实际路径及注册表路径。
- `ky/today/record.py`：`latch_freeze_if_needed` 成功发布冻结记录后直接返回 `latched=True`，移除发布后的冻结文件重读。
  完成写入与队列推进均包装 `OSError`；阶段按已持久化的最后一步确定。
- `tests/contract/test_today_port.py`：覆盖冻结已写后完成事件 `OSError`（`freeze_written`）、无冻结时完成写入失败
  （`rejected`）、完成事件已写后队列 `OSError`（`event_written`），并检查事件保留。
- `ky/today/port.py`：把今日装配拆为 `_read_today_sources`、`_calculate_today_content`、
  `_assemble_today_view`、课表 / 路线 / 复盘 / 记录映射构造函数。配置、队列、计划、路线、可用时间、课表、复盘与题库
  均由装配阶段读取一次；公开视图字段和值保持原状。
- `ky/web/server.py`：真题按 `question_level` / `check` 单独渲染引用与年份题号元数据；改编题渲染题面、选项与折叠答案。
  路线配额按 `display_name` 显示；周期文字采用周期终日及次日复盘，无周期时省略日期句；0 分钟保留为“0 分钟”。
- `tests/contract/test_web_port.py`：新增真题元数据、科目中文名、周期日期和零分钟渲染断言。
- `tests/contract/test_today_port.py`：两个旧版基线身份断言改用旧实现独有的
  `_day_plan_record_freeze` / `_day_plan_record_advance_queue`，并断言当前源码不含这些特征。
- 固定基线矩阵新增带复习项的 `day-plan record --review-store` 成功推进分支；`compare_runs` 对比退出码、stdout、stderr
  与完整输出树字节。

## 固定基线分支

- `preflight`：登记缺省文本 / JSON、无注册表显式 `--config --items`、`--usage`、紧急与冻结策略、已锁存冻结日。
- `review-questions`：文本与 JSON，并验证改编题停用提示。
- `pacing status`。
- `day-plan record`：显式 store 与 review-store、登记缺省文本 / JSON、空事件、带复习项并推进队列。
- 单独的推进失败对照只允许新增恢复命令一行，其余输出字节与输出文件树一致。

## 验收

- 任务书验收命令：`Ran 112 tests in 192.895s`，`OK`。
- 第一次全验收尝试临时设置了全局 `KY_WORKSPACE`，改变了 `test_cli` 的无注册表测试语义（2 failures、1 error）；撤销该变量后重跑通过。
- 完整验收后将冻结分支注入改为 `OSError`，并显式返回已读取上下文映射；受影响模块复跑：
  `py -3.12 -m unittest tests.contract.test_today_port`，`Ran 12 tests in 36.024s`，`OK`。
- 今日与网页端口模块复验：`Ran 21 tests in 36.501s`，`OK`。
- 全量未跑（按 `AGENTS.md`，由决策者提交前统一跑）。未读写真实个人学习目录，未联网，未提交。
  本轮未触碰 `docs/安全风险登记.md`；该文件在本轮开始前已有工作区改动，未回退。

## 未覆盖 / 说明

- 无周期时采用规格允许的省略方案，不显示“复盘尚未开始”句。
- 固定基线使用临时合成工作区；本机忽略目录未参与测试。
- 安全登记中的认证 / CSRF 等事项不属于本轮范围。
