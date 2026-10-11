# 任务书：WP-H5 题→知识点权重的确定性聚合与增量（M6，决议 D5）

先读仓库根 `AGENTS.md`，再读：`docs/题-知识点映射-多模型交叉验证方法.md`（方法、置信度权重、产物说明）、
`docs/阶段2.5-接缝收口.md` §七 D5 与 H5 行、`docs/模块地图.md` M6 行、`contracts/workspace.md`、
`tools/apply_knowledge_weights.py`（权重的下游写入者）、`tools/verify_408_index.py`（权重分布规则与 `WEIGHT_SUM_TOLERANCE`）。

你在独立 git worktree 里工作（派发时的工作目录）。本包用到的 `data/review_weights/` 是 git 跟踪的，不需要 `data/raw_materials/`。

## 为什么做

`data/review_weights/topic_weights.json`（注册表 `reference.topic_weights`）是三个编码者产出（`data/review_weights/coder_outputs/`）按
置信度加权聚合出来的，但**产生它的聚合代码不在仓库里**。结果是：下一年的真题打完标以后，没有办法按同一方法把它加进去，
更没法证明旧年份的结果没被改动。

目标：**新一年 / 新科目的题 = 放三份编码者产出 + 在批次清单里登记一行 + 跑聚合；旧批次的逐题结果逐字节不变。**

## 决策者已定的设计（照做；有更好的写法先在报告里提，不要自行改设计）

### 1. 批次清单（数据）+ 注册表键

- 新文件 `data/review_weights/batches.yaml`，注册表新增**可选**键 `reference.weight_batches` 指向它。改 `contracts/workspace.md` §2.1、`ky/workspace.py`、`tests/contract/test_workspace.py`（正例 + 路径越界负例，照已有键的写法）。
- 清单每一批：`subject_id`、`exam_year`、可选 `paper_source`（缺省 `national`）、`node_table_sha256`、`coders`（编码者名 → 产出文件路径，路径相对工作区根）。
  三个编码者名与置信度权重表（high 1.0 / medium 0.6 / low 0.3）从现有 `topic_weights.json` 的 `meta` 读出来写进清单顶层，不要在代码里写死。
- 现有 11 批照实登记：cs408 2024 那一批用的是不带科目年份的 `map-sol.json` / `map-luna.json` / `map-claude.json`——**先打开核对**它们确实是 cs408 2024（看 `meta`），再登记。

### 2. 聚合器（新规格 `contracts/topic_weights.md` + 实现）

- 规格写清 `topic_weights.json` 的现有格式（`meta` / `batch_stats` / `topic_weight` / `per_question`）与聚合规则（逐题按置信度权重 ÷ 该编码者列出的节点数投票，归一化到 1.0，按方法文档的舍入；`topic_weight` 按方法文档的汇总粒度求和）。
  `per_question` 的键规则按现有数据描述（现有键形如 `cs408-2023-1`，**不补零**，与索引的 `question_id` 不同——照实写进规格，不改）；自命题卷的键加出题单位，写一条规则。
- 实现放 `ky/exam/topic_weights.py`（模块头写明 M6 与规格），纯函数：输入清单 + 各编码者产出 + 各科树节点，输出与文件同结构的映射。编码者产出与树经注册表 / 知识树端口读取。
- 工具 `tools/aggregate_topic_weights.py`：`--check`（重算并与登记的 `topic_weights.json` 比较，不一致退出 1 并列出差异）与 `--write`（写出）。

### 3. 第一步必须是复现现有文件

**先**用清单对现有 11 批重算，与现有 `topic_weights.json` 按字段比较（`per_question` 每题分布、`topic_weight` 每节点、`batch_stats`、`meta`）。
- 完全一致 → 继续。
- 不一致 → **停下来**，在报告里列出差异（哪些题 / 节点、差多少、你认为的原因：舍入位置、早期运行、节点表版本……），**不要改 `topic_weights.json`，也不要为了对上而在代码里加特判**。决策者据此决定。
  （方法文档 §2.1 提到"另 2024 的 3 份早期运行"，差异很可能来自这里。）

### 4. 增量性质

聚合必须是"逐批独立"的：一批的 `per_question` 只由该批的三份产出决定。加一批时旧批次的 `per_question` 条目逐字节不变，`topic_weight` 只增加新批的贡献。

## 不做的

- 不改 `topic_weights.json`、编码者产出、索引数据文件；不改 `tools/apply_knowledge_weights.py`、`tools/verify_408_index.py`。
- 不重新打标、不调用任何模型。
- 不改投影、不改 M24。

## 测试（只写这些）

`tests/contract/test_topic_weights_port.py`（新）：
1. 复现：对登记清单重算，与登记的 `topic_weights.json` 按字段相等（若第 3 节发现不一致，这条先不写，报告里说明）。
2. 增量：在临时工作区复制清单与产出，追加一批合成的新年份（三份合成产出，含一致、2:1 分裂、低置信度三种题），重算：旧批次每条 `per_question` 的 JSON 序列化逐字节不变；`topic_weight` 的增量等于新批贡献。
3. 负例各一条（断言具体错误子串）：产出里的节点不在树里、题号缺失 / 重复、清单里批次重复、`node_table_sha256` 与该科树节点表不符（先看方法文档怎么算节点表哈希；算不出来就写进报告，不要猜）。
不写数据量字面量。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_topic_weights_port tests.contract.test_workspace
py -3.12 tools/aggregate_topic_weights.py --check
```

另：`docs/模块地图.md` 的 M6 行改为指向新规格、实现、契约测试与验收命令。

## 报告

`review/rounds/round-74-wp-h5-luna.md`（在你的 worktree 里）：清单核对结果（尤其 cs408 2024 那批）、复现比较结果、改了哪些文件、验收输出、建议。
写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。含中文的文件写完查 `???`。
