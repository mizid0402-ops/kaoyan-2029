# 第 155 轮 WP-M15-small 实现报告（opus）

- 工作树：`F:\workspace\kaoyan-ai-system\.claude\worktrees\agent-ab5c60aa85f14b9ae`
- 分支：`worktree-agent-ab5c60aa85f14b9ae`（基于 `b43eb1f`）
- 未提交（按 AGENTS.md，由决策者提交）。
- 全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。

## 1. 改动

| 文件 | 改动 |
|---|---|
| `ky/projection/__init__.py` | `PROJECTION_SCHEMA_VERSION` 3 → 4；`exam_questions` 末尾新增 `paper_source TEXT NOT NULL`；新增 `_index_paper_source`（取索引顶层 `paper_source`，缺省 `national`，按 `^[a-z][a-z0-9]*$` 校验）、`_exam_document_rows`（单个索引文件 → 行，从原 `_build_exam_rows` 拆出，避免三层以上嵌套）、`_claim_question_ids`（跨全部登记索引检测重复 `question_id`）；`_build_exam_rows` 增加 `root` 参数用于把来源文件写成相对工作区根的 POSIX 路径。 |
| `ky/projection/status.py` | `_SCHEMA_VERSION = str(PROJECTION_SCHEMA_VERSION)`（从构建器取，不再写第二个字面量）；两处 docstring 的 "schema 3" 改为"当前 schema"。错误消息 `projection schema version is ...; rebuild with schema ...` 原样保留。 |
| `contracts/projection.md` | 标题与 `projection_schema_version` 改为 4；表格加 `paper_source TEXT`；新增 "Exam questions" 一节：列取值与缺省、代码格式错误、`question_id` 冲突规则（消息与错误路径）、schema 4 与 3 只差这一列与冲突规则。 |
| `contracts/projection_status.md` | 版本要求改为"等于构建器的 `ky.projection.PROJECTION_SCHEMA_VERSION`（当前为 4），更早版本一律要求重建"。 |
| `contracts/learning_state_projection.md` | 标题 "(M15, schema version 3)" → "(M15, schema version 3 and later)"。任务书未点名；不改会与 projection.md 的 4 自相矛盾，只改标题一词。请决策者确认。 |
| `tests/contract/test_projection_port.py` | 新增 `ProjectionPaperSourceTest`（3 个测试，见 §4）与辅助函数；常量 `SCHEMA3_COMMIT = "8bd4f4d"`、`CUSTOM_SOURCE = "probe"`。 |
| `tests/contract/test_projection_status.py` | 旧版本拒绝测试从只测 `"2"` 改为子测试 `"2"`、`"3"`，并断言消息含 `rebuild`。 |
| `tests/contract/test_learning_state_projection.py`、`tests/test_projection_service.py` | 钉住 `"3"` 的断言改为 `str(PROJECTION_SCHEMA_VERSION)`。 |

没有碰 `ky/__main__.py`、`ky/storage/`、`tools/`。

说明：索引契约（`contracts/exam_index.md` §1）里 `paper_source` 只在**文件顶层**，条目的键集合不含它（未知键被拒）。
因此"每条目 / 每文件"的取值都是该条目所在文件的顶层值。

## 2. schema 4 与 schema 3 的差异

```
exam_questions (
    question_id TEXT PRIMARY KEY, exam_year INTEGER NOT NULL, number INTEGER NOT NULL,
    subject_id TEXT NOT NULL, question_type TEXT NOT NULL, marks INTEGER, answer TEXT,
    answer_confidence TEXT, knowledge_point_id TEXT, knowledge_point_status TEXT,
-   n_knowledge_points INTEGER NOT NULL, locator_page INTEGER, paper_sha256 TEXT)
+   n_knowledge_points INTEGER NOT NULL, locator_page INTEGER, paper_sha256 TEXT,
+   paper_source TEXT NOT NULL)
projection_meta.projection_schema_version: "3" -> "4"
```

新列放在末尾，前 13 列的位置、类型、约束不变；行排序键 `(exam_year, number, question_id)` 不变。
其他表、视图、`sqlite_master` 定义、其余 meta 键值逐一相同——由 §4 的对照测试在"克隆的真实工作区 + 一份自定义来源索引"上证明。

行为变化（仅在新条件下）：

- 索引顶层 `paper_source` 存在但不是合法代码（含显式 `null`）时，构建以 `ContractError`
  失败，路径 `reference.exam_indexes.<subject>.paper_source`。旧构建器会忽略该键。M5 校验器
  （`tools/verify_408_index.py`）本来就拒绝这类索引；仓库现有索引都不带该键，输出不受影响。

## 3. 冲突行为

`_build_exam_rows` 按 科目（排序）→ 登记顺序 → 条目顺序 遍历，`claimed` 记录每个 `question_id` 首次出现的文件。
再次出现时抛出：

```
ContractError("question_id 'cs408-2023-01' is produced by both copied/indexes/cs408-0.json and
               copied/indexes/cs408-duplicate.json",
              "reference.exam_indexes.cs408.entries[0].question_id")
```

- 文件以相对 `Workspace.root` 的 POSIX 路径给出（与 `projection_meta.inputs` 的键同一口径）；同一文件内重复时两处都是该文件。
- 错误路径指向后出现的那条条目。
- 检测在 `_write_projection_database` 之前完成，旧投影文件逐字节不变（测试断言）。
- 改动前的行为（变异 M3 实测）：`sqlite3.IntegrityError: UNIQUE constraint failed: exam_questions.question_id`
  ——临时库被删、旧文件未动，但 CLI 得到的是 traceback 而不是退出码 2 的契约错误。

