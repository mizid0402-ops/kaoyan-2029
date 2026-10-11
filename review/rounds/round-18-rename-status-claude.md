# Round 18 执行报告：把「三模型一致」的状态名从 assigned_reviewed 改成 assigned_multi_model

## 1. 改了哪些文件，每处理由

| 文件 | 改动 | 理由 |
|---|---|---|
| `tools/verify_408_index.py` | `ENUMS["knowledge_point_status"]` 加入 `assigned_multi_model`（保留 `assigned_reviewed`）；`kp is None` 的交叉检查加入 `assigned_multi_model`；新增三条规则（见 §3） | 任务书 §1、§5 要求的 schema 扩展 + 拒绝规则 |
| `tools/apply_knowledge_weights.py` | 单节点分布写 `assigned_multi_model`（原写 `assigned_reviewed`）；docstring 同步措辞 | 任务书 §2：本流程从三模型分布推出的是"模型间共识"，不是"人工复核" |
| `tests/test_exam_index.py` | `test_knowledge_point_weights_shape` 的期望值 `assigned_reviewed if ... else ...` 改成 `assigned_multi_model` | 这是对 round 15 写回结果的回归锁，写回规则变了，锁跟着变，否则这条测试会假报警 |
| `data/exam_questions/408_index_{2023,2024,2025,2026}.json`、`math1_index_{2023,2025}.json` | 116 处 `knowledge_point_status`：`assigned_reviewed` → `assigned_multi_model`；**只改状态字段，字节级验证过没有改动其他任何字段（见 §4/§5）** | 任务书 §3 |
| `data/exam_questions/{eng1_index_2024,eng1_index_2025,eng1_index_2026,math1_index_2024,math1_index_2026}.json` | **未改动**（哈希改前改后完全相同） | 这 5 个批次的 432 题分布里没有单节点（英语一树太粗、数学一 2024/2026 也全是 spread，见 `docs/题-知识点映射-多模型交叉验证方法.md` §2.4），本来就没有 `assigned_reviewed`，无需改 |
| `docs/题-知识点映射-多模型交叉验证方法.md` | 新增「五、写回状态字段」一节，列出四个取值的确切含义和产生者，明确 `assigned_reviewed` 现在专指人工复核、暂无人使用；旧「五、遗留与待办」顺延为「六」，其第 1 条标记为已完成并指回新节 | 任务书 §4 |
| `交接文档.md` | **未改动** | grep 全文搜索 `assigned_reviewed`/`assigned_unreviewed`/`knowledge_point_status`/`topic_weights`/`apply_knowledge_weights` 均无命中——这份文档从未提到知识点状态字段的具体取值，没有需要同步的内容 |

**没有改**（按任务书边界，也没有理由改）：`data/review_weights/coder_outputs/**`、`data/structured_materials/**`、`data/materials.yaml`、`data/english_vocabulary/**`；`review/rounds/*.md` 下的历史报告（round-15、本任务书自身）——这些是历史记录，不是本轮的"文档同步"对象，任务书边界里也没有把 `review/**` 列入可改范围。

## 2. 如何判断"其他地方该不该跟着改"

先用 Grep 工具搜遍全仓库找 `assigned_reviewed`（不止 `ky/`、`tools/`、`tests/`、`docs/` 四个目录，是搜了整个仓库根，因为任务书列的四个目录不保证完整），命中 12 个文件，逐个判断：

- `tools/apply_knowledge_weights.py`、`tools/verify_408_index.py`：本流程的写入/校验逻辑，**必须改**。
- `tests/test_exam_index.py`：对 round 15 写回结果的回归锁，断言写死了旧规则，**必须改**，否则字段改名后这条测试会用旧期望值去比对新数据而失败（我在改之前跑过一次全量 unittest 确认过这一点会报错）。
- `data/exam_questions/*.json`（6 个文件命中，实际应处理 11 个索引都要过一遍）：**任务书 §3 明确要求改**。
- `docs/题-知识点映射-多模型交叉验证方法.md`：**任务书 §4 明确要求改**（这次 grep 前该文档其实还没提到这两个状态值，是新增说明，不是改已有措辞）。
- `review/rounds/round-15-apply-weights-claude.md`、`review/rounds/round-15-apply-weights-task.md`：round 15 的历史任务书与执行报告，记录的是"round 15 当时做了什么、为什么用 assigned_reviewed 这个名字"。**不改**——改这些等于伪造历史记录，是历史事实的快照，而不是当前 schema 的文档来源；文档同步的职责在 `docs/` 和 `交接文档.md`，不在 `review/rounds/`（任务书边界里 `review/**` 也没有出现在"可改"清单）。
- `review/rounds/round-18-rename-status-task.md`：任务书自身，**不改**（这是用户给我的指令文件）。
- `交接文档.md`：命中的是任务书本身描述，实际文件内无命中，**不改**（见 §1 表格）。
- `ky/`：全仓库搜索没有命中任何 `ky/` 下的文件，**确认无需改动**（不是"目录里没查全"，是真的没有引用）。

