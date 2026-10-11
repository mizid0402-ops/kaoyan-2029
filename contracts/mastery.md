# M30 掌握度（路线图 ⑤b：能力画像与目标差距的数据端口）

> 决议来源：用户 2026-10-01（§7）。**第二版（同日晚）**：A 真题门槛（§2）、B 按路线阶段目标算应到（§5）。状态：sol 259 初检 FAIL（M1 权重启用、M2 目标差距边界、M3 遗忘次数输出）→ 本版已改；
> 同日用户改选"接 FSRS 并由它接管复习时间"（`contracts/review_progress.md`"FSRS 算法"），档位改按 FSRS 稳定度（§2）。
> 需求依据：`review/requirements.md` §8.3、§8.4。展示由 M17 负责（`contracts/charts.md` §8）。

## 1. 职责与边界

- **只读、纯推导**：输入已加载的复习队列项、各科知识点序列与树语法、可选 408 考频权重、日期与起止日；输出普通映射。不读文件、不写任何状态。
- **自评零特权**（`交接文档.md` §4.1 硬不变量③）：档位只由复习调度状态推导，**不读** `last_self_rating`。
  依据：FSRS 稳定度只在有锚点核对时由 FSRS 更新，未核对的完成不碰它；阶梯模式的间隔只在有锚点核对（correct / partial）时推进变长，
  未核对的完成——无论自评如何——不会让间隔变长，lenient 档最多把它缩短（降档，不提级）（sol 259 已核实两档）。
- 不是预测分数：不把档位换算成考试分数。

## 2. 每个复习项的档位

对状态为 `queued` 或 `scheduled` 的复习项（`suspended`、`retired` 不参与档位，见 §3），取一个"记忆天数" `m`：

- `fsrs` 模式：`m = schedule.stability`（FSRS 记忆稳定度：回忆概率降到 90% 所需天数）；
- 其他模式（阶梯，含尚未核对过的新项）：`m = schedule.interval_days`。

| 档位 | 条件 |
|---|---|
| `learned`（学过） | `m < 7` |
| `progressing`（掌握中） | `7 <= m < 30` |
| `consolidated`（已巩固） | `m >= 30` **且**该复习项有过真题答对（见下） |

门槛 7 / 30 是本端口的常量（用户 2026-10-01 选定），写在一处，测试引用常量名。

**真题门槛**（第二版，用户 2026-10-01 选 A）：只有当该复习项在完成事件里至少有一次 `check: past_question` 且 `outcome: correct` 时，`m >= 30` 才算 `consolidated`；
否则封顶为 `progressing`。改编题、练习、默写对照答对都不够（`contracts/question_bank.md` §2，修订后的 B10）。
调用方从完成事件推出"真题答对过的复习项 ID 集合"传进来（M30 不读文件）。

## 3. 知识点（叶子）的档位

层级与"可学节点 / 叶子"与 M17 §4.3 相同：父子关系用 M4 `tree_parent`，去掉无非 `subject` 后代的 `subject` 级跟踪节点。

- 挂在某节点上的复习项 = `knowledge_point_id` 等于该节点、状态为 `queued` / `scheduled` 的项。
- 叶子的档位：
  1. 叶子自己挂有复习项 → 取这些项档位中**最低**的（一个知识点有多条复习项时，全部巩固才算巩固）；
  2. 否则沿 `tree_parent` 向上找**最近**挂有复习项的祖先 → 取该祖先上各项档位的最低值（按较粗粒度引入的复习视为覆盖整棵子树，同 M17 §4.3）；
  3. 都没有 → `unlearned`（未学）。
- 叶子的**遗忘次数** `lapses` = 第 1 / 2 步取到的那组复习项 `schedule.lapses` 的最大值（未学为 0）；**薄弱** = `lapses >= 2`（用户 2026-10-01：只看遗忘次数）。
  M17 的薄弱清单直接显示这个数，不自己重推（sol 259 M3）。
- 只有 `suspended` / `retired` 项挂着的叶子按"没有复习项"处理（继续向上找或为未学），并在 `excluded_refs` 里列出这些项的 ID。
- 引用不在生效树里或引用了跟踪节点的复习项：不参与，分别列进 `unknown_refs` / `tracker_refs`。

## 4. 科目能力（加权分布）

- 权重启用由**注册表显式开关**决定，不看考频文件里有没有该科的键（sol 259 M1：文件里数学一、英语一也有权重）：
  - 科目档案 `features` 含 `weighted_mastery`（`contracts/workspace.md`）**且**登记了 `reference.topic_weights` → 调用方传该科的 `topic_weight[<科目>]`；
    叶子权重 = 其最近的、出现在该映射里的祖先（含自身）的权重 ÷ 该祖先下可学叶子数；没有这样的祖先 → 权重 0，叶子列入 `unweighted_leaves`
    （"近年真题未覆盖"，页面单独显示，不悄悄消失）。开关打开但没登记考频文件或文件里没有该科 → 契约错误（找到但不能用，fail-closed）。
  - 其他科目调用方传 `weights=None`：每个叶子权重 1。
  - 仓库注册表只给 408 打开 `weighted_mastery`（用户 2026-10-01：408 按考频加权，数一英一等权）；不写死科目 ID（D6）。
