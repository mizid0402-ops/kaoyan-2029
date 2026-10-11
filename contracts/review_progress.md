# 端口规格：复习推进（M10）

对应决议：`docs/阶段2.5-接缝收口.md` §七 D3、D8′、D9；`README.md` 硬不变量③；
`docs/评审结论与实施契约.md` §4.3。

## 完成事件

完成事件使用 `schema_version: 2`；可选 `study_minutes`（当天实际学习总分钟，非负整数，排除布尔）存在时写 `schema_version: 3`。
缺少该字段仍写 v2，保持既有文件字节不变；填 `0` 是有效记录。v1、v2、v3 均可读取，v1/v2 读取为 `study_minutes=None`。
每条 `reviews` 记录包含非空 `review_id`、ISO 日期
`completed_on` 和 `check`。`check` 取 `past_question`（真题）、`exercise`（练习题）、
`recall_vs_notes`（默写后对照）或 `none`（未核对）。当 `check` 不是 `none` 时，必须提供
`outcome`：`correct`、`partial` 或 `incorrect`。当 `check` 为 `none` 时，`outcome` 必须缺省。

`question_ref` 是可选字符串，用于引用核对材料，例如 `cs408-2023-1`。系统信任用户对照答案后
声明的 `check` 和 `outcome`，不独立验证实际核对材料，因此 `question_ref` 可选。
`self_rating` 是可选四档自评（`unknown`、`vague`、`basic`、`fluent`）。每条记录可提供
`completion_id`（非空字符串）；缺省时，解析器按其完成事件日期和 `reviews` 中的零起始位置
生成 `"{event.day}#{index}"`。同一事件内 completion ID 必须唯一。

旧 `schema_version: 1` 事件仍可读取。其 `quality` 是历史自评，解析后等价于 `check: none`，
不得参与推进。该语义变化是有意的：D3 要求复习完成只认有锚点的核对结果，落实硬不变量③。
已写入的 v1 文件是只写一次的历史记录，不作迁移或覆盖。

## 推进端口

`ReviewAlgorithm` 定义 `progress_quality(completion)` 和
`advance(item, completion) -> ReviewItem`。调用方依赖此协议；算法可替换，例如未来以 FSRS
实现相同端口。`LadderSm2Algorithm(self_rating_mode="strict" | "lenient")` 在构造时接收策略；缺省
为 `strict`。outcome 到质量的映射只由算法提供；两种策略的已核对推进相同。

对 `check != none`，推进用质量固定映射为 `correct -> 4`、`partial -> 3`、`incorrect -> 1`，
再按现有 fixed-bootstrap 阶梯和 SM-2 Lite 公式推进。阶梯、公式及其既有边界保持不变。

对 `check == none`，按 D9 策略推进：

| 策略 | 自评 | `check == none` | `check != none` |
|---|---|---|---|
| strict | unknown | 保持当前间隔 | 按核对结果推进 |
| strict | vague | 保持当前间隔 | 按核对结果推进 |
| strict | basic | 保持当前间隔 | 按核对结果推进 |
| strict | fluent | 保持当前间隔 | 按核对结果推进 |
| lenient | unknown | 间隔设为 1 天 | 按核对结果推进 |
| lenient | vague | 间隔设为 `max(1, interval_days // 2)` | 按核对结果推进 |
| lenient | basic | 保持当前间隔；报告 `needs_check` | 按核对结果推进 |
| lenient | fluent | 保持当前间隔；报告 `needs_check` | 按核对结果推进 |

无自评时，两种策略都保持当前间隔；lenient 报告 `needs_check`。

所有未核对的结果都不得比同一完成但无自评的结果间隔更长。`due_date` 为
`completed_on + 本次间隔`。已核对结果不受策略或自评影响，按上面的质量映射推进。

`self_rating` 是允许更新的排序元数据：完成事件带有该字段时写入 `ReviewItem.last_self_rating`，
缺省时保留原值。严格策略以及 lenient 的 basic/fluent/无自评不改变其调度间隔。v1 的历史
`quality` 不参与推进。

## 宽松档的出题提示（D9）

`day-plan record --review-store` 在 `review_policy.self_rating_mode: lenient` 下完成推进后，若推进报告
含 `needs_check_review_ids`，按每个复习项的 `knowledge_point_id` 调用 M24
`candidate_check_questions(workspace, knowledge_point_id, limit=3)`。出题提示是只读附加信息，不写入
完成事件或队列，也不改变推进结果。严格档不调用 M24、不产生出题提示。

