# 复审：`2e53d6e`（B4 投影层级）与 `904c37f`（B1 / B5 / B6 及 B2、B8）

遵守 `AGENTS.md`（不跑全量）。运行用 `git archive 904c37f` 导到系统临时目录（缺 gitignore 原始资料照前几轮做法复制进临时归档）。

范围：两次提交；实现报告 `review/rounds/round-82-projection-hierarchy-luna.md`、`round-81-wp-h5-sol80-fixes-luna.md`。

请判断：
1. 你第 80 轮 B1、B4、B5、B6 的原复现是否都关闭；B2、B8 的规格措辞是否恰当。
2. B4：投影重建后的 `parent_id` 变化行数（38 / 4 / 0，补充表 38）是否可信；投影 schema 不升版的理由是否成立；`depth` 列义保持不变是否留下误导。
3. B1：`--write` 的写入目标越界检查是否可靠（目标文件不存在、父目录是 junction 等）。
4. B6：键解析在"科目名 / 出题单位 / 年份"之间有无歧义；只写已登记索引（原来是扫描目录）这一行为变化是否恰当；统考写回逐字节一致的对照做法是否可信。
5. 新回归测试撤修复是否变红。

产物：`review/rounds/round-83-review-sol-out.md`，每项"必须改 / 建议改 / 不改"附可复现输入，最后 PASS / FAIL。只写这一个文件。
