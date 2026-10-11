# 对抗性验证报告：round-31 verify_tree.py 修复（gpt-5.6-sol 声称）

审查对象：`F:\workspace\kaoyan-ai-system\tools\verify_tree.py`（round-31 后版本）
被审查报告：`review/rounds/round-31-verifier-fix-codex.md`
审查者：claude-sonnet-5（本轮只读，未修改 `tools/verify_tree.py` 或 `data/**` 任何文件）
探针目录：`C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\adv\`（`probe.py` + 生成的 `mut_*.yaml` + `p16_minimal.yaml` + `p17_disguised_ambiguous.yaml` + `probe_output.txt`）

## 结论先说

**证伪。** 原报告声称的四条完成标准里，标准 1/2/3（四棵真实树全过 + unittest 全绿）**属实**；但标准 4「不明即拒 / 结构必须真的被检查」**不成立**——存在至少三条独立可复现的路径，能让验证器在树被严重破坏（整章节点被删除、树形被伪装成歧义形态）时仍打印 `ALL CHECKS PASSED` 并以退出码 0 通过；另外 eng1 所用 `structure` 树形的 item-parent 检查是**必然为真、永远不会失败的死代码**，与本轮改动是否触及它无关，但直接反驳"structure-tree 规则仍然生效"这一隐含前提。

---

## 1. 我实际跑的命令与原始输出

### 1.1 基线复核（四棵真实树 + 完整 unittest + 聚焦回归）

```
py -3.12 tools/verify_tree.py data/structured_materials/cs408/knowledge_tree.yaml
py -3.12 tools/verify_tree.py data/structured_materials/cs408/knowledge_tree_multisource.yaml
py -3.12 tools/verify_tree.py data/structured_materials/math1/knowledge_tree.yaml
py -3.12 tools/verify_tree.py data/structured_materials/eng1/knowledge_tree.yaml
```
实测结果：四条命令均退出码 0，`ALL CHECKS PASSED`，节点数/树形/structure 分布与原报告第 3 节逐字一致（403/410/69/24 节点，cs408/cs408/math1/structure）。**实测：证实。**

```
py -3.12 -m unittest discover -s tests -q
```
实测：`Ran 248 tests in 92.721s` / `OK`，与原报告一致。**实测：证实。**

```
py -3.12 -m unittest tests.test_verify_tree_shapes tests.test_round29_tree_split -v
```
实测：`Ran 22 tests in 18.960s` / `OK`，全部 22 个用例逐一 `ok`。**实测：证实。**

### 1.2 我自己的探针（`probe.py`，完整原始输出见 `probe_output.txt`）

探针只在 `%TEMP%\kaoyan-probe\adv\mut_*.yaml` 上运行，从不写回 `data/**` 或 `tools/verify_tree.py`。运行前后对六个受保护文件（cs408 两棵树、math1、eng1、`verify_tree.py`、`knowledge_point.py`）做 SHA-256 比对：

```
ALL REPO FILES UNCHANGED: True
```
（`probe_output.txt` 中列出六个文件逐一的 before/after 哈希，全部相等；`probe.py` 运行后我又单独重跑了一次 `sha256sum` 六个文件，与开工前完全一致。）

---

## 2. 逐条声称结果：证实/证伪

| 声称 | 结果 | 证据 |
|---|---|---|
| cs408 两棵树 verify 全过 | **证实** | §1.1 |
| math1、eng1 仍全过 | **证实** | §1.1 |
| unittest 全绿（248） | **证实** | §1.1 |
| 聚焦回归 22 个测试全绿 | **证实** | §1.1 |
| 四条变异测试确实变红（原报告自带的 4 条） | **证实**（复核了报告贴出的命令与断言，与源码逻辑吻合，未独立重放这 4 条——它们只是复现原作者已给的命令，价值有限，我把力气放在了自己构造的探针上） | 见 `tests/test_verify_tree_shapes.py` 源码 |
| "不使用分支顺序猜测"、混合/未知树形一律拒绝（"不明即拒"） | **证伪** | 见 P1/P2/P3/P17（§3） |
| subject 规则"没有删除结构检查" | **部分证伪** | 见 P6（§3）：一种真实的层级违规被完全放过 |
| eng1 的 structure-tree 规则仍然生效 | **证伪** | 见 P16（§3）：该分支的核心检查是永假条件，从未生效过 |
| "220 条失败只是被跳过还是被正确检查" | **两者都发生**：cs408/math1 中"chapter 节点仍存在"的破坏被正确拒绝（P4/P5/P9/P10/P13/P14/P15 全部正确变红）；但"chapter 节点整体消失或被伪装"的破坏被**放过**（P1/P2/P3/P17） | §3 |

---

## 3. 我构造的探针清单与结果（原始输出节选自 `probe_output.txt`；完整版见该文件）

全部探针在真实树的内存深拷贝上构造，写入 `%TEMP%\kaoyan-probe\adv\mut_NNN.yaml`，用子进程调用 `py -3.12 tools/verify_tree.py <mut_file>`，只读取真实文件、只写临时文件。

| # | 构造 | 期望 | 实测退出码 | 实测结论 |
|---|---|---|---|---|
| P1 | cs408 真实树，**删除全部 24 个 `scope=chapter` 节点**，保留其下 116 个 section + 243 个 item | 应变红（116+243 个节点全部悬空） | **0，`ALL CHECKS PASSED`** | **BLOCKER**：树形静默降级为 `structure`，116 个 section 无任何 ancestor 检查，`ALL CHECKS PASSED` |
| P2 | math1 真实树，删除全部 22 个 `scope=chapter` 节点 | 应变红（.content/.requirements 二件套规则、section-ancestor 规则均应失效报错） | **0，`ALL CHECKS PASSED`** | **BLOCKER**：同上，math1 特有的"每章必须有 content+requirements"规则整个被绕过 |
| P3 | cs408 真实树，**不删除**节点，只把全部 24 个 chapter 节点的 `scope` 从 `chapter` 改成 `section`（id 不变，仍是合法 chapter-NN 形态） | 应变红 | **0，`ALL CHECKS PASSED`** | **BLOCKER**：`infer_tree_shape` 只看 `scope=="chapter"`，重新贴标签就能让 24 个真实章节点"隐身"，116 个原 section 全部合并成扁平 `section:140` 且无任何检查 |
| P4 | cs408 真实树，删除**一个**中间章节点（`cs408.co.chapter-06`），保留其 3 个 section | 应变红 | 1，命中 `section has no direct chapter-NN ancestor` | 正确（独立于官方测试的另一个章节，验证不是巧合） |
| P5 | cs408 真实树，某 section id 从 `chapter-01.section-01` 改写为 `chapter-99.section-01`（chapter-99 不存在），不删除任何节点 | 应变红 | 1，命中同上错误 | 正确 |
| P6 | cs408 真实树，注入一个 `scope=subject` 节点，id = 某真实 subject id + `.ghost.deep`（**孙辈**，不是直接子节点，也不在任何 chapter 的真实 id 子树内） | 不确定（这正是要测的盲区） | **0，`ALL CHECKS PASSED`** | **BLOCKER**：`subject_scope_failures` 只抓"直接子节点"，chapter 子树 rank 检查只抓"落在某 chapter 真实前缀下"的节点；一个既非直接子节点、又不挂在任何 chapter 下的 subject 孙节点，完全逃过检查 |
| P7 | eng1 真实树，删除一个 section 节点本身，保留其子 item | 不确定 | 0，`ALL CHECKS PASSED` | 见 §4 说明：此探针构造本身有缺陷（删除时连带清空了共享前缀的全部兄弟节点），**不能单独作为证据**，已被 P16 的干净复现取代 |
| P8 | eng1 真实树，试图构造"孤儿 item"（无父、无兄弟）控制组 | 应变红 | 0，`ALL CHECKS PASSED` | 同上，构造有缺陷（见 §4），但结果指向了 P16 揭示的真正根因 |
| P16 | **干净复现**：只含 1 个节点的最小合法树，`scope=item`，id=`zzz.totally.orphaned.item`，树中不存在任何其他节点、任何 section、任何共享前缀 | 应变红（"item has no parent node under 'zzz.totally'"） | **0，`ALL CHECKS PASSED`** | **BLOCKER**：`structure` 树形分支里 item 的父节点检查是死代码（见 §4 根因分析），对任何输入都不可能触发 |
| P17 | cs408 真实树删除全部 chapter 后（同 P1），再追加一个 `scope=section`、id=`cs408.zzz.ambiguous-marker.chapter` 的节点（math1 风格标记，但挂在 section 而不是 chapter 上），与仍然存在的 cs408 风格 `chapter-NN.section-NN` id 共存 | 应报 `ambiguous chapter tree`（这正是任务书重点要求的"歧义形态必须失败"） | **0，`ALL CHECKS PASSED`，`tree shape: structure`** | **BLOCKER**：`infer_tree_shape` 只检查 `scope=="chapter"` 的 id，构造一棵同时含有两种命名约定、但标记不落在 chapter 节点上的树，能完全绕开"歧义必须拒绝"的核心承诺 |
| P9 | cs408 真实树，**追加**（非重命名）一个 math1 风格 `.chapter` 后缀的新章节点，与真实 chapter-NN 节点共存 | 应报 `ambiguous chapter tree` | 1，命中该错误 | 正确（独立于官方测试用"重命名已有节点"的构造方式，用"新增节点"验证同一结论，排除官方测试可能只测了重命名路径的偶然性） |
| P10 | cs408 真实树，一个 chapter id 改成两种约定都不匹配的 `cs408.ds.unit-01` | 应报 `unrecognized chapter tree` | 1，命中该错误 | 正确 |
| P11 | 空树（`[]`） | 应报 `CONTRACT FAILURE: empty tree` | 2，命中该错误 | 正确 |
| P12 | 6 个节点的"混乱树"：id 无意义、scope 乱序（subject/chapter/section/item/chapter/item 交替，id 各不相干） | 应变红，且不能崩溃/不能"识别不出就当过" | 1，命中 `unrecognized chapter tree: expected cs408 chapter-NN ids or math1 .chapter ids` | 正确：至少在含 `scope=chapter` 节点时，"识别不出就拒绝"是成立的（这与 P17 形成对照——一旦攻击者避免使用 `scope=chapter`，同样的"识别不出"局面就不再触发拒绝） |
| P13 | cs408 **multisource**（410 节点）树，某节点 sha256 改错 | 应报 `sha256 mismatch` | 1，命中该错误 | 正确：哈希检查在更大的 multisource 文件上同样生效，不是只在 baseline 文件上生效 |
| P14 | math1 真实树，只删 `.requirements`（不删 `.content`），独立于官方"只删 .content"的测试 | 应报 `missing ...requirements` | 1，命中该错误 | 正确 |
| P15 | math1 真实树，复制一个节点制造 id 重复 | 应报 `duplicate knowledge_point_id` | 1，命中该错误 | 正确 |

---

## 4. 根因分析（不只是现象，还有为什么）

### 4.1 树形推断只信任 `scope=="chapter"` 这一个信号源（P1/P2/P3/P17 的共同根因）

`infer_tree_shape()`：
```python
chapter_ids = [p.knowledge_point_id for p in points if p.scope == "chapter"]
if not chapter_ids:
    return "structure"
```
只要真实文件里的 `scope: chapter` 字段被删除、改名、或干脆把该 id 挪到别的 scope 上，函数无条件返回 `"structure"`——不会看任何 section/item 的 id 长什么样，也不会看之前是不是像 cs408/math1。而 `structure` 分支的校验远弱于 `cs408`/`math1` 分支（没有 `subject_scope_failures`、没有 chapter 子树 rank 检查、也没有 §4.2 提到的死代码之外的其它检查）。**"三种树形严格区分"的说法只在攻击者规规矩矩地保留 chapter 标记时成立；一旦破坏面刚好是 chapter 标记本身，检查力度会断崖式下降而不是报错。**

原报告"没有把握的地方"第 3 条已经隐约触及（"不能外推为无 chapter 的任意 structure 树也会拒绝相同变异"），但报告把这一点定性为"任务书未要求"，而不是作为一个需要在完成标准里明确排除或修复的风险披露——鉴于任务书明确要求"歧义形态必须失败"，P17 表明这个要求事实上没有被满足。

### 4.2 `structure` 分支的 item 父节点检查是永假条件（P16 的根因）

```python
elif tree_shape == "structure":
    for point in points:
        if point.scope != "item":
            continue
        parts = point.knowledge_point_id.split(".")
        if len(parts) < 3:
            continue
        parent = ".".join(parts[:-1])
        if parent not in by_id and not any(
            other.knowledge_point_id.startswith(parent + ".") or other.knowledge_point_id == parent
            for other in points
        ):
            failures.append(...)
```
`other` 遍历的是 `points`，其中包含 `point` 自身。对任意 item，`point.knowledge_point_id` 天然以 `parent + "."` 开头（因为 `parent` 就是去掉最后一段的自己），所以 `any(...)` 里至少有 `other is point` 这一项恒为真。`not any(...)` 恒为假，整个 `if` 恒不成立。**这段代码不会因为任何输入而报错**——不是"弱"，是"从不执行"。P16 用一棵只有 1 个孤立节点、没有任何父节点或兄弟节点的最小树直接证实：`ALL CHECKS PASSED`。

这段代码是否是本轮改动引入，我**无法通过 git 历史确认**（`F:\workspace` 与 `F:\workspace\kaoyan-ai-system` 均不是 git 仓库，`git log`/`git blame` 均报 "not a git repository"）。但无论是否本轮引入，它直接关系到任务书要求核实的"eng1 的 structure-tree 规则是否仍然生效"——答案是从未生效。

### 4.3 `subject_scope_failures` 只覆盖两种情况，孙辈节点是盲区（P6 的根因）

该函数只对两类节点报错：(a) 与某 subject 同 scope 且 id 恰为其直接子节点；(b) 落在某 chapter 真实 id 前缀子树内、scope 却不比 chapter 窄的节点。一个 `scope=subject` 的节点，id 比另一个 subject 深两段、且不在任何 chapter 前缀下，两类都不命中，直接放过。

---

## 5. 分级问题清单

### BLOCKER
1. **P1/P2**：删除 cs408 或 math1 树中全部 `scope=chapter` 节点 → 树形静默降级为 `structure` → `ALL CHECKS PASSED`。这是最直接的"删节点、验证器仍然绿"的证据，正对应任务里要求重点攻击的方向。
2. **P3**：不删除、只把 chapter 节点的 `scope` 字段改掉，同样触发降级 → `ALL CHECKS PASSED`。说明 §4.1 的漏洞不需要"删除"这种粗暴手段，字段级篡改即可触发。
3. **P17**：构造一棵同时含 cs408 风格与 math1 风格 id、理应被判定为"歧义"的树，只要歧义标记不落在 `scope=chapter` 节点上，就会被静默接受为 `structure` 形态并通过——**直接反驳任务书要求验证的"歧义形态必须失败"这一硬指标**。
4. **P16**：`structure` 树形分支的 item 父节点检查是永真条件短路出的死代码，对任何输入都不可能报错。eng1 现在能通过验证，不是因为它的结构被正确校验，而是因为它撞上的这一检查从不执行。
5. **P6**：`subject_scope_failures` 存在孙辈节点盲区——一个真实的、不该允许的 subject 嵌套违规（不是直接子节点、不在任何 chapter 子树下）完全不被检测。

### MAJOR
- 无（P1/P2/P3/P6/P16/P17 的严重性已达 BLOCKER；未发现介于两者之间的独立问题）。

### MINOR
- 我最初为验证"structure 树 item 检查"设计的 P7/P8 构造方式有缺陷：删除节点时用了"再删除所有共享前缀的节点"这一步骤，无意中把待观测的相邻节点也清空了，导致这两个探针本身不能单独作为证据（已用 P16 的干净复现替代，见 §3、§4.2）。记录在此是为了如实说明我自己探针设计上的一次失误，而不是隐藏它。
- 在为 P16 手工构造 YAML 时，我第一次尝试通过 bash heredoc 传入含中文的 `quote_ref` 字符串，触发了 `verify_tree.py` 内部未捕获的 `UnicodeDecodeError`（读取 YAML 文件本身时崩溃，而不是优雅报错退出）。**这不是一个独立验证过的攻击面**——崩溃原因是我自己的 shell/heredoc 编码链路把文件写成了非法 UTF-8 字节，而不是我特意构造的恶意输入；换用 `Write` 工具直接写 UTF-8 文件后问题消失。是否存在"attacker 可控的、能让 verify_tree.py 崩溃而非清晰报错"的真实路径，我没有把握，仅记录为观察，未定级。

---

## 6. 实测 vs 推断

### 实测
- §1.1、§1.2 中列出的全部命令均由我本人在本次会话中执行，原始 stdout/exit code 见上文摘录及 `probe_output.txt` 全文。
- 六个受保护文件（cs408 两棵树、math1、eng1、`tools/verify_tree.py`、`ky/knowledge/knowledge_point.py`）在我的整个探针会话前后 SHA-256 完全一致，我从未对它们执行写操作（探针脚本里唯一的写文件调用只对 `TMPDIR` 下的路径）。
- P1–P17（含 P16 的最小复现）全部是我独立设计、独立运行、原始输出未经删改的构造，未复用原报告任何测试代码。

### 推断
- §4.1、§4.2、§4.3 的"根因"是我读代码后给出的机制性解释（为什么会这样），不是单纯的黑盒观察；我认为这些解释是可靠的（代码逻辑清晰、行为与解释吻合），但它们是**推断**，不是我逐行调试断点确认的。
- "这段死代码是否是本轮改动引入的"——**无法确认**，因为没有可用的 git 历史（推断的反面：我明确说了我不知道，不是含糊地假装知道）。
- 官方 4 条变异测试（原报告 §4 表格）我没有独立重放，只是读了 `tests/test_verify_tree_shapes.py` 源码确认断言与其宣称的输出吻合——这是**推断**（源码逻辑自洽），不是我本人重新执行后的**实测**。

---

## 7. 没有把握的地方

1. **P7/P8 构造缺陷的影响范围**：我用"删除共享前缀的全部节点"这一步骤，可能掩盖了 eng1 数据本身其他潜在问题（例如它是否还有别的、我没试到的合法路径能绕过检查）。P16 的最小复现证明了死代码这一点足够充分，但我不能排除 eng1 真实数据结构上还有其他未被我试到的边界情况。
2. **崩溃面（§5 MINOR 第二条）**：我不确定是否存在攻击者可控的、能让 `verify_tree.py` 抛出未捕获异常而非清晰报错退出的真实输入；我遇到的那次崩溃是自己工具链导致的编码问题，不构成独立证据。
3. **本轮改动的确切 diff 范围**：没有 git 仓库可用（`F:\workspace` 和 `kaoyan-ai-system` 均报 "not a git repository"），我完全依赖原报告自己贴出的"改动前/改动后 SHA-256"表格来判断哪些文件被碰过；我没有独立手段验证原报告所称的"改动前哈希"是否真实对应过一份历史版本，只能确认"现在的文件"与它自己在这次会话开始时的哈希一致。
4. **官方 4 条变异测试是否真的如原报告所说逐条独立运行过**：我核对了测试源码与其断言逻辑自洽，但没有重新执行这 4 条具体命令去比对原始终端输出字节，因此这一项我标注为"推断"而非"实测"（见 §6）。
5. **cs408/math1 之外，是否还有其他"降级到 structure 就能逃过检查"的变体我没试到**：我构造了删除全部 chapter（P1/P2）、重贴 scope 标签（P3）、隐藏歧义标记（P17）三种路径，但 §4.1 的根因意味着理论上还有更多变体（例如只删除一部分但让所有 chapter 标记恰好都不匹配严格正则、从而落入"unrecognized"而非我测的"全部消失"路径——这条我用 P10/P12 测过一个节点的情形，但没有测试"故意让所有 chapter id 都不匹配"的整棵树版本，即 P12 的放大版）。我认为这些变体大概率会命中同一根因，但没有逐一构造验证，属于**未完全穷举**。

---

## 附：文件清单

- `C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\adv\probe.py` — 主探针脚本（P1–P15）
- `C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\adv\probe_output.txt` — 上述脚本的完整原始输出
- `C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\adv\p16_minimal.yaml` — P16 最小复现输入
- `C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\adv\p17_disguised_ambiguous.yaml` — P17 伪装歧义树输入
- `C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\adv\mut_001.yaml` … `mut_015.yaml` — P1–P15 对应的临时变异树
