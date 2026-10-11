# Claude 独立评审：408 知识树方向共识

> 评审者：Claude Sonnet 5 ｜ 日期：2026-09-15 ｜ 未修改任何文件，全部命令只读执行并已实测复核。

---

## 1. 对底本的复核结果

### 1.1 完全复现的 claim（实测）

| # | claim | 复核方式 | 结果 |
|---|---|---|---|
| 1 | `knowledge_tree.yaml` 因 `.chapter` 祖先规则失败 | `py -3.12 tools/verify_tree.py data/structured_materials/cs408/knowledge_tree.yaml` | ✅ 复现，`contract OK (403 nodes)`，随后 FAILURES |
| 2 | `knowledge_tree_multisource.yaml` 同样失败于同一规则 | 同上命令跑主表 | ✅ 复现，`contract OK (410 nodes)`，FAILURES 段起始行完全一致 |
| 3 | `knowledge_tree_agreement.yaml` 因 `baseline_relation_counts` 被契约拒 | 同上命令跑 sidecar | ✅ 复现：`CONTRACT FAILURE: ...baseline_relation_counts: unknown field` |
| 4 | `knowledge_tree_weighted.yaml` 同样因该字段被拒 | 同上命令跑 weighted | ✅ 复现，同样的报错 |
| 5 | 项目里没有生产代码消费这些树 | `grep -rn "knowledge_tree_weighted\|multisource\|agreement" ky/` + `grep -rln "source_support\|evidence_tag" ky/` | ✅ 复现，两条 grep 均为空 |
| 6 | 三处 `weight` 指三个不同概念 | 读 `ky/schedule/review_clip.py`（学科级时间预算）、`tools/apply_knowledge_weights.py`（题目→知识点置信度）、`tools/tree_source_support.py` 顶部文档字符串（自己就写明了这两处的区别） | ✅ 复现，且 round-29 的作者本人已在 `tree_source_support.py` 的 docstring 里显式写出这条区分，不是我推断出来的 |
| 7 | `_POINT_KEYS` 白名单被 `transition_knowledge_point`/`eligible_for_frequency`/`apply_deterministic_frequency` 共用 | 读 `ky/knowledge/knowledge_point.py` 60/251/289/315/332 行 | ✅ 复现，四个函数确实共用同一个 `_unknown(node, _POINT_KEYS, path)` 校验 |
| 8 | round-29 把 `evidence_tag→source_support` 抽成独立函数并重现全部 410 个值 | **底本说主控尚未独立复验——我独立复验了**：运行 `pytest tests/test_tree_source_support.py`（7 passed，含 `test_reproduces_all_410_weight_values`）和 `pytest tests/test_round29_tree_split.py`（12 passed，含 `test_all_410_values_identical_to_the_historical_weight`）；另外 `round29_build_tree_split.py` 的 `build()` 函数本身在不匹配时会 `raise AssertionError`，文件已生成在磁盘上这件事本身就是构建时断言通过的证据 | ✅ **实测确认为真**，比底本更进一步——这不只是"重现"，`tools/tree_source_support.py` 是一张**穷举校验表**（`KNOWN_COMBINATIONS`），遇到未见过的 `(evidence_tag, source_count, match_kind)` 组合会拒绝而不是外推，且有第二个独立文件 `round29_validate_agreement.py` 对磁盘上的真实文件重新推导校验一遍（不导入 builder 的内部状态） |
| 9 | `verify_tree.py` mtime 早于 round-24/round-29 | `ls -la --time-style=full-iso` | ✅ 复现：`verify_tree.py` = 09-13 10:33，`knowledge_tree.yaml`(基线) = 09-13 01:20（更早），`knowledge_tree_weighted.yaml` = 09-14 13:34，`multisource/agreement` = 09-15 08:20。本仓库无 `.git`，无法看到更早的历史，但现存文件的 mtime 顺序支持"这条规则不是这两轮引入的" |

### 1.2 底本**低估**的地方（这是本轮最重要的发现）

