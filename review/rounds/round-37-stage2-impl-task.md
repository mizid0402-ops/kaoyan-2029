# 任务：②「24 个月计划与月度闭环」实施

> 本任务书由主控根据两份独立方案（Codex / Claude）合成。**实施者：Claude Sonnet 5（high）。**
> **主控负责审查。** 项目已有 git（`F:\workspace\kaoyan-ai-system`）。

---

## 0. 开工前必做

1. **`git status`** 确认起点干净。若有未提交改动，**先报告，不要覆盖**。
2. 跑一次 `py -3.12 -m unittest discover -s tests -q`，**记录开工前基线**（应为全绿）。
3. 开工前对以下文件算 **SHA-256 并记在报告里**（用于事后证明你没偷改它们）：
   - `ky/schedule/review_clip.py`（**排序核，只许加参数，不许改算法**）
   - `ky/schedule/budget.py`、`ky/schedule/longitudinal.py`、`ky/schedule/monthly_close.py`
   - `ky/schedule/vocab_channel.py`、`ky/models.py`

---

## 1. 背景：已定的设计原则（**不可违反**）

用户已拍板（见 `docs/阶段2决议-预算与词汇编排.md`）：

> **系统提供"输入接口 + 护栏"，不提供"数值决定"。**

| 决定 | 内容 |
|---|---|
| 每日时长 | **不写死**，由"负责当天学习任务的 AI"自由安排 |
| 每日词量 | 同样由该 AI 安排 |
| 四科占比 | 40/20/40 只是**初始默认**；后续按"还剩多少/已学多少"动态调 |
| 词汇编排 | 按天分摊到 24 个月；前十几个月以背词为主，之后转长难句/短语 |
| 长难句/短语 | **留扩展位，当前不安排来源** |
| 距考试 N 天清空积压 | **不是必须的**，降为可选倾向 |

**边界规则（Claude 提出，主控采纳）**：

> 系统里**不存在第四类函数**。每个公开函数只能是：
> **① 读**（快照/查询）｜**② 验证**（布尔判断 + 精确原因）｜**③ 写**（原子落盘已验证的记录）。
> **不存在"建议/推荐/默认/优化"式函数。**

**这条要能被机器检查**：新增模块的公开函数名**不得**命中
`recommend*` / `suggest*` / `default*` / `optimal*` / `next_month_*`。
`monthly_close.py` 已有先例（`test_close_does_not_prescribe_next_month`），**把该模式复制到新模块**。

---

## 2. 第一步：修护栏的洞（**必须先做**）

主控写的 `check_invariants()` 有五条护栏，但**实测至少四条不成立**。
以下**七条已由主控逐条复现**，全部为真：

| # | 洞 | 实测现象 |
|---|---|---|
| 1 | `vocab_new_items` 为负可通过 | `-5` → `ok=True`（该字段根本没被检查）|
| 2 | `backlog_minutes` 为负可通过 | `-1` → `ok=True` |
| 3 | **不传 `subject_minutes` 时，比例倒置检查完全不运行** | 权重 `0.90/0.05/0.05` → `ok=True` |
| 4 | `max_single_item_minutes` 比的是**整条通道总量**，不是单条 | 知识通道共 60 分钟、上限 30 → 报 `knowledge allocation 60 exceeds the single-item bound 30` |
| 5 | **声明足够 backlog 后，任何超载都合法** | 容量 60、分配 100、`backlog=40` → `ok=True` |
| 6 | `close_month` 把同一天传两次会**双计** | `days_planned=2`、`available=120`（单日应为 60）|
| 7 | `PlanHorizon` 的"24 个月"是 **720 天**，不等于 24 个日历月 | `2026-09-15 → 2028-09-04`，实际日历应为 731 天；源码注释还误写"730 days" |

### 要求

- **1–5 修在 `check_invariants`**：每个数量字段**逐字段闭合**——所有数量非负；
  学科分钟合计等于知识通道；**每个 pass 单独受上限**（不是通道合计）；
  已安排分钟不超过可用容量；未安排需求**逐项**进入 backlog；同一版本同一天唯一。
- **6 修在 `monthly_close`**：同一天重复传入必须**拒绝或去重并报告**，不得静默双计。
- **7 修 `PlanHorizon`**：改为**日历感知**（真正的 24 个日历月），并修正错误注释。
  **注意**：改了会牵动 `test_longitudinal.py` 里断言 721 天的测试——**那是既有测试，
  要同步更新，并在报告里说明改了哪条断言、为什么新值是对的**。
- **新增回归测试锁死这七条**：每条都要有一个"修复前会通过、修复后会拒"的用例。

### 完成标准

