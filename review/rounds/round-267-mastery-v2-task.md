# 第 267 轮任务书：掌握度第二版（A 真题门槛 + B 阶段目标）（gpt-6-luna，续 luna-c）

## 先读

`AGENTS.md`；规格 `contracts/mastery.md` 第二版（§2 真题门槛、§4 覆盖值、§5 阶段目标、§6 端口）、`contracts/route_plan.md` 末节"阶段目标"（schema v4）、`contracts/charts.md` §8 卡片 2；
sol 第 264 轮初检 `review/rounds/round-264-abc-spec-review-sol61.md`（必须改已改进规格，以规格为准）。
你上一轮写的 `ky/mastery/`、`ky/charts/`；路线读写 `ky/schedule/planning.py`（v2/v3 序列化规则）、`ky/pacing/port.py` 的 `apply_pacing` 与两个辅助函数。

## 工作区与并行

主仓库 master 当前提交之上。luna-a 在改 `ky/review/`、`ky/question_bank/`、`ky/__main__.py`、`ky/workspace.py`，并会**调用**你的 `item_level` 新签名；luna-b 在改数学一树与树语法。
**不碰**这些；不改 README、`docs/模块地图.md`（决策者统一改）。尽早落地 `item_level(item, past_question_passed)` 的新签名。

## 要做的

1. `ky/mastery/port.py`：§2 真题门槛（`item_level(item, past_question_passed: bool)`，`subject_mastery(..., past_question_passed: Collection[str])`）；§4 输出 `covered`；
   §5 `mastery_gap(subjects, today, route)` 按阶段目标插值，三种 `status`；sol 263 的引用清单口径按规格 §6 写清（`unknown_refs` / `tracker_refs` 是知识点 ID）。
2. 路线阶段 `targets`（schema v4，规格全部规则：取值、`consolidated <= covered`、跨阶段不减、v2/v3 拒绝、无 targets 时字节不变）；`apply_pacing` 切段时 `targets` 留在后半段。
3. `ky/charts/`：`ky chart ability` 装配处从完成事件推出"真题答对过的 review_id 集合"（`check == past_question` 且 `outcome == correct`），传给 M30；
   卡片 2 改为覆盖与巩固两行、`missing_route` / `no_targets` 的说明；`mastery_gap` 不再读复盘设置。
4. 模块头与 `contracts/mastery.md` 不一致处以规格为准；`prompts/` 里路线规划的 AI 指引（找 `grep -rln "route" prompts/`）补一句"每个阶段末写覆盖与巩固目标（`targets`）"。

## 不做的

不改 M10 / FSRS、M24、题库；不改既有路线文件与无 targets 时的任何输出；不读 `data/personal/`。

## 测试（只写这些）

- `tests/contract/test_mastery_port.py`：稳定度 ≥ 30 但没真题答对 → `progressing`；答对过 → `consolidated`；改编题（`exercise`）答对不算；`covered` 值；
  `mastery_gap`：两个目标点之间插值、早于起点 0、晚于最后目标点取末值、无路线 / 无 targets 两种 status、单科 null。
- `tests/contract/test_route_plan_port.py`：v4 往返；`consolidated > covered`、跨阶段下降、v2/v3 带 targets → 契约错误带路径；**无 targets 的既有 v2 / v3 文件读写字节不变**。
- `tests/contract/test_pacing_port.py`：切段时 `targets` 归后半段、原地替换保留。
- `tests/contract/test_charts_port.py`：卡片 2 两行与说明文字。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_mastery_port tests.contract.test_route_plan_port tests.contract.test_pacing_port tests.contract.test_charts_port
```

报告 `review/rounds/round-267-mastery-v2-luna.md`：改动、做法、测试输出原文、"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"、歧义与选择。
不提交；中文字符串写字面量；含中文的文件只用 `apply_patch`；写完 `rg -n '\?\?\?'` 检查；保持 LF 换行。
