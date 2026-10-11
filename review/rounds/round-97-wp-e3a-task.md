# 任务书：WP-E3a 路线包络落盘——文件格式、版本化存储与 `ky route` CLI（M11 / M13 / M14，审查项 B4）

先读仓库根 `AGENTS.md`，再读：`docs/阶段2.5-接缝收口.md` B4 与 WP-E 行、`docs/模块地图.md` M11 / M13 / M19 行、
`contracts/workspace.md`（`state.routes`、`write_target`）、`contracts/planner_port.md`（只读，了解 E2 的形状）、
`ky/schedule/planning.py`（`RoutePlan`、`MonthEnvelope`、`validate_route_plan`）、`ky/schedule/longitudinal.py`（`add_calendar_months`、`Channel`）、
`ky/storage/day_plan_store.py`（版本化 + manifest 的写法）、`ky/storage/atomic.py`（`replace_bytes`）、`ky/__main__.py` 的 `day-plan submit` 与 `_plans_store_path`。

你在 worktree `F:\workspace\kaoyan-wt-e3a`（分支 `stage25/e3a`）里工作，只改这个目录。

## 为什么做

`RoutePlan`（24 个月的阶段 / 容量包络）只存在于 `planning.py` 与测试里：没有文件格式、没有落盘、没有 CLI，
`stage1_input_hash` 也没有生产者（审查项 B4）。本包让路线成为一份可提交、可查看、有版本与来源的文件。
**E3 拆成两步**：本包 E3a 只做格式 + 存储 + 人工提交 / 查看；E3b（下一包）再做 AI 经 staging 提案、路线输入包、
日输入包的 `route_plan` 字段。所以本包**不改 `ky/planner/`**。

## 决策者已定的设计（照做；有更好的写法先在报告里提，不要自行改设计）

### 1. 文件格式（M11，公开接口放在 `ky/schedule/planning.py`）

- 新增 `route_plan_to_mapping(plan) -> dict` 与 `parse_route_plan(raw, path) -> RoutePlan`，二者互逆，是路线 YAML / JSON 形状的**唯一来源**（E3b 的输入包也将用它）。
- 顶层键**恰好**：`schema_version`（整数 1，拒绝布尔）、`route_id`、`revision`、`start_date`、`target_exam_date`、`policy_version`、`stage1_input_hash`、`months`。
  每个 `months[i]` 键**恰好**：`index`、`start`、`end_exclusive`、`phase_label`、`projected_capacity_minutes`、`subject_weights`、`channel_capacity_minutes`、`target_vocab_words`。
  未知键 / 缺键都拒绝，错误带精确路径（如 `months[3].phase_label`），异常类型用 `RoutePlanError`（已有 `path`）。
- 类型：整数字段拒绝 `bool` 与浮点；`subject_weights` 值接受 int / float（拒绝 bool）；日期字段接受 YAML 日期（`date`，但不是 `datetime`）或 `YYYY-MM-DD` 字符串，序列化一律写 ISO 字符串。
- `parse_route_plan` 解析后**调用 `validate_route_plan`**，闭合性违规原样抛出。不改 `validate_route_plan` 的现有语义。
- 读 YAML 用 `ky.models.load_yaml_text`（重复键 fail-closed）。

### 2. 版本化存储（M13，新文件 `ky/storage/route_store.py`，类 `RoutePlanStore`）

- 根目录 = `write_target("state.routes")`（或显式 `--store`）。布局：`routes_manifest.yaml` + `route--r<revision>.yaml`。
- `write_route_plan(plan, *, actor="unknown", input_hash=None) -> WriteReport`（`WriteReport` 可复用 `day_plan_store` 的公开类，或在规格里定义同形状的一个；不 import 私有名）：
  ① `validate_route_plan`；② **版本比较并交换**：库空时 `revision` 必须为 1；否则 `route_id` 必须等于当前 `route_id`，且 `revision` 必须恰为当前 + 1——
  这样两份基于同一旧版的提案只有先到的能落盘（为 E3b 的过期拒绝打底），违规报 `StorageError`，路径 `revision` / `route_id`，**不写任何文件**；
  ③ 目标版本文件已存在即拒绝（从不覆盖旧版本字节）；④ 写版本文件：临时文件 → 用 `parse_route_plan` 重读校验 → 替换到位；⑤ manifest 用 `replace_bytes` 写。
