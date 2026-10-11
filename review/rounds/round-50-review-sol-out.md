# Round 50 Codex 独立评审

范围：`f00259c` 的 WP-B′4 tools 迁移；`e5c929b` 的 P4/V1 修复和 `_ProjectionRows` 重构。只在系统临时目录导出提交及构造探针；未改仓库实现、数据或生产投影。依 `AGENTS.md` 只跑相关单模块，未跑全量。

## 1. `f00259c`：FAIL

| 项目 | 判断 | 证据与处理 |
|---|---|---|
| T1：旧版来源不固定 | **必须改，MAJOR** | `tests/test_cs408_lecture_pipeline.py:75-89` 的 `_head_script` 执行 `git show HEAD:<工具>`。该测试是在提交前写成的；提交后 HEAD 已含迁移版，拿到的“旧版”其实还是新版，并且 `ROOT = Path(` 的替换条件不再匹配。当前 HEAD `ab86529` 下单跑 `py -3.12 -m unittest tests.test_cs408_lecture_pipeline -v`：第一项通过，`test_effective_outputs_match_head_templates` 在执行所谓旧 `extract_cs408_bundle.py` 时就因 `ModuleNotFoundError: ky` 失败，尚未比较输出。`f00259c` 自身的 HEAD 也已含同一新版脚本。应固定到 `f00259c^:<工具>`（或固定的前版提交），并在测试中验证取到的是旧版；不要依赖运行时 HEAD。 |
| T2：删一行用户可见模板的检出力 | **不改断言本身，前提是先修 T1** | 本机把 `_head_script` 在测试进程中改为读取 `f00259c^`，未动仓库：原始新版对旧版的 `test_effective_outputs_match_head_templates` **通过**。再把 `tools/build_408_deck_scaffold.py` 复制到系统临时目录，仅删掉含“### 练习指向”的模板行并让当前侧调用该临时副本：测试在 `tests/test_cs408_lecture_pipeline.py:326-329` **失败**，提示 `effective teaching-unit output changed: cs408.ds.chapter-01.section-01.md`。可见比较正文能检出此类删除；提交原样运行时的失败发生得更早，不能算这项检出。 |
| T3：用户可见文字实际漂移 | **必须改，MAJOR** | 在同一份系统临时工作区输入上运行 `f00259c^` 的 bundle/scaffold 与新版，旧 `coverage.md` 警示语写“2023–2026 这四套卷子”，新版写“2023–2026 年索引”；旧讲解单元写“2023–2026 四套卷”，新版写“2023–2026 年索引”（新版还多出“索引”和“的”之间的空格）。代码位置为 `tools/extract_cs408_bundle.py:184-190,233-244`、`tools/build_408_deck_scaffold.py:149-153`；旧文字可由 `git show f00259c^:<对应文件>` 核对。任务书只授权新增生效标记/视图信息，未授权改这两处原有提示。按 `AGENTS.md` 迁移规则恢复旧文案，或由决策者明确批准文字变更后把差异列入任务。 |
| T4：归一化范围 | **必须改，MAJOR** | 任务书 `review/rounds/round-49-wp-b4-tools-task.md:18-24` 明写的输出差异是新增 `is_effective/view_name`、补充视图元数据和非生效节点的可见标注；`AGENTS.md` 要求其余输出逐字节一致。测试 `:258-280` 把 CSV/JSON 解析成对象再比较，放过旧字段的列顺序、引号、空白和换行变化；`:303-314` 只遍历旧 manifest 键，任何额外的非授权新键也会通过；`:107-118,294-301` 把“在 … 映射”之间任意文字归一化，实际掩盖了 T3，且 `splitlines` 忽略行尾差异。应对输出字节做定向变换，只放过任务书明写的新增字段、视图元数据与非生效标注；比较文件集合及 manifest 允许新增键的**精确集合**。 |
| 其他迁移工具的输出对照 | **建议改；未核实完整输出等价** | 现有对照只实际构建 bundle 与 scaffold（`tests/test_cs408_lecture_pipeline.py:220-334`）；其余抽取工具和验证器仅有路径迁移/帮助或既有验证测试。尝试在系统临时目录导出 `f00259c` 并跑 `tests.test_exam_index`、`tools/verify_408_index.py`，因 Git 归档不含所需的原始试卷文件，分别失败于缺失资料；这不能归因于迁移实现。任务书 `:25` 允许无原始资料的一次性抽取工具只做 `--help` 检查；这些工具的逐文件输出等价在本轮记为未核实。 |

**结论：FAIL。** T1 使提交后的旧版对照不成立；T3 是已发生的未授权文案变化，T4 使对照把它抹掉。固定前版来源、恢复或获准修改原文、收窄归一化后，只重跑 `tests.test_cs408_lecture_pipeline` 并重复临时副本删行探针即可。

## 2. `e5c929b`：PASS

