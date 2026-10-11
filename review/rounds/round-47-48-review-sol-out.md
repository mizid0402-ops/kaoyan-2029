# Round 47/48 独立评审

范围：`6fd9ff4`（WP-B′2 修复）和 `16d8c55`（WP-B′3 词汇通道）。只读检查实现；探针只在系统临时目录建数据，未改仓库代码或参考数据。定向运行：

- `py -3.12 -m unittest tests.contract.test_projection_port -q`：13 项，OK。
- `py -3.12 -m unittest tests.contract.test_vocabulary_port -q`：4 项，OK。
- `py -3.12 -m unittest tests.test_knowledge_contract -q`：4 项，OK。

全量未跑（按 `AGENTS.md:23-29`，由决策者提交前统一跑）。

## 1. `6fd9ff4` 投影修复

| 项目 | 判断 | 证据与处理 |
|---|---|---|
| 上轮 M1：哈希与解析两次读取 | **不改，已修好** | `ky/projection/__init__.py:71-76,99-133` 将每个唯一登记路径读成 `_RegisteredInput(content, sha256)`；`:136-159,192-196` 直接解析同一份字节。`tests/contract/test_projection_port.py:256-301` 在首次读树后改文件，断言投影标题与元数据仍对应旧字节；本机该模块通过。 |
| 上轮 M2：畸形索引逃逸 `ContractError` | **不改，已修好** | `ky/projection/__init__.py:338-355` 先检查 `locator` 映射和字段类型，`:358-410` 逐条建行；`tests/contract/test_projection_port.py:303-349` 覆盖 `locator=[1]`、坏年份/分数及 CLI exit 2；本机通过。 |
| 上轮 M3：补充树混入外科目 ID | **不改，已修好** | `ky/projection/__init__.py:241-248` 对每个补充节点核对 ID 科目与视图科目，错误落在 `.items[index].knowledge_point_id`；`tests/contract/test_projection_port.py:351-379` 用跨科节点回归，本机通过。 |
| 新文本入口与路径入口 | **建议改诊断文案；解析行为一致** | `ky/knowledge/knowledge_point.py:374-418` 让路径加载器读字节后调用 `load_knowledge_points_from_text`；`ky/models.py:278-301` 让文件 YAML 加载器调用 `load_yaml_text`，两路都使用同一个严格 loader。本机临时文件：`items: [123]` 时两种知识树入口均报 `KnowledgePointError.path=<文件>.items[0]`；嵌套 `title` 重复时均拒绝，`.path=<文件>`；`load_yaml_text` 和 `_read_yaml_file` 的重复键 `.path` 也一致。重复键目前只有文件级路径，没有 `.items[0].title`；`KnowledgePointError(str(exc), source)` 还把文件路径重复拼进文案（`knowledge_point.py:385-387`）。若契约需要精确重复字段路径，应在共享 YAML 节点解析层实现；当前两入口没有互相漂移。 |
| D7 拆分与写入顺序 | **不改** | `build_projection` 在 `ky/projection/__init__.py:620-627` 完成登记文件读取、树/附表、索引和权重解析；`:628-639` 才调用写库步骤；真正 `mkdir`、`.building`、SQLite 连接位于 `:569-572`。输入失败不先创建临时库的顺序保留；表、元数据、视图与 `os.replace` 在 `:450-610` 分步执行。M1/M2/M3 的定向回归及契约模块通过，未发现拆分引入的运行时回归。 |
| P4：契约测试仍钉死数据规模 | **必须改，MAJOR（现行 D5 规则）** | `AGENTS.md:34-38` 明令契约测试期望值从登记文件推导，只有专门数据清单测试可固定某版本数字。`tests/contract/test_projection_port.py:121-134` 仍断言有效 403、补充 410、有效补充 403；此提交还改了同一测试方法的其他断言。若合法地给登记的生效/补充树增加一个共同节点，构建仍符合规格，这三个断言会错误失败。该方法已在 `:135-145` 读出有效与补充 ID 集，可将期望改为集合长度；若要固定 D1 历史版本数字，移入专门的数据清单测试。新回归中固定 `cs408`/`math1`（`:260,307,355,359`）也应按 D6 尽量从注册表选择目标与另一科目；至少不要把它复制到可扩展的通用测试中。 |

