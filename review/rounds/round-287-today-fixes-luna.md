# 第 287 轮：M33 今日视图修复

结论：C-M1、C-M2、B-M3、C-M4 已逐条处理；未提交。

## C-M1：来源快照一次读取

- `ky/today/port.py:96`、`:133`：装配先读队列、计划、配置等；预检选出项目后再加载对应树、祖先、索引与权重，避免读未选科目来源。
- `ky/storage/review_shards.py:310`、`ky/storage/day_plan_store.py:464`：快照带已计算 ID、manifest 版本；M13 预检与推进用同一队列快照。
- `ky/review/check_questions.py:222`、`:229`；`ky/today/questions.py:25`：新增 M24 已加载计算入口，M31 复用树、索引和权重，不在选题时从路径重读。
- `ky/pacing/port.py:238`、`ky/today/port.py:198`：一次加载并校验复盘报告，映射层只消费结果。
- `ky/today/port.py:224`、`ky/today/record.py:46`、`:81`、`:148`：记录沿用视图加载的队列与冻结上下文；补推进用同次读取的事件和队列快照。
- 输出映射未改；固定基线矩阵通过。相关端口说明更新于 `contracts/check_questions.md`、`contracts/day_plan_store.md`、`contracts/state_sources.md`、`contracts/pacing_review.md`。

探针（Path.open 读模式；合成两条同科 progressing 项、当日事件）：

- 修前（sol 283 M1 复现）：索引 2、权重 2、manifest 2、每个 shard 2；树由计算阶段现读。
- 修后：config 1；索引 1；权重 1；计划完成事件 1；manifest 1；shard `math1--b10--0000--v2.yaml` 1、`math1--b15--0000--v2.yaml` 1；树 `math1.yaml` 1。

## C-M2：冻结发布后清理错误

- `ky/storage/day_plan_store.py:208`：`os.link` 发布后，临时文件清理的 `OSError` 不再覆盖已发布结果；发布前清理错误仍会抛出。未按错误文字判断阶段。
- 探针：修前 `stage=rejected, freeze_events=1, completion_event=false`；注入 freeze 临时文件 `unlink` 的 `PermissionError` 后，修后记录成功，冻结事件 1 条、完成事件存在（到达 `event_written`）。

## B-M3：全停用提示

- `ky/today/questions.py:122`：`progressing` 且改编题全停用时也输出“缺改编题：先生成”、停用原因和 `generation_command`；`learned` 原行为保留。未改 M31 选题算法。

## C-M4：模块头

- `ky/today/port.py:1`：列出 M33、`contracts/today.md` 和四个公开接口；仅文档变化。

## 验收

- `py -3.12 -m unittest tests.contract.test_today_port`：`Ran 13 tests in 36.395s`，`OK`
- `py -3.12 -m unittest tests.contract.test_freeze_port tests.contract.test_resume_port`：`Ran 22 tests in 19.191s`，`OK`
- `py -3.12 -m unittest tests.test_cli`：`Ran 63 tests in 74.362s`，`OK`
- 全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。
- 未跑的疑似受影响模块：M13 `tests.contract.test_day_plan_store_port` / `tests.test_review_queue_advance`；M24 `tests.contract.test_check_questions_port`；M28 `tests.contract.test_pacing_port`。按任务书仅跑指定验收；CLI 与冻结/恢复模块已覆盖部分调用路径。
- 未做 / 限制：发布后清理错误被视为可恢复清理；若 unlink 持续失败，临时 `.tmp` 可能残留，但已发布事件与记录阶段不受影响。未跑全量、未提交。