判断标准：区分"当前生效的 schema / 代码 / 会被再次读取校验的文档"（要改）和"某一轮的历史事实记录"（不改，改了就是篡改记录）。

## 3. 验证器是否该拒绝本流程写入 assigned_reviewed —— 判断与实现

**判断：应该拒绝，而且能给出一条可判定（decidable）的规则，不是含糊的"大概率"。**

理由：`tools/verify_408_index.py` 是一个无状态的 schema 校验器，逐次校验时看不到"这个文件是被哪个脚本写的"。但它能看到一个可靠的指纹：`knowledge_point_weights`——这个字段目前**只有 `tools/apply_knowledge_weights.py` 一个写入者**（round 15 引入，round 18 未改变这一点），任何人工复核如果只是"对照答案书核对了 AI 给的单一节点对不对"，天然不需要三模型的置信度分布这个中间产物。所以：

> `knowledge_point_status == "assigned_reviewed"` 同时 `knowledge_point_weights` 非空
> ⟹ 这条记录要么是 round 18 改名前的遗留（本流程写的，该叫 `assigned_multi_model`），
>   要么是有人手改了状态字段却没有清掉本流程的指纹去冒充人工复核。
> 两种情况都不该放行。

实现（`tools/verify_408_index.py` 新增，位于 `knowledge_point_status` 的既有交叉检查之后）：

```python
if kp_status == "assigned_reviewed" and kpw is not None:
    problems.append(
        f"{where}: knowledge_point_status=assigned_reviewed but knowledge_point_weights "
        f"is set -- this pipeline cannot claim human review; use assigned_multi_model "
        f"for a converged 3-model distribution"
    )
```

顺带补了两条同源的完整性检查（不是任务书直接要求，但和上面这条是同一份契约里的空子，不补就是留了一半）：
- `assigned_multi_model` 但 `knowledge_point_weights` 不是恰好 1 个节点 → 拒绝（状态在说"三方一致"，分布却不是单节点，自相矛盾）。
- `assigned_unreviewed` 但 `knowledge_point_weights` 只有 0/1 个节点 → 拒绝（状态在说"有分歧"，分布却是单节点或空）。

这两条我在补之前用 §「数据扫描」脚本核对过：改名前 432 条分布里，`assigned_reviewed` 全部（116/116）是单节点、`assigned_unreviewed` 全部（316/316）是多节点，**零反例**，所以加上这两条不会误伤现有数据（下面 §5 的 verifier 全绿输出就是证据）。

**没有做的事**：没有让 `assigned_reviewed` 完全从 enum 里消失。任务书 §1 明确要求"保留但本流程不再写入"，这条规则做到的是"任何写入的记录如果带着本流程的指纹就拒绝"，而不是"这个值永远非法"——一个真正的人工复核如果不产生 `knowledge_point_weights`（比如直接改 `knowledge_point_id` 并把 `knowledge_point_weights` 设回 `null`），这条规则不会挡它。这是刻意的：规则挡的是"冒用"，不是"人工复核本身"。

## 4. 变异测试结果 + 还原哈希

**步骤**：取 `408_index_2024.json` 第一条 `assigned_multi_model` 记录（`cs408-2024-01`），手工改回 `assigned_reviewed`（`knowledge_point_weights` 保持不动），跑校验器。

```
408_index_2024.json: FAIL (1)
   - $.entries[0]: knowledge_point_status=assigned_reviewed but knowledge_point_weights
     is set -- this pipeline cannot claim human review; use assigned_multi_model
     for a converged 3-model distribution

VERIFICATION FAILED
exit code: 1
```

规则按预期触发。随后把该条状态改回 `assigned_multi_model`，用**不含结尾换行**（与原文件一致的写法，我第一次复原时手滑多写了一个 `\n`，靠哈希比对发现后立刻重写修正）重新落盘，`sha256` 与改名完成后的哈希完全一致：