底本第 2 节只展示了 `verify_tree.py` 输出的前 20 行 FAILURES（工具本身用 `failures[:20]` 截断打印），**这让读者以为失败只有一种类型**（section 缺 `.chapter` 祖先）。我绕过截断，直接调用 `ky.knowledge.knowledge_point.load_knowledge_points()` 复算了全部检查，并且用 `tests/test_round29_tree_split.py` 里已经写好的 `structural_failure_categories()` 交叉验证：

```
baseline: {'section_ancestor': 116, 'chapter_missing_suffix': 48, 'subject_rank': 56}
main(multisource): {'section_ancestor': 116, 'chapter_missing_suffix': 48, 'subject_rank': 56}
```

**共 220 条失败，三种独立的类型，不是一种。** 而且——**这不是我第一个发现的**：`review/rounds/round-29-tree-split-claude.md` 第 31/39/212 行已经把这三类失败的确切计数写出来了。底本作者显然读过 round-29 的报告（4.5 节引用了它），但在共同底本里又把它压缩回只展示第一类，**这会误导评审者把方向 A 想得比实际简单**。

- **`section_ancestor`（116 条）与 `chapter_missing_suffix`（48 条）都源于同一个根因**：`verify_tree.py` 假设 chapter 节点 id 以 `.chapter` 结尾，且每个 chapter 必须有 `<base>.content`/`<base>.requirements` 两个同级节点。cs408 的 chapter id 是 `cs408.ds.chapter-01`（编号嵌入 id 本身），既不以 `.chapter` 结尾，也没有 content/requirements 这两个占位节点——**因为 cs408 真实地有 2~6 个具名 section（如"栈和队列""排序"），根本不是 math1 那种"每章固定两块"的简化建模**。
- **`subject_rank`（56 条）是一个完全不同的问题，方向 A 的"改 id 还是改验证器"框架根本套不上它**。我读了 `data/structured_materials/cs408/generate_tree_round6.py`（126-143 行）和实际数据：cs408 树里每个学科除了 1 个真正的顶层 `subject` 节点（如 `cs408.ds.subject`），还有 4 个"考查目标"相关节点被打上了 **`scope: subject`**（`cs408.ds.exam-objectives` 及其 3 个 `item-01/02/03`）——4 学科 × 4 节点 = 16。这些节点和真正的 subject 节点共享同一个 id 前缀（如 `cs408.ds.`），于是触发 `verify_tree.py` 的"同前缀下不能有第二个 subject 级节点"规则。**关键是：这不是 cs408 数据的随意错误，而是 `ky/knowledge/knowledge_point.py` 自己的设计意图**——该文件 30-37 行的注释明确写着："408 大纲的 12 条考查目标全部是 subject 级……scope 使这个区别可机器检查……必须把 objective-scope 的目标报告为一个 standing tracker"。也就是说：**"考查目标"节点被有意设计成 scope=subject，但 `verify_tree.py` 的"同前缀下唯一 subject"规则从未考虑过这种合法的"同级多个 subject 节点"场景**。这是契约设计意图与验证器实现之间的一个**真实矛盾**，不是数据缺陷，也不是简单的命名习惯问题。

**结论：底本对"验证失败"的描述在事实上没有错（我复现了它引用的那一行），但呈现方式（只截取一种失败类型）会让方向 A/D 的决策者低估修复范围。** 这是我认为底本最值得修正的地方。

### 1.3 支持性验证（进一步确认规则不是残留物）

- `tests/test_tree_integrity.py::test_math1_shape_is_locked`（111-125 行）**明确把 `.chapter`/`.content`/`.requirements` 的三件套写死为断言**，并且我跑了 `py -3.12 tools/verify_tree.py data/structured_materials/math1/knowledge_tree.yaml`，**math1 树全过（`ALL CHECKS PASSED`）**。这证明该规则**当前正被一个真实、活跃、有专门锁定测试的文件在使用**，绝非早期树形的死残留——它保护的是 math1，只是从未被扩展以覆盖 cs408 的第二种真实树形。
- `eng1/knowledge_tree.yaml` 走的是 `verify_tree.py` 本来就有的第三条分支（`has_chapters=False` 的 "structure tree"），也全过。**所以 `verify_tree.py` 已经证明自己能够按 shape 分流校验规则——这正是我认为该给 cs408 加的第三条分支的先例，不是要新发明一种机制。**

