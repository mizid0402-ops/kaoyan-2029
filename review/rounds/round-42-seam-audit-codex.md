# Round 42 Codex 独立判断

> 核查环境：2026-09-25，Windows，`py -3.12`，HEAD `cf3f5ab`。仅新增本报告；A4 样本和测试日志位于系统临时目录。下文“未核实”不等于否定。严重度按报告的 P0/P1/P2 标注。

## 1. 逐条核实

| 编号 | 结论 | 证据 | 严重度意见 |
|---|---|---|---|
| A1 | 部分属实 | `ky/contracts/__init__.py:1-7` 明言包未使用；仓库没有 `*.schema.json`。但“所有文件格式只存在于 `frozenset`”过强：`tools/verify_408_index.py:64-81,157-277` 已规定真题索引键、枚举和语义，`ky/storage/review_shards.py:267-326` 规定分片 manifest；只是缺独立、跨语言且完整的端口规格。 | 关键跨模块端口 P0；把所有格式一次性补齐并非每个模块开工的 P0。 |
| A2 | 部分属实 | `ky/projection/__init__.py:39-51` 固定树、索引、权重、词库；`ky/schedule/state_snapshot.py:43-53` 固定树约定；`tools/build_408_deck_scaffold.py:22` 固定盘符。已有局部覆盖入口：`ky/__main__.py:78-79,403-407` 可传配置、队列、词库，`ky/schedule/state_snapshot.py:139-157` 可注入 `tree_paths`。 | M12/M15 生效数据分叉应 P0；“所有路径都写死”不成立，余项 P1。 |
| A3 | 属实（“两套权威”是判断） | `ky/schedule/state_snapshot.py:46-53` 读 403 节点版，`ky/projection/__init__.py:43-45` 读 410 节点版；`tools/verify_408_index.py:109-121`、`tools/classify_questions.py:38`、`tests/test_tree_integrity.py:33-35` 仍读 403 版。只读解析实测：两树 403 个共同 ID，410 版额外 7 个 `legacy-item`；共同节点中 380 个仅 `sources` 不同。 | 同意 P0：同一 408 口径在快照和投影中不一致；选树需要先定“当年考纲”还是“跨年历史”。 |
| A4 | 属实 | 用 `load_review_items` 取 `tests/fixtures/reviews/reviews-normal.yaml` 的 3 项，`write_review_queue(<TEMP>/round42-review-shards-… , items)` 写分片，`load_review_queue` 读回 3 项。随后 `py -3.12 -m ky preflight --config tests/fixtures/config/config-minimal.yaml --items <该目录> --date 2026-09-25` 与同参 `snapshot` 均输出 `contract violation: file does not exist: <该目录>`、退出 2。代码 `ky/__main__.py:424-429` 使用 `load_review_items`，而 `ky/storage/review_shards.py:553-557` 的 `load_review_queue` 可识别目录。 | 同意 P0，已落地的 CLI 主链路断开。 |
| A5 | 部分属实 | `docs/阶段2决议-预算与词汇编排.md:106-121` 将数值决策交给当天 AI；`ky/storage/day_plan_store.py:65-68` 的日计划字段无 actor、输入哈希；仓库无 planner 输入包或 staging/apply 入口。已有通用 `day-plan submit` 校验落盘，见 `ky/__main__.py:495-539`，因此“没有 apply 命令”字面不准；它没有 staging 约束或来源审计。 | 对将要接入的 AI 规划者是 P0 门禁；对当前纯函数与存储模块是 P1，不应笼统说全部不合格。 |
| B1 | 属实 | `ky/schedule/completion.py:64-69` 明写 self-assessed quality；`125-188` 以它决定通过、间隔和到期日；`docs/评审结论与实施契约.md:209-214` 明确自评不能改 due_date 或提高 quality。`review_clip.py:16,209-211` 对 `last_self_rating` 的限制不能覆盖完成事件的另一条路径。 | 同意 P1，且应在复习算法端口定稿前解决。 |
| B2 | 部分属实 | 对 SQLite 以 `mode=ro` 查询：`delivery_log=15`、`words=3409`、`source_entries=5530`。`tools/daily_words.py:119-149` 可直接删/增旧投放记录；但“4 个写入口”混合了建库脚本、验证器的临时副本变异与生产写入，`ky/schedule/vocab_channel.py:56,102-119` 明确只读，`tests/test_monthly_close.py:100-115` 锁定新流程不改此库。 | 同意 P1 的状态/参考数据边界问题；生产写入口数量被夸大。 |
| B3 | 属实 | `ky/projection/__init__.py:123-155` 用 `yaml.safe_load` 读树并自行取键，未调用 `load_knowledge_points`；`ky/models.py:248-287` 的重复键扫描不经此路。`ky/` 无真题索引及权重的统一加载契约，当前强校验在 `tools/verify_408_index.py`。 | 同意 P1；投影输入失效可污染派生视图。 |
| B4 | 属实 | `ky/schedule/planning.py:84-101` 有 RoutePlan 和 `stage1_input_hash`，`ky/__main__.py:122-131` 只有 preflight、ledger、snapshot、day-plan、month-close；`ky/schedule/longitudinal.py:117-136` 的 DayPlan 只有分钟/渠道/科目，无任务 ID。未找到路线落盘或该哈希的生产者。 | 同意 P1；应拆到 M11 路线端口和 M19 规划输入端口。 |
| B6 | 部分属实 | `ky/models.py:311-321` 仍称 `total_daily_minutes` 为唯一权威；与 `docs/阶段2决议-预算与词汇编排.md:8-15,106-121` 冲突。但 `ky/schedule/review_clip.py:227-231,268` 支持逐日覆盖，`ky/schedule/longitudinal.py:194-198` 明确不要求 `available_minutes` 等于固定数。 | P2 文档/配置语义漂移更准确；并非运行时强制 120。 |
| B7 | 部分属实 | 队列项只有 `knowledge_point_id` 的局部格式校验，未见与生效树联查；`ky/projection/__init__.py:130-155,172-221` 无外键。但“权重→树、索引完全无检查”不对：`tools/verify_408_index.py:229-266` 验证索引内权重 ID 属于树；`tests/test_projection.py:78-84` 检查投影中的题权重关联。`topic_weights.json` 到索引的全量双向校验仍未见作为运行时门禁。 | 同意 P1 的跨端口缺口，但应明确已有检查及未覆盖的边。 |
| C1 | 部分属实；干净克隆数字未核实 | 本机按指定命令 `py -3.12 -m unittest discover -s tests -t .`：**Ran 436，434 过、2 败、退出 1**；失败为 `test_eng1_vocabulary` 缺 `%TEMP%/kaoyan-probe/claude2/dl/bv_e1_2024.pdf`，`test_round24_weighted_tree` 缺 `%TEMP%/kaoyan-probe/ghsurvey/downloads/408_syllabus_2022.pdf`。Linux 报告的第三项 datasette 故障本机未复现。未删 `data/raw_materials/`，故 598 failures + 5 errors 未核实；`tests/test_tree_integrity.py:68-98` 确实依赖原始资料。 | 把可移植测试门禁列 P1 更合适，尤其替换验收需可在干净环境运行。 |
| C3 | 部分属实（历史状态，当前不成立） | 当前 `git status --short` 只有未跟踪项，`git diff --stat` 与 `git diff --ignore-cr-at-eol --stat` 均为空；已跟踪索引 `git ls-files --eol data/exam_questions/408_index_2024.json` 显示 `i/lf w/crlf attr/-text`，确有按原始字节哈希漂移的条件，但“工作区 60 个已修改文件”不是当前状态。 | 同意 P2 风险；不能把旧副本的 60 文件计数当作本机现状。 |

