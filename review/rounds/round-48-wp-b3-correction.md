# Round 48 修正 + Round 47 修复（一次派发，两部分分开报告）

先读仓库根 `AGENTS.md`：新增了"最高原则：可维护性与可读性优先"（决议 D7）与"数据会增长"两节，本轮起生效（行宽 ≤ 100、模块头 docstring 写明模块编号与规格、一个函数一件事、不写聪明捷径）。

## 第一部分：WP-B′3 撤回越界的语义变化（`ky/schedule/vocab_channel.py`）

你删除了 `remaining_pool` / `preview_batch` 对已投放词的排除（以及 `exclude_delivered` 参数）。这是 WP-D 的事，而承接投放状态的新存储还不存在：
现在已投放的 15 个词会被重新预览、"剩余"多算 15。这是回归，不是迁移。起因是我在任务书里写"新代码不得再依赖 `delivery_log`"，措辞有歧义——本意是"不要新增依赖"，不是"删除现有依赖"。

请：
1. **恢复**排除已投放词的行为与 `exclude_delivered` 参数（默认 True），读取仍来自 `delivery_log`；把这段集中到一个命名清楚的私有函数（如 `_legacy_delivered_word_ids(con)`），docstring 写明"遗留桥接：审查项 B2，WP-D 改为读学习状态存储后删除"。
2. **还原** `preview_batch` 里 `count == 0` 的位置（在打开数据库之前返回），不做无关的行为变更。
3. `contracts/vocabulary.md` 同步：日常读路径**目前**仍经遗留桥接排除已投放词；WP-D 后改为由调用方传入已投放集合。删去"不读投放状态"的现在时说法。
4. 模块 docstring 的职责描述改回与行为一致。
5. 加一条回归：用仓库词库，`remaining_pool` 等于"视图行数 − 已投放且在视图中的词数"（**期望值从库里算，不写字面量**）；`preview_batch` 返回的词不含任何已投放词。

验收：`py -3.12 -m unittest tests.contract.test_vocabulary_port tests.test_monthly_close tests.test_state_snapshot`。

## 第二部分：WP-B′2 投影三处 MAJOR

照 `review/rounds/round-47-wp-b2-fix-task.md` 执行（M1 哈希与解析同源、M2 畸形索引条目、M3 补充树外科目节点、两处断言加强）。
同时按 D7 把 `ky/projection/__init__.py` 里超过 100 字符的行与 `build_projection` 这个超长函数拆成有名字的步骤（读输入 / 建生效行 / 建补充行 / 读索引 / 读权重 / 写库），**不改行为**。

## 报告

- 第一部分追加到 `review/rounds/round-48-wp-b3-vocab-luna.md` 末尾（"## 修正"）。
- 第二部分追加到 `review/rounds/round-47-wp-b2-projection-luna.md` 末尾（"## 修复（sol FAIL 后）"）。
不提交；全量不跑。