- 输出每科四个档位的权重占比（和为 1；总权重为 0 时全部为 `null`）、**覆盖值 = 非 `unlearned` 的权重占比**与**能力值 = `consolidated` 的权重占比**；
  另给不加权的叶子计数（四档各多少个）。占比保留 4 位小数，ROUND_HALF_EVEN，用 `fractions.Fraction` 计算后再舍入（不用浮点累加）；
  四个展示值各自舍入，和可能差 0.0001，这是展示值，不再强行凑 1。

## 5. 目标差距（第二版：按路线阶段目标，用户 2026-10-01 选 B）

第一版按"起点到考试线性"算应到，用户指出不合理：两年计划是基础 → 强化 → 冲刺几轮，第一轮几个月就覆盖完，之后是加深。改为：

- 目标写在路线阶段上：阶段可选 `targets: {covered: 0–100, consolidated: 0–100}`，表示**该阶段末**（`end_exclusive` 那天）应达到的覆盖值与能力值百分比
  （`contracts/route_plan.md` "阶段目标"）。
- 目标点序列 = `(route.start_date, 0, 0)` 加上每个写了 `targets` 的阶段的 `(end_exclusive, covered, consolidated)`，按日期升序。
- 今天 `T` 的应到：落在两个相邻目标点之间 → 两点间按天数线性插值（`Fraction`，输出 4 位小数）；早于起点 → 0；晚于最后一个目标点 → 取最后一个目标点的值。
- 没有当前路线 → `status: missing_route`（"目标差距需要路线"）；路线没有任何阶段写 `targets` → `status: no_targets`（"路线还没写阶段目标"）；两者 `expected` 为 `null`。
  复盘设置不再作为起止日期来源（第一版的同源规则随之作废）。
- 每科两个差距：`gap_covered = 覆盖值 − 应到覆盖`、`gap_consolidated = 能力值 − 应到巩固`；该科值为 `null` 时对应差距为 `null`，其他科照算。
- 目标对三科相同（路线是全局的）；以后要分科目标再另议。

## 6. 端口

```python
LEARNED_MAX_DAYS = 7          # interval < 7 → learned
CONSOLIDATED_MIN_DAYS = 30    # interval >= 30 → consolidated
WEAK_MIN_LAPSES = 2

item_level(item: ReviewItem, past_question_passed: bool) -> str | None   # queued/scheduled → 档位；其余 None
subject_mastery(subject_id, points, grammar, items, weights: Mapping[str, float] | None,
                past_question_passed: Collection[str]) -> Mapping   # 真题答对过的 review_id 集合（§2）
mastery_gap(subjects: Sequence[Mapping], today, route: RoutePlan | None) -> Mapping
    # {status: "ok" | "missing_route" | "no_targets",
    #  expected: {covered: "0.xxxx", consolidated: "0.xxxx"} | null,
    #  subjects: [{subject_id, covered, ability, gap_covered, gap_consolidated}]}   # 差距 "±0.xxxx" | null
```

`subject_mastery` 映射：

```
{subject_id, leaves: {<leaf_id>: {level, lapses: int, weak: bool, weight: str(Fraction 4 位小数)}},
 counts: {unlearned, learned, progressing, consolidated},
 shares: {unlearned, learned, progressing, consolidated} | 全 null,
 covered: "0.xxxx" | null, ability: "0.xxxx" | null,
 weak_leaves: [leaf_id, ...],            # 按树文件顺序
 unweighted_leaves: [leaf_id, ...],
 unknown_refs, tracker_refs: [knowledge_point_id, ...], excluded_refs: [review_id, ...]}   # sol 263：引用清单口径按实现统一
```

参数先校验再运算（`AGENTS.md` 已知缺陷 6）：类型不对、`today` 不是 `date`、树语法未知 → `ContractError` 带参数名。

## 7. 决议记录（用户 2026-10-01）

| 问题 | 选择 |
|---|---|
| 档位 | 四档：未学 / 学过 / 掌握中（≥ 7 天）/ 已巩固（≥ 30 天）；同日改选 FSRS 后"天数"= FSRS 稳定度，阶梯项仍用间隔（§2） |
| 薄弱点 | 只看遗忘次数 ≥ 2 |
| 科目能力 | 408 按考频权重加权，数学一、英语一等权 |
| 应完成度 | 按时间从起点到考试线性推进 |（第一版）
| 档位第二版 | A：已巩固须真题答对过（§2） |
| 应到第二版 | B：按路线阶段末目标插值，覆盖与巩固两项（§5）；第一版的时间线性作废 |

决策者自拟、待 sol 初检的细则：§2 档位按 `interval_days` 而不是 `repetitions`；§3 多项取最低、粗粒度向上继承、`suspended`/`retired` 不计；
§4 章权重均摊到叶子、无权重叶子权重 0 并单列；能力值只算 `consolidated` 占比（不给"掌握中"折算分）；§5 起点 / 终点的取法与目标 = 全部巩固。
