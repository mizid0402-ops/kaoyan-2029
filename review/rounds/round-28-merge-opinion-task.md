# 咨询：408 两棵知识树合并时的 `weight` / `source_count` 语义问题

## 背景事实（都已实测，可复核）

项目有两棵 408 知识树：

| | `knowledge_tree.yaml`（单源基线） | `knowledge_tree_weighted.yaml`（加权，双源） |
|---|---|---|
| 节点数 | 403 | **410**（严格超集：403 共有 + 7 个 2022 独有）|
| 每节点 `sources` | **记录列表** `{path, sha256, locator{section,offset,quote_ref}}` | **标签列表** `["A","B"]` |
| 逐节点 `path`/`sha256`/`locator` | **403/403** | **0/410** |
| `weight` | 无 | 有（`1.0: 318` / `0.75: 77` / `0.5: 15`）|
| `source_count` | 无 | 有（`2: 380` / `1: 30`）|
| `evidence_tag` | 无 | 有（`dual_source_exact` 315 / `structural_equivalent` 65 / `candidate_recent_new` 7 / `legacy_only_pending` 7 / `single_source_unverified` 8 / `text_layer_ocr_risk` 8）|
| 能否被 `tools/verify_tree.py` 验 | **能**（它要求逐节点 `sources[i].path`/`sha256`/`locator.quote_ref`）| **不能** |

**加权树的信息全在文档级 `sources_registry`**，而且里面两个源指向**临时目录**：

```
A: data/raw_materials/cs408/syllabus/archive408_408_outline_2026.html   ← 项目内
B: C:/Users/.../Temp/kaoyan-probe/ghsurvey/downloads/408_syllabus_2022.pdf   ← 临时目录
C: C:/Users/.../Temp/kaoyan-probe/ghsurvey/downloads/408q_full.json          ← 临时目录
```

**源 C（第三方题库）实测 `knowledgePointIds` 全为 null（799 题 0 个非空）**，所以它对树**没有提供知识点支持**，只是被登记过。
**因此 408 的加权实际是"两源加权"（A 2026 + B 2022），不是三源。**

## 计划做的合并

把加权树补成"既有验证能力、又有权重"的那一棵：

1. 每节点 `sources` 从 `["A","B"]` **改成记录列表**（path + sha256 + locator + quote_ref），
   A 侧从基线树继承，B 侧补上
2. 把 2022 PDF（与源 C JSON）**移进项目**，注册表路径改成项目内
3. 合并完成并**通过 `verify_tree.py`** 之后，再决定是否退休基线树

**已确认`weight` 不与 `sources` 共用槽位**（`weight` 是独立顶层 float，`sources` 里没有 `weight`），
所以**字段本身不会被覆盖**。

## 待决问题（这就是要问你们的）

补 `sources` 记录后，`source_count` 与 `weight` **要不要跟着变？**

### 方案 A：保持冻结
- `weight` 继续表示**"有几个来源独立支持这个节点"**；补进 `sources` 的只是**定位信息**，不算新增支持
- 后果：`source_count` 会与 `len(sources)` **不等**，需要给 `verify_tree.py` 加显式例外
- 支持理由：`sources` 里加一条只说明"2022 在那个位置提到了它"，**不等于"2022 独立支持它"**——
  例如 `legacy_only_pending` 那些节点，2022 的对应本来就只是"宽泛节标题"

### 方案 B：重算
- `sources` 里出现的都算支持，`source_count = len(sources)`，`weight` 按新源数重算
- 后果：字段自洽，但**会把"仅 2022 有"的节点权重抬高**，抹掉分歧信息

### 方案 C：拆成两个字段
- 新增 `source_supports`（**支持**该节点的源）与 `sources`（**提到过**该节点的源）分开
- 后果：概念不打架、不用给验证器开例外，但 schema 更复杂、下游要处理两个字段

## 请回答

1. **你选哪个方案？** 给理由
2. **如果不选我倾向的 A**，说明 A 的哪个前提你认为错了
3. **有没有我没列到的第四种做法？** 如果有，具体是什么
4. **这个 schema 决定会怎样影响下游**？（下游会用到：复习调度按 `weight` 降权、
   Web 投影展示来源、将来加新源时的合并）
5. **反过来说：有没有可能根本不需要合并两棵树？** 比如只保留加权树 + 另写一份可复核的
   "溯源对照表"，而不是把溯源塞进同一棵树

## 重要约束（判断时请守住）

- **这一轮的目的不是"让验证器通过"**，而是**让数据的语义正确**。
  **不要为了通过验证而放宽验证**——如果必须开例外，要能说清这个例外为什么是对的。
- **加权树的权重是"来源支持度"的度量，不是"正确性"**。树里已写明：
  `本树为多源加权基线，非人工核准；权重反映来源支持度，不反映正确性。`
- 所有节点 `status=extracted`（`approved` 要求 `actor=human`，本流程无权产生）。

## 输出

写入文件后回复。**不要修改任何文件**，只给意见：

- Claude：`%TEMP%\kaoyan-probe\opinion-merge-claude.md`
- Codex：`%TEMP%\kaoyan-probe\opinion-merge-codex.md`

**不要去看对方的产出**——独立作答，两边结论若不一致本身就是有价值的信息。

报告里请包含：
1. 你的选择与理由
2. 对另外两个方案的反驳（说清它们错在哪）
3. 你没把握的地方
4. 「我实测到了」vs「我推断」（你看到的都是二手描述，除文件外未实测，请如实标明）
