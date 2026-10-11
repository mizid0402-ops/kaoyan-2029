# 评审：WP-H5（`17c8443`，合并 `11cda18`）+ H4b 最后一处修复 `d0df05a`

遵守 `AGENTS.md`（不跑全量）。运行用 `git archive 11cda18` 导到系统临时目录（缺 gitignore 原始资料照前几轮做法复制进临时归档）。

## A. `d0df05a`（你第 77 轮 N1）

只看 `git show d0df05a`：空链 `--apply` 现在是否仍校验目标版本登记与队列参照、成功时仍不写盘。你建议的"路径搜索提前停止"哨兵测试决策者未采纳（提交信息有理由），可反驳。

## B. WP-H5 题→知识点权重的确定性聚合

任务书 `review/rounds/round-74-wp-h5-task.md`、`round-76-wp-h5-rules-task.md`、`round-78-wp-h5-hierarchy-task.md`、`round-79-wp-h5-split-task.md`；实现报告 `round-78-wp-h5-luna.md`、`round-79-wp-h5-split-luna.md`。
新规格 `contracts/topic_weights.md`；`contracts/knowledge_tree.md` 新增"层级"一节与 `ky/knowledge/hierarchy.py`；注册表新增 `reference.weight_batches`。

决策者裁定（可以反驳）：`topic_weight` 的汇总规则由探针从现有产物反推（cs408 上卷到 chapter，math1 / eng1 不上卷），方法文档 §1.3 以产物为准更正；`node_table_sha256` 只作来源记录（同批编码者之间值不一致）。

重点：
1. `tools/aggregate_topic_weights.py --check` 的"逐位相等"是否真的逐位（比较方式有无容差或字符串化掩盖）；重算是否完全不依赖现有 `topic_weights.json`（避免"读答案再写答案"）。
2. 增量性质：加一批时旧 `per_question` 逐字节不变的测试是否真能抓到回退；`topic_weight` 浮点累加顺序对"加一批"是否稳定。
3. 层级定义（最长的、在树中的点分真前缀）与现有树语法 / 投影的父节点逻辑是否一致；有无树能让两者给出不同父节点。
4. 聚合器的输入校验：编码节点不在生效树、题号缺失 / 重复、批次重复、`topic_rollup` 未登记科目、自命题卷的键规则。
5. 契约测试撤检查是否变红。

产物：`review/rounds/round-80-review-sol-out.md`，A、B 分别 PASS / FAIL，每条"必须改 / 建议改 / 不改"附可复现输入。只写这一个文件。