### 1.4 其它复核

- opus 树（`knowledge_tree_opus.yaml`）：`grep -rln "knowledge_tree_opus" --include="*.py" .` 结果为空——**全仓库零引用**，比 4.4 条的范围还彻底。
- exam_questions 覆盖：410 = 403(baseline) + 7(新增) 是超集关系（`multisource_ids ⊇ baseline_ids`），我核对了 `data/exam_questions/*.json` 里全部 117 个 cs408 `knowledge_point_id`，在 baseline 和 multisource 中**同时 100% 命中**——退役 baseline、以 multisource 为准不会破坏任何现有题目映射。
- sidecar 契约失败是否是一个"真问题"：round29_build_tree_split.py 自己的 docstring（24 行）称 agreement 表是"non-contract annotation layer"，**从设计意图上从未打算过 verify_tree.py。仓库里没有任何测试/工具对 cs408 目录下的 yaml 做"批量跑 verify_tree.py"式的盲扫**（我 grep 过，没有这种 glob 调用）。所以这个"契约报错"只在**人工手动**把 verify_tree.py 指向 sidecar 时才会出现——这更像是"用错工具"，不是 sidecar 本身有缺陷。

---

## 2. 方向 A–E 逐项表态

### 方向 A：树形命名统一 —— **不改 cs408 的 id，改验证器加一条分支**

- **不改 id** 的理由：(1) 即使改了 chapter id 加上 `.chapter` 后缀，`chapter_missing_suffix`（48 条）依然会失败，因为 cs408 没有、也不该有 `.content`/`.requirements` 占位节点——它们的真实内容已经用 section/item 表达了，硬造这两个节点是**纯粹的数据捏造**，违反项目纪律。(2) `subject_rank`（56 条）跟 chapter id 命名完全无关，改 id 也解决不了它。(3) 432 条题目映射的收益为零、成本不为零。**结论：单纯改 id 无法让 cs408 树通过，反而制造了新的伪造数据风险，此路不通。**
- **改验证器**：给 `verify_tree.py` 加第三种 catalog 子形状（暂命名 "outline catalog"：chapter id 不以 `.chapter` 结尾、无 content/requirements 要求、section 数量可变）。判定依据：`has_chapters=True` 且没有任何 chapter 节点 id 以 `.chapter` 结尾 → 用"section 前缀必须等于某个已存在 chapter 节点的 id"（不再拼接 `.chapter`）作为祖先规则，且跳过 content/requirements 检查。这不是"放宽验证器让文件过"——**math1 的强约束原封不动保留**（新分支只在检测到"非 math1 命名法"时才启用，math1 继续用旧分支、继续要求 content/requirements 二件套），是**新增一种真实存在的合法形状**，跟 eng1 已有的第三分支同一个模式。

### 方向 B：sidecar 的归属与校验方式 —— **维持现状：sidecar 只由 `round29_validate_agreement.py` 校验，永不喂给 `verify_tree.py`**

- `baseline_relation_counts` 不需要删除——它是个纯摘要缓存字段，**没有代码读取它**（我 grep 过），但也没有代码因为它的存在而出错，唯一"报错"的场景是有人手动把 `verify_tree.py` 指向 sidecar。**真正该做的不是改文件字段，而是明确"sidecar 家族"这个概念**：round29_validate_agreement.py 已经是一个完整、独立、有 5 类检查的校验器（含"从 main 表重新推导 source_support 并比对"），**不需要也不应该被塞进知识点契约**——契约是给"一个知识点"用的，sidecar 是给"一批知识点的元评估"用的，二者语义不同，硬塞会重演 round-24 weighted 树把六个额外字段塞进主文档、在文档级直接炸掉契约的老问题。
- 建议：`round29_validate_agreement.py` 增加一条内部一致性检查——`baseline_relation_counts` 应等于对 `items` 现场 `Counter()` 的结果（目前完全没有校验这个字段，它是"写入时算一次就再也不检查"的冷数据，有静默漂移的风险，虽然目前没人读它，但既然留着就该有一致性保证）。这是**低成本增量**，不是"新需求"——顺手补在同一个校验器里即可。

