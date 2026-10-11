# 附件审计专用证据包（自包含 / 无需联网 / 无需读原始文件）

本文件由 `tools/build_evidence_bundle.py` 生成。**它验证了什么、没验证什么，必须分清**
（第一版把这一点说过头了，被独立审查当场拆穿）：

**已验证（机器校验，可复核）**
- 总表的 URL / HTTP 状态 / 响应字节数 / 响应 sha256 由生成器从 `index.json` 读出，
  而 `index.json` 是抓取器写入的响应记录。生成器**不修改**这些字段。
- 构建时对每个本地证据文件现算 sha256，并打印在本表「本地文件 sha256」列；
  **该列与「响应 sha256」不等是预期的**——文本页面被抓取器解码后重新编码为 UTF-8 落盘，
  只有二进制载荷（PDF）才逐字节相同。第一版把「不等」放在「一致」列里，是表述错误。

**未验证（独立审查指出的缺口，必须知道）**
- 摘录文本与**响应字节之间没有密码学绑定**：它取自重编码后的本地文件，
  而本地文件的哈希不等于任何被记录的响应哈希。因此「摘录正文被改过一个字」这件事，
  本包与 `index.json` 都不会发现。信任根仍是本项目自己两个工具的自我报告。
- 没有外部锚点（archive.org 快照、第三方时间戳、独立第二次抓取）。
- 正确修法（尚未实施）：抓取器应把**原始响应字节原样落盘**，摘录直接取自该字节流，
  这样摘录的哈希就能钉在响应哈希上。已记入本轮遗留项。

**规则**：不得联网；不得再读 `cache/evidence/` 下的原始文件；不得运行抓取工具。
全部判定只能基于本文件给出的元信息与摘录。

## 抓取元信息总表

| # | URL | HTTP | 响应字节 | 响应 sha256 | 本地文件 sha256 |
|---|---|---:|---:|---|---|
| A1 | https://www.moe.gov.cn/srcsite/A15/moe_778/s3261/202509/t20250918_1413836.html | 200 | 76773 | `276d67be6ac5bbdc` | `16c8a028a84defa2` |
| A2 | https://www.zxhsd.com/kgsm/ts/2025/10/17/6704598.shtml | 200 | 48508 | `e64c108a5ba9aa01` | `f6abb0f240355e9a` |
| A3 | https://www.megbook.com.tw/mall/detail.jsp?proID=4159518 | 200 | 102 | `c94f0fcc209d647a` | `962fbb8eb71bd4b8` |
| A4 | https://aus.zxhsd.com/kgsm/ts/2025/10/17/6694606.shtml | 200 | 25173 | `23125bac723b679e` | `be316275e7514b46` |
| A5 | https://search.megbook.com.tw/mall/detail.jsp?proID=4159208 | 200 | 8045 | `39e167cba7f8e0c5` | `0e833aaca0545314` |
| B1 | https://www.chinakaoyan.com/info/article/id/527517.shtml | 200 | 29747 | `20c2ea3eecef20ae` | `bdbbbce8ee550a11` |
| B2 | https://download.chinakaoyan.com/list-show-218527.html | 200 | 17702 | `93b335a8c3a78ab7` | `8c2b13e2e174ea8e` |
| B3 | https://www.tjrac.edu.cn/sxjxb/info/1340/3002.htm | 200 | 16738 | `5f508d8a5a75fb8b` | `397083ad36ee1d62` |
| B4 | https://m.juyingonline.com/news/356469.html | 200 | 21108 | `07ccc84435ffa8fc` | `ff4b263c9e1afec8` |
| B5 | https://m-jixun.iqihang.com/kyzt/shuxue/ | 200 | 121054 | `f6b0da6925cc565b` | `4a897a4c170ab853` |
| B6 | https://m-jixun.iqihang.com/kyzt/shuxue/shuxue1/2025703715.html | 200 | 106638 | `759f721ccd469c75` | `def7c846ccd4675b` |
| B7 | https://m.juyingonline.com/news/357790.html | 200 | 24472 | `835ed3bc3a850abf` | `c42f94f1579b9b0a` |
| C1 | https://english-exam.lazynote.cn/kaoyan/paper/2024-english-one/ | 200 | 229272 | `6b7be9b615f99cae` | `9bf6762d9c53e204` |
| C2 | https://www.chinakaoyan.com/info/article/id/526859.shtml | 200 | 33869 | `e2f45c7cc3590d2a` | `129d444f3fa025ab` |
| C3 | https://english-exam.lazynote.cn/kaoyan/paper/2025-english-one/ | 200 | 225659 | `25b207451db2af61` | `ed78b125222a8664` |
| C4 | https://kaoyan.xdf.cn/202501/14059107.html | 200 | 64814 | `4b94689c98c01247` | `11867f78cc3af8a8` |
| C5 | https://www.yanbbs.com/nd.jsp?id=47 | 抓取失败 | — | `—` | `—` |
| C6 | https://english-exam.lazynote.cn/kaoyan/paper/2026-english-one/ | 200 | 228441 | `3c64ff4d94d61070` | `c8c7b27219c19279` |
| C7 | https://static.kaoyan.cn/file/question/2025/12/27/4644ae5c80a12b9a2135e54dc56c0724.pdf | 200 | 903877 | `d33c331413174826` | `d33c331413174826` |
| C8 | https://english-exam.lazynote.cn/kaoyan/english-one/ | 200 | 157020 | `806f02f3ff0dc6a9` | `a3d6d5dbd93c7c13` |

### 二进制载荷的自证

- C7: magic bytes `%PDF-1.3
%Ã¢Ã£Ã`（有效 PDF 应以 `%PDF-` 开头）

## 逐条证据摘录

### A1 — 2026 研考初试时间 2025-12-20—21；数学一/英语一为全国统一命题科目

