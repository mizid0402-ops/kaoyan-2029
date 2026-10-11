# M24 核对出题端口

## 职责

按知识点从工作区登记的真题索引中选出可用于核对掌握情况的题目。只返回题目 ID、归属、映射权重和原始定位，不返回题目原文，也不生成题目或写入工作区。

宽松自评档的上层调用方可以使用此端口。没有关联真题时，端口返回空候选并给出 `fallback: ai_generated_allowed`。依决议 B10，AI 生成的巩固题只能产生 `validation=guided` 级证据，永不进入频率统计；本端口不负责生成或记录这种题目。

## 输入

- `workspace`: M0 `Workspace`，通过 `require_all("reference.exam_indexes.<subject>")` 读取索引；要求 `reference.topic_weights` 也已登记且可读。
- `knowledge_point_id`: 知识点 ID。其第一段必须对应工作区科目档案中的科目 ID。
- `exclude`: 可选的已做过题目 ID 集合，默认空集合。
- `limit`: 可选的非负整数数量上限；`None` 表示不限制。

M33 装配可通过 `load_check_question_sources(workspace, subjects)` 一次读取指定科目的索引和共享权重，
再调用 `candidate_check_questions_loaded(subject, knowledge_point_id, entries, per_question, *, outline, ...)`。
该计算入口只使用已解析的索引、权重和知识树，不从工作区路径读取文件；候选与错误规则同上。

## 输出

返回映射：`{"candidates": [...], "fallback": ...}`。每个候选包含：

| 字段 | 含义 |
|---|---|
| `question_id` | 索引中的题目 ID |
| `subject_id` | 索引中的科目 ID |
| `exam_year` | 索引中的考试年份 |
| `number` | 索引中的题号 |
| `weight` | 该题对目标知识点的映射权重 |
| `locator` | 索引中的原始定位对象 |
| `source` | 固定为 `past_question` |

有候选时 `fallback` 为 `null`。没有任何题目映射到目标知识点时，候选为空且 `fallback` 为 `ai_generated_allowed`。若关联真题均被 `exclude` 排除，候选为空且 `fallback` 为 `null`，因为数据中仍有可用真题来源。

## 选择与错误规则

1. 只选择 `knowledge_point_weights` 含目标 ID 的题目，或索引的 `knowledge_point_id` 等于目标 ID 的题目。
2. 权重依次取索引 `knowledge_point_weights`、`reference.topic_weights.per_question` 中键为 `<subject>-<year>-<number>` 的分布；只有直接 ID 映射且两处都没有权重时按单位权重 `1.0` 处理。
3. 每题只产生一个候选；索引逐题权重优先于聚合文件中的逐题分布。
4. 排序为权重降序、年份降序、题号升序；相同三项时按 `question_id` 升序保证确定性。
5. 排除 `exclude` 中的题目后应用 `limit`。
6. 每个登记索引条目的 `subject_id` 必须等于该索引登记的科目，`locator` 必须是映射。
   同一科目登记索引内的 `question_id` 必须唯一；重复项报错并指向第二次出现的字段，
   不去重、不择一。
7. 未知科目、缺失登记索引、损坏的 JSON 或无效的必要索引字段均抛出 `ky.models.ContractError`。索引缺失不降级为空结果。

## 可替换性

实现位于 `ky/review/check_questions.py`，由 `tests/contract/test_check_questions_port.py` 验收。此端口只读，可由保持相同输入、输出和确定性规则的实现替换。
