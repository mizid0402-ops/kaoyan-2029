# 任务书：WP-E5a 路线改为可变时间线——格式、存储、展示（M11 / M13 / M14 / M19，决议 D10）

先读仓库根 `AGENTS.md`，再读：`docs/阶段2.5-接缝收口.md` 的 **D10**（全文，本包的依据）、`contracts/route_plan.md`、`contracts/planner_port.md`（路线输入包、路线提案、日输入包 `route_plan` 字段）、
`ky/schedule/planning.py`、`ky/storage/route_store.py`、`ky/planner/port.py`、`ky/__main__.py` 的 `route_main`、`tests/contract/test_route_plan_port.py`、`tests/contract/test_planner_port.py`、`tests/test_planning.py`。

你在主仓库 `F:\workspace\kaoyan-ai-system` 工作。

## 为什么做

用户要的"24 个月路线"其实是一份**可变时间线**：任意起止日期的阶段、首尾相接、覆盖到考试日，每段写各科每日复习分钟（D10）。
现有 `RoutePlan` 写死"恰好 24 个自然月、每月容量 / 通道 / 权重 / 单词目标"，形状不对。本包只换**形状**（格式、校验、存储、展示、输入包字段）；
让复习分钟真正影响每日裁剪是下一包 E5b，本包**不改** `ky/schedule/review_clip.py`、`ky/schedule/budget.py`。

## 决策者已定的设计（照做；有更好的写法先在报告里提，不要自行改设计）

### 1. 时间线格式（M11，`ky/schedule/planning.py`）

- `RoutePlan` 顶层：`route_id`、`revision`、`start_date`、`target_exam_date`、`policy_version`、`stage1_input_hash`、`phases`；序列化 `schema_version: 2`。
- 新值类型 `Phase`（替换 `MonthEnvelope`）：`index`、`start`、`end_exclusive`、`label`、`review_minutes`（映射：科目 ID → 非负整数分钟，非空）。
- `validate_route_plan` 改为时间线闭合规则：`phases` 非空；`index` 从 0 连续；`phases[0].start == start_date`；每段 `end_exclusive > start`；后一段 `start` 等于前一段 `end_exclusive`；
  最后一段 `end_exclusive == target_exam_date`；`label` 非空；`review_minutes` 键为非空字符串、值为非负整数（拒绝 bool / 浮点）。其余顶层规则（`route_id`、`revision >= 1`、`policy_version`、`stage1_input_hash`）不变。错误带精确路径（如 `phases[2].review_minutes.math1`）。
- 删除 `ROUTE_PLAN_MONTHS`、`MonthEnvelope`、`envelope_bounds`，以及只为它们存在的常量（D7：不留兼容别名）。`longitudinal.py` 的 `add_calendar_months` / `PlanHorizon` 另有用途，不动。
- `route_plan_to_mapping` / `parse_route_plan` 改为新形状：顶层键恰好 `schema_version`（精确整数 2）、`route_id`、`revision`、`start_date`、`target_exam_date`、`policy_version`、`stage1_input_hash`、`phases`；
  每段键恰好 `index`、`start`、`end_exclusive`、`label`、`review_minutes`。`schema_version: 1` 报契约错误，消息写明"旧 24 月格式已作废（D10），请按时间线格式重写"。其余严格性（日期、类型、未知 / 缺键、键类型）照现有实现。
- 科目 ID **不在格式层**对照配置（配置里在考科目会变）；对照在 E5b 使用时做。

### 2. 存储（M13）

`RoutePlanStore` 的比较并交换、锁、manifest、发布与回滚全部不变；只是经新的 `parse_route_plan` 读写。

### 3. 展示（M14）

`ky route show` 文本：头部同现在；每段一行：`index`、`start`–`end_exclusive`（写明右开）、`label`、各科复习分钟（按科目 ID 排序，形如 `math1=30 eng1=20`）。`--json` 形状不变（`route_plan` 用新映射）。

### 4. 规划者端口（M19）

- 日输入包 `route_plan`：当天落在某段 `[start, end_exclusive)` 时为 `{"route_id", "revision", "phase": <该段映射>}`，键名由 `envelope` 改为 `phase`；否则 `null`。无路线时字节仍须与改动前一致（现有 `f0df351` 对照测试保持通过）。
- 路线输入包 `current_route` 用新映射；路线提案 `route` 用新格式。其余校验不变。

### 5. 规格与文档

`contracts/route_plan.md` 按新格式重写格式与校验两节（存储、CLI、恢复规则等保留）；`contracts/planner_port.md` 的 `route_plan` 字段改为 `phase`；
`docs/模块地图.md` M11 行职责改为"可变时间线（阶段起止 + 各科复习分钟）"。模块头 docstring 引用 D10。

## 不做的

- 不改 `review_clip.py`、`budget.py`、preflight 的裁剪逻辑（E5b）。
- 不做区间模板、周期重复、从课表生成阶段（④）。
- 不迁移旧数据（仓库无已存路线）。

## 测试（只改 / 写这些）

- `tests/test_planning.py`：把针对 24 月包络的 `validate_route_plan` 用例**替换**为时间线闭合用例（首段起点、连续、不重叠、末段等于考试日、空阶段、`review_minutes` 类型各一条），其余与路线无关的用例不动。
- `tests/contract/test_route_plan_port.py` 与 `tests/contract/test_planner_port.py`：把构造 24 月路线的辅助函数改为构造时间线（阶段数、日期都由参数推导，**不写数据量字面量**），现有断言语义保留；新增：`schema_version: 1` 被拒且消息含"D10"；日输入包在段边界（某段 `end_exclusive` 当天）取到下一段、在考试日当天为 `null`。
- 撤实现变红：至少对"末段须等于考试日""相邻段首尾相接"两条各做一次撤回验证，写进报告。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.test_planning tests.contract.test_route_plan_port tests.contract.test_planner_port tests.test_cli
```

## 报告

`review/rounds/round-111-wp-e5a-luna.md`：改了哪些文件、每条设计的落点、删除了哪些公开名（逐个列出，按 `AGENTS.md` 13 条说明理由）、验收输出、给 E5b 的建议。
写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。含中文的文件只用 `apply_patch` 编辑，写完查 `???`。