### 方向 C：基线树的去留 —— **保留 multisource + agreement 两份为活跃文件，其余三份归档**

- `knowledge_tree.yaml`（基线）→ **归档**：已被 multisource 完全超集覆盖（410 ⊇ 403），题目映射 100% 兼容，无需再单独维护。
- `knowledge_tree_weighted.yaml`（round-24）→ **归档**：round-29 已经把它拆成 multisource+agreement 并逐值验证零漂移，继续留在 `data/` 目录下只会让人误用（它本身连契约都过不了）。
- `knowledge_tree_opus.yaml` → **归档**：零代码引用，仅作历史比对用途，比对工作如果还要做，从归档目录读同样可行。
- `data/structured_materials/cs408/audit_round6.py`、`generate_tree_round6.py` → **归档**（这两个脚本躺在数据目录里本身就不合常规，且是 round-6 的一次性工具，round-22 之后的所有工作都没有依赖它们——但我没有跑穷尽的引用检查，标记为低置信度，建议归档前用一次 grep 复核）。
- **"归档"= 移到 `archive/` 并保留**，不删除。理由：这些文件目前互相之间有精确的数值可比关系（如 weighted 的 weight 值是 source_support 公式的黄金参照），删除后如果将来 `derive_source_support` 需要扩展新组合，就没有历史真值可比对了。

### 方向 D：验证器与契约的边界

- **`.chapter` 后缀规则的意图**：**不是残留，是 math1 的真实、活跃约束**（`test_math1_shape_is_locked` 锁定，math1 树当前全过）。它挡的是"chapter 节点必须有统一的、可预测的子节点二件套"这个 math1 特有的建模选择，不是一个通用的、放之四海而皆准的"catalog 树"要求。**判断依据**：读了 `knowledge_point.py`（无此规则，契约本身不关心节点间的父子形状）和 `verify_tree.py` 第 134-139 行的注释（"Two tree shapes are legitimate…Infer which one this is rather than forcing one shape onto both"——**作者自己写明了"不要把一种形状强加给另一种"，但实现上只做到了两种分支，没想到 cs408 是第三种**）。所以该改的是验证器的分支覆盖度，不是这条规则本身。
- **契约白名单要不要扩** —— **不扩，维持"节点级来源支持度字段永不上树"**。理由已经很充分：(1) 4.3 条已证实白名单被状态流转/频率统计共用，扩它的影响面远超"给树加个字段"这么简单；(2) 4.4 条已证实目前零消费方，没有任何实际需求在等这个扩展；(3) sidecar 方案已经工作良好（B 方向的校验器测试全过），没有理由为了"少一个文件"而承担白名单扩张的风险。

### 方向 E：一次性收敛 vs 继续打补丁 —— **一次性收敛，范围见下节**

---

## 3. 推荐的最小稳定终态

**保留哪些文件**：
- `data/structured_materials/cs408/knowledge_tree_multisource.yaml` —— 唯一的、契约可验证的主表（410 节点）
- `data/structured_materials/cs408/knowledge_tree_agreement.yaml` —— 唯一的、非契约 sidecar（410 行元评估）
- `data/raw_materials/cs408/syllabus/*`、`data/raw_materials/cs408/exam_banks/*` —— 已在 round-29 移入，不变
- `tools/round29_build_tree_split.py`、`tools/round29_quote_locate.py`、`tools/tree_source_support.py`、`tools/round29_validate_agreement.py` —— 保留为 multisource/agreement 的唯一生成与校验链路
- `tools/verify_tree.py` —— 保留为主表（及 math1/eng1）唯一校验器，扩展第三条 catalog 分支

