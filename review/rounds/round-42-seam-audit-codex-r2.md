# Round 42 Codex 独立判断：第 2 轮

已通读 `docs/阶段2.5-接缝收口.md` 与 `review/rounds/round-43-wp-a-queue-task.md`。本轮只读，未跑测试。

## a. 十步顺序

总体同意。**WP-D 在 WP-E 前合理**：规划者要读词汇剩余量，须先固定“冻结参考库的 15 条旧投放如何一次性导入状态、以后由谁写状态”的语义；现有 `ky/schedule/vocab_channel.py:102-122` 仍从旧表读取基线。WP-F **不必整体早于 WP-E**：若 WP-E 输入仍走 `snapshot/preflight`，它不依赖 SQLite 学习状态投影；但应在 WP-E 定输入包时先约定学习状态读模型，避免 WP-F 再造另一套口径。WP-F 实现可随后完成，必须早于前端。

有一处组织矛盾：§四要求“每个 WP 只落一个模块/端口”，但 WP-B′ 涵盖 M12/M15/M7/M5/M6，WP-E 涵盖 M19/M11，WP-D 横跨 M7/M13。建议把这些名称当**里程碑**，各模块迁移、词汇基线导入与规划者/路线落盘分别形成独立验收子包。§五第 9 步又把测试分层、历史脚本、行尾、CLI 帮助混在一包，也宜拆开；测试分层至少应在各 WP 契约测试开始时给出最小规则。

## b. D1 的连带影响

**最重要的遗漏是附表语义。**当前投影 `knowledge_points` 直接按 ID 接 `knowledge_tree_agreement.yaml` 的 `source_support/source_count/evidence_tag`（`ky/projection/__init__.py:123-156`）。该附表有 410 行、是对 410 版的注记；本机只读解析：403 个共同节点中 **380 个**的附表 `source_count` 与 403 树的实际 `len(sources)` 不同（例如附表 2、树 1），另有 7 行只属补充树。不能只把投影树路径改为 403 而保留原样拼接。应把附表和 410 版绑定为补充端口；若展示它，字段必须标明“跨年来源支持”，不可伪装成生效树自身来源数。决议 §二所写“387 个共同节点补来源”也与当前文件不符，当前差异数为 380。

`knowledge_points.knowledge_point_id` 目前是单列主键（`ky/projection/__init__.py:108-120`），所以 **403 生效树与 410 补充树不能同时作为两套完整行塞进这张表**。可让此表只收 403，并另设补充视图/表或单独投影；`v_knowledge_points_by_subject` 和 `projection_meta.inputs` 的计数、哈希也要随口径调整（同文件 `229-253`）。现有 `tests/test_projection.py:85-92` 用 `TREES` 自证计数，新增独立断言“cs408 生效点数=403、7 个 legacy ID 不在生效表、补充数据可追溯”。重建后若 Datasette 以 `--immutable` 服务旧库，还需验证服务端实际读到新投影。

PPT 是**间接链路**：`tools/extract_cs408_bundle.py:29-30,86-89` 读 410 树与附表生成 `tree_flat.csv`，`tools/build_408_deck_scaffold.py:27-35,119-130` 再读 CSV。若继续用 410，应在导出的节点和讲解页明确标识那 7 个 `legacy_only_pending`，避免把它们列为当年必学；若改用 403，须重定导出端，不能只改脚手架常量。附表原有校验器以 410 主表为对象（`review/rounds/round-29-tree-split-claude.md:117-121,169`），也不能直接拿它验证 403。

## c. WP-A 任务书验收

任务书抓到了主闭环，但失败测试只要求“空目录”。请补一个**已写分片被篡改/缺失**的 CLI 测试：`preflight` 和 `snapshot` 都必须 `contract violation`、退出 2、无 traceback；这直接验证 manifest/分片错误沿 `StorageError(ContractError)` 被捕获（`ky/storage/review_shards.py:60,400-418`；`ky/__main__.py:167-173,424-429`）。还应确认分片队列中未知 `subject_id` 仍被 `preflight` 的 `validate_items_against_config` 拒绝，而非只验证读成功。

验收第 2 条要求再跑全量 436 项，与本项目“最小范围验证足够就不跑全量”的要求不合，且当前多人同工作区会干扰结果。WP-A 的四个指定测试模块加上述 CLI 回归足够作为本包门禁；全量留给工作区稳定后的集成验收。`--items manifest.yaml` 的正例、扁平/分片等价、record 后到期计数变化均应保留。