**提交结论：FAIL（规则门禁）。** M1/M2/M3 的运行时修复通过；P4 是当前仓库明确禁止的数据量字面量，且对允许的数据增长有确定的错误失败。只需修该测试并重跑 `tests.contract.test_projection_port`，不必重新审整份投影或跑全量。此前提出的读树 `writer="deterministic_script"` 混用问题仍属于跨模块接口决议，本次提交未处理，也未作为新增阻断项。

## 2. `16d8c55` 词汇通道

| 项目 | 判断 | 证据与处理 |
|---|---|---|
| 路径端口、只读、关系选择 | **不改** | `contracts/vocabulary.md:3-12,26-36` 要求显式路径、`mode=ro`、优先 `v_top_words` 否则 `words`；`ky/schedule/vocab_channel.py:43-59,76,101,129-137` 符合。`tests/contract/test_vocabulary_port.py:36-50,93-105,107-114` 覆盖路径替换、最小 `words` 视图及登记文件缺失；模块测试通过。 |
| 遗留 `_legacy_delivered_word_ids` 的范围 | **不改** | `ky/schedule/vocab_channel.py:62-73` 只读 `delivery_log.word_id`；调用点 `:94-96` 与 `:165-169` 仅用于从池计数、预览中排除已投放词，不写表、不决定批量。`import_delivery_baseline` 的独立只读迁移入口在 `:101-126` 仍读旧日志，正是规格 `contracts/vocabulary.md:38-42` 明列的例外。 |
| V1：不支持的关系形状未按规格报错 | **必须改，MAJOR** | `contracts/vocabulary.md:10-18,34-36` 规定所选关系必须有 `word_id`、`word_form`，不支持的形状抛 `VocabChannelError`。`_pick_view` (`vocab_channel.py:51-59`) 只看名称，不验列；`remaining_pool` 的查询 `:95`、`preview_batch` 的查询 `:180-185` 让 SQLite 原始异常外漏。本机临时库只有 `CREATE TABLE words (id INTEGER)`：两函数分别抛 `OperationalError: no such column: word_id` / `word_form`，而非 `VocabChannelError`。选关系时检查必需列，并把数据库结构/查询错误收束为带关系名的 `VocabChannelError`；在契约测试加入缺列库以及 `v_top_words`/`words` 表或视图的选择用例。 |
| 零词预览与缺失库 | **建议改规格或实现** | `vocab_channel.py:152-155` 在 `_connect` 前返回零词批次；本机对不存在的显式 `db` 调用 `preview_batch(0, db=...)` 仍成功。`contracts/vocabulary.md:34-36` 的“missing databases ... raise `VocabChannelError`”没有写零词例外。若保留历史零词短路，就在规格说明该例外；若缺失路径必须一律报错，先验证路径再短路。此项单独不阻断。 |

**提交结论：FAIL。** V1 是本包规格明确覆盖的错误边界，现有 4 项契约测试未包含缺必需列的可复现输入。修后只重跑 `tests.contract.test_vocabulary_port`。

## 3. D7 可读性：最该改的三处

| 优先 | 判断 | 建议 |
|---|---|---|
| 1 | **建议改** | 投影 `_insert_projection_rows`、`_write_meta_and_views`、`_write_projection_database` 在 `ky/projection/__init__.py:478-510,558-594` 反复传 6 组同型列表，调用时位置一错不易看出。将解析结果收成有字段名的 `_ProjectionRows`，三个写入步骤只收一个具名对象；保持目前“先解析、后写库”的边界。 |
| 2 | **建议改** | 词汇 `remaining_pool` 与 `preview_batch` 在 `ky/schedule/vocab_channel.py:85-96,157-180` 重复选关系、查列与组筛选条件，必需列检查正好缺在共同边界。抽出返回关系名、列集和过滤条件的明确辅助步骤；`import_delivery_baseline` 的连接也可复用 `_connect`，避免两套只读连接写法（`:43-48,111-114`）。 |
| 3 | **建议改** | 新知识树文本入口在 `ky/knowledge/knowledge_point.py:383-387` 把已带 `source` 的 `ContractError` 整串再包成同一路径的 `KnowledgePointError`，本机重复键报错文案出现两次文件名。保留底层结构化路径、只转换错误类别；在接口注释中说明重复 YAML 键目前是文件级定位，避免使用者误以为拿到了字段路径。 |
