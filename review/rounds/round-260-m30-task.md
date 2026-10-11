# 第 260 轮任务书：M30 掌握度 + M17 能力画像页（gpt-6-luna，续 luna-c）

## 先读

`AGENTS.md`；规格 `contracts/mastery.md`（新模块，本包唯一依据之一）与 `contracts/charts.md` §8（页面）；
sol 第 259 / 261 轮初检报告（`review/rounds/round-259-m30-spec-review-sol61.md`、`round-261-fsrs-spec-review-sol61.md`；其中的必须改已改进规格，以规格为准）。
现有实现参考：`ky/charts/`（你上一轮写的第二版，目录树、卡片、配色都复用）、`ky/knowledge/hierarchy.py` 的 `tree_parent`、`ky/models.py` 的 `ReviewItem` / `ReviewSchedule`。

## 工作区

主仓库 `F:\workspace\kaoyan-ai-system`，在第 262 轮（luna-a：FSRS 接管复习时间，`ReviewSchedule` 新增 `stability` / `difficulty` 与 `fsrs` 模式）之上继续——
那一轮的改动可能尚未提交，直接用工作区里的版本。**不要改** `ky/schedule/`、`ky/models.py`、`ky/projection/`。

## 要做的

0. `ky/workspace.py`：`_SUBJECT_FEATURES` 加 `weighted_mastery`；仓库 `kaoyan.workspace.yaml` 的 cs408 档案加 `features: [weighted_mastery]`（`contracts/workspace.md` 已改）；
   复制注册表的测试辅助若校验 features，按需同步（先 `grep -rn "features" tests/`）。
1. 新包 `ky/mastery/`（`port.py` + `__init__.py`）：规格 §2–§6 的常量与三个函数；模块头写 M30、`contracts/mastery.md`、对外接口。纯函数，不读文件。
   M17 已有的"可学节点 / 叶子 / Node 树"逻辑若需要共用，把它提到 M4 或 M30 的公开函数里，**不要**从 `ky.charts` import 私有名，也不要复制粘贴一份。
2. `ky/charts/`：`ability_chart_data`（data 层）、`render_ability`（render 层）、`ky chart ability`（cli）；四张卡片照规格 §8。
   读 `reference.topic_weights`（仅对开了 `weighted_mastery` 的科目）、`settings.pacing`、`state.routes`、`state.review_queue`、知识树；同一数据只读一次。
3. `docs/模块地图.md` 登记 **M30 掌握度**一行（规格、实现、读哪些键、可替换性、验收命令）；M17 行补上 `ky chart ability`；M0 行注明 `weighted_mastery`；README 模块速查与"四、上手"各补一行。

## 不做的

不读 `last_self_rating`；不改 M10 推进、M6 考频、M4 既有接口；不改既有命令输出；不读 `data/personal/`。

## 测试（只写这些）

- `tests/contract/test_mastery_port.py`：
  - `item_level`：阶梯项间隔 6/7/29/30 四个边界；fsrs 项按 `stability` 6.9/7/29.9/30 边界（与 `interval_days` 无关）；`suspended` / `retired` → `None`；`last_self_rating` 改成任何值档位都不变。
  - `subject_mastery`：合成 `numbered_chapters` 小树（含一个跟踪节点）：叶子自挂多项取最低、向上继承最近祖先、未学；
    叶子 `lapses` 取所选项组最大值、`weak` = `lapses >= 2`；只挂 `suspended` 项的叶子按无项处理并进 `excluded_refs`；`unknown_refs` / `tracker_refs`；
    有权重：章权重均摊、无权重叶子权重 0 进 `unweighted_leaves`；`weights=None` 等权；`shares` 4 位小数 ROUND_HALF_EVEN、`ability` = consolidated 占比；总权重 0 时全 null。
  - CLI 装配：`weighted_mastery` 开着但考频文件没登记 / 没有该科 → 退出 2；没开 → 等权。
  - `mastery_gap`：有路线取路线的起止、否则取设置的起止（不混用）、都没有 → `missing_start`；`exam <= start` → `exam_not_after_start`；
    `T` 早于起点 / 晚于终点 clamp 到 0 / 1；差距符号；某科能力 `null` 时该科差距 `null`、其他科照算。
  - 参数校验：错误类型 → `ContractError` 带参数名。
- `tests/contract/test_charts_port.py`：`ability_chart_data` 映射与 HTML 关键文字（`能力 xx.x%`、`应到`、`落后`、薄弱标记与遗忘次数、"暂无薄弱点"）；`ky chart ability` 两次生成逐字节相同、离线。
- `tests/contract/test_workspace.py`：`weighted_mastery` 合法、未知 feature 仍拒绝。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_mastery_port tests.contract.test_charts_port tests.contract.test_knowledge_tree_port tests.contract.test_workspace
```

报告写 `review/rounds/round-260-m30-luna.md`：改动、做法、测试输出原文、"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"、歧义与选择。
不提交；中文字符串写字面量，不要写成 `\uXXXX`；含中文的文件只用 `apply_patch`；写完 `rg -n '\?\?\?'` 检查。
