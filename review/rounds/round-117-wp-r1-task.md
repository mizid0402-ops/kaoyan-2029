# 任务书：WP-R1 积压冻结判定与冻结效果（新模块 M27，决议 D11）

先读仓库根 `AGENTS.md`，再读：`docs/阶段2.5-接缝收口.md` 的 **D11**（本包依据，细则逐条照做）与 D10 补充、`contracts/route_plan.md`（生效规则）、`contracts/availability.md`、`contracts/planner_port.md`、
`ky/models.py`（`ReviewItem.is_due` / `overdue_days`、`KaoyanConfig.review_hard_cap_minutes`）、`ky/schedule/review_clip.py`（`ReviewPolicy`、`select_daily_reviews`、`preflight_to_mapping`）、`ky/schedule/budget.py`（`resolve_day_budget`、`allocate_new_content`）、
`ky/__main__.py` 的 preflight（`main`）与 `day-plan submit`、`ky/planner/port.py` 的 `_build_input_data`。

你在 worktree `F:\workspace\kaoyan-wt-r1`（分支 `stage25/r1`）里工作，只改这个目录。"基线提交"= 本 worktree 起点（`git rev-parse HEAD`，测试里写完整哈希字面量，照 `AGENTS.md` 12a 断言取到的是旧版）。

## 为什么做

D11：逾期积压多到一定程度，说明用户分心或有事；继续每天压任务适得其反。系统应**冻结**（不排复习、不排新内容），等用户手动 `ky resume` 后再按遗忘程度重排（重排是下一包 R2）。本包只做**判定**与**冻结期间的效果**。

## 决策者已定的设计（照做；有更好的写法先在报告里提，不要自行改设计）

### 1. 判定（新模块 M27，`ky/freeze/`，规格 `contracts/freeze.md`）

- `FreezePolicy`（值类型，`backlog_days: int = 3`，必须 ≥ 1）；`FreezeStatus`（`frozen: bool`、`overdue_minutes`、`overdue_count`、`threshold_minutes`、`backlog_days`）。
- `assess_freeze(day, config, items, policy) -> FreezeStatus`：逾期项 = `state == "queued"` 且 `due_date < day`；`overdue_minutes` = 它们 `estimated_minutes` 之和；`threshold_minutes = backlog_days × config.review_hard_cap_minutes()`（**用配置容量**，不看当日手填，D11 细则）；`frozen = overdue_minutes >= threshold_minutes`。纯函数。
- 冻结是**推导**出来的状态，不写任何文件（preflight 仍然只读）。

### 2. 冻结效果

- **preflight 与 M19 日输入包**（两处都调用 M27，不要各写一份）：先照常解析 `resolve_day_budget`（其错误照常报出），再 `assess_freeze`。
  冻结时：`select_daily_reviews(..., daily_minutes_override=0)`（不传阶段配额），`allocate_new_content(config, 0, floor_policy="drop_when_short")`——即当天复习与新内容都为 0，所有到期项进延期；
  payload 增加 `"freeze": {overdue_minutes, overdue_count, threshold_minutes, backlog_days, "resume": "ky resume"}`（**只在冻结时出现**）。未冻结时 preflight JSON / 文本、输入包字节与基线提交**完全一致**。
  文本在冻结时首行之后加醒目一行：`FROZEN             : 积压 <X> 分钟 ≥ <N> 天复习上限 <T> 分钟；今天不排任务，准备好后运行 ky resume`（措辞可调，写进规格）。
- **`ky preflight --freeze-backlog-days N`**：新参数，缺省 3，校验 ≥ 1（非法为用法错误，退出 3，照 `--urgent-overdue-days` 的写法）。M19 输入包用缺省 `FreezePolicy()`（与它用缺省 `ReviewPolicy()` 一致）。
- **`day-plan submit`（两种形式）**：能找到注册表（`_discovered_workspace`）且登记了 `state.review_queue` 时，按提交计划的 `day` 与缺省 `FreezePolicy()` 判定；冻结时报契约错误（退出 2，不写），消息写明"已冻结，请先运行 ky resume"。找不到注册表时不判定（规格写明）。
- **`day-plan record` 不受影响**：如实记录已完成的内容永远允许（D11）。

### 3. 规格与地图

`contracts/freeze.md`（判定公式、推导不落盘、效果、各入口行为、R2 将提供 `ky resume`）；`contracts/planner_port.md` 与 `contracts/route_plan.md` 各补一句冻结优先于阶段配额；`docs/模块地图.md` 新增 M27 行。

## 不做的

- 不做 `ky resume`（R2）；不改裁剪算法、紧急规则、`check_invariants`；不改考试配置结构。

## 测试（只写这些，新 `tests/contract/test_freeze_port.py`）

每条都要在撤回对应实现时变红（报告里写怎么验证的）：
1. `assess_freeze`：刚好低于 / 等于阈值；`scheduled`、未到期、当天到期（`due_date == day`）不计入；`backlog_days < 1` 被拒。
2. 未冻结：preflight JSON 与文本、输入包字节与基线提交一致（固定哈希、断言旧版）。
3. 冻结：preflight `--json` 有 `freeze` 键、`selected` 为空、新内容为 0、退出 0；文本含冻结行；输入包 `review_clip` 等于 preflight `--json` 去 `config`。
4. `--freeze-backlog-days 0` 退出 3；调大该值可让同一队列不冻结。
5. `day-plan submit --plan` 冻结时退出 2 且不写；`day-plan record` 冻结时照常成功。
不写数据量字面量（阈值由配置与策略推导）。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_freeze_port tests.contract.test_day_budget_port tests.contract.test_planner_port tests.test_cli tests.test_review_scheduler
```

worktree 没有 `data/raw_materials/`；依赖它的用例报缺目录属已知现象（G1 合并后会变为跳过）。

## 报告

`review/rounds/round-117-wp-r1-luna.md`（写在 worktree 里）：改了哪些文件、每条设计的落点、逐字节对照做法、验收输出、给 R2 的建议。
写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。含中文的文件只用 `apply_patch` 编辑，写完查 `???`。