- 七条各自有测试，且**变异测试证明有效**（把修复改回去 → 测试变红 → 还原 → 给前后哈希）
- 既有 306 个测试**不许因为修护栏而失效**（若某条既有断言依赖旧行为，需说明并更新）

---

## 3. 第二步：`review_clip` 接受当日预算覆盖

**问题**（Claude 独立发现，且主控在 `阶段2决议` §3 的 C6 条已承认但未落实）：

`ky/schedule/review_clip.py::select_daily_reviews()` 的预算来源是
`config.total_daily_minutes`——**从配置加载一次的单一标量**。
**所以"120 不写死"这条决议，对复习通道实际上没有落地。**

### 要求

- 给 `select_daily_reviews()` **加一个可选参数**（建议 `daily_minutes_override: int | None = None`），
  缺省回退到 `config.total_daily_minutes`。
- **硬上限与软配额基于该值计算。**
- **只许扩展签名，不许改排序算法**（排序核已过 4 轮审查 + 变异测试）。

### 完成标准

- 不传该参数时，**输出与今天逐字节一致**（用既有测试证明）
- 传该参数时，硬上限/软配额**确实按新值算**（新增测试）
- 既有 306 个测试**一个不改地全部通过**

---

## 4. 第三步：`RoutePlan`（24 个月路线）+ 状态快照

### 4.1 `ky/schedule/planning.py`（新）—— `RoutePlan`

**Codex 指出的承重缺口**：现在只有零散 `DayPlan` 和汇总，**没有阶段、月容量包络、路线版本、
目标考试日**。所以"24 个月计划"实际不存在。

**要求**：
- `RoutePlan` 含：`route_id`、**不可变 `revision`**、`start_date`、`end_exclusive`、
  `target_exam_date`、**24 个连续月包络**、`policy_version`、**阶段①输入的哈希**
- 每个包络含：阶段标签、预测容量、学科权重、通道容量、目标词数
  —— **这些数值全部由 AI 提案，系统只验闭合性**
- **只做 24 个"计划月/阶段容量包络"，绝不预生成 731 天的具体任务**
  （否则是制造两年后的虚假精度）

### 4.2 `ky/schedule/state_snapshot.py`（新）—— 状态快照

**给 AI 看的"今天的仪表盘"，不是"今天该做什么"。**

含：每科"知识树总条目 / 已进入复习队列条目 / 今日到期复习条数与分钟 / 当前 backlog 分钟"、
词汇通道"已投递词数 / 剩余词数"、"距考试天数"。

**两条硬要求**：

1. **只读**，不写任何文件，**不做任何"建议"**
2. **每个来自知识树的数字必须带 `tree_status` 字段**——如实反映 `extracted`/`approved`。
   **理由**：三棵树的 `status` **全部是 `extracted`，无一个 `approved`**，
   而契约明确"extracted 不得用于频率统计、考纲覆盖率或能力画像"；
   而"还剩多少/已学多少"**语义上非常接近覆盖率**。
   **不允许把未审核的计数伪装成权威覆盖率。**

---

## 5. 第四步：日计划落盘 + CLI

### 5.1 `ky/storage/day_plan_store.py`（新）

**复用 `ky/storage/review_shards.py` 的落盘范式**（临时文件 → 用同一份校验逻辑重读 →
`os.replace` 原子提交 → 失败清理；manifest + sha256；**不覆盖旧文件，只加新版本**）。

- 单位：每天一个 `DayPlan` 记录，**按月分片**
- `write(day_plan)`：**提交前必须先跑 `check_invariants()`，不过就拒绝写入**，
  错误精确到是哪一条护栏
- `write(month_close)`：**追加式，一旦写入不可覆盖**（闭环是历史事实，不能被"改分"）
- `load(date)` / `load_month(year, month)`：只读查询

**注意**：`ReviewShardStore` 硬编码了 `ReviewItem` 的字段，**结构上装不了 `DayPlan`**——
**不要硬塞，另建 store**。

### 5.2 CLI（在 `ky/__main__.py` 加子命令，延续现有 `preflight`/`ledger` 的风格）

```
py -3.12 -m ky snapshot --config ... --items ... --date ...           # 只读，打印快照
py -3.12 -m ky day-plan submit --config ... --plan <plan.yaml> --store <dir>
py -3.12 -m ky day-plan record  --config ... --done <done.yaml> --store <dir>   # 见第六步
py -3.12 -m ky month-close --store <dir> --year --month               # 首版只读打印
```

- **退出码约定沿用现有**：`0`=成功，`2`=契约/护栏违规，`3`=用法错误
- 违规时**不写任何东西**，打印精确到字段的违规原因

