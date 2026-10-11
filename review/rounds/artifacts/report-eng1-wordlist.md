# 考研英语（一）大纲词汇网上检索与取证报告

检索日期：2026-09-13  
工作目录：`C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\wordlist\`  
范围纪律：未修改 `F:\workspace\kaoyan-ai-system`；未执行 Git；未落盘真题原文或教辅正文。

## 结论先行

找到 3 个可实际下载并核验的候选文件，但它们来自 2 个来源家族：

1. `exam-data/NETEMVocabulary`：JSON 声称来自 2024 年英语（一）大纲的 5,530 个词，并增加跨约 200 套试卷的频次排序；实测 5,530 条，严格不区分大小写后 5,528 个。证据等级 C，不是官方发布；仓库自声明 CC BY-NC-SA 4.0。
2. `busiyiworld/maimemo-export` 的 `2025硕士研究生英语（一）大纲词汇.csv`：实测 5,687 行，精确去重 5,683 条，大小写折叠去重 5,680 条。证据等级 C；文件名自称“大纲词汇”，但无官方责任者证明。
3. 同一仓库的 `2025考研英语大纲词汇5500.csv`：实测 5,689 行，精确去重 5,684 条，大小写折叠去重 5,681 条。证据等级 C；与候选 2 高度同源，不是独立证据。

推荐：将 NETEM 的 `netem_5530_words.txt` 作为候选底表、将 `netem_full_list.json` 中的频次作为“真题/语料热度”字段，但只能在非商业、保留署名、链接许可、注明修改并按同许可发布的条件下登记/分发。它仍需在项目中标注“公开整理、非官方、2024 口径”，不能写成“教育部官方 2026 词表”。

## 1. 候选来源表

“去重后”主数字采用英文词条大小写折叠后的去重数；同时保留精确字符串去重数，避免 `May/may` 等重复造成误判。

| 候选 | URL | 等级与依据 | 实测词条数 | 编制者/自述 | 自称口径 | 版权/许可自述 | 本地文件、字节数、SHA-256 | `may_store` | `may_redistribute` |
|---|---|---|---:|---|---|---|---|---|---|
| NETEM 词频 JSON | https://github.com/exam-data/NETEMVocabulary/blob/master/netem_full_list.json；原始下载：https://raw.githubusercontent.com/exam-data/NETEMVocabulary/refs/heads/master/netem_full_list.json | **C**。公开 GitHub 项目；README/Release 有方法和数据说明，但不是教育部、出版社或考试院直接发布 | 5,530 行/记录；精确去重 5,530；大小写折叠去重 **5,528** | Release/仓库显示维护者 `awxiaoxian2020`；自述以 2024 英语（一）大纲 5,530 词为底，按约 200 套四六级、考研、专四专八文本频次排序，部分释义人工校对 | 同时是“大纲词汇底表”与“词频排序数据”；不是“官方词汇文件”，也不是仅三套真题的高频表 | README 明示仓库数据 **CC BY-NC-SA 4.0**，程序 MIT；但上游大纲及外部词典权利未由该声明完全证明 | [`netem_full_list.json`](<C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\wordlist\netem_full_list.json>)；1,106,068 bytes；`6d71a301321056291902bc4804e223c6926dca0d629a45076a6ca5adab185f62` | **yes，条件式**：按其公开 CC 声明、署名、许可链接、修改说明使用；如项目不是非商业用途则不能据此判断可用 | **yes，条件式**：仅非商业；保留署名、许可和变更说明；派生/混合作品需满足 ShareAlike；商业分发为 no |
| Maimemo 英语（一）大纲 CSV | https://github.com/busiyiworld/maimemo-export/blob/main/exported/translation/2025%E7%A1%95%E5%A3%AB%E7%A0%94%E7%A9%B6%E7%94%9F%E8%8B%B1%E8%AF%AD%EF%BC%88%E4%B8%80%EF%BC%89%E5%A4%A7%E7%BA%B2%E8%AF%8D%E6%B1%87.csv；原始下载：https://raw.githubusercontent.com/busiyiworld/maimemo-export/main/exported/translation/2025硕士研究生英语（一）大纲词汇.csv | **C**。仓库是公开的、有 README 和可追溯维护者，但不是官方/出版社发布；文件本身没有官方责任者字段 | 5,687 行；精确去重 5,683；大小写折叠去重 **5,680** | README 自述这是导出墨墨背单词本地词库的项目；作者/代码署名为 `ourongxing`，仓库由 `busiyiworld` 发布；中文翻译自述使用 ECDICT；本文件没有独立编制者声明 | 文件名自称“大纲词汇”；不自称官方；不是“历年高频词”排序文件 | README 明示“仅用于学习，禁止用于商业用途”，并称词库版权归墨墨背单词；代码是 MIT，但这不等于词库数据是 MIT | [`maimemo_2025_masters_english1_outline.csv`](<C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\wordlist\maimemo_2025_masters_english1_outline.csv>)；424,595 bytes；`b715f48a4470750789a3bbfd04d0962e3554e501a24d7f228f5e7f72afab4fe8` | **unknown**。已有学习用途限制和第三方版权声明，没有给本项目登记的明确数据许可；未知不等于可用 | **unknown**；非商业限制不自动授予复制/再分发许可；商业使用至少为 no；安全门禁下不登记、不分发 |
| Maimemo “5500” CSV | https://github.com/busiyiworld/maimemo-export/blob/main/exported/translation/2025%E8%80%83%E7%A0%94%E8%8B%B1%E8%AF%AD%E5%A4%A7%E7%BA%B2%E8%AF%8D%E6%B1%875500.csv；原始下载：https://raw.githubusercontent.com/busiyiworld/maimemo-export/main/exported/translation/2025考研英语大纲词汇5500.csv | **C**，理由同上；文件名不是官方证明 | 5,689 行；精确去重 5,684；大小写折叠去重 **5,681** | 同一 `maimemo-export` 项目；没有本文件独立编制者声明 | 文件名自称“考研英语大纲词汇 5500”；实测并非 5,500 个严格唯一词条；不是官方文件，也不是频次榜 | 同一 README：学习用途、禁止商业用途、词库版权归墨墨；代码 MIT 不覆盖词库版权 | [`maimemo_2025_exam_outline_5500.csv`](<C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\wordlist\maimemo_2025_exam_outline_5500.csv>)；424,772 bytes；`d0148fe0ab0c16e25343a97c8e2f3ee297ae9dddbb8d7624e77e2545e6b6a5c4` | **unknown**；同上，未知不等于可用 | **unknown**；同上，安全门禁下不登记、不分发 |

### 等级解释

- **A**：本次没有取得可安全落盘的官方英语（一）词表电子文件。中国教育考试网检索页确实由教育部教育考试院主办，但公开列表中可直接看到的是 2017 年考试大纲条目，不是本次取得的 2024/2025/2026 词表文件。
- **B**：本次没有找到“出版社/知名机构公开发布、同时明确授予词表数据使用权”的完整英语（一）附录词表。
- **C**：公开项目或培训/个人整理，责任链和方法至少可观察，但不能升级为官方证据。
- **D**：本次未将来源不明、明显拼凑或只提供搜索摘要的材料列入可用候选。

## 2. 实际取得与内容核对

### 2.1 NETEM JSON

已实际 HTTP 取得并保存原始 JSON。解析 JSON 的唯一顶层数组，读取字段 `单词`，未把释义或分类当作词条。实测结果：

- 原始记录：5,530。
- 精确字符串去重：5,530。
- 大小写折叠去重：5,528；重复折叠键为 `may`、`march`，说明“记录数”不能直接当作严格唯一词数。
- 严格字母型 token：5,524；`according to`、`air conditioning`、`ice cream`、`living room`、`ought to`、`owing to` 为带空格短语，不是单个词。
- 顺序：**不是字母序**；这是按频次降序的列表，不能误当成 A-Z 大纲附录原排版。
- 结构：JSON 没有 A/B/C 分节标题；有序号、词频、单词、释义、其他拼写、分类、子分类字段。
- 抽样核对的词（仅列词）：`the`、`be`、`a`、`think`、`factory`、`lung`、`zoom`、`X-ray`、`yourselves`、`zigzag`。这些样本均来自 `单词` 字段，表现为词或词形，不是句子；本报告不抄录例句。

### 2.2 Maimemo 英语（一）大纲 CSV

已实际 HTTP 取得并保存 CSV。文件没有表头，第一行就是 `a`；初始解析曾误把第一行当表头，已纠正并重新计算，最终计数以上表为准。读取第一列作为词条，第二列没有用于报告展示。

- 原始行：5,687。
- 精确字符串去重：5,683。
- 大小写折叠去重：5,680。
- 严格字母型 token：5,678；可见带空格短语 `according to`、`air conditioning`、`ice cream`、`living room`、`ought to`、`owing to`、`per cent`，并有 `café`、`résumé` 等非 ASCII 字符词条。
- 顺序：总体接近按首字母组织，但**严格字母序为 false**，统计到 88 个相邻逆序；开头为 `a`、`an`、`abandon`，不是通常的严格字典序 `a`、`abandon`、`abide`……。
- 结构：没有 A/B/C 分节标题；是无表头两列数据。
- 抽样核对的词（仅列词）：`a`、`an`、`abandon`、`aerial`、`comprehension`、`kindness`、`zoom`、`zigzag`、`zip`、`zone`、`zoo`。本报告不抄录例句。

### 2.3 Maimemo “5500”变体

第二个 CSV 同样实际取得并核对：5,689 行、精确去重 5,684、大小写折叠去重 5,681；严格字母型 token 为 5,681，仍不是严格 A-Z 序列。文件名中的“5500”是发布者命名，不是实测唯一词条数。

### 2.4 官方/中介 PDF 取证

环球青藤页面：https://m.hqqt.com/kaoyan-kaoshi/ziliaolm/1243957.html  
页面给出的 PDF：https://oss-hqwx-video.hqwx.com/考研英语大纲-英语一（2026年）_d97bb471977a26524d7b585749a44487f90830b3.pdf

该 PDF 没有作为候选文件落盘。实际以 HTTP 200 下载到内存，现算结果：34,913,071 bytes，SHA-256 `8bf9e7a910ebc6d5938980111ecea9d0d88a20cdb24b9d216d59f4fe68c0f561`；45 页，文本层仅 2 页。因无文本层，按任务书使用 `pypdfium2` 渲染并目视抽查；可见页包括封面、英语样题、参考答案和页面说明，未取得“附录一词汇表”的可解析内容。由于该 PDF 可能包含试题示例/答案，未把 PDF 或渲染图保留在工作目录。因此它不是本报告的可用词表候选；其来源文件的编制者和授权声明也没有在该中介页面上被清楚给出。

## 3. 独立性与同源判断

计算口径：对英文词条大小写折叠后比较集合；Jaccard = 交集 / 并集；顺序相似度用共同词条序列的 `SequenceMatcher` 比率；“字母规范化序列”先把共同集合各自按字母排序，再比较，用于判断是否共享同一底表而非比较频次排序。

| 比较 | 集合/顺序实测 | 判断 |
|---|---|---|
| NETEM vs Maimemo 英语（一） | 交集 5,527；NETEM 5,528 中覆盖 0.999819；Jaccard **0.972892**；直接顺序相似度 **0.033565**；共同词条按字母规范化后的序列相似度 **1.000000** | 直接顺序低是因为 NETEM 按频次、Maimemo 近似按字母；字母规范化完全一致且 NETEM 几乎全部被覆盖，合理推断共享同一份 5,500 左右的底表或其公开转载版本；不能仅凭此证明具体复制链 |
| Maimemo 英语（一） vs Maimemo “5500” | Jaccard **0.998065**；直接顺序相似度 **0.994630**；共同词条 5,675；第二列完全相同 5,656/5,675，精确注释相同率 **0.996652**；共同词条字母规范化顺序相似度 **1.000000** | **高度疑似同源/同仓库版本变体**，不是两个独立候选 |
| NETEM 注释 vs Maimemo 注释 | 未把中文注释直接判作同源：NETEM 自述人工校对并引用 little dict 等来源，Maimemo README 自述中文翻译使用 ECDICT；两边字段体系也不同 | 词序/词集证据强，但注释来源不同或至少自述不同；不能把任何一边的释义版权自动推给另一边 |

结论：本次检索没有获得两个相互独立、都可升级到 A/B 的 5,500 词表。三个下载文件中，NETEM 与 Maimemo 之间的高词集重合更像共享基础词表；Maimemo 两个文件则几乎可以视为同一来源的版本副本。

## 4. 推荐登记方案与保留

### 推荐候选：NETEM

推荐原因：

- 实测正好 5,530 条记录，接近任务目标；
- 自述来源口径明确：2024 英语（一）大纲底表 + 更广泛语料频次，而不是只用项目已有的三套真题；
- 同一条记录带词频，便于实现“大纲词表打底 + 真题/语料热度标注”；
- 仓库明确写出 CC BY-NC-SA 4.0，至少存在可审计的许可文本。

保留：

- 证据等级只能是 C，不是官方 A；
- 它是频次排序，不是大纲附录原顺序；
- 5,530 记录中有大小写折叠重复和短语；项目需要在内部数据模型中区分 `surface_form`、规范化键和短语；
- README 的 CC 声明是仓库自述，未解决其所引用的官方大纲、外部词典和人工释义的全部上游权利；正式对外发布前应做一次版权/许可复核；
- 若项目是商业服务或商业分发，CC BY-NC-SA 不能直接授权该用途，`may_redistribute=no`。

安全的工作区输出：

- [`netem_5530_words.txt`](<C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\wordlist\netem_5530_words.txt>)：仅保存从 JSON `单词` 字段提取的一词一行词条，保留频次排序；不含例句。
- [`netem_full_list.json`](<C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\wordlist\netem_full_list.json>)：保留原始 JSON 字段，供内部核对词频与来源；按上表许可条件使用。

### 不推荐直接登记：Maimemo

Maimemo 文件在数量和近似 A-Z 形态上有参考价值，但其 README 明确把词库版权归墨墨背单词，并仅给出学习用途/商业禁止语句，没有向本项目授予清晰的数据复制和分发许可。代码的 MIT 标识不能覆盖词库数据。故登记门禁：`may_store=unknown`、`may_redistribute=unknown`；“未知不等于可用”。本次保留下载文件仅为内部取证，不代表获得再利用授权。

## 5. 我试过但没有作为可用候选的路径

| 路径/搜索词 | 结果与失败原因 |
|---|---|
| `考研英语一大纲词汇表`、`考研英语5500词汇表`、`2026考研英语大纲附录 词汇`、`考研英语大纲词汇 完整版`、`考研英语词汇表 pdf`、`考研英语大纲词汇 excel` | 搜到大量培训资料、出版物、转载页；只有标题或摘要不能证明是官方附录，逐一按责任者/许可/可下载内容筛选后未升级为 A/B |
| `考研英文一大綱詞彙表 5500`、`研究生英語 大綱 詞彙 5500 pdf`、`graduate entrance exam English syllabus vocabulary China 5500` | 未找到可核验的官方英语（一）附录词表；英文/繁体结果主要落到自命题科目、英语二或教辅材料 |
| 中国教育考试网考试大纲索引：https://yankao.neea.edu.cn/html1/category/1509/6235-2.htm；2017 英语（一）页：https://yankao.neea.edu.cn/html1/report/16103/1379-1.htm | 这是官方站点，但索引实际公开可见的是旧版 2017 条目；页面没有本次所需的 2024/2025/2026 完整词汇附录下载文件，不能据此生成当前词表 |
| 中国教育在线恩波核心词汇页：https://kaoyan.eol.cn/fu_xi/yingyu/200603/t20060330_170682.shtml | 页面明确写“恩波教育授权”“内容来自《恩波图书考研英语大纲核心词汇》”“未经允许不得转载”；这是教辅出版物正文，不能直接落盘或作为可分发底表 |
| 中国教育在线 A 页：https://kaoyan.eol.cn/kao_shi_da_gang/200603/t20060323_43939.shtml | 只打开到旧版 A 部分，且是 2006 年网页，不是当前完整电子附录；未把其分页面正文下载拼接，避免将旧教辅/转载正文当成官方词表 |
| Iteye/CSDN 资源页：https://www.iteye.com/resource/katagiry-12702598 | 页面称“5500 大纲词汇乱序打印版.xlsx”，但下载需 48 积分/C 币，页面不展示完整文件、责任者或开放许可；未取得完整文件 |
| 环球青藤资料页：https://m.hqqt.com/kaoyan-kaoshi/ziliaolm/1243957.html | 取得的 2026 PDF 为 45 页扫描件，文本层几乎不存在；`pypdfium2` 目视抽查所见为样题/参考答案等，未取得可用词汇附录；PDF 未落盘 |
| GitHub `XiaoJing-C/Express-words_5500`：https://github.com/XiaoJing-C/Express-words_5500 | README 自述数据爬取自 dict.cn，并包含释义、例句、近反义词等查询数据；无清晰词表数据许可，且不是经证实的官方附录；未下载其可能含例句/词典正文的数据库 |
| 新东方、社科赛斯、宏医教育等网页/搜索结果 | 可见“5500”“大纲词汇”等宣传口径，但多数是培训机构页面、分篇文章、领取/下载引导或教辅正文；没有同时满足完整取得、责任者清楚、许可可用三项条件 |

## 6. 没有把握的地方

1. “2024 大纲 5,530”是 NETEM 维护者的来源自述，不是本次从教育部官方附录逐词复核得到的数字；因此只能写“自述/实测”，不能写“官方确认”。
2. NETEM 与 Maimemo 的词集高度相似，支持“共享底表/转载”的推断，但公开文件没有提供完整复制链；无法仅凭数值确定谁先发布、谁复制谁。
3. `may_store`/`may_redistribute` 是工程登记门禁判断，不是法律意见；尤其是 NETEM 对上游官方大纲和外部词典的权利链没有完整证明，正式分发应再取得权利人确认。
4. Maimemo CSV 的“5,500”是文件名，不是实测唯一数；其实际大小写折叠唯一词条超过 5,500，且含短语、派生/异形和个别非 ASCII 词条，不能不清洗就当作规范化单词表。
5. 环球青藤 PDF 的中介页面称“2026 考研英语一大纲”，但文件本身扫描质量和内容范围不足以证明它是人民教育出版社或教育部教育考试院的官方电子版；其授权状态暂时无法验证。

## 7. 可复核文件清单

- [`candidate_download_metadata.json`](<C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\wordlist\candidate_download_metadata.json>)：三份下载文件的 HTTP 状态、字节数、SHA-256、原始行数和初步解析结果。
- [`candidate_analysis.json`](<C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\wordlist\candidate_analysis.json>)：去重、排序、词集/顺序/注释相似度结果。
- [`official_2026_probe.json`](<C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\wordlist\official_2026_probe.json>)：中介 PDF 的内存下载哈希、页数、文本层检查和“不落盘”记录。
- [`netem_5530_words.txt`](<C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\wordlist\netem_5530_words.txt>)：推荐的仅词条候选输出。
- [`maimemo_2025_english1_words.txt`](<C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\wordlist\maimemo_2025_english1_words.txt>)：仅词条形式的 Maimemo 内部比对输出，不代表获得分发许可。

报告中的计数、哈希和相似度均来自本次实际下载/本地解析；来源等级、同源关系和权利门禁属于基于公开声明与实测数据的判断，已与事实分开标注。
