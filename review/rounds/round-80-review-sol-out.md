# Round 80 Codex 独立评审

审查基线：`git archive 11cda18` 解到系统临时目录，并复制本机 Git 忽略的 `data/raw_materials/`；只跑相关单模块、单条命令和临时归档内的精确探针。未跑全量测试。下文路径和行号均指该归档，除非注明提交差异。

## A. H4b `d0df05a`：空链 `--apply`

| 编号 | 意见 | 证据与可复现输入 |
| --- | --- | --- |
| A1 | 不改 | `git show d0df05a` 将空链返回移到 `workspace.require(target_key)` 和 `check_queue_references` 之后、`store.write` 之前；见 `ky/__main__.py:909-930`。在临时归档的测试工作区，分别执行 `py -3.12 -m ky review-queue migrate --subject cs408 --from 2099 --to 2099 --apply`（目标未登记）、同命令改为 `--from 2027 --to 2027`（队列项仍属 2026 树）、改为 `--from 2026 --to 2026`（合法同版本），并均传入测试注册表与队列的 `--workspace`、`--store`：前两者退出 2，错误分别含 `not registered` / `不在科目`，队列文件不变；后者退出 0，提示无需迁移，队列文件仍不变。`tests/contract/test_syllabus_migration_port.py:319-331` 的新增回归测试在把空链返回移回校验之前后出现 2 个失败；恢复后 `py -3.12 -m unittest tests.contract.test_syllabus_migration_port` 为 18/18 通过。 |
| A2 | 不改 | 路径搜索提前停止的专门哨兵测试属于第 77 轮建议项，本次提交没有修改搜索算法；现有提前停止分支可直接审读。决策者不采纳专测可接受，不能把它算作 N1 未修。 |

**A：PASS。**

## B. WP-H5 `17c8443`（合并 `11cda18`）

