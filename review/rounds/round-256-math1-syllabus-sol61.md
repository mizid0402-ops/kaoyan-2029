# 第 256 轮：数学一大纲搜寻、下载与核对（sol61-math1，2026-10-01）

结论：未取得 2026/2027 官方全文，属于第三种情况；新增 6 条资料登记，不改当前树。
| 编号 | URL / 发布单位 | 年份、官方性与全文判定 |
|---|---|---|
| A | [高教社](https://xuanshu.hep.com.cn/front/book/findBookDetails?bookId=6aa1910be119ac97297a608f) | 2027；官方出版社信息页，教育部教育考试院编，ISBN 978-7-04-068404-9，160 页；标注出版 2026-09-29，详情和目录均“暂无”，非全文。 |
| B | [教育考试院大纲列表](https://yankao.neea.edu.cn/html1/category/1509/6235-1.htm) | 官方；数学可见条目为 2022 版公告，无本轮目标年份全文。 |
| C | [环球网校下载页](https://www.hqwx.com/kaoyan-kaoshi/ziliaolm/1449227.html) | 标称 2027，更新时间 2026-09-30；第三方，页面非全文。 |
| D | [C 页提供的 PDF](https://oss-hqwx-video.hqwx.com/考研数学大纲（2027年）_490a2486eff173a056fd251bce710698deb2e64d.pdf) | 第三方；封面 2027，4 页，实为更新说明、推广及使用说明，无数一章节正文；WPS 元信息创建于 2026-09-11。 |
| E | [聚创考研](https://www.juyingonline.com/news/357341.html) | 2026，页面日期 2025-10-14；第三方，只有原文网盘线索，未取得网盘文件，无章节正文。 |
| F | [新都网](http://edu.newdu.com/Master/Math/Guide/202511/4818166.html) | 标题为 2026；第三方全文转录，含高数、线代、概率统计 22 章及内容/要求；是既有来源重新取证，不是独立第三来源。 |
已搜 neea.edu.cn（含 yankao）、yz.chsi.com.cn、pep.com.cn、hep.com.cn：研招网命中招生规定及旧解读，人教社未命中目标全文；仅 A 确认新版本出版信息。“未找到”限于本轮检索，不能断言全网不存在。[文都候选](https://kaoyan.wendu.com/m/2025/1017/212673.shtml) HTTPS 为 SSLEOFError，HTTP 为 RemoteDisconnected；失败元信息保留，未当作取得全文。
下载均使用 `py -3.12 tools/fetch_evidence.py <临时 urls.txt> --out data/raw_materials/math1/syllabus/round-256`；下表文件名均相对该目录，哈希均为本地字节。
| 编号 | 文件名 | 字节数 | SHA-256 |
|---|---|---:|---|
| A | xuanshu_hep_com_cn_front_book_findBookDetails_bookId_6aa1910be119ac97297a608f.html | 41676 | 903db5e747e22a85a9b253a477713e1b16a7be5249a62ebae02f53829562126e |
| B | yankao_neea_edu_cn_html1_category_1509_6235_1_htm.html | 24317 | fb384a43365d65dd1ad52dccdceff21921f6c6aecb41d42c16fad0dcd2c8eb07 |
| C | www_hqwx_com_kaoyan_kaoshi_ziliaolm_1449227_html.html | 25170 | 9fdd733af1febdc892e00541d1ed3c35742b3a0dc7ed56124ad0818772f0c095 |
| D | oss_hqwx_video_hqwx_com_E8_80_83_E7_A0_94_E6_95_B0_E5_AD_A6_E5_A4_A7_E7_BA_B2_EF_BC_882027_E5_B9_B4_EF_BC_89_490a2486eff.bin | 490157 | 328d58916107fc3600a7c6f0327e467bb8236cc1e8c7f503c1450af9e9deae26 |
| E | www_juyingonline_com_news_357341_html.html | 34239 | 680e61d9b90399772a477c3b50d5aa81f35b89b84e66ab1573b7b22608346caa |
| F | edu_newdu_com_Master_Math_Guide_202511_4818166_html.html | 71184 | f90af9e1ac11e5354807e175c3ac4cf3d494e277da29dcbd135f9456ed5fcf49 |
保留 `index.json`、`reprint-index.json`、`more-index.json`、`fulltext-index.json`；D 原始 PDF 按工具保存为 `.bin`，未重编码。HTML 解码保存后哈希与 JSON 的响应哈希不同，登记使用上表本地哈希；6 条 `verify_bytes` 均为 True。
逐章对照：F 的 `.trs_editor_view` 正文与旧新都快照分别去空白后按章切分；仅作转录一致性核对。A–E 均无章正文，故 2027 官方差异逐章不可核实。下表“定位”指该章现有 title、两区块 quote_ref 及“考试内容/考试要求”标签可定位；不是正文逐字背书。
| 科目 | 当前章标题（短定位串） | F 定位 / 与旧转录正文差异 | 2027 官方差异 |
|---|---|---|---|
| 高数 | 一、函数、极限、连续 | 可定位；空白归一后相同 | 无全文，不能判断 |
| 高数 | 二、一元函数微分学 | 可定位；相同 | 无全文，不能判断 |
| 高数 | 三、一元函数积分学 | 可定位；相同 | 无全文，不能判断 |
| 高数 | 四、向量代数和空间解析几何 | 可定位；相同 | 无全文，不能判断 |
| 高数 | 五、多元函数微分学 | 可定位；相同 | 无全文，不能判断 |
| 高数 | 六、多元函数积分学 | 可定位；相同 | 无全文，不能判断 |
| 高数 | 七、无穷级数 | 可定位；相同 | 无全文，不能判断 |
| 高数 | 八、常微分方程 | 可定位；相同 | 无全文，不能判断 |
| 线代 | 一、行列式 | 可定位；相同 | 无全文，不能判断 |
| 线代 | 二、矩阵 | 可定位；相同 | 无全文，不能判断 |
| 线代 | 三、向量 | 可定位；相同 | 无全文，不能判断 |
| 线代 | 四、线性方程组 | 可定位；相同 | 无全文，不能判断 |
| 线代 | 五、矩阵的特征值和特征向量 | 可定位；相同 | 无全文，不能判断 |
| 线代 | 六、二次型 | 可定位；相同 | 无全文，不能判断 |
| 概率统计 | 一、随机事件和概率 | 可定位；相同 | 无全文，不能判断 |
| 概率统计 | 二、随机变量及其分布 | 可定位；相同 | 无全文，不能判断 |
| 概率统计 | 三、多维随机变量及其分布 | 可定位；相同 | 无全文，不能判断 |
| 概率统计 | 四、随机变量的数字特征 | 可定位；相同 | 无全文，不能判断 |
| 概率统计 | 五、大数定律和中心极限定理 | 可定位；空白归一后相同 | 无全文，不能判断 |
| 概率统计 | 六、数理统计的基本概念 | 可定位；相同 | 无全文，不能判断 |
| 概率统计 | 七、参数估计 | 可定位；相同 | 无全文，不能判断 |
| 概率统计 | 八、假设检验 | 可定位；相同 | 无全文，不能判断 |
现有 138 个 source-quote 对在 F 空白归一后均可定位；其中 6 对原样不命中，均涉及第一章/第十九章标题（多来源重复及 content 节点引用同章标题）。旧错字仍在，未以第三方信息修树；不确认官方考纲有无增删。
登记 A 为 `official_publisher`、B 为 `official`、C/E/F 为 `trusted_reprint`、D 为 `community_archive`。A/B 的 rights 为 `official_public`，其余为 `personal_use`；均允许本地存储，第三方不公开显示，全部禁止再分发和结构化，未声称取得全文许可。
仅修改 `data/materials.yaml` 并新增本报告；无节点增删、来源替换、状态推进。树仍 69 节点、全部 extracted；`knowledge_tree_report.md` 未改；数据清单测试无数值变化。树 SHA-256 保持 `27d39511276b3747cc3a1f0e87b43dfe991095405aad5d33831b5491037979b2`，原构建报告保持 `d4cac92fff09da5653f4ab128ba75d5d92099d86d7d4e971116ec053948782d9`。
`py -3.12 tools/verify_tree.py data/structured_materials/math1/knowledge_tree.yaml --workspace kaoyan.workspace.yaml`（退出 0），输出原文：
```text
contract        : OK (69 nodes validated by ky.knowledge.knowledge_point)
sources         : 2 distinct files, 2 hashed
hashes          : OK (every sources[i].sha256 matches the bytes on disk)
quote_ref       : OK (every quote_ref locates in its declared source)
tree shape      : math1
structure       : {'subject': 3, 'chapter': 22, 'section': 44}

ALL CHECKS PASSED
```
`py -3.12 -m unittest tests.test_data_manifest tests.test_verify_tree_shapes tests.test_ledger`（退出 0），输出原文：
```text
................................................................
----------------------------------------------------------------------
Ran 64 tests in 14.093s

OK
MUTATION HASH test_ambiguous_cs408_and_math1_markers_are_rejected: before=fc369b440e2d51383586373844e3edf2cc89729e170d3d2249c777c7bb7a9d4e mutated=3e88d9531e8edece321566dc1b61bd1a884775f14bf0c86d4f0ecedcf7c05aa5 restored=fc369b440e2d51383586373844e3edf2cc89729e170d3d2249c777c7bb7a9d4e
MUTATION HASH test_cs408_all_chapters_deleted_is_rejected: before=fc369b440e2d51383586373844e3edf2cc89729e170d3d2249c777c7bb7a9d4e mutated=31074d4845c67001f4ada1433040640af151f4336c9b1ebec9fcd9da74536fbb restored=fc369b440e2d51383586373844e3edf2cc89729e170d3d2249c777c7bb7a9d4e
MUTATION HASH test_cs408_chapter_scopes_relabelled_is_rejected: before=fc369b440e2d51383586373844e3edf2cc89729e170d3d2249c777c7bb7a9d4e mutated=202b9078619947aa4cf89f57d179c11b9d0592ddcf7499c352c24135abf736bf restored=fc369b440e2d51383586373844e3edf2cc89729e170d3d2249c777c7bb7a9d4e
MUTATION HASH test_cs408_missing_chapter_prefix_is_rejected: before=fc369b440e2d51383586373844e3edf2cc89729e170d3d2249c777c7bb7a9d4e mutated=aae6f9fac6be3837ceabb82c815b2238819ffd49e468c4b55a667bd1877bf075 restored=fc369b440e2d51383586373844e3edf2cc89729e170d3d2249c777c7bb7a9d4e
MUTATION HASH test_math1_all_chapters_deleted_is_rejected: before=27d39511276b3747cc3a1f0e87b43dfe991095405aad5d33831b5491037979b2 mutated=521a2c8fcd4844c19af1c80d3c0855e52bcf67322cb8c0ee1064a475dca433a3 restored=27d39511276b3747cc3a1f0e87b43dfe991095405aad5d33831b5491037979b2
MUTATION HASH test_math1_missing_content_is_rejected: before=27d39511276b3747cc3a1f0e87b43dfe991095405aad5d33831b5491037979b2 mutated=0bd44a59a98d4b9479df2b7748f9836e654333f2072ee9c49c8af28b20c5f061 restored=27d39511276b3747cc3a1f0e87b43dfe991095405aad5d33831b5491037979b2
MUTATION HASH test_math1_required_content_wrong_scope_is_rejected: before=27d39511276b3747cc3a1f0e87b43dfe991095405aad5d33831b5491037979b2 mutated=d3a984829c656f2333d41efc349486d1928a413acff2ec81e59fbe959279c8b4 restored=27d39511276b3747cc3a1f0e87b43dfe991095405aad5d33831b5491037979b2
MUTATION HASH test_mixed_namespace_is_rejected: before=fc369b440e2d51383586373844e3edf2cc89729e170d3d2249c777c7bb7a9d4e mutated=0fe5167d854a07a96b3ae729c14e4f1620bff96ec4bce4b3103f74ba264c3e3a restored=fc369b440e2d51383586373844e3edf2cc89729e170d3d2249c777c7bb7a9d4e
MUTATION HASH test_subject_scope_node_below_cs408_section_is_rejected: before=fc369b440e2d51383586373844e3edf2cc89729e170d3d2249c777c7bb7a9d4e mutated=62ae35a567e4cfb55eb7c2d716e139df924e3d5015ba8179a742edd0b834ba5b restored=fc369b440e2d51383586373844e3edf2cc89729e170d3d2249c777c7bb7a9d4e
MUTATION HASH test_unknown_namespace_is_rejected: before=fc369b440e2d51383586373844e3edf2cc89729e170d3d2249c777c7bb7a9d4e mutated=62213d1f43ce4f07274fc6af56871c47466d56d0327af9209f25521495053d7c restored=fc369b440e2d51383586373844e3edf2cc89729e170d3d2249c777c7bb7a9d4e
```
全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。未提交；未下载真题、答案或辅导书正文；未读 data/personal/。
