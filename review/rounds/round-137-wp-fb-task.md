# 任务书：WP-F-b 学习状态进投影（M15 schema 3；WP-F 第二块）

你是固定窗口 `luna-c`，上两轮做了 F-a（`read_state_sources` 系列端口，已提交 `b97f3ac`）。本包在它之上把学习状态写进投影。
先读仓库根 `AGENTS.md`，再读：**`review/rounds/round-132-wp-f-rules-sol-out.md`（本包照它"建议的最终规则"1、3、5、6 与 F7、F8 做）**、`contracts/projection.md`（schema 2）、`contracts/state_sources.md`、
`contracts/freeze.md`、`ky/projection/__init__.py`、`ky/projection/__main__.py`、`tests/test_projection_service.py`、`docs/前端设计-范围与待定.md`（只读）。
F-a 的评审（sol 第 136 轮）可能与本包同时进行；若它要求改 F-a 接口，决策者会另派返工，本包按当前接口写。

在主仓库 `F:\workspace\kaoyan-ai-system` 工作。只改：新文件 `ky/projection/learning_state.py`、`ky/projection/__init__.py`（接入、schema 版本、meta）、新规格 `contracts/learning_state_projection.md`、
`contracts/projection.md`（版本号与指向新规格的一节）、`docs/模块地图.md` 的 M15 一行、`tests/test_projection_service.py` 里固定断言 schema 2 的地方、新测试文件。

## 要做的

1. **`projection_schema_version` = 3**。schema 2 的参考数据各表：相同参考输入下行集合与字段值不变（对照测试证明）；`projection_meta` 的版本值与新增键是唯一明示差异。
2. **学习状态表**（列取各端口公开数据类的字段，不另造语义；列名与类型写进新规格）：
   - `review_items`：`ReviewItem` 全部公开事实字段（含 `revision`、`title`、`granularity`、`schedule` 的各字段、`last_self_rating`），`review_id` 主键。
   - `day_plans`：每天**当前版本**一行（`DayPlan` 的全部标量字段含 `notes` ＋ 版本、`actor`、`input_hash`）；`day_plan_subject_minutes(day, subject_id, minutes)`。不设逐条任务表（`DayPlan` 没有这种数据）。
     计划里的 `backlog_minutes` 等是**写入当时的计划字段**，列说明写清，不能冒充按查询日计算的实时量。
   - `completion_events`（每个事件一行）、`completion_reviews`（主键 `(event_day, ordinal)`，保留 `completion_id`、`completed_on`、核对方式、结果、`question_ref`、`self_rating` 等全部字段）、
     `completion_vocab_words`（区分投放 `delivered` 与练习 `practiced`）。
   - `freeze_events(sequence PK, kind, day)`。
   - `route_phases`（当前路线的 `route_id`、`revision`、阶段序号、`label`、`start`、`end_exclusive`）＋ `route_phase_review_minutes(phase, subject_id, minutes)`；无路线 → 两表为空。
   - `availability_days(day, minutes)`。
   - `projection_meta`：`state_inputs`（JSON：键 = `<注册表键>/<相对该存储根的路径>`，例如 `state.plans/2026-09/day_plans_manifest.yaml`，值 = F-a 端口给的 SHA-256；键排序稳定）；
     `freeze_events_latched`（`0/1`，由 M27 `latch_active` 算，规格写明**这不是"当日是否冻结"**，后者取决于查询日与队列，归 F-c）。
3. **读取只经 F-a 端口**，不解析状态 YAML、不另读文件算哈希。队列与日计划存储是注册表必填键；`state.routes` 未登记 → 空；`state.availability` 登记即必须有文件（缺失 → 契约错误）。
   任何状态源无效 → `ContractError`，**旧投影逐字节不变**（沿用"先校验、临时库、原子替换"）。
4. **不存"今天"、不存建议**（F4 / F7）：不写入到期、积压、是否冻结等随查询日期变化的量；表名 / 列名 / 视图名不含建议、推荐、优先、下一步之类的词。
5. **确定性**（F8）：相同输入字节两次构建，全部表内容与 meta 相同；行排序、JSON 键顺序固定。
6. **规格**：`contracts/learning_state_projection.md`：每张表的列、来源端口与字段对应、缺失 / 无效策略、确定性、"不存今天"、`freeze_events_latched` 的含义、写入 → 重建 → 可读到的契约与**不承诺**的部分（运行中的 `serve --immutable` 不会自动看到新库；W2 前端刷新流程另定；显式 `--store` / `--items` 指到非注册表路径的写入不会被投影）。

## 不做的

- 不做按日期查询端口（F-c）；不做写命令后自动重建；不改 `serve`；不改 F-a 端口与任何写入路径；不做性能优化。

## 测试（只写这些）

新文件 `tests/contract/test_learning_state_projection.py`：
- **写入 → 重建 → 可读到**（F6）：在临时工作区分别走 `day-plan submit`、`day-plan record`（带 `--review-store`：完成事件与队列两侧都能读到）、`route submit`、`ky resume`（重排结果与恢复事件）、`review-queue migrate --apply` 的真实写入分支，每次后 `build_projection` 并查到这次写入的事实。
- 缺失策略：未登记 `state.routes` → 空；`state.availability` 登记但缺文件 → 失败；队列缺 manifest → 空表。
- 任一状态源无效 → 构建失败且旧投影文件字节不变。
- 确定性：两次构建逐表逐行相等、meta 相等；`state_inputs` 的每个值等于对应文件字节的 SHA-256，且不含旧版本计划文件。
- 参考数据对照：用 `git show b97f3ac:ky/projection/__init__.py`（断言取到的是 schema 2 版本）在同一参考输入上构建旧投影，比较 schema 2 的每张参考表逐行相等。
- 不写数据量字面量；科目从注册表取。
每条撤实现时变红（定点变异，报告写实际命令与结果）。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_learning_state_projection tests.test_projection_service tests.contract.test_state_sources_port
```
另在报告里记录一次**规模实测**：临时工作区合成约 800 天的日计划与完成事件（外加相应规模的队列），`build_projection` 的耗时（不写成测试）。

## 报告

`review/rounds/round-137-wp-fb-luna.md`：各表列清单与来源、`state_inputs` 键约定、变异验证、验收输出、规模实测结果、留给 F-c 的注意事项、建议。
写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。含中文的文件只用 `apply_patch` 编辑，写完查 `???`。
