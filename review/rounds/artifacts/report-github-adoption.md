# GitHub 现有项目可用性评估表（第三轮：逐条实测复核 + 阶段可用性结论）

调研时间：2026-09-15（Asia/Shanghai）| 工作目录：`%TEMP%\kaoyan-probe\ghsurvey3\`
基线：前两轮报告 `review/rounds/artifacts/report-github-survey.md`（中文，2026-09-14）与
`report-github-survey-en.md`（英文补充，2026-09-14）。本轮**未修改** `F:\workspace\kaoyan-ai-system`
下任何文件，**未执行 git**。

**术语约定**（与前两轮一致）：**「我实测到了」**＝本轮用 API/网页拉取了 repo 元数据、下载了文件、
现算了 SHA-256、解析了源码/JSON 结构；**「我推断」**＝基于实测到的结构做的工程判断，未实际跑通集成。

## 0. 本轮方法说明（与前两轮不同）

- 本轮任务是**复核**，不是重新地毯式搜索。核验对象＝前两轮报告里与③④⑤（本轮高优先）
  和②叠加候选相关的全部 repo，共 **19 个**：
  ③ `simonw/datasette`、`simonw/sqlite-utils`、`rclement/datasette-dashboards`、
  `coleifer/sqlite-web`、`mkdocs/mkdocs`、`squidfunk/mkdocs-material`；
  ④ `collective/icalendar`、`ics-py/ics-py`、`PyJobShop/PyJobShop`、`fullcalendar/fullcalendar`；
  ⑤ `plotly/plotly.py`、`plotly/dash`、`streamlit/streamlit`（`fullcalendar` 与④共用）；
  ② `open-spaced-repetition/py-fsrs`、`fsrs4anki`、`awesome-fsrs`、`srs-benchmark`、
  `alankan886/SuperMemo2`、`vellvient/obsidian-learning-engine`。
- **GitHub REST `core` 与 `code_search` 配额本轮一开始就被前两轮当天累计的调用打满**
  （`GET /rate_limit` 实测 `core: remaining=0/60`），改用任务书允许的降级路径：
  `curl.exe -s -L https://github.com/<owner>/<repo>`（页面内嵌 JSON 取 `stargazerCount` /
  `spdxId` / `isArchived` / `defaultBranch`）＋ `https://github.com/<owner>/<repo>/commits/<branch>.atom`
  （取真实最近一次 commit 时间，不用 `pushed_at`/`updated_at` 冒充）。`search` 配额剩余 10 次，
  留给本轮的中英双语补充抽查。
- 文件哈希用 `codeload.github.com/<owner>/<repo>/zip/refs/heads/<branch>` 现下现算 SHA-256（`py -3.12`
  `hashlib.sha256`），不依赖 API。
