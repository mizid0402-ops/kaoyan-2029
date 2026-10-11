# 任务书：WP-E3b 路线提案经 staging、路线输入包、日输入包 `route_plan` 字段（M19，审查项 B4 / A5）

先读仓库根 `AGENTS.md`，再读：`contracts/planner_port.md`（全文，尤其"信任边界"）、`contracts/route_plan.md`、`docs/模块地图.md` M11 / M13 / M19 行、
`ky/planner/port.py`、`ky/schedule/planning.py`（`route_plan_to_mapping`、`parse_route_plan`、`envelope_bounds`）、`ky/storage/route_store.py`、
`ky/__main__.py` 的 `planner-input`、`day-plan submit`、`route submit|show`，以及 `review/rounds/round-96-review-sol-out.md` 与 `round-98-review-sol-out.md` 的 H1 一行。

你在 worktree `F:\workspace\kaoyan-wt-e3b`（分支 `stage25/e3b`）里工作，只改这个目录。

## 为什么做

E3a 让路线可以由人提交、查看、按版本保存。E3b 把它接进规划者端口：AI 看着一份确定的"路线输入包"提出新版本路线，写进 `staging/`，
由用户或可信编排者执行 apply（与日计划同一套信任边界）；日输入包里的 `route_plan` 从 `null` 改为当天所在月份的包络，让日规划者看得见路线。
同时收掉 sol 96 / 98 留下的 H1 尾巴：`--plan` 接到 `staging/` 下的文件时直接拒绝。

## 决策者已定的设计（照做；有更好的写法先在报告里提，不要自行改设计）

### 1. 路线输入包（M19）

- `py -3.12 -m ky planner-input --kind route --date D [--config C] [--workspace W]`；`--kind` 缺省 `day`（现有行为与输出**逐字节不变**）。
- 写到 `write_target("staging")/inputs/route--<D>--<hash[:12]>.json`；写法与哈希规则同日输入包（`canonical_json_bytes`、`replace_bytes`、包内不含自身哈希）。
- 内容：`schema_version: 1`、`kind: route_planner_input`、`day`、`config`（完整 `asdict(config)`）、`state_snapshot`（同 `snapshot_to_mapping`）、
  `current_route`（`route_plan_to_mapping(store.current())`，无路线或 `state.routes` 未登记时为 `null`）。不放复习裁剪（那是日级的）。
- 提出者据 `current_route.revision` 得出下一版本号；这就是存储版本比较并交换的输入。

### 2. 路线提案与统一 apply（M19 + M14）

- 提案文件在 `write_target("staging")/routes/` 下，内容恰好：`schema_version: 1`（精确整数）、`kind: route_proposal`、`actor`（规则同日计划提案）、
  `input_hash`（小写 64 位，**必填**）、`route`（`parse_route_plan` 的映射）。
- **`route.stage1_input_hash` 必须等于 `input_hash`**：给这个一直没有生产者的字段一个生产者（B4），并在规格里写明其含义。
- apply 顺序：① 路径在 `staging/routes/` 下（按真实路径，照 `_validate_staging_path` 的写法）；② 结构；③ `staging/inputs/route--*--<hash[:12]>.json` 中恰有一个文件的规范化哈希等于 `input_hash`、`kind` 为 `route_planner_input`；
  ④ 用该包的 `day` 重新生成路线输入包，哈希不同 → 拒绝（沿用"输入已变化，请基于新输入包重新提案"）；⑤ `RoutePlanStore.write_route_plan(plan, actor=..., input_hash=...)`（版本比较并交换在存储里）。
- `ky route submit --from-staging FILE`，与 `--plan` 互斥；两种都经 M19 的**同一个** apply 函数（`--plan` 包装成 `actor: human`、`input_hash: null`）。E3a 在 CLI 里直接调存储的代码改为调 M19。
- M19 的日计划与路线两套逻辑共用的部分（staging 路径校验、提案头校验、包哈希校验）抽成有名字的辅助函数，不要复制两份。

### 3. 日输入包的 `route_plan` 字段

- 由 `null` 改为：存储有当前路线且 `day` 落在某个月包络 `[start, end_exclusive)` 内时，
  `{"route_id": ..., "revision": ..., "envelope": <该月在 route_plan_to_mapping 里的那一项>}`；否则 `null`（无路线、`state.routes` 未登记、或 `day` 在路线范围外）。
- 这会改变有路线时日输入包的字节与哈希（因此路线换版本会让基于旧版的日提案过期——这是想要的，写进规格）；无路线时字节必须与改动前一致。

### 4. `--plan` 拒绝 staging 路径（H1 尾巴）

- `day-plan submit --plan` 与 `route submit --plan`：能加载注册表时（显式 `--workspace`，或向上发现成功），若文件真实路径在 `write_target("staging")` 之下 → 契约错误，退出 2，什么都不写。
- 没给 `--workspace` 且发现不到注册表：不做此检查（没有注册表就没有 staging 的定义），规格写明。显式 `--workspace` 加载失败照现有规则报错。
- 检查放 M19（例如 `reject_staging_plan_path(path, workspace)`），CLI 只调用。

### 5. 规格

`contracts/planner_port.md` 增"路线输入包 / 路线提案"两节、日输入包 `route_plan` 字段、`--plan` 拒绝 staging 路径（替换"端口不检测"那句）；
`contracts/route_plan.md` 的 CLI 一节加 `--from-staging`，删去"E3b 将加入"一句，写明 `stage1_input_hash` 的含义。

## 不做的

- 不用路线包络约束日计划（护栏不变）；不做 `availability`（E4）。
- 不改 `RoutePlanStore` 的比较并交换与锁语义、不改 `parse_route_plan`（有问题写进报告）。
- 不调用任何模型。

## 测试（只写这些）

加在 `tests/contract/test_planner_port.py`（路线相关也可放 `tests/contract/test_route_plan_port.py`，二选一并在报告里说明）：
1. 路线输入包字节稳定；有 / 无当前路线时 `current_route` 分别为映射 / `null`。
2. 路线提案 → apply 成功，存储来源为提案的 `actor` / `input_hash`，`stage1_input_hash` 等于 `input_hash`。
3. 负例各一条（断言具体错误子串或路径）：不在 `staging/routes/`；缺 `input_hash`；`stage1_input_hash` 与 `input_hash` 不符；包不存在；包 `kind` 不对；过期；版本号不是当前 + 1。
4. `route submit --plan` 与 `--from-staging` 调用同一 apply 函数（mock 断言）。
5. 日输入包：无路线时字节与改动前相同（对照固定到提交哈希 `f0df351` 的 `ky/planner/port.py`，照 `AGENTS.md` 12a 断言取到的是旧版）；有路线时 `route_plan.envelope` 为当天所在月；`day` 在路线范围外为 `null`。
6. `--plan` 指向 `staging/` 下文件：两种 submit 都退出 2 且不写；无注册表时不检查（用显式 `--store` 的临时目录）。
不写数据量字面量。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_planner_port tests.contract.test_route_plan_port tests.test_cli tests.test_day_plan_store
```

worktree 没有 `data/raw_materials/`（gitignore）；`tests.contract.test_workspace` 等依赖它的用例报缺目录属已知现象，不必处理。
`docs/模块地图.md` M19 行（读哪些键、验收命令）与 §4 缺口表（只剩 E4 `availability`）更新。

## 报告

`review/rounds/round-100-wp-e3b-luna.md`（写在 worktree 里）：改了哪些文件、每条设计的落点、规格改动、无路线时字节对照的做法、验收输出、建议。
写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。含中文的文件只用 `apply_patch` 编辑，写完查 `???`。
