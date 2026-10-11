# 任务书：WP-H4b 复习队列按大纲版本迁移 + 参照完整性（新模块 M25，决议 D5，审查项 B7）

先读仓库根 `AGENTS.md`，再读：`docs/阶段2.5-接缝收口.md` §七 D5 / H4 行、`docs/模块地图.md`、
`contracts/syllabus_mapping.md`、`contracts/workspace.md`（`reference.syllabus_versions`）、`contracts/review_progress.md`、
`review/rounds/round-69-review-sol-out.md` 中"H4b 须补来源成员判定与版本链解析"与"`def56be` … 减少了版本登记集成覆盖"两条。

## 为什么做

H4a 让新大纲能登记为新版本并写版本映射，但复习队列里的 `knowledge_point_id` 仍指向旧版节点：
换了生效树以后，这些复习项会指向不存在的知识点（审查项 B7"队列→树无参照检查"）。本包把"迁移"和"检查"做成一块新拼图。

## 决策者已定的设计（照做；有更好的写法先在报告里提，不要自行改设计）

### 1. 新模块 M25 大纲迁移（`ky/review/syllabus_migration.py` + 规格 `contracts/syllabus_migration.md`）

纯函数部分（不做 I/O）：

- `resolve_mapping_chain(mappings, from_version, to_version) -> tuple[SyllabusMapping, ...]`：
  输入是某科**全部已登记**映射；沿 `from_version → … → to_version` 找出**唯一**一条连续链。
  无路径、有多条路径、同一对版本重复登记、成环 → `ContractError`（带说明）。`from == to` → 空链。
- `plan_queue_migration(items, chain, *, subject_id) -> MigrationPlan`：只处理 `subject_id` 这一科、且 `state != "retired"` 的复习项；
  其他科目与已退役项原样保留。逐步应用链上每一个映射（拆分后的项在下一步继续映射）。每一步对每个项：

| 映射结果 `targets(id)` | 处理 |
|---|---|
| `(id,)`（原样保留） | 不变 |
| 单个新 ID（改名 / 合并） | 改 `knowledge_point_id`，`revision + 1`，其余（到期日、阶梯、ease、历史）不变 |
| 多个 ID（拆分） | 原项 `state = "retired"`、`revision + 1`；每个目标新建一项：`review_id = f"{原 review_id}>{目标 ID}"`，复制到期日、schedule、`introduced_on`、`last_reviewed_on`、`last_quality`、`estimated_minutes` 等，`revision = 1`、`defer_count = 0` |
| `()`（删除） | `state = "retired"`、`revision + 1`（保留历史，不删除） |
| 源树里没有该 ID | 整个迁移拒绝（`ContractError`，列出全部悬空的 `review_id`）——这是 `targets()` 已有的报错，汇总后再抛 |

  合并去重：一步结束后，若同一科有多个**未退役**项指向同一 `knowledge_point_id`，保留到期日最早的一项（同日按 `review_id` 字典序最小），
  其余退役（`revision + 1`）。理由：合并后的知识点只需一条复习线，保留最早到期的最保守。
  新建项的 `review_id` 若与已有项冲突 → 拒绝。
- `MigrationPlan` 至少给出：`items`（迁移后的完整队列）、`unchanged` / `renamed` / `split` / `retired` / `merged` 各自的 `review_id` 列表，便于 CLI 打印与测试断言。
- `check_queue_references(items, tree_ids_by_subject) -> list[str]`：每个**未退役**项的 `knowledge_point_id` 必须在其科目的生效树里；
  科目没登记生效树 → 报"该科无生效树"。返回问题列表（空 = 通过）。

### 2. CLI（M14，`ky/__main__.py` 新子命令 `review-queue`）

```
py -3.12 -m ky review-queue check   [--workspace W] [--store DIR]
py -3.12 -m ky review-queue migrate --subject S --from 2026 [--to 2027] [--workspace W] [--store DIR] [--apply]
```

- `--store` 缺省取注册表 `state.review_queue`；`--to` 缺省取 `workspace.effective_version(S)`。
- 映射只从注册表取：`workspace.require_all("reference.syllabus_versions.<S>.mappings")` 逐个 `load_syllabus_mapping(..., subject_id=S)`。
- `migrate` 默认只打印计划（dry-run），`--apply` 才经 `ReviewShardStore.write` 原子写入；写入前对迁移后的队列跑 `check_queue_references`（对 `--to` 版本的树），不通过就不写。
- 旧版（schema 1）且含已复习项的队列：`write` 会拒绝（`ed456ec` 的保护），CLI 如实报错、退出 2，不绕过。
- 退出码沿用现有约定：0 成功、2 契约违规、3 用法错误。

### 3. 版本登记的集成演练（sol 第 69 轮建议）

`tests/contract/test_syllabus_migration_port.py` 里至少一项端到端：临时工作区登记 `"2026"`、`"2027"` 两个版本 + 一份映射（含改名、拆分、合并、删除、新增）+ 一个复习队列；
`migrate --apply` → 把 `knowledge_trees.<S>` 指到 2027 → `review-queue check` 通过 → `ky snapshot` 正常。

## 不做的

- 不改 `ky/knowledge/syllabus_mapping.py` 的对外行为（发现它不够用，写进报告"建议"，不要自己改）。
- 不给队列 manifest 加"当前大纲版本"字段（`--from` 由用户显式给出；是否持久化留作建议）。
- 不改知识树 / 索引 / 权重数据，不改投影、快照实现。
- 不迁移完成事件、日计划里的历史 `review_id`（它们是写一次的历史记录）。

## 测试（只写这些）

1. `tests/contract/test_syllabus_migration_port.py`（新）：链解析（单步、两步、无路径、两条路径、重复边、环）；
   迁移表格里每一种结果各一条，逐字段断言（新项 `review_id`、复制的到期日与 schedule、退役项 `revision`）；合并去重（到期日不同、同日按 `review_id`）；
   悬空 ID 整体拒绝且列出全部 `review_id`；其他科目与已退役项原样；`check_queue_references` 正反例；上面第 3 节的端到端演练；
   CLI：dry-run 不写盘（队列目录逐字节不变）、`--apply` 写盘、检查失败不写盘。
2. 不写数据量字面量；测试里的树在临时目录造（照 `tests/contract/test_syllabus_mapping_port.py`）。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_syllabus_migration_port tests.contract.test_syllabus_mapping_port tests.test_cli tests.test_review_queue_advance
```

另：`docs/模块地图.md` 登记 M25 一行（规格 / 实现 / 读哪些注册表键 / 可替换性 / 验收命令）；§4 缺口表里 H4b 那行删除或改写为剩余缺口。

## 报告

`review/rounds/round-72-wp-h4b-luna.md`：改了哪些文件、每条设计的落点、验收输出、建议。
写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。含中文的文件写完查 `???`。