补充实测：`py -3.12 tools/verify_tree.py` 对 403、410 两树均 `ALL CHECKS PASSED`、退出 0；`py -3.12 tools/verify_408_index.py` 为 `ALL INDEX FILES VERIFIED`、退出 0。全量测试包含命名为 mutation 的测试用例；没有单独执行变异脚本，测试后 `git diff --stat` 为空。

## 2. 推进顺序意见

**阶段 2.5 应插在 ④ 课表之前，但按模块/端口交付，不宜把七项做成七个横向大包。**我建议：

1. **M0 + M4/M12/M15：先定生效数据和关键端口的最小规格。**明确工作区配置的路径解析、版本、缺失文件和输入哈希语义；定 408 树的“当年生效/历史补充”边界。第 3 步的关键端口规格应前移到第 1 步之前；其余规格跟随对应模块实现。
2. **M13 + M14：立即修 A4。**CLI 与分片存储共用队列加载端口，做扁平文件与分片目录的往返契约测试。原第 2 步可并行设计，但作为第一个小修补优先落地。
3. **M12/M15/M5/M6/M7：接入工作区配置并收紧读取端口。**原第 1 步拆成配置规格、各模块迁移、最后清理历史脚本；不应“一次去掉所有写死路径”。同时补 B3/B7 的参照校验、B2 的旧写入关闭和状态迁移。每个端口迁移后立即跑该端口的契约测试，原第 4 步不必等全部规格写完。
4. **M10 + M11 + M19：先决议 B1/B5，再做路线、规划输入、staging/apply。**B1 决定复习算法的输入；B5 决定是否存在 study 适配端口。将原第 6 步提前。M19 可先认 `availability` 端口的手填输入，④ 再实现课表来源；日计划还需具体任务关联。
5. **M15 + M16：在前端前增加学习状态投影与保存后刷新契约。**报告的七步没有覆盖这个已确认的消费端缺口：`ky/projection/__init__.py:87-284` 当前只投影参考数据，而 `docs/前端设计-范围与待定.md:64-70` 要求写课表后重建并即时显示。最后再更新 README，给每个模块列替换步骤和最小验收命令。