- URL: `https://www.moe.gov.cn/srcsite/A15/moe_778/s3261/202509/t20250918_1413836.html`
- HTTP 200；最终 URL `http://www.moe.gov.cn/srcsite/A15/moe_778/s3261/202509/t20250918_1413836.html`；Content-Type `text/html`；响应字节 76773；sha256 `276d67be6ac5bbdc36cd900d9c6314c1dbac7f39e0a829083e8672c15c0331f9`；标题：教育部关于印发《2026年全国硕士研究生招生工作管理规定》的通知 - 中华人民共和国教育部政府门户网站
- 探针检查（主张关键词是否真的出现在页面里）：
    - `12月20日` → 命中

      ```text
      ［已删去可能属真题/答案原文的 92 字符中文片段］</p>
      <p> 鼓励招生单位积极选择使用上述全国统一命题科目。</p>
      <p> 第三十五条 招生单位须按教育部有关规定确定考试科目并使用相关试题。</p>
      <p> 第三十六条 初试方式均为笔试。初试时间为2025年12月20日至21日。其中，12月20日上午8:30—11:30，思想政治理论或管理类综合能力；12月20日下午14:00—17:00，外国语；12月21日上午8:30—11:30，业务课（一）或专业基础综合；12月21日14:00开始，业务课（二）。考试时间以北京时间为准。</p>
      <p> 不在规定日期举行的考试，一律不予承认。具体考试时间、考试科目及有关要求等由报考点和招生单位公布。</p>
      <p> 第三十七条 初试的组织工作和考务工作由教育部教育考试院及各级教育招生考试机构按照相关文件规定执行。</p>
      <p> 第三十八条 因试卷错寄、漏寄、邮递故障等非考生本人原因而无法正常考试的考生可参加补考。</p>
      <p> ［已删去可能属真题/答案原文的 104 字符中文片段］</p>
      <p> 各补考科目均由招生单位命题。补考试题的形式和难易程度应与原试题相一致。</p>
      <p align="center"><strong>第六章 评卷<
      ```
    - `12月21日` → 命中

      ```text
      综合（法学）、经济类综合能力、教育综合。</p>
      <p> 鼓励招生单位积极选择使用上述全国统一命题科目。</p>
      <p> 第三十五条 招生单位须按教育部有关规定确定考试科目并使用相关试题。</p>
      <p> 第三十六条 初试方式均为笔试。初试时间为2025年12月20日至21日。其中，12月20日上午8:30—11:30，思想政治理论或管理类综合能力；12月20日下午14:00—17:00，外国语；12月21日上午8:30—11:30，业务课（一）或专业基础综合；12月21日14:00开始，业务课（二）。考试时间以北京时间为准。</p>
      <p> 不在规定日期举行的考试，一律不予承认。具体考试时间、考试科目及有关要求等由报考点和招生单位公布。</p>
      <p> 第三十七条 初试的组织工作和考务工作由教育部教育考试院及各级教育招生考试机构按照相关文件规定执行。</p>
      <p> 第三十八条 因试卷错寄、漏寄、邮递故障等非考生本人原因而无法正常考试的考生可参加补考。</p>
      <p> ［已删去可能属真题/答案原文的 104 字符中文片段］</p>
      <p> 各补考科目均由招生单位命题。补考试题的形式和难易程度应与原试题相一致。</p>
      <p align="center"><strong>第六章 评卷</strong></p>
      <p> 第三十九条 全国统一命题科目的评卷工作实行省级招委会统一领导、省级教育招生考试机构统一组织、评卷点具体实施的管
      ```
    - `统一命题` → 命中

      ```text
      p> 招生单位根据下达的招生计划、社会需求和办学条件，依据有关政策规定确定本单位各学科专业的招生人数。</p>
      <p> 第六条 ［已删去可能属真题/答案原文的 83 字符中文片段］</p>
      <p> ［已删去可能属真题/答案原文的 66 字符中文片段］</p>
      <p> ［已删去可能属真题/答案原文的 144 字符中文片段］</p>
      <p> 第七条 全国硕士研究生招生考试试题（包括副题）、参考答案、评分参考（指南）等应当按照教育工作国家秘密范围的有关规定严格管理。</p>
      <p> 第八条 硕士研究生学习方式分为全日制和非全日制。全日制和非全日制研究生考试招生依据国家统一要求，执行相同的政策和标准。</p>
      <p> 硕士研究生就业方式分为定向就业和非定向就业。</p>
      <p> 第九条 硕士研究生考试招生工作坚持重大事项集体研究、集体决策，严格规范管理，落实考试招生回避、信息公开等要求。</p>
      <p> 第十条 考生应诚信参加考试，自觉遵守考试管理各项规定。</p>
      <p align="center"><strong>第二章 管理机构及其职责</strong></p
      ```

### A2 — 数学大纲 ISBN 9787107404689 / 157 页 / 29.00 元 / 含 2024-2025 试题及参考答案

- URL: `https://www.zxhsd.com/kgsm/ts/2025/10/17/6704598.shtml`
- HTTP 200；最终 URL `https://www.zxhsd.com/kgsm/ts/2025/10/17/6704598.shtml`；Content-Type `text/html`；响应字节 48508；sha256 `e64c108a5ba9aa01407e34b5705b4dceccc2159d3c5252cd0b81ff2655a44c05`；标题：2026年全国硕士研究生招生考试数学考试大纲：编者:教育部教育考试院|责编:白文亭 : 数理化学科 :数理化学科 :数学 :浙江新华书店网群
- 探针检查（主张关键词是否真的出现在页面里）：
    - `9787107404689` → 命中

      ```text
      <div class="ProductsInfo">
       <ul>
       <li>
       <script language="javascript">
       document.write(xjm_6704598+"：<strong>￥"+xsj_6704598+"</strong>元");
       </script>
       </li>
       <li>定价：<del> ￥29 </del>元</li>
       <li>ISBN：9787107404689</li>
       <li>开 本：32开 平装 </li>
       </ul>
       <ul>
       <li>&nbsp;</li>
       <li>折扣：<script language="javascript">document.write(zk_6704598);</script>折</li>
      ```
    - `157` → 命中

      ```text
      >&nbsp;</li>
       <li>折扣：<script language="javascript">document.write(zk_6704598);</script>折</li>
       <li>出版社：［HTML 属性已删］人民教育</a></li>
       <li>页数：157页</li>
       </ul>
       <ul>
       <li>作者：［HTML 属性已删］编者:教育部教育...</a></li>
       <li>立即节省：<script language="javascript">document.write(js_6704598);</script>元</li>
       <li>2025-09-01 第1版 </li>
       <li>2025-09-01 第1次印刷</li>
       </ul>
       ［HTML 属性已删］
       ［HTML 属性已删］
       ［HTML 属性已删］
      ```
    - `29` → 命中

      ```text
      究生招生考试数学考试大纲"></a>
       </div>
       <div class="ProductsInfo">
       <ul>
       <li>
       <script language="javascript">
       document.write(xjm_6704598+"：<strong>￥"+xsj_6704598+"</strong>元");
       </script>
       </li>
       <li>定价：<del> ￥29 </del>元</li>
       <li>ISBN：9787107404689</li>
       <li>开 本：32开 平装 </li>
       </ul>
       <ul>
      ```
    - `考试内容和考试要求` → 命中

      ```text
      ［已删去可能属真题/答案原文的 63 字符中文片段］2026年全国硕士研究生招生考试数学科目的考查。</p>
      
      
      
      
      
      
      
       <div class="title"><h3>目录</h3></div>
       <p>I 考试性质<br>Ⅱ 考查目标<br>Ⅲ 试卷分类及使用专业<br>Ⅳ 考试形式和试卷结构<br>V 考试内容和考试要求<br>数学(一)<br>数学(二)<br>数学(三)<br>Ⅵ 题型示例及参考答案<br>题型示例<br>参考答案<br>附录<br>2024年全国硕士研究生招生考试<br>数学试题及参考答案<br>数学(一)试题<br>数学(一)试题参考答案<br>数学(二)试题<br>数学(二)试题参考答案<br>数学(三)试题<br>数学(三)试题参考答案<br>2025年全国硕士研究生招生考试<br>数学试题及参考答案<br>数学(一)试题<br>数学(一)试题参考答案<br>数学(二)试题<br>数学(二)试题参考答案<br>数学(三)试题<br>数学(三)试题参考答案<br></p>
      
      
      
      
      ```
    - `数学(一)` → 命中

      ```text
      大纲也为教师开展教学活动提供了参考，有助于他们更精准地指导学生备考，提升学生的应考能力，以更好地适应2026年全国硕士研究生招生考试数学科目的考查。</p>
      
      
      
      
      
      
      
       <div class="title"><h3>目录</h3></div>
       <p>I 考试性质<br>Ⅱ 考查目标<br>Ⅲ 试卷分类及使用专业<br>Ⅳ 考试形式和试卷结构<br>V 考试内容和考试要求<br>数学(一)<br>数学(二)<br>数学(三)<br>Ⅵ 题型示例及参考答案<br>题型示例<br>参考答案<br>附录<br>2024年全国硕士研究生招生考试<br>数学试题及参考答案<br>数学(一)试题<br>数学(一)试题参考答案<br>数学(二)试题<br>数学(二)试题参考答案<br>数学(三)试题<br>数学(三)试题参考答案<br>2025年全国硕士研究生招生考试<br>数学试题及参考答案<br>数学(一)试题<br>数学(一)试题参考答案<br>数学(二)试题<br>数学(二)试题参考答案<br>数学(三)试题<br>数学(三)试题参考答案<br></p>
      
      
      
      
      ```

