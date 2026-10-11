# Round 29: 408 加权树拆分为「可验证主表 + 一致性附表」—— 执行报告

执行者：Claude Sonnet 5（claude-sonnet-5, high）
任务书：`review/rounds/round-29-tree-split-task.md`

## 摘要（先说结论，细节见下文）

- 第 1 步：B（2022 大纲 PDF）、C（408 题库 JSON）已复制进项目，复制前后 SHA-256 逐字节比对一致；`tools/round22_extract.py` 的 `PDF` 常量已改为项目内路径（原 Temp 文件保留未删）。
- 第 2 步：`evidence_tag → source_support`（原名 `weight`，见"命名冲突"节）规则已抽成 `tools/tree_source_support.py::derive_source_support()`；用现有 410 个节点的 `(evidence_tag, source_count, match_kind)` 反推，**410/410 全部重现，零漏配**（`tests/test_tree_source_support.py`）。
- 第 3 步：新建主表 `knowledge_tree_multisource.yaml`（410 节点，与 `knowledge_tree.yaml` 同构）与附表 `knowledge_tree_agreement.yaml`（410 条注记）。**没有改动或退休任何旧文件**——`knowledge_tree_weighted.yaml`、`tools/round24_build_weighted_tree.py`、`tools/round24_validate_weighted_tree.py`、`tests/test_round24_weighted_tree.py` 原样保留，仍全绿。
- 第 4 步：verify_tree.py 的 **contract / hashes / quote_ref 三项在主表上全部 OK**；但发现一个**任务前提之外、独立于本次改动的既存问题**——verify_tree.py 的"章节结构"检查（第 4 类检查）在**未被本任务触碰的基线 `knowledge_tree.yaml` 上同样失败**，且失败的节点集合、类别、数量与主表**逐一相同**。这不是本次拆分引入的回归，但意味着字面意义上的"verify_tree.py 全过"目前对任何 cs408 树都不可达。详见下文"关键发现"。**我没有修改 verify_tree.py**，按纪律要求把决定权留给用户。
- 附表 410 个 `source_support` 值与改造前 `weight` 值**逐一相等，零漂移**。
- `py -3.12 -m unittest discover -s tests -q`：开工前 **213 个测试全绿**（71.4s）；收工后 **238 个测试全绿**（86.5s，新增 25 个测试，无一失败/跳过）。
- 报告路径：本文件。

---

## 关键发现：verify_tree.py 对 cs408 树的"章节结构"检查存在既存缺陷，基线本身也过不了

任务书的前提是"验基线树 `knowledge_tree.yaml`——`contract : OK (403 nodes validated)`"，我在**完整跑完整个 `verify_tree.py`（不只看第一行）**后发现：

```
$ py -3.12 tools/verify_tree.py data/structured_materials/cs408/knowledge_tree.yaml
contract        : OK (403 nodes validated by ky.knowledge.knowledge_point)
sources         : 1 distinct files, 1 hashed
hashes          : OK
quote_ref       : OK
...
FAILURES:
  - cs408.ds.chapter-01.section-01: section has no ancestor node 'cs408.ds.chapter-01.chapter'
  ...(共 116 条 section_ancestor + 48 条 chapter_missing_suffix + 56 条 subject_rank，合计 220 条)
退出码：1
```

**根因**：`verify_tree.py` 的结构检查（`section` 必须有 `<...>.chapter` 结尾的祖先节点；`chapter` 节点必须有 `<base>.content`/`<base>.requirements` 两个同级节点）是照着 **math1 树的 ID 约定**写的——math1 的 chapter id 确实以 `.chapter` 结尾（`tests/test_tree_integrity.py::test_math1_shape_is_locked` 里 `p.knowledge_point_id[: -len(".chapter")]` 就是证据）。但 **cs408 的 chapter id 是 `cs408.ds.chapter-01` 这种把编号嵌进 id 本身的形式，从不以 `.chapter` 结尾**，也没有 `.content`/`.requirements` 兄弟节点。这个检查从写下的那天起，只要真的跑到底，就会在 cs408 的任何树上失败——包括从未被本任务碰过的 `knowledge_tree.yaml` 本身。

我用直接调用 `ky.knowledge.knowledge_point.load_knowledge_points()` 复算了同一批检查（不经过 verify_tree.py 的 CLI 截断输出），确认：

