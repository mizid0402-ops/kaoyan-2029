# 按日期读取投影状态（M15）

## 接口

`status_as_of(projection_path, day, config, policy=FreezePolicy()) -> StatusAsOf`
只读打开 SQLite 投影，并按 `day` 评估最近一次成功重建所记录的事实。`day` 必须是
`datetime.date`。`config` 是本次查询所用的配置；其中科目顺序决定 `subjects` 行顺序，队列
中出现配置外科目时抛出 `ContractError`。`policy` 是 M27 的 `FreezePolicy`。

读取 `projection_meta.projection_schema_version` 后必须等于构建器的
`ky.projection.PROJECTION_SCHEMA_VERSION`（当前为 `4`，见 `projection.md`；端口不另写版本字面量），
更早版本一律要求重建，然后检查查询需要的表与列。
投影文件不存在、数据库无法读取、缺少表 / 列或 schema 版本不符均抛出带投影路径的
`ContractError`，错误说明要求重建投影。端口不得创建数据库或修改投影字节。调用方必须先
成功取得配置；CLI 从显式 `--config` 读取，否则使用工作区的 `settings.exam_config`。两者
都未提供时抛出路径为 `settings.exam_config` 的 `ContractError`，并说明如何登记或传参。

每条 `review_items` 记录按投影列组装为 `validate_review_item` 的输入映射（包括嵌套
`schedule` 与 `self_rating`），再以该验证器还原唯一的 `ReviewItem` 对象；最后调用
`validate_items_against_config` 校验其科目关系。M12 `count_review_items_by_subject(items, day)`
复用 M27 `overdue_review_items` 计算 `backlog_minutes`；M15 使用该 M12 计数结果，并按本次
配置顺序返回每科计数与零值行。

冻结事件按 `sequence` 升序还原为 M27 `FreezeEvent`。`latch_active(events)` 用于取得当前
事件序列的锁存状态，`assess_freeze(day, config, items, policy, latched=...)` 使用本次调用
的日期、配置阈值及策略计算结果。冻结状态中的 `frozen` 始终为布尔值；只有 `frozen` 为
真时 JSON 才包含 `resume` 字段。

其他事实按日期读取：当天当前日计划和各科分钟；当天是否有完成事件；当天手填可用分钟；
包含当天的路线阶段（`start <= day < end_exclusive`）及各科复习分钟。缺少日计划 / 路线阶段
时对应 JSON 值为 `null`；没有完成事件为 `false`；没有当天可用时间记录时分钟值为 `null`。

## `StatusAsOf` 与唯一 JSON 形状

`status_to_mapping(status: StatusAsOf) -> dict[str, object]` 是该接口唯一的 JSON 映射形状。
字段固定如下：

| 字段 | 形状 | 内容 |
|---|---|---|
| `as_of` | ISO 日期字符串 | 本次查询日期。表示按该日期评估**最近一次成功重建**的投影事实，不是历史回放，也不承诺投影已经反映刚才的写入。 |
| `subjects` | 对象数组 | 按配置顺序输出 `{subject_id, in_review_queue, due_today_count, due_today_minutes, backlog_minutes}`。口径与 M12 一致。 |
| `freeze` | 对象 | 始终含 `frozen` 布尔、`overdue_minutes`、`overdue_count`、`threshold_minutes`、`backlog_days`、`latched`；冻结时另含 `resume`。锁存来自当前投影事件序列，即使查询过去日期也不回放当时的事件状态。 |
| `day_plan` | 对象或 `null` | 当天当前日计划所有标量字段及 `subject_minutes` 映射；分钟字段是计划写入时的数值，不是查询日重新计算的实时积压。 |
| `completion_event_exists` | 布尔 | 当天是否有完成事件。 |
| `availability_minutes` | 整数或 `null` | 当天投影中的手填可用分钟。 |
| `route_phase` | 对象或 `null` | 当天所属阶段的路线 ID、revision、phase、label、边界日期及 `review_minutes` 映射。 |

对象字段的顺序由 `status_to_mapping` 固定；科目与分钟映射按稳定顺序输出。该接口不产生
建议、推荐、优先级或下一步任务。

## CLI

`py -3.12 -m ky.projection status --date D [--config PATH] [--workspace W] [--json]`
查询工作区注册的投影。显式 `--config` 优先于 `settings.exam_config`。`--json` 输出
`status_to_mapping` 的 JSON；不带 `--json` 输出简短的人类可读状态。原重建命令
`py -3.12 -m ky.projection [--workspace W] [--out PATH] [--json]` 的参数、行为和输出保持不变。

## 更新边界

命令只读取投影，不写状态，也不触发重建。`as_of` 不是状态源的历史版本选择器：它只把
查询日期应用到最近一次成功构建的事实。冻结阈值按本次传入的配置计算。正在运行的
`serve --immutable` 不会自动切换到新建的数据库；W2 前端刷新流程另行约定。使用显式
`--store` / `--items` 指向注册表之外路径完成的写入不会进入该工作区投影，除非另有被注册
的输入来源。
