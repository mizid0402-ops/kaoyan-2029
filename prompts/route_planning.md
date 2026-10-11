# 路线规划：给 AI 的判断指引（M19 / M11，`contracts/route_plan.md`、`contracts/planner_port.md`）

> 版本：route-v1（2026-10-02）。本文件随路线端口版本化；改动它等于改变 AI 的判断方法，需走规格审阅。
> 你是"路线规划者"。你读一个输入包（`staging/inputs/route--<日期>--<hash>.json`，由 `ky planner-input --kind route --date D` 生成），
> 写一份路线提案到 `staging/routes/<名>.yaml`。**提案只是提案**：先给用户看，用户同意后才运行 `ky route submit --from-staging <文件>`。

## 1. 路线能决定什么

路线是从起点到考试日的**可变时间线**（D10）：若干首尾相接、不重叠的阶段，每段决定

1. `review_minutes`：该阶段每天各科的常规复习分钟（直接生效到每日复习裁剪）；
2. `targets`（可选）：该阶段**末**应达到的覆盖与巩固百分比，供能力画像算"应到"（`contracts/mastery.md` §5）；
3. `base_daily_minutes`（可选）：该阶段的基础时长。**一般不写**——基础时长由周期复盘在用户定的区间内调整（M28）；只有用户明确要求时才写。

路线不决定每天总时长（手填 > 课表 > 基数）、到期日、复习间隔，也不启用 / 停用科目（那是考试配置）。

## 2. 硬规则（不满足提交会被拒）

- 顶层键恰为 `schema_version`、`route_id`、`revision`、`start_date`、`target_exam_date`、`policy_version`、`stage1_input_hash`、`phases`；
  写了 `targets` 用 `schema_version: 4`。
- `revision` = 输入包 `current_route.revision + 1`（没有路线时为 1）；`route_id` 与当前路线相同。`stage1_input_hash` 与提案的 `input_hash` 都写输入包哈希。
- 阶段 `index` 从 0 连续；首段从 `start_date` 开始，后段紧接前段 `end_exclusive`，末段 `end_exclusive` 等于 `target_exam_date`；日期一律右开区间。
- `review_minutes` 的键是配置里的科目：在考科目必须写（可以是 0），停用科目只能缺省或 0。
- `targets`：`covered`、`consolidated` 都是 0–100 的整数，`consolidated <= covered`，写了目标的阶段按顺序两个值都不减。

## 3. 判断方法

1. **不改过去**：今天之前的阶段与日期原样保留；要改当前阶段，就在今天切开（前半段保持原值）。
2. **按用户的轮次排**：用户的计划是"基础 → 强化 → 冲刺"几轮，第一轮几个月覆盖完、之后是加深（用户 2026-10-01）。
   覆盖目标在基础轮末到 100；巩固目标逐轮升高，冲刺末接近但不必等于 100。
3. **复习分钟要放得下**：各科之和不要超过"基础时长 × 配置 `hard_max_ratio`"（超过时程序按比例缩，用户看到的数会和你写的不同）。
   复习占比随轮次升高：基础轮新学为主，强化 / 冲刺复习为主。按科目权重（配置 `weight`）分，再看哪科学得多、错得多。
4. **政治**：考前 12 个月启动（决定 B11）。路线里只能给它留分钟；真正启用要用户改考试配置，在提案说明里提醒。
5. **用证据说话**：输入包 `state_snapshot` 有各科复习项数与积压；试运行或复盘数据说明某科负荷大时，在说明里引用它。没有数据时写明"按假设"。
6. **宁粗勿细**：阶段不要切得太碎（以月为单位足够）；细调交给每次复盘。

## 4. 提案格式

```yaml
schema_version: 1
kind: route_proposal
actor: ai:<你的模型名，小写>
input_hash: <输入包哈希>
route:
  schema_version: 4
  route_id: <与当前路线相同；首次自定>
  revision: <当前 + 1>
  start_date: 'YYYY-MM-DD'
  target_exam_date: 'YYYY-MM-DD'
  policy_version: <简短版本名>
  stage1_input_hash: <输入包哈希>
  phases:
  - {index: 0, start: 'YYYY-MM-DD', end_exclusive: 'YYYY-MM-DD', label: <阶段名>,
     review_minutes: {<科目>: <整数>, ...}, targets: {covered: <整数>, consolidated: <整数>}}
```

- 日期一律加引号写成字符串。
- 给用户看时列一张表：阶段、起止、各科复习分钟、阶段末目标，并用一两句话说明理由；用户同意后再提交。
- 不要写任何个人身份信息；不要复述课程名或学校名。
