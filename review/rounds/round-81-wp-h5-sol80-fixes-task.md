# 任务书：修复 sol 第 80 轮对 WP-H5 的 B1 / B5 / B6（+ B2、B8）——M6 与其写回工具

先读 `review/rounds/round-80-review-sol-out.md` B 节（每条有复现输入）。遵守 `AGENTS.md`。H5 已合入 master，你在主工作区改，不提交。
**另一个 luna 同时在改投影（`ky/projection/`、`contracts/projection.md`、`tests/contract/test_projection_port.py`、`tests/contract/test_knowledge_tree_port.py`）——不要碰这些文件。**

## 必须改

1. **B1**：`tools/aggregate_topic_weights.py --write` 不读旧产物，只从清单 + 编码者产出 + 生效树重算后写出；只有 `--check` 读旧产物。
   写出目标取注册表登记的 `reference.topic_weights` 路径，允许文件尚不存在，但路径必须落在工作区内（照 `ky/workspace.py` 的越界判定做法，不要自己另写一套；若 `Workspace` 没有给写入目标用的公开检查，先在报告里说明你用了什么）。
   补测试：旧产物内容损坏（非 JSON）与文件缺失两种情况下 `--write` 都能重建，且重建结果 `--check` 通过。
2. **B5**：批次身份与 H3 一致：`exam_year` 为四位年份，`paper_source` 匹配 `^[a-z][a-z0-9]*$`（缺省 `national`）。能复用 H3 已有的公开定义就复用，没有公开定义就在 M6 按规格写并在报告里指出重复点。
   补负例：年份 `1`、出题单位 `school-x`；正例：`paper_source: xidian` 通过。
3. **B6**：`tools/apply_knowledge_weights.py` 能处理自命题卷的 `per_question` 键（`<科目>-<出题单位>-<年份>-<题号>`，见 `contracts/topic_weights.md`），并把它写回对应 `paper_source` 的登记索引；
   统考键的行为与写回结果**不变**（按 `AGENTS.md` 11–12 条：用固定基线 `11cda18` 的旧版工具与新版在同一份临时副本上各跑一次，比较被写回的索引文件逐字节一致）。
   键的解析按规格定义的格式来（这是规格定义的标识符格式，不是从自由文本猜结构）；与索引的对应关系用 `(科目, 年份, 出题单位, 题号)`。补一条含学校卷键的测试（临时工作区）。
   这个工具目前没有契约测试模块的话，测试放 `tests/contract/test_topic_weights_port.py`。

## 同时做

4. **B2**：规格、工具输出与报告里把"逐位相等"改为"无容差的数值相等"（`0.0 == -0.0` 视为相等，写明）。
5. **B8**：规格写明 `nodes` 为空的条目可省略 `confidence`（它不投票），与实现一致。

## 不做的

不改投影、知识树端口、`topic_weights.json`、编码者产出、索引数据文件（B6 的测试在临时副本里写回）。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_topic_weights_port
py -3.12 tools/aggregate_topic_weights.py --check
py -3.12 tools/verify_408_index.py
```

每条新负例临时撤掉对应修复确认变红，再还原，写进报告。

## 报告

`review/rounds/round-81-wp-h5-sol80-fixes-luna.md`：逐条落点、B6 固定基线对照结果、撤修复记录、验收输出。全量：未跑。不提交。含中文文件查 `???`。
