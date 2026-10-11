# 任务书：WP-E2 规划者端口——输入包、staging 提案与统一 apply（新模块 M19，审查项 A5；README 硬不变量②）

先读仓库根 `AGENTS.md`，再读：README "三条不可逾越的硬不变量"（尤其②"AI 产物零特权：先进 staging，经程序校验后 apply"）、
`docs/阶段2.5-接缝收口.md` A5 与 WP-E 行、`docs/模块地图.md` M11 / M13 / M19 行、`contracts/workspace.md`（`staging`、`state.*`、`write_target`）、
`contracts/state_snapshot.md`、`ky/schedule/longitudinal.py`（`DayPlan`、`check_invariants`）、`ky/storage/day_plan_store.py`、`ky/__main__.py` 的 `day-plan submit`。

## 为什么做

现在 `ky day-plan submit --plan <yaml>` 已是通用"校验后落盘"入口，但：没有 staging 约束（AI 产出可以直接交给 submit）、
不知道提案是谁出的（`actor`）、不知道它是看着哪份输入做的（`input_hash`），也就无法判断提案是否已经过期、无法审计。
目标：**"换一个 AI" = 换一个读输入包、往 staging 写提案的程序；系统这一侧不变。手填与 AI 产出走同一条 apply。**

## 决策者已定的设计（照做；有更好的写法先在报告里提，不要自行改设计）

### 1. 输入包（M19，新规格 `contracts/planner_port.md`）

- `py -3.12 -m ky planner-input --date D [--config C] [--workspace W]`：生成当天规划者可见的全部输入，写到 `write_target("staging") / "inputs" / f"{D}--{hash[:12]}.json"` 并打印路径与完整哈希。
- 内容（JSON 对象，`schema_version: 1`、`kind: planner_input`、`day`）：配置里与规划相关的部分（科目、权重、每日分钟等——照 `ky.models` 的配置对象，别手挑字段漏掉约束）；
  状态快照（与 `ky snapshot --json` 同一份数据）；当天复习裁剪结果（与 `ky preflight --json` 同一份）；词汇余量与已投放数；可用时间（本包先用配置的每日分钟，`availability` 留 E4，字段先写 `null` 并在规格里说明）；
  路线包络（`RoutePlan` 落盘在 E3，本包写 `null`）。
- **`input_hash`** = 该 JSON 的**规范化字节**（UTF-8、键排序、无多余空白、固定分隔符；在规格里写死规则）的 SHA-256。同一输入重复生成字节必须相同。

### 2. 提案（staging 文件）

- 位置：`staging/day_plans/<D>--<actor 规范名>--<任意后缀>.yaml`；内容：`schema_version: 1`、`kind: day_plan_proposal`、`actor`、`input_hash`、`plan`（现有日计划映射，字段与 `parse_day_plan` 相同）。
- `actor`：`human` 或 `ai:<模型名>`（`^ai:[a-z0-9][a-z0-9._-]*$`）。AI 提案必须带 `input_hash`；`human` 可以为 `null`。

### 3. 统一 apply（M19 实现 + M14 CLI）

- `ky day-plan submit --from-staging <提案文件>`：依次
  ① 提案文件必须在 `write_target("staging")/day_plans/` 之下（按真实路径判定）；② 校验提案结构；
  ③ 有 `input_hash` 时：`staging/inputs/` 下必须有该哈希的输入包、重算其规范化哈希一致、其 `day` 等于 `plan.day`；
  ④ **过期检查**：用当前数据重新生成该日输入包，哈希与提案的 `input_hash` 不同 → 拒绝（"输入已变化，请基于新输入包重新提案"），退出 2；
  ⑤ 走现有 `DayPlanStore.write_day_plan` 的全部护栏；⑥ 成功后把来源写进存储（见 4）。
- 现有 `--plan <yaml>` **保留**（`contracts/workspace.md` §3.2：不得删除既有 CLI 用法），实现为：把它包装成 `actor: human`、`input_hash: null` 的提案，调用**同一个** apply 函数（不经 staging 目录）。
- apply 逻辑放 M19 新模块（例如 `ky/planning/port.py`，模块头写明 M19 与规格），CLI 只做参数解析与输出。

### 4. 来源审计（M13）

- 日计划的版本记录（`day_plans_manifest.yaml` 的每个版本条目）增加 `actor` 与 `input_hash`（可为 null）。manifest 已有 `schema_version` 的话升一版；旧版本条目读取时视为 `actor: unknown`、`input_hash: null`，**不回写旧文件**。
  先读现有 manifest 格式与读写代码，在报告里写清你怎么改、兼容规则是什么。日计划文件本身（`parse_day_plan` 的字段）不改。
- 提供只读查询（例如 `DayPlanStore.day_plan_provenance(day) -> (version, actor, input_hash)`）。

## 不做的

- 不做 `RoutePlan` 落盘（E3）、`availability`（E4）；输入包里这两项为 `null`。
- 不调用任何模型；不写"AI 规划者"本身。
- 不改完成事件、复习推进、快照 / 预检的现有输出（输入包只**复用**它们的数据）。

## 测试（只写这些）

新 `tests/contract/test_planner_port.py`（临时工作区，照已有契约测试的写法）：
1. 输入包：同一输入两次生成字节相同；改动一条复习项后哈希变化；规范化规则按规格（可用一个手算的小例子）。
2. 提案 → apply 成功，存储里的来源为提案的 `actor` / `input_hash`。
3. 负例各一条（断言具体错误子串）：提案不在 `staging/day_plans/` 下；AI 提案缺 `input_hash`；输入包不存在；输入包被改过（哈希不符）；输入包 `day` 与计划不符；**输入已变化（过期）**；`actor` 格式非法；计划违反现有护栏（沿用 `check_invariants` 的一条）。
4. `--plan` 旧用法：仍然成功，来源记为 `human` / `null`，且走的是同一 apply 函数（例如 mock 断言被调用一次）。
5. M13：旧版 manifest 条目读取为 `unknown`；新写入条目带来源。
不写数据量字面量。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_planner_port tests.test_day_plan_store tests.test_cli tests.test_planning
```

另：`docs/模块地图.md` 的 M19 行改为指向新规格、实现、契约测试与验收命令，可替换性按实际填写；§4 缺口表"规划者 AI 无端口"一行改写为剩余缺口（E3 / E4）。

## 报告

`review/rounds/round-91-wp-e2-luna.md`：改了哪些文件、每条设计的落点、manifest 兼容规则、规范化序列化规则、验收输出、建议。
写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。含中文的文件写完查 `???`。