### A3 — 台湾大书城数学大纲核验页

- URL: `https://www.megbook.com.tw/mall/detail.jsp?proID=4159518`
- HTTP 200；最终 URL `https://www.megbook.com.tw/mall/detail.jsp?proID=4159518`；Content-Type `text/html;charset=UTF-8`；响应字节 102；sha256 `c94f0fcc209d647a8e185af472b399083143816673c9bed39bb5602ed2f37406`；标题：（空）
- 探针检查（主张关键词是否真的出现在页面里）：
    - `9787` → **未命中**
    - `数学` → **未命中**

### A4 — 英语一大纲 ISBN 9787107404603 / 236 页 / 附录三含 2024-2025 试题及参考答案 / 附录一词汇表

- URL: `https://aus.zxhsd.com/kgsm/ts/2025/10/17/6694606.shtml`
- HTTP 200；最终 URL `https://aus.zxhsd.com/kgsm/ts/2025/10/17/6694606.shtml`；Content-Type `text/html`；响应字节 25173；sha256 `23125bac723b679e9e29f0198da8cff62c6259573f8ae40bbcdb0daf273b2fb3`；标题：澳大利亚新华书店网
- 探针检查（主张关键词是否真的出现在页面里）：
    - `9787107404603` → 命中

      ```text
      考试大纲(非英语专业)"></a>
       </li>
       <li class="infocontent">
       <ul>
       <li class="sm">2026年全国硕士研究生招生考试英语&lt;一&gt;考试大纲(非英语专业)</li>
       <li>
       <ul class="l">
       <li>作者：编者:教育部教育考试院|责编:张译峻</li>
       <li>出版社：人民教育</li>
       <li>ISBN：9787107404603</li>
       </ul>
       <ul class="r">
       <li>出版日期：2025/09/01</li>
       <li>页数：236</li>
      ```
    - `236` → 命中

      ```text
      6年全国硕士研究生招生考试英语&lt;一&gt;考试大纲(非英语专业)</li>
       <li>
       <ul class="l">
       <li>作者：编者:教育部教育考试院|责编:张译峻</li>
       <li>出版社：人民教育</li>
       <li>ISBN：9787107404603</li>
       </ul>
       <ul class="r">
       <li>出版日期：2025/09/01</li>
       <li>页数：236</li>
       </ul>
       </li>
       <li class="price"></li>
       <li class="libuycar">
      ```
    - `附录三` → 命中

      ```text
      考研英语（一）中取得理想成绩。
       </li>
       <li>
       <h1>作者介绍</h1>
      
       </li>
       <li>
       <h1>目录</h1>
       Ⅰ 考试性质<br>Ⅱ 考查目标<br>Ⅲ 考试形式、考试内容与试卷结构<br>Ⅳ 题型示例及参考答案<br>附录一<br>词汇表<br>部分国家（或地区）名称及相关信息<br>大洲名和大洋名<br>附录二<br>常用前缀和后缀<br>常见缩写词<br>附录三<br>2024年全国硕士研究生招生考试<br>英语（一）试题<br>2024年全国硕士研究生招生考试<br>英语（一）试题参考答案<br>2025年全国硕士研究生招生考试<br>英语（一）试题<br>2025年全国硕士研究生招生考试<br>英语（一）试题参考答案<br><BR>
       </li>
       </ul>
       </div>
       <!-- end left side -->
      
      ```
    - `试题参考答案` → 命中

      ```text
      >目录</h1>
       Ⅰ 考试性质<br>Ⅱ 考查目标<br>Ⅲ 考试形式、考试内容与试卷结构<br>Ⅳ 题型示例及参考答案<br>附录一<br>词汇表<br>部分国家（或地区）名称及相关信息<br>大洲名和大洋名<br>附录二<br>常用前缀和后缀<br>常见缩写词<br>附录三<br>2024年全国硕士研究生招生考试<br>英语（一）试题<br>2024年全国硕士研究生招生考试<br>英语（一）试题参考答案<br>2025年全国硕士研究生招生考试<br>英语（一）试题<br>2025年全国硕士研究生招生考试<br>英语（一）试题参考答案<br><BR>
       </li>
       </ul>
       </div>
       <!-- end left side -->
      
       <!-- navrightside -->
      
       <div class="pagerightside">
       <div class="relevance">
       <h1><span class="sale_icon_01 png">同类热销排行榜</span></h1>
      
      
      ```
    - `词汇表` → 命中

      ```text
      ［已删去可能属真题/答案原文的 80 字符中文片段］
       </li>
       <li>
       <h1>作者介绍</h1>
      
       </li>
       <li>
       <h1>目录</h1>
       Ⅰ 考试性质<br>Ⅱ 考查目标<br>Ⅲ 考试形式、考试内容与试卷结构<br>Ⅳ 题型示例及参考答案<br>附录一<br>词汇表<br>部分国家（或地区）名称及相关信息<br>大洲名和大洋名<br>附录二<br>常用前缀和后缀<br>常见缩写词<br>附录三<br>2024年全国硕士研究生招生考试<br>英语（一）试题<br>2024年全国硕士研究生招生考试<br>英语（一）试题参考答案<br>2025年全国硕士研究生招生考试<br>英语（一）试题<br>2025年全国硕士研究生招生考试<br>英语（一）试题参考答案<br><BR>
       </li>
       </ul>
       </div>
       <!-- end left side -->
      
      ```

