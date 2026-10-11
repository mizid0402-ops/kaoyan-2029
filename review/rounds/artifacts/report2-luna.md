# task4-luna：英语一来源与 burningvocabulary 核验报告

核验日期：2026-09-13  
工作目录：`C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\luna2\`

## 结论先行

1. **burningvocabulary 的三份 PDF 本身不含参考答案。** 我逐节检查了 Use of English、Reading、Translation、Writing：有题干、选项和答题说明，没有选项字母答案表、参考答案或解析。它们可用于核对题面，不能单独用于核对答案。
2. **burningvocabulary 网页产品具有答案功能，但这不等于 PDF 含答案。** 保存的站点页面明确展示“查答案”“专家答案解析”等付费功能；页面中的 `newAnswer` 是加密/不可直接阅读的载荷。本轮没有把网页宣传当作已读出的答案，也没有把 PDF 误判为含答案。
3. **`zhenti.burningvocabulary.com` 与 `zhenti.burningvocabulary.cn` 是同站域名别名，不是两个独立来源。** 三个年份的 `.com` 页面均 200 后跳转到对应 `.cn` 页面；跳转后 HTML 与直接访问 `.cn` 的文件字节和 SHA-256 均相同。
4. **每年可确认的发布来源为 3 个：LazyNote、burningvocabulary、以及一个第三来源；排除 LazyNote 后为 2 个。** 这里的“独立”是发布/内容层面可确认的独立页面或文件，不是已经证明每个站都来自不同考生原稿。上游来源链仍有不确定性。

## 1. burningvocabulary 完整核验

### 1.1 三份 PDF 的来源页面

| 试卷年份 | 来源页面 URL（非 PDF 直链） | 本地原件 | 页面观察 |
|---|---|---|---|
| 2024 | <https://zhenti.burningvocabulary.cn/kaoyan/2024/01> | `claude2/dl/bv_e1_2024.pdf` | 页面标题/产品形态为英语真题在线，提供 PDF 下载和在线练习入口 |
| 2025 | <https://zhenti.burningvocabulary.cn/kaoyan/2025/01> | `claude2/dl/bv_e1_2025.pdf` | 同一产品模板，在线查看、查词、翻译、答案/解析等功能入口 |
| 2026 | <https://zhenti.burningvocabulary.cn/kaoyan/2026/01> | `claude2/dl/bv_e1_2026.pdf` | 同一产品模板，页面展示付费版和答案/解析功能入口 |

页面的自我描述是“英语真题在线官方网站/按试卷排版设计”，并标注“Copyright 2026 @burningvocabulary.cn 旗下独立产品”。据保存页面可确认，它是一个商业化的独立真题练习/题库产品，带在线阅读、查词、翻译、高亮和答案解析等学习功能；**不能据此把它认定为教育考试主管部门或试卷官方发布者**。在保存的 HTML 中没有找到明确的官方上游试卷来源声明。

### 1.2 是否含答案：逐节结果

对三份 PDF 均做了原生文本抽取和逐节检查。它们都是 14 页、具有原生文本层的 PDF；结构均为：

- 第 1 页：Use of English 题干及 1–20 空的文章；
- 第 2 页：1–20 题选项及 Reading Comprehension 开始；
- 第 3–10 页：阅读文章、题干和 A/B/C/D 选项；
- 第 11–14 页：Translation、Part B、Writing 等题目和作答说明。

全文没有发现 `answer key`、`reference answer`、`answers:`、`参考答案`、`correct answer` 等答案键标记，也没有在选项后发现被选中的字母。PDF 中的 “ANSWER SHEET” 是要求考生把答案填到答题卡，并不是答案表。

因此应作如下区分：

| 对象 | 是否含答案 | 证据边界 |
|---|---:|---|
| `bv_e1_2024.pdf`、`bv_e1_2025.pdf`、`bv_e1_2026.pdf` | **否** | 文件中只有题面/选项/作答说明；全文关键词检查和逐节阅读一致 |
| burningvocabulary 在线产品 | **有答案功能的页面证据** | 页面展示“查答案”“专家答案解析”和付费版；`newAnswer` 内容为加密载荷，本轮未取得可读答案正文 |
| 用 burning PDF 核验主源答案 | **不能仅靠 PDF 完成** | 需要另一个能读出答案的页面/文件；本报告用新东方、有路、启航分别补做交叉核验 |

### 1.3 两个域名是否同站

对 2024、2025、2026 的同一路径分别请求两个域名：

| 年份 | `.com` 请求结果 | `.cn` 请求结果 | 跳转后 HTML |
|---|---|---|---|
| 2024 | 200，最终 URI 为 `https://zhenti.burningvocabulary.cn/kaoyan/2024/01` | 200 | 两份均 34,143 字节，SHA-256 `49EC4ED0715CC37231AEBDC401EFD83A2223CF24B96727D5B375455BC84E8409` |
| 2025 | 200，最终 URI 为 `https://zhenti.burningvocabulary.cn/kaoyan/2025/01` | 200 | 两份均 34,324 字节，SHA-256 `6A2486786010EE2E453DC7B06540A4531B0CFD7A1440A9ABCA301C5B10981F60` |
| 2026 | 200，最终 URI 为 `https://zhenti.burningvocabulary.cn/kaoyan/2026/01` | 200 | 两份均 34,123 字节，SHA-256 `2F47A75CABA8C1F8738016EC219506AE5589F3320A1BE0F342C51FD8116F5FD9` |

