# Round 64 Codex 独立评审：`2ebce6c` WP-H3

评审环境：从 `git archive 2ebce6c`、`git archive 924fb0e` 分别解到系统临时目录；仅把本机已有、归档因 gitignore 缺失的 408 答题页及三份试卷复制到两份临时归档。未改仓库实现，未跑全量测试。以下“通过”只指列出的局部输入，不代表穷举。

## 1. 旧版拒绝边界有没有变弱

| 判断 | 证据与可复现输入 |
|---|---|
| 不改：在已核对的 408 边界上未发现旧拒新收 | 对两份归档的 `data/exam_questions/408_index_2024.json` / `408_index_2026.json` 分别变异后调用 `verify`：2024 Q1 `answer="E"`，旧版报 A–D 和重读不符，新版报同类两错；2024 Q41 分值 `13→14` 且总分 `150→151`，两版均报卷面分值和总分不符；2024 只把总分改为 151，两版均拒；2026 Q41 `marks=null→1`，两版均拒；2026 `marks_total=null→150`，两版均拒。新规则落在 `tools/verify_408_index.py:223-260,264-307,574-579`，原始登记在 `data/paper_shapes/cs408.yaml:4-119`。这是定向差分，不声称对所有可能 JSON 穷举。 |
| 不改：独立答案重读的题号集合比旧版更严格 | 旧版只比较读出的答案数量与 40，随后逐项比答案；新版用 `set(answers) == expected_answers`，再逐题比对，见 `tools/verify_408_index.py:285-307`。现有 408 各年形状仍将 1–40 登为 A–D 并指定 `csgraduates_quiz_dom`。 |
| 建议改：旧边界缺少专门的回归断言 | `tests/contract/test_exam_index_port.py:150-251` 没有 A–D、独立重读题号集合、已核实分值和总分的负例。我在归档进程中临时把 `_verify_entry_section` 返回的 A–D 问题过滤掉，运行该模块 7 项仍全绿。至少补一条 A–D 负例和一条答题页多/缺题号负例；不必写入固定数据量。 |

## 2. D5 / D6：只加数据与身份

| 判断 | 证据与可复现输入 |
|---|---|
| 不改：D5 的“新年份入投影”通路成立 | 归档内 `py -3.12 -m unittest tests.contract.test_exam_index_port`：7 项通过，其中 `test_2027_national_paper_is_data_only_and_projected` 只添加 2027 卷面段、索引、注册表路径，然后断言校验空问题及投影含该年全部题号，见 `tests/contract/test_exam_index_port.py:150-180`。该测试复用 2026 来源与答案，证明的是路径/数据模型通路，不证明真实 2027 来源可信；这是任务书 `round-61-wp-h3-task.md:92-94` 明定的合成演练。 |
| 不改：正确填写出题单位时，统考与学校卷可并存 | 在归档临时工作区依测试辅助函数加入 2026 `xidian` 卷，注册索引后 `verify(...) == []`；构建投影并查询 `exam_questions`，得到学校 ID 47 条、统考 ID 47 条。身份分别由 `cs408-xidian-2026-NN` 与 `cs408-2026-NN` 表示；校验器要求精确 ID，见 `tools/verify_408_index.py:338-340,400-411`，投影以 `question_id` 为主键，见 `ky/projection/__init__.py:476-483`。 |
| 建议改：缺省 `national` 不能识别误标的学校卷 | 同一临时工作区把 `xidian` 索引的顶层 `paper_source` 删除、各题 ID 改为 `cs408-2026-NN`；单文件 `verify(...) == []`，因为缺省就是 `national` 且两卷形状相同。再把它与原统考卷同时登记建投影，报 `IntegrityError: UNIQUE constraint failed: exam_questions.question_id`，没有静默覆盖。此处是已选“缺省 national”设计的边界，单凭索引内容无法判定来源实际为学校。建议在投影解析阶段把重复 ID 变成带两份注册路径的 `ContractError`，并在数据登记流程显式核对出题单位；若要从源头阻止误标，需另有可信的注册表来源字段。D6 契约测试目前只验证学校卷的单文件校验，没有学校卷入投影或撞车场景，见 `tests/contract/test_exam_index_port.py:182-199`。 |

## 3. 规格、实现与新增漏洞