### A5 — 台湾大书城英语一大纲页

- URL: `https://search.megbook.com.tw/mall/detail.jsp?proID=4159208`
- HTTP 200；最终 URL `https://search.megbook.com.tw/mall/detail.jsp?proID=4159208`；Content-Type `text/html;charset=UTF-8`；响应字节 8045；sha256 `39e167cba7f8e0c5cd23e10122433c8c6bfb25ef4a4391175b8a002d02c6285e`；标题：商品詳情 - 《2026年全国硕士研究生招生考试英语（一）考试大纲（非英语专业）》 - 教育考试院 - 人民教育出版社 - 台灣大書城 megBook Store
- 探针检查（主张关键词是否真的出现在页面里）：
    - `9787` → 命中

      ```text
      html>
      <head>
      <title>商品詳情 - 《2026年全国硕士研究生招生考试英语（一）考试大纲（非英语专业）》 - 教育考试院 - 人民教育出版社 - 台灣大書城 megBook Store</title>
      ［HTML 属性已删］
      ［HTML 属性已删］
      ［HTML 属性已删］
      <meta content="megBook" name=Author>
      ［HTML 属性已删］
      ［HTML 属性已删］
      ［HTML 属性已删］
      </head>
      ［HTML 属性已删］
      <body
      ```
    - `英语` → 命中

      ```text
      <html>
      <head>
      <title>商品詳情 - 《2026年全国硕士研究生招生考试英语（一）考试大纲（非英语专业）》 - 教育考试院 - 人民教育出版社 - 台灣大書城 megBook Store</title>
      ［HTML 属性已删］
      ［HTML 属性已删］
      ［HTML 属性已删］
      <meta content="megBook" name=Author>
      ［HTML 属性已删］
      ［HTML 属性已删］
      ［HTML 属性已删］
      </head>
      ［HTML 属性已删］
      <bod
      ```

### B1 — 2024 数学一真题及答案（网络整理 PDF）

- URL: `https://www.chinakaoyan.com/info/article/id/527517.shtml`
- HTTP 200；最终 URL `https://www.chinakaoyan.com/info/article/id/527517.shtml`；Content-Type `text/html; charset=gb2312`；响应字节 29747；sha256 `20c2ea3eecef20aed74f94226d3e1857a5c4622e2e7e1dc1be40c33fb90bc1b0`；标题：2024年考研数学一真题及答案（PDF版） - 中国考研网
- 探针检查（主张关键词是否真的出现在页面里）：
    - `2024` → 命中

      ```text
      ［已删去可能属真题/答案原文的 69 字符外文片段］>
      ［HTML 属性已删］
      <head>
      ［HTML 属性已删］
      <title>2024年考研数学一真题及答案（PDF版） - 中国考研网</title>
      ［HTML 属性已删］
      ［HTML 属性已删］
      ［HTML 属性已删］
      ［HTML 属性已删］
      ［HTML 属性已删］</script>
      ［HTML 属性已删］</script>
      <script src="［已删去可能属真题/答案原文的 53 字符外文片段］
      ```
    - `数学一` → 命中

      ```text
      /［已删去可能属真题/答案原文的 61 字符外文片段］>
      ［HTML 属性已删］
      <head>
      ［HTML 属性已删］
      <title>2024年考研数学一真题及答案（PDF版） - 中国考研网</title>
      ［HTML 属性已删］
      ［HTML 属性已删］
      ［HTML 属性已删］
      ［HTML 属性已删］
      ［HTML 属性已删］</script>
      ［HTML 属性已删］</script>
      <script src="［已删去可能属真题/答案原文的 60 字符外文片段］
      ```
    - `真题` → 命中

      ```text
      " "［已删去可能属真题/答案原文的 56 字符外文片段］>
      ［HTML 属性已删］
      <head>
      ［HTML 属性已删］
      <title>2024年考研数学一真题及答案（PDF版） - 中国考研网</title>
      ［HTML 属性已删］
      ［HTML 属性已删］
      ［HTML 属性已删］
      ［HTML 属性已删］
      ［HTML 属性已删］</script>
      ［HTML 属性已删］</script>
      <script src="［已删去可能属真题/答案原文的 62 字符外文片段］=
      ```
    - `答案` → 命中

      ```text
      ［已删去可能属真题/答案原文的 56 字符外文片段］>
      ［HTML 属性已删］
      <head>
      ［HTML 属性已删］
      <title>2024年考研数学一真题及答案（PDF版） - 中国考研网</title>
      ［HTML 属性已删］
      ［HTML 属性已删］
      ［HTML 属性已删］
      ［HTML 属性已删］
      ［HTML 属性已删］</script>
      ［HTML 属性已删］</script>
      <script src="［已删去可能属真题/答案原文的 62 字符外文片段］="te
      ```

### B2 — 同站下载中心提供该 PDF

- URL: `https://download.chinakaoyan.com/list-show-218527.html`
- HTTP 200；最终 URL `https://download.chinakaoyan.com/list-show-218527.html`；Content-Type `text/html`；响应字节 17702；sha256 `93b335a8c3a78ab77fd91176beb3d010a3dd43eac2988b20379174a92b50e95f`；标题：2024考研数学一真题及答案下载 - 中国考研网
- 探针检查（主张关键词是否真的出现在页面里）：
    - `2024` → 命中

      ```text
      ［已删去可能属真题/答案原文的 74 字符外文片段］>［HTML 属性已删］<head>［HTML 属性已删］<title>2024考研数学一真题及答案下载 - 中国考研网</title>［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］</head>
      <body>
      ﻿<script src="js_base/system.js"></script>
      <!--百度广告管家-->
      ［HTML 属性已删］</script>
      <!--百度广告管家-->
      <div class="xz1">
       <div>［HTML 属性已删］<img src="img/logo_ck.gif" alt="中国考研网"
      ```
    - `数学` → 命中

      ```text
      ［已删去可能属真题/答案原文的 68 字符外文片段］>［HTML 属性已删］<head>［HTML 属性已删］<title>2024考研数学一真题及答案下载 - 中国考研网</title>［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］</head>
      <body>
      ﻿<script src="js_base/system.js"></script>
      <!--百度广告管家-->
      ［HTML 属性已删］</script>
      <!--百度广告管家-->
      <div class="xz1">
       <div>［HTML 属性已删］<img src="img/logo_ck.gif" alt="中国考研网" /></a
      ```

### B3 — 天津仁爱学院数学教学部提供 2025 数学一真题及答案解析 PDF 附件

