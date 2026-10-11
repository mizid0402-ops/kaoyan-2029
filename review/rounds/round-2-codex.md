## R1

### 1. 交叉复核结论

两份第一轮评审的主结论高度一致：需求不是“做不到”，而是必须从结果承诺改造成可验证的本机单用户学习闭环。第二轮真正需要收敛的，不是 A/B/C 路线或部署形态，而是四个工程契约：总预算怎样拆、复习怎样限流、AI 产物怎样获得权限、考研扩展怎样接入 `study` 而不制造第二套状态机。

以下代码事实已经重新从 `F:\workspace\study\study_workspace\` 核验，而不是沿用第一轮印象：

- `project_config.py:9-34` 只验证单项目的 `duration.daily_minutes` 和 `duration.total_weeks`，没有科目权重或复习配额；`project.py:315-393` 的 `create_project()` 也只创建一个 `daily_minutes`。
- `schedule.py` 管的是项目周区间、暂停区间、重放与截止日；不存在课程时隙模型。这一事实已由任务书拍板，本轮不再重复论证。
- `recovery_selection.py:23-27, 230-306, 411-492` 管的是“项目暂停后恢复”的历史回看、`concept/operation/pitfall` 固定分钟装箱，不是持续运行的间隔复习队列。把考研 ReviewItem 直接塞进该模块会混淆两个生命周期。
- `generation.py:506-648, 1966-2008` 确实实行单 pending 槽、Context Builder、staging、校验、`apply_generation()` 与审计；`context_builder.py:40-176` 的任务策略是显式白名单，不会自动读取新增考研目录。
- `week_evidence.py:1-35, 191-225, 298-378` 禁止 AI 直接声明任务整体状态，证据引用必须匹配冻结路径及 SHA-256；`week_close.py:569-655` 在证据就绪后才计算关闭结果并调用 Skill Graph 更新。
- `skill_graph.py:135-181, 335-355` 要求至少两个不同关闭周期的成功，且其中至少一个是 `independent`，才可能升级；单次成功或单纯自评不能提级。
- `week_parsing.py:316-345` 会把日期目录下非临时文件收为 supplementary evidence，因此题目作答记录可以接入现有周证据链，无需让 `学习心得.md` 承担机器事实。
- `workspace_sync.py:33-39, 113-130` 只同步被受控操作登记的路径并排除 `.study/state/**`；“把新目录放进项目里”并不会自动获得可靠同步语义。

### 2. 共识

| # | 双方独立形成的共识 | 第二轮收敛 |
|---|---|---|
| C1 | 380 分只能是用户目标，不能是软件结果承诺。 | 软件验收只覆盖约束满足、证据完整、状态可重放、预测校准；分数估计必须显示样本量与不确定性。 |
| C2 | 远期规划只能粗、近期计划才能细。 | 远期保留阶段、容量、先修关系和硬节点；月滚动、周承诺、日生成，不写死两年日任务。 |
| C3 | 自评四档不足以支撑能力画像或“距 380 分”。 | 自评只作辅助信号；题目来源、限时结果、正确率、提示、错误类型、间隔后复测才是客观证据。 |
| C4 | 固定 1/3/7/15/30 对所有粒度一刀切会产生容量爆炸。 | 每个复习单元必须有预计分钟数；设目标配额和硬上限，超出的任务显式形成 backlog，不能偷借未来时间。 |
| C5 | 资料结构化必须有来源、版本、审核和纠错门禁。 | 采用 `raw → extracted → reviewed → approved → superseded`；频率由确定性脚本统计，LLM 不得报“印象频率”。 |
| C6 | 真题数据存在可得性、准确性和权利边界。 | D6 已决定“公开来源 + 用户合法资料、只结构化不传播原文”；每份资料仍须逐项登记取得方式、许可、哈希和可展示范围。现行著作权法并没有给“考试资料”一个可任意复制传播的通用豁免，具体材料仍须逐项判断。[中国人大网《中华人民共和国著作权法》](https://www.npc.gov.cn/c2/c30834/202011/t20201119_308796.html) |
| C7 | 课程表不能只有周期模板，必须有例外日历。 | D4 已把课表从第一版移出；将来实现时再加入临时调课、考试周、假期、通勤和锁定任务，不让本阶段背负该复杂度。 |
| C8 | 本地文件与数据库不能双主写。 | D5 下由受控文件/审计事件做权威状态；SQLite 是可删除重建的查询投影，Web 首版只读。 |
| C9 | 三条路线中应选 C，且先做薄接入验证。 | 复用 Context Builder、受控生成、周关闭、Skill Graph、资料库、审计和同步；考研领域逻辑在姊妹包，内核只补通用扩展缝。 |
| C10 | 排程和统计核心必须确定性，AI 只产候选语义与解释。 | 预算裁剪、去重、频率计数、状态迁移和哈希校验全部由代码执行；AI 产物先 staging，再经程序/人工门禁。 |

### 3. 真分歧及裁定

#### Df1：复习容量的两套数字是否冲突

- **争议点**：Codex 用 `5 × N × r` 的稳态公式和 87,600 分钟总预算做敏感性分析；Claude 进一步假设 `N≈2.5 个/天`、知识点 `12.5 条/天`，另加 `100 词/天` 的单词通道。
- **Codex 立场**：先说明单位数和单次成本未知，用多组 `N/r` 展示何时必然超载。
- **Claude 立场**：给出知识点总数、有效学习天数、词汇量和单项耗时的点估计，得到约 250 分钟/天的中位复习负载。
- **裁定与依据**：两者**不是公式冲突**，Claude 是给 Codex 同一公式代入了一组更悲观的假设。Claude 的结论更“风险厌恶”，但它所用的 1,200–1,600 个知识点、510 个有效日、0.5–2 分钟/词均未核实，因而不是更可靠的容量估计；尤其单词适合批量 session，不能把“每词分钟数”和知识点任务等价相加。Codex 的敏感性模型在认识论上更保守，也更容易用真实数据证伪。

  此外，两份第一轮的 87,600 分钟已被 D2 改写：从 2026-09-12 到暂以 2028-12-01 表示的“12 月初”共有 811 天，上限为 `811 × 120 = 97,320` 分钟；若以 12 月 10 日计则是 98,400 分钟。它仍只是“不缺勤、不减量”的理论上限，且确切初试日目前未核实。后续不得继续把 730 天写成当前项目总周期。

  可证伪办法不是再猜一个全国知识点总数，而是首两周记录：每日新增 ReviewItem 数 `N`、实际耗时 `r_actual`、到期数、延期数和 backlog 分钟。以 14 天滚动窗口的 P50/P90 代入模拟；只要连续 3 天 P90 到期成本超过复习硬上限，就自动停止新增复习债务并报告容量缺口。

#### Df2：AI 生成题能否用于训练与统计

- **争议点**：Codex 强调其不能进入真题频率和最终验收；Claude 强调基础期可使用，第三、四阶段必须使用真资料。
- **Codex 立场**：AI 题仅可作为经审核的低风险练习草稿，不进入真题频率统计或最终验收。
- **Claude 立场**：基础期可以训练，强化/冲刺期使用真实资料，并强制分开标签。
- **裁定与依据**：两者在“不得冒充真题、不得污染真题统计”上没有冲突；真正需要修正的是不能只按“阶段”授权。题的**来源和用途**才是边界：

  1. `source_kind=ai_generated` 永不进入历年出现频率、考纲覆盖率分母、基线测验、阶段测验、套卷预测或最终验收。
  2. 它可以进入基础巩固练习，但必须有独立求解/答案校验、显著标签、生成模型与 prompt 哈希；未通过校验只能是 `draft`。
  3. AI 题作答最多形成 `validation=guided` 的练习证据，不能形成 `independent` 证据，不能单独触发能力提级或提速。
  4. `official_exam/user_owned_exam/licensed_exam` 且 `status=approved` 的题，才可进入历史频率；只有未见、限时、无提示且与训练集隔离的已批准题，才可进入测量/验收。

#### Df3：§18 应重排，还是只插入“第 0 步索要资料”

- **争议点**：Codex 要先做决策合同和闭环；Claude 要先向用户索要资料，再沿原顺序推进。
- **Codex 立场**：不能让全量资料采购阻塞价值验证，应先建立合同与最小闭环，再做小样本金标和扩展。
- **Claude 立场**：没有真实资料不能结构化，因此在原 §18 前插入索要资料。
- **裁定与依据**：D2、D3、D6 已消除“考试对象未知”和“只能由用户给资料”两个前提，Claude 的第 0 步不再足够，也不应变成等待用户上传整套真题。Codex 的重排方向正确，但第一轮把课程表排程放得过早。最终顺序应为：

  `实现契约与不变量 → 纯函数/fixture 验证 → 资料台账与一小批合法样本 → 结构化/审核/确定性统计 → 真实摸底与首周计划 → 周证据闭环 → 长期滚动路线 → 只读 Web 投影 → 课表协同`。

  这既不“先抓全”，也不在没有真实样本时生成正式能力结论。

#### Df4：是否修改 `study_workspace` 内核

- **争议点**：Claude说“新增可选层、不改必填字段、新模块不进 `study_workspace`”，但又要求“扩展 `recovery_selection.py`”；Codex主张扩展包/适配层并复用受控流程。
- **Codex 立场**：考研领域在边界清晰的扩展包，所有权威写入仍走内核受控流程；SQLite 只是投影。
- **Claude 立场**：原则上考研新模块放姊妹包，但复习容量裁剪进入现有 `recovery_selection.py`。
- **裁定与依据**：两者的大方向相同，但 Claude 的具体步骤自相矛盾。源码显示 `recovery_selection.py` 服务于暂停/恢复，不是常驻间隔复习；直接扩展会把“暂停后回看”和“每天到期复习”耦合成一个状态机。裁定为：

  - 科目、ReviewItem、题型、频率、考研证据适配器、投影与 Web 全部在 `kaoyan_workspace` 姊妹包；
  - `study_workspace` 只增加一个**领域无关**的受控扩展 API，使外部 task type 仍共用单 pending 槽、Context Builder 来源白名单、staging、`apply_generation()`、审计与 sync 登记；
  - 不改既有必填字段，不改 `schedule.py`、`recovery_selection.py`、`week_close.py` 或 `skill_graph.py` 的领域语义。

#### Df5：D4 后第一轮“阶段 1”是否作废

- **争议点**：Codex 的 7 天课程表约束闭环和 Claude 的 `course_schedule.yaml` 小脚本都依赖课表或生产假数据。
- **Codex 立场**：用课程冲突、调课、锁定任务等反例验证一周排程。
- **Claude 立场**：用手写课表和 5 条假复习队列验证 free slots。
- **裁定与依据**：两者的“课表部分”均因 D4 作废；容量、确定性和复习限流问题没有作废。替代阶段应是**无生产写入的合同 + 纯调度核纵向切片**：用永久保留的回归 fixture 验证 YAML schema、ReviewItem 状态迁移和 120 分钟配额裁剪，不创建临时 `study` 项目，不生成要事后删除的计划。详见 R4。

#### Df6：公开资料是否只能等用户提供

- **争议点**：Claude 第一轮称真题原文必须由用户提供；Codex 允许官方链接、元数据和用户合法文件。
- **Codex 立场**：先建资料台账，可登记或下载授权明确的公开资料；公网不传播原题。
- **Claude 立场**：AI 不负责原文获取，用户提供正版材料。
- **裁定与依据**：D6 已明确允许系统联网搜集公开资料，Claude 的绝对禁令不再成立。可执行边界是“发现不等于可复制”：搜索候选元数据可以自动进行；只有 `acquisition=download` 且权利/站点条款允许、来源可追溯时才保存文件；其余只存 URL/元数据，或等用户提供合法副本。任何来源都不能因为“网上搜到”就自动标为 `authoritative` 或允许再分发。

#### Df7：Web 写入是否可以先落 SQLite `pending_changes`

- **争议点**：Claude 提议 Web 写 `pending_changes`，之后由 Agent 消费；Codex 提议 Web 提交命令、SQLite 只做投影。
- **裁定与依据**：如果某个尚未消费的变更只存在 SQLite，它就是不可由文件重建的权威状态，已不再是“纯投影”。D5 首版 Web 应完全只读；将来开放写入时，请求必须先进入受控应用服务，产生文件化、带幂等键的审计事件后才确认成功，SQLite 只缓存其状态。不得存在“数据库已改、受控文件尚未改，但页面称已生效”的窗口。

### 4. Claude 第一轮遗漏或处理不足的风险

1. **把暂停恢复误当持续复习扩展点。** 这是具体代码边界错误，不是措辞问题；会让已有恢复台账、D+ 节点和考研间隔复习共享含义不同的 `due`/`deferred` 状态。
2. **没有处理 D2 对“24 个月”的改写。** 现在目标窗口距评审日约 26.7–26.9 个月；产品名可以保留“24 个月滚动”，但调度必须以目标窗口计算，不能同时保留固定 730 天预算。
3. **`pending_changes` 与“SQLite 可重建”冲突。** Claude识别了双写，却在建议中又让数据库保存不可重建的待处理命令。
4. **未定义真题去重后再计频。** 同一题可能来自不同扫描件、回忆版或教辅转载；若只按标签计数，会把副本数当出现次数。频率必须按稳定 `question_identity` 去重，并公开分母、年份覆盖和数据集指纹。
5. **没有给扩展产物进入现有单 pending 槽的具体接口。** “新增文件 + 独立模块”若不补受控扩展缝，最终只能直接写考研 YAML，绕开第一轮双方都主张复用的生成门禁与同步登记。

## R2

以下只列 D1–D7 之后仍需用户选择的项目；“阻塞实现”是指阻塞对应生产功能，不代表 R4 的无写入工程切片不能开始。

### 1. 阻塞实现

| # | 问题 | 为什么阻塞 | 建议默认值 | 可选答案 |
|---|---|---|---|---|
| B1 | 120 分钟如何在数学一、英语一、408 与复习之间分配和轮转？ | 它决定真实周计划与复习硬上限；没有这项只能验证算法，不能发布生产排程。 | 活跃科目周目标权重：数学一 45%、408 35%、英语一 20%、政治 0%；复习是横切配额，目标占总时长 30%、硬上限 40%。英语每天至少 20 分钟；其余按最近 7 天“目标分钟－实际分钟”的缺口选择，每天最多 3 科。复习耗时计入对应科目权重。 | A：45/35/20；B：50/30/20；C：40/40/20；D：用户自定义。复习上限可选 30%/40%/50%。 |
| B2 | 未完成任务是否形成“时间债务”，次日能否突破 120 分钟？ | 不定义会导致系统悄悄把昨日欠账叠到今天，破坏 D4 的硬预算。 | **不结转分钟，只结转任务。** 次日重新参与排序，仍不得超过 120 分钟；长期超载显示 backlog 并减少新学。 | 不结转分钟；允许周内调剂但单日仍 ≤120；用户手动批准临时超时。 |
| B3 | 是否接受“先跑通主线和资料门禁，真题随后小批补入”？ | 若要求全量真题先到齐，开发第一步会被资料取得和审核无限阻塞；若完全无真题又开始正式能力评估，会产生假结论。 | 接受：先实现契约、调度和受控导入；正式频率、摸底分数、能力提级在首批 `approved` 真实资料到位前保持“证据不足”。 | 接受；必须先有一科小样本；必须先有三科完整资料后才开始真实计划。 |
| B4 | AI 生成题在基础训练中是否启用？ | 决定首批练习供给和证据权限；不能在实现后再决定是否污染统计/画像。 | 启用，但只作显著标记的基础巩固；必须答案校验；不计真题频率、不进保留测验，证据最多为 `guided`，不能单独驱动提级或提速。 | 按默认边界启用；完全禁用；仅用户逐题批准后启用。 |
| B5 | 非零基础怎样摸底、保存到什么粒度？ | D3 只否定“零基础”，不能给出实际起点。若不保留题目级结果，就无法解释跳过了什么、为什么调速。 | 做 3 天轻量摸底，共 360 分钟（每天占用正常 120 分钟），覆盖数学一、英语一、408，约 45–60 个可定位小题；保存题目 ID、得分、耗时、提示、错误类型，不默认保存版权受限题干全文。政治启动时再单独摸底。 | 3 天题目级；1 天筛查后按弱项追加；只保存科目汇总（则关闭知识点级画像）；暂不摸底并从课程已修范围开始。 |
| B6 | 首批能力画像是否允许由 AI 题或已见题驱动加速？ | 这是证据权限，不是 UI 偏好；若允许，会把熟悉度误当迁移能力。 | 不允许。已见题/AI题可触发“继续练/提前复习”，只有已批准、无提示、限时的独立题证据才能支持跳级或加速。 | 采用默认；允许已见题但降低权重；完全人工决定加速。 |

### 2. 可延后

| # | 问题 | 为什么不阻塞当前切片 | 建议默认值 | 可选答案 |
|---|---|---|---|---|
| L1 | 第一版 Web 展示哪些页面，何时允许写入？ | R4 和首个 CLI 闭环不依赖 Web。 | 首版只读：今日/本周计划、复习 backlog、证据化能力条形图、资料状态、投影健康状态；不做课表编辑、记录录入或 AI 触发按钮。 | 只读 5 页；只做今日页；增加受控“记录学习结果”写入；完整交互后台。 |
| L2 | 政治何时启动？ | 当前基础期可把政治设为 `deferred`、权重 0，不影响前三科模型。 | 以 `months_before_exam: 6` 作为**可配置策略默认**，约在 2028-06 启动；这不是官方规律或成功保证，届时结合大纲、基线和前三科负荷确认。 | 立即；考前 12/9/6 个月；达到前三科里程碑后；用户指定日期。 |
| L3 | 分科目标分如何组成 380？ | 能力估计尚无基线，过早精确分配是假精确。 | 暂以数学 120、英语 75、408 115、政治 70 作展示性目标，不驱动自动决策；摸底和目标院校信息稳定后再确认。 | 沿用默认；用户指定；基线后由系统给候选、用户批准。 |
| L4 | 2028 年确切初试日公布前怎样倒排？ | D2 已给出年份和月份，schema 可表达窗口，不需猜具体官方日期。 | `2028-12-01..2028-12-10`、`date_status: provisional`，容量检查按窗口首日保守倒排；官方日期确认后以审计事件更新。 | 按最早日；按窗口中点；用户指定暂定日。 |
| L5 | 课表协同恢复开发时采用何种输入？ | D4 明确后置，当前不应为未知教务格式写 parser。 | 先支持版本化 YAML 周模板 + 日期例外；真实教务导出作为后续适配器。 | YAML；CSV；教务导出；网页手填；图片/OCR。 |
| L6 | 本地记录保留和删除策略？ | D5 降低了公网隐私风险，且可先保持追加审计。 | 结构化记录长期保留；原始自由文本不出本机；删除走带原因的软删除/墓碑事件；允许导出。 | 长期；24 个月；用户手动归档；硬删除（不推荐）。 |
| L7 | 是否需要手机/PWA、通知和日历订阅？ | 都不影响权威状态、证据和调度正确性。 | 响应式本机 Web；不做原生 App；提醒先用站内待办。 | 无；PWA；系统通知；日历订阅；邮件。 |
| L8 | 既有三个暂停项目将来恢复时怎样共享时间？ | 当前均为 paused，D4 的 120 分钟可先只计算考研项目。 | 任一旧项目恢复时强制重新确认全局日预算，不让多个项目各自宣称拥有同一 120 分钟。 | 考研独占；共享全局预算；用户为每项目另加时间。 |

## R3

本节的字段和文件均为**实现草案**；上文带源码行号的内容才是已确认现状。草案遵循一个核心不变量：`study` 权威文件/审计事件是写入真相源，考研姊妹包负责领域计算，SQLite 与 Web 不获得绕过门禁的写权限。

### 1. 文件与包边界

建议代码放在当前项目，权威学习数据仍落在 `study` 的受管项目：

```text
F:\workspace\kaoyan-ai-system\
├─ kaoyan_workspace\
│  ├─ cli.py
│  ├─ models.py
│  ├─ budget.py
│  ├─ review_scheduler.py
│  ├─ knowledge.py
│  ├─ frequency.py
│  ├─ evidence_adapter.py
│  ├─ generation_extension.py
│  ├─ projection.py
│  └─ web.py
├─ contracts\
│  ├─ kaoyan_config.schema.json
│  ├─ review_item.schema.json
│  ├─ knowledge_item.schema.json
│  └─ study_attempt.schema.json
└─ tests\

F:\workspace\study\projects\kaoyan-2029\
├─ project.yaml                         # study 既有配置；daily_minutes=120
├─ capabilities.yaml                    # study 既有能力注册表
├─ skill_graph.yaml                     # study 唯一能力状态，只能由周关闭更新
└─ 考研\
   ├─ config.yaml                       # 四科与预算合同
   ├─ knowledge\items\<item_id>.yaml   # 题目/知识结论及审核状态
   ├─ statistics\frequency-v1.yaml      # 确定性可重建统计
   ├─ review\items\<review_id>.yaml     # 当前 ReviewItem
   └─ audit\...                         # 姊妹包的确定性配置/导入审计
```

`project.yaml.duration.daily_minutes=120` 继续表示 `study` 看见的项目总上限；四科内部份额只存在 `考研/config.yaml`。不得为四科创建四个互相争抢预算的 `study` 项目，否则周关闭、总预算和跨科复习会被割裂。

### 2. 科目与预算模型

`projects/kaoyan-2029/考研/config.yaml` 草案：

```yaml
schema_version: 1
project_id: kaoyan-2029
exam:
  cohort: 2029                       # int, 2027..2100
  target_window:
    start: 2028-12-01                # ISO date
    end: 2028-12-10                  # ISO date, >= start
    status: provisional              # provisional | official
  score_goal: 380                    # int, 0..500；愿景，不是软件验收值

budget:
  total_daily_minutes: 120           # int, 1..1440；必须等于 project.yaml 的 daily_minutes
  accounting_window_days: 7          # int, 1..28；默认 7
  min_session_minutes: 20            # int, 5..120；默认 20
  max_subjects_per_day: 3            # int, 1..4；默认 3
  minute_rollover: none              # none | within_week_manual；默认 none
  review:
    target_ratio: 0.30               # number, 0..0.60；默认 0.30
    hard_max_ratio: 0.40             # number, target_ratio..0.70；默认 0.40
    urgent_overdue_days: 3            # int, 1..30；默认 3
    urgent_defer_count: 2             # int, 1..20；默认 2

subjects:
  - id: math-1                       # enum: math-1 | english-1 | cs-408 | politics
    name: 数学一
    status: active                   # active | deferred | completed
    target_share: 0.45               # number, 0..1
    daily_min_minutes: 0             # int, 0..120；默认 0
    max_gap_days: 1                  # int, 0..14；0 表示不设；默认 0
    tie_break_rank: 10               # int, 0..1000；越小越优先
  - id: english-1
    name: 英语一
    status: active
    target_share: 0.20
    daily_min_minutes: 20
    max_gap_days: 1
    tie_break_rank: 30
  - id: cs-408
    name: 408 统考
    status: active
    target_share: 0.35
    daily_min_minutes: 0
    max_gap_days: 1
    tie_break_rank: 20
  - id: politics
    name: 政治
    status: deferred
    target_share: 0.0
    daily_min_minutes: 0
    max_gap_days: 0
    tie_break_rank: 40
    activation:
      mode: months_before_exam       # manual_date | months_before_exam | milestone
      value: 6

policy:
  unapproved_knowledge_schedulable: false
  ai_generated_max_validation: guided
  self_rating_can_accelerate: false
  frequency_allowed_source_kinds:
    - official_exam
    - user_owned_exam
    - licensed_exam
```

程序必须强制以下不变量：

1. `subjects[].id` 唯一；所有 `active` 科目的 `target_share` 之和为 `1.0±1e-9`，`deferred/completed` 必须为 0。
2. `total_daily_minutes` 与 `project.yaml.duration.daily_minutes` 不一致时拒绝排程，不取较大值或悄悄覆盖。
3. `review.target_ratio ≤ review.hard_max_ratio`；任何实际计划总分钟数都不得超过 120。
4. ReviewItem 花费同时计入“复习配额”和所属科目的 7 日实际分钟，避免同一分钟在两个预算里各算一次却不约束总量。
5. 科目份额是 7 日目标，不强迫每天机械按 45/35/20 切三段。日选择优先补足 `target_minutes - actual_minutes`，这样允许数学/408 做连续大块，同时保证英语不断线。
6. `minute_rollover=none` 时，未完成只结转任务，不增加次日容量。
7. 目标考试窗口转为 official 前，页面必须显示“暂定”，不得伪装成已确认官方日期。

### 3. ReviewItem 与间隔规则

`projects/kaoyan-2029/考研/review/items/<review_id>.yaml`：

```yaml
schema_version: 1
review_id: rv_math_limit_0001          # string, 项目内唯一、稳定
revision: 3                            # int >= 1；乐观并发控制
subject_id: math-1
knowledge_point_id: kp_math_limit_001  # 必须引用 approved 知识点
title: 等价无穷小替换条件
granularity: concept                   # concept | procedure | question_pattern |
                                       # error_pattern | vocabulary_batch
state: queued                          # queued | scheduled | suspended | retired
estimated_minutes: 8                   # int, 1..30；超 30 必须先拆分
introduced_on: 2026-09-20              # ISO date
due_date: 2026-09-23                   # ISO date；未选中时不得偷偷改晚
last_reviewed_on: 2026-09-21           # ISO date | null
schedule:
  mode: fixed_bootstrap                # fixed_bootstrap | sm2_lite
  phase: 2                             # int, 0..5
  interval_days: 2                     # int, 1..180
  ease_factor: 2.50                    # number, 1.30..3.00
  repetitions: 1                       # int >= 0
  lapses: 0                            # int >= 0
defer_count: 0                         # int >= 0
last_quality: 4                        # int 0..5 | null；由客观作答映射
source_evidence:
  - path: projects/kaoyan-2029/第一个月/第一周/2026-09-20/attempts/att-001.yaml
    sha256: 64位小写十六进制
    locator:
      kind: yaml_pointer               # yaml_pointer | text_lines | pdf_page |
                                       # pdf_page_bbox | image_region | question_id
      value: /results/0
created_at: 2026-09-20T20:00:00+08:00
updated_at: 2026-09-21T20:00:00+08:00
last_request_id: UUID
```

#### 3.1 固定阶梯与简化 SM-2 的取舍

不能一开始就让低质量、自评驱动的数据调 ease，也不能永远为每项机械安排五次。采用确定性混合规则：

1. 新项进入 `fixed_bootstrap`，成功后的相邻间隔为 `[1, 2, 4, 8, 15]` 天，对应累计约第 1/3/7/15/30 天。
2. `quality >= 3` 才推进一个 phase；`quality < 3` 不推进，`lapses += 1`，次日重试。
3. 完成 phase 5 后切换 `sm2_lite`。SM-2 原始思路使用 0–5 质量分、最低 ease 1.3，并按 ease 放大后续间隔；这里保留其可解释公式，但使用本系统的 bootstrap 起点。[SuperMemo 对 SM-2 的原始说明](https://www-beta.supermemo.com/en/articles/history)
4. 更新公式：`EF' = clamp(1.30, 3.00, EF + 0.1 - (5-q)*(0.08+(5-q)*0.02))`。
5. `q >= 3`：`next_interval = clamp(7, 180, ceil(interval_days * EF'))`；`q < 3`：`next_interval=1`，保留更新后的 EF。所有随机抖动首版关闭，保证同输入同输出。
6. 质量分由程序根据正确性、提示和限时表现映射：5=无提示且在时限内完全正确；4=无提示正确但超时；3=一次提示后正确；2=错误但完成纠正复述；1=错误且纠正不完整；0=未作答/完全无法回忆。自评不得直接写 `last_quality`。

该规则不是声称“优于所有算法”，而是先提供可回放、可审计的基线；有足够真实复习数据后，再用遗忘率和实际分钟回测是否更换算法。

#### 3.2 每日复习配额裁剪

精确排序键（升序元组；负号代表原值越大越靠前）：

```text
(
  -is_urgent,
  -overdue_days,
  -defer_count,
  -lapses,
  -subject_deficit_ratio,
  due_date,
  tie_break_rank,
  review_id
)
```

其中 `is_urgent = overdue_days >= urgent_overdue_days or defer_count >= urgent_defer_count`；`subject_deficit_ratio=(target_minutes-actual_minutes)/max(target_minutes,1)`，只从最近 7 天已验证记录计算。不得让 LLM 生成优先级数字。

```python
def select_reviews(day, total_minutes, policy, items, seven_day_usage):
    target = floor(total_minutes * policy.target_ratio)
    hard_cap = floor(total_minutes * policy.hard_max_ratio)
    eligible = [
        x for x in items
        if x.state == "queued" and x.due_date <= day
    ]
    ranked = sorted(eligible, key=deterministic_sort_key)

    selected = []
    used = 0

    # 第一遍：所有到期项都竞争目标配额；装不下不拆、不改 due_date。
    for item in ranked:
        if used + item.estimated_minutes <= target:
            selected.append(item)
            used += item.estimated_minutes

    # 第二遍：只有紧急且尚未入选的项可以借到 hard_cap。
    for item in ranked:
        if item in selected or not is_urgent(item, day, policy):
            continue
        if used + item.estimated_minutes <= hard_cap:
            selected.append(item)
            used += item.estimated_minutes

    deferred = [x for x in ranked if x not in selected]
    for item in deferred:
        item.defer_count += 1       # due_date 原样保留，形成可见逾期

    return {
        "selected": selected,
        "deferred": deferred,
        "review_minutes": used,
        "new_learning_minutes": total_minutes - used,
        "backlog_minutes": sum(x.estimated_minutes for x in deferred),
        "over_capacity": bool(deferred),
    }
```

若单项大于硬上限，导入时标为 `requires_split` 并拒绝进入队列；不得靠跳过大项永久饥饿。实际完成耗时只影响后续 `estimated_minutes` 的 P50/P90 校准，不回写过去计划。

### 4. 知识点/题型结构化 schema

每个 `knowledge/items/<item_id>.yaml` 表示一个可审核对象；题目正文可以不落库，只保存合法文件引用与结构化结论：

```yaml
schema_version: 1
item_id: qi_2024_408_01_03
revision: 2
status: reviewed                     # raw | extracted | reviewed | approved | superseded
kind: exam_question                  # exam_question | syllabus_clause | knowledge_point |
                                     # question_pattern | error_pattern
subject_id: cs-408
question_identity:
  exam_family: national-postgraduate
  exam_year: 2024
  paper_code: "408"
  question_no: "1.3"
  subquestion_no: null
  content_fingerprint: sha256:...
source:
  resource_id: 408-2024-user-copy
  source_kind: user_owned_exam        # official_exam | user_owned_exam | licensed_exam |
                                      # ai_generated | teacher_created | derived_variant
  path: projects/kaoyan-2029/第一个月/项目资料/下载资料/408-2024.pdf
  sha256: 64位小写十六进制
  locator:
    kind: pdf_page_bbox
    page: 4                           # 1-based
    bbox: [0.08, 0.12, 0.92, 0.38]   # 归一化 x0,y0,x1,y1；均在 0..1
  rights:
    acquisition: user_provided        # public_download | user_provided | licensed
    license: unknown                  # 字符串；unknown 不等于可传播
    may_store_original: true
    may_display_original: false
    source_url: null
claims:
  - claim_id: clm_001
    claim_type: knowledge_point       # knowledge_point | question_pattern | difficulty |
                                      # prerequisite | common_error | capability
    value: kp_ds_graph_shortest_path
    producer: ai                      # ai | deterministic | human
    confidence: 0.86                  # 0..1；仅用于复核排序，不赋予权限
    evidence_refs:
      - path: projects/kaoyan-2029/第一个月/项目资料/下载资料/408-2024.pdf
        sha256: 64位小写十六进制
        locator: {kind: pdf_page_bbox, page: 4, bbox: [0.08, 0.12, 0.92, 0.38]}
extraction:
  request_id: UUID
  model: model-id
  prompt_path: .study/prompts/extensions/kaoyan/extract_question.md
  prompt_sha256: 64位小写十六进制
  extracted_at: 2026-09-20T20:00:00+08:00
review:
  decision: changes_requested         # approve | changes_requested
  reviewer: user
  reviewed_at: 2026-09-21T20:00:00+08:00
  notes: "题型标签过宽"
approval: null                         # approved 时必须为 mapping
supersedes: qi_2024_408_01_03@1
superseded_by: null
created_at: 2026-09-20T20:00:00+08:00
updated_at: 2026-09-21T20:00:00+08:00
```

状态权限与迁移：

| 迁移 | 发起者 | 必须条件 |
|---|---|---|
| `∅ → raw` | 确定性导入器 | 资源已登记、路径存在、SHA-256 匹配、locator 合法；不产生 AI claims。 |
| `raw → extracted` | AI，经受控生成 | `request_id/prompt_sha256/model` 完整；所有 claim 有来源引用；只能写 staging。 |
| `extracted → reviewed` | 人工或独立审查器 | 写 review 决定与理由；审查器不能直接批准自己的生成。 |
| `reviewed → approved` | 用户显式命令 | `decision=approve`、schema/引用/能力 ID/去重检查全通过。 |
| `reviewed|approved → superseded` | 确定性替换命令 | 新 revision 已成功落盘且双向填写 `supersedes/superseded_by`；旧件不可删除。 |

`changes_requested` 不做原地回退覆盖：生成新 revision，旧 revision 进入 `superseded`。`confidence` 再高也不能跳过 reviewed/approved。

#### 4.1 确定性频率统计

`kaoyan_workspace/frequency.py` 只读取 `status=approved` 的 `exam_question`：

1. 只接受 `policy.frequency_allowed_source_kinds`；排除 `ai_generated/teacher_created/derived_variant`。
2. 先按 `(exam_family, exam_year, paper_code, question_no, subquestion_no)` 去重；若身份冲突，再用 `content_fingerprint` 报错，不擅自合并。
3. 一个批准题可计入多个已批准知识点，但每个 `(question_identity, knowledge_point_id)` 最多计一次。
4. 输出每个知识点的 `question_count`、`paper_count`、`exam_years`、`total_eligible_questions`、`total_eligible_papers`，同时输出由排序后的 `path:sha256:revision` 计算的 `dataset_fingerprint`。
5. `frequency-v1.yaml` 标记 `generated_by: kaoyan_workspace.frequency:v1`；任何 `producer=ai` 的 frequency claim 直接拒绝。

建议命令：

```powershell
py -m kaoyan_workspace frequency rebuild --study-root F:\workspace\study --project kaoyan-2029
py -m kaoyan_workspace frequency verify  --study-root F:\workspace\study --project kaoyan-2029
```

相同输入必须得到相同 `dataset_fingerprint` 和统计正文；时间戳不得参与统计哈希。

### 5. 学习记录 → 证据 → 能力

#### 5.1 题目级作答记录

自由格式 `学习心得.md` 保留给用户，不强迫改成表单；机器事实另写到同一日期目录的 `attempts/<attempt_id>.yaml`，因此会被现有 `week_parsing._supplementary_files()` 收入冻结证据：

```yaml
schema_version: 1
attempt_id: att_20260920_001
project_id: kaoyan-2029
task_id: kaoyan-2029.task.xxxxx
subject_id: cs-408
knowledge_point_ids: [kp_ds_graph_shortest_path]
question_item_id: qi_2024_408_01_03
question_revision: 2
source_kind: user_owned_exam
started_at: 2026-09-20T19:00:00+08:00
elapsed_seconds: 480
time_limit_seconds: 600
score: 8
max_score: 10
correctness: partial                  # correct | partial | incorrect | ungraded
hint_count: 0
error_codes: [boundary_condition]
self_rating: basic                    # unknown | vague | basic | fluent
answer_artifacts:
  - path: projects/kaoyan-2029/.../2026-09-20/answers/att_001.md
    sha256: 64位小写十六进制
verification:
  mode: answer_key                    # answer_key | human | deterministic_test | none
  verifier_ref:
    path: projects/kaoyan-2029/.../answer-key.yaml
    sha256: 64位小写十六进制
    locator: {kind: yaml_pointer, value: /answers/qi_2024_408_01_03}
recorded_at: 2026-09-20T20:00:00+08:00
```

#### 5.2 权限链

```text
学习心得.md（用户叙述，候选来源）
      + attempt YAML / 答案产物（机器可验事实）
      ↓ close-week 第一次调用
week_close.yaml 冻结 source_files + sha256 + task IDs + 验收标准
      ↓ derive_week_evidence，经同一 pending/staging/apply-generation
week_evidence_ai.yaml（逐标准 satisfied/not_satisfied/blocked；能力观察）
      ↓ close-week 第二次调用，确定性消费
任务状态 / carry-over / 已注册 capability updates
      ↓ update_skill_graph_from_closure
skill_graph.yaml（至少两周成功且至少一次 independent 才可升级）
```

`学习心得.md` 非空、自述“会了”、自评 fluent 都不是完成证据；它们只能帮助 AI 找待核验陈述。`attempt` 引用的文件缺失、哈希不符、题目未 approved 或 `verification.mode=none` 时，不能生成 `independent success`。

#### 5.3 自评四档的精确权限

| 自评用途 | 允许 | 禁止 |
|---|---|---|
| 复习排序 | `unknown/vague` 可把到期项风险调高或触发额外诊断；与客观结果矛盾时显示 mismatch。 | `basic/fluent` 不能单独推迟 due date、跳过复习或提高 quality。 |
| 任务完成 | 可作为反思文本的一部分。 | 不能把验收标准标为 satisfied，不能把任务写成 completed。 |
| 能力画像 | 可显示“主观信心”独立维度。 | 不能直接改变 Skill Graph level，不能生成 `independent`。 |
| 提速 | 只能提出候选，等待客观测验。 | **不能单独驱动提速。** 至少需要已批准题上的无提示客观证据；能力提级仍服从现有跨周门槛。 |

### 6. 与 `study` 的接口边界

#### 6.1 允许改在 `study_workspace` 包内的内容

只增加领域无关的公共扩展缝：

```text
study_workspace/extension_api.py       # 新增：注册外部 task、目标根、validator 与显式 context sources
study_workspace/generation.py          # 小改：把已注册扩展任务接入现有 prepare/apply，不另建 pending
study_workspace/context_builder.py     # 小改：校验扩展显式来源在 workspace 内，不递归扫描
study_workspace/__init__.py            # 导出稳定 facade
tests/test_extension_generation.py     # 验证单槽、路径逃逸、哈希、apply、审计与 sync 登记
```

建议公共接口：

```python
@dataclass(frozen=True)
class ExtensionGenerationSpec:
    extension_id: str
    task_type: str
    target_root: str
    validator_version: str
    validate_content: Callable[[Path, dict, str], None]

def register_generation_extension(spec: ExtensionGenerationSpec) -> None: ...

def prepare_extension_generation(
    root: Path,
    *,
    extension_id: str,
    task_type: str,
    project_id: str,
    target: Path,
    prompt_path: str,
    context_sources: list[dict[str, str]],
    schema_version: int,
) -> dict: ...

def apply_extension_generation(root: Path, content_file: Path) -> dict:
    # 内部必须调用 generation.apply_generation；不得复制 apply 逻辑
    ...
```

扩展 request 必须额外冻结 `extension_id/task_type/schema_version/validator_version`；目标只能在 `projects/<project>/考研/`，context source 必须在 workspace 内且列入请求。未注册 task、validator 版本变化、路径逃逸或已有别的 pending 一律拒绝。`kaoyan_workspace` CLI 启动时注册自己的 validator，再调用上述 facade；普通 `study_workspace` 核心不 import 考研包。

不得把考研字段加成 `project.yaml` 新必填项，也不得修改旧项目的配置。更不能修改 `recovery_selection.py` 来实现日常间隔复习。

#### 6.2 姊妹包负责的内容

`kaoyan_workspace` 独占：四科配置验证、预算缺口、ReviewItem 与状态迁移、固定/SM-2 混合调度、知识结构化 validator、去重/频率、attempt 写入、周证据适配、SQLite 重建和 Web。它可以调用 `study` 的公共 facade，不得 import `_private_function` 或直接拼 `.study` 内部状态。

#### 6.3 复用的现有 CLI

| 用途 | 现有命令 |
|---|---|
| 建考研项目与总预算 | `py -m study_workspace create-project ... --daily-minutes 120` |
| 月计划/修订 | `plan-monthly`、`adjust-monthly-plan` |
| 周计划 | `prepare-generation --task-type generate_week_plan`，随后 `apply-generation` |
| 日计划 | `plan-daily`，随后 `apply-generation`；不直接写 `学习计划.md` |
| 生成失败处理 | `discard-generation`；不得覆盖 pending 文件 |
| 周证据闭环 | `close-week`（冻结）→ `derive_week_evidence` → `apply-generation` → `close-week`（关闭） |
| 到期批处理 | `close-due-periods` |
| 资料 | `resource-status`、`add-resource`、`fetch-resource`、`promote-resource` |
| 能力候选治理 | `list-capability-proposals`、`resolve-capability-proposal` |
| 同步 | `sync --status`、`sync --nightly`；扩展写入也必须先被受控操作登记 |

考研扩展的 `extract_knowledge`、`approve_knowledge`、`record_attempt`、`schedule_reviews`、`projection rebuild` 使用 `py -m kaoyan_workspace ...`，但凡 AI 生成内容，最终 apply 必须委托 `study_workspace.generation.apply_generation()`，共享同一 pending 和审计。

#### 6.4 明确禁止

- 不得直接写 `skill_graph.yaml`；只允许周关闭调用 `update_skill_graph_from_closure()`。
- 不得把 `学习心得.md` 或自评直接转成 completed/success。
- 不得直接写正式日/周/月计划，不得绕过 `apply-generation`。
- 不得为考研扩展另建第二个 pending 槽、第二套周关闭或第二套 Git 同步。
- 不得让 Context Builder 递归扫描整个 `考研/`、整个资料库或其他项目；每次只读 request 中列出的来源。
- 不得让 SQLite 成为第二写源；不得用 SQL 直接改计划、复习状态、能力或审核状态。
- 不得把 AI 题标为真题、authoritative、independent，或计入真题频率/保留测验。
- 不得将权利状态 `unknown` 解释为可公开展示；D5 虽是本机，也仍不改变数据来源的事实属性。
- 不得将当前 `recovery.py/recovery_selection.py` 的暂停恢复节点与 ReviewItem 合表。

### 7. 本机 Web 最小范围与 SQLite 投影

技术选型：FastAPI + Jinja2 + HTMX + Chart.js，Uvicorn 只监听 `127.0.0.1`。首版避免 SPA、账户系统、WebSocket 和公网部署。

#### 7.1 只读边界

首版仅提供 GET：

```text
/                       今日摘要与证据状态
/week                   本周任务、科目分钟、未安排项
/reviews                今日到期、逾期、backlog 分钟
/capabilities           等级、样本量、最近证据、不确定性
/sources                资料权利/审核/哈希状态
/system/projection      投影版本、源指纹、最后重建错误
/api/v1/...             对应只读 JSON
```

不提供课表编辑、记录录入、批准知识条目、应用计划、关闭周期或触发 AI 的 POST。未来若开放写操作，HTTP handler 只能调用应用服务命令并返回 request/audit ID，不能执行领域表 `INSERT/UPDATE`。

#### 7.2 投影文件和表

SQLite 放在 `F:\workspace\study\.study\state\kaoyan\projection.sqlite3`，属于可删除的本机派生状态，正好落在现有 sync 排除目录。至少包含：

```sql
projection_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
subjects(subject_id TEXT PRIMARY KEY, status TEXT, target_share REAL, actual_7d_minutes INTEGER);
plan_tasks(task_id TEXT PRIMARY KEY, plan_path TEXT, subject_id TEXT, task_date TEXT, status TEXT, minutes INTEGER);
review_queue(review_id TEXT PRIMARY KEY, subject_id TEXT, due_date TEXT, estimated_minutes INTEGER, defer_count INTEGER, state TEXT);
attempts(attempt_id TEXT PRIMARY KEY, task_id TEXT, question_item_id TEXT, correctness TEXT, elapsed_seconds INTEGER, source_hash TEXT);
capabilities(capability_id TEXT PRIMARY KEY, level INTEGER, sample_count INTEGER, last_evidence_at TEXT, uncertainty TEXT);
knowledge_frequency(knowledge_point_id TEXT PRIMARY KEY, question_count INTEGER, paper_count INTEGER, dataset_fingerprint TEXT);
sources(resource_id TEXT PRIMARY KEY, source_kind TEXT, rights_status TEXT, sha256 TEXT, review_status TEXT);
```

#### 7.3 可重建协议

```powershell
py -m kaoyan_workspace projection rebuild --study-root F:\workspace\study --project kaoyan-2029
py -m kaoyan_workspace projection verify  --study-root F:\workspace\study --project kaoyan-2029
py -m kaoyan_workspace web --host 127.0.0.1 --port 8765
```

重建必须：

1. 只读受控项目文件、关闭文件、Skill Graph、资料 manifest 和已批准考研 schema；
2. 对排序后的 `path + sha256` 计算 `source_fingerprint`；
3. 在同目录新建临时数据库，单事务装载，执行 foreign-key/integrity 检查；
4. 成功后 `os.replace` 原投影，失败则保留上一有效投影并记录错误；
5. Web 以 SQLite URI 只读模式打开；页面展示的 `source_fingerprint` 必须与当前源扫描一致，否则显示 stale；
6. 删除 SQLite 后重建结果除时间戳外一致，且不需要数据库里的任何业务输入。

## R4

### 一天内只做一件事：完成“考研领域合同 + 纯复习裁剪核”的无写入纵向切片

这不是建立临时考研项目，也不是生成一份看似真实的周计划。它产出后续直接复用的 schema、纯函数和回归测试，不依赖 B1–B6 的最终选择；测试 fixture 是长期保留的规范样例，不进入生产学习数据。

#### 交付物

1. `contracts/kaoyan_config.schema.json` 与 `contracts/review_item.schema.json`，落实 R3 的字段、范围和跨字段不变量。
2. `kaoyan_workspace/models.py`：加载/验证 config 与 ReviewItem；报错包含 JSON Pointer/YAML 路径。
3. `kaoyan_workspace/review_scheduler.py`：实现 R3 的确定性排序、目标配额、urgent 借用硬上限和 backlog 输出；函数不读写文件、不调用 AI。
4. `tests/test_contracts.py`、`tests/test_review_scheduler.py` 和永久 fixture：正常、权重不闭合、总预算不一致、逾期、同优先级稳定排序、单项过大、超载六类。
5. 一个 `preflight` 命令只读取显式 fixture/config 并把结果输出到 stdout；不创建项目、不登记 pending、不写 SQLite。

#### 最小验证命令与验收标准

只跑直接相关的最小范围，不跑全套或冒烟测试：

```powershell
py -m unittest -v tests.test_contracts tests.test_review_scheduler
py -m kaoyan_workspace preflight --config tests/fixtures/config-minimal.yaml --items tests/fixtures/reviews-overloaded.yaml --date 2026-09-12
```

验收标准：

- 合法配置通过；活跃权重不等于 1、review 比例倒置、单项超过 30 分钟、与外层 120 分钟不一致均被拒绝。
- 任意输出 `review_minutes ≤ floor(120×hard_max_ratio)`，`review_minutes + new_learning_minutes = 120`。
- 未选中项的 `due_date` 不变且 `defer_count+1`；输出明确 `backlog_minutes/over_capacity`。
- 相同输入重复 100 次，selected 顺序与结果摘要逐字节一致。
- 测试结束后 `F:\workspace\study` 无任何新增/修改文件；测试 fixture 留在测试目录，后续作为回归资产，不需要丢弃。

#### 明确不做

- 不创建 `kaoyan-2029` 生产项目，不改 `study_workspace` 内核，不准备或应用 generation。
- 不搜集/下载真题，不虚构知识点、能力、学习记录或正式日周计划。
- 不做课程表、Web、SQLite、Skill Graph 更新、长期阶段规划或分数预测。
- 不先实现 SM-2 的长期效果优化；只实现可回放的合同和裁剪基线。

#### 风险

- 这一天只能证明合同自洽、算法确定且不超预算，不能证明默认 45/35/20 最适合用户，也不能证明复习策略有效。
- JSON Schema 难以表达“活跃权重之和为 1”等全部跨字段约束，因此 `models.py` 必须有二次语义校验；只过 schema 不算通过。
- 纯函数通过不等于已接入 `study`。下一阶段仍须先实现并验证 R3 的通用受控扩展 API，再允许任何考研 AI 产物进入正式状态。