- 本轮完整原始产物：`repo_meta.json`（API 尝试记录，含限流报错原文）、`web_meta.tsv`（19 repo 的
  star/license/archived/branch/最近提交）、`zip_*.zip` + `zip_hashes.json`（9 个 repo 的现算哈希）、
  `search_spotcheck.json` + `study_dashboard.json`（中英双语补充检索）、`octo1.html`/`octo2.html`/
  `zip_octopus-kaoyan-workbench.zip`（本轮新发现候选的核验产物），均保存在
  `%TEMP%\kaoyan-probe\ghsurvey3\`，可复核。

---

## 一、复核结果表（19 条候选，逐条实测）

| repo | 阶段/能力 | star（本轮/上轮） | 最近提交（本轮实测，UTC） | 许可证 | 实测下载与哈希 | 三轴结论 | 与自研冲突 | 建议 | 改动量级 |
|---|---|---|---|---|---|---|---|---|---|
| [simonw/datasette](https://github.com/simonw/datasette) | ③ SQLite→只读 Web 投影 | 11,465 / 11,460 | 2026-09-11 | Apache-2.0（`LICENSE` 首行 `Apache License` 实测确认） | **首次现算**：默认分支 ZIP，1,231,807 B，SHA-256=`b21c6c2d95f55f6f5cd0a6f422f054e83bbe9adb7199a3ff95a17f51699df568` | ①能直接从 SQLite 文件生成只读浏览/API 界面，命中"SQLite 可重建、Web 只读投影"的架构决策；②能直接用（`datasette mydb.sqlite`），要做"考研专用视图"需写 `metadata.yml`/canned queries，改动量级=小～中；③MIT/Apache-2.0 代码可落盘可再分发，本机单用户使用无限制 | 无 `weight` 概念，无冲突 | **引入** | 小～中（装包+写投影配置，不改动现有排序核/契约） |
| [simonw/sqlite-utils](https://github.com/simonw/sqlite-utils) | ③ 从源文件批量重建 SQLite | 2,169 / 2,168 | 2026-09-02 | Apache-2.0（`LICENSE` 首行确认） | **首次现算**：ZIP 362,612 B，SHA-256=`72cfe46b40bc2e75ef3efe374103516e407b32273099789237f41adffa0202e2` | ①配合 datasette 做"从 YAML/契约源重建 SQLite"的构建步骤；②CLI+库都可直接用；③同上 | 无冲突 | **引入** | 小（构建脚本里加一步） |
| [rclement/datasette-dashboards](https://github.com/rclement/datasette-dashboards) | ③⑤ Datasette 插件仪表盘 | 178 / 178（不变） | 2026-09-10 | Apache-2.0 | 本轮仅复核元数据，未重新下载（非本轮三大件，优先级让位于 plotly） | ①可在 datasette 之上做交互仪表盘；②插件化直接用，但需学其 YAML 配置 DSL；③同上 | 无冲突 | 参考（若 plotly 静态图不够用再启用） | 中 |
| [coleifer/sqlite-web](https://github.com/coleifer/sqlite-web) | ③ 本机 SQLite 浏览器（支持 `--read-only`） | 4,159 / 4,159（不变） | 2026-09-13 | MIT | **复核**：ZIP 723,644 B，SHA-256=`9e485cc604fa15ee1c51d51f21cb41c0785c3e94f1f69ac91c645415e4aa1d71` —— **与上轮（2026-09-14）现算值逐字节相同**，确认过去 24 小时仓库无变化、无供应链篡改 | ①本机快速审查 SQLite，须显式传 `--read-only`（默认支持增删改）；②直接用；③MIT 可落盘可再分发 | 无冲突 | 参考（临时排查用；正式只读投影仍优先 datasette，因为 sqlite-web 默认可写，风险面更大） | 小，但需要人工记得加 `--read-only` 参数，属于"配置项而非架构保证"，风险需项目自己接受 |
| [mkdocs/mkdocs](https://github.com/mkdocs/mkdocs) | ③（备选）Markdown→静态站 | 22,434 / 22,433 | 2025-10-20（约 11 个月未提交，**本轮复核确认仍未更新**） | BSD-2-Clause | 未重新下载（非本轮候选） | ①不直接读 SQLite，需求匹配度低于 datasette；②要额外写"SQLite→Markdown"的导出层才能用；③同上 | 无冲突 | **不用**（datasette 更贴合"SQLite 只读投影"这一具体架构决策，且 mkdocs 近一年未提交） | 中～大（多一层导出逻辑） |
| [squidfunk/mkdocs-material](https://github.com/squidfunk/mkdocs-material) | ③（备选）mkdocs 主题 | 27,439 / 27,427 | 2026-08-30 | MIT | 未重新下载 | 同上，仅在选择 mkdocs 路线时才有意义 | 无冲突 | 不用（同上原因） | — |
| [collective/icalendar](https://github.com/collective/icalendar) | ④ `.ics` 解析/生成 | 1,171 / 1,171（不变） | **2026-09-14**（本轮核验当天前一天，非常活跃） | 仓库字段 NOASSERTION，**本轮重新下载并读取** `LICENSE.rst`：确认为 BSD-2-Clause 风格文本（Copyright Plone Foundation 2012-2013，含 redistribution 条款），与上轮结论一致 | **复核+首次现算**：ZIP 874,284 B，SHA-256=`a1ceb36f31f2bb0782cdb3b0f720b0633d348f63e2d5fd699e14fb671fca4e3c` | ①直接满足④的 `.ics` 解析/生成需求；②直接用，`Calendar`/`Event` 对象读写课表文件；③代码可落盘可再分发（BSD-2-Clause） | 无冲突 | **引入** | 小 |
| [ics-py/ics-py](https://github.com/ics-py/ics-py) | ④（备选） `.ics` 解析/生成 | 721 / 721（不变） | **本轮发现重大修正：实际最近一次 commit 是 2024-12-06**（`README.rst` typo 修复，#426），**并非上轮报告写的 "2026-04-15"** —— 该日期实测是 `v0.8.0-dev1` **release/tag 发布时间**，不是 commit 时间，上轮把两者搞混了 | 仓库字段 NOASSERTION，`LICENSE.rst` 为 Apache-2.0（上轮已读取，本轮未重复下载复核内容，仅信任上轮的文本级结论） | 未重新下载 ZIP（本轮判定优先级让位于更活跃的 icalendar） | ①同 icalendar，API 更 Pythonic；②直接用；③同 icalendar | 无冲突 | **不用**（改用 icalendar：真实代码提交已停滞近 21 个月，"最近有 release"是假活跃信号，不能证明库仍在积极维护） | 小（若已用可暂不迁移，但不建议新引入） |
| [PyJobShop/PyJobShop](https://github.com/PyJobShop/PyJobShop) | ④ 约束排程（资源容量/截止日/休息段/可选任务） | 163 / 163（不变） | 2026-06-26（约 80 天未更新，**本轮复核确认仍是这个日期，无新提交**） | MIT | **复核**：ZIP 444,044 B，SHA-256=`c76b43ce6b41530dba5aeb45505420dbed27d10e1a6f32977f9014fc4244e9bf` —— **与上轮逐字节相同**，确认无变化 | ①能建模"多资源+截止日+休息段+可选任务"的排程，理论上能表达"临时覆盖/调课"；②**只能当参考/重度改造**——本轮实测其 `pyproject.toml` 依赖 `ortools>=9.12.4544`（Google OR-Tools，大体积原生二进制求解器包）、`matplotlib`、`fjsplib`、`psplib`；③MIT 代码本身可落盘可再分发，但 `ortools` 是独立重依赖，许可证另算（Apache-2.0，自行核实） | **本轮实测**：`pyjobshop` 源码里 "weight" 出现 200+ 次（`Model.py`、`ProblemData.py`、`Objective.py` 等），是**第 4 种"weight"语义**——目标函数各项的权重系数（如迟到惩罚权重），与项目现有 3 种 `weight`（学科时间预算/题目置信度/来源支持度）语义完全不同；但因为它被封装在 `pyjobshop.*` 自己的命名空间里（不会污染项目自己的模块），**不构成 Python 标识符层面的直接冲突**，只是"团队交流时提到 weight 要说清楚指哪一种"的文档纪律问题 | 参考（暂不引入） | **大**——多一个重量级原生依赖（ortools），且项目目前的排程需求是"120 分钟/天固定预算+临时覆盖"，比 PyJobShop 面向的通用车间排程问题简单得多，用它是"杀鸡用牛刀"；仅当未来真出现多资源/多约束的复杂排程需求才建议评估 |
| [fullcalendar/fullcalendar](https://github.com/fullcalendar/fullcalendar) | ⑤（④交叉）交互式周视图 + iCalendar 插件 | 20,636 / 20,636（不变） | 2026-09-05 | MIT | **复核**：ZIP 1,408,640 B，SHA-256=`7587270bd0b0fe50feb13ed971393bc12e912d3b0eb8054dacf99628b411e10e` —— **与上轮逐字节相同** | ①能做课表周视图并接 `.ics`；②**改数据模型适配**——它是浏览器端 JS 库，要接入需要一个前端页面加载它；③MIT 可用 | 无 `weight` 概念 | **不建议引入**（**必须说明**：这是纯前端 JS 库，需要浏览器里跑 JS，虽然不强制要求 Node **构建链**（可以用 `<script>` CDN 直接引入，不必 webpack/vite），但项目当前③阶段定位是"本机只读投影"，若用 datasette/plotly 静态渲染路线，引入一整个前端周视图组件库属于额外复杂度；如果确实要做可交互课表，这是唯一现成选项，但要接受"多一层前端资产管理"的代价） | 中（能不装 Node 构建链用，但要维护一份前端 HTML/JS 资产） |
| [plotly/plotly.py](https://github.com/plotly/plotly.py) | ⑤ 雷达图/甘特图/柱状图 | 18,782 / 18,780 | **2026-09-14**（非常活跃） | MIT（`LICENSE.txt` 首行 `MIT License` 实测确认） | **首次现算**：ZIP 12,131,874 B，SHA-256=`9a271ccc36a55dd189e5096f920e940bedc7281bbe60967a1c9810eadea32e6e`。**抽样核对**（只列条目数，不抄正文）：源码中与 `scatterpolar`（雷达图）相关文件 **59 个**（`plotly/graph_objs/_scatterpolar.py` 等）；`plotly/express/_chart_types.py` 中确认存在 `def timeline(data_frame, x_start, x_end, y, ...)` 函数（甘特图，Python 侧，非前端库） | ①雷达图（能力画像）、甘特图（`px.timeline`，课表周视图）、柱状图（政治）三种都能在同一个纯 Python 库里找到，不需要额外找组件；②直接用，`import plotly.express as px`；③MIT 可落盘可再分发 | 无 `weight` 概念 | **引入** | 小（生成静态 HTML/PNG 图嵌入只读投影即可，不需要跑一个前端应用） |
| [plotly/dash](https://github.com/plotly/dash) | ⑤（备选）交互仪表盘框架 | 24,408 / 24,405 | 2026-09-11（`dev` 分支） | MIT | 未重新下载（非本轮采纳对象） | ①可做交互仪表盘；②要跑一个 Dash 服务进程；③MIT | 无冲突 | 不用（与"只读静态投影"定位冲突，Dash 是运行时 Web 应用框架） | 中～大 |
| [streamlit/streamlit](https://github.com/streamlit/streamlit) | ⑤（备选）快速数据应用 | 45,756 / 45,740 | **2026-09-15**（核验当天，非常活跃） | Apache-2.0 | 未重新下载 | ①可配合 plotly 做交互看板；②要跑一个常驻服务进程（`streamlit run`）；③Apache-2.0 | 无冲突 | 不用（同 Dash，运行时服务形态与"本机只读、单文件优先"的既定架构有张力；若项目以后决定接受一个本机常驻服务，可重新评估） | 中～大 |
| [open-spaced-repetition/py-fsrs](https://github.com/open-spaced-repetition/py-fsrs) | ②（叠加候选）FSRS 调度算法 | 488 / 486 | 2026-08-09 | MIT（`LICENSE` 文件确认存在） | **首次现算**：ZIP 207,168 B，SHA-256=`9e8b03bee013a24c1690fc66087ffb046884db0910913d02ca9e94e7fb33431b`。**抽样核对**（结构，见下方"叠加 vs 替换"详述）：`fsrs/card.py` 的 `Card` dataclass 字段 **7 个**（`card_id, state, step, stability, difficulty, due, last_review`）；`fsrs/scheduler.py` 的 `Scheduler` 类方法 **26 个**，含 `review_card`/`reschedule_card`/`get_card_retrievability` | 见下方阶段②小节的"叠加 vs 替换"分析 | **本轮实测**：`Scheduler` docstring 原文将其内部参数数组 `DEFAULT_PARAMETERS` 明确称为 "the model weights of the FSRS scheduler"——即 FSRS 术语体系里存在**第 4 种"weight"语义**（算法参数向量，社区惯称 `w`），但该库的 Python 属性名是 `parameters` 不是 `weight`，**不构成标识符层面冲突**，只是概念层面要注意区分 | **叠加评估通过，不建议替换**（见下） | 中（新增 3 个持久化字段 + 1 次调度调用 + 扩展现有全序键比较器；不改动、不替换现有 8 键排序核） |
| [open-spaced-repetition/fsrs4anki](https://github.com/open-spaced-repetition/fsrs4anki) | ②（参考）Anki 插件形态的 FSRS | 4,067 / 4,064 | 2026-08-14 | MIT | 未重新下载 | Anki 插件形态，不可直接用；算法思路参考价值高 | 无直接冲突（不采用其代码） | 参考，不引入 | — |
| [open-spaced-repetition/awesome-fsrs](https://github.com/open-spaced-repetition/awesome-fsrs) | ②（参考索引） | 687 / 685 | 2026-09-11 | CC0-1.0 | 未重新下载 | 生态索引，非代码 | 无 | 参考 | — |
| [open-spaced-repetition/srs-benchmark](https://github.com/open-spaced-repetition/srs-benchmark) | ②（参考）算法效果基准 | 263 / 263（不变） | 2026-09-12 | **本轮复核确认仍无 LICENSE**（页面无 `licenseInfo` 字段，与上轮 "NONE" 结论一致） | 未重新下载 | 方法论可参考，代码因无许可证不建议直接复用 | 无 | 参考，不引入 | — |
| [alankan886/SuperMemo2](https://github.com/alankan886/SuperMemo2) | ②（参考）SM-2 算法 | 121 / 121（不变） | 2024-06-23（**本轮复核确认 `archived=true` 未变**） | MIT | 未重新下载 | 已停止维护（archived），仅供算法思路参考 | 无 | **不用** | — |
| [vellvient/obsidian-learning-engine](https://github.com/vellvient/obsidian-learning-engine) | ②（参考）图谱+FSRS+队列+本机 cockpit 整体系统 | 4 / 4（不变） | 2026-07-17 | MIT | **复核**：ZIP 244,605 B，SHA-256=`644a4e9075484e0c062c2c4d5d44b71079bc9bfec6944ed9471e6e36b66b3c41` —— **与上轮逐字节相同** | 架构对照价值高，star 极低（4），其自写 FSRS v6 与官方实现等价性未证 | 未逐一核对其 weight 用法 | 参考，不引入代码 | — |

---

## 二、本轮新发现的候选（中英双语补充抽查，非完整重搜）

`search` API 配额本轮仅剩 10 次，用于对③④⑤方向做小规模中英文补抽（不是重复前两轮的地毯式检索）：

| 查询词 | 语种 | `total_count` | 结果 |
|---|---|---|---|
| `课表` | 中文单词 | 4,056 | 全部噪声（NLP 工具、书单、系统学习资料汇总等），0 条与③④⑤工具需求相关 |
| `倒计时` | 中文单词 | 3,200 | 全部噪声，0 条相关 |
| `topic:study-planner` | 英文 topic | 285 | 全是通用学习计划类应用（网络安全学习计划、AI 学习伴侣等），0 条是可直接复用的"轮子" |
| `topic:study-dashboard` | 英文 topic | 9 | **发现 `zhangyushaonao/octopus-kaoyan-workbench`（2 ⭐）与其姊妹仓库 `octopus-kaogong-workbench`（92 ⭐，"考公"版）**，见下方详述 |
| `sqlite readonly viewer` | 英文 | 1 | `jacobecontreras/readOnlySqlViewer`，0 ⭐，价值极低，不采纳 |
| `timetable solver ics python` | 英文 | 0 | 无命中 |

### 新发现候选：`zhangyushaonao/octopus-kaoyan-workbench` / `octopus-kaogong-workbench`

- **实测**：两仓库均 `defaultBranch=main`、`isArchived=false`、`spdxId=MIT`；
  `octopus-kaoyan-workbench` star=2；`octopus-kaogong-workbench` star=92，最近提交（atom 实测）
  2026-08-01T18:25:49Z。
- **实测下载**：`octopus-kaoyan-workbench` 默认分支 ZIP，2,311,375 B，
  SHA-256=`16a7edf1e4d26395b181505915e1f6def185211625c77981ed4f7c7bb23ca459`。
- **实测结构**：文件清单为 `app.js` / `index.html` / `server.mjs` / `styles.css` / `package.json`
  （纯前端 + 一个零依赖 Node 静态服务器，`package.json` 的 `dependencies` 字段**实测为空**，
  `scripts.start` = `node server.mjs`）；README 标题层级（只列结构，未抄正文）：
  `# Octopus Kaoyan Workbench` 下含定位、学科专业信息架构、复习强度设置、色彩体系、卡片、
  运行方式、目录结构、使用指南、后续规划、许可协议共 10 个二级标题。
