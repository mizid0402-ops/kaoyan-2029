# WP-H5 实施与验收报告

## 结论

WP-H5 已按第 74 / 76 / 78 轮决议实现。原 `topic_weights.json` 未改写；按新增清单与生效树
重算后，`--check` 对完整 JSON 比较通过，所有字段相等，逐位浮点差值为 0.0。

## 前序轮次结论与规则落地

- 第 74 轮只读探针曾确认 432 条 `per_question` 和所有 `batch_stats` 与产物一致；当时
  `topic_weight` 汇总规则和节点表哈希步骤尚未明确，所以按门槛暂停。第 76 轮继续核对后
  发现知识树对象没有 `parent_id`。决策者随后确认轻量 M4 层级接口路径，并裁定汇总与哈希
  规则。
- 第 78 轮在 `contracts/knowledge_tree.md` 写明：父节点为树内最长点分 ID 真前缀，祖先由
  重复父查询得到。新增 `parent_id()` 与 `nearest_ancestor_with_scope()` 公共函数，M6 只
  通过后者查找 cs408 的 chapter 祖先；原 `tree_grammar.py` 私有检查未改，避免改变树语法
  校验行为。
- `topic_weight` 累计未舍入逐题分布，严格按清单批次、首位登记 coder 的题号出现顺序、
  逐题节点插入顺序执行浮点加法。`per_question` 继续舍入到三位小数。cs408 按祖先上卷；
  math1 / eng1 按编码节点汇总。清单记录 `topic_rollup`、coder 与置信度权重。
- `node_table_sha256` 未写入批次清单，聚合器不读取或校验它；每个实际编码节点都通过 M4
  知识树端口加载的生效树做成员校验。错误指出 coder、题号与节点 ID。
- 已重新核对无年份文件 `map-sol.json`、`map-luna.json`、`map-claude.json`：三者的
  `meta` 均为 cs408 2024。它们摘要值相同，但按新裁定只保留来源信息，不作为校验依据。

## 修改落点

- **M4 层级端口**：新增 `ky/knowledge/hierarchy.py` 并从 `ky.knowledge` 导出两个查询函数；
  更新 `contracts/knowledge_tree.md` 和 `tests/contract/test_knowledge_tree_port.py`。
- **工作区登记**：在 `contracts/workspace.md`、`ky/workspace.py` 与
  `tests/contract/test_workspace.py` 增加可选 `reference.weight_batches`，含有效路径、越界
  路径与缺省测试；主注册表已登记批次清单。
- **M6 数据与实现**：新增 `data/review_weights/batches.yaml`、
  `contracts/topic_weights.md`、`ky/exam/topic_weights.py` 和
  `tools/aggregate_topic_weights.py`。工具提供互斥 `--check` / `--write`；检查不一致时
  递归列出字段差异。
- **规则与模块图**：方法文档 §1.3 加入粒度更正；`docs/模块地图.md` 更新 M4、M6 行及
  M6 规格、实现、注册键和验收命令。
- 新增 `tests/contract/test_topic_weights_port.py`：登记产物复现、逐题旧 JSON 序列化不变的
  增量、题号缺失、题号重复、批次重复和生效树外节点六项契约。
- 未改 `topic_weights.json`、编码者 JSON、索引数据、`tools/apply_knowledge_weights.py` 或
  `tools/verify_408_index.py`。未提交。

## 复现比较

最终执行 `py -3.12 tools/aggregate_topic_weights.py --check` 输出：

```text
topic_weights.json matches registered batches
```

这比较了完整结构中的 `meta`、`batch_stats`、各科 `topic_weight` 与所有
`per_question` 分布；无字段差异，浮点结果精确相等。

## 增量与负例

指定 unittest 命令中的 M6 六项契约均通过。合成批次由注册数据推导科目与下一年份，包含
一致、2:1 分裂和低置信度题；旧逐题对象的紧凑 JSON 序列化前后相同，新 chapter 权重增加
恰好 3.0，其余旧 chapter 权重不变。负例分别覆盖未知节点、缺失题号、重复题号和重复批次，
均按预期抛出 `ContractError`。

## 指定验收输出

命令：

```text
py -3.12 -m unittest tests.contract.test_topic_weights_port tests.contract.test_workspace tests.contract.test_knowledge_tree_port tests.test_verify_tree_shapes
```

结果：54 tests，11 failures，1 error，1 skipped。M6 六项契约和新增 M4 层级正反例均通过。
其余错误/失败与 worktree 未包含 `data/raw_materials/` 有关：

- `test_1_repository_registry` 在 `workspace.require("materials.raw_root")` 遇到该登记目录
  缺失。
- 知识树读取器的 `test_readers_accept_same_tree_with_deterministic_frequency`，以及
  `tests.test_verify_tree_shapes` 中 10 个变异断言，在 `verify_tree` 输出了登记来源文件
  缺失信息后未得到预期语法错误文本。缺失资料包括数学大纲两份 HTML、CS408 大纲 HTML。
- 1 项跳过由现有测试的环境条件触发。

命令：

```text
py -3.12 tools/aggregate_topic_weights.py --check
```

结果：exit 0，现有产物与重算结果匹配。

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。含中文文件已检查，没有连续三个问号。

## 建议

当前已达到本工作包要求。决策者提交前统一全量测试时，需提供登记树来源引用的
`data/raw_materials/` 文件，或把相应原始资料缺失作为该环境的已知限制单独记录。
