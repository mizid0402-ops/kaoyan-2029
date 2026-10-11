# 第 256 轮任务书：数学一考研大纲 搜寻 → 下载 → 核对 → 合并（gpt-6.1-sol，新窗口 sol61-math1，已开联网搜索）

这是**工作任务**，不是评审。用户 2026-10-01 原话："派 6.1sol 去搜寻一下数一考研大纲，如果能找到，下载到本地核对之后和当前树合并一下"。
用户也说过 sol 容易在检查上花太多时间：**核对做到能下结论即可**，报告约 80 行以内。

## 先读

`AGENTS.md`；`交接文档.md` §4.2（AI 不得凭自己知道的内容补节点，只能"大纲原文 → 节点"）、§4.3（`rights` 与 `source_tier` 两轴）、§5.0 A（审查者联网下载真题原文写进日志的事故）；
`data/structured_materials/math1/knowledge_tree.yaml` 文件头（证据等级声明、quote_ref 精确性边界）与 `knowledge_tree_report.md`；
`data/materials.yaml` 里 `math1-outline-*` 各条；`contracts/ledger.md`、`contracts/knowledge_tree.md`；`tools/fetch_evidence.py`、`tools/verify_tree.py` 用法。

## 现状

当前数学一树 = **2026 版**大纲，来自两份第三方全文转录（`trusted_reprint`，`may_define_syllabus()` 为 false），全部节点 `status: extracted`；
已知转录错字（"柑合性""伯努"）。官方纸质书只登记为 `remote_reference`。

## 要做的

1. **搜寻**：优先官方来源（教育部教育考试院 neea.edu.cn、中国研究生招生信息网 yz.chsi.com.cn、人民教育出版社等）上的
   《全国硕士研究生招生考试数学考试大纲》**数学一**全文；年份优先 2027 版（若已发布），其次 2026 版。官方找不到全文时，记下找到了什么（公告、目录、第三方转载），不要硬凑。
2. **下载**：用 `py -3.12 tools/fetch_evidence.py <urls.txt> --out data/raw_materials/math1/syllabus/<子目录>` 取回（该目录 gitignore），
   保留它生成的 `.json` 取证元信息。PDF 等二进制照实保存。
3. **核对**：判断是否官方（域名、发布单位、标题、年份、是否完整）；对当前树逐章比对（章节标题、`locator.quote_ref` 能否在新来源中定位），列差异表。
4. **登记**：在 `data/materials.yaml` 新增条目，`source_tier` 与 `rights` 照实填（官方域名发布的才可填 `official`），`storage.sha256` = 本地文件哈希（§5.2.1 末尾说明）。
5. **合并**（按找到的东西分三种情况）：
   - **找到 2026 版官方全文**：把官方来源写进各节点 `sources`（官方来源放第一个，`sha256` 等于本地文件哈希，`quote_ref` 在其中可定位）；
     按官方原文改正转录错字与标题差异；节点 `status` **保持 `extracted`**（AI 不得推进状态）；不增删节点，除非官方原文确有当前树缺的条目或多出的条目——增删都写进报告差异表并说明原文位置。
     更新树文件头的来源与证据等级说明、`knowledge_tree_report.md` 的比对表。
   - **找到 2027 版官方全文**：**不改当前树**（换大纲版本要走 D5 流程：新树 + 版本映射 + 注册表登记 + 迁移，由决策者另派）。只做下载、登记、与 2026 树的逐章差异表。
   - **只找到第三方转载或什么都没有**：不改树；报告写清搜过哪些站点与结果。

## 不做的

- 不下载真题、答案、辅导书正文；只取大纲页面。
- **报告、日志、节点里不得整段粘贴大纲原文**：只写章节标题、短的 `quote_ref` 定位串（与现有树同样长度级别）与差异说明。
- 不提交；不改 `contracts/`、`ky/` 代码；不读 `data/personal/`。

## 验收（只跑这些）

```
py -3.12 tools/verify_tree.py data/structured_materials/math1/knowledge_tree.yaml --workspace kaoyan.workspace.yaml
py -3.12 -m unittest tests.test_data_manifest tests.test_verify_tree_shapes tests.test_ledger
```

改了树的节点数或来源而导致 `tests/test_data_manifest.py` 钉住的数字变化时，按 `AGENTS.md` 第 7 条只在该数据清单测试里更新，并在报告里列出旧值 → 新值。

## 输出

`F:\workspace\kaoyan-ai-system\review\rounds\round-256-math1-syllabus-sol61.md`：
搜到了什么（URL、发布单位、年份、是否官方、是否全文）→ 下载文件与哈希 → 逐章差异表 → 属于上面哪种情况、做了哪些合并改动 → 测试输出原文 → "全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。