- **三轴结论**：①能解决⑤"学习进度/能力画像"仪表盘的**界面设计参考**问题，不解决数据管线/排程问题；
  ②只能当参考——它是纯前端静态页面，没有后端调度/数据聚合逻辑；③MIT，代码可参考。
- **与项目约束冲突**：**明确冲突**——项目"Python 3.12 为主，无 Node 构建链"，虽然这个仓库**不需要
  webpack/vite 之类的构建步骤**（零 npm 依赖），但运行 `server.mjs` 仍然**需要安装 Node.js 运行时**，
  这本身就是在纯 Python 技术栈里引入一个新的语言运行时，与既定约束方向相悖。
- **建议**：**仅作视觉/信息架构参考，不引入代码**；若要照抄某个卡片/配色的设计思路，可以照着截图
  重新用 Python（配合 plotly/datasette 模板）实现，不必引入这个仓库本身。
- **没有把握之处**：未逐行 diff `octopus-kaoyan-workbench` 与更受欢迎的 `octopus-kaogong-workbench`
  两个仓库，不确定"考研版"相对"考公版"具体做了哪些针对性改动，还是仅换了标题和文案。

**结论**：中英双语本轮补充检索**均未发现能改变③④⑤"最该引入三样"结论的新候选**；唯一的新发现
（octopus 系列）因语言栈冲突被排除在"引入"之外。这与前两轮观察到的规律一致：中文单关键词命中量大
但噪声率极高，`topic:` 检索精度更高但覆盖面窄。

