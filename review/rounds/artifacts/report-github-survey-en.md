# 英文 GitHub 补充检索报告：修正中文 AND 检索的假阴性

调研时间：2026-09-14（Asia/Shanghai）  
工作目录：`C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\ghsurvey_en\`  
上一轮基线：`C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\report-github-survey.md`

## 结论先行

- **相对上轮新增 9 个唯一仓库**。它们均未在上一轮报告中出现，已逐一下载默认分支 ZIP、解包并对选定文件现算 SHA-256。
- **阶段①仍未找到可实际下载、可作为 408 / 数学一 / 英语一“考纲定义源”的结构化考纲数据。** 英文路径补到了结构化相邻物：408 考纲解析/映射脚本、商业课程 408 章节表、商业词书 JSON、英语真题结构化索引，以及多版本真题合并参考实现；但这些都不能等同于可定义考纲的独立结构化考纲源。
- 最容易误判的是 `dengduanglang/408-knowledge`：README 声称生成 `knowledge/syllabus.json`，但**实测公开默认分支归档中既没有该 JSON，也没有脚本要求的考纲 Markdown 输入**，所以本报告只把它列为“参考实现”，不把 README 中的产物数字当作已下载数据。
- 英文/拼音/topic 路径确实改善了上一轮假阴性：找到了 9 个此前漏掉的相关仓库；但对最高优先级的“第二份独立结构化考纲”并未补洞。

## 方法、口径与证据

1. 完整阅读任务书与上一轮报告，先按 repo 全名去重。
2. GitHub REST 仓库搜索执行 27 条查询；原始响应保存在 `ghsurvey_en/q01.json` 至 `q27.json`，汇总在 `search_summary.json`。
3. GitHub 网页/搜索引擎补查了 API 长短语返回 0 的路径；这一步直接发现了 API 未命中的 `dengduanglang/408-knowledge`。
4. 对 9 个候选实际下载默认分支 ZIP；ZIP 字节数与 SHA-256 在 `candidate_metadata.json`，解包文件在 `ghsurvey_en/extracted/`。
5. star、许可、archive、open item 数取自 2026-09-14 的 GitHub REST 元数据；“最近提交”取默认分支 Atom feed 的首条 commit（UTC），不是把仓库 `updated_at` 冒充提交时间。
6. issue 检查口径：open item 为 0 时记“无开放项可判断”；非 0 时抽查最早开放项的评论数与最近更新时间。GitHub 的 `open_issues_count` 包含 PR，报告会明确区分。
7. 数据抽样只输出字段名、条目数与集合重合率；没有抄录考纲正文、题干、例句、教辅讲解或词表释义。
8. 未修改 `F:\workspace\kaoyan-ai-system`，未执行 Git；本轮只用 `py -3.12` 做检索结果解析、JSON 结构统计和哈希/交叉核验。

“实测”表示本轮下载、解析或由 API/Atom 取得；“推断”表示基于结构和说明判断，未运行仓库程序或逐条核对内容。

---

## 一、按阶段分组的新增候选

### 阶段①：知识树、结构化考纲、真题与多源合并（最高优先级）

| repo / URL | 用途 | 可核验事实与活跃度 | 实际下载与抽样（只列字段/计数） | 类别 | 可用性结论 |
|---|---|---|---|---|---|
| `dengduanglang/408-knowledge`<br>https://github.com/dengduanglang/408-knowledge | 408 考纲 Markdown → 树/概念标签 JSON 的构建管线 | **实测** star=7；默认分支最近提交 `f5c0386`，2026-08-05（约 40 天前）；license=NONE；未 archive；open item=0。 | 默认分支 ZIP：98,007 B，SHA-256=`31586ee5492c6ff2a8d72baa343b9c52678c8057740f5689f538da75d4f11e14`。`scripts/build_syllabus.py`：6,791 B，SHA-256=`ac59be7bc5c197a57cd40970c5131bb5c87a86c8cc33893b87b526cbc9bd0124`。输出 schema 字段：顶层 `[meta, tree, concept]`；树节点 `[no, title, subsections]`；子节点 `[title, items]`；条目 `[title, note]`；概念映射 `[required, entry]`。**实际数据条目数=无法统计：`knowledge/syllabus.json` 与输入考纲 Markdown 均不在公开归档。** | **参考实现**，不是公开数据 | 可借鉴解析和标签 schema；不能作为第二份考纲数据源，也不能用 README 的“已生成”数字代替下载证据。 |
| `storm-crypto/kaoyan-2027-coach`<br>https://github.com/storm-crypto/kaoyan-2027-coach | Obsidian 考研教练；含 408 商业课程章节对照、SRS、日/周计划、单 HTML 仪表盘 | **实测** star=5；最近提交 `287046b`，2026-09-09（约 5 天前）；license=NONE；未 archive；open item=0。 | ZIP：419,326 B，SHA-256=`28bafb2799c6a2bc22d1dfb21e7e869f1a5788eb36714d6323820ab8d6782f42`。`references/408-laotang-outline.md`：28,130 B，SHA-256=`94dc509b627d2da613968322a407caf6c8b7c7c19669b379683657f8213ba8af`；表字段 `[节, 课时, 覆盖内容, 真题]`，四列表格行=187（含表头；README 另称 4 模块/32 章/147 节，本轮未把表行强行等同于 147 节）。`scan_due_reviews.py`：6,314 B，SHA-256=`f6d58f06d6439a34f8c09b635b80a6287357dafc42ccb48551f0d7ad7717e070`。 | **数据（课程章节表）+ 参考实现** | 章节表可本地参考，但来源是商业课程大纲，不是国家考试考纲，不能定义 408 考纲；无许可，只宜本地自用。其 SRS/计划/仪表盘可跨阶段参考。 |
| `3056810551/2027-kaoyan-english-redbook-json`<br>https://github.com/3056810551/2027-kaoyan-english-redbook-json | 商业考研英语词书的结构化 JSON | **实测** star=22；最近提交 `f12139c`，2026-08-21（约 24 天前）；GitHub license=MIT；未 archive；open item=0。README 明示数据来自网络流传 PDF，且归原作者/出版社。 | ZIP：8,572,887 B，SHA-256=`9a61b5f745c88613f3786badfea890f5487e78e96b0690da14359e03dcb9afed`。`words.json`：922,612 B，SHA-256=`c2cb5e5ebc42796216490b81d685b5391ea8987917577e8d03fe448fe7a76f6f`；6,550 条，字段 `[index, meaning, page, word]`。`category_page_assign.json`：1,110,284 B，SHA-256=`6898df905bde5f90dcb8a2c410e5d68f11015261f3979a9ffdf3260d1cfb9a45`；6,551 条，同字段。与上轮 NETEM 数据按规范化词形交叉：唯一项 6,547 vs 5,528，交集 5,434；覆盖 NETEM=98.30%，覆盖本库=83.00%，Jaccard=81.83%。 | **数据（高版权风险）+ 提取参考实现** | 交叉结果说明与考研词汇范围高度重合，但它是商业词书而非官方考纲词表，额外项很多；不能定义英语一考纲。MIT 是否覆盖第三方 PDF/派生数据不清楚，传播权记 unknown，仅本地自用。 |
| `Echo1LZJY/echo-kaoyan-english-skill`（原 owner URL 会重定向）<br>https://github.com/Echo1LZJY/echo-kaoyan-english-skill | 英语一/二真题的结构化检索索引、题号映射及 Agent 工作流 | **实测** star=60；最近提交 `48ed691`，2026-07-30（约 46 天前）；license=NONE；未 archive；open item=0。 | ZIP：1,227,197 B，SHA-256=`885f0d038a36c2c6b7d24e8296c81ef030f6646eafd41147d418c993375985a2`。`index.json`：1,367,459 B，SHA-256=`1d23b33377f269d80e6546202452f139683a60e705d1e9bdd18e639ee00acdfd`；顶层字段 `[description, exams, source, version]`，exam=2。`corpus-index.json`：9,923 B，SHA-256=`b43fbf189eb3ade585ae93a70b546b62783ca8cfffdc244c997d68c8b7e207f2`；英语一/二各 17 年。共 34 个 `question-map.json`、34 个 `meta.json`；英语一每年映射 52 条，英语二每年 48 条；meta 字段 `[content_scope, exam, sections, year]`，每年 sections=8；映射项字段 `[file, section]`。 | **数据（真题）+ 参考实现（高风险）** | 是上轮漏掉的结构化真题索引，不是考纲。结构跨年一致，但仓库未给可独立核对的逐题来源链，本轮也未读取/复述题干；准确性未确认。无许可，传播权 unknown，仅本地自用。 |
| `Orinkle/kaoyan-engine`<br>https://github.com/Orinkle/kaoyan-engine | 目录树抽取、真题抽取、映射、待复核与多版本真题合并 | **实测** star=1；最近提交 `5dee4cb`，2026-08-05（约 40 天前）；license=NONE；未 archive；open item=0。 | ZIP：157,850 B，SHA-256=`84b46aad026f31362ed7e6831c3dffc16fa526f415b1a35b50970ea43be62107`。`skills/version_merge.md`：2,764 B，SHA-256=`b886e2d5be1c063103dd6f6f6444bcf883ac2314b0c99e16339f89a2517a1949`。模型字段：`DirectoryNode` 8 个、`QuestionItem` 10 个、`MatchResult` 7 个、`TaskStats` 5 个、`TaskResult` 10 个；核心输出含 `[matched, pending_review, unmatched, confidence, trace]`。 | **参考实现 / 应用骨架** | 这是“同题多版本择优 + 目录映射 + 人工待复核”，不是按独立来源权重合并考纲的实现；可借鉴审计字段和 pending-review 流程，不能解决“缺第二份考纲源”。无许可，不建议直接复制代码。 |

#### 阶段①小结

- **最推荐参考**：`Orinkle/kaoyan-engine` 的审计/待复核 schema，以及 `dengduanglang/408-knowledge` 的考纲解析输出 schema；两者都是方法参考，不是数据源。
- **可本地研究的数据**：红宝书 JSON 和 Echo 真题索引，但前者不是考纲、后者是题库，且传播权均不足以支持再分发。
- **仍缺**：408、数学一、英语一中任一科“可实际下载的独立结构化考纲正文/树”；也没有找到能直接用于考纲的“≥2 独立来源 + 权重 + 冲突审计”实现。
- **英文路径对假阴性的改善**：找到了 5 个阶段①相关新仓库，但对最高优先级数据缺口仍是 **0 份新增合格结构化考纲**。

### 阶段②：间隔重复、长期计划、队列与容量

| repo / URL | 用途 | 可核验事实与活跃度 | 实际下载与抽样 | 类别 | 可用性结论 |
|---|---|---|---|---|---|
| `vellvient/obsidian-learning-engine`<br>https://github.com/vellvient/obsidian-learning-engine | Obsidian + stdlib Python 的知识图谱、FSRS v6、FIRe 隐式复习、daily ranker、本机 cockpit | **实测** star=4；最近提交 `9b4e15e`，2026-07-17（约 59 天前）；MIT；未 archive；API open item=1，但抽样项是无评论 PR #2，未抽到开放 issue。 | ZIP：244,605 B，SHA-256=`644a4e9075484e0c062c2c4d5d44b71079bc9bfec6944ed9471e6e36b66b3c41`。`vault/cockpit_engine.py`：51,220 B，SHA-256=`f8130eb64d3da0a6231ffdd4cbfed7f63b2141939fe545cadb6cd46183a4bc31`；顶层函数=40。`course_map.example.json`：459 B，SHA-256=`ac0a54917e84b2d6a4a51f16d4e2b528aa6098d4937155173934b1b50b3f4fda`；字段 `[course, mappings, new_nodes, rules, version]`，内部计数 mappings=3、new_nodes=1、rules=3。 | **参考实现** | 比上一轮的单纯 FSRS 库更接近“长期计划 + 图谱 + 队列”的整体系统，可用于设计对照；但其 FSRS 是自写移植且 star 很低，本轮未证明与上游算法等价，生产依赖仍优先上一轮的 `py-fsrs`。 |

补充：阶段①的 `storm-crypto/kaoyan-2027-coach` 也实现了 SM-2 风格的 interval/ease 更新、超期降级、到期队列和日/周计划；实测它不是 FSRS，且没有许可。`PyJobShop` 可做容量约束，详见阶段④。

#### 阶段②小结

- **最推荐新增参考**：`vellvient/obsidian-learning-engine`，因为它同时展示“图谱先修关系、SRS、积压队列、今日排序、局部 Web UI”的组合方式。
- **最推荐实际依赖仍不变**：上一轮 `open-spaced-repetition/py-fsrs`；本轮没有找到比它更稳妥的 Python FSRS 库。
- **仍缺**：针对考研多科配额、截止日、积压债务和人工锁定的通用长期计划生成器。

### 阶段③：本机/单文件优先 Web、SQLite 只读展示

| repo / URL | 用途 | 可核验事实与活跃度 | 实际下载与抽样 | 类别 | 可用性结论 |
|---|---|---|---|---|---|
| `coleifer/sqlite-web`<br>https://github.com/coleifer/sqlite-web | Python 本机 SQLite Web 浏览器，支持 `--read-only` | **实测** star=4,159；最近提交 `4b15f12`，2026-09-13（约 1 天前）；MIT；未 archive；open item=0。 | ZIP：723,644 B，SHA-256=`9e485cc604fa15ee1c51d51f21cb41c0785c3e94f1f69ac91c645415e4aa1d71`。`sqlite_web/sqlite_web.py`：70,891 B，SHA-256=`00b4f70eb4278cb8762bb7b050108f8a673f165b4206f6884086fb673d6497a8`；类=3、顶层函数=63，并实测存在 read-only 配置路径。 | **库/轮子** | 是上一轮漏掉的直接 SQLite 浏览方案；必须显式用 `--read-only`，因为默认产品也支持增删改。它是本机服务而非静态单 HTML；若要发布式只读投影，上一轮 Datasette 仍更强。 |

交叉阶段参考：`storm-crypto/kaoyan-2027-coach` 的 `build_dashboard.py` 会生成本地 HTML（55,786 B，SHA-256=`12278bf4c0ac258e6c419f8438ff09d487930fb7f7491188038499af10152d53`）；`vellvient/obsidian-learning-engine` 提供本机 cockpit，但两者都不是“SQLite → 静态站”通用库。

#### 阶段③小结

- **最推荐新增**：`sqlite-web`，用于本机快速审查 SQLite；生产只读投影仍建议比较它与上一轮 Datasette 的默认安全边界。
- **仍缺**：真正“一条命令把 Markdown/YAML 与 SQLite 一起打包成无服务单文件站点”的成熟 Python 方案；本轮只找到了局部拼图。

### 阶段④：课表解析、约束排程、临时覆盖

| repo / URL | 用途 | 可核验事实与活跃度 | 实际下载与抽样 | 类别 | 可用性结论 |
|---|---|---|---|---|---|
| `PyJobShop/PyJobShop`<br>https://github.com/PyJobShop/PyJobShop | Python 约束排程：release/deadline/due date、先后约束、可再生/消耗资源、break、optional task | **实测** star=163；默认分支最近提交 `20d51ab`，2026-06-26（约 80 天前）；MIT；未 archive；open item=35。最早开放 issue #166 有 6 条评论，2026-05-09 仍更新，不能说“无人理”，但积压不小。 | ZIP：444,044 B，SHA-256=`c76b43ce6b41530dba5aeb45505420dbed27d10e1a6f32977f9014fc4244e9bf`。`resource_constrained_project_scheduling.ipynb`：11,490 B，SHA-256=`6dc8467cc9a8359125b840922e979d470b770bbf44df45b47ba73b5e2c46e45a`；字段 `[cells, metadata, nbformat, nbformat_minor]`，20 cells（code=11、markdown=9）。 | **库/轮子** | 是上轮“3 个 star≤1 作业项目”之外的成熟约束排程候选；可建模课时容量、截止日、休息段和可选任务，但它面向生产/项目调度，临时调课语义需项目自己映射，不能直接开箱即用。 |

交叉阶段参考：`fullcalendar/fullcalendar` 的 iCalendar 插件可读取 `.ics` 并显示周视图，详见阶段⑤；实际 `.ics` 解析/生成后端仍优先上一轮 Python `icalendar`。

#### 阶段④小结

- **最推荐新增**：当项目确实需要多资源、前置依赖、break、deadline、optional task 时评估 `PyJobShop`；若只是每天分钟配额，直接引入 CP-SAT 可能过重。
- **仍缺**：不绑定某高校、能处理国内教务导出且明确支持“临时覆盖/恢复原课表”的完整参考实现。

### 阶段⑤：进度、目标差距、周视图与甘特图

| repo / URL | 用途 | 可核验事实与活跃度 | 实际下载与抽样 | 类别 | 可用性结论 |
|---|---|---|---|---|---|
| `fullcalendar/fullcalendar`<br>https://github.com/fullcalendar/fullcalendar | 浏览器日历与周视图；仓库含 iCalendar event source 插件 | **实测** star=20,636；最近提交 `f34b025`，2026-09-05（约 9 天前）；MIT；未 archive；open item=1,130。最早开放 issue #268 有 20 条评论且 2026-08-06 更新，不是无人理，但 backlog 很大。 | ZIP：1,408,640 B，SHA-256=`7587270bd0b0fe50feb13ed971393bc12e912d3b0eb8054dacf99628b411e10e`。`packages/icalendar/src/event-source-def.ts`：3,829 B，SHA-256=`76abc63f2bf7427746cc9bfd32924adfb7a7a0807111a80c7f5435a730b160d5`；仓库 packages 目录=17 个子包。 | **库/轮子** | 周视图比 Plotly 更像真正课表，且可接 `.ics`；但它不是静态图表库，前端集成成本更高。不要把 core 周视图误说成免费资源甘特图；甘特仍可用上一轮 Plotly，或 PyJobShop 的任务甘特绘制。 |

交叉阶段参考：`PyJobShop` 自带 `plot_task_gantt.py`（1,960 B，SHA-256=`18fe6289f92a4b8be9d637d86b22ec0e6fe8c159dfc9ed0ab2b2763bdae76039`）；`storm-crypto/kaoyan-2027-coach` 的单 HTML dashboard 可参考学习进度布局。

#### 阶段⑤小结

- **最推荐新增**：需要交互课表周视图时用 FullCalendar；只要只读统计图/雷达/甘特时，上一轮 Plotly 仍更简单。
- **仍缺**：考研“当前能力 vs 目标要求”的可复用数据模型；图表库并不能替代目标差距的定义与证据。

---

## 二、三条互不推导的判定轴

| repo | ① 权威性：能否定义考纲 | ② 准确性：能否交叉验证 | ③ 可传播性：能否落盘/再分发 |
|---|---|---|---|
| `dengduanglang/408-knowledge` | 非官方；**不能**。且公开归档无实际 syllabus 数据。 | 解析脚本可测试，但没有公开输入/输出可与官方文本算一致率；本轮未确认内容准确性。 | 无 LICENSE；代码/未来派生数据均记 unknown。本地研究可行，不建议再分发。 |
| `storm-crypto/kaoyan-2027-coach` | 商业课程章节表；**不能**定义国家考纲。 | 可核表结构与行数；没有与官方考纲逐条对齐证据。 | 无 LICENSE；unknown，仅本地自用。 |
| `3056810551/2027-kaoyan-english-redbook-json` | 商业词书；**不能**定义英语一考纲。 | 已与 NETEM 集合交叉，交集=5,434、NETEM 覆盖率=98.30%；这只证明高重合，不证明额外项属于考纲。 | 根许可证为 MIT，但 README 明示 PDF/内容权利归第三方；代码可按 MIT，数据/全文再分发权 unknown，仅本地自用。 |
| `Echo1LZJY/echo-kaoyan-english-skill` | 真题资料；不是考纲定义源。 | 34 年卷目录结构高度一致；缺逐题独立来源链，内容准确性暂无法确认。 | 无 LICENSE；数据和代码均 unknown，仅本地自用。 |
| `Orinkle/kaoyan-engine` | 工具轴不适用；它不提供考纲事实。 | schema 有置信度、待复核和 trace，具备交叉验证接口；本轮未运行其 LLM/测试，不能声称结果准确。 | 无 LICENSE；不可据此再分发代码，最多本地参考设计。 |
| `vellvient/obsidian-learning-engine` | 工具轴不适用。 | 有测试和示例，但自写 FSRS v6 是否与上游等价未独立核验。 | MIT，可落盘/修改/再分发代码；仓库明确不带受版权课程数据。 |
| `coleifer/sqlite-web` | 工具轴不适用。 | 实测源码含 read-only 路径；未启动服务做运行测试。 | MIT，可传播代码；用户数据库本身权利另算。 |
| `PyJobShop/PyJobShop` | 工具轴不适用。 | 公开约束模型/测试/示例可复现；本轮只做静态结构核验，未求解实例。 | MIT，可传播代码与示例；输入课表数据权利另算。 |
| `fullcalendar/fullcalendar` | 工具轴不适用。 | iCalendar 插件源码与包结构可核；本轮未构建前端。 | GitHub 元数据为 MIT；可传播开源代码，需另外核对可能的 premium 功能边界。 |

关键纠正：**“非官方”只降低“能否定义考纲”的权威性，不自动推导出“不准确”或“不可本地使用”；同样，MIT 代码许可也不自动覆盖仓库内第三方教材、PDF、题干或派生数据。**

---

## 三、相对上轮的核心增量

英文/拼音/topic 与网页补搜新增的 9 个唯一仓库如下；上一轮报告逐名检索均为未出现：

1. `dengduanglang/408-knowledge`：408 考纲解析与标签 schema；公开产物缺失，故是参考实现。
2. `storm-crypto/kaoyan-2027-coach`：考研专用 SRS、计划、单 HTML 仪表盘和 408 商业课程章节表。
3. `3056810551/2027-kaoyan-english-redbook-json`：6,550 条商业词书 JSON；可与 NETEM 交叉但不是考纲。
4. `Echo1LZJY/echo-kaoyan-english-skill`：英语一/二 2010–2026 年结构化真题索引。
5. `Orinkle/kaoyan-engine`：多版本真题择优、目录映射、置信度和待复核参考实现。
6. `vellvient/obsidian-learning-engine`：FSRS v6 + FIRe + 图谱 + daily ranker + 本机 cockpit 的完整参考系统。
7. `coleifer/sqlite-web`：支持显式只读模式的本机 SQLite Web 浏览器。
8. `PyJobShop/PyJobShop`：有资源容量、break、deadline、optional task 的 Python 约束排程库。
9. `fullcalendar/fullcalendar`：带 iCalendar event source 的交互式周视图前端库。

改善量应分两层报告：

- **仓库发现层**：新增 9 个，说明上一轮中文多词 AND 确有假阴性。
- **阶段①瓶颈层**：新增合格结构化考纲=0；英文路径也没补上第二份独立结构化考纲。

---

## 四、我试过但没找到的路径：具体搜索词与计数

下表为 GitHub REST repository search 的 `total_count`；多词查询按 GitHub 语义近似 AND，广义单词结果含大量噪声。计数是 2026-09-14 快照，不代表代码内容搜索。

| # | 搜索词 | total_count |
|---:|---|---:|
| 01 | `China postgraduate entrance exam syllabus` | 0 |
| 02 | `kaoyan syllabus` | 1 |
| 03 | `"Postgraduate Entrance Examination" China` | 8 |
| 04 | `"Chinese graduate entrance exam" 408` | 0 |
| 05 | `"computer science postgraduate exam" China` | 0 |
| 06 | `NETEM syllabus dataset` | 0 |
| 07 | `"exam syllabus" dataset China` | 0 |
| 08 | `"curriculum knowledge graph" exam` | 0 |
| 09 | `kaoyan dataset` | 2 |
| 10 | `kaoyan json` | 3 |
| 11 | `kaoyan "knowledge graph"` | 0 |
| 12 | `kaoyan ontology` | 0 |
| 13 | `topic:kaoyan` | 81 |
| 14 | `topic:chinese-exam` | 2 |
| 15 | `topic:study-notes kaoyan` | 7 |
| 16 | `topic:spaced-repetition exam-prep` | 43 |
| 17 | `topic:exam-prep kaoyan` | 10 |
| 18 | `考研` | 4,010 |
| 19 | `考纲` | 146 |
| 20 | `大纲` | 1,048 |
| 21 | `408` | 12,821 |
| 22 | `数学一` | 10,149 |
| 23 | `英语一` | 1,785 |
| 24 | `真题` | 2,375 |
| 25 | `kaoyan obsidian` | 12 |
| 26 | `kaoyan anki` | 5 |
| 27 | `kaoyan notion` | 1 |

具体未补上的目标：

- `408 syllabus.json`：网页搜索只找到 `dengduanglang/408-knowledge` 的 README/构建脚本，默认分支没有可下载的 `syllabus.json`。
- 数学一结构化考纲：API 的 `数学一` 单词命中很多，但最高结果多为通用数学、资料合集或笔记；本轮没有确认一个带来源、字段和可下载树数据的数学一考纲仓库。
- 英语一完整结构化考纲：找到了官方词表的相邻商业词书数据和结构化真题索引，但没有找到完整考试要求/题型要求的独立结构化考纲树。
- 多源加权考纲合并：`Orinkle/kaoyan-engine` 是同题多版本择优，不是按来源权重的考纲共识合并；仍未找到现成实现。
- Anki/Obsidian/Notion：分别 5/12/1 个 API 命中；发现了学习系统、词表或徽章项目，但没有藏着合格的第二份结构化考纲。
- 通用临时覆盖课表：找到通用 `.ics`、周视图和约束求解拼图，但没有找到“国内教务导出 + 临时覆盖 + 自动恢复”的通用方案。

一个重要的检索反例：`kaoyan "knowledge graph"` 的 repository API 计数为 0，但网页精确搜索仍找到 `dengduanglang/408-knowledge`。这说明“0”仍只能解释为“该索引/该组合未命中”，不能解释为仓库不存在。

---

## 五、没有把握的地方

1. `dengduanglang/408-knowledge` 的 README 报告了本地生成规模，但公开分支缺输入和产物；无法确认作者本地 `syllabus.json` 的真实条目数、准确性与版权状态。
2. `storm-crypto/kaoyan-2027-coach` 的 408 表来自商业课程大纲；本轮只核结构和行数，未将章节逐项与官方考纲比对。
3. 红宝书 JSON 与 NETEM 的 98.30% 覆盖率只对规范化词形集合成立；它不验证释义、页码、分类或额外词是否准确，也不证明它是官方考纲。
4. Echo 真题库结构跨年一致，但没有可核的逐题来源链；按版权纪律未读取、复述或逐题比较正文，所以内容准确性暂时无法确认。
5. 许可探测有边界：GitHub 的 MIT/NOASSERTION/NONE 是仓库元数据；即使根目录有 MIT，也不能自动授予第三方 PDF、教材、题干和派生数据的再分发权。
6. Atom feed 给的是默认分支首条 commit，`pushed_at` 可能因其他分支/引用更新而更晚；本报告采用 Atom commit 作为“最近提交”，但 GitHub 后续更新会使 star、issue 和日期快照过时。
7. 本轮没有运行这 9 个仓库的应用或测试；“可用”结论只基于静态文件、schema、文档、许可和活跃度，不是运行验收。
8. API 只返回仓库级 name/description/topics/README 匹配，网页搜索也不是完整代码索引；完全不用 kaoyan/考研/科目名命名的私有或冷门仓库仍可能漏掉。

---

## 六、严格区分：我实测到了 / 我推断

### 我实测到了

- 27 条 GitHub repository 查询的原始 JSON 与 total_count。
- 9 个新增仓库的 API 元数据、默认分支 Atom commit、ZIP 字节数/SHA-256、解包文件树。
- 所列选定文件的字节数、SHA-256、JSON 字段名与条目数。
- `dengduanglang/408-knowledge` 公开归档不含 `knowledge/syllabus.json` 和脚本指定的考纲输入。
- 红宝书 JSON 与上轮 NETEM JSON 的集合交集和三项比例。
- Echo 目录中的 34 个 question-map、34 个 meta，以及每年条目数分布。
- `sqlite-web` 源码/README 存在显式 read-only 路径；PyJobShop 示例确有资源约束排程 notebook；FullCalendar 仓库确有 iCalendar event source 包。

### 我推断（未做运行或内容级验证）

- `vellvient/obsidian-learning-engine` 的整体架构可作为项目长期计划设计对照，但其自写 FSRS 与上游等价性未证。
- `PyJobShop` 能映射到学习任务容量/截止日/休息段；具体映射成本和求解规模尚未验证。
- FullCalendar 比 Plotly 更适合交互课表周视图；这属于产品适配判断，不是仓库事实。
- Echo 和红宝书数据可用于本地交叉研究；是否允许任何形式再分发需要权利人/法律判断。

## 附：证据文件

- `ghsurvey_en/search_summary.json`：27 条查询、计数和每条 top repositories。
- `ghsurvey_en/candidate_metadata.json`：9 个仓库元数据、下载 ZIP 哈希、archive/open item 抽样。
- `ghsurvey_en/artifact_analysis.json`：默认分支 commit、选定文件哈希、字段/函数/条目结构。
- `ghsurvey_en/crosscheck_results.json`：红宝书 vs NETEM 集合交叉、Echo 年份分布、408 章节表结构计数。
- `ghsurvey_en/downloads/` 与 `ghsurvey_en/extracted/`：实际下载归档及解包文件，可复核本报告全部 SHA-256。
