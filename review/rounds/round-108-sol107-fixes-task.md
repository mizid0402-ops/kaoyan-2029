# 任务书：修 sol 第 107 轮对 WP-E4 的 F1 / C1 / C2 与建议 T1（M26 / M8 / M9 / M14 / M19）

先读仓库根 `AGENTS.md`，再读 `review/rounds/round-107-review-sol-out.md`（全文，复现输入都在里面）、`contracts/availability.md`、
`ky/availability/port.py`、`ky/schedule/budget.py`（`allocate_new_content`）、`ky/schedule/review_clip.py`（`select_daily_reviews`、`unschedulable` 判定）、
`ky/__main__.py` 的 preflight（`main`）、`ky/planner/port.py` 的 `_build_input_data`、`tests/contract/test_availability_port.py`。

你在主仓库 `F:\workspace\kaoyan-ai-system` 工作，只改上面列出的实现与规格，以及 `tests/contract/test_availability_port.py`。

## 决策者已定的规则（照做；有更好的写法先在报告里提）

1. **F1**：`load_availability` 的未知顶层键检查不得因键类型混合而崩溃：先拒绝非字符串键，或用不比较不同类型的确定性选取；报 `ContractError`，路径为该键。CLI 退出 2、无 traceback。

2. **C1 低容量日的新内容分配（M8）**：`allocate_new_content` 增加关键字参数（例如 `floor_policy: Literal["strict", "drop_when_short"] = "strict"`）。
   - `"strict"`（缺省）：行为与现在**完全相同**，保底之和超预算仍抛 `ValueError`（它的文档说明这是为了暴露配置写错，不能改）。
   - `"drop_when_short"`：仅当保底之和 > 预算时，放弃全部保底，整个预算按权重走现有 `_proportional_split`（最大余数法）；此时每项的 `floor_minutes` 记 0（表示实际适用的保底）。保底之和 ≤ 预算时与 strict 相同。
   - 只有当日分钟来源为 `availability` 时，preflight 与 M19 输入包才传 `"drop_when_short"`；来源为 `config` 时不传（输出逐字节不变）。在 `contracts/availability.md` 写明这条规则与理由（手填是用户对当天的事实陈述，不是配置错误）。

3. **C2 当天放不下 ≠ 需要拆分（M9）**：`select_daily_reviews` 判定 `unschedulable`（提示拆分）时，始终用**配置容量**下的硬上限（`config.hard_cap_minutes`）；
   项目成本 ≤ 配置硬上限但 > 当日（override 后）硬上限时，按现有延期规则进 `deferred`（`due_date` 不动、`defer_count` 语义照旧）。无 override 时两个上限相同，结果逐字节不变。
   在该函数 docstring 与 `contracts/availability.md` 里写明。

4. **T1（建议，采纳）**：preflight 文本输出的 `daily budget` 行在有手填值时显示手填分钟——加一条断言；无手填时的文本输出纳入已有的固定基线（`79623ee`）逐字节对照。
   另在 `contracts/availability.md` 写明：preflight 会向上发现注册表，发现到无效注册表时退出 2（原来退出 0），这是有意的 fail-closed 变化（sol 107 第 2 项）。

## 测试（只写这些，加在 `tests/contract/test_availability_port.py`）

每条都要在撤回对应修复时变红（报告里写怎么验证的）：
- F1：`extra: 1` 与整数键 `2: 3` 并存 → `ContractError` 带路径；preflight 退出 2、stderr 无 `Traceback`。
- C1：手填 0 与手填 30（低于保底之和）时，preflight `--json` 退出 0，各科分配之和等于当日新内容预算、`floor_minutes` 为 0；输入包同样可生成；`allocate_new_content` 缺省 strict 仍抛错。
- C2：手填 0 时，正常 fixture 的到期项进 `deferred` 而非 `unschedulable`；成本大于配置硬上限的项仍进 `unschedulable`。
- T1：见上。
不写数据量字面量。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_availability_port tests.test_review_scheduler tests.test_contracts tests.contract.test_planner_port tests.test_cli
```

## 报告

`review/rounds/round-108-sol107-fixes-luna.md`：每项落点、撤修复验证、验收输出、建议。
写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。含中文的文件只用 `apply_patch` 编辑，写完查 `???`。