- URL: `https://www.tjrac.edu.cn/sxjxb/info/1340/3002.htm`
- HTTP 200；最终 URL `https://www.tjrac.edu.cn/sxjxb/info/1340/3002.htm`；Content-Type `text/html`；响应字节 16738；sha256 `5f508d8a5a75fb8bb484cf921fec80d2142ecddc206251e3320eaa0c91eb07d9`；标题：2025年考研数学（一）真题及答案解析-天津仁爱学院数学教学部
- 探针检查（主张关键词是否真的出现在页面里）：
    - `2025` → 命中

      ```text
      dtd">
      ［HTML 属性已删］
      <head>
       ［HTML 属性已删］
       ［HTML 属性已删］
       <title>2025年考研数学（一）真题及答案解析-天津仁爱学院数学教学部</title><meta name="pageType" content="3">
      ［HTML 属性已删］
      ［HTML 属性已删］
      ［HTML 属性已删］
       ［HTML 属性已删］
      
      <!--［已删去可能属真题/答案原文的 35 字符外文片段］>
      ［HTML 属性已删］</script>
      <!-- ［已删去可能属真题/答案原文的 58 字符外文片段］>
      ```
    - `数学（一）` → 命中

      ```text
      html xmlns="http://www.w3.org/1999/xhtml">
      <head>
       ［HTML 属性已删］
       ［HTML 属性已删］
       <title>2025年考研数学（一）真题及答案解析-天津仁爱学院数学教学部</title><meta name="pageType" content="3">
      ［HTML 属性已删］
      ［HTML 属性已删］
      ［HTML 属性已删］
       ［HTML 属性已删］
      
      <!--［已删去可能属真题/答案原文的 35 字符外文片段］>
      ［HTML 属性已删］</script>
      <!-- ［已删去可能属真题/答案原文的 58 字符外文片段］>
      <link r
      ```
    - `真题` → 命中

      ```text
      xmlns="http://www.w3.org/1999/xhtml">
      <head>
       ［HTML 属性已删］
       ［HTML 属性已删］
       <title>2025年考研数学（一）真题及答案解析-天津仁爱学院数学教学部</title><meta name="pageType" content="3">
      ［HTML 属性已删］
      ［HTML 属性已删］
      ［HTML 属性已删］
       ［HTML 属性已删］
      
      <!--［已删去可能属真题/答案原文的 35 字符外文片段］>
      ［HTML 属性已删］</script>
      <!-- ［已删去可能属真题/答案原文的 58 字符外文片段］>
      <link rel="s
      ```
    - `pdf` → 命中

      ```text
      e="list-style-type:none;">
       <li>附件【［HTML 属性已删］2025年考研数学1真题及答案解析.pdf</a>】已下载<span id="nattach18013567"><script language="javascript">［已删去可能属真题/答案原文的 56 字符外文片段］</script></span>次</li>
       </UL>
       </p>
       <p align="right">
       上一条：<a href="3012.htm">2025年考研数学（二）真题及答案解析</a>
       下一条：<a href="1046.htm">常用希腊字母的读音</a>
       </p>
       <!-- <p align=right>【［HTML 属性已删］关闭</a>】</p>-->
      </div>
      </form>
       </div>
       </div>
       <div class="footer">
      ```

### B4 — 聚创考研 2025 数学一解析页

- URL: `https://m.juyingonline.com/news/356469.html`
- HTTP 200；最终 URL `https://m.juyingonline.com/news/356469.html`；Content-Type `text/html;charset=UTF-8`；响应字节 21108；sha256 `07ccc84435ffa8fcec4206475346ef35d2082f3e85a16a345b07621abd4e5bba`；标题：2025考研数学一真题答案_25考研数学一估分对答案_聚创考研官网
- 探针检查（主张关键词是否真的出现在页面里）：
    - `2025` → 命中

      ```text
      <!DOCTYPE html>
      <html>
      <head>
       <meta charset="utf-8">
       ［HTML 属性已删］
       <title>2025考研数学一真题答案_25考研数学一估分对答案_聚创考研官网</title>
       ［HTML 属性已删］
       <meta name="description" content="">
       ［HTML 属性已删］
       ［HTML 属性已删］
      
      </head>
      <body>
      <header class="hui-header">
      ```
    - `数学一` → 命中

      ```text
      <!DOCTYPE html>
      <html>
      <head>
       <meta charset="utf-8">
       ［HTML 属性已删］
       <title>2025考研数学一真题答案_25考研数学一估分对答案_聚创考研官网</title>
       ［HTML 属性已删］
       <meta name="description" content="">
       ［HTML 属性已删］
       ［HTML 属性已删］
      
      </head>
      <body>
      <header class="hui-header">
      ```

### B5 — 启航数学真题索引

- URL: `https://m-jixun.iqihang.com/kyzt/shuxue/`
- HTTP 200；最终 URL `https://m-jixun.iqihang.com/kyzt/shuxue/`；Content-Type `text/html; charset=utf-8`；响应字节 121054；sha256 `f6b0da6925cc565b2a7bc8b10f8401f749d52d0ad6196863de6a025f4a814d67`；标题：数学真题_考研真题 - 启航教育考研官网
- 探针检查（主张关键词是否真的出现在页面里）：
    - `数学` → 命中

      ```text
      <!DOCTYPE html>
      <html lang="en">
      <head>
       <meta charset="UTF-8">
       <title>数学真题_考研真题 - 启航教育考研官网</title>
       ［HTML 属性已删］
       ［HTML 属性已删］
       ［HTML 属性已删］
       ［HTML 属性已删］
       <!-- 启用360浏览器的极速模式(webkit) -->
       <meta name="renderer" content="webkit">
       <!-- 避免IE使用兼容模式 -->
       ［HTML 属性已删］
       <!-- 针对手持设备优
      ```

### B6 — 启航 2026 数学一完整卷 + 解析

- URL: `https://m-jixun.iqihang.com/kyzt/shuxue/shuxue1/2025703715.html`
- HTTP 200；最终 URL `https://m-jixun.iqihang.com/kyzt/shuxue/shuxue1/2025703715.html`；Content-Type `text/html; charset=utf-8`；响应字节 106638；sha256 `759f721ccd469c75147eeebd026675d7d0f784e3c03ae4930062d84816789800`；标题：2026考研数学一真题及答案解析（pdf版已更新）-启航考研
- 探针检查（主张关键词是否真的出现在页面里）：
    - `2026` → 命中

      ```text
      <!DOCTYPE html>
      <html lang="en">
      <head>
       <meta charset="UTF-8">
       <title>2026考研数学一真题及答案解析（pdf版已更新）-启航考研</title>
       ［HTML 属性已删］
       ［HTML 属性已删］
       ［HTML 属性已删］
       ［HTML 属性已删］
       <!-- 启用360浏览器的极速模式(webkit) -->
       <meta name="renderer" content="webkit">
       <!-- 避免IE使用兼容模式 -->
       ［HTML 属性已删］
       ［HTML 属性已删］
      ```
    - `数学一` → 命中

      ```text
      <!DOCTYPE html>
      <html lang="en">
      <head>
       <meta charset="UTF-8">
       <title>2026考研数学一真题及答案解析（pdf版已更新）-启航考研</title>
       ［HTML 属性已删］
       ［HTML 属性已删］
       ［HTML 属性已删］
       ［HTML 属性已删］
       <!-- 启用360浏览器的极速模式(webkit) -->
       <meta name="renderer" content="webkit">
       <!-- 避免IE使用兼容模式 -->
       ［HTML 属性已删］
       ［HTML 属性已删］
      ```
    - `答案` → 命中

      ```text
      <!DOCTYPE html>
      <html lang="en">
      <head>
       <meta charset="UTF-8">
       <title>2026考研数学一真题及答案解析（pdf版已更新）-启航考研</title>
       ［HTML 属性已删］
       ［HTML 属性已删］
       ［HTML 属性已删］
       ［HTML 属性已删］
       <!-- 启用360浏览器的极速模式(webkit) -->
       <meta name="renderer" content="webkit">
       <!-- 避免IE使用兼容模式 -->
       ［HTML 属性已删］
       ［HTML 属性已删］
      ```