文本输出每个候选一行：`<review_id> 需要核对：<question_id>（<年份> 第 <题号> 题，卷面第 <页> 页）`。
无关联真题时输出：`<review_id> 该知识点无真题，可用 AI 巩固题（仅 guided 证据）`。
`--json` 将候选结果放在 `check_question_candidates` 数组中；每项包含 `review_id`、
`knowledge_point_id`、M24 的 `candidates` 和 `fallback`。未找到工作区注册表时记录与队列推进照常完成，
文本输出 `未找到工作区注册表，跳过出题`；JSON 返回空数组并以
`check_question_suggestions_skipped` 说明跳过原因。

## D8′：每条完成记录只计算一次

完成事件中的每条记录均按到达顺序对当前队列状态计算。同一复习项同日有多条不同完成记录时，
每条都推进。`ReviewShardStore` manifest 持久保存已计算过的 `completion_id` 集，并与更新后
队列在一次 manifest 原子替换中提交。schema-1 manifest 可读取，但其历史计算身份不可恢复：
schema-1 队列里**只要有任一项**已有 `last_reviewed_on`，对该队列的任何写入（推进任何一项、
增删复习项）都必须拒绝，推进时提示“旧版队列无已计算记录，无法保证只算一次；请先升级队列”；
这项检查属于写入前预检，完成事件写入之前就要拒绝。整条队列都拒绝而不只拒绝已复习项，是因为提交
任何一项都会把 manifest 升为 schema 2，旧历史"未经证明"这一事实随之丢失（sol 第 60 轮 C2）。
所有项都从未复习过的 schema-1 队列没有历史可重放，可照常推进，并在提交时将 manifest 写为 schema 2。

调用方也可显式调用 `upgrade_legacy_queue(store, acknowledge_unknown_history=True)`。
这表示调用方确认旧计算记录未知且无法恢复；升级保留当前队列项，但以空的已计算 ID 集生成
schema-2 manifest。未显式确认时拒绝升级。升级后只保证新写入的计算 ID 可防止重放。

- 已计算过的 `completion_id` 报告为 `replayed`，不推进，也不写入队列。
- 较 `last_reviewed_on` 更早的记录仍推进，报告为 `late`；调度按到达顺序作用于当前状态，
  `last_reviewed_on = max(旧值, completed_on)`。
- `day-plan record --review-store` 写入前仅因未知 `review_id` 或事件内重复 `completion_id`
  拒绝；同日的不同完成和较早补录均不是冲突。

此规则信任用户对照答案后声明的核对结果。`question_ref` 是可选引用，未提供它不会使声明失效。

## 退回起点（D11）

`reset_for_relearning(schedule: ReviewSchedule) -> ReviewSchedule` 将
`interval_days` 设为 `1`、`repetitions` 设为 `0`，并保留 `mode`、`phase`、
`ease_factor` 与 `lapses`。这是长期逾期后的重学安排，不是一次核对失败；因此不增加
`lapses`，也不降低 `ease_factor`。

## FSRS 算法（第二个 `ReviewAlgorithm` 实现；用户 2026-10-01）

> 决议：用户看过第一周模拟实验（决策者 scratchpad 里的 `sim_fsrs_week1.py`，未入库）后选择"接 FSRS，并且让 FSRS 接管复习时间"。
> 状态：sol 261 初检 FAIL（F1 记忆时钟、F2 补录时间倒流、F3 投影例外）→ 本版已改。容量裁剪、科目配额、八键排序（M9）不变；FSRS 只决定每个复习项的下次到期日与记忆状态。

### 选择开关

考试配置 `review_policy.algorithm`：`ladder`（缺省，即现有 `LadderSm2Algorithm`）或 `fsrs`（`FsrsAlgorithm`）。
**省略时一切行为与输出逐字节不变**（`AGENTS.md` 已知缺陷 7）。`self_rating_mode` 两种算法都适用（见下）。
"逐字节不变"覆盖命令输出与状态文件。**显式例外**（sol 261 F3）：只读投影是可删可重建的缓存，按"结构变就升版"规则升到 schema 5、
`review_items` 新增三列（见"复习项的 FSRS 状态"）；非 `fsrs` 复习项这三列为 NULL，其余表与列不变。

### 依赖与参数

- 依赖 `fsrs>=6,<7`（`open-spaced-repetition/py-fsrs`，MIT；2026-09-15 轮子调研已核验）。
- `Scheduler(parameters=默认, desired_retention=0.9, learning_steps=(), relearning_steps=(), maximum_interval=180, enable_fuzzing=False)`：
  - 按天计（无分钟级学习步）；`maximum_interval=180` 与队列 `interval_days` 上限一致；关掉随机扰动以保证同输入同输出。
  - 参数用库的默认值；以后有真实复习记录再用 FSRS 优化器拟合（另立包，需用户同意）。
