# 第 224 轮任务书：④a 课表协同实现评审（gpt-6.1-sol，续 sol61-m18）

## 范围

工作区里未提交的 ④a 全部实现（T1 第 219 轮、T2 第 222 轮、T3 第 223 轮，另有决策者的小修）：

- M18 `ky/timetable/`（新）；M0 `ky/workspace.py`（两个新键 + 本地补充文件 §2.6）；M26 `ky/availability/port.py`；M8 `ky/schedule/budget.py`；
  M14 `ky/__main__.py`（preflight 解释行、`ky timetable` CLI、resume 装配）；M19 `ky/planner/port.py`；M27 `ky/freeze/resume.py`；
- 规格：`contracts/timetable.md`、`contracts/workspace.md`、`contracts/availability.md`、`contracts/planner_port.md`、`contracts/route_plan.md`；
- 测试：`tests/contract/test_timetable_port.py`（新）及 `test_workspace`、`test_availability_port`、`test_day_budget_port`、`test_planner_port`、
  `test_resume_port`、`test_day_plan_store_port`、`tests/test_cli.py` 的改动。

用 `git diff` 与 `git status` 看改动；三份实现报告是 `review/rounds/round-219-*-luna.md`、`round-222-*-luna.md`、`round-223-*-luna.md`。
`contracts/pacing_review.md`（M28）只是规格，**不在本轮范围**。

## 请判断

1. 实现是否符合 `contracts/timetable.md` 与 `contracts/workspace.md` §2.6（逐条对照；尤其 §4 计算、§6.2 三步优先顺序、§8 CLI 退出码与空状态）。
2. 未登记课表时的逐字节不变：`tests/contract/test_day_budget_port.py::test_unregistered_timetable_commands_match_e381792_bytes`
   是否真的固定 `e381792`、断言取到旧版、覆盖"无路线 / 路线已登记但未开始"两种工作区与 preflight 文本、`--json`、`planner-input --kind day`、`resume --dry-run`。
   它取代了原先固定 `20f4391` 的对照测试（旧测试用旧 `__main__.py` 配新 `ky` 包，签名变化后无法运行）；判断覆盖面是否有缺口。
3. 决策者已知、请你裁定是否必须改：`ky timetable show --week` 的网格按原始课表显示、不体现 `no_class` / `follow` 例外，而末行分钟数体现例外。
4. `AGENTS.md` 已知缺陷清单逐条（同一数据只读一次、只写一次文件、错误路径、参数先校验等）与 D7 可读性。
5. 个人数据：被跟踪的文件（代码、测试、规格、报告）里不得出现用户学校的名字或 ID、用户课表内容；本地补充文件与 `data/personal/` 已 gitignore。
   只报告发现的位置，**不要**在你的报告里复述任何个人数据内容。

## 可以运行

只跑与结论直接相关的单个模块或单条命令（`AGENTS.md` 评审者规则），例如
`py -3.12 -m unittest tests.contract.test_timetable_port` 或一条 `ky` 命令；不跑全量。

## 输出

`review/rounds/round-224-m18-implementation-review-sol61.md`：PASS / FAIL；必须改（附可复现输入与命令）/ 建议改 / 不改；安全登记单列。

## 禁止

不联网；只写这一份报告；不修改其他文件；不读仓库外文件；报告里不复述个人数据。