### B7 — 聚创考研 2026 数学一手写版 PDF

- URL: `https://m.juyingonline.com/news/357790.html`
- HTTP 200；最终 URL `https://m.juyingonline.com/news/357790.html`；Content-Type `text/html;charset=UTF-8`；响应字节 24472；sha256 `835ed3bc3a850abf10e63267240dff85a609c9103a64a7516e5ad7704efa900a`；标题：2026年考研数学一试题及答案_26考研数学一估分对答案_聚创考研官网
- 探针检查（主张关键词是否真的出现在页面里）：
    - `2026` → 命中

      ```text
      <!DOCTYPE html>
      <html>
      <head>
       <meta charset="utf-8">
       ［HTML 属性已删］
       <title>2026年考研数学一试题及答案_26考研数学一估分对答案_聚创考研官网</title>
       ［HTML 属性已删］
       <meta name="description" content="">
       ［HTML 属性已删］
       ［HTML 属性已删］
      
      </head>
      <body>
      <header class="hui-header">
      ```
    - `数学一` → 命中

      ```text
      <!DOCTYPE html>
      <html>
      <head>
       <meta charset="utf-8">
       ［HTML 属性已删］
       <title>2026年考研数学一试题及答案_26考研数学一估分对答案_聚创考研官网</title>
       ［HTML 属性已删］
       <meta name="description" content="">
       ［HTML 属性已删］
       ［HTML 属性已删］
      
      </head>
      <body>
      <header class="hui-header">
      ```

### C1 — 懒笔记 2024 英语一整卷 + PDF/Word/解析

- URL: `https://english-exam.lazynote.cn/kaoyan/paper/2024-english-one/`
- HTTP 200；最终 URL `https://english-exam.lazynote.cn/kaoyan/paper/2024-english-one/`；Content-Type `text/html; charset=utf-8`；响应字节 229272；sha256 `6b7be9b615f99cae6bddf5ab94e1032ddd25be1877a4dd7598bd66f7208b6815`；标题：2024考研英语一真题及答案解析 · 整卷电子版 PDF/Word 下载 · 懒笔记
- 探针检查（主张关键词是否真的出现在页面里）：
    - `2024` → 命中

      ```text
      ［已删去可能属真题/答案原文的 56 字符外文片段］
       ? 'dark'
       : 'light';
       ［已删去可能属真题/答案原文的 39 字符外文片段］= theme;
       } catch (e) {
       /* localStorage 不可用时不阻断渲染 */
       }
       })();
       </script><title>2024考研英语一真题及答案解析 · 整卷电子版 PDF/Word 下载 · 懒笔记</title>［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］<meta property="og:title" content="2024考研英语一真题及
      ```
    - `PDF` → 命中

      ```text
      ［已删去可能属真题/答案原文的 31 字符外文片段］
       ? 'dark'
       : 'light';
       ［已删去可能属真题/答案原文的 39 字符外文片段］= theme;
       } catch (e) {
       /* localStorage 不可用时不阻断渲染 */
       }
       })();
       </script><title>2024考研英语一真题及答案解析 · 整卷电子版 PDF/Word 下载 · 懒笔记</title>［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］<meta property="og:title" content="2024考研英语一真题及答案解析 · 整卷电子版 PDF/Word 下载
      ```
    - `Word` → 命中

      ```text
      ［已删去可能属真题/答案原文的 27 字符外文片段］
       ? 'dark'
       : 'light';
       ［已删去可能属真题/答案原文的 39 字符外文片段］= theme;
       } catch (e) {
       /* localStorage 不可用时不阻断渲染 */
       }
       })();
       </script><title>2024考研英语一真题及答案解析 · 整卷电子版 PDF/Word 下载 · 懒笔记</title>［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］<meta property="og:title" content="2024考研英语一真题及答案解析 · 整卷电子版 PDF/Word 下载 · 懒笔
      ```
    - `解析` → 命中

      ```text
      ［已删去可能属真题/答案原文的 42 字符外文片段］
       ? 'dark'
       : 'light';
       ［已删去可能属真题/答案原文的 39 字符外文片段］= theme;
       } catch (e) {
       /* localStorage 不可用时不阻断渲染 */
       }
       })();
       </script><title>2024考研英语一真题及答案解析 · 整卷电子版 PDF/Word 下载 · 懒笔记</title>［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］<meta property="og:title" content="2024考研英语一真题及答案解析 · 整卷电子版 P
      ```

### C2 — 中国考研网 2024 英语一各题型答案索引

- URL: `https://www.chinakaoyan.com/info/article/id/526859.shtml`
- HTTP 200；最终 URL `https://www.chinakaoyan.com/info/article/id/526859.shtml`；Content-Type `text/html; charset=gb2312`；响应字节 33869；sha256 `e2f45c7cc3590d2aa5e5aa865a79081c2bbe06fe8833b663bc9294d10492eb08`；标题：2024年考研英语（一二）真题及答案解析 - 中国考研网
- 探针检查（主张关键词是否真的出现在页面里）：
    - `2024` → 命中

      ```text
      ［已删去可能属真题/答案原文的 69 字符外文片段］>
      ［HTML 属性已删］
      <head>
      ［HTML 属性已删］
      <title>2024年考研英语（一二）真题及答案解析 - 中国考研网</title>
      ［HTML 属性已删］
      ［HTML 属性已删］
      ［HTML 属性已删］
      ［HTML 属性已删］
      ［HTML 属性已删］</script>
      ［HTML 属性已删］</script>
      <script src="［已删去可能属真题/答案原文的 54 字符外文片段］
      ```
    - `英语` → 命中

      ```text
      /［已删去可能属真题/答案原文的 61 字符外文片段］>
      ［HTML 属性已删］
      <head>
      ［HTML 属性已删］
      <title>2024年考研英语（一二）真题及答案解析 - 中国考研网</title>
      ［HTML 属性已删］
      ［HTML 属性已删］
      ［HTML 属性已删］
      ［HTML 属性已删］
      ［HTML 属性已删］</script>
      ［HTML 属性已删］</script>
      <script src="［已删去可能属真题/答案原文的 61 字符外文片段］
      ```