本地证据为 `luna2/domain_1.html` 至 `domain_6.html`。因此两个域名不能计为两个来源；`.com` 是跳转到 `.cn` 的同站入口/别名。

### 1.4 历史年份

保存的 burningvocabulary 年份索引页面 <https://zhenti.burningvocabulary.cn/kaoyan/> 展示 **2000–2026 年、44 套真题**，其中包括英语一/英语二。故可确认该站页面列有 2023、2022、2021、2020 及更早年份，历史范围向前延伸到 2000 年。这个范围是本次保存页面的快照，页面未来可能变动；本报告没有把未逐个下载的历史年份计入三年来源统计。

## 2. 每年来源表与前五题核对

主源为 LazyNote；主源答案基准来自 `pages/eng1_2024.html` 的已有核验结果，以及本地 `pages/eng1_2025.html`、`pages/eng1_2026.html`。前三年主源完形第 1–5 题答案分别为：2024 `D C B A B`，2025 `B C B C B`，2026 `A D B C B`。

“前五题一致”指题干要点与选项可对应；若来源还公开了答案，则同时核对答案。因为同一场考试的题面天然应相同，题面相同本身不证明上游采集链独立。

### 2024

| 来源 | URL | 类型 | 字节数 / SHA-256 | 前 5 题与主源 | 基于内容的独立性判断 |
|---|---|---|---|---|---|
| LazyNote 主源 | <https://english-exam.lazynote.cn/kaoyan/paper/2024-english-one/> | 原生文本层、排版 PDF | 220,061；`32cabc2db207d257696a41879e1c081ef5bc7c5385a5278e8fa75fa2d518238a` | 基准：`D C B A B` | 主源 |
| burningvocabulary | <https://zhenti.burningvocabulary.cn/kaoyan/2024/01> | 原生文本层、原卷排版 PDF | 739,386；`969cf8c175e037eebecb289293dbb2457fde4fc696b42315c0204fe59f02a465` | 题干/选项 5/5；PDF 无答案 | 与 LazyNote 是不同站点、不同排版文件；题面相同是同一考试的预期结果，不能证明上游稿件不同 |
| 新东方在线 | <https://kaoyan.koolearn.com/20231223/1678741.html> | HTML 页面 + 图片；页面不是原生试卷 PDF | 页面 147,114；`2AA7114CB7F5305B85BD9243223598D0E16E3659861C0E8819FF8B8D1BA6760D`；答案图 54,795；`C04ED41ED3185C2458DA21329310B9D967868775DCF0480886F5AC56A6F3A42B` | 题干/选项 5/5；答案图为 `D C B A B` | 机构 HTML/图片整理，解析/答案呈现方式不同于两份 PDF；可确认是独立发布物，但图片的上游原卷来源未证明 |

新东方页面实际下载到本地 `luna2/xdf_1.html`，并实际下载了题面图 `xdf_assets/asset_1.jpg`（103,650 字节，SHA-256 `D533A2F162AE75558A86A48434F3CE02003617DC9A977D404FB14C27C6E491EA`）和答案图 `xdf_assets/asset_2.jpg`。答案图直接显示前五题为 D、C、B、A、B。

### 2025