---

## 三、阶段小结与"叠加 vs 替换"分析

### 阶段③ 本机只读 Web：结论不变，且更稳固

`datasette` + `sqlite-utils` 组合的 star、许可证、活跃度本轮全部复核通过，且**本轮为这两个库
首次现算了文件级 SHA-256**（此前两轮只做过元数据级核验），后续如需验证下载完整性可直接比对。
`coleifer/sqlite-web` 复核后 ZIP 哈希与昨日逐字节相同，确认为潜在轻量替代/排查工具，但因其默认
可写、只读靠人工加 `--read-only` 参数，架构保证不如 datasette 强，仍建议以 datasette 为主。

### 阶段④ 课表协同：本轮最大的修正在这里——`ics-py` 的"活跃"是假象

复核过程中发现，上轮报告给 `ics-py/ics-py` 标注的"最近提交 2026-04-15"**实际是 release/tag
发布时间，不是 commit 时间**——本轮用 commits atom feed 实测其默认分支 `main` 的最后一次真实
提交是 **2024-12-06**（一次 README 拼写修正），据此推算已经 **将近 21 个月没有实质性代码提交**。
`collective/icalendar` 则在 **2026-09-14**（复核前一天）仍有提交，活跃度对比悬殊。
**修正结论：④阶段的 `.ics` 解析首选 `icalendar`，不再把 `ics-py` 与其并列为"二选一"。**
`PyJobShop` 复核后 ZIP 哈希不变（无新提交），且本轮新发现其依赖 `ortools`（重量级原生求解器
依赖）——对于"120 分钟/天固定预算"这种相对简单的排程需求，代价明显偏大，维持"仅参考、暂不引入"。