**第 1 步与第 3 步：第 3 步的核心规格先做。**`kaoyan.workspace.yaml` 自身就是端口；若先写文件并让所有调用方依赖它，随后才讨论路径相对谁解析、允许哪些数据版本、切换树是否连同来源/权重一起切换，会把错误语义固化。先做短规格和当前消费者清单，再实现工作区配置；详细 JSON Schema 可随模块逐步补。

**A3 生效树：当前 2026 考纲口径暂选 403 节点 `knowledge_tree.yaml`。**两树共享全部 403 ID；410 版只增加 7 个仅由 2022 大纲文本支持、标为 `legacy_only_pending` 的节点（`review/rounds/round-29-tree-split-claude.md:76-79,110,149`），当前 11 份索引和 `topic_weights.json` 对这些 ID 的引用数均为 0（本机只读解析）。索引校验、题目分类、词表、树完整性测试读 403；投影及 PPT 脚手架读 410。410 版可保留为明确命名的跨年补充视图，不能无标记地当“2026 考纲生效树”。若用户决定目标是跨年知识全集，可改选 410，但须先定义旧年独有节点的状态/显示语义并迁移所有消费者；两树均通过当前验证器，不构成“410 已经是当年权威”的证明。

**B1：倾向加证据字段，并同时更改计算门禁。**`ReviewCompletion` 应区分自评与有客观作答/回忆证据的结果；仅证据支持的 `quality` 可推进间隔。无证据时沿固定保守规则安排下次复习。单纯新增字段而仍用自评算 due_date 不能解决冲突；直接修订不变量③会放弃已明确的安全边界（`docs/评审结论与实施契约.md:214`）。

**B5：倾向正式作废“必须修改 study 内核”这一实施承诺，保留可选适配器端口。**契约 `docs/评审结论与实施契约.md:172,193-206` 和 `README.md:4,79` 写了混合架构，但 `rg study_workspace ky` 无引用，当前模块已有独立真相源、排程与存储；此时强行落地跨仓库内核依赖会降低可替换性。若未来确有复用需求，再以用例和契约测试论证通用适配器。此项是架构建议，作废决议仍须由项目决策者更新契约。

## 3. 报告的错漏

- **过度概括**：A1 的“所有格式只在 frozenset”、A2 的“换目录都要改代码”、A5 的“没有 apply 命令”、B2 的“4 个写入口”、B7 的“完全没有参照检查”均需按上表收窄。
- **环境结论需分开**：Linux 3.10 的 433/436 与本机 3.12 的 434/436 不同；第三项 datasette 失败不是跨环境固定缺陷。干净克隆的 598 failures + 5 errors 本轮没有复现，不应写成已核实事实。C3 的 60 个行尾修改也不是当前工作区状态。
- **缺少重要前置决策**：报告的配置示例直接把 410 版设为 cs408 生效树，却未讨论 7 个 `legacy_only_pending` 节点只来自旧大纲，也未列全仍消费 403 版的分类器、索引校验器及测试；“切换一行配置”目前远远不够。
- **七步漏了消费端能力**：M15 尚无学习状态投影；仅补写入端口和 workspace 配置不能兑现前端“保存后页面即时反映”。此外 B2/B3/B7 在 §6 没有明确落到模块/端口，应列为各自的验收项。
- **“任意部分可替换”的判准不够可测**：替换需要保持哪些语义、接受哪些历史数据、如何回滚和验证跨端口参照，应先给典型替换演练。纯函数可替换性 A 是相对评价，不能单凭“无 I/O”证明替换后全系统正常。

## 4. 一句话总结

先把生效树与端口语义定清，再按 M13/M14、M12/M15、M10/M11/M19 等模块逐个收口和验收；报告指出的接缝问题真实，但若照原七步横向推进，会固化 408 口径分叉并漏掉前端所需的状态读模型。
