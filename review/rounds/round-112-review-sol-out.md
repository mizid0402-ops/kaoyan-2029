# Round 112 Codex 评审：WP-E5a 可变路线时间线

范围：`20f4391^..20f4391`，依据 D10、`review/rounds/round-111-wp-e5a-task.md` 与 `contracts/route_plan.md`。所有运行均在 `git archive 20f4391` 的系统临时归档（补原始资料及 `products` 空目录）；未跑全量测试。

| 项目 | 意见 | 证据与可复现输入 |
| --- | --- | --- |
| 1. 时间线闭合与 YAML 绕过 | **不改** | `ky/schedule/planning.py:73-125,153-203` 先把 YAML 映射解析为日期、精确整数和阶段，再校验首段起点、相邻段首尾相接、每段非空、末段等于考试日及索引连续。以 `make_route(boundaries=(START+30 天,))` 序列化成 YAML，分别把首段起点加一天、第二段起点加/减一天、末段终点加/减一天、第二段索引改 2，均得 `RoutePlanError`，路径分别为 `phases[0].start`、`phases[1].start`、`phases[1].end_exclusive`、`phases[1].index`。单段 `end_exclusive == start`、空 `phases` 也拒绝。未加引号的 YAML 日期可接受；datetime 字符串、非字符串映射键、空 `review_minutes`、布尔/浮点/null/负分钟探针均拒绝；未找到经 YAML 绕过闭合规则的输入。 |
| 2. 格式严格性与错误路径 | **不改** | `planning.py:153-242` 要求顶层和阶段键恰好匹配规格；版本 2 接受，版本 1（含真实旧键 `months`）先报 `route_plan.schema_version` 且消息含 D10，版本 3、布尔、浮点及缺失均在该路径拒绝。把旧文件交给 `py -3.12 -m ky route submit --plan <旧文件> --store <临时目录>`，退出 2，stderr 含 D10 而非 `unknown field`，存储目录未生成。解析层的类型错误含传入的源路径；闭合层沿用规格示例的 `phases[i].字段` 路径。`route_plan_to_mapping()` ↔ `parse_route_plan()` 的新格式往返测试通过。 |
| 3. 公开名、字段与 `end_exclusive` | **建议改 D1 文案** | `ky/schedule/planning.py:18-35,47-67,130-150` 已删除 `ROUTE_PLAN_MONTHS`、`MonthEnvelope`、`envelope_bounds`、`RoutePlan.months`，新属性 `end_exclusive == target_exam_date`；`ky/`、`tools/`、`tests/`、现行契约及模块地图中搜索旧公开名和旧阶段字段无命中。旧交接文档的 §0–§11 仍提 24 月，但文件开头明确标为历史过时内容，不是运行调用方。`docs/阶段2.5-接缝收口.md:205` 说阶段字段“只有”四项，而本轮任务书、规格与实现还要求 `index`；当前请求也明确要求索引连续。建议把 D10 该句澄清为“四个用户设置字段，另有序号 index”，避免后续按决议误删索引。此文案差异不阻断实现。 |
| 4. 存储与 `route show` | **不改** | `git diff 20f4391^ 20f4391 -- ky/storage/route_store.py` 无差异；版本比较并交换、manifest 错误、锁/发布/回滚的 `tests.contract.test_route_plan_port` 定向测试均通过。临时提交两段路线后，`ky route show --json` 的 `route_plan` 等于 `route_plan_to_mapping(plan)`；文本逐段显示 `index`、右开日期、标签和按科目 ID 排序的分钟（`ky/__main__.py:714-723`）。拒绝无效路线时现有存储字节不变的测试仍通过。 |
| 5. M19 输入包与提案 | **不改** | `ky/planner/port.py:78-93,103-119,365-380` 通过唯一映射接口读当前路线；日包在首段、第二段起点分别取得相应 `phase`，考试日当天为 `null`（`tests/contract/test_planner_port.py:230-249`）。无路线包继续通过固定 `f0df351` 旧源码的规范 JSON 字节对照（第 210–228 行）。路线输入包的 `current_route` 为新映射，路线提案的 `route` 由新解析器校验，来源与新鲜度测试通过。本包尚未让阶段分钟影响复习裁剪，按 D10 分包安排属于 E5b。 |
| 6. 测试撤实现 | **建议改 T1 测试韧性** | 在临时归档依次撤掉“末段终点等于考试日”“相邻阶段连续”“schema 1 D10 提示”，把日包右开比较改为右闭，并取消 `route show` 科目排序；对应单测分别变红（相邻阶段的间隙、重叠两例都红）。主要新行为已有有效回归。`tests/contract/test_route_plan_port.py:75-78` 用写死的 `'2026-09-15'` 文本替换来测 YAML 日期；当前确实替换了两处并解析为 `date`，但将来改测试起点时可能静默不再覆盖 YAML 日期。建议用 `START.isoformat()` 生成替换串，并断言替换确实发生。 |

**结论：PASS。** 未发现违反 E5a 格式、闭合、存储和输入包要求的阻断项。定向运行 `py -3.12 -m unittest tests.test_planning tests.contract.test_route_plan_port tests.contract.test_planner_port`：57 项通过；`git diff --check 20f4391^ 20f4391` 通过。未跑全量。