### 阶段⑤ 可视化：`plotly.py` 复核通过，字段级抽样确认三种图表都有

本轮对 `plotly.py` 做了首次文件级哈希，并做了**结构抽样**（不抄正文）：确认雷达图相关模块 59 个
文件（`Scatterpolar` 系列）、`plotly.express.timeline()` 函数签名存在且含 `x_start/x_end/y` 参数
（对应甘特图/周视图所需的时间区间绘制能力）。柱状图（`px.bar`）是 plotly.express 最基础的图表类型，
本轮未单独抽样（其存在性属于该库最广为人知的功能，风险极低，未额外验证）。`fullcalendar` 复核后
哈希不变；重申它是纯前端 JS 库，**不强制要求 Node 构建链**（可用 CDN `<script>` 直接嵌入，无需
webpack/vite），但仍然是"要维护一份前端资产"的额外复杂度，与项目当前"只读静态投影"定位有摩擦，
建议只有在明确需要"可交互周视图"时才评估引入。

### 阶段② FSRS："叠加"评估——给出可执行的代价对比，不建议替换

这是任务书明确要求的分析，本轮基于**实测到的 `py-fsrs` 源码结构**（而不是转述 README）给出：

**叠加方案（推荐）**：
1. 每个复习条目新增 3 个可持久化字段：`stability`（float）、`difficulty`（float）、
   `fsrs_due`（datetime，FSRS 预测的下次到期时间）——这 3 个字段名**本轮实测确认**在
   `py-fsrs` 的 `Card` dataclass 里叫 `stability`/`difficulty`/`due`，**均不与项目现有
   `weight`（学科时间预算，`ky/models.py:306` 实测确认字段名）、题目→知识点置信度、
   来源支持度这三种既有 `weight` 语义冲突**——因为它们根本不叫 `weight`。