### C3 — 懒笔记 2025 英语一整卷

- URL: `https://english-exam.lazynote.cn/kaoyan/paper/2025-english-one/`
- HTTP 200；最终 URL `https://english-exam.lazynote.cn/kaoyan/paper/2025-english-one/`；Content-Type `text/html; charset=utf-8`；响应字节 225659；sha256 `25b207451db2af61723e4d99ab428a090a292f081b34a26018845bb254cb43a4`；标题：2025考研英语一真题及答案解析 · 整卷电子版 PDF/Word 下载 · 懒笔记
- 探针检查（主张关键词是否真的出现在页面里）：
    - `2025` → 命中

      ```text
      ［已删去可能属真题/答案原文的 56 字符外文片段］
       ? 'dark'
       : 'light';
       ［已删去可能属真题/答案原文的 39 字符外文片段］= theme;
       } catch (e) {
       /* localStorage 不可用时不阻断渲染 */
       }
       })();
       </script><title>2025考研英语一真题及答案解析 · 整卷电子版 PDF/Word 下载 · 懒笔记</title>［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］<meta property="og:title" content="2025考研英语一真题及答
      ```
    - `PDF` → 命中

      ```text
      ［已删去可能属真题/答案原文的 31 字符外文片段］
       ? 'dark'
       : 'light';
       ［已删去可能属真题/答案原文的 39 字符外文片段］= theme;
       } catch (e) {
       /* localStorage 不可用时不阻断渲染 */
       }
       })();
       </script><title>2025考研英语一真题及答案解析 · 整卷电子版 PDF/Word 下载 · 懒笔记</title>［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］<meta property="og:title" content="2025考研英语一真题及答案解析 · 整卷电子版 PDF/Word 下载 ·
      ```
    - `Word` → 命中

      ```text
      ［已删去可能属真题/答案原文的 27 字符外文片段］
       ? 'dark'
       : 'light';
       ［已删去可能属真题/答案原文的 39 字符外文片段］= theme;
       } catch (e) {
       /* localStorage 不可用时不阻断渲染 */
       }
       })();
       </script><title>2025考研英语一真题及答案解析 · 整卷电子版 PDF/Word 下载 · 懒笔记</title>［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］<meta property="og:title" content="2025考研英语一真题及答案解析 · 整卷电子版 PDF/Word 下载 · 懒笔记
      ```

### C4 — 新东方 2025 英语一试题及答案

- URL: `https://kaoyan.xdf.cn/202501/14059107.html`
- HTTP 200；最终 URL `https://kaoyan.xdf.cn/202501/14059107.html`；Content-Type `text/html`；响应字节 64814；sha256 `4b94689c98c0124791f03676099031e8ed5a90320f3ff37937cea075942dba19`；标题：【考研真题】2025年考研英语（一）真题和答案-答案部分-新东方网
- 探针检查（主张关键词是否真的出现在页面里）：
    - `2025` → 命中

      ```text
      eferrer-when-downgrade">［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］<title>【考研真题】2025年考研英语（一）真题和答案-答案部分-新东方网</title><link data-n-head="ssr" rel
      ```
    - `英语（一）` → 命中

      ```text
      content="考研真题，考研英语，2025年考研真题，2025年考研英语真题">［HTML 属性已删］［HTML 属性已删］<title>【考研真题】2025年考研英语（一）真题和答案-答案部分-新东方网</title>［HTML 属性已删］<link data-n-head="ssr" rel="stylesheet" type="text/css" href="https://cdn1.xdf
      ```
    - `答案` → 命中

      ```text
      ="考研真题，考研英语，2025年考研真题，2025年考研英语真题">［HTML 属性已删］［HTML 属性已删］<title>【考研真题】2025年考研英语（一）真题和答案-答案部分-新东方网</title>［HTML 属性已删］<link data-n-head="ssr" rel="stylesheet" type="text/css" href="https://cdn1.xdf.cn/xdf-
      ```

### C5 — 考研之家标注《2025 英语一试题参考答案.pdf》

- URL: `https://www.yanbbs.com/nd.jsp?id=47`
- 抓取结果: **失败** —— SSLError: HTTPSConnectionPool(host='www.yanbbs.com', port=443): Max retries exceeded with url: /nd.jsp?id=47 (Caused by SSLError(SSLCertVerificationError(1, '[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate (_ssl.c:1000)')))
- 结论提示: 无法用字节支持该主张。

### C6 — 懒笔记 2026 英语一整卷 + 分模块解析

