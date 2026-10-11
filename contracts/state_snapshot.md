# 状态快照端口（M12）

## 复习队列计数接口

`count_review_items_by_subject(items: Sequence[ReviewItem], day: date) -> Mapping[str, ReviewCounts]`
是纯计数函数，只读取调用方提供的复习项序列与日期，不读取存储或系统日期。返回映射按
`subject_id` 排序；缺少的科目由调用方按零值行处理。

`ReviewCounts` 包含 `in_review_queue`、`due_today_count`、`due_today_minutes` 与
`backlog_minutes`。队列项计数包含 `queued` 和 `scheduled`；到期今日仅统计 `queued` 项并使用
`due_date == day`；积压分钟复用 M27 判定，统计 `queued` 与 `scheduled` 且 `due_date < day` 的项。
`build_snapshot` 使用同一函数，
仍按配置中的科目顺序输出全部科目，包括零值行。

## 职责与输入

状态快照是只读状态展示：汇总配置科目、已加载复习队列、知识树节点数、可选的考试日期差值和词汇通道计数。它不制定今日计划，也不生成学习建议。

`build_snapshot(config, items, ..., workspace=None)` 的输入由调用方提供：

| 输入 | 来源与优先级 |
|---|---|
| `config` | 调用方显式传入的考试配置。给出 `workspace` 时，每个 `config.subjects[i].subject_id` 必须属于 `workspace.subjects`。 |
| `items` | 调用方显式加载的复习队列；本函数不加载队列。 |
| 科目知识树 | 显式 `tree_paths` 映射优先；否则用 `workspace.knowledge_trees`。显式映射作为本次调用的完整树路径来源。 |
| 词汇数据库 | 显式 `vocab_db` 优先；否则用 `workspace.vocabulary_db`。 |
| `today`、`target_exam_date` | 调用方给出的日期；`target_exam_date` 缺省时 `days_to_exam` 为 `null`。 |

若 `workspace`、`tree_paths`、`vocab_db` 均未提供，`build_snapshot` 抛 `ContractError`。它不自行发现工作区；CLI 才调用 `load_workspace`，按工作区端口的显式参数、`KY_WORKSPACE`、向上查找优先级完成发现。CLI 的 `--vocab-db` 覆盖工作区词库路径。

## 缺失策略

- 配置科目在 `workspace.subjects` 中、但在 `workspace.knowledge_trees` 中未登记树：该科目的 `tree_total` 为 `null`，例如 politics。
- 给出的 `workspace` 中，树已登记但文件不存在、不是文件或解析后越出工作区：通过 `workspace.require("reference.knowledge_trees.<subject>")` 失败，向调用方抛 `ContractError`。加载快照不得将这类错误折算成 `null`。
- `workspace` 登记的词库缺失、不是文件或越出工作区：通过 `workspace.require("reference.vocabulary_db")` 失败，抛 `ContractError`。
- 显式 `vocab_db` 是覆盖值；按既有行为，若其目标文件不存在则 `vocab` 为 `null`。显式 `tree_paths` 中未给出的科目或显式树文件缺失时，该科目的 `tree_total` 为 `null`。
- 给出 `workspace` 后，如果配置出现未登记在 `workspace.subjects` 的科目，按 `subjects[i].subject_id` 抛 `ContractError`。

## `--json` 输出

`snapshot_to_mapping(snapshot)` 是快照 JSON 字段形状的唯一来源；CLI 与 M19 输入包都调用它。
CLI 只负责将该映射序列化输出。

顶层 JSON 对象只包含下列字段：

| 字段 | 类型 | 含义 |
|---|---|---|
| `as_of` | ISO 日期字符串 | 快照采用的 `today`。 |
| `days_to_exam` | 整数或 `null` | `target_exam_date - today` 的天数；未传目标考试日期时为 `null`。 |
| `subjects` | 对象数组 | 按配置顺序逐科给出的状态。 |
| `vocab` | 对象或 `null` | 词汇数据库可读时给出计数；未提供数据库或显式词库覆盖路径缺失时为 `null`。 |

每个 `subjects[]` 对象包含：

| 字段 | 类型 | 含义 |
|---|---|---|
| `subject_id` | 字符串 | 配置里的科目 ID。 |
| `tree_total` | `{count: integer, tree_status: string}` 或 `null` | 已读取的树节点总数及被计数节点的状态标签。`null` 表示该科目没有可用的已登记树，或显式树覆盖没有提供/找不到文件；已登记工作区树的存在性、类型或边界错误会令命令失败。 |
| `in_review_queue` | 整数 | 状态为 `queued` 或 `scheduled` 的复习项数。 |
| `due_today_count` | 整数 | 今天到期且状态为 `queued` 的复习项数。 |
| `due_today_minutes` | 整数 | 上述今天到期项的预计分钟数总和。 |
| `backlog_minutes` | 整数 | M27 选出的逾期 queued 与 scheduled 项预计分钟数总和。 |

`vocab` 非空时包含 `delivered` 与 `remaining` 两个非负整数。`delivered` 是 `state.plans`
下所有完成事件 `vocab.delivered_words` 按 `word_form` 去重后的数量；`remaining` 使用同一组
词形从词汇参考库可选池中扣除后计数。`state.plans` 未注册时没有已投放词集，按空集计数；
注册目录不存在时，DayPlanStore 的空存储行为同样给出空集。参考库本身仍按本规格既有规则
处理：显式缺失覆盖为 `vocab: null`，注册参考库缺失则 `Workspace.require` 失败。
只认存储自己写出的路径 `<YYYY-MM>/completion--<YYYY-MM-DD>.yaml`（且文件名日期等于事件 `day`）；
其他位置或名实不符的 `completion--*.yaml`、以及内容不合完成事件契约的文件，都是契约违规，不静默计入或跳过。
`remaining` 的单位是**词形行**（参考库可选关系的行数），不是 `tools/daily_words.py` 投放时使用的词族数；
两者不可互相换算（sol 第 86 轮 R2）。

## 只读与不推荐约束

此端口只读配置、队列、树和词库；不得创建目录或文件，不得写入或更新词库中的交付记录。公开 API、数据类和 JSON 不得出现暗示建议、推荐、最优安排或下一步处方的名称/字段。树节点计数必须附带真实 `tree_status`，不得将 `extracted` 状态描述为已审核或已掌握，也不得将节点数称作学习覆盖率。
