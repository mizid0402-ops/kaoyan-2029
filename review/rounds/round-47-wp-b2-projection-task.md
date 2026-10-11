# Round 47 任务书：WP-B′2 投影迁移到工作区注册表 + 生效/补充分离 + 经契约读树（M15）

你是实现者（续同一会话）。只动 M15 投影（`ky/projection/`）及其测试、规格。
依据：`contracts/workspace.md`（§2.4 补充视图消费规则、§3.2、§4 缺失策略、§7 替换演练）、`docs/阶段2.5-接缝收口.md` D1 及其"连带后果"、审查项 B3。

## 先读：已提交的变化

- WP-B′1 已提交（`f386dac`），快照已走注册表，`build_snapshot(..., workspace=ws)` 可直接用于"快照与投影一致"的测试。
- `ky/workspace.py` 经 gpt-6-sol 两轮审查又改了 4 处（`9dc9191`、`63efad7`）：重复键路径改为节点树遍历、Windows 大小写别名去重、单次读取哈希、别名成环不崩。接口不变。
- 快照 CLI 同时捕获 `ContractError` 与 `KnowledgePointError`——投影 CLI 照此处理。

## 背景（为什么这样改）

- 现在投影读 410 版 408 树，快照读 403 版——同一系统报两个 408 数（A3）。D1 定生效树 = 403 版；410 版 + 附表是补充视图。
- 现在投影把附表 `knowledge_tree_agreement.yaml` 的 `source_support/source_count/evidence_tag` 按 ID 拼到每个知识点上；
  附表是**对 410 版**的注记，403 个共同节点里 380 个的 `source_count` 与 403 版实际来源数不同——拼到生效树上就是错的。
- 现在投影直接 `yaml.safe_load` 读树（B3），绕过了知识点契约（重复键、字段校验）。
- 现在投影对缺失输入 `if not path.is_file(): continue`，缺文件也能产出"成功"的投影。

## 要做的

1. **`ky/projection/__init__.py`**
   - 删除 `ROOT`、`TREES`、`AGREEMENT`、`INDEX_DIR`、`TOPIC_WEIGHTS`、`VOCAB_DB`、`DEFAULT_OUTPUT` 常量。
   - `build_projection(workspace: Workspace, out: Path | None = None) -> dict`；`out` 缺省 = `workspace.projection`。
   - 所有输入经 `workspace.require(...)` / `require_all(...)` 取得；**任一登记输入缺失 → `ContractError`，不产出、不替换已有投影**（旧投影原样保留）。
   - 知识树经 `ky.knowledge.load_knowledge_points` 读取（B3），不再 `yaml.safe_load`。附表用 `ky.models` 的严格 YAML 读取（拒绝重复键）。
   - **`knowledge_points` 表只收生效树**（`workspace.knowledge_trees` 的每一科），并**删除** `source_support / source_count / evidence_tag` 三列；`tree_source` 改为登记键（如 `reference.knowledge_trees.cs408`）。
   - 新表 **`supplementary_views`**(`view_name` PK, `kind`, `subject_id`, `description`)。
   - 新表 **`supplementary_knowledge_points`**(`view_name`, `knowledge_point_id`, `subject_id`, `domain`, `scope`, `title`, `parent_id`, `depth`, `tree_status`, `is_effective` INTEGER 0/1, `source_support`, `source_count`, `evidence_tag`, PK(`view_name`,`knowledge_point_id`))：
     每个 `cross_year_tree` 视图的补充树全部节点；`is_effective` = 该 ID 是否在同科生效树中；附表属性只进这张表。
   - 构建时校验（违约即失败）：生效树 ID ⊆ 补充树 ID；附表的 ID 集合 = 补充树 ID 集合。
   - 真题索引只读 `workspace.exam_indexes` 登记的文件（不再 glob 目录）。
   - `projection_meta.inputs`：键为相对 `workspace.root` 的 POSIX 路径，值为 sha256，**恰好是本次实际读取的文件**；另加 meta 键 `workspace_registry_sha256`。
   - 新增 meta `kp_effective_by_subject`、`supplementary_views`（名称列表）。`PROJECTION_SCHEMA_VERSION` 升为 **2**（表结构变了）。
   - 视图 `v_knowledge_points_by_subject` 保持只统计生效表；新增视图 `v_supplementary_not_effective`（`is_effective = 0` 的补充节点）。
   - `content_notice` 补一句：补充视图的节点与附表属性是跨年来源支持，不属于当年生效范围。
2. **`ky/projection/__main__.py`**：加 `--workspace`（发现规则同规格 §3.1）；`--out` 显式覆盖 `workspace.projection`；`ContractError` 与 `KnowledgePointError` → `contract violation: …` exit 2。
3. **`ky/projection/serve.py`**：`--database` 缺省改为注册表的 `projection`（加 `--workspace`）；显式 `--database` 仍覆盖。只改路径来源，不改其他行为。
4. **规格 `contracts/projection.md`**：表与视图的字段表（schema_version 2）、生效/补充分离规则、输入集合与哈希、确定性（同输入两次构建内容相同）、永不写回、缺失即失败。`docs/projection.md` 若与新结构冲突，改为指向该规格并更新表结构描述。
5. **测试**
   - 改 `tests/test_projection.py`：用仓库注册表；构建输出一律写到 `tempfile` 目录（**不要再写仓库里的 `data/projections/`**）；`test_node_count_matches_the_source_trees` 改为对照注册表里的生效树。
   - 新增 `tests/contract/test_projection_port.py`：
     - 仓库数据：`knowledge_points` 中 cs408 = 403；7 个 `legacy-item` ID 不在 `knowledge_points`，在 `supplementary_knowledge_points` 且 `is_effective=0`；补充表 cs408 共 410 行、`is_effective=1` 恰 403 行；`knowledge_points` 没有 `source_count` 等列。
     - **快照与投影一致**：对同一注册表，`build_snapshot(..., workspace=ws)` 的每科 `tree_total.count` 等于投影 `knowledge_points` 该科行数。
     - **替换演练**：临时工作区里把某科树、某个索引文件、权重、词库复制到另一相对路径并改注册表，投影读到新路径（`inputs` 键随之变化、计数正确）。
     - 缺失：删掉临时工作区里一个已登记的索引文件 → `ContractError`，且事先存在的旧投影文件逐字节不变。
     - 补充视图校验：附表缺一行 / 多一行、生效树含补充树没有的 ID → `ContractError`。
     - 确定性：同输入两次构建，除构建时间外内容相同（沿用现有做法）；`inputs` 恰好等于实际读取的文件集合。
   - `tests/test_projection_service.py` 按新参数调整，保持原有断言。

## 不做的

- 不投影学习状态（那是 WP-F）；不改 `data/` 下任何文件；不动快照、词汇通道、tools。
- 不重建仓库里的 `data/projections/kaoyan_projection.sqlite`（决策者统一重建）。

## 验收

1. `py -3.12 -m unittest tests.test_projection tests.test_projection_service tests.contract.test_projection_port tests.contract.test_state_snapshot_port tests.contract.test_workspace` 全绿。
2. 全量：只允许基线已知的 2 项失败。
3. `grep -rn "parents\[2\]\|safe_load" ky/projection/` 无结果。

## 产物

不要提交。报告：`review/rounds/round-47-wp-b2-projection-luna.md`（改动、表结构前后对照、验收输出摘要、规格歧义）。
