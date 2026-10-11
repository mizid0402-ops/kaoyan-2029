# 任务书：F-b 验收补强 ＋ WP-F-c 按日期查询端口（窗口 `luna-c`）

你做过 F-a、F-b（已提交 `b867ae7`）。本轮两部分，**分两节写报告**，决策者会分两次提交。
先读仓库根 `AGENTS.md`，再读 **`review/rounds/round-142-review-sol-out.md`（全文：第一部分是 F-b 的 B1，第二部分末尾"建议给实现者的最终规则"是 F-c 的规则，照它做）**、
`contracts/learning_state_projection.md`、`contracts/state_snapshot.md`、`contracts/freeze.md`、`ky/schedule/state_snapshot.py`、`ky/freeze/port.py`、`ky/projection/__main__.py`。
**吸取已有教训**：测试辅助函数给嵌套路径赋值时列表下标不能用 `key not in node`；做"调换 / 改值看测试是否变红"的变异时设 `PYTHONDONTWRITEBYTECODE=1`。

在主仓库 `F:\workspace\kaoyan-ai-system` 工作。另一个窗口（`luna-a`）正在改 `ky/__main__.py` 和新增 `tests/test_cli_split_baseline.py`，**不要碰这两个文件**。

## 第一部分：F-b 的 B1（只改测试）

`tests/contract/test_learning_state_projection.py` 的 `test_real_cli_writes_are_visible_after_rebuild`：
- `day-plan record --review-store` 后，按 `review_id` 从**投影** `review_items` 读状态、到期日、上次复习日、`schedule_*` 等被推进的字段，与写后的队列对象逐一核对，并断言与写前不同；
- `ky resume` 后，同样从**投影**核对重排后的到期日等字段，以及恢复事件。
撤修改验证：把 `learning_state.py` 里写 `due_date` 的值改成常量 → 该测试变红（报告写实际命令与结果）。

## 第二部分：F-c（照 sol 142 最终规则 1–4）

1. **M12**：公开一个只依赖 `ReviewItem` 序列与日期的纯计数函数（各科 `in_review_queue`、`due_today_count`、`due_today_minutes`、`backlog_minutes`，口径不变），`build_snapshot` 改为调用它，保留科目顺序与零值行；`contracts/state_snapshot.md` 补这个接口。
2. **M15** 新文件 `ky/projection/status.py`：`status_as_of(projection_path, day, config, policy=FreezePolicy()) -> StatusAsOf` 与唯一 JSON 形状 `status_to_mapping()`。
   - SQLite **只读**打开，先核对 `projection_schema_version == 3`；缺文件 / 缺表 / 版本不符 → 可操作的契约错误（提示重建），不创建空库。
   - `review_items` 行**逐列组装**成 `validate_review_item` 接受的输入映射（嵌套 `schedule`、`self_rating` 等），经唯一校验器还原；再用 `validate_items_against_config` 校验与本次配置的科目关系。
   - 计数用第 1 条的 M12 函数；冻结用 M27 `latch_active`（由 `freeze_events` 行按序号重建 `FreezeEvent`）与 `assess_freeze`。JSON 里冻结对象**显式含 `frozen` 布尔**，非冻结时不给 `resume` 提示。
   - 另返回该日当前日计划（含科目分钟）、该日完成事件是否存在、该日手填分钟、该日所在路线阶段（`start <= D < end_exclusive`，含各科复习分钟）；缺项用约定的 `null` / `false`。不含任何建议 / 推荐 / 优先语义。
   - 规格写明：`as_of` = "按日期 D 评估**最近一次成功重建**的投影事实"，**不是历史回放**，不代表"已反映刚才的写入"；冻结阈值按**本次传入的配置**计算。
3. **CLI**：`py -3.12 -m ky.projection status --date D [--config PATH] [--workspace W] [--json]`。配置优先 `--config`，否则注册表 `settings.exam_config`，都没有 → 带路径的契约错误并说明怎么设置。
   **原重建命令 `py -3.12 -m ky.projection [--workspace] [--out] [--json]` 的调用与输出保持不变**（固定 `b867ae7` 对照）。
4. **规格**：新写 `contracts/projection_status.md`；`docs/模块地图.md` 的 M12、M15 行补接口（只改这两行）。

## 不做的

不写状态、不自动重建、不改 `serve`；不改 F-a / F-b 的实现（第一部分只改测试）。

## 测试（只写这些）

- 第一部分的两处断言补强。
- `tests/contract/test_state_snapshot_counts_baseline.py`：`git show b867ae7:ky/schedule/state_snapshot.py` 旧版（断言取到的是旧版）与新版在同一组输入上比较快照 JSON 逐字节相同；覆盖零项科目、`scheduled`、昨日 / 今日 / 明日到期边界。
- `tests/contract/test_projection_status.py`：同一份队列、配置、日期下，M12 计数与 `status_as_of` 计数相等、M27 冻结结果相等；锁存按事件序列；`as_of` 取过去日期时仍用当前事件锁存（写明含义的断言）；只读打开（构建前后投影字节不变）；缺文件 / schema 2 / 配置外科目 → 契约错误；CLI 缺配置报错、`--config` 生效；旧重建命令与 `b867ae7` 输出逐字节相同。
每条撤实现时变红（定点变异，`PYTHONDONTWRITEBYTECODE=1`，报告写实际结果）。不写死科目或数据量。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_learning_state_projection tests.contract.test_projection_status tests.contract.test_state_snapshot_counts_baseline tests.test_projection_service tests.contract.test_state_snapshot_port
```


## 报告

`review/rounds/round-145-wp-fc-luna.md`：**分两节**（F-b 补强 / F-c），各写改动落点、变异验证实际结果、验收输出；F-c 另写接口签名、JSON 形状、CLI 行为、建议。
写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。含中文的文件只用 `apply_patch` 编辑，写完查 `???`。