- 时刻：一次完成的复习时刻取 `completed_on` 当天 `00:00 UTC`；到期日 = FSRS 返回的 `due` 的 UTC 日期；`interval_days = max(1, (due 日期 − completed_on).days)`。

### 核对结果 → FSRS 评分

| `check` / `outcome` | FSRS |
|---|---|
| `correct` | `Rating.Good` |
| `partial` | `Rating.Hard` |
| `incorrect` | `Rating.Again` |
| `check: none`（任何自评） | **不调用 FSRS**，记忆状态不变（硬不变量③） |

`Rating.Easy` 不使用（没有对应的锚点结果）。

### 复习项的 FSRS 状态

- `ReviewSchedule.mode` 新增取值 `fsrs`；`fsrs` 模式另有三个必填字段：`stability`（有限浮点，> 0）、`difficulty`（有限浮点，1–10）、
  `fsrs_reviewed_on`（ISO 日期，**FSRS 记忆时钟**＝最近一次被 FSRS 采用的已核对完成日期）。其他模式**不得**出现这三个字段（旧模式的复习项写盘字节不变）。
  `fsrs` 模式下 `phase` 固定为 5、`ease_factor` 原样保留不用；`repetitions` 每次被 FSRS 采用的已核对推进 +1，`lapses` 在 `Again` 时 +1。
- **记忆时钟与"最近完成"分开**（sol 261 F1）：`last_reviewed_on` 仍按现有规则随每次完成（含未核对）更新，供排序与展示；
  FSRS 只用 `fsrs_reviewed_on`。未核对完成与 D11 退回起点**不改** `stability`、`difficulty`、`fsrs_reviewed_on`。
- FSRS 卡片由 `stability`、`difficulty`、`fsrs_reviewed_on`（作为 `last_review`，当天 00:00 UTC）还原，`state = Review`，`card_id` 固定为 1（只用于计算，不持久化）；
  卡片 `due` 不参与计算。**首次接管**（非 `fsrs` 项的第一次已核对完成）用库的新卡 `Card(card_id=1)`（默认 `State.Learning`，空学习步使其一次评分后进入 Review）。
- **从阶梯切换**：`algorithm: fsrs` 时，一个非 `fsrs` 模式的复习项在下一次**已核对**完成时按新卡处理（忽略阶梯历史），完成后变为 `fsrs` 模式。
  尚未核对过的新复习项仍按现有创建规则（`fixed_bootstrap`、次日到期）入队，不改创建端口。

### 晚到的已核对完成（D8′ 补录；sol 261 F2）

已核对完成的 `completed_on` **早于**该项 `fsrs_reviewed_on` 时（例如先记了 10-10 的核对，又补录 10-05 的），FSRS 不能倒着算：
**不调用 FSRS**，`stability`、`difficulty`、`fsrs_reviewed_on`、`interval_days`、`due_date`、`repetitions`、`lapses` 都不变，只按现有规则更新 `last_reviewed_on`；
该 `completion_id` 照 D8′ 记为已计算（不会重放）；推进报告新增列表 `fsrs_late_checks`（`review_id`、`completion_id`、`completed_on`、当时的 `fsrs_reviewed_on`），
CLI 打印一行"晚到的核对未被 FSRS 采用：…"，不静默。`completed_on` **等于** `fsrs_reviewed_on`（同日第二次核对）照常调用 FSRS（经过 0 天，库的短期分支），不是倒流。

### 未核对的完成（`check: none`）

记忆状态不变；到期日按 D9 表的同一规则只作用于 `interval_days`：strict 保持当前间隔；lenient 的 `unknown` → 1、`vague` → `max(1, interval_days // 2)`。
所有未核对结果都不得比同一完成但无自评的结果间隔更长（与阶梯算法同一约束）。

### 退回起点（D11）与 FSRS

`reset_for_relearning` 对 `fsrs` 模式：`interval_days = 1`、`repetitions = 0`，**保留** `stability`、`difficulty`、`fsrs_reviewed_on`、`lapses`。
下次已核对完成时，FSRS 按真实间隔（可能很长）与评分自行更新记忆状态，不额外惩罚。

### 从 FSRS 切回阶梯

把 `algorithm` 改回 `ladder` 后，`fsrs` 模式的复习项在下一次已核对完成时按 `sm2_lite` 处理：以当前 `interval_days` 与原 `ease_factor` 进入 SM-2 Lite 公式，
完成后 `mode = sm2_lite`、去掉三个 FSRS 字段。未核对完成按 D9 表只改间隔，模式与 FSRS 字段不变。
