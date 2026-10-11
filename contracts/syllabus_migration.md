# 大纲版本迁移端口（M25）

对应决议：`docs/阶段2.5-接缝收口.md` §七 D5/H4；审查项 B7。

## 1. 职责与边界

M25 将复习队列中的知识点 ID 沿已登记的大纲映射迁移，并检查未退役队列项是否引用
科目的生效树。纯函数不读取注册表或文件；CLI（M14）负责按注册表加载映射、队列和树。
本端口不迁移完成事件或日计划中的历史 `review_id`，也不修改队列 manifest schema。

实现：`ky/review/syllabus_migration.py`。错误使用 `ky.models.ContractError`；输入映射为
`ky.knowledge.syllabus_mapping.SyllabusMapping`，队列记录为 `ky.models.ReviewItem`。

## 2. 纯函数

### `resolve_mapping_chain(mappings, from_version, to_version)`

输入为某科全部已登记映射，按 `from_version → ... → to_version` 返回唯一连续链，类型为
`tuple[SyllabusMapping, ...]`。先拒绝重复版本边和映射图中任意成环，再处理起止版本相同的
空链请求。无路径、多路径、重复版本边或映射图中任意成环均抛 `ContractError`，错误说明原因。
查找多路径时找到第二条即可停止搜索。

### `plan_queue_migration(items, chain, *, subject_id)`

只迁移指定科目且 `state != "retired"` 的项；其他项保留原对象值。按链顺序逐步应用，拆分项
会继续进入下一步映射。`targets(id)` 为原 ID 时不变；单目标改 ID 并递增 revision；多目标时
退役原项并为每个目标创建新项（ID 为 `<原 review_id>><目标 ID>`、revision 为 1、defer_count 为
0，其余字段复制）；零目标只退役并递增 revision。拆分新 ID 冲突时拒绝。源树中无此 ID 时
拒绝整次迁移，并在错误中列出全部悬空 review_id。

每步结束后同科、同知识点的未退役项去重：优先保留 `state == "queued"` 的项；都不是
`queued` 时再按原规则。相同优先档按 due_date 最早、再按 review_id 字典序保留；其他项退役且
revision 加一。

返回 `MigrationPlan`：完整 `items`，以及 `unchanged`、`renamed`、`split`、`retired`、
`merged` 五组按 review_id 排序的元组。类别可用于 CLI 报告；`retired` 包括映射删除、拆分源项
及去重时产生的退役项，`merged` 列出去重淘汰项。分类可重叠，例如一项可同时属于
`renamed`、`merged` 和 `retired`。

### `check_queue_references(items, tree_ids_by_subject)`

检查所有未退役项的 `knowledge_point_id` 是否存在于该科目的生效树 ID 集。树未登记时报告
“该科无生效树”，ID 缺失时报告具体队列项和缺失 ID；无问题返回空列表。

## 3. CLI

```text
py -3.12 -m ky review-queue check [--workspace W] [--store DIR]
py -3.12 -m ky review-queue migrate --subject S --from YYYY [--to YYYY]
    [--workspace W] [--store DIR] [--apply]
```

缺省工作区按 M0 发现；`--store` 缺省使用 `Workspace.review_queue` 写入目标路径，不调用
`require()`。迁移目标缺省为
`Workspace.effective_version(subject)`。映射文件只从
`reference.syllabus_versions.<subject>.mappings` 读取，且每个路径经
`load_syllabus_mapping(..., subject_id=subject)` 校验。检查命令按每科 `knowledge_trees` 生效树
构建 ID 集。

迁移默认只打印计划。`--apply` 遇到空链（`from == to`）打印“无需迁移（from == to）”并退出，
不写队列。其他迁移在写入前对目标版本树运行参照检查，成功后经
`ReviewShardStore.write` 原子写入；schema-1 队列含已复习项时遵循 M13 拒写保护。

退出码：0 成功，2 契约违规，3 用法错误。CLI 不绕过旧版队列保护。

## 4. 验收

`py -3.12 -m unittest tests.contract.test_syllabus_migration_port tests.contract.test_syllabus_mapping_port tests.test_cli tests.test_review_queue_advance`