- manifest `schema_version: 1`，`route_id`，`revisions` 列表，每项 `revision`、`path`、`sha256`、`actor`、`input_hash`——**每个版本的来源都保留**（与日计划只记当前版本不同，在规格里写明）。
- 只读：`current() -> RoutePlan | None`、`load_revision(n) -> RoutePlan`、`provenance(n) -> (actor, input_hash)`；读时校验 sha256，不符报错。库目录不存在 = 空库。
- 本包的调用方只有人工提交：`actor` 记 `human`、`input_hash` 记 `null`。

### 3. CLI（M14）：`py -3.12 -m ky route submit|show`

- `route submit --plan FILE [--store DIR] [--workspace W]`：读 YAML → `parse_route_plan` → `RoutePlanStore.write_route_plan(actor="human", input_hash=None)`，打印写入路径、revision、sha256。
- `route show [--revision N] [--store DIR] [--workspace W] [--json]`：人读摘要（route_id、revision、起止、目标考试日、policy_version、来源；每月一行：index、start、phase_label、容量）；
  `--json` 输出 `{"route_plan": route_plan_to_mapping(...), "actor": ..., "input_hash": ...}`；库空时摘要打印"尚无路线"、`--json` 打印 `null`，退出 0。
- `--store` 缺省取注册表 `state.routes`（照 `_plans_store_path` 的写法）；未登记时报契约错误并提示 `--store` 或登记 `state.routes`。
- 退出码照 `day-plan`：0 成功，2 契约 / 护栏违规（什么都没写），3 用法错误。CLI 只做参数解析与输出。
- 在仓库注册表 `kaoyan.workspace.yaml` 的 `state` 下登记 `routes: data/routes`（`contracts/workspace.md` 已把它列为可选键）。

### 4. 规格

新 `contracts/route_plan.md`：文件格式（两层键、类型、日期规则）、存储布局与版本比较并交换、manifest、只读接口、CLI、错误路径、
"E3b 将加入 staging 提案与输入包字段"一句。模块头 docstring 按 `AGENTS.md` 写明模块编号与规格。

## 不做的

- 不改 `ky/planner/`、`contracts/planner_port.md`（E3b）；不做 `availability`（E4）。
- 不用路线包络去约束日计划（日计划护栏不变）。
- 不改 `validate_route_plan`、`RoutePlan` / `MonthEnvelope` 的字段。

## 测试（只写这些）

新 `tests/contract/test_route_plan_port.py`（临时目录；用 `envelope_bounds` 程序化生成一份合法 24 个月路线，**不写数据量字面量**）：
1. 格式：`parse_route_plan(route_plan_to_mapping(p)) == p`；未加引号的 YAML 日期可读；负例各一条（断言错误路径）：顶层未知键、月份缺键、`revision: true`、`datetime` 日期、`schema_version: "1"`、一条闭合性违规（如某月通道分钟和不等于容量）。
2. 存储：r1 → r2 成功且 r1 文件字节不变；跳号、旧号、换 `route_id` 各被拒且目录字节不变；manifest 两个版本各带来源；篡改版本文件后读取报 sha256 不符。
3. CLI：`submit` 成功后 `show --json` 取回同一映射且 `actor` 为 `human`；非法路线退出 2 且没写文件；未登记 `state.routes` 又没给 `--store` 退出 2 并提示。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_route_plan_port tests.test_planning tests.contract.test_workspace tests.test_cli
```

另：`docs/模块地图.md` M11 行（规格、实现、验收命令、可替换性）与 M13 行（加 `route_store.py`、`state.routes`）更新；§4 缺口表"路线包络尚未落盘"改为剩余缺口（E3b：staging 提案与输入包字段）。

## 报告

`review/rounds/round-97-wp-e3a-luna.md`（写在 worktree 里）：改了哪些文件、每条设计的落点、格式与存储规则、验收输出、建议。
写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。含中文的文件只用 `apply_patch` 编辑，写完查 `???`。