```
408_index_2024.json  1ae5cdc3ce0e1b1d343f87ae60704777666fb0fedf63f43e7edc70b50cea1f79
```

**改名前后 11 个文件的完整哈希对照**（sha256）：

| 文件 | 改名前 | 改名后 |
|---|---|---|
| 408_index_2023.json | `1132bf699fc6347799a6d4ba6856bf7423aee92fd794314a2f8a7a4e02185f78` | `b22bb67224549e6bd949bc0b28550c378940f24320a1b57eeb0c899b00fe8624` |
| 408_index_2024.json | `2b0d4366a65a966f7c9c74d751a094179b25871841dae11322d25020d6013009` | `1ae5cdc3ce0e1b1d343f87ae60704777666fb0fedf63f43e7edc70b50cea1f79` |
| 408_index_2025.json | `3cc50ae0d1e626aac69471f4abd701575f2d91b5c716543e646b3fa995ebc3d6` | `6f68e04d51ae10838627da7b5adc93b2dfed8f8347c74082f6a3611ce49d6721` |
| 408_index_2026.json | `1501ef22e97422f112e85186fc745a2e4a9627939919392716ffc83936cd7f08` | `89ff5165f79aa5577174530aadcce4f06f4bf12c0a8be6fcacd26fc22131b692` |
| eng1_index_2024.json | `3beeb569a539d6625fe9f006cce891b9b6056ec3d2ae5bc111f45b1000ede792` | 同左（未改动） |
| eng1_index_2025.json | `54736733e006497477bfdcdb1efb3b00210d03556b9ddabdd1684cdf1702a989` | 同左（未改动） |
| eng1_index_2026.json | `e74bc4cbee2077a8a9cec8358a6996e1c222c931e2a520aee14113e98b905645` | 同左（未改动） |
| math1_index_2023.json | `deb3a44c6ee7e9f85f930ae4837da0b9b815bf17a1f5956c2d61358516b53cb8` | `9c40615abde8f8011de65479d638b6f69178f33b36aeb08efed2d71764a2daa4` |
| math1_index_2024.json | `e544e6e991ae7ddd712fb11f477026329ce19303f4df7390753d1793c7f761be` | 同左（未改动） |
| math1_index_2025.json | `03140250ffbe52bbb1e5b797939ed0d5bab7dd61106d533481753203f6591e28` | `cab7ead330d5b254caae34e572f4bb7276fd564b3ab3827158fdb7a18b1919e0` |
| math1_index_2026.json | `12d091437e2c92f2920c58ed41eedd1640f5a333e5fe96a41a5b1649dc69e344` | 同左（未改动） |

**"只改了状态字段、没改权重数值"的独立证据**：改名后跑 `py -3.12 tools/apply_knowledge_weights.py --check`（干跑，不写盘），结果 `TOTAL write=0 unchanged=432`——即用改名后的脚本从 `topic_weights.json` 重新计算一遍所有字段（`knowledge_point_id`、`knowledge_point_weights`、`knowledge_point_status`），和当前磁盘上 11 个文件的内容逐字段比对，**432 条全部 unchanged**。这比逐行 diff 更强，因为它证明的不是"两个文件的文本一样"，而是"当前文件的每个字段都等于从原始证据重新推导的结果"。

## 5. `verify_408_index.py` 与 `unittest` 的实际输出

```
$ py -3.12 tools/verify_408_index.py
408_index_2023.json: OK
408_index_2024.json: OK
408_index_2025.json: OK
408_index_2026.json: OK
eng1_index_2024.json: OK
eng1_index_2025.json: OK
eng1_index_2026.json: OK
math1_index_2023.json: OK
math1_index_2024.json: OK
math1_index_2025.json: OK
math1_index_2026.json: OK

ALL INDEX FILES VERIFIED
exit: 0
```

```
$ py -3.12 -m unittest discover -s tests -q
...
FAIL: test_default_delivery_is_stopword_free_and_idempotent (test_eng1_vocabulary...)
  OperationalError: no such column: w.lemma_confidence
FAIL: test_verifier_and_deterministic_check (test_eng1_vocabulary...)
  OperationalError: no such table: stopwords
----------------------------------------------------------------------
Ran 193 tests in 37.995s
FAILED (failures=2)
```

这两个失败**都在 `tests/test_eng1_vocabulary.py`**，操作的是 `data/english_vocabulary/eng1_vocabulary.sqlite`——任务书边界明确排除的目录（"另一任务正在进行，不要碰"）。我没有改动过 `data/english_vocabulary/**` 下任何文件，错误信息也是 sqlite 表结构缺列/缺表，和本轮改的状态字段、索引文件毫无关联。单独跑本轮相关的测试：