**归档（移入 `data/structured_materials/cs408/archive/` 或等价目录，不删除）**：
- `knowledge_tree.yaml`（基线）
- `knowledge_tree_weighted.yaml`（round-24 中间产物）
- `knowledge_tree_opus.yaml`
- `audit_round6.py`、`generate_tree_round6.py`（低置信度，归档前需一次引用复核）

**字段命名**：
- 节点级来源支持度：`source_support`（已定案，round-29 命名，不再变）——**永不进入主表**，只活在 agreement sidecar
- `ky/schedule/review_clip.py` 的 `weight`（学科时间预算）、`tools/apply_knowledge_weights.py` 的 `weight`（题目置信度）：**不改名**——它们不在本次讨论范围内，且各自语境清晰，本次只是确认它们和 `source_support` 不是一回事

**由谁校验**：
- 主表：`tools/verify_tree.py`（扩展第三分支后）
- sidecar：`tools/round29_validate_agreement.py`（增加 `baseline_relation_counts` 自洽性检查）
- 两者永不交叉：**不存在"sidecar 也要过 verify_tree.py"这回事**，这条边界应该写进 `verify_tree.py` 或 sidecar 文件本身的文档字符串里，防止未来又有人手动跑错命令产生一次假警报

---

## 4. 实施步骤与顺序，及每步完成标准

**顺序原则：先补验证器缺口，再动数据文件位置，最后收尾清理。理由是如果先归档再改验证器，一旦验证器改动发现新的意外失败类别，回溯成本更高。**

1. **给 `verify_tree.py` 加第三条 catalog 分支（outline catalog）**
   - 完成标准：`py -3.12 tools/verify_tree.py data/structured_materials/math1/knowledge_tree.yaml` 依然 `ALL CHECKS PASSED`（回归测试，math1 不能退化）；`py -3.12 tools/verify_tree.py data/structured_materials/cs408/knowledge_tree_multisource.yaml` 的 `section_ancestor`/`chapter_missing_suffix` 两类失败清零（`subject_rank` 暂不要求，见步骤 2）
   - 建议连带写一个类似 `test_math1_shape_is_locked` 的 `test_cs408_outline_shape_is_recognized` 测试，锁定这条新分支不会被将来的改动误伤

2. **处理 `subject_rank`（考查目标 vs 验证器"唯一 subject"假设的矛盾）**
   - 先确认这是唯一一处该矛盾出现的地方（cs408 四科都用了这个"考查目标"模式，math1/eng1 没有），再决定是给验证器加"考查目标类子节点例外"，还是给这类节点换一个新的、`VALID_SCOPES` 里没有的 scope 值（后者代价更大，牵动 `knowledge_point.py` 的契约本身、`NON_EXAMINABLE_SCOPES`、`BLOCK_ASSESSABLE_SCOPES` 等下游逻辑，**不建议在本轮做**）
   - 完成标准：`multisource` 主表跑 `verify_tree.py` 后 `subject_rank` 类失败清零，且 math1/eng1 的既有测试全绿

3. **`round29_validate_agreement.py` 增加 `baseline_relation_counts` 一致性检查**
   - 完成标准：新增一个断言/测试，故意把 sidecar 里的 `baseline_relation_counts` 改错一个数字，验证器必须报错

4. **`knowledge_tree_multisource.yaml`（此时应已 ALL CHECKS PASSED）正式确立为唯一主表**
   - 完成标准：`py -3.12 tools/verify_tree.py data/structured_materials/cs408/knowledge_tree_multisource.yaml` 退出码为 0

5. **归档四份文件到 `archive/`**
   - 归档前对 `audit_round6.py`/`generate_tree_round6.py` 做一次 `grep -rln "audit_round6\|generate_tree_round6" . --include="*.py"` 复核，确认零引用后再移动
   - 完成标准：`data/structured_materials/cs408/` 目录下只剩 `knowledge_tree_multisource.yaml`、`knowledge_tree_agreement.yaml`；旧文件在 `archive/` 下可被找到且内容字节不变（用 sha256 对比移动前后）