## 4. 新增测试（`tests/contract/test_projection_port.py::ProjectionPaperSourceTest`）

1. `test_paper_source_column_records_default_and_custom_sources`：克隆工作区，把第一个登记科目的第一份索引复制为
   `paper_source: probe`，ID 按契约改写为 `<subject>-probe-<year>-<nn>` 并登记。期望值从登记的每份索引文件推导
   （缺键 → `national`），与投影 `question_id → paper_source` 全表相等。另断言 probe 行恰为该文件的条目、至少有一行
   `national`，列类型 `TEXT` 且 `notnull=1`。
2. `test_duplicate_question_id_names_both_files_and_keeps_projection`：先成功构建一次，再把同一索引复制到新路径登记，
   重建必须抛 `ContractError`；消息含两个文件路径与冲突 ID，错误路径为 `...entries[0].question_id`，旧投影字节不变。
3. `test_schema4_matches_pinned_schema3_builder_except_paper_source`：`git show 8bd4f4d:ky/projection/__init__.py`
   载入旧构建器，并断言其 `PROJECTION_SCHEMA_VERSION == 3`（第 12a 条：固定哈希，断言确是旧版）。在同一份输入
   （克隆的真实工作区 + probe 索引）上分别构建，比较：
   - `sqlite_master`（type, name, sql）除 `exam_questions` 外全部相同；
   - `exam_questions` 的 `PRAGMA table_info` = 旧列 + 末尾 `paper_source TEXT NOT NULL`，旧库无该列；
   - 除 `projection_meta` 外每张表、每个视图按旧列全列排序后的行完全相同（`exam_questions` 非空已断言）；
   - meta：`projection_schema_version` 旧 "3"、新 "4"，其余键值字典完全相同。

`8bd4f4d` 的 `ky/projection/__init__.py` 与本轮基线 `b43eb1f` 的该文件逐字节相同（`git show 8bd4f4d:… | diff - …` 无差异）。

测试不含数据量字面量；科目取自注册表第一个 `exam_indexes` 键，没有写死科目 ID。

## 5. 变异验证（`PYTHONDONTWRITEBYTECODE=1`，每次跑单个目标测试，改前后 SHA-256 比对还原）

| 变异 | 目标测试 | 结果 |
|---|---|---|
| M1 缺省来源改为 `"default"` | 列取值测试 | 被杀（failures=1） |
| M2 忽略索引的 `paper_source`，一律缺省 | 列取值测试 | 被杀（failures=1） |
| M3 删除 `_claim_question_ids` 调用 | 冲突测试 | 被杀（errors=1，`sqlite3.IntegrityError`） |
| M4 消息只写后一个文件 | 冲突测试 | 被杀（failures=1） |
| M5 `answer_confidence` 写成 `None`（改动其他列） | 基线对照 | 被杀（failures=1） |
| M6 多写一个 meta 键 `paper_sources` | 基线对照 | 被杀（failures=1） |
| M7 列改为可空 `paper_source TEXT` | 列取值测试 / 基线对照 | 均被杀（failures=1） |
| M8 `status.py` 保留字面量 `"3"` | `tests.contract.test_projection_status` | 被杀（failures=2, errors=1） |
| M9 `status.py` 同时接受 `"3"` | `tests.contract.test_projection_status` | 被杀（failures=1） |

还原核对：`ky/projection/__init__.py` 前后均为 `7101c026…2e5f`，`ky/projection/status.py` 前后均为 `ec3acddc…4590`。
未做的变异：把 `SCHEMA3_COMMIT` 改成 `HEAD`——提交前 HEAD 恰好就是 schema 3，这个变异当前杀不死；防护靠测试里的
`PROJECTION_SCHEMA_VERSION == 3` 断言，提交后若误改为 HEAD 会立即失败。

## 6. 测试输出

```
$ PYTHONDONTWRITEBYTECODE=1 py -3.12 -m unittest tests.contract.test_projection_port \
    tests.test_projection_service tests.contract.test_projection_status \
    tests.contract.test_learning_state_projection tests.contract.test_exam_index_port
..............................sss.sssss........
----------------------------------------------------------------------
Ran 45 tests in 32.266s

OK (skipped=8)
```

8 个跳过都在 `tests.contract.test_exam_index_port`（`require_raw=True`：工作树里没有 gitignore 的原始资料），
与本轮改动无关；其中 `test_custom_paper_source_is_required_in_question_ids` 与 `test_2027_national_paper_is_data_only_and_projected`
会构建投影，建议决策者在有原始资料的主工作区跑全量时留意这两条。

## 7. 怀疑受影响、未跑的模块

- `tests.test_projection`：用 `PROJECTION_SCHEMA_VERSION` 常量断言版本，并按列名查 `exam_questions`，预计不受影响。
- 任何按位置读 `exam_questions` 全列（`SELECT *`）的前端 / Datasette 查询：多了末尾一列。仓库内未发现此类代码。
- 已有的 schema 3 投影文件：`status` 会要求重建（按设计）。

## 8. 建议

- 本轮新增了来源代码正则 `^[a-z][a-z0-9]*$` 的第四份私有副本（`ky/exam/paper_shape._CODE`、`ky/exam/topic_weights._PAPER_SOURCE_RE`、
  `tools/verify_408_index.PAPER_SOURCE` 之外又加一份 `ky/projection._PAPER_SOURCE_RE`）。照周围写法做了，没有跨模块
  import 私有名；建议后续把来源代码格式与缺省值提升为一个公开接口（例如 M5 端口的公开常量），各模块改为引用。