| 编号 | 意见 | 证据与可复现输入 |
| --- | --- | --- |
| B1：旧产物参与写入 | **必须改** | 纯函数 `aggregate_topic_weights()` 只接收清单、编码产出、树，不读现有答案（`ky/exam/topic_weights.py:366-412`）；但 CLI 的 `_load_inputs()` 无条件 `workspace.require("reference.topic_weights")` 并解析旧 JSON（`tools/aggregate_topic_weights.py:54-100`），`--write` 也先调用它，随后又用 `require` 取输出路径（同文件 `:141-160`）。复现：在临时归档把旧 `topic_weights.json` 内容改为 `not-json`，运行 `py -3.12 tools/aggregate_topic_weights.py --write`，退出 2，报 `reference.topic_weights: cannot read JSON`，未能重建；文件不存在时也无法通过 `require`。旧产物若损坏或丢失，聚合写入即失效，与“从三份编码产出重建产物”的目标（`review/rounds/round-74-wp-h5-task.md:11-15,26-31`）不符。最小修法：仅 `--check` 读旧产物；`--write` 从清单及编码产出重算，目标路径仍按注册表约束，但允许创建尚不存在的目标文件。补一条损坏／缺失旧产物仍可重建的工具测试。 |
| B2：相等比较 | 建议改 | `tools/aggregate_topic_weights.py:103-129` 递归比较 JSON 类型、键和值，浮点值用 Python `!=`，没有容差或字符串化。临时归档把现有 `topic_weight.cs408.os.chapter-02` 从 `15.104273504273504` 改为相邻浮点值 `15.104273504273506`，`--check` 退出 1 并列出该路径；原文件 `--check` 退出 0。严格说这不是 IEEE **逐位**比较：`_differences({"x": 0.0}, {"x": -0.0}) == []`。当前权重产物没有这种有符号零差异；如“逐位”指字节位模式，应另比浮点位，否则把文档措辞改成“无容差数值相等”。 |
| B3：增量与累加顺序 | 不改 | `tests/contract/test_topic_weights_port.py:65-172` 追加一批合成题，旧 `per_question` 逐题用紧凑 JSON 序列化作字节比较，同时断言新增 chapter 增量和其他 chapter 不变。把“追加批次时篡改第一个旧题分布 +0.001”的临时 mutant 注入后，该测试失败；撤回 mutant 后通过。`ky/exam/topic_weights.py:262-312,321-364,366-412` 按清单批次、首位编码者题目出现顺序、节点出现顺序累加，末尾追加不会改变旧批次的计算前缀；重新排序或插入旧批次之前则不能承诺 `topic_weight` 的浮点位相同。当前测试的新增贡献是整数 `3.0`，可再用含非整权重的新批补强浮点顺序哨兵，但不是本轮阻断。 |
| B4：层级端口与投影 | **必须改** | 新规格定义父节点为树中最长点分真前缀，并要求消费者用公开端口（`contracts/knowledge_tree.md:68-78`）；新端口按此实现（`ky/knowledge/hierarchy.py:14-34`）。投影仍只查紧邻前一段，缺失即写 `NULL`（`ky/projection/__init__.py:224-227,273-278`）。最小有效树节点 `cs408.ds.chapter-01` 与 `cs408.ds.chapter-01.section-01.item-01`：公开端口返回 chapter，投影返回 `NULL`；树语法的结构／chapter 校验均接受。对归档现有树逐节点核对，cs408 403 点中 38 点、eng1 24 点中 4 点两者不一致，例如 `cs408.co.chapter-01.section-01.detail-04.note-01`。这是新写下的统一层级契约与已有消费者的真实分歧；应在投影模块单独改用端口并给“缺中间前缀”回归，或明确修订契约的消费者范围。不要在 H5 聚合模块内顺手改投影。`tests/contract/test_knowledge_tree_port.py:106-134` 全用完整前缀链；把端口临时改成“只认紧邻父段”，这两条测试仍通过，说明该关键边界未覆盖。 |
| B5：批次身份校验 | **必须改** | `ky/exam/topic_weights.py:72-89` 只要求 `exam_year` 为正整数、`paper_source` 为非空串。把首批及三份编码产出 `meta.exam_year` 一起改为 `1`，聚合接受并输出 `cs408-1-1`；把首批 `paper_source` 改为 `school-x`，聚合也接受并输出 `cs408-school-x-2023-1`。H3 的卷面／索引端口要求四位年份和 `paper_source` 匹配 `^[a-z][a-z0-9]*$`（`contracts/exam_index.md:23-25,59-60`）；这些键无法表示合法登记卷。应复用或同步 H3 的身份规则，至少拒绝上述两例，并测试 `paper_source: xidian` 仍通过。`node_table_sha256` 不校验符合已定“只作来源记录”（`contracts/topic_weights.md:33-38`）。 |
| B6：合法自命题键的消费者 | **必须改** | 把首批 `paper_source` 设为合法的 `xidian`，聚合正常生成 `cs408-xidian-2023-1`，符合 `contracts/topic_weights.md:73-78`。但既有 `tools/apply_knowledge_weights.py:51-65` 只接受 `^([a-z0-9]+)-(\d{4})-(\d+)$`；用该聚合产物调用 `load_distributions()` 得到 `ValueError: unparseable per_question key: 'cs408-xidian-2023-1'`。由于它遍历整个 `per_question`，加入一份合法自命题卷会让全国卷的权重写回也整体失败。第 74 轮任务书 `:44-49` 明定本包不改该工具，因此应登记为跨模块阻断并单独安排消费端升级；不能把当前产物宣称为可供现有写回链路直接使用。 |
| B7：常规负例及测试强度 | 不改 | `ky/exam/topic_weights.py:143-178,211-225,233-255,270-276` 检查编码题号连续且各编码者一致、同一输出题号重复、批次身份重复、节点属于生效树、批次科目有 `topic_rollup`。`tests/contract/test_topic_weights_port.py:173-215` 对树外节点、缺题、重复题、重复批次均断言错误内容；在临时归档逐一撤掉对应检查，这四条测试各自变红（或暴露后续 `KeyError`），不是只跑通正常样本。`py -3.12 -m unittest tests.contract.test_topic_weights_port` 为 6/6 通过；现有登记产物的 `--check` 通过。 |
| B8：输入形状与测试补强 | 建议改 | `contracts/topic_weights.md:46-52` 写编码条目均有 `confidence`，但 `ky/exam/topic_weights.py:197-209` 仅在 `nodes` 非空时检查；把一个空节点条目的 `confidence` 删除仍被接受。空节点不投票，数值结果不受影响，但规格与实现不一致，应明确允许空节点省略置信度，或统一校验。另应补 B1、B4、B5、B6 的精确回归；现有 6 条聚合契约测试没有触及这些边界。 |

**B：FAIL。** 聚合纯函数对当前登记数据的复现与追加批次性质成立；写入工具的旧产物依赖，以及层级、卷身份、自命题键的跨模块契约仍需收口。