6. **跑一次全量回归**：`pytest tests/ -k "tree or knowledge"`，确认步骤 1-5 都没有破坏既有测试

---

## 5. 明确建议"不做"的事

- **不改 cs408 的任何 `knowledge_point_id`**（方向 A 已论证：改了也治不好 chapter_missing_suffix/subject_rank，且白白牵动 432 条题目映射）
- **不给 `knowledge_point.py` 的 `_POINT_KEYS` 白名单加字段**（sidecar 方案已验证可行，没有实际消费方在等这个扩展）
- **不让 sidecar 兼容 `verify_tree.py`**（语义不同的两类文件，硬凑兼容只会重演 round-24 的错误）
- **不删除任何被归档的文件**（只移动位置，保留 sha256 可追溯）
- **不在本轮引入新的 scope 值来解决"考查目标"问题**（步骤 2 的备选方案之一，代价过大，超出本轮"最小稳定终态"范围，如果步骤 2 的"加例外"方案走不通，应该单独开一轮讨论而不是顺手在这轮做掉）
- **不处理 `ky/schedule/review_clip.py` 和 `tools/apply_knowledge_weights.py` 的 `weight` 命名**——它们跟本次讨论的字段没有实际冲突（分属不同模块、不同文件、不会被同一段代码同时读到），改名纯粹是无谓的范围膨胀

---

## 6. 没有把握的地方

- `audit_round6.py`/`generate_tree_round6.py` 是否真的零引用——我只搜了 `.py` 文件的直接 import/exec，没有搜 shell 脚本、文档里的调用示例（这些不会导致代码层面的破坏，但可能有人工操作流程依赖它们的存在）
- 步骤 2（`subject_rank`）的"加例外"方案具体怎么写没有细化到代码层面——我判断这是可行方向，但没有像步骤 1 那样验证过一个具体实现；也不排除深入之后发现"考查目标"节点还有别的、我没注意到的下游依赖（比如 `NON_EXAMINABLE_SCOPES` 相关的调度/统计逻辑是否已经依赖了"同前缀下只有一个 subject"这个隐含假设——我没有去 `ky/schedule/` 或频率统计代码里反向确认这点）
- `knowledge_tree_opus.yaml` 的历史比对价值——我只确认了"没有代码引用它"，没有去判断它对人工复核/未来审计是否还有价值（比如作为"独立抽取结果"用来抽查 multisource 质量）

---

## 7. 「实测」vs「推断」总结

**实测（我本人在这次评审里跑过命令/读过代码原文得到的结论）**：
- 底本 1.1 节全部 9 条
- 三类结构失败的精确计数（116/48/56=220）及其在 multisource 上逐一相同
- math1 树全过、eng1 树全过
- `test_math1_shape_is_locked` 存在且断言了 `.chapter`/`.content`/`.requirements` 三件套
- `knowledge_point.py` 30-37 行注释明确写"考查目标"应为 subject scope
- cs408 树里确有 16 个"考查目标"相关节点被标为 `scope: subject`
- opus 树零代码引用
- exam_questions 117 个 cs408 id 在 baseline 与 multisource 中都 100% 命中
- 没有任何测试/工具对 cs408 目录做"批量跑 verify_tree.py"的盲扫

**推断（基于实测证据的判断，但没有做到穷尽验证）**：
- "考查目标 vs subject_rank 规则冲突"是**设计意图层面的矛盾**而非数据 bug——这是我把 `knowledge_point.py` 的注释和 `verify_tree.py` 的实现对照后得出的判断，我没有找到第三方文档明确写"这就是已知的已接受的矛盾"，所以标记为推断而非定论
- `audit_round6.py`/`generate_tree_round6.py` 可以安全归档——基于 grep 零引用，但没有做穷尽的人工流程排查
- 归档（而非删除）四份文件是"低成本"——推断基于"文件不大、sha256 可追溯"，没有实际测量过团队维护这类归档目录的历史成本
