# WP-H3 实施报告

## 改动

- 新增 `contracts/paper_shape.md`、`contracts/exam_index.md`，并更新
  `contracts/workspace.md`：增加可选 `reference.paper_shapes` 登记。
- 新增 `data/paper_shapes/cs408.yaml`、`math1.yaml`、`eng1.yaml`；cs408 的 2023–2026
  `basis` 从固定提交 `924fb0e` 的 `paper_shape.py` 原文读入。数学一登记 2023–2026，英语一
  登记 2024–2026，只记录原有题量和题型段，不写分值。
- `ky/workspace.py` 解析可选卷面映射、限制科目键并暴露 `Workspace.paper_shapes`；根注册表
  登记现有三科卷面文件。
- `ky/exam/paper_shape.py` 改为严格 YAML 加载器，覆盖连续题号、题型、分值、答案字母、唯一
  `(年份, 出题单位)` 与非空依据校验；删除常量与 `shape_for`。
- `tools/verify_408_index.py` 增加可选 `paper_source` 和题号身份校验；科目来自注册表，卷面
  规则来自注册文件，按登记的读取器独立复核答案。未知科目卷面、未登记卷面、无读取器名均
  失败。原有索引字段、来源哈希、权重与校准检查保留。
- `tools/build_408_index_v2.py` 从注册表加载 cs408 卷面。
- 新增 `tests/contract/test_paper_shape_port.py`、`test_exam_index_port.py`；更新
  `test_workspace.py`。`test_check_questions_port.py` 的临时工作区去掉不适用于其单科夹具的
  根注册表卷面键，生产 M24 实现未改。
- `docs/模块地图.md` 更新 M5、M5′ 端口、替换边界、验收命令和 WP-H3 剩余缺口。

未改 11 份索引数据、权重、知识树、投影实现、`ky/review/check_questions.py` 与
`tools/classify_questions.py`；未提交。

## 索引身份预检

逐个核对了注册表当前登记的 11 份索引。每份顶层科目与年份均和所有条目一致，且每个
`question_id` 都匹配统考格式 `<科目>-<年份>-<两位题号>`。没有不满足项，因此没有修改索引数据。

## 验收结果

- 指定 unittest 模块组：`Ran 54 tests ... OK (skipped=1)`。
- 旧校验器（`924fb0e` 的 `tools/verify_408_index.py`，配套旧卷面模块）与新校验器对当前索引
  都输出 `ALL INDEX FILES VERIFIED`，退出码均为 0。
- 新校验器汇总：`ALL INDEX FILES VERIFIED`。
- `py -3.12 tools/mutation_test_408_index.py`：`all 8 mutations rejected; real index untouched`。
- `py -3.12 tools/mutation_test_knowledge_weights.py`：`all 6 mutations rejected; real index untouched`。
- 固定基线 `924fb0e:tools/build_408_index_v2.py` 与新版在系统临时目录分别输出 2023、2024、2025、
  2026；四个输出均逐字节一致。输出字节数依次为 44703、44747、44705、45011。未覆盖
  `data/exam_questions/`。
- 中文文件连续问号扫描：无命中。
- 全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。

## 建议与边界

- 投影目前仍未单列 `paper_source`；读取出题单位需要解析 `question_id`，建议后续投影包评估新增列。
- `tools/classify_questions.py` 仍是 cs408 专用关键词到知识点映射，并固定读取
  `reference.knowledge_trees.cs408`；按本任务范围未改。`ky/review/check_questions.py` 未发现科目
  或卷面写死项。
- `tools/build_408_index_v2.py` 仍是 cs408 来源采集适配器；新增卷面登记与索引校验不依赖它。