| 来源 | URL | 类型 | 字节数 / SHA-256 | 前 5 题与主源 | 基于内容的独立性判断 |
|---|---|---|---|---|---|
| LazyNote 主源 | <https://english-exam.lazynote.cn/kaoyan/paper/2025-english-one/> | 原生文本层、排版 PDF | 190,726；`35263e112fee8b11014b45bbcc137ccd5341fccd365d3da5dfcc2b32d60495df` | 基准：`B C B C B` | 主源 |
| burningvocabulary | <https://zhenti.burningvocabulary.cn/kaoyan/2025/01> | 原生文本层、原卷排版 PDF | 530,380；`088a555c8e216be07b47ccb70324d5e9c2d8fe1efb4058fef60c08c119380473` | 题干/选项 5/5；PDF 无答案 | 不同站点和文件结构；题面相同不等于来源链已证独立 |
| 有路教育 | <https://www.youlu.com/kaoyan/article/CA20241222010000000012> | 公开 HTML；完形题面 + 解析，不是全卷 | 106,469；`7D3EE10DBAFACC49D4AF17F7E2BA71434B4BA8F34207308D943BB930495C6663` | 前五题语义/选项可对应；答案 `B C B C B` | 独立机构的文本整理；可观察到少量转录差异，如缺少冠词、`ricers` 拼写错误，说明不是对 LazyNote 文件的字节复制；仍不能证明上游原稿不同 |

有路页面实际保存为 `luna2/youlu2025.html`。页面公开包含 1–20 题题干、选项和逐题解析，不需要登录才能核对前五题；它只覆盖完形部分，不能写成“完整试卷来源”。

### 2026

| 来源 | URL | 类型 | 字节数 / SHA-256 | 前 5 题与主源 | 基于内容的独立性判断 |
|---|---|---|---|---|---|
| LazyNote 主源 | <https://english-exam.lazynote.cn/kaoyan/paper/2026-english-one/> | 原生文本层、排版 PDF | 189,386；`1bb250a110c4a6eff0f5c72f3d25ee346f5d766b085e5d47589eb0dc11a193a9` | 基准：`A D B C B` | 主源 |
| burningvocabulary | <https://zhenti.burningvocabulary.cn/kaoyan/2026/01> | 原生文本层、原卷排版 PDF | 482,661；`945d409b044c7a2b956c22a8a32748742fe4f2eda27e60b55e0c6ddff56f5d38` | 题干/选项 5/5；PDF 无答案 | 不同站点和文件结构；题面相同不等于来源链已证独立 |
| 启航英语一参考答案及解析 | <https://aged-jixun-cdn.iqihang.com/2025/1221/20251221052326101.pdf> | 20 页、原生文本层 PDF；机构考后重构/回忆材料，含解析 | 1,609,937；`5F5660021FC2FE03F4D51D37D72D562A8284AC3ABDBC85B71236ECB469034E30` | 前五题题干/选项可对应；答案 `A D B C B` | 解析文本和版式不同于 LazyNote/burning；可确认是独立发布文件，但其原始采集链和“回忆版”性质不能升级为官方原卷 |

启航 PDF 实际保存为 `luna2/qihang2026.pdf`。第 1 页即出现“参考答案及解析”，第 1–2 页可直接读出完形前五题答案；它不是 burningvocabulary 的答案附件，也没有被计入 burningvocabulary 文件。

### 2.4 年度计数的准确含义

| 年份 | 可确认发布来源总数 | 排除 LazyNote 后 | 计数成员 |
|---|---:|---:|---|
| 2024 | 3 | 2 | LazyNote、burningvocabulary、新东方 |
| 2025 | 3 | 2 | LazyNote、burningvocabulary、有路 |
| 2026 | 3 | 2 | LazyNote、burningvocabulary、启航 |

`hit2024_e1.pdf` 与 `bv_e1_2024.pdf` 字节和 SHA-256 完全相同（均为 739,386 字节、`969cf8c175e037eebecb289293dbb2457fde4fc696b42315c0204fe59f02a465`），所以没有把它算成第四个来源。`static.kaoyan.cn` 的多个文件也按任务书要求视为一个聚合来源，并且没有计入上表。

## 3. 我试过但没找到的路径

以下是检索路径和实际结论；搜索结果中的中文聚合站、标题页或与英语一不匹配的材料没有被冒充成第三来源。

1. 英文关键词：`2026 Chinese postgraduate entrance examination English I answers`、`2025 Chinese postgraduate entrance exam English one question answer`、`2026 postgraduate entrance exam China English I answer key`。结果主要回到中国机构站、LazyNote 或 static 聚合 PDF；没有找到一个可验证、独立的英文海外发布站。
2. GitHub：检索 `site:github.com 2026 考研 英语一 真题 答案`、`site:github.com "Chinese postgraduate" "English I" exam`，并检查了 <https://github.com/neville-studio/408-exam-paper> 和 <https://github.com/songmuhan/408> 的仓库/文件范围。后两个是 408 计算机资料，不能用于英语一；前述英文检索未找到可实际核对英语一前五题的 GitHub 文件。
3. Internet Archive：尝试 `2026 China postgraduate English exam`、`2026 Chinese postgraduate English exam` 及 <https://archive.org/advancedsearch.php?q=2026+Chinese+postgraduate+English+exam&output=json>。没有找到可核对中国考研英语一题面和答案的海外存档文件；命中项属于其他国家/其他考试体系或无关资料。
4. Scribd：尝试 `2026 考研英语一`、`2024 考研英语一答案解析`。曾看到 2024 英语一答案解析预览，但受预览/登录限制，不能作为本轮实际下载的强第三来源；它也没有改变按新东方实际下载页面+答案图计数的结果。
5. 英文描述中国考研的普通网站：搜索结果中出现 Reddit、大学招生页和其他考试资料，但没有能同时提供本题年份、英语一完形题面和前五题答案的可核验页面，因此未计入。