```
$ py -3.12 -m unittest tests.test_exam_index -q
----------------------------------------------------------------------
Ran 9 tests in 1.571s
OK
exit: 0
```

**本轮改动相关的测试全绿；`test_eng1_vocabulary.py` 的 2 个失败是另一任务的未完成状态，非本轮引入。**

## 6.「我实测到了」vs「我推断」

**实测到了：**
- 11 个索引文件改名前后的 sha256（§4 表格），以及改名前 `assigned_reviewed`/`assigned_unreviewed` 计数（116/316）与《题-知识点映射...》文档 §2.4 表格的单节点/分散题数逐批次核对一致。
- 改名前对 432 条分布做过穷举扫描：`assigned_reviewed` 全部 `len(knowledge_point_weights)==1`，`assigned_unreviewed` 全部 `>1`，零反例（见 §3）。
- `verify_408_index.py` 改名后跑通 11/11、`unittest` 本轮相关 9/9、变异测试触发新规则、还原后哈希比对逐字节相等。
- `apply_knowledge_weights.py --check` 显示 `write=0 unchanged=432`，独立证明重写后的文件与"从原始证据重新计算"完全一致。
- 全仓库 grep `assigned_reviewed` 的 12 处命中逐个读过，确认改动范围。

**推断（没有跑穷举验证，是基于代码阅读和现有数据形态的判断）：**
- "未来人工复核不会自然产生 `knowledge_point_weights`"是我对"人工复核"这个假设流程的合理推测，不是已验证的事实——因为这个流程现在根本不存在，无法实测。如果将来人工复核的实现方式是"在现有分布基础上打勾确认"而不是清空重写，我加的这条规则会挡住它，需要那时候的实现者知道这个约束。
- `review/rounds/*.md` 不属于"文档同步"对象这个判断，是我从任务书边界清单（只列了 `tools/**`、`tests/**`、`data/exam_questions/**`、`docs/**`、`交接文档.md`）和"历史记录不应回填"这条通用原则推出的，没有找到本项目里明文写过"round 报告是只读历史"的规则来印证，是合理推断而非确认过的项目约定。

## 7. 没有把握的地方（至少 3 条）

1. **验证器新增的"单节点/多节点必须与状态一致"两条规则（`assigned_multi_model` 要求恰好 1 个节点、`assigned_unreviewed` 要求 >1 个节点）不是任务书直接要求的**，是我认为和"拒绝 assigned_reviewed 冒用"同一份契约里的自然延伸而加的。如果用户认为这超出了本轮授权范围，应该单独确认后再决定是否保留——我在 §3 已经说明了理由和零反例证据，但"要不要加"本身是我的判断，不是拿到明确指令后做的。
2. **"`knowledge_point_weights` 是本流程唯一写入者"这个假设**目前为真（全仓库只有 `apply_knowledge_weights.py` 一处写这个字段），但验证器的拒绝规则是建立在这个假设上的隐式契约，没有代码层面强制"只有这一个脚本能写这个字段"。如果以后出现第二个写入者（哪怕是人工复核工具经过这个字段做增量修改），这条规则的前提就悄悄不成立了，需要那时候重新审视。
3. **文档新增的「五、写回状态字段」小节**里我写了"round 18 改名为 assigned_multi_model"，但没有去检索项目里是否存在其他地方（比如某个我没搜到的笔记、聊天记录摘要）用不同措辞描述过这次改名的动机，只依据了本任务书给出的说法转写，如果任务书对动机的概括和用户实际想法有出入，文档里的措辞会跟着偏。
4.（额外一条）**`交接文档.md`"未改动"的结论**是基于 grep 关键词命中为零，但 grep 找不到不等于语义上没有相关描述——比如如果交接文档用完全不同的措辞（不含"assigned"/"knowledge_point_status"/"topic_weights"字样）描述过知识点状态流转，我不会通过关键词搜索发现。我读了交接文档里能搜到的相邻上下文（"两棵树的人工复核"§138/168/330/477 一带），确认那些讲的是知识树本身 `extracted→reviewed` 的状态机（`ky/knowledge/knowledge_point.py` 的另一套状态），和本轮的 `knowledge_point_status`（题目↔知识点映射的状态）是两个不同的字段/不同的状态机，同名词"reviewed"但指代不同东西，容易混淆但确认后不需要同步。