| | 节点数 | section_ancestor 失败 | chapter_missing_suffix 失败 | subject_rank 失败 |
|---|---|---|---|---|
| `knowledge_tree.yaml`（基线，未改动） | 403 | 116 | 48 | 56 |
| `knowledge_tree_multisource.yaml`（本次主表） | 410 | 116 | 48 | 56 |

**两者的失败类别、数量、具体节点 id 逐一相同**（`tests/test_round29_tree_split.py::test_baseline_and_main_table_fail_the_same_pre_existing_structural_checks` 已固化此对比为回归测试）。也就是说：

- 我**没有**引入任何新的失败类别或新增失败节点；
- 主表在"这次任务真正要新增验证的东西"上（contract 是否符合 `ky.knowledge.knowledge_point` 白名单、sha256 是否对得上磁盘字节、quote_ref 是否能在声明的源文件里定位到）**全部通过**；
- 但字面意义上的"`verify_tree.py <主表>` 全过（退出码 0）"目前**对任何 cs408 树都不可达**，这与任务书的前提（"基线...全过"）不符——前提大概率只截取/复述了 `contract : OK` 这一行，没有跑到底看退出码。

按纪律"禁止为了让验证器通过而放宽验证器……如果必须开例外，先停下来在报告里说明，不要自己决定"：**我没有修改 `tools/verify_tree.py`**，也没有改动 cs408 的 chapter id 命名（那会牵动 `ky/` 里所有引用 cs408 id 的下游代码，远超本任务范围）。这是一个需要用户决定如何处理的既存缺陷（是修 verify_tree.py 的章节假设，还是给 cs408 单独放宽结构检查、或接受 cs408 树永远拿不到"ALL CHECKS PASSED"），我把决定权留在这里。

---

## 第 1 步：把 B/C 源移进项目

| | 原路径（Temp，未删除） | 新路径（项目内） | 复制前 SHA-256 | 复制后 SHA-256 | 一致 |
|---|---|---|---|---|---|
| B（2022 大纲 PDF） | `C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\ghsurvey\downloads\408_syllabus_2022.pdf` | `data/raw_materials/cs408/syllabus/408_syllabus_2022.pdf` | `60c54de8fbc5642543d3324580f83f5f95ff435609fcad8f4baf58d125aabcaf` | 同左 | ✅ |
| C（408 题库 JSON） | `C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\ghsurvey\downloads\408q_full.json` | `data/raw_materials/cs408/exam_banks/408q_full.json` | `451197409bd3471168ccb1754a86e766bf528c8f354ec1866ace82701d03f275` | 同左 | ✅ |

- 复制用 `shutil.copy2` + 复制前后各自现算 `hashlib.sha256`，两次哈希逐字节相等（详见执行记录；数值已固化进 `tools/round29_build_tree_split.py` 的 `source_registry` 输出）。
- Temp 目录原件**未删除**，仍在原处，可交叉核对。
- `tools/round22_extract.py` 的 `PDF` 常量从 Temp 路径改为 `ROOT / "data/raw_materials/cs408/syllabus/408_syllabus_2022.pdf"`（字节不变，只是路径搬家）。这个常量被 `round24_build_weighted_tree.py`、`round24_validate_weighted_tree.py`、`tests/test_round24_weighted_tree.py`（间接经由 validator）复用；改动后重跑 `tests.test_round24_weighted_tree`，**15 个测试全绿**，证明这个改动没有破坏任何既有断言。
- **额外产出（第 3 步需要，此处一并说明来源）**：`data/raw_materials/cs408/syllabus/408_syllabus_2022.extracted.txt`（14231 字节，SHA-256 `b6f2d739ec72df272dda2c7a1d93e70c4a051b70e9e4fd38d365fd1e341f022f`）——用 `round22_extract.extract_2022()` 对 B 做的确定性纯文本抽取（`normalized_source_text` 字段，逐字节可重跑复现）。**这不是第三份新源，是 B 的一个只读、确定性派生视图**：`verify_tree.py` 按 UTF-8 文本读取源文件做 `quote_ref` 字符串定位，无法处理 PDF 二进制流，所以主表节点凡引用 B 的 `sources[].path` 都指向这个 `.txt`，而不是 `.pdf` 本身。`sources_registry` 里两者的 SHA-256 都各自登记（`B_raw` 与 `B_text`），互不混淆。

---

## 第 2 步：`evidence_tag → source_support` 规则表 + 410 值全部重现的证明

