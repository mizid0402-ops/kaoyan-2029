# WP-E2 规划者端口实施报告

## 改动文件

- `contracts/planner_port.md`：定义 M19 输入包字节规则、提案格式、staging 与过期校验、共享 apply 及来源查询。
- `ky/planning/port.py`、`ky/planning/__init__.py`：输入包生成与哈希、提案结构校验、staging 真实路径检查、输入包校验、过期拒绝；手填和 staging 都调用 `_apply()`，最终由 `DayPlanStore.write_day_plan()` 执行护栏与写入。
- `ky/__main__.py`：增加 `planner-input`；`day-plan submit` 改为 `--plan` / `--from-staging` 互斥参数。保留旧 `--plan` 缺文件时 exit 3。
- `ky/storage/day_plan_store.py`：manifest 写入升为 schema 2，增加 `actor` / `input_hash`；增加 `day_plan_provenance()`。
- `docs/模块地图.md`：更新 M11、M13、M19 行；缺口表改为剩余 E3 / E4。
- `tests/contract/test_planner_port.py`：覆盖输入确定性、规范化、来源 apply、拒绝条件、旧 CLI 与 manifest 兼容。

## 设计落点

1. **输入包**：完整序列化 `KaoyanConfig` 数据模型；复用 `build_snapshot()`、`load_review_queue()`、`select_daily_reviews()`，快照字段和 preflight summary 结构与现有 CLI 输出一致。`availability`、`route_plan` 均为 `null`；每日配置分钟数和词汇 `delivered` / `remaining` 单独提供。
2. **提案**：严格检查五个顶层字段、actor 正则、AI 必须有 SHA-256；plan 交给现有 `parse_day_plan()`。staging 路径按真实路径限制在 `staging/day_plans/`，输入包限制在真实 `staging/inputs/`。
3. **统一 apply**：staging 提案先检查输入包存在、规范化哈希及日期，再重算当天输入并拒绝过期输入；随后只通过 M13 写入。旧 `--plan` 包装为 `human` / `null` 并进入同一 `_apply()`。
4. **来源审计与兼容**：现有 manifest 是 schema 1，每个日期保存一个当前版本指针，计划正文另存为带版本号的文件。schema 2 在该指针增加来源字段。读 schema 1 或缺来源字段时返回 `actor: unknown`、`input_hash: null`，仅读不回写；下次成功写计划时写 schema 2 和新来源。`day_plan_provenance(day)` 返回当前 `(version, actor, input_hash)`，无计划时为 `None`。计划 YAML 字段未变。

## 规范化序列化

输入对象按 UTF-8 JSON 序列化：`ensure_ascii=False`、键排序、分隔符 `(',', ':')`、无缩进且无尾随换行；SHA-256 对这些字节计算。哈希不放入被哈希对象，避免递归；完整哈希由 CLI 打印，文件名使用前 12 位。规格和测试含手算例：`{"z":"é","a":[2]}` 规范化为 `{"a":[2],"z":"é"}`，其中 `é` 使用 UTF-8 字节。

## 验收

- 首次执行任务书四模块命令运行 91 项，其中一项测试错误地把 JSON 尾随空格当成内容篡改。规范化哈希本来就忽略空白，因此将负例改为修改真实字段。
- 修正后重跑受影响模块：`py -3.12 -m unittest tests.contract.test_planner_port`，13 项通过。首次四模块执行中 `tests.test_day_plan_store`、`tests.test_cli`、`tests.test_planning` 均通过；因契约模块当时的一项断言失败，整条命令结果为失败，没有在修正后重复跑其它三个模块。
- `git diff --check` 通过；本轮涉及的文件未发现连续问号替代文本。
- 全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。

工作区状态另有 `tests/contract/test_workspace.py` 的修改，不属于本任务实现，本轮未编辑或回滚。

## 建议

- 后续 E3 / E4 落地时扩展输入对象并同步更新 schema 或版本约定；本轮按决策保留 `route_plan` 与 `availability` 为 `null`。
- 当前 M13 manifest 对每个日期只保留当前版本指针；`day_plan_provenance(day)` 因此查询当前版本来源。若后续需要查询每个历史版本的来源，应另行设计追加式版本索引。
