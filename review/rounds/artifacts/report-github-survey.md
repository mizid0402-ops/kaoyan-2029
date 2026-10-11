# GitHub 检索报告 —— 为项目后续五阶段找现成数据/轮子/参考实现

调研时间：2026-09-14 | 检索方式：GitHub 公开 REST API（无 token，`curl.exe` + `py -3.12`）
工作目录：`%TEMP%\kaoyan-probe\ghsurvey\`（原始查询结果、下载文件、脚本均保留在此，未修改 `F:\workspace\kaoyan-ai-system` 任何文件，未执行 git）

> 术语约定：**「我实测到了」**＝我用 API 拉取了 repo 元数据 / 下载了文件 / 现算了 SHA-256 / 解析了 JSON 结构；**「我推断」**＝基于描述、文件名、目录结构做的合理判断，未逐条验证内容。下文每条都会标注。

---

## 一、按阶段分组的候选表

### 阶段①：知识树数据（最高优先级）

| repo | 用途 | 事实（star / 最近提交 / 许可） | 抽样核对结果 | 类别 | 可用性结论 |
|---|---|---|---|---|---|
| [exam-data/NETEMVocabulary](https://github.com/exam-data/NETEMVocabulary) | 英语一考纲词汇表（结构化） | star=241，最近提交 2026-06-06，仓库整体 license=NOASSERTION，但**实测**根目录 `LICENSE`=CC BY-NC-SA 4.0（数据），`LICENSE-CODE`=MIT（脚本），未 archive，5 个 open issue | **实测下载** `netem_full_list.json`，1,106,068 字节，SHA-256=`6d71a301321056291902bc4804e223c6926dca0d629a45076a6ca5adab185f62`。结构：顶层 1 个 key `"5530考研词汇词频排序表"` → list，**5530 条**，每条字段 `[序号, 词频, 单词, 释义, 其他拼写, 分类, 子分类]`。README 明确说明数据源自《2024年全国硕士研究生招生考试英语（一）考试大纲词汇表》 | **数据** | 见下方阶段①小节 |
| [kaichan-kc/408-questions](https://github.com/kaichan-kc/408-questions) | 408 历年真题 + 考点标注（结构化） | star=1，创建与最后提交同一天（2026-05-08），仓库无 LICENSE 文件（license=NONE），无 issue | **实测下载** `408_questions.json`，1,056,638 字节，SHA-256=`451197409bd3471168ccb1754a86e766bf528c8f354ec1866ace82701d03f275`；`408_questions_by_year/2020.json`，57,145 字节，SHA-256=`33e7db47435eabbdf480a5b02acbdeb7ffdc756521fe4b4d918a350bb6e91880`。结构：顶层按年份（2009–2025）为 key，每年 list **47 条**，每条含嵌套 `question` 对象，字段包括 `id, questionIndex, paperId, knowledgeTagsId, questionType, mdContent, score, year, answerText, answer, analysisText, ratingTotal, avgDifficulty, knowledgePointIds` 等**（含考点标注字段）**。**实测**仓库内 `scrape_408.py` 显示数据抓取自第三方付费题库站 `api.408os.cn`，使用 `ddddocr` 破解验证码登录 | **数据（高风险）** | 见下方阶段①小节 |
| [TsekaLuk/Kaoyan-Math1-Papers](https://github.com/TsekaLuk/Kaoyan-Math1-Papers) | 数学一历年真题（1987–2025）独立转录 | star=79，创建于 2026-02-13，最近提交 2026-02-14，license=NOASSERTION（仓库内有独立 LICENSE 文件，未读取全文），1845 个文件，仓库体积 189MB | 未下载正文（版权敏感）。**实测**目录树：`papers/*.md`（39 个按年份命名的 markdown 真题转录文件）+ `solutions/*/`（每年一个目录，含 MinerU OCR 管线产物 `*_content_list.json`、`*_model.json`、`layout.json`、`*_origin.pdf`） | **数据（真题）+ 参考实现（OCR 管线产物）** | 见下方阶段①小节 |
| [Noob-Dream/cskaoyan](https://github.com/Noob-Dream/cskaoyan) | 408 官方考纲 PDF（非结构化） | star=612，license=GPL-3.0，最近提交 2022-07-17（3年多未更新，未 archive），5 个 open issue | **实测下载**并现算 `408统考/2022年408考研大纲.pdf`，616,115 字节，SHA-256=`60c54de8fbc5642543d3324580f83f5f95ff435609fcad8f4baf58d125aabcaf`，文件头验证为合法 PDF（`%PDF-1.7`） | **数据（PDF 原文，非结构化）** | 见下方阶段①小节 |
| [StreamAzure/Computer_Basics_Notes](https://github.com/StreamAzure/Computer_Basics_Notes) | 按 408 考纲章节组织的个人笔记（mkdocs-material 生成站点） | star=3，无 license，最近提交 2024-01-08 | **实测**目录树：289 个文件，全部是 mkdocs-material 生成的 HTML+图片，按 `0x01 绪论`…`0x07 IO系统` 等 408 标准章节编号组织，无 JSON/YAML 结构化数据 | **参考实现**（章节结构侧面印证，非独立数据源） | 见下方阶段①小节 |
| asdfkjs/CS-408 | 408 个人笔记 | star=30，license=MIT，最近提交 2025-07-24 | **实测**目录树 7905 个文件，绝大部分是 CLion/CMake 编译产物和个人代码练习，无结构化考纲/真题数据 | 无价值 | 不推荐，检查后排除 |

### 阶段②：SRS 引擎与长期计划

| repo | 用途 | 事实 | 类别 | 可用性结论 |
|---|---|---|---|---|
| [open-spaced-repetition/py-fsrs](https://github.com/open-spaced-repetition/py-fsrs) | FSRS 算法 Python 包 | **实测** star=486，license=MIT，最近提交 2026-08-09，未 archive，0 open issue，仓库体积 624KB | 库/轮子 | 见阶段②小节 |
| open-spaced-repetition/fsrs-rs / ts-fsrs / go-fsrs | FSRS 其他语言实现 | **实测** stars 分别为 422 (BSD-3-Clause) / 790 (MIT) / 145 (MIT)，均最近一个月内有提交 | 库/轮子 | 仅作对照，项目是 Python 栈用不上 |
| [open-spaced-repetition/fsrs4anki](https://github.com/open-spaced-repetition/fsrs4anki) | Anki 上的 FSRS 参考实现（含优化器） | **实测** star=4064，license=MIT，最近提交 2026-08-14 | 参考实现 | 算法思路参考价值高，但是 Anki 插件形态，不可直接用 |
| [open-spaced-repetition/awesome-fsrs](https://github.com/open-spaced-repetition/awesome-fsrs) | FSRS 生态汇总列表 | **实测** star=685，license=CC0-1.0，最近提交 2026-09-11 | 参考索引 | 用于横向了解各语言/平台实现现状 |
| [open-spaced-repetition/srs-benchmark](https://github.com/open-spaced-repetition/srs-benchmark) | 各调度算法（FSRS/SM-2等）效果基准测试 | **实测** star=263，license=NONE，最近提交 2026-09-12（活跃） | 参考实现 | 评估"是否引入 FSRS"时可参考其对比方法论，但代码本身不直接可用（license 缺失） |
| [alankan886/SuperMemo2](https://github.com/alankan886/SuperMemo2) | SM-2 算法 Python 包 | **实测** star=121，license=MIT，**已 archived**，最近提交 2024-06-23 | 库/轮子 | 已停止维护，仅供参考，不建议依赖 |
| 考研/应试长期计划生成器 | —— | 检索 0 命中（见"没找到"部分） | —— | 未找到 |
| 通用队列调度/容量规划/积压处理库 | —— | 检索 0 命中（见"没找到"部分） | —— | 未找到（这类需求通常是项目自己实现，不是独立发布的库） |

### 阶段③：本机只读 Web 投影

| repo | 用途 | 事实 | 类别 | 可用性结论 |
|---|---|---|---|---|
| [simonw/datasette](https://github.com/simonw/datasette) | 从 SQLite 直接生成只读 Web 浏览/发布界面 | **实测** star=11,460，license=Apache-2.0，最近提交 2026-09-11（非常活跃），718 open issues | 库/轮子 | 与"本机只读 Web 投影，SQLite 可重建"的需求高度吻合 |
| [simonw/sqlite-utils](https://github.com/simonw/sqlite-utils) | CLI + Python 库，从各种数据源批量生成/操作 SQLite | **实测** star=2168，license=Apache-2.0，最近提交 2026-09-02 | 库/轮子 | 适合做"从 Markdown/YAML 源文件重建 SQLite 投影"的构建步骤 |
| [rclement/datasette-dashboards](https://github.com/rclement/datasette-dashboards) | Datasette 插件，做交互式仪表盘 | **实测** star=178，license=Apache-2.0，最近提交 2026-09-10 | 库/轮子 | 阶段③④⑤可复用同一套技术栈做可视化投影 |
| [mkdocs/mkdocs](https://github.com/mkdocs/mkdocs) | Markdown → 静态站 | **实测** star=22,433，license=BSD-2-Clause，最近提交 2025-10-20 | 库/轮子 | 若不需要"从 SQLite 直读"而是纯 Markdown/YAML 源，mkdocs 更成熟 |
| [squidfunk/mkdocs-material](https://github.com/squidfunk/mkdocs-material) | mkdocs 的主题/增强 | **实测** star=27,427，license=MIT，最近提交 2026-08-30 | 库/轮子 | 同上；StreamAzure 那个 408 笔记站点就是用这个生成的（实测目录结构确认） |
| logya / ezcv / gnrt / papery / staticpie（Python 静态站生成器） | Markdown/YAML → 静态站 | **实测** star 均 ＜20，最新提交不一 | 库/轮子 | star 太低，活跃度不足，不推荐；mkdocs 更值得用 |

### 阶段④：课表协同

| repo | 用途 | 事实 | 类别 | 可用性结论 |
|---|---|---|---|---|
| [collective/icalendar](https://github.com/collective/icalendar) | Python 的 iCalendar (.ics) 解析/生成库 | **实测** star=1171，仓库 license 字段=NOASSERTION，但**实测下载** `LICENSE.rst` 内容为 BSD-2-Clause（Plone Foundation, 2012-2013），最近提交 2026-09-13（非常活跃） | 库/轮子 | 直接可用于阶段④的 .ics 解析/生成 |
| [ics-py/ics-py](https://github.com/ics-py/ics-py) | 更 Pythonic 的 iCalendar 库 | **实测** star=721，仓库 license 字段=NOASSERTION，**实测下载** `LICENSE.rst` 内容为 Apache-2.0，最近提交 2026-04-15 | 库/轮子 | 同上，API 更友好，二选一 |
| 各高校教务系统课表解析/导出脚本（miaotony/NUAA_ClassSchedule、walo20001/SHSMU-SJTUSM-course-planner 等十余个） | 教务系统课表→ICS 的实现思路 | **实测**（列表见 q29/q30 原始查询结果），均为特定学校定制，star 普遍 ＜40 | 参考实现 | 不可直接用（绑定特定学校教务系统接口），但"临时覆盖/调课"的处理模式可以借鉴思路 |
| 带约束排程（timetable scheduler） | 固定课程+可变任务排程 | **实测**检索到的 3 个仓库均 star ≤1，属于课程作业级项目 | 参考实现（价值很低） | 不推荐参考，质量不足 |

### 阶段⑤：可视化

| repo | 用途 | 事实 | 类别 | 可用性结论 |
|---|---|---|---|---|
| [plotly/plotly.py](https://github.com/plotly/plotly.py) | Python 交互图表库，内置雷达图(Scatterpolar)、甘特图(timeline) | **实测** star=18,780，license=MIT，最近提交 2026-09-12 | 库/轮子 | 雷达图（能力画像）、甘特图（课表周视图）、柱状图（政治）都可以用同一个库实现 |
| [plotly/dash](https://github.com/plotly/dash) | 基于 plotly 的仪表盘框架 | **实测** star=24,405，license=MIT，最近提交 2026-09-11 | 库/轮子 | 若阶段③要做交互式仪表盘可选，但和"本机只读投影"定位略重 |
| [streamlit/streamlit](https://github.com/streamlit/streamlit) | Python 快速构建数据应用 | **实测** star=45,740，license=Apache-2.0，最近提交 2026-09-13 | 库/轮子 | 可配合 plotly 做能力雷达图/进度看板，但是"运行时服务"形态，与"只读投影"的静态化目标需要额外适配 |
| 各类 "streamlit + radar chart" 简历分析类项目 | 雷达图具体用法参考 | **实测**检索到 7 个，均为简历评分类应用，star ≤9 | 参考实现（价值低） | 仅供参考 plotly 雷达图的调用方式，不是可复用组件 |

---

## 二、每阶段小结

### 阶段①：知识树数据 —— 这是本次调研的核心，也是收获最大的部分

**找到了什么**：
- **英语一**：找到一份**独立于项目现有来源**的结构化词汇数据 —— `exam-data/NETEMVocabulary`，5530 条，基于官方英语一考纲词汇表整理，字段含词频排序。这**直接满足任务书里"找到一份独立的结构化考纲，比找到合并库更有价值"的诉求**——项目现在英语一只有 1 份目录，这是第 2 份独立来源，且已经是结构化 JSON，理论上现在就有条件对"英语一词汇范围"做双源加权合并（虽然目前还只是词表，不是完整考纲大纲文本）。
- **408**：没找到结构化的**考纲**，但找到了：(a) 一份可能是官方原文的 PDF 考纲（`Noob-Dream/cskaoyan` 里的 2022 年 408 考研大纲.pdf，已验证是合法 PDF）；(b) 一份结构化的**真题+疑似考点标注**数据（`kaichan-kc/408-questions`），但来源合规性存疑，不建议直接使用其抓取正文。
- **数学一**：没找到结构化考纲，但找到一份**独立于项目现有转录**的真题原文转录（`TsekaLuk/Kaoyan-Math1-Papers`，1987–2025），可作为第二来源用于交叉校验真题文本本身（不是考纲）。

**最推荐哪个**：`exam-data/NETEMVocabulary` —— 唯一一个"结构化 + 来源可核实（明确说明取自官方考纲词表）+ 许可可用（CC BY-NC-SA 4.0，本机单用户落盘没有问题）+ 活跃度尚可"的数据源。

**还缺什么**：
- 408 / 数学一 / 英语一的**考纲正文本身**（不是真题、不是词表）仍然没有独立的第二份结构化来源。
- 没有找到任何"多源加权合并/共识合并"的**通用开源实现**能直接套用在考纲合并场景——这类算法通常就是简单的加权投票/并集+置信度，项目大概率需要自己写，找现成库的收益不大。

### 阶段②：SRS 与长期计划

**找到了什么**：FSRS 生态非常成熟且活跃（`open-spaced-repetition` 组织下 py-fsrs/fsrs-rs/ts-fsrs/go-fsrs/fsrs4anki/awesome-fsrs/srs-benchmark，均为近期活跃仓库，MIT/BSD 许可）。SM-2 找到但主流实现已 archived。**没有找到**考研/应试类的长期计划生成器，也没有找到通用的"队列调度+容量规划+积压处理"库——这类东西看起来在 GitHub 上很少被单独包装成库。

**最推荐哪个**：`open-spaced-repetition/py-fsrs`（Python，MIT，活跃）。

**还缺什么**：**评估性**的空白——FSRS 解决的是"单张卡片何时再出现最优"（概率化遗忘曲线预测），项目现有的确定性排序核解决的是"今天候选集合内先做哪个"（全序键排序）。两者是不同层次的问题，**我没有能力替项目做"叠加还是替换"的决策**，只能提示：字面上看更像是可以叠加（FSRS 输出的"遗忘概率/下次到期日"可以作为排序核的一个新特征维度），而不是相互替代，但这需要项目自己结合 B8/B10 等既定约束评估。

### 阶段③：本机只读 Web 投影

**找到了什么**：`datasette`（从 SQLite 直接生成只读浏览/发布界面）+ `sqlite-utils`（构建/维护 SQLite 库）这对组合，正是"SQLite 可重建投影"需求的标准解法，且都极度活跃、Apache-2.0 许可、生态成熟（`datasette-dashboards` 插件可以顺带覆盖阶段⑤的仪表盘需求）。Markdown→静态站方面，`mkdocs` + `mkdocs-material` 是目前搜到的最成熟选项（其余几个 Python 静态站生成器 star 个位数到十几，活跃度不足，不推荐）。

**最推荐哪个**：`datasette` + `sqlite-utils` 组合。

**还缺什么**：没有找到"专门针对考研学习系统"的现成模板/参考实现，需要项目自己在 datasette 之上做定制视图。

### 阶段④：课表协同

**找到了什么**：Python 侧 iCalendar 解析/生成有两个成熟库可选（`icalendar` 实测 BSD-2-Clause，`ics-py` 实测 Apache-2.0，均活跃）。国内高校教务系统课表导出为 .ics 的实现有十几个，但全部是**特定学校定制**（如南航、复旦、湖大、UPC等），不能直接用于任意学校，只能作为"如何处理临时调课/覆盖"的实现思路参考。没有找到质量较高的"固定课程+可变复习任务"约束排程的通用库或参考实现（检索到的 3 个都是课程作业级项目，star ≤1）。

**最推荐哪个**：`icalendar`（或 `ics-py`）作为 .ics 读写的基础库；具体排程逻辑大概率需要项目自己写。

**还缺什么**：没有一个通用的、非绑定特定学校的"教务课表 + 复习任务"排程参考实现；"考试周/假期/实习"这类临时覆盖模式，也没有找到现成的设计模式文档或库，只能从各校定制脚本里各自摘取零散思路。

### 阶段⑤：可视化

**找到了什么**：`plotly.py`（MIT，18.7k star，非常活跃）自带雷达图（`Scatterpolar`）、甘特图（`timeline`/`Gantt`）、柱状图（`Bar`）等所有任务书要求的图表类型，一个库可以覆盖阶段⑤全部可视化需求（能力画像用雷达图、课表用甘特图/周视图、政治用柱状图）。`streamlit` 可选配合做交互界面，但要注意它是"运行时应用"形态，与阶段③"只读静态投影"的定位有一定张力，需要项目自己决定是纯 plotly 生成静态图嵌入 datasette，还是额外跑一个 streamlit 服务。

**最推荐哪个**：`plotly.py`（不需要额外找"雷达图组件"这种小众仓库，直接用 plotly 内置图表类型即可）。

**还缺什么**：没有找到"学习进度/能力画像/目标差距"这个具体业务场景的现成开源组件——这类东西高度定制化，本来就不太可能有通用轮子，用 plotly 自己画是合理路径。

---

## 三、当前最该引入的三样东西

1. **`exam-data/NETEMVocabulary` 的 `netem_full_list.json`**（阶段①）——这是本次调研里唯一真正解决"来源不够"这个瓶颈的东西：英语一现在有了第 2 份独立结构化来源，是目前唯一可以真正做"多源加权合并"的科目。
2. **`datasette` + `sqlite-utils`**（阶段③）——直接对应"本机单用户、SQLite 可重建、Web 只读投影"的既定架构决策（B5），不需要绕路子自己写投影层。
3. **`open-spaced-repetition/py-fsrs`**（阶段②，前提是评估后决定引入）——生态最成熟、许可最干净的 FSRS 实现；但引入前必须先完成"叠加还是替换现有排序核"的评估，不要默认替换。

（`plotly.py` 和 `icalendar`/`ics-py` 也很值得后续引入，但相对没有那么紧迫——阶段④⑤要等阶段①②先落地。）

---

## 四、我试过但没找到的路径（具体搜索词与结果）

| 搜索词 | 结果 |
|---|---|
| `kaoyan 408 computer science syllabus` | total_count=0 |
| `考研数学一 大纲` | total_count=0 |
| `考研数学 大纲 json` | total_count=0 |
| `考研英语一 大纲 词汇` | total_count=0 |
| `英语一 大纲`（不带"词汇"） | total_count=0 |
| `考研真题 词频`（非英语，泛指） | total_count=0 |
| `kaoyan syllabus outline json` | total_count=0 |
| `408 大纲 数据结构 操作系统 计算机网络 组成原理` | total_count=0 |
| `真题 考点 标注 json` | total_count=0（kaichan-kc/408-questions 是通过 `topic:kaoyan` 浏览列表间接发现的，不是这个词命中的） |
| `考研 计划生成 排程` | total_count=0 |
| `capacity planning backlog scheduler python` | total_count=0 |
| `datasette sqlite readonly`（三词 AND） | total_count=0（改用 `datasette in:name` 直接命中） |
| `sqlite readonly web dashboard python` | total_count=0 |
| `constraint scheduling timetable python available slots` | total_count=3，均为课程作业级项目（star ≤1），价值很低 |

**规律**：GitHub 仓库搜索 API 对多个中文关键词做 AND 组合时极易返回 0（可能是因为它只索引 name/description/topics/README 的浅层匹配，长尾中文短语很难命中），单个关键词或英文关键词命中率明显更高。这意味着"没找到"里有一部分可能是**关键词覆盖不足**导致的假阴性，不完全等于"真的不存在"。

---

## 五、没有把握的地方（至少 3 条）

1. **`TsekaLuk/Kaoyan-Math1-Papers` 的许可证具体条款未核实**——仓库级别 GitHub API 报告 license=NOASSERTION，但仓库内确实有一个独立的 `LICENSE` 文件（932 字节），我没有下载读取其正文，所以不确定这份数据实际能不能落盘/再分发，只能标"unknown"。
2. **`Noob-Dream/cskaoyan` 里的 2022 年 408 考研大纲 PDF 是否为教育部官方原文的完整准确副本**——我只验证了"文件存在、616,115 字节、SHA-256 已现算、是合法 PDF"，没有做逐字比对，不确定内容是否完整、是否是当年真实官方版本还是有人二次排版过的版本。
3. **`kaichan-kc/408-questions` 里 `mdContent`/`answerText`/`analysisText` 等字段的实际正文内容未逐条核对**——我只解析了 JSON 的字段名和条目数（47条/年 × 17年），没有读取题目正文本身（按任务书要求不应抄录），所以无法判断这些正文的准确性，只能确认字段结构存在且抓取脚本证据确凿指向未授权爬取一个付费站点。
4. **"没找到"是否真的意味着不存在**——如第四节所说，GitHub repo 搜索 API 对中文多词 AND 组合很不敏感，理论上可能存在用不同措辞描述但实际内容相关的仓库，本次检索没有覆盖到（例如用拼音、英文缩写、或完全不含"考研/kaoyan"字样命名的仓库）。
5. **FSRS 与项目现有确定性排序核的"叠加 vs 替换"判断，我没有做**——任务书明确要求"需要评估，不要默认替换"，但这个评估依赖项目内部对排序核语义、B8/B10 等约束的完整上下文，我只呈现了 FSRS 生态的客观事实（成熟度、许可、活跃度），具体怎么整合需要项目自己判断，我在此没有给出结论性建议。

---

## 附：本次下载并现算 SHA-256 的文件清单

| 文件 | 字节数 | SHA-256 |
|---|---|---|
| netem_full_list.json (exam-data/NETEMVocabulary) | 1,106,068 | `6d71a301321056291902bc4804e223c6926dca0d629a45076a6ca5adab185f62` |
| 408_questions.json (kaichan-kc/408-questions) | 1,056,638 | `451197409bd3471168ccb1754a86e766bf528c8f354ec1866ace82701d03f275` |
| 408_questions_by_year/2020.json (kaichan-kc/408-questions) | 57,145 | `33e7db47435eabbdf480a5b02acbdeb7ffdc756521fe4b4d918a350bb6e91880` |
| 408统考/2022年408考研大纲.pdf (Noob-Dream/cskaoyan) | 616,115 | `60c54de8fbc5642543d3324580f83f5f95ff435609fcad8f4baf58d125aabcaf` |

所有原始查询结果（q1–q36）、repo 结构导出（r_*.txt）、下载文件与哈希/结构抽样脚本均保存在 `%TEMP%\kaoyan-probe\ghsurvey\`，可复核。