| 判断 | 证据与可复现输入 |
|---|---|
| **必须改 M1：必需的 `calibration` / `kind` 可缺失，官方答案门槛可绕过** | `contracts/exam_index.md:15-35,61-83` 将二者列为顶层固定字段，且 `calibration` 只许两种值。校验器 `check_enum` 在值为 `None` 时直接返回，见 `tools/verify_408_index.py:155-160,330-345`；官方声明门槛只在 `calibration == "awaiting_official_book"` 时执行，见 `:644-655`。复现：从现有 2026 索引删除 `calibration`，把 `entries[0].answer_confidence` 改为 `official`，`verify(...)` 返回 `[]`；单独删除 `kind` 也返回 `[]`。这是旧校验器已有缺口，**不是本提交造成的变弱**，但新规格现已声称这两项必需，且省略校准状态可以实际绕过证据门槛。应明确检查固定顶层字段存在且值合法，并补精确负例。 |
| **必须改 M2：规格允许的小数分值会被浮点相等误拒** | `contracts/paper_shape.md:34-47` 允许任意有限正浮点数；`ky/exam/paper_shape.py:95-101` 也接收。构造 2027 卷面一段 1–3 题、`marks_each: 0.1`，索引每题 `marks: 0.1`、`marks_total: 0.3`：`tools/verify_408_index.py:250-260` 算出 `0.30000000000000004`，报 `marks_total 0.3 != registered shape total 0.30000000000000004`；通用总分计算 `:567-579` 同样用浮点精确相等。归档内直接调用 `_verify_registered_total` 已复现。用十进制值求和/比较，或在规格里规定可检验的舍入规则；只测 `0.5`（二进制可精确表示）不足以守护此条。 |
| 建议改：卷面 YAML 错误不总能按规格给字段路径 | `contracts/paper_shape.md:18-19` 要求未知/重复键以字段路径拒绝。`ky/exam/paper_shape.py:76-79` 对未知键直接排序；在一个 paper 同时加入整数键 `1` 和字符串键 `bad`，`load_paper_shapes` 抛原生 `TypeError: '<' not supported between instances of 'int' and 'str'`。重复 `papers[0].exam_year` 时虽抛 `ContractError`，其 `path` 是文件名，消息只给 `exam_year` 和行号，没有 `papers[0].exam_year`。均拒绝了坏数据，故不升为阻断；建议稳定转换为带字段路径的契约错误。 |
| 建议改：题号上限的规格与数据增长边界要讲清 | `contracts/exam_index.md:19-22` 定义两位题号，`tools/verify_408_index.py:47,405-411` 的正则限制两位，但 `ky/exam/paper_shape.py:196-213` 对 `question_count` 没有 99 上限。若将来卷面登记 100 题，格式化得到 `...-100`，又被 ID 正则拒绝。当前登记最大 52，非本轮 D5 的现实失败；建议明确“最多 99 题”或扩展 ID 规则并做迁移约束。 |

## 4. `build_408_index_v2.py` 逐字节对照

| 判断 | 证据与可复现输入 |
|---|---|
| 不改：报告的固定基线对照可信 | 两份归档各自用自己的 `tools/build_408_index_v2.py`，同一批本机原始答题页/试卷和缓存、相同命令 `py -3.12 tools/build_408_index_v2.py --year Y --out %TEMP%/.../Y.json`，对 2023–2026 分别运行；用 `[System.Linq.Enumerable]::SequenceEqual([byte[]]旧,[byte[]]新)` 比较原始字节，四项全为 `True`，长度依次 44703、44747、44705、45011，SHA-256 与 `review/rounds/round-63-wp-h3-fixes-luna.md:27-34` 一致。旧代码来自固定 `924fb0e`，无 `HEAD` 漂移。另以 Python 比较 2023–2026 原 `PaperShape.basis` 与新 YAML 读出的 `basis`，四项均相等。这个对照只覆盖已有四年；`tools/build_408_index_v2.py:280-283` 仍固定四个年份，但任务书将它界定为 408 专用采集脚本，新年份可以按索引端口另行产出。 |

## 5. 契约测试撤销检查探针与结论

| 判断 | 证据与可复现输入 |
|---|---|
| 不改：已有负例大多指向具体错误 | `tests/contract/test_exam_index_port.py:137-147` 的 `_assert_problem` 断言目标错误子串，而非“有任意错误”；去掉卷面、题型、`unverified`、未知读取器、学校 ID 检查时，相应负例有机会变红。卷面加载器 4 项通过；索引端口 7 项通过。 |
| 建议改：关键旧检查和 M1/M2 没有守护 | 如上 A–D 撤销探针，7 项测试仍全绿。测试还没有“缺 `calibration` 且声称 `official`”“缺 `kind`”“0.1×3 总分 0.3”“答案读取器题号集合缺/多一号”的负例。`test_2027...` 证明投影新年份；`test_custom...` 没断言学校卷进投影，也没检验双卷并存。建议按这些实际漏洞补对应单项，不扩大全量。 |
| 不改：归档环境造成的失败不算提交缺陷 | 纯 `git archive` 下，索引端口 7 项初次均在复制被忽略的 `data/raw_materials/cs408/quiz_pages/cs408_quiz_2026.html` 时失败；把本机原文件复制进临时归档后 7 项通过。`tests.contract.test_workspace` 在归档中 13 项有 1 项因被忽略的 `products.cs408_lecture_workspace` 目录缺失而失败、1 项跳过；其余通过。未因此认定代码失败。 |

**总体：FAIL。** 旧 408 拒绝边界及 D5/D6 的正确数据通路经定向验证成立，四年构建器输出逐字节相同；M1 的官方声明门槛绕过与 M2 的合法小数误拒应在接收前修复。复审只需对应的两个缺陷及其精确回归测试。