2. 每次自评后调用一次 `Scheduler.review_card()`（本轮实测该方法存在于 `fsrs/scheduler.py`
   的 `Scheduler` 类，26 个方法之一），更新上述 3 个字段。
3. 在现有全序键（逾期天数、延期次数、遗忘次数、科目落后率、`due_date`、类型优先级、自评、
   `review_id`）**之后追加**一个新的 tie-breaking 维度（例如"FSRS 预测遗忘概率"），只在前面
   8 个键都打平时才生效；对尚无 FSRS 历史的条目，该维度取中性默认值（不影响现有排序行为）。
4. 代价：新增 3 个字段的存储与迁移（旧条目为空值）、新增一次调度调用、扩展比较器逻辑；
   **不改动、不替换**现有 8 键排序核本身，也不改动其契约与已有的变异测试。

**替换方案（不推荐，仅作对比）**：
- 用 FSRS 的"预测下次到期/遗忘概率"整体取代现有全序键排序逻辑。
- 代价：FSRS 解决的是"单张卡片何时再复习最优"（概率化遗忘曲线），完全不建模"数学一占
  预算 40%""距考试还有 N 天必须清空积压"这类**硬约束**——现有排序核的逾期天数/科目落后率/
  容量规划语义会全部丢失，需要重新设计一套机制把这些硬约束塞回 FSRS 框架里，**代价远高于
  收益**，且直接违反任务书"已过 4 轮审查，不要默认替换"的要求。

**结论：只建议"叠加"，不建议"替换"；命名层面无 Python 标识符冲突，但团队文档里出现"weight"
一词时建议注明是"FSRS 参数权重"（FSRS 官方文档管这个词叫模型 weights，本轮在 `Scheduler`
docstring 里实测确认）还是项目原有三种 `weight` 之一，避免人类读者混淆。**

### 阶段①⑥：本轮未新增核验（按任务书优先级，维持前两轮结论）

任务书明确①⑥为低优先级——"已有自研且经审查，除非能显著减少维护面，否则不引入"。本轮的
19 条复核对象与 6 条补充检索均未涉及知识树/数据管线的替代实现，也没有在补充检索中意外发现
任何与①⑥相关、足以推翻"自研已足够"结论的新证据。**维持前两轮结论：不引入。**

---

## 四、当前最该引入的候选（本轮复核后的结论）

1. **`datasette` + `sqlite-utils`**（阶段③）—— 复核通过，24 小时内无变化风险，本轮已建立文件级哈希基线。
2. **`collective/icalendar`**（阶段④）—— 复核通过且比 `ics-py` 明显更活跃；**本轮的关键修正是排除
   `ics-py`**（真实最后提交已停滞近 21 个月，此前误信了它的 release 时间戳）。