### 规则表（`tools/tree_source_support.py`）

| evidence_tag | source_support | 需要 match_kind 才能确定？ | 理由 |
|---|---|---|---|
| `dual_source_exact` | 1.00 | 否 | 两源皆有，且是精确/全文匹配 |
| `structural_equivalent` | 0.75 | 否 | 两源皆有，但只是重排/改名/模糊/拆分/迁移/提升后的匹配 |
| `candidate_recent_new` | 0.75 | 否 | 2026 新增，或 2022 已知的新近考点 |
| `single_source_unverified` | 0.50 | 否 | 仅一源支持，无独立印证 |
| `legacy_only_pending` | 0.50 | 否 | 仅 2022 出现，2026 未见对应编号条目 |
| `text_layer_ocr_risk` | **1.00** 若 `match_kind ∈ {exact, reorder_exact, full_text_match}`；**0.75** 若 `match_kind ∈ {fuzzy, manual_override, split_from_2022, cross_section_move, scope_promotion_from_item}` | **是** | OCR 风险标记只是"盖住"了原本的 tag，实际支持度沿用被盖住之前那次匹配的强度 |

`source_count` 在公式里**不独立影响数值**（它与 `evidence_tag` 天然一致，比如 `dual_source_exact` 恒为 2），保留在函数签名里只是为了校验调用方传入的三元组是否自洽——凡不在 `KNOWN_COMBINATIONS`（410 个节点中实际出现过的 16 种 `(evidence_tag, source_count, match_kind)` 组合）里的输入，直接抛 `UnknownSourceSupportCombination`，不做任何"合理猜测"。

### 410 值全部重现的证明

`tests/test_tree_source_support.py::test_reproduces_all_410_weight_values`：把 `knowledge_tree_weighted.yaml` 里全部 410 个节点的 `(evidence_tag, source_count, match_kind)` 喂给 `derive_source_support()`，与该节点的历史 `weight` 逐一比较。

```
$ py -3.12 -m unittest tests.test_tree_source_support -v
test_every_combination_seen_in_the_data_is_declared_known ... ok
test_exactly_410_nodes ... ok
test_reproduces_all_410_weight_values ... ok
test_known_tag_with_wrong_match_kind_is_rejected ... ok
test_known_tag_with_wrong_source_count_is_rejected ... ok
test_ocr_risk_requires_a_known_match_kind ... ok
test_unknown_tag_is_rejected ... ok
----------------------------------------------------------------------
Ran 7 tests in 0.298s
OK
```

**410/410，零失配。**

---

## 第 3 步：拆分——主表与附表

### 主表：`data/structured_materials/cs408/knowledge_tree_multisource.yaml`

- **410 节点**（403 条继承自基线 `kept` + 7 条 `new_vs_baseline`），顶层是**裸列表**（不是带 `items:` 键的字典），与 `knowledge_tree.yaml` **完全同构**——同一套契约字段：`schema_version / knowledge_point_id / title / scope / status / source_kind / sources / frequency / evidence / transition_history / supersedes / revision`，**不含** `aliases / weight / source_count / evidence_tag / baseline_relation / match_kind` 这 6 个白名单外字段。
- `sources`：403 条基线节点里，387 条在 A 记录之外补上了真实的 B 记录（`{path: .../408_syllabus_2022.extracted.txt, sha256, locator: {quote_ref}}`）；`quote_ref` **保证是源文件里逐字可定位的真实子串**（构造方法见下）。其余 16 条基线节点（`evidence_tag` 为 `single_source_unverified` 中一部分等）保持单源 A。7 条新节点 `sources` 只含 B 一条记录，符合任务书"作为普通节点、sources 只含 B"的要求。
- `source_kind` 全部为 `official_outline`（A、B 都是官方/半官方考纲文本，属同一 source_kind，不需要区分）。

**quote_ref 的构造方法（原本会失败，已解决）**：`round24_build_weighted_tree.py` 判定"2026 标题在 2022 全文中出现"用的是 `key()`——NFKC + casefold + `1/o`→`i/o` 的 OCR 修正 + 去掉全部空白和标点后的**模糊包含检测**。直接把这个"模糊匹配上"的原始标题文本当 `quote_ref` 塞给 `verify_tree.py`（它只做**空白折叠**，不去标点、不 casefold），24/387 个候选**在初次尝试时定位失败**（例如 2026 标题 `"IEEE 754 标准。"` 末尾的句号在 2022 原文对应位置其实是换行，不是句号；`"设备的...I/O 接口"` 在 2022 文本层里 OCR 成了 `l/o`）。

