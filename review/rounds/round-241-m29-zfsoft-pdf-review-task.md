# 第 241 轮任务书：WP-IO3 正方 PDF 适配器实现评审（gpt-6.1-sol，续 sol61-m18）

## 范围

主工作区未提交的改动：`ky/timetable_io/zfsoft_pdf.py`（新）、`tests/contract/test_timetable_io_zfsoft_pdf.py`（新）、
`ky/timetable_io/staging.py`（adapter 白名单加 `zfsoft_pdf`）、`ky/__main__.py`（`import-pdf` 子命令）。实现者报告 `review/rounds/round-238-m29-zfsoft-pdf-luna.md`。
实现者在一个以未修正 IO1 为起点的 worktree 里完成，决策者把新增部分搬到 master（IO1 已提交 `8f97c50`）。
决策者已在本机用用户真实 PDF 做了验收：解析结果与现有课表同学期逐门一致（24 / 24，无差异）。真实 PDF 是个人数据，不提供。

## 请判断

1. 是否符合 `contracts/timetable_import_zfsoft_pdf.md`（§2 模板与区域 / 白名单 / 锚点、§3 切分与核对、§4 命令与缺省周数）和第 231、232 轮你列出的细节；
   有没有静默错收的路径（给出合成片段序列）。
2. 实现者自选的歧义：周次表达式要求详情里恰有一个带"周"或奇偶标记的候选（零个或多个拒绝），是否合理。
3. 与 IO1 公开接口的衔接（只用公开入口；暂存 adapter 白名单；隔离检查；不回显片段文字）。
4. `AGENTS.md` 已知缺陷与 D7；测试是否有实质断言、结果是否不依赖片段输入顺序。

## 已知、不在本轮

`import-pdf` 预览暂不打印每日分钟（IO2 会提供公用预览函数，合并时接上）。

## 输出

`review/rounds/round-241-m29-zfsoft-pdf-review-sol61.md`：PASS / FAIL；必须改（附可复现输入）/ 建议改 / 不改；安全登记单列。

## 禁止

不联网；只写这一份报告；不修改其他文件；不读仓库外文件；报告里不写个人数据。只跑相关单个模块，不跑全量。
