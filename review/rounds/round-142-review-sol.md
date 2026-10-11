# 评审 WP-F-b（`b867ae7`）＋ 审 WP-F-c 细则

遵守 `AGENTS.md`（不跑全量；严重度按威胁模型，安全类单列）。你在本窗口审过 WP-F 细则（132）与 F-a（136 / 141）。用 `git archive b867ae7`（补原始资料与 `products` 空目录；`git show` 基线用 `GIT_DIR`），只在你自己的临时目录运行。

## 一、评审 F-b：`b867ae7`

依据：你第 132 轮最终规则 1、3、5、6、F7、F8；任务书 `review/rounds/round-137-wp-fb-task.md`；实现者报告 `round-137-wp-fb-luna.md`；规格 `contracts/learning_state_projection.md`、`contracts/projection.md`。
提交信息写了决策者的改动：四个复制注册表的契约测试补复制 `state.availability` 文件（登记即必须存在，复制品原先不忠实，全量 9 项失败）。

请查：各表列与端口数据类字段是否一一对应、无另造语义；`state_inputs` 键约定与值来源（不重读文件）；缺失 / 无效策略与你 132 F5 一致；失败时旧投影字节不变；确定性；参考表与 schema 2 基线逐行相同；
"写入 → 重建 → 可读到"五个写命令的测试是否真走写入分支；`freeze_events_latched` 的说明是否足以防止被当成"当日冻结"；有没有日期相关量被写进表。

## 二、审 F-c 细则（只审规则，不审实现）

决策者拟定（依据你 132 最终规则第 4 条）：

C1. **M12 抽出公开纯函数**（例如 `queue_counts(items, day) -> 各科 {in_review_queue, due_today_count, due_today_minutes, backlog_minutes}`），`build_snapshot` 改为调用它，快照输出逐字节不变（固定哈希对照）。口径不变：`due_today` = `state == queued` 且 `due_date == day`；积压 = `queued` 且 `due_date < day`；`in_review_queue` = `queued` 或 `scheduled`。
C2. **M15 新增只读查询端口** `ky/projection/status.py`：`status_as_of(projection_path, day, config, policy=FreezePolicy()) -> StatusAsOf` 与唯一 JSON 形状 `status_to_mapping()`。只读投影（SQLite 只读打开），不读状态文件。
   由 `review_items` 行经 `ky.models.validate_review_item`（唯一校验器）重建 `ReviewItem`，再调 C1 的计数与 M27 `assess_freeze(day, config, items, policy, latched=latch_active(由 freeze_events 行重建的事件))`——口径只有一份定义。
   返回：`as_of`、各科计数、完整冻结状态（`freeze_to_mapping`）、该日的当前日计划（若有）、该日完成事件是否存在、该日手填分钟（若有）、该日所在路线阶段（若有）。不含任何建议 / 推荐 / 优先。
C3. **config 由调用方传入**（CLI 从注册表 `settings.exam_config` 读）；投影不存配置，投影与配置不一致（例如队列里有配置外科目）→ 契约错误。
C4. **CLI**：`py -3.12 -m ky.projection status --date D [--workspace W] [--json]`，读注册表的投影路径；投影文件不存在 → 契约错误并提示先重建。
C5. **投影版本**：`status_as_of` 只接受 `projection_schema_version == 3`，否则契约错误（提示重建）。
C6. 不做写入、不做自动重建、不改 `serve`（W2 仍待定）。

请重点查：C2 从投影行重建 `ReviewItem` 会不会与队列文件里的原对象有差（字段丢失、类型、日期文本）；冻结判定需要的输入是否都在投影里（`assess_freeze` 用到的配置字段、策略参数）；
M12 快照与 F-c 在同一天、同一数据上是否必然同数（需要什么对照测试）；C4 放在 `ky.projection` 的 CLI 下是否合适；还有什么日常使用会出错的边界（例如投影陈旧：写了新记录但没重建）。

## 产物

`review/rounds/round-142-review-sol-out.md`：第一部分 F-b 的"必须改 / 建议改 / 不改"附可复现输入、"安全登记"、PASS / FAIL；第二部分 F-c 细则逐条"同意 / 修改 / 反对"与你建议的最终规则。只写这一个文件。