## 4. 没有把握的地方

1. **上游原稿是否真正独立。** 不同发布域名和不同排版只能证明发布层面不同；2024–2026 同一场考试的题面与答案可能都来自同一份考生回忆或互相转载，现有证据不足以重建每站的采集链。
2. **burningvocabulary 的在线答案是否对匿名访问者完整开放。** 页面确实展示答案/专家解析功能，且保存页有加密 `newAnswer` 字段和付费版信息；本轮没有登录或解密，因此不能声称已验证其在线答案正文，也不能据此说 PDF 含答案。
3. **burningvocabulary 的官方性。** 页面使用“官方网站”等产品文案，但保存 HTML 没有给出考试主管部门或试卷出版方的上游证明；本报告将其归类为商业独立题库产品，而不是官方原卷发布者。
4. **2024 新东方图片的原卷性质。** 页面和答案图内容足以核对前五题，但图片可能是机构排版、扫描或回忆重制；没有把它提升为官方原始扫描件。
5. **2025 有路的覆盖范围。** 它公开的是完形题面和解析，不是整套试卷；前五题核对可靠，但不能用它证明阅读、翻译和写作部分的来源或答案。
6. **2026 启航 PDF 的原始性质。** PDF 带完整解析且文本层清楚，但属于机构考后重构/回忆材料，不是官方原始扫描；答案一致提高交叉可信度，却不能证明原卷真实性或上游独立性。
7. **历史年份结论是页面快照。** 2000–2026 的年份范围来自本轮保存的年份索引；未对每个年份逐一下载，未来页面改版也可能改变展示范围。
8. **国外路径的“找不到”有范围限制。** 这是本轮搜索引擎、公开仓库和公开页面内未找到可核验结果，不等于私人网盘、登录后页面或未被索引的资料绝对不存在。

## 5. 实测与推断的边界

### 实测

- 六个 burningvocabulary 页面请求的状态、最终 URI、HTML 字节数和 SHA-256；`.com` 与 `.cn` 三年逐年同哈希。
- 三份 burning PDF 的页数、字节数、SHA-256、原生文本层和逐节文本；没有读到答案键。
- 2024 新东方 HTML、题面图、答案图；2025 有路 HTML；2026 启航 PDF，均已保存到 `luna2` 并自行计算哈希。
- 三年主源与第三来源的完形前五题题干/选项对应关系；答案分别核对为 2024 `D C B A B`、2025 `B C B C B`、2026 `A D B C B`。
- `hit2024_e1.pdf` 与 burning 2024 PDF 完全同哈希；static 聚合源未拆成多个独立来源。

### 推断

- burningvocabulary 是商业化独立题库/学习平台，而不是官方考试发布机构：这是基于页面产品功能、版权文案和缺少官方上游声明的分类判断。
- 每年排除 LazyNote 后有 2 个可计数的发布来源：burningvocabulary 加一个实际核验的机构第三来源；“上游原稿各自独立”不能从当前材料推出。
- `.com` 与 `.cn` 是同站别名：这是由跳转目标、最终 URI 和逐年相同 HTML 哈希支持的高可信判断，不是仅凭相似品牌名推断。

## 6. 本地证据索引

- burning 原件：`C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\claude2\dl\bv_e1_2024.pdf`、`bv_e1_2025.pdf`、`bv_e1_2026.pdf`。
- 主源页面：`C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\pages\eng1_2026.html`，以及同目录 2025 页面；2024 答案基准沿用已核验材料。
- 域名对照：`C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\luna2\domain_1.html` 至 `domain_6.html`。
- 第三来源：`xdf_1.html`、`xdf_assets/asset_1.jpg`、`xdf_assets/asset_2.jpg`、`youlu2025.html`、`qihang2026.pdf`。
- 本报告未访问、未修改 `F:\workspace\kaoyan-ai-system`，也未执行 Git。