---

## 6. 第五步：复习项推进状态机（**用户已定：归入"AI 分配学习"板块**）

**背景**：`ReviewItem` **只有 `with_deferral()`**（未完成时 `defer_count+1`），
**没有任何函数在"今天真的完成了"时推进 `due_date` / `interval_days` / `ease_factor` / `repetitions`**。

**后果**：**复习队列是死的**——完成的复习不会往后排，`review_clip.py` 的排序核
**会一直基于"从未完成过"的假设运行**。

**用户决定：这个状态机归入"AI 分配学习"板块**（即日计划的提交/完成记录模块），
不单独立项。

### 要求

- **区分"计划"与"实际"**：`monthly_close` 现在拿 `DayPlan` 当"实际发生"，**这是错的**。
  必须有独立的**完成事件**模型与写入入口。
- **投递单词 ≠ 学会单词**：`vocab_delivered` 与 `vocab_practiced` **分开统计**，
  **不得用 delivery 代替完成**。
- 完成事件要能**确定性地推进 `ReviewItem`**（`due_date` / `interval_days` 等）。
- **`data/english_vocabulary/eng1_vocabulary.sqlite` 永久只读**：
  现在 `tools/daily_words.py` 会写它的 `delivery_log`，**下一次投递就会改变冻结哈希**
  （冻结值 `839d48be…`）。后续投递状态**写到外部学习事件**，现有 15 条 delivery 作为基线导入。

---

## 7. 完成标准（缺一不可）

| # | 标准 |
|---|---|
| 1 | 七条护栏洞各有测试，且**变异测试证明有效 + 还原哈希** |
| 2 | `review_clip` 扩展后，**既有 306 测试一个不改地全绿** |
| 3 | `RoutePlan` 能表达 24 个日历月包络，**且不预生成逐日任务** |
| 4 | `state_snapshot` **只读**（沙盒测试证明零文件写入），且**每个知识树数字带 `tree_status`** |
| 5 | `day_plan_store`：违规提交后**目录哈希完全不变**（零副作用）；合法提交可原样读回 |
| 6 | 三个 CLI 子命令遵守退出码约定，**违规输入不产生任何文件**（黑盒测试） |
| 7 | 完成事件能推进 `ReviewItem`；`vocab_delivered` 与 `vocab_practiced` 分开 |
| 8 | **词库 SQLite 只读**：跑一次投递后其哈希不变 |
| 9 | `py -3.12 -m unittest discover -s tests -q` **全绿**，且新增测试数 > 0 |
| 10 | 新模块公开函数名**不命中** `recommend*/suggest*/default*/optimal*/next_month_*` |

---

## 8. 明确不做

- **③④⑤** 任何东西（Web 投影、课表协同、可视化）
- **任何"推荐/建议/默认分配"函数**——即使只是给用户看的提示文案也不做
- **长难句/短语素材接入**——`phrase_minutes` 字段留着、值可为 0，仅此而已
- **不替换 `review_clip.py` 的排序核**，只加可选参数
- **不自动把 `month-close` 写成不可逆历史**——首版只读打印
- **不替用户决定"知识树 approved 之前能不能用于快照"**——只做到如实标注状态

---

## 9. 纪律

- **可改/可新建**：`ky/**`、`tests/**`、`review/rounds/**`
- **禁止改**：`data/**`（含所有树、索引、词库）、`docs/**`、`review/408知识点树与真题/**`
- **禁止为了让测试通过而放宽验证**——修护栏是**加严**，不是放宽
- **不许改 `review_clip.py` 的排序算法**，只加参数
- 本机**没有 `rg`**，用 Glob/Grep 或 `Get-ChildItem -Recurse`
- 必须用 `py -3.12`
- 终端吞中文：结果写 UTF-8 文件再用 read 工具读
- **改完必须 `git add -A && git commit`**，提交信息写清改了什么、什么是已知未完成
- 不要 push（没有远程）

## 10. 报告

写入 `review/rounds/round-37-stage2-impl-claude.md`：

1. 开工前 `git status` 与测试基线
2. **开工前 vs 完工后**，那 6 个既有文件的 SHA-256 对比（证明你没偷改）
3. 五步各自怎么做的
4. **10 条完成标准的实际输出**（原始命令 + 结果）
5. 七条护栏洞的**变异测试结果 + 还原哈希**
6. 你更新了哪些既有断言、为什么新值是对的
7. 「我实测到了」vs「我推断」
8. 没有把握的地方至少 3 条

最后用一句话回复：五步各完成没有 + 10 条标准过了几条 + 既有 306 测试是否仍全绿 + 提交哈希 + 报告路径。