3. **`plotly.py`**（阶段⑤）—— 复核通过，抽样确认雷达图与甘特图 API 均存在，一个库覆盖⑤全部需求。

（`open-spaced-repetition/py-fsrs` 经本轮字段级核验，"叠加"方案可行且代价可控，但按任务书要求
它属于**需要项目自己决定是否现在做**的"中优先"事项，不计入本轮"三大件"，留待项目决策。）

## 五、明确不建议引入清单

- `ics-py/ics-py` —— 本轮修正：真实最后提交 2024-12-06，近 21 个月无实质提交，改用 `icalendar`。
- `mkdocs/mkdocs` —— 11 个月未提交，且不直接解决"SQLite→只读投影"这个具体需求。
- `PyJobShop/PyJobShop` —— 需要 `ortools` 重依赖，对当前"120 分钟/天固定预算"排程需求过重。
- `fullcalendar/fullcalendar` —— 纯前端 JS 库，与"只读静态投影"定位有摩擦，仅在明确需要可交互
  周视图时才评估。
- `plotly/dash`、`streamlit/streamlit` —— 均为运行时常驻服务形态，与"本机只读、单文件优先"架构冲突。
- `alankan886/SuperMemo2` —— 已 archived，确认死亡。
- `zhangyushaonao/octopus-kaoyan-workbench` / `octopus-kaogong-workbench` —— 需要 Node 运行时，
  与"无 Node 构建链"的技术栈约束方向相悖，仅供 UI 设计参考。
- `open-spaced-repetition/fsrs4anki` —— Anki 插件形态，不可脱离 Anki 直接使用。

## 六、我试过但没找到 / 价值太低而放弃的路径

| 路径 | 结果 |
|---|---|
| `课表`（中文单关键词） | `total_count=4056`，抽样前 5 条全部噪声 |
| `倒计时`（中文单关键词） | `total_count=3200`，抽样前 5 条全部噪声 |
| `topic:study-planner` | `total_count=285`，抽样前 5 条均为通用学习计划应用，非可复用轮子 |
| `sqlite readonly viewer`（英文） | `total_count=1`，唯一结果 0 星，不采纳 |
| `timetable solver ics python`（英文） | `total_count=0` |
| GitHub REST `core`/`code_search` 配额 | 本轮开始时已被当天前序调用打满（`remaining=0/60`），
  改用网页+atom feed 降级路径完成全部 19 条复核；`search` 配额本轮用掉 7/10（6 条主查询 + 1 条
  `topic:study-dashboard` 重跑） |

## 七、我实测到了 / 我推断（严格区分）

**我实测到了**：
- 19 个候选 repo 本轮的 star / license spdxId / archived 状态 / 默认分支 / 最近一次 commit
  时间（通过网页内嵌 JSON + commits atom feed，非 `pushed_at`/`updated_at`）。
- 9 个 repo 的默认分支 ZIP 字节数与现算 SHA-256（`datasette`、`sqlite-utils`、`icalendar`、
  `plotly.py`、`py-fsrs` 为**本轮首次**建立哈希基线；`sqlite-web`、`PyJobShop`、`fullcalendar`、
  `obsidian-learning-engine` 为**复核**，与上轮哈希逐字节相同）。
- `ics-py` 最近一次真实 commit 是 2024-12-06（README typo 修复 #426），而非上轮报告的
  2026-04-15（该日期实测为 release/tag 发布时间）。
- `icalendar` 的 `LICENSE.rst` 正文（BSD-2-Clause 风格）、`datasette`/`sqlite-utils` 的 `LICENSE`
  首行（Apache License）、`plotly.py` 的 `LICENSE.txt` 首行（MIT License）。
- `py-fsrs` 的 `Card` dataclass 7 个字段名、`Scheduler` 类 26 个方法名、docstring 中把参数数组
  称为 "model weights" 的原文措辞。
- `PyJobShop` 的 `pyproject.toml` 依赖列表（含 `ortools>=9.12.4544`）、源码中 "weight" 出现于
  `Model.py`/`ProblemData.py`/`Objective.py` 等文件。
- `plotly.py` 中 `scatterpolar` 相关文件 59 个、`plotly/express/_chart_types.py` 中
  `def timeline(...)` 函数签名存在。
- `octopus-kaoyan-workbench` 的文件清单、`package.json`（`dependencies` 为空）、README 标题层级。
- 项目自身 `ky/models.py:306` 的 `Subject.weight` 字段与 `data/structured_materials/cs408/
  knowledge_tree_weighted.yaml` 里的来源支持度 `weight` 字段（只读确认，未修改）。

