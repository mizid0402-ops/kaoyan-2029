# 评审：WP-H4a（`a92c04f`，合并 `a691cb1`，后续 `def56be`）+ H3 收口 `bf4c137`

遵守 `AGENTS.md`（不跑全量）。运行用 `git archive def56be` 导到系统临时目录（缺 gitignore 原始资料照前几轮做法复制进临时归档）。

## A. `bf4c137`（你第 67 轮两项）

只看 `git show bf4c137`：`calibration` / `kind` 为 null 是否已拒；三个描述字段恢复可选是否与规格一致。十进制精度那条建议决策者未采纳（提交信息写了理由），可以反驳。

## B. WP-H4a 大纲多版本登记 + 版本映射端口

任务书 `review/rounds/round-66-wp-h4a-task.md`、决策者意见 `round-68-wp-h4a-fixes-task.md`、实现报告 `round-66-wp-h4a-luna.md` / `round-68-wp-h4a-fixes-luna.md`。
新规格 `contracts/syllabus_mapping.md`；`contracts/workspace.md` 新增 `reference.syllabus_versions`。
`def56be` 修了合并后 27 项测试失败（几个测试辅助函数复制注册表时没处理新键），提交信息写了原因。

重点：
1. 映射规则是否闭合：能否构造一份映射让旧树某个 ID 无去向却通过、或新树某个 ID 无来源却通过；拆分 / 合并 / 改名 / 删除 / 新增的组合边界（例如同一 ID 既在 `changes.from` 又两树都有、`to` 里重复同一 ID、`changes` 把一个两树都有的 ID 映射到别处）。
2. "生效树必须等于某个登记版本"的检查：路径比较方式（大小写、`..`、junction）会不会误判或被绕过；`effective_version()` 语义。
3. `require` / `require_all` 对新键的行为是否与规格一致；`tools/verify_tree.py` 的识别顺序。
4. 这个设计对 H4b（按映射迁移复习队列 + 参照完整性）够不够用——例如 `targets()` 对"原样保留"与"删除"的区分、多步版本链（2026→2027→2028）。只给意见，H4b 还没开工。
5. `def56be` 选择在测试辅助函数里去掉 `syllabus_versions` 而不是同步它，是否掩盖了什么。

产物：`review/rounds/round-69-review-sol-out.md`，A、B 分别 PASS / FAIL，每条"必须改 / 建议改 / 不改"附可复现输入。只写这一个文件。