我写了 `tools/round29_quote_locate.py`：对源文本做与 `key()` **完全一致**的归一化（NFKC → casefold → OCR 修正 → 去标点/空白），同时记录每个保留字符在原文里的原始位置（"keymap"），命中后把原始位置区间**逐字节切回原文**当作 `quote_ref`——这样定位到的文本对 `verify_tree.py` 的宽松 `norm()` 天然成立（它是真实原文的一个连续子串）。用这个方法重跑全部 387 个候选：**387/387 全部定位成功，零遗留**（详见 `tests/test_round29_quote_locate.py` 的 4 个真实回归用例）。

### 附表：`data/structured_materials/cs408/knowledge_tree_agreement.yaml`

- **410 条注记**，按 `knowledge_point_id` 关联，顶层字段：`schema_version / generated_at / generator / concept_name / concept_note / source_registry / baseline_relation_counts / items`。
- 每条 `items[]`：`knowledge_point_id / source_support / source_count / evidence_tag / match_kind / baseline_relation / aliases`（`review_note` 仅 7 条新节点有，可选）。
- **不经过** `ky.knowledge.knowledge_point.validate_knowledge_point()`；自带的小 schema 在 `tools/round29_validate_agreement.py::validate()` 里独立实现（字段白名单、取值集合、交叉引用主表、重算 `source_support`）。
- `source_support` **全部由第 2 步的函数派生**，不是手填静态值——`round29_build_tree_split.py` 在构建每个节点时都会 `derive_source_support(tag, source_count, kind)` 并与 `round24_build_weighted_tree.evidence_for()` 算出的历史值**断言相等**，任何一条不等就直接抛异常中止构建（这就是"硬门槛"在构建时的落地，不只是事后检验）。
- **可再生成**：`py -3.12 tools/round29_build_tree_split.py` 对同样的输入（baseline 树 + B 文本 + 已验证的对齐上下文）重复执行，`tests/test_round29_tree_split.py::ReproducibilityTest` 证明两次调用 `build()` 的 `main_items`/`agreement_items` **深度相等**（附表顶层 `generated_at` 是当次墙钟时间，故意不参与这个比较，只比较对结果有意义的 `items` 内容）。

---

## 第 4 步：五项验证的实际输出

### ① `py -3.12 tools/verify_tree.py <主表>`

```
contract        : OK (410 nodes validated by ky.knowledge.knowledge_point)
sources         : 2 distinct files, 2 hashed
hashes          : OK (every sources[i].sha256 matches the bytes on disk)
quote_ref       : OK (every quote_ref locates in its declared source)
tree shape      : catalog (subject/chapter/section)
structure       : {'subject': 20, 'chapter': 24, 'section': 116, 'item': 250}
FAILURES: (220 条，全部是"关键发现"一节所述的既存章节结构假设不匹配，与基线逐一相同)
退出码：1
```

**contract / hashes / quote_ref 三项 OK**；退出码非零的唯一原因是上面"关键发现"一节描述的、独立于本任务、基线同样存在的既存缺陷。

### ② 主表与基线树的节点集合关系

```python
baseline_ids ⊆ main_ids   # True
len(main_ids) - len(baseline_ids) == 7   # True
main_ids - baseline_ids == {7 个 legacy-item id}  # 与 knowledge_tree_weighted.yaml 里 baseline_relation=new_vs_baseline 的 7 个 id 完全相同
```
（`tests/test_round29_tree_split.py::SupersetRelationTest`，2 个测试全绿）

### ③ 附表 `source_support` 与改造前逐一相等

```
old_by_id = {pid: weight for ... in knowledge_tree_weighted.yaml}       # 410 条
new_by_id = {pid: source_support for ... in knowledge_tree_agreement.yaml}  # 410 条
set(old_by_id) == set(new_by_id)   # True
{pid: (old,new) for pid where old != new} == {}   # True，空集
```
（`tests/test_round29_tree_split.py::SourceSupportUnchangedTest`，全绿）

### ④ 附表独立校验脚本