- URL: `https://english-exam.lazynote.cn/kaoyan/paper/2026-english-one/`
- HTTP 200；最终 URL `https://english-exam.lazynote.cn/kaoyan/paper/2026-english-one/`；Content-Type `text/html; charset=utf-8`；响应字节 228441；sha256 `3c64ff4d94d610708fa63df3ca1462476b3eae627cb43e35f4334c96b555a4eb`；标题：2026考研英语一真题及答案解析 · 整卷电子版 PDF/Word 下载 · 懒笔记
- 探针检查（主张关键词是否真的出现在页面里）：
    - `2026` → 命中

      ```text
      ［已删去可能属真题/答案原文的 56 字符外文片段］
       ? 'dark'
       : 'light';
       ［已删去可能属真题/答案原文的 39 字符外文片段］= theme;
       } catch (e) {
       /* localStorage 不可用时不阻断渲染 */
       }
       })();
       </script><title>2026考研英语一真题及答案解析 · 整卷电子版 PDF/Word 下载 · 懒笔记</title>［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］<meta property="og:title" content="2026考研英语一真题及答
      ```
    - `完形` → 命中

      ```text
      /
       }
       })();
       </script><title>2026考研英语一真题及答案解析 · 整卷电子版 PDF/Word 下载 · 懒笔记</title>［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］<meta property="og:description" content="2026考研英语一真题整卷：全部题型的真题原题、答案与逐题解析，整卷电子版 PDF/Word 免费下载；另含各题型试卷排版、原文精读与单独下载入口。全卷共设 45 道客观题：完形填空 20 题、阅读
      ```
    - `阅读` → 命中

      ```text
      ;
       </script><title>2026考研英语一真题及答案解析 · 整卷电子版 PDF/Word 下载 · 懒笔记</title>［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］<meta property="og:description" content="2026考研英语一真题整卷：全部题型的真题原题、答案与逐题解析，整卷电子版 PDF/Word 免费下载；另含各题型试卷排版、原文精读与单独下载入口。全卷共设 45 道客观题：完形填空 20 题、阅读理解 4 篇 20
      ```
    - `新题型` → 命中

      ```text
      考研英语一真题由哪些题型构成，各部分有多少道题？</dt> ［HTML 属性已删］2026年考研英语一真题共 9 个模块、45 道编号小题，构成为：完形填空（Section I）1 篇 20 题（占 10 分）；仔细阅读（Section II Part A）4 篇文章共 20 题，每篇 5 题（21-40 题，占 40 分）；段落排序新题型（Part B）1 篇 5 题（41-45 题，占 10 分）；英译汉划线翻译（Part C）5 处划线句（占 10 分）；写作 2 篇——小作文（约 100 词）与大作文（160-200 词）。</dd> </div>［HTML 属性已删］ ［HTML 属性已删］2026年考研英语一阅读语料的 CEFR 难度分布是怎样的？</dt> ［HTML 属性已删］2026年考研英语一全卷 6 篇阅读语料按 CEFR 标注为 B2 共 4 篇、C1 共 2 篇。其中完形填空（AI 与美）和前三篇仔细阅读（驴的驯化、好莱坞影视业、无线电广播史）为 B2；难度最高的 C1 两篇分别是第四篇仔细阅读（野火与规定火烧）和划线翻译篇（科学素养）。</dd> </div>［HTML 属性已删］ <dt class="faq__q"
      ```
    - `翻译` → 命中

      ```text
      答案解析 · 整卷电子版 PDF/Word 下载 · 懒笔记</title>［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］<meta property="og:description" content="2026考研英语一真题整卷：全部题型的真题原题、答案与逐题解析，整卷电子版 PDF/Word 免费下载；另含各题型试卷排版、原文精读与单独下载入口。全卷共设 45 道客观题：完形填空 20 题、阅读理解 4 篇 20 题、段落排序 5 题；另有英译汉划线句翻译与写作共 3 道主观
      ```
    - `写作` → 命中

      ```text
      析 · 整卷电子版 PDF/Word 下载 · 懒笔记</title>［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］<meta property="og:description" content="2026考研英语一真题整卷：全部题型的真题原题、答案与逐题解析，整卷电子版 PDF/Word 免费下载；另含各题型试卷排版、原文精读与单独下载入口。全卷共设 45 道客观题：完形填空 20 题、阅读理解 4 篇 20 题、段落排序 5 题；另有英译汉划线句翻译与写作共 3 道主观大题。
      ```

### C7 — kaoyan.cn 静态 PDF 含 2026 英语一试题及答案

- URL: `https://static.kaoyan.cn/file/question/2025/12/27/4644ae5c80a12b9a2135e54dc56c0724.pdf`
- HTTP 200；最终 URL `https://static.kaoyan.cn/file/question/2025/12/27/4644ae5c80a12b9a2135e54dc56c0724.pdf`；Content-Type `application/pdf`；响应字节 903877；sha256 `d33c331413174826c333437b46e6819ab8b6da2435da1300d670d701fbac84c4`；标题：（空）
- 非文本载荷（PDF/二进制）：**不提供内容摘录**，只报元信息。

### C8 — 懒笔记 2010—2026 英语一总库

- URL: `https://english-exam.lazynote.cn/kaoyan/english-one/`
- HTTP 200；最终 URL `https://english-exam.lazynote.cn/kaoyan/english-one/`；Content-Type `text/html; charset=utf-8`；响应字节 157020；sha256 `806f02f3ff0dc6a9f4bf2d94319c9c0eb79b7831b4c3946759f18d5352010ca7`；标题：考研英语一真题在线使用和 PDF/Word 下载（2010–2026 共 17 套）· 英一真题分题型试卷和解析 · 懒笔记
- 探针检查（主张关键词是否真的出现在页面里）：
    - `2010` → 命中

      ```text
      ［已删去可能属真题/答案原文的 31 字符外文片段］
       ? 'dark'
       : 'light';
       ［已删去可能属真题/答案原文的 39 字符外文片段］= theme;
       } catch (e) {
       /* localStorage 不可用时不阻断渲染 */
       }
       })();
       </script><title>考研英语一真题在线使用和 PDF/Word 下载（2010–2026 共 17 套）· 英一真题分题型试卷和解析 · 懒笔记</title>［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］<met
      ```
    - `2026` → 命中

      ```text
      ［已删去可能属真题/答案原文的 26 字符外文片段］
       ? 'dark'
       : 'light';
       ［已删去可能属真题/答案原文的 39 字符外文片段］= theme;
       } catch (e) {
       /* localStorage 不可用时不阻断渲染 */
       }
       })();
       </script><title>考研英语一真题在线使用和 PDF/Word 下载（2010–2026 共 17 套）· 英一真题分题型试卷和解析 · 懒笔记</title>［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］<meta pro
      ```
    - `PDF` → 命中

      ```text
      ［已删去可能属真题/答案原文的 43 字符外文片段］
       ? 'dark'
       : 'light';
       ［已删去可能属真题/答案原文的 39 字符外文片段］= theme;
       } catch (e) {
       /* localStorage 不可用时不阻断渲染 */
       }
       })();
       </script><title>考研英语一真题在线使用和 PDF/Word 下载（2010–2026 共 17 套）· 英一真题分题型试卷和解析 · 懒笔记</title>［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］<meta property="og:title" content="考研英语一真题在线使用和 PDF/Word 下载（2010–2026 共 17 套）· 英一真题分题型试卷和解析
      ```
    - `Word` → 命中

      ```text
      '(［已删去可能属真题/答案原文的 37 字符外文片段］
       ? 'dark'
       : 'light';
       ［已删去可能属真题/答案原文的 39 字符外文片段］= theme;
       } catch (e) {
       /* localStorage 不可用时不阻断渲染 */
       }
       })();
       </script><title>考研英语一真题在线使用和 PDF/Word 下载（2010–2026 共 17 套）· 英一真题分题型试卷和解析 · 懒笔记</title>［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］［HTML 属性已删］<meta property="og:title" content="考研英语一真题在线使用和 PDF/Word 下载（2010–2026 共 17 套）· 英一真题分题型试卷和解析 · 懒
      ```

## 特别说明（审查者必须注意）

- `megbook.com.tw ...proID=4159518` 响应体只有 102 字节：这是一个 JS 跳转壳，
  **它的 200 状态码不代表核验成功**。
- `static.kaoyan.cn/...pdf` 是真实 PDF（903877 字节）。按项目规则，真题与答案原文
  **不得入库**（`docs/资料可得性侦察.md` §2.4 第 8–10 条）。本包故意不提供其内容。
- 上一轮审查中，一个 Codex 审查者**自行联网下载并解析了该 PDF**，把 2026 英语一试题与
  参考答案原文写进了自己的日志。该行为违反边界；那份日志已被删除。这正是本轮
  改用自包含证据包的原因。**不要再重复这个动作。**