| 项目 | 判断 | 证据 |
|---|---|---|
| P4：契约测试去数据量字面量 | **不改，已修好** | `tests/contract/test_projection_port.py:115-164` 从登记生效树与补充树的 ID 集推导三项计数，并按 `view.name` 查询。确需钉住本版数字的断言移到专门的 `tests/test_data_manifest.py:1-44`，符合 `AGENTS.md` D5 的例外。替换/错误测试也改为从注册表选科目（同契约文件 `:205-275,317-400`）。 |
| V1：词汇关系形状 | **不改，已修好** | `ky/schedule/vocab_channel.py:55-90` 选 `v_top_words` 或 `words` 后检查必需的 `word_id`、`word_form`；`:131-135,193-199` 将 SQLite 查询错误收束为 `VocabChannelError`。本机临时库只有 `words(id)`：`remaining_pool` 和 `preview_batch(1)` 均报 `VocabChannelError: words: missing required columns word_form, word_id`。`tests/contract/test_vocabulary_port.py` 增加关系为表/视图的组合及缺列回归。规格 `contracts/vocabulary.md:40-41` 明确零词请求可在打开库前返回，消除了上轮零词歧义。 |
| `_ProjectionRows` 与写入顺序 | **不改；建议后续用关键字构造** | `ky/projection/__init__.py:62-69,488-510` 用具名字段传解析结果；`build_projection` 的读入与树、索引、权重解析在 `:599-606`，`:607-616` 组装结果后才调用写库；`mkdir` 和 SQLite 连接在 `:566-569`。因此输入校验仍先于临时库创建。当前六个同型列表在 `:607-614` 仍按位置构造，改为 `effective=...` 等关键字可让顺序更易审查，但没有观察到错位。 |

为排除后续 HEAD 的影响，本机用 `git archive e5c929b` 把相关文件导出到系统临时目录并分别运行：`tests.contract.test_projection_port` **13 项 OK**、`tests.contract.test_vocabulary_port` **6 项 OK**、`tests.test_data_manifest` **1 项 OK**。当前 HEAD `ab86529` 的工作区加载器已要求 schema 2，而根注册表仍写 schema 1；在当前检出上这三个模块会先报 `unsupported schema_version 1`。这是后续提交与当前注册表的集成状态，不能算作 `e5c929b` 的回归；相关疑点模块为 `ky.workspace` 与根注册表，本轮未扩大验证。

**结论：PASS。** P4、V1 已按本轮范围修复，`_ProjectionRows` 没有改变先解析后写库的顺序。

## 复审 dc1d04e

**结论：FAIL。** 仅复审 T1/T3/T4；T1、T3 已修，T4 的字节对照仍会放过未授权变化。当前 master 为 `462e1d7`，目标提交为 `dc1d04e`；本轮未改实现或运行全量测试。

| 原项 | 复审 | 证据 |
|---|---|---|
| T1 固定旧版来源 | **PASS / 不改** | `tests/test_cs408_lecture_pipeline.py:24,78-95` 固定 `PRE_MIGRATION_COMMIT = "762786f"`，并断言旧源码含迁移前绝对根路径；`git merge-base --is-ancestor 762786f dc1d04e` 返回 0。当前 master 单跑该模块 2/2 通过，旧工具确实可执行并完成新旧输出比较。 |
| T3 恢复旧文案 | **PASS / 不改** | `tools/extract_cs408_bundle.py:186-208,247-250,284-287`、`tools/build_408_deck_scaffold.py:41-64,161-166,203-206` 恢复“这四套卷子”“四套卷”等原句式，年份区间与套数改为从输入推导。对当前登记输入，定向测试的 `coverage.md` 直接逐字节比较通过；讲解单元在剥离允许的视图标注后逐字节比较通过。 |
| T4 归一化只放过授权差异 | **FAIL / 必须改，MAJOR** | `tests/test_cs408_lecture_pipeline.py:98-126` 的 `_drop_csv_columns`、`_drop_tree_json_columns` 虽最终比较 bytes，但先将**整份** CSV/JSON 解析并重写。临时探针把旧字段 `a=x` 的 CSV 单元改为额外加引号，`_drop_csv_columns` 仍与旧 bytes 相等；把 JSON 原字段周围空白改掉，`_drop_tree_json_columns` 仍与旧 bytes 相等。两项均非第 49 轮授权的新增列。另 `:148-171` 对所有以 `补充视图：` 开头的行一律删除；临时探针在预期视图行外再加一条 `补充视图：unauthorized text`，剥离后仍与旧 bytes 相等，且 `:255-257` 的预期行计数仍为 1。原 T4 所要求的“其余输出逐字节一致”尚未成立。**最小修法**：CSV/JSON 只精确删除新增字段的原始字节片段，保留旧字段字节、列顺序和行尾；视图行只删除已验证的精确一行及其约定空行，遇到其他同前缀行应失败。为三种未授权变化各加一个负向断言。 |

**删行探针复现：PASS。** 将 `tools/build_408_deck_scaffold.py` 复制到系统临时目录，只删除包含 `### 练习指向` 的那一行，并让对照测试调用临时副本：`tests=1, failures=1, errors=0`，失败指向 `deck/cs408.cn.chapter-01.section-01.md` 的原始字节差异。仓库工具未改。内置的同类探针见 `tests/test_cs408_lecture_pipeline.py:423-448`。

**定向验证**：`py -3.12 -m unittest tests.test_cs408_lecture_pipeline -v` → 2 tests OK。当前注册表中间态没有干扰本次测试。仅 T4 仍阻止本项复审通过。