**我推断（未实际跑通集成，属工程判断）**：
- FSRS"叠加"方案的具体代价量级（3 个新字段 + 1 次调度调用 + 扩展比较器）——基于阅读
  `py-fsrs` 公开 API 结构做出的估计，未实际写代码验证迁移路径对已有历史数据的兼容性。
- `PyJobShop` 引入 `ortools` 后的实际磁盘/安装体积——基于 `ortools` 作为已知大型原生二进制
  包的一般认知，本轮未实际 `pip install` 测量。
- `fullcalendar` 用 CDN `<script>` 免构建链引入的可行性——基于其是标准浏览器 JS 库的一般判断，
  未在本机浏览器里实际验证加载效果。
- `octopus-kaoyan-workbench` 相对 `octopus-kaogong-workbench` 的具体差异程度——未逐行 diff。

## 八、没有把握的地方（至少 3 条）

1. **多数候选的 open issue 数本轮未能重新核验**——GitHub REST `core` 配额在本轮一开始就已耗尽
   （前两轮当天调用量已达上限），网页 HTML 静态抓取拿不到 issue 计数（现代 GitHub 页面用前端
   异步加载该数字），本轮只对 star/license/commit/hash 四项做了扎实复核，issue 活跃度数据请
   参考前两轮报告的对应快照，并明确知晓"可能已过去 24 小时产生漂移"。
2. **`octopus-kaoyan-workbench` 与 `octopus-kaogong-workbench` 的实际差异未逐行核对**，不确定
   "考研版"是否只是改了标题文案，还是真的做了学科结构上的定制。
3. **FSRS 叠加方案里"对已有历史数据的兼容性"未实测**——若项目现有复习记录已经积累了较多条目，
   给这些条目补齐 FSRS 所需的初始 `stability`/`difficulty` 状态需要一次性回填逻辑，这部分
   本轮没有验证可行性，只确认了字段本身不冲突。
4. **`plotly.py` 的 `px.bar`（柱状图）本轮未做字段级抽样**，因为其存在性是该库最基础且广为人知
   的能力，风险很低，但严格来说不属于"实测"，只是"极高置信度的推断"。
5. **网页降级路径（`stargazerCount`/`spdxId`/`isArchived` 取自页面内嵌 JSON）不是官方文档化的
   API**，GitHub 前端实现细节变化可能导致这条路径未来失效，仅作为本轮限流时的应急手段，不建议
   作为长期自动化监控的数据源。

---

## 附：本轮现算 SHA-256 一览

| 文件（repo，默认分支 ZIP） | 字节数 | SHA-256 | 与上轮对比 |
|---|---|---|---|
| `simonw/datasette` | 1,231,807 | `b21c6c2d95f55f6f5cd0a6f422f054e83bbe9adb7199a3ff95a17f51699df568` | 首次建立基线 |
| `simonw/sqlite-utils` | 362,612 | `72cfe46b40bc2e75ef3efe374103516e407b32273099789237f41adffa0202e2` | 首次建立基线 |
| `collective/icalendar` | 874,284 | `a1ceb36f31f2bb0782cdb3b0f720b0633d348f63e2d5fd699e14fb671fca4e3c` | 首次建立基线 |
| `plotly/plotly.py` | 12,131,874 | `9a271ccc36a55dd189e5096f920e940bedc7281bbe60967a1c9810eadea32e6e` | 首次建立基线 |
| `open-spaced-repetition/py-fsrs` | 207,168 | `9e8b03bee013a24c1690fc66087ffb046884db0910913d02ca9e94e7fb33431b` | 首次建立基线 |
| `coleifer/sqlite-web` | 723,644 | `9e485cc604fa15ee1c51d51f21cb41c0785c3e94f1f69ac91c645415e4aa1d71` | **与上轮逐字节相同** |
| `PyJobShop/PyJobShop` | 444,044 | `c76b43ce6b41530dba5aeb45505420dbed27d10e1a6f32977f9014fc4244e9bf` | **与上轮逐字节相同** |
| `fullcalendar/fullcalendar` | 1,408,640 | `7587270bd0b0fe50feb13ed971393bc12e912d3b0eb8054dacf99628b411e10e` | **与上轮逐字节相同** |
| `vellvient/obsidian-learning-engine` | 244,605 | `644a4e9075484e0c062c2c4d5d44b71079bc9bfec6944ed9471e6e36b66b3c41` | **与上轮逐字节相同** |
| `zhangyushaonao/octopus-kaoyan-workbench`（本轮新增候选） | 2,311,375 | `16a7edf1e4d26395b181505915e1f6def185211625c77981ed4f7c7bb23ca459` | 首次建立基线 |

所有原始查询结果、下载 ZIP、`web_meta.tsv`、`search_spotcheck.json` 均保存在
`%TEMP%\kaoyan-probe\ghsurvey3\`，可复核。
