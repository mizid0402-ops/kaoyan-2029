# WP-R1 实施报告：积压冻结判定与冻结效果

基线提交：`2bbeaae55e82725baed492143c494ffe22d1d6ec`（测试内固定该哈希；旧版源码从该提交读取，并断言旧版没有冻结入口）。本轮未提交。

## 改动文件与设计落点

- `ky/freeze/__init__.py`、`ky/freeze/port.py`：新增 M27。`FreezePolicy` 默认 3 天并拒绝小于 1 的值；`assess_freeze` 只计 `queued` 且 `due_date < day` 的项，按配置硬上限计算阈值，返回不可变状态，不落盘。
- `contracts/freeze.md`：记录公式、入口行为、未初始化队列语义及 R2 的 `ky resume` 边界。
- `ky/__main__.py`：preflight 预算解析后判定冻结；冻结时传 `daily_minutes_override=0`、不传阶段配额、以 `drop_when_short` 分配 0 分钟；冻结 JSON 增加 `freeze`，文本在首行后显示提示。新增 `--freeze-backlog-days`，小于 1 返回用法错误 3。`day-plan submit` 的两种格式读取计划日后判定冻结并在写入前拒绝；record 路径未改变。
- `ky/planner/port.py`：M19 输入构建使用同一个 M27 判定和同样的冻结裁剪；只在冻结 payload 中添加 `freeze`。预算解析仍先于判定。
- `contracts/planner_port.md`、`contracts/route_plan.md`：补充冻结优先于阶段配额的规则。
- `docs/模块地图.md`：登记 M27。
- `tests/contract/test_freeze_port.py`：覆盖策略边界、旧版字节对照、冻结效果、CLI 阈值参数与 submit/record 边界。

实现细节：注册表存在且队列路径已登记、但队列路径尚未创建时，submit 按空队列判定；队列路径已存在时正常读取并校验。首轮指定验收发现仓库既有 CLI 测试会在未初始化队列的工作区提交计划，因此采用空队列解释以保留既有行为；该行为已写入契约。

## 逐字节对照

测试固定从 `2bbeaae55e82725baed492143c494ffe22d1d6ec` 读取 `ky/__main__.py` 和 `ky/planner/port.py`，并分别断言旧 CLI 无 `--freeze-backlog-days`、旧 M19 无 `assess_freeze`。同一临时配置、队列、工作区和日期分别运行旧/新 preflight JSON 与文本，比较 stdout/stderr 原始 UTF-8 字节；M19 用旧版 `_build_input_data` 与新版构建结果按规范 JSON 字节比较。未冻结 JSON 也断言不含 `freeze`。

## 测试与验收

指定命令首轮运行：

```text
py -3.12 -m unittest tests.contract.test_freeze_port tests.contract.test_day_budget_port tests.contract.test_planner_port tests.test_cli tests.test_review_scheduler
Ran 122 tests in 25.861s
FAILED (errors=1)
```

唯一错误是新测试把 `subject_allocation` 的字段名写成 `minutes`；实现输出字段为 `new_content_minutes`。修正断言后按 `AGENTS.md` 只重跑受影响模块：

```text
py -3.12 -m unittest tests.contract.test_freeze_port
Ran 5 tests in 2.510s
OK
```

指定命令其余模块在首轮全部通过；首轮唯一错误已在受影响模块复验通过后消除。按 `AGENTS.md`，未重跑未受影响模块。

变红对应关系：

1. 公式 / 边界测试在漏计阈值等号、把当天到期或 scheduled 项计入、或不校验策略时失败。
2. 未冻结旧版对照在无条件新增 payload 字段、改变输出行或修改输入包字段时失败。它是非冻结兼容性护栏；单独撤回冻结实现不会使这条负向对照失败，这是该测试目标本身的逻辑限制。
3. 冻结效果测试在冻结判定移除、未将预算置零、未加 payload 或 M19 与 preflight 分叉时失败。
4. 参数测试在缺少参数校验或忽略自定义天数时失败。
5. submit/record 测试在 submit 未拦截、拦截后仍写入、任一提交入口漏拦截，或 record 被冻结拦截时失败。

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。

## 给 R2 的建议

- `ky resume` 应继续把状态视为队列派生结果；恢复后的队列变化应自然令 M27 不再冻结，不另写冻结标记。
- 按 D11 分别实现“可能遗忘 / 逾期不久”两层；验证可能遗忘只退回核对失败起点、不增加 lapse、不改 ease，并确保两层均不拉长间隔。
- 恢复操作应先解析当天预算与路线配额，再构造并校验完整新队列，最后原子提交并保留审计记录；失败时队列不应部分更新。
