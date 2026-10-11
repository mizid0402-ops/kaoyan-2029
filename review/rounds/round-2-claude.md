# 第二轮：交叉复核 + 实现契约收敛 —— Claude Code（claude-sonnet-5, high，主实现者）

> 本轮已实际读取 `F:\workspace\study\study_workspace\` 下的 `project_config.py`、`schedule.py`、
> `project.py`、`recovery.py`、`recovery_selection.py`、`skill_graph.py`、`week_evidence.py`、
> `daily_evidence.py`、`capability_registry.py`、`capability_proposals.py`、`month_close.py`、
> `workspace_sync.py`、`cli.py`、`generation.py`（部分）与 `README.md`，所有涉及代码事实的论断
> 均以本次实读为准，不复用第一轮印象。凡未联网复核的外部事实标注"未核实"。

---

## R1. 交叉复核

### 共识（双方独立得出、合并为一条）

1. **380 分不能作为工程验收目标**，只能是用户侧长期参考值；系统内部必须换成可测的过程/代理指标（知识点覆盖率、限时正确率、预测误差等），并保留不确定性。
2. **24 个月总规划只能做到"阶段边界 + 预算占比"粒度**，不能写到日级，否则与 §16.2"不得一次性写死"直接冲突；月/周/日按"滚动展开"分层承诺。
3. **自评四档（不会/模糊/基本会/熟练）不能单独支撑能力画像与差距分析**，必须叠加客观信号（正确率、限时表现、错误类型），否则是伪精度。
4. **"近十年真题"自动联网批量抓取/再分发有版权与准确性风险**；真题正文应来自用户合法提供或授权白名单，AI 只做结构化，不做原文获取与再传播（此点在用户拍板 D6 后已定案，此处仅确认双方论证方向一致）。
5. **资料结构化必须有质量门禁**：knowledge point/题型/难度等定性字段可由 AI 出初稿，但"出现频率"这类定量声明必须由确定性脚本对已批准语料计数，不能由 LLM 直接报数字；需要 `raw→extracted→reviewed→approved` 状态机与人工金标抽检。
6. **课表模型需要"周期表 + 例外事件"两层**，静态周模板无法覆盖调课/考试周/节假日/寒暑假；不过 D4 已定第一版不做课表，这条结论后置生效。
7. **网站/数据库与本地文件必须锁定唯一真相源**，禁止"网页改数据库、AI 改本地文件"两个独立生效的写入口同时存在。
8. **第一版必须是单用户、本机运行**（现已由 D5 定案）。
9. **`study` 目前完全没有课程表时间槽与冲突检测能力**——`schedule.py` 只回答"某天属于第几周/是否处于暂停期"，不回答"某天几点到几点有课"。本轮已复读 `schedule.py` 全文确认：其核心是 `frozen_period`/`projected_period`（周计划自身的时间区间）与 `pause_intervals`（暂停区间回放），与"日历时间槽冲突检测"是完全不同的问题域。
10. **两方都推荐路线 C（复用内核 + 扩展包），且都主张"先用 B 式最薄接入验证，再演进为 C"**，不是一步到位改造 `study`。
11. **§18 先整理十年资料这一步在本机现状下会直接阻塞**（`context.md` 已实测本机无任何考研资料），推进顺序必须调整，先做一个不依赖资料的验证闭环。

### 真分歧（逐条裁定）

#### 分歧 1：复习容量估算口径——"5×N 稳态 + 87,600 分钟总预算"（Codex）vs "N≈2.5/天 + 12.5 条/天 + 单词通道 100 词/天"（Claude）

**这两套数字不是真冲突，是同一方法论的不同颗粒度应用，可以直接合并使用。**

- Codex 的 `87,600 分钟`（`730 天 × 120 分钟`）是**总预算天花板**，`5nr` 是**通用稳态公式的示意**（用 `n=5, r=5` 这组不针对具体考研语料的数字，证明"哪怕很保守的参数，固定 5 次复习也会在约 30 天后吃满预算"）。它的价值是给出一个**任何具体语料都必须服从的宏观上限**，代价是没有落到"这次考研到底有多少知识点"这个具体问题上，因而不能直接用来设计裁剪算法的参数。
- Claude 的 `N≈2.5/天`、`12.5 条/天` 是**对本次考研语料规模的具体估算**（数学一+408 约 1200–1600 个知识点级条目 ÷ 510 个有效学习天），额外单列了英语单词这条独立通道（这是 Codex 版本完全没有量化的部分——单词复习成本结构（`0.5–2 分钟/词`）与知识点复习（`5–15 分钟/条`）差一个数量级，混在一起算会显著低估）。它的价值是**可直接用于工程参数**，代价是"1200–1600 个知识点"这个数字目前是**未核实的估计值**，一旦真实 408/数学一大纲到手，需要用确定性脚本重新计数校准（这正是 R3.3 "频率必须由脚本产出"原则的自然延伸）。
- **裁定**：两者都保守（都用固定 5 次全量复习的最坏情形，没有假设任何合并/降频），**Claude 的估算更可证伪**——因为它给出了具体的 N 和数据来源假设，可以在拿到真实大纲后立刻验证或推翻；Codex 的估算更适合做**宏观分钟预算的护栏检查**（"总投入 1,460 小时里，光是知识点+单词两个复习通道稳态就要吃掉约 208–458 小时"这类跨阶段的量级判断）。R3.2 会同时使用两者：知识点/单词/公式分通道估算参数，Codex 式总预算上限做护栏断言。**不存在需要二选一的冲突。**

#### 分歧 2：AI 生成题能否用于训练与统计——Codex（不进频率统计、不进最终验收）vs Claude（基础期可用、三四阶段须真资料、分开标签）

**裁定：采纳 Codex 的强约束作为底线，Claude 的分期例外作为其内部的一个受限子集，给出可执行的机器可判分界规则，而不是停留在"分开标签"的软约束。**

- 分界规则（新增 schema 字段，见 R3.3）：每条练习题/题目引用必须带 `source_type: verified_exam | ai_generated`。
- `frequency.value`（出现频率）、`skill_graph.yaml` 的 `validation: independent`（升级判定）、以及任何"距 380 分差距"的展示，**只能读取 `source_type == verified_exam` 且状态为 `approved` 的条目**——这是 Codex 立场的字面落地，无例外，无阶段差异。
- `ai_generated` 条目**只允许**出现在 `ReviewItem` 的 `item_type` 为 `concept`/`formula` 的**巩固练习**里，且**必须**满足：该知识点在真题语料库（`verified_exam`）里当前**没有任何 approved 条目**覆盖（用一个查询函数 `has_verified_coverage(kp_id)` 机器判断，不是人工判断"处于基础期所以可以用"）。一旦该知识点有了 `verified_exam` 条目，`ai_generated` 条目自动降级为 `status: retired`，不再被日计划选中。
- 这样"基础期可用"不再依赖"现在是第几阶段"这种模糊时间判断（Claude 原提案的弱点：阶段边界本身还没定案），而是依赖"这个知识点有没有真题覆盖"这个随时可查的客观状态——**在真题稀缺的早期，覆盖率天然低，AI 生成题自然会被大量使用；真题到位后自动退场**，不需要额外维护"现在到第几阶段了"的门禁逻辑。

#### 分歧 3：§18 推进顺序该不该改——Codex（决策合同→一周排程闭环→资料台账→…）vs Claude（插入"第 0 步：索要资料"）

**裁定：两者不冲突，合并为一条顺序，并按 D4 修正"排程闭环"的内容。**

Claude 的"第 0 步"和 Codex 的"决策合同"本质是同一件事的两种表述——都是"在动手之前，先把用户尚未回答的阻塞项问清楚"（这正是 R2 的产出）。合并后的顺序：

```
0. 决策合同（R2 阻塞清单拍板，含资料来源确认——即 Claude 的"第0步"与 Codex 的"决策合同"是同一步）
1. 固定预算容量闭环验证（原 Codex 的"一周排程闭环"，按 D4 去掉课表/冲突检测部分，见 R1-分歧4）
2. 资料台账 + 小样本金标（Codex/Claude 一致）
3. 知识结构与复习调度扩展到真实规模
4. 长期路线（24 个月阶段/容量）与月度闭环
5. Web/DB 只读投影
```

这与"用户已定 D4"完全兼容：第 1 步不再是"课表排课"，而是 R4 定义的"固定 120 分钟预算 + 四科分配 + 复习裁剪"闭环。

#### 分歧 4：`study` 内核是否应被修改——Claude（新增可选层/不改必填字段/新模块不进包）vs Codex（扩展包/适配层/复用受控流程/SQLite 只做投影）

**裁定：读代码后确认——这是同一强度的方案，只是描述粒度不同，不是"温和 vs 激进"的两个选项。**

逐项对照实测代码：

| 表述 | Claude 说法 | Codex 说法 | 代码事实 |
|---|---|---|---|
| 是否改 `study_workspace/*.py` | 不改 | "扩展包/适配层"（隐含不改内核文件） | 两者都成立：`project_config.py` 的必填字段校验（`project_id/project_name/status/priority/duration`，见 `project_config.py:21-23`）与考研的多科目需求无冲突，因为 `duration.daily_minutes` 只是"日总预算"这一个数字，考研项目一样可以填这个数字（如 120），完全不需要改这个文件。 |
| 新模块放哪 | "新模块不进 `study_workspace` 包" | "扩展包/适配层" | 同一件事：新建仓库顶层 sibling 包（本文档定名 `kaoyan_scheduling`），`study_workspace` 不 import 它，它 import `study_workspace` 的公开函数。 |
| 写入方式 | 未直接展开 | "复用受控流程" | 已用 `cli.py:153-186` 确认 `prepare-generation`/`apply-generation`/`discard-generation` 是唯一的 AI 写入口，两方在 Q3 落地方案里其实都写了"走受控生成"，只是 Claude 放在方案第 4 条、Codex 放在方案第 4 条，用词几乎一致。 |
| SQLite 角色 | "数据库只读投影，不作为唯一真相源" | "SQLite 只做可重建投影" | 完全相同的表述。 |

**结论：这不是真分歧，是同一方案的两份独立复述，可以直接合并为 R3.5 的接口边界。** 唯一值得补一句的精确化：`project.yaml` 的单一 `duration.daily_minutes` 在考研项目里必须保留（否则不满足 `project_config.py` 的校验），它代表"四科合计"，四科怎么切分放在新增的 `subject_budgets.yaml` 里——这是本轮读代码后才能给出的具体落点，两份第一轮回答都没有精确到这一层。

#### 分歧 5：D4 之后，Codex 的"阶段 1 = 一周容量受限排课闭环"是否作废？

**部分作废，替换方案见 R4。** 原方案里"课表冲突检测""临时调课/请假事件"两个组件因 D4 不再需要；但"容量受限""复习优先级裁剪""确定性可重放""同输入同输出"这几条验收标准完全保留，只是把"今天几点到几点有课"换成"今天固定 120 分钟，按科目权重切分"。Claude 第一轮的阶段 1（"排课地基验证"）同样需要按此收窄——它也假设了 `course_schedule.yaml`，在 D4 之后这份文件不需要在第一天出现。

### 对方遗漏的（本轮读代码后新发现，双方第一轮均未提及）

1. **两方都把 `recovery.py`/`recovery_selection.py` 类比为"可复用的间隔复习调度器"，但读完整个模块后这个类比不成立。** `recovery.py` 顶部文档与 `DPLUS_OFFSETS = (1, 3, 7, 14, 30)`（`recovery.py:33`）明确显示：这一整套机制是**项目暂停后恢复（`resume-project`）时"要不要补课"的一次性回顾流程**，锚点是"暂停日期"，不是"某个知识点的到期日"；`recovery_selection.py` 的 `lookback_window` 也是"从暂停日往前最多 30 天"的单次窗口计算，不是持续运行的每日调度器。这意味着 Claude 第一轮 Q3-C 第 3 条"扩展 `recovery_selection.py` 的选择算法"字面上不可行——可以复用的是它的**算法模式**（`time_weight` 确定性排序键、按 `item_type` 固定分钟数的 bin packing、`dedup_key` 去重、超额顺延到 `deferred`），不能"扩展"这个模块本身。R3.2 因此设计为全新模块，只借鉴模式，不改、不导入 `recovery_selection.py` 的函数。
2. **两方都没有检查 `skill_graph.py` 的等级升降门槛，而这个门槛已经替 Q4"自评四档能否驱动提速"给出了现成答案。** 代码显示（`skill_graph.py:151-160`）：升级要求同一节点在 **至少 2 个不同 closure** 都记录 `outcome: success`，且这些证据里 **至少一条 `validation: independent`**；降级默认关闭（`automatic_demotion_enabled` 默认 `False`，见 `project_config.py:92-109`），连续失败只生成 `demotion_candidates` 供人工看，不自动降级。也就是说，"自评能不能加速"这个问题在现有内核哲学下**已经有答案：不能，纯自评永远到不了 `independent`**——这不需要我们重新设计一套哲学，只需要在 R3.4 里让考研系统沿用同一约束（自评最多算 `validation: none`）。
3. **`capability_registry.py` + `capability_proposals.py` 提供了"能力身份注册 + 跨周候选队列 + 人工/策展批准转正"的现成机制**（`capability_registry.py:1-16` 的模块文档明确说这是为了不让"每次 closure 都长出一个新的内容哈希节点"）。这正是考研系统"知识点 ID 需要跨月/跨版本稳定"这个需求的现成解法，但两方第一轮讨论 Q3/Q5 时都没有提到可以复用这一层，都是在自己设计新的知识点身份体系。R3.3/R3.5 会显式接入这两个模块。
4. **`create-project` 的 CLI 参数表已完整核实**（`cli.py:68-79`）：`--daily-minutes` 是单个必填 `int`，`--priority` 是单选 `main/secondary/optional`，没有任何多科目、多预算相关参数。这不是新结论，但把"study 完全没有多科目并行预算"这个此前只从 `project_config.py` 校验逻辑推断的结论，坐实到了创建入口本身——确认新增的多科目切分必须整个放在 CLI 之外的新文件里，不能通过给 `create-project` 加参数解决。

---

## R2. 待用户拍板清单（第二轮剩余项，不重复 D1–D7）

### 阻塞实现

| 问题 | 为什么阻塞 | 建议默认值 | 可选答案 |
|---|---|---|---|
| 每日 120 分钟在数学一/英语一/408/政治（后置）之间的初始权重与轮转规则 | R3.1 `subject_budgets.yaml` 的 `weight` 字段需要具体数字才能跑通 R4 的验证闭环；不给出权重，"今天新学多少分钟"这个问题无法计算。 | 参照需求 §3.2/§11.2 的"重点数学与专业课、英语不断线、政治后置"：`math1=0.40, eng1=0.20, cs408=0.40, politics=0(未激活)`，`rotation_rule: proportional_daily`（按权重每天都切一刀，不做按天轮转）。 | 按上述默认值 / 用户自定权重表 / 按阶段给出不同权重表（`phase_weight_table`，R3.1 已预留字段）。 |
| 是否接受"先做主线跑通、真题随后补" | 直接决定 R4 第一阶段能否被验收为"有意义的一步"，还是被认为"没有真实内容不算数"。 | 接受：R4 的一天原型全部用人工构造的占位数据验证算法骨架，真实资料在 R1 顺序的第 2 步进入。 | 接受 / 不接受（则第一阶段必须等到至少有一份真实资料，时间线相应后移，见 R1-分歧3）。 |
| 摸底测试要不要、规模多大 | D3 已确认用户"非零基础"，但具体缺口在哪必须有客观依据才能校准 `ReviewItem` 和知识结构的起点，否则"非零基础"只是一句定性描述，无法转成 `current_level`/`prerequisite_kp_ids` 之类的具体字段。 | 数学与 408 各出一份 20–30 题、覆盖大一/大二已学模块（高数上下、线代、数据结构、组成原理基础）的分层诊断卷，限时完成，只记录客观对错，不问自评；英语用一份词汇量分级测试（如已有工具，未核实具体选型）。 | 摸底测试定起点（建议）/ 用户自述起点（自评四档直接定级，精度低，见 Q2.1）/ 完全按"零基础"起步（浪费用户已修课程的既有基础，明确不推荐）。 |
| 复习条目（`ReviewItem`）的类型体系用什么分类 | `study` 现有 `recovery_selection.py` 的 `concept/operation/pitfall` 三分类是为"暂停恢复"场景设计的（见 R1-遗漏1），不能直接套用到考研的多学科复习场景；这个分类直接决定 R3.2 的 `item_type` 枚举值和每类的默认耗时，进而决定容量裁剪结果，是本轮读代码后新发现、双方第一轮均未触及的问题。 | `concept`（知识点，默认 10 分钟）/ `formula`（公式记忆，默认 8 分钟）/ `vocab`（单词，默认 1.5 分钟）/ `problem_pattern`（题型套路，默认 15 分钟）/ `error_case`（错题回炉，默认 12 分钟）。 | 采用上述五分类 / 用户合并或拆分类别 / 按科目各自定义类型表（更灵活但复杂度上升，不建议第一版做）。 |
| AI 生成题使用规则是否按 R1-分歧2 的机器可判分界执行 | 决定 R3.3 的 `source_type` 字段与"是否有真题覆盖即自动退场"这条自动化规则能否作为产品决策落地，而不是停留在人工纪律层面。 | 按 R1-分歧2 的规则执行：`ai_generated` 仅用于知识点级巩固练习，且仅在该知识点无 `verified_exam` 覆盖时可选中；一旦有真题覆盖自动 `retired`；两者永不共用 `frequency` 统计和验收展示。 | 按此规则 / 完全不允许 AI 生成题（早期真题稀缺阶段会没有练习素材）/ 放宽为"人工可手动豁免退场"（增加一个需要人管理的例外，不建议）。 |

### 可延后

| 问题 | 为什么可以延后 | 建议默认值 | 可选答案 |
|---|---|---|---|
| 政治启动的具体时点 | 政治权重在 `subject_budgets.yaml` 里默认 `active: false`，不影响前几个阶段的验证；真正要不要开始只需要在某次月度更新时把 `active` 改成 `true` 并回填 `weight`，是纯配置变更，不涉及代码或 schema 改动。 | 由 `activation.trigger: phase_start_date` 触发，占位日期定为目标考试前 12 个月，用户可在任意月度更新时提前或推后覆盖。 | 立即启动 / 考前 18/12/9/6 个月 / 完成某阶段后由用户手动触发。 |
| 第一版 Web 可视化的最小范围 | 两方第一轮和本轮 R3.6 都把 Web 放在最后一个交付阶段，前四个阶段（决策合同、容量闭环、资料台账、知识结构+调度）完全不依赖 Web 是否存在；R4 的一天原型也不含 Web 组件。 | 只读展示：`subject_budgets` 当前权重、今日/本周计划（从 `学习计划.md`/`week_plan.md` 解析）、`ReviewItem` 队列状态、`skill_graph.yaml` 摘要；不做课表编辑（D4 已定不做课表）、不做网页学习记录录入（`学习心得.md` 手写路径已经跑通，没必要重复造一个写入口）。 | 按上述只读范围 / 用户要求补充某个具体展示项 / 推迟到有真实数据后再定范围（不建议——范围不锁定容易在阶段 5 蔓延）。 |
| 目标初试日期的精确值（日/月已由 D2 定为"2028 年 12 月"） | 24 个月总规划只需要月级锚点即可定阶段边界（R1-共识2），日级精度只在冲刺期（考前 2–3 个月）才有意义，且教育部通常在考试当年 9–10 月才发布次年具体日期公告，现在核实不到确切日期属正常，不构成阻塞。 | 暂定 2028 年 12 月最后一个周末（历年惯例，**未核实**），随教育部年度公告更新，冲刺阶段（约 2028 年 10 月）前必须核实确认一次。 | 现在按惯例占位 / 等官方公告后再确认，此前一律用"2028-12（TBD）"标记月级锚点。 |
| 月度自动调整是否需要人工批准 | 不影响前几个阶段的算法验证；`apply-generation` 本身已经是"生成→人工/程序校验→应用"的强制流程，第一版沿用即可，不需要额外拍板。 | 沿用 `study` 现有 `prepare-generation`/`apply-generation` 两步流程，不新增审批层。 | 维持现状 / 未来加一层"月度调整需用户显式确认"的额外开关。 |
| 学习记录保留期限、导出与删除 | 本机单用户、本地文件即状态，理论上可无限期保留，不产生存储或合规压力；只有涉及公网/多用户时才是真问题（已由 D5 排除）。 | 结构化记录长期保留，用户可用现有 `sync`/Git 历史自行导出；不做自动清理。 | 维持默认 / 用户自定保留期并配套一个清理脚本（可延后到有实际存储压力时再做）。 |
| 通知与提醒渠道 | 与排程正确性无关，纯体验层功能。 | 无主动提醒，用户主动查看 Web 只读页面或命令行输出。 | 无提醒 / 未来接入系统通知或邮件。 |
| 既有三个暂停项目（python/ppt/embedded-basics）是否与考研项目共享每日预算 | 三者当前均为 `status: paused`（已实测，`.study/projects.yaml`），不产生实际预算冲突；只有用户主动恢复其中之一时才需要重新做跨项目容量分配，那是另一个独立问题。 | 考研项目独占新分配的每日预算，三个暂停项目维持暂停，互不占用；恢复任一项目时另行触发全局容量重算。 | 维持默认 / 用户现在就要求预留联动机制（不建议——增加当前不需要的复杂度）。 |

---

## R3. 实现契约草案

> 约定：以下所有新增文件均落在 `projects/<project-id>/` 目录内（与现有 `skill_graph.yaml`、
> `capabilities.yaml`、`pending_capability_proposals.yaml` 同级），或落在仓库顶层新建的
> sibling 包 `kaoyan_scheduling/` 内；不修改 `study_workspace/` 包内任何文件。

### R3.1 科目与预算模型

新增文件：`projects/<project-id>/subject_budgets.yaml`（与 `project.yaml` 平级）。

```yaml
schema_version: 1
project_id: kaoyan-2029
total_daily_minutes: 120        # 必须与 project.yaml 的 duration.daily_minutes 相等，由校验函数强制核对
review_reserve_ratio: 0.45      # [0,1]，单日预算中最多可分配给复习裁剪的比例上限（呼应 R1-分歧1 修法）
rotation_rule: proportional_daily   # 目前仅支持一种取值；round_robin_days 等留空占位，第一版不实现
subjects:
  - subject_id: math1            # 稳定 id，小写字母数字，供 ReviewItem/knowledge_point 外键引用
    display_name: 数学一
    weight: 0.40                 # [0,1]；active 子集的 weight 之和必须等于 1（容差 1e-6）
    active: true
    min_daily_minutes: 0         # 可选下限，保证冷门科目不被完全挤出
  - subject_id: eng1
    display_name: 英语一
    weight: 0.20
    active: true
    min_daily_minutes: 15
  - subject_id: cs408
    display_name: 408
    weight: 0.40
    active: true
    min_daily_minutes: 0
  - subject_id: politics
    display_name: 政治
    weight: 0.0                  # 未激活科目 weight 恒为 0，校验函数强制要求
    active: false
    activation:
      trigger: phase_start_date  # 枚举：phase_start_date | manual
      value: "2028-01-01"        # 占位，由 R2"政治启动时点"拍板结果回填
phase_weight_table:              # 可选：按阶段覆盖 subjects[].weight，不填则全程使用 subjects[].weight
  - stage: foundation
    weights: {math1: 0.40, eng1: 0.20, cs408: 0.40, politics: 0.0}
  - stage: improvement
    weights: {math1: 0.35, eng1: 0.20, cs408: 0.35, politics: 0.10}
```

校验规则（新增函数 `kaoyan_scheduling.subject_budgets.load_subject_budgets`，命名与校验风格对齐
`study_workspace.project_config.load_project_config`）：

- `total_daily_minutes` 必须等于对应 `project.yaml` 的 `duration.daily_minutes`（用
  `study_workspace.project_config.load_project_config` 读取后比对，不重复造校验逻辑）；
- `active=true` 的科目 `weight` 之和必须为 1（容差 1e-6），`active=false` 的科目 `weight` 必须为 0；
- `subject_id` 全局唯一，且与 `knowledge_point.subject_id`（R3.3）取值域一致；
- 本文件**不经过** `apply-generation`——它是纯配置文件，由用户或维护者手改，不由 AI 生成，因此不需要
  受控生成流程；但一旦被 `kaoyan_scheduling` 的任何计算读取，必须先跑校验函数，校验失败直接抛异常，
  不允许"忽略非法值继续跑"。

### R3.2 复习单元与调度

**结论先行**：不复用 `recovery_selection.py`（原因见 R1-遗漏1），新建独立模块
`kaoyan_scheduling/review_queue.py`，只借鉴其确定性排序 + 固定分钟数 bin packing 的**模式**。

`ReviewItem` 字段（存于 `projects/<project-id>/review_queue.yaml`，运行时可重建投影，权威来源是
下方"间隔规则"计算逻辑 + 历次复习结果的追加记录，不是凭空编辑）：

```yaml
item_id: str            # sha1(subject_id + knowledge_point_id)[:12]，稳定
subject_id: str          # 外键 -> subject_budgets.subjects[].subject_id
knowledge_point_id: str  # 外键 -> knowledge_point.kp_id（R3.3），必须 status=approved 才能创建
item_type: enum[concept, formula, vocab, problem_pattern, error_case]   # 见 R2 拍板项
granularity: enum[point, cluster]
single_pass_minutes: int    # 来自 item_type 默认表，可被单条覆盖
created_on: date
due_on: date              # 调度器计算写入，AI/人工均不可直接改，只能通过"记录一次复习结果"间接推进
interval_state:
  scheme: fixed_ladder_with_ease   # 见下方取舍结论，第一版只有这一种，不做二选一开关
  ladder_index: int         # 0..4，对应 [1,3,7,15,30] 天
  ease_factor: float        # 默认 2.5，范围 [1.3, 2.8]
  interval_days: int        # 当前实际间隔 = ladder[ladder_index] * (ease_factor/2.5)，四舍五入，clamp[1,90]
last_review:
  date: date | null
  self_report: enum[不会,模糊,基本会,熟练] | null
  objective_result: enum[correct, partial, incorrect] | null
  validation: enum[independent, guided, none]   # 复用 week_evidence.VALID_VALIDATIONS 的同名枚举值
evidence_refs:
  - path: str
    sha256: str
    locator: str           # 复用 recovery_selection._locator_resolves 的解析规则：标题/L<a>-L<b>/原文子串
status: enum[active, suspended, retired]
```

**间隔规则取舍**：不用纯 1/3/7/15/30 固定梯队（对所有内容一刀切，Q2-9 已证明会爆预算），也不用完整
SM-2（需要更多参数且对"考研只剩不到两年、需要收敛到考试日"这个场景过度复杂）。采用"梯队打底 + ease
系数微调"的简化版：

- `ladder = [1, 3, 7, 15, 30]`，`ease_factor` 默认 2.5；
- 每次记录复习结果后：`objective_result == correct` 时 `ease_factor += 0.1`（上限 2.8）且 `ladder_index += 1`
  （封顶 4）；`partial` 时 `ease_factor`、`ladder_index` 均不变；`incorrect` 时 `ease_factor -= 0.3`
  （下限 1.3）且 `ladder_index` 回退到 0；
- `interval_days = round(ladder[ladder_index] * (ease_factor / 2.5))`，`clamp(1, 90)`；
- `self_report` 单独存档，**不参与** `ease_factor`/`ladder_index` 的调整公式——原因见 R3.4（对齐
  `skill_graph.py` "自评不能单独驱动状态变化"的既有原则）；没有 `objective_result` 的复习只更新
  `last_review`，不推进间隔。

**每日复习配额裁剪算法**（`kaoyan_scheduling.review_queue.clip_daily_review`）：

```
输入：due_items（所有 due_on <= today 且 status=="active" 的 ReviewItem 列表）、
      subject_budgets（R3.1，当前 stage 的权重表）、today

1. candidates = due_items 原样（不再过滤，due_on/status 已在输入前保证）
2. 排序键（tuple，升序排列即为优先级从高到低）：
   key(item) = (
       -(today - item.due_on).days,                 # 逾期越久越优先
       -subject_budgets.weight_of(item.subject_id),  # 科目权重越高越优先
       ITEM_TYPE_PRIORITY[item.item_type],           # 固定优先级表，越小越优先，如 formula/concept=0, vocab=1, problem_pattern=2, error_case=3
       item.item_id,                                 # 稳定 tie-break
   )
   ranked = sorted(candidates, key=key)
3. budget = min(
       subject_budgets.total_daily_minutes * subject_budgets.review_reserve_ratio,
       subject_budgets.total_daily_minutes - sum(subject_budgets.min_new_content_minutes for each active subject)
   )
4. boxed = []; deferred = []; remaining = budget
   for item in ranked:
       cost = item.single_pass_minutes
       if cost <= remaining:
           boxed.append(item); remaining -= cost
       else:
           deferred.append(item)     # due_on 保持不变，不显式改写；下次逾期天数自然增大，排序天然靠前
5. 返回 {boxed, deferred, budget, remaining, overload: len(deferred) > 0}
```

关键设计决定：**`deferred` 条目不改写 `due_on`**——用"逾期天数"这个派生量自然实现优先级递增，而不是
显式修改到期日。这对齐 `study` 现有哲学（"只有受控生成/apply 才能改写权威状态，其余一律派生计算"，
见 `schedule.py` 文档"从不重新计算已冻结的 `frozen_period`"的同一思路）；也避免了"顺延写入"本身
需要额外审计的问题。

### R3.3 知识点/题型结构化 schema

存于 `projects/<project-id>/knowledge_points/<kp_id>.yaml`（每条一个文件，便于按路径引用哈希，
沿用 `study` 现有"一份资料一个 manifest 条目"的颗粒度习惯）。

```yaml
kp_id: str                    # 格式 <subject_id>.<module_slug>.<slug>，如 math1.mid-value-theorem.rolle
status: enum[raw, extracted, reviewed, approved, superseded]
superseded_by: str | null     # 仅 status=superseded 时必填，指向新 kp_id
title: str
subject_id: str
module_path: [str]            # 层级路径，如 [高等数学, 中值定理]
difficulty: enum[easy, medium, hard]     # 命题属性；AI 只能出初稿，进入 approved 前须人工/金标复核
prerequisite_kp_ids: [str]
common_errors: [str]
ability_requirement: str
frequency:
  value: int | null           # 只能由确定性脚本写入；AI 写入本字段直接触发 apply-generation 拒绝
  computed_by: str            # 例如 "script:count_kp_occurrences.py@<git_rev>"
  computed_at: datetime | null
  corpus_version: str | null  # 指向被统计的真题库快照版本号
source_refs:
  - path: str
    sha256: str
    locator: str              # 题号/页码/行号
    source_type: enum[verified_exam, ai_generated]   # 见 R1-分歧2 的分界规则
review:
  reviewed_by: enum[human, gold_set_script] | null
  reviewed_at: datetime | null
  accuracy_sample: bool       # 是否属于人工金标集
version: int
created_at: datetime
updated_at: datetime
```

状态机流转：

- `raw -> extracted`：新增 task_type `extract_knowledge_points`，走标准
  `prepare-generation`/`apply-generation`，AI 只产出定性字段（`title`/`module_path`/
  `difficulty` 初稿/`prerequisite_kp_ids`/`common_errors`/`ability_requirement`），`frequency`
  字段禁止出现在 AI 产出内容里；
- `extracted -> reviewed`：人工抽检，或命中金标集合（`review.accuracy_sample=true`）时强制人工
  确认；未抽中金标的条目允许按预设阈值（如 90%）批量放行到 `reviewed`，但阈值本身需要用户/维护者
  拍板（本轮不预设具体数字，留待有真实抽检数据后再定）；
- `reviewed -> approved`：只有 `approved` 的 kp 才能被 `ReviewItem.knowledge_point_id` 引用、才能
  进入 `frequency` 统计的分母；
- `approved -> superseded`：版本更正走"追加新 kp_id + 旧条目标记 superseded_by"，不静默覆盖——直接
  对齐 `project.py::update_project_goal` 里"改前先备份旧版本到 revision 文件"的既有模式。

`frequency.value` 的确定性脚本约束：新增 `kaoyan_scheduling/count_kp_occurrences.py`，输入只能是
`status=approved` 且 `source_refs[].sha256` 全部验证通过的条目集合；`apply-generation` 侧新增一条
校验（仿照 `week_evidence.py` "AI 不能自己填 `status`，只能填 `criteria_assessments`"的模式）：
若某次 pending 生成内容里 `frequency.value` 被写入但找不到匹配的 `computed_by` 脚本审计记录，直接
拒绝应用。

### R3.4 学习记录 → 证据 → 能力的链路

自由格式 `学习心得.md` 已有 `daily_evidence.py` 定义的 `ai_writeback.daily_result` 结构
（`status`/`completed_items`/`incomplete_items`/`actual_outputs`/`evidence`，每条 evidence 是
`{path, sha256, kind}`）。考研系统新增一层派生产物，不改这个既有结构：

新增 task_type `derive_kaoyan_daily_evidence`（与 `derive_week_evidence` 同构），产出
`projects/<project-id>/.../kaoyan_daily_extract.yaml`：

```yaml
review_outcomes:
  - item_id: str                 # 外键 -> ReviewItem.item_id
    self_report: enum[不会,模糊,基本会,熟练]
    objective_result: enum[correct, partial, incorrect] | null
    evidence_refs: [{path, sha256, locator}]
new_kp_evidence:
  - kp_id: str
    outcome: enum[success, failure, observed]     # 复用 week_evidence.VALID_OUTCOMES 原值
    validation: enum[independent, guided, none]   # 复用 week_evidence.VALID_VALIDATIONS 原值
    evidence_refs: [{path, sha256, locator}]
```

**自评四档在链路中的确切位置与权限**（这是本轮读代码后能给出精确答案的问题，见 R1-遗漏2）：

- `self_report` **只**写入 `ReviewItem.last_review.self_report`，**不参与** R3.2 间隔规则的
  `ease_factor`/`ladder_index` 计算，**不参与** `skill_graph.yaml` 的等级升降；
- `self_report` 唯一被允许影响的，是 `clip_daily_review` 排序键的**第五级 tie-break**（当前四级
  完全相同时，`基本会`/`熟练` 的条目略微降低优先级，把预算让给 `不会`/`模糊` 的条目）——即只能在
  "同样紧急程度下调整谁先做"，**不能**跳过间隔、不能改 `due_on`、不能让某条目提前"毕业"；
  能力升级仍然只能通过 `new_kp_evidence` 里 `validation: independent` 的客观证据触发，且沿用
  `skill_graph.py::_apply_outcome` 现有规则（≥2 个不同 closure、至少一条 independent）——**这不是
  我们新加的限制，是直接复用 study 现有内核已经验证过的门槛**，考研系统没有理由做得比现有内核更松。

### R3.5 与 `study` 的接口边界

**改在 `study_workspace` 包内的部分：无。** 不修改该包下任何 `.py` 文件。

**新增文件位置**：

- `projects/<id>/subject_budgets.yaml`、`projects/<id>/knowledge_points/*.yaml`、
  `projects/<id>/review_queue.yaml`——都是 project 目录下的"新增可选文件"，`study_workspace`
  核心模块（`context_builder.py`/`generation.py`/`week_close.py`/`schedule.py` 等）不读取、不
  校验、不感知它们的存在，正如它们今天也不感知 `capabilities.yaml`/`pending_capability_proposals.yaml`
  这类"项目自带但内核不强制"的文件一样；
- 新 sibling 包 `kaoyan_scheduling/`（仓库顶层，与 `study_workspace/` 平级）：`import study_workspace`
  的公开函数（`project_config.load_project_config`、`context_builder.resolve_project_path`、
  `week_evidence.VALID_OUTCOMES`/`VALID_VALIDATIONS` 等常量），反向不被 `study_workspace` import。

**调用的现有 CLI 命令**：

- `create-project`：建标准骨架（`--daily-minutes 120 --priority main --study-days-per-week 7`
  等，具体值由 R2 拍板结果回填）；
- `prepare-generation` / `apply-generation` / `discard-generation`：新增 task_type
  `extract_knowledge_points`、`derive_kaoyan_daily_evidence`，均走同一个 pending → staging →
  apply 流程，同一时间只允许一个 pending 请求（沿用现有约束，不新增并行生成通道）；
- `plan-daily` / `close-week` / `close-due-periods`：不变——日/周计划正文仍由这些命令产出，
  `kaoyan_scheduling` 只负责计算"今天的 `free_review_minutes`/`free_new_content_minutes` 各是
  多少、今天应该出现哪些 `ReviewItem`"，作为**上下文输入**提供给现有的 Context Builder 流程，
  不接管这些命令本身；
- `resource-status` / `project-resource-status` / `add-resource` / `promote-resource`：真题/教辅
  资料登记完全走这条既有资料库路径（D6 已确认），不新建第二套资料库。

**明确禁止事项**：

1. 不得绕过 `apply-generation` 直接写 `学习计划.md`/`week_plan.md`/`skill_graph.yaml`/
   `capabilities.yaml`；
2. 不得让 AI 直接写 `knowledge_point.frequency.value`（见 R3.3，需机器校验拒绝）；
3. 不得让 `kaoyan_scheduling` 直接改写 `skill_graph.yaml`——能力更新必须仍通过
   `skill_graph.update_skill_graph_from_closure` 这个既有入口，`kaoyan_scheduling` 只负责组装
   它需要的 `proposed_updates` 列表参数，函数本身零改动；
4. 不得新增第二个"当前有效周计划"或"当前有效课表"的权威写入口——SQLite/Web（R3.6）只读，或者
   写入独立的 `pending_changes` 队列表，绝不直接覆盖本地文件状态；
5. 不得修改 `project_config.py` 的必填字段校验集合（`project_id`/`project_name`/`status`/
   `priority`/`duration`）——考研项目的 `project.yaml` 必须和 `python`/`ppt` 项目一样合法，
   多科目信息全部放在旁边的新文件里，不塞进 `project.yaml` 本身。

### R3.6 本机 Web 最小范围

- **技术选型**：后端 FastAPI（只读 API），前端任意轻量方案 + ECharts 类图表库，不引入 SPA 框架
  （两方第一轮在这一点上意见一致，本轮维持）；
- **只读 vs 可写边界**：**v1 全部只读**。展示内容：`subject_budgets.yaml` 当前权重、今日/本周
  计划（解析既有 `学习计划.md`/`week_plan.md`）、`review_queue.yaml` 的 boxed/deferred 状态、
  `skill_graph.yaml` 摘要（按科目分组的等级条形图，采纳 Codex/Claude 第一轮一致意见"避免雷达图
  掩盖证据不足"，附样本量提示）。**不做**课表编辑（D4 已定不做课表）、**不做**网页学习记录录入
  （`学习心得.md` 手写路径已跑通，重复造一个写入口只会制造 R1-共识7 警告的双写问题）；
- **SQLite 作为投影的重建方式**：新增 `kaoyan_scheduling/build_projection.py`，每次运行**全量
  清空重建**（不做增量 diff）：依次读取 `projects/<id>/**/*.yaml`、经 `daily_evidence.py` 校验
  过的 `学习心得.md` 派生结果、`skill_graph.yaml`，写入 SQLite 表；脚本本身单向只读源文件，绝不
  写回任何 `study_workspace` 状态文件。全量重建在本项目当前数据规模（单用户、24 个月）下不构成
  性能问题，换来的是"数据库随时可从文件真相源重放，不会漂移"这个更重要的正确性保证。

---

## R4. 第一阶段（一天内可验证）的定义

在 D4（不做课表）前提下，"今天只做一件事"重新定义为：**证明 R3.1（四科预算切分）+ R3.2（复习
容量裁剪算法）这两个纯确定性模块本身是对的**——不接资料、不接课表、不接 Web、不接 AI 生成、不
接真实 `study` 项目。

- **交付物**：
  1. 仓库顶层新增 `kaoyan_scheduling/` 包的最小实现：`subject_budgets.py`（R3.1 的加载与校验函数）、
     `review_queue.py`（R3.2 的 `clip_daily_review` 与相关排序/计算函数）；
  2. 一份手写占位 `subject_budgets.yaml`（用 R2 建议默认值：`math1=0.40, eng1=0.20, cs408=0.40,
     politics=0(未激活)`）；
  3. 15–20 条人工构造的占位 `ReviewItem`（`knowledge_point_id` 全部用 `placeholder.<n>` 这种明显
     不真实的 id，避免被误当成正式知识结构数据）；
  4. 跑 `clip_daily_review`，打印今日 `boxed`/`deferred`/`remaining` 到终端；
  5. 全部产物落在项目仓库外的 `_dev/day1_prototype/` 之类的临时目录，**不** `create-project`、
     **不**写入任何真实 `projects/` 目录，避免污染已注册的 `python`/`ppt`/`embedded-basics` 项目，
     也不产生"事后需要专门清理"的假状态文件。

- **验证命令/验收标准**（用 `unittest`/`pytest` 写 6 条断言，非人工目测）：
  1. `sum(boxed.minutes) + remaining == budget` 且 `budget <= total_daily_minutes`；
  2. 相同输入连续跑两次，输出完全一致（确定性，无隐藏随机性/时间依赖）；
  3. 构造 `active` 科目权重之和为 0.9 的非法输入，`load_subject_budgets` 必须抛出校验异常；
  4. 把 `total_daily_minutes` 从 120 调到 60 后重跑，`deferred` 列表长度必须不减少（容量收紧只能
     让更多条目延后，不能凭空变少）；
  5. 在候选集里加入一条 `due_on` 比其他条目早 15 天的条目，它必须出现在 `boxed`（或即便预算不够也
     必须排在 `deferred` 的最前面）——验证"逾期越久越优先"这条排序规则生效；
  6. 把某科目 `active` 设为 `false`、`weight` 设为 0 后，该科目的条目在裁剪结果里权重排序位置必须
     落到所有 active 科目条目之后（验证未激活科目不会意外抢占预算）。

- **不做哪些事**：不碰真题/资料结构化（R1 顺序第 2 步）；不碰课表/日历（D4 已定第一版不做）；不碰
  Web/数据库（R3.6，最后阶段）；不调用任何 AI 生成（本阶段是纯确定性代码，`prepare-generation`/
  `apply-generation` 流程本阶段不涉及）；不接入真实 `study` 项目注册表。

- **风险**：
  1. 科目权重占位值（R2 待拍板项）后续可能被推翻——但推翻只影响 `subject_budgets.yaml` 里的
     数字，不影响 `clip_daily_review` 算法骨架本身是否正确，两者互不阻塞；
  2. `ReviewItem` 类型体系（R2 待拍板项）后续可能调整分类和默认耗时——同样只影响输入数据，不影响
     排序/裁剪逻辑的正确性验证；
  3. 若这一步都无法在容量收紧时正确产生 `overload` 信号，说明容量裁剪算法本身有缺陷，应该在这里
     停下来修正模型，而不是急着往后接资料结构化或 Web——这与两方第一轮共识的"用可复现证据决定是否
     进入下一阶段，而不是看功能数量"完全一致。

**满足题设要求的核对**：一天内可完成（纯 Python 算法 + 6 条断言测试，无外部依赖）；结果可复现
（第 2 条断言直接验证确定性）；不依赖任何未拍板问题（用占位数字验证算法骨架，占位数字本身不是
结论的一部分）；不产生需要事后丢弃的假数据（全部产物落在项目仓库外的临时目录，不触碰
`projects/` 下任何真实或已注册状态）。