```
$ py -3.12 tools/round29_validate_agreement.py
VALID: 410 agreement entries, 0 errors
```
检查内容：字段白名单（无多无少）、取值集合（`baseline_relation`/`evidence_tag`/`source_support`）、每个 id 都能在主表找到、主表里也没有附表未覆盖的 id、`source_count` 与主表实际 `len(sources)` 一致、`source_support` 与 `derive_source_support()` 重算结果一致。

### ⑤ 变异测试（含还原哈希证明）

`tests/test_round29_tree_split.py::MutationTest`（全部只操作内存副本/临时文件，`setUp`/`tearDown` 记录并断言真实文件的 SHA-256 在测试前后未变）：

| 变异 | 断言 | 结果 |
|---|---|---|
| 主表某节点 `sources[0].sha256` 改成 `"0"*64` | `verify_tree.py` 对临时文件退出非零，输出含 `"sha256 mismatch"` | ✅ 变红 |
| 附表某 `dual_source_exact` 节点 `source_support` 改成 0.42 | `round29_validate_agreement.validate()` 报错含 `"source_support=0.42"` | ✅ 变红 |
| 附表新增一条主表没有的 id | 报错含 `"not found in main table"` | ✅ 变红 |
| 附表某条 `source_count` 改成 99（与主表实际 `len(sources)` 不符） | 报错含 `"source_count=99"` | ✅ 变红 |
| 从附表删掉一条主表有的 id | 报错含 `"missing"` 且 `"id"` | ✅ 变红 |
| 真实文件 SHA-256（`knowledge_tree_multisource.yaml` / `knowledge_tree_agreement.yaml`）测试前后 | 逐字节相等 | ✅ 未被任何变异测试污染 |

### ⑥ `unittest discover` 前后对比

```
开工前：Ran 213 tests in 71.395s — OK
收工后：Ran 238 tests in 86.474s — OK
```
新增 25 个测试（`test_tree_source_support.py` 7 个 + `test_round29_quote_locate.py` 6 个 + `test_round29_tree_split.py` 12 个），**无一失败、无一跳过**；原有 213 个测试**原样全绿**（包括改了路径常量后重跑的 `test_round24_weighted_tree.py` 15 个）。

---

## 三个同名 `weight` 的处理

| 位置 | 含义 | 本次改动 |
|---|---|---|
| `ky/schedule/review_clip.py` 的 `weight` | 学科级**每日时间预算**权重（`config.subject(subject_id).weight`） | 未改动 |
| `tools/apply_knowledge_weights.py` 的 `weight` | 题目 → 知识点分布的**置信度**（`knowledge_point_weights` 字典里的值） | 未改动 |
| 本任务节点级的"权重" | 知识点标题被两份考纲**来源支持的强度** | **只改名，不改语义**：新字段叫 `source_support`，取值集合（0.5/0.75/1.0）、判定规则与原 `weight` 完全一致；旧文件 `knowledge_tree_weighted.yaml` 里的字段名仍叫 `weight`（该文件本身未被改动，见下） |

三者互不调用、互不依赖，本次没有改动前两者的任何代码或字段名——只是确保**新引入的第三个概念**不再共用"weight"这个已经被占用两次的名字，并在 `tools/tree_source_support.py` 与附表的 `concept_note` 字段里各写了一遍区别说明。

---

## 「我实测到了」vs「我推断」

**我实测到了**：
- B、C 复制前后 SHA-256 逐字节相等；A 的 SHA-256 与基线树里已登记的值相等。
- `(evidence_tag, source_count, match_kind)` 在 410 个节点里只构成 16 种组合，每种组合对应唯一 `weight` 值（用 `Counter`/分组直接统计，零歧义）。
- 387 个需要 B 记录的候选节点，用原始 `raw_2022` 文本直接当 `quote_ref` 时，24 个在 `verify_tree.py` 的空白折叠归一化下**定位失败**；换成 keymap 方法后 387 个**全部定位成功**。
- 基线 `knowledge_tree.yaml`（未改动）在完整跑完 `verify_tree.py` 后**退出码为 1**，失败于 220 条"章节结构"检查（116 section_ancestor + 48 chapter_missing_suffix + 56 subject_rank），与本次主表的失败集合逐一相同。
- 主表 `contract`/`hashes`/`quote_ref` 三项检查在完整 410 节点上全部 `OK`。
- 附表 410 个 `source_support` 值与改造前 `weight` 值集合相等且逐一相等（零漂移）。
- `unittest discover` 开工前 213 全绿、收工后 238 全绿。

**我推断**（未逐一人工核实，标注置信依据）：
- 24 个 `quote_ref` 定位失败案例背后的具体原因（句末标点差异、OCR 把 "I/O" 认成 "l/o"）——这是从**部分**样例（如 `IEEE 754 标准`、`设备的基本概念...`）人工比对原文得出的解释，**没有对全部 24 条逐条人工确认**，只确认了修复后全部 387 条能定位成功这个结果本身。
- `round24_build_weighted_tree.py::evidence_for()` 判定"哪个节点该有哪个 `evidence_tag`"的**分类逻辑本身**没有被本任务重新审查或验证正确性——本任务只验证"给定已分配的 `evidence_tag`，能不能推出正确的 `weight`"，完全信任 round-24 报告已经审过的对齐/分类结果。

---

## 没有把握的地方（至少 3 条）

1. **verify_tree.py 的章节结构检查该怎么处理，不是我能决定的**——如"关键发现"一节所述，这个检查对 cs408 的 id 命名约定从一开始就不成立，基线树本身也过不了。我判断"不碰 verify_tree.py、不碰 cs408 的 id 命名"是当前纪律下最安全的选择，但这只是把问题留在原地，不是修复它；用户可能有更合适的处理方式（比如给 verify_tree.py 按 tree shape 分流不同的结构检查规则，类似它已经对 eng1 的"structure tree"做的事）。
2. **`405_syllabus_2022.extracted.txt` 作为"可引用来源"这个设计选择本身，我没有找到项目里的先例可以对照**——目前全仓库没有任何知识点引用过 PDF 来源（唯一的 `official_outline` source_kind 例子就是本次的 A/B），"PDF 本身不可被 verify_tree.py 当文本读，所以引用它的确定性文本抽取物"这个模式是我这次新引入的,而不是沿用既有约定。如果项目对"什么文件可以作为 sources[].path"有本报告没触及的隐含要求，这个设计可能需要重新讨论。
3. **7 个 `legacy_only_pending` 新节点的 `knowledge_point_id` 编号方案**（`<parent>.legacy-item-NN`）直接照抄了 `round24_build_weighted_tree.py` 里的旧编号逻辑，是为了让这 7 个 id 与历史 `knowledge_tree_weighted.yaml` 里的记录保持一致、可交叉核对——但我没有评估过这套编号是否符合 cs408 树未来收编"真正的正式节点"时的命名规范（比如它们会不会需要改名成不含 `legacy-item` 字样的正式 id）。
4.（额外一条）**`aliases` 字段在附表里沿用了 round-24 的原始生成逻辑**（`raw_2022 != n["title"]` 时才记一条别名），我没有重新审查这批别名文本本身的翻译/OCR 质量，只确认了它们在源文件里能被逐字定位（`verify_tree.py` 的 `quote_ref` 检查覆盖的是"存在性"，不是"内容准确性"）。

---

## 变更清单

**新建**：
- `data/raw_materials/cs408/syllabus/408_syllabus_2022.pdf`
- `data/raw_materials/cs408/syllabus/408_syllabus_2022.extracted.txt`
- `data/raw_materials/cs408/exam_banks/408q_full.json`
- `data/structured_materials/cs408/knowledge_tree_multisource.yaml`
- `data/structured_materials/cs408/knowledge_tree_agreement.yaml`
- `tools/tree_source_support.py`
- `tools/round29_quote_locate.py`
- `tools/round29_build_tree_split.py`
- `tools/round29_validate_agreement.py`
- `tests/test_tree_source_support.py`
- `tests/test_round29_quote_locate.py`
- `tests/test_round29_tree_split.py`
- `review/rounds/round-29-tree-split-claude.md`（本文件）

**改动**：
- `tools/round22_extract.py`：`PDF` 常量从 Temp 路径改为项目内路径（字节内容不变）。

**未改动**（刻意保留，供交叉核对/历史留痕）：
- `data/structured_materials/cs408/knowledge_tree_weighted.yaml`
- `tools/round24_build_weighted_tree.py`
- `tools/round24_validate_weighted_tree.py`
- `tests/test_round24_weighted_tree.py`
- `ky/knowledge/knowledge_point.py`（白名单未动——第 2 步的推导没有证明需要新增字段，全部新信息都放进了走独立小 schema 的附表）
- Temp 目录下的 B/C 原件
