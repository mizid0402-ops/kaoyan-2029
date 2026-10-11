# M31 改编题库与按档位出题（用户 2026-10-01）

> 决议来源：用户 2026-10-01（§8）。状态：sol 264 初检 FAIL（M1 函数名、M2 存储单位、M3 取题顺序、M4 非叶子、M5 无真题路径；M6 属包 C）→ 本版已改。
> 关联：M24 `contracts/check_questions.md`（真题候选）、M30 `contracts/mastery.md`（档位）、M10 `contracts/review_progress.md`（核对结果）。

## 1. 为什么

用户原话："第一天学完第三天复习，根据考研真题出一道相对简单的题，符合当前水准，等复习天数往后增加的时候再上考研原题。"
所以复习核对按掌握档位分两层：

| 复习项档位（M30 §2） | 出什么题 | 完成事件里记成 |
|---|---|---|
| `learned`（记忆天数 < 7） | **改编题**：AI 依据该知识点关联的真题改编的较简单题 | `check: exercise`、`question_ref: qb:<题号>` |
| `progressing` 及以上（≥ 7） | **真题原题**（M24 候选） | `check: past_question`、`question_ref: <真题 question_id>` |

M30 只在真题答对过时才给"已巩固"（`contracts/mastery.md` §2 第二版），改编题最多把复习项推到"掌握中"。

## 2. 决议 B10 的修订

原 B10："AI 生成题永不进频率统计 / 覆盖率 / 基线 / 套卷预测 / 最终验收；**仅在无真题覆盖时**用于巩固，最多 `validation=guided`。"
修订为（用户 2026-10-01）：改编题**在有真题覆盖时也用于"学过"档的复习核对**；其余限制全部保留——永不进频率统计、覆盖率、基线、套卷预测、最终验收；
只能得到 `validation=guided` 级证据；**不能单独让复习项到"已巩固"**。没有真题覆盖的知识点照旧可用 AI 巩固题（M24 `fallback: ai_generated_allowed`）。

## 3. 题库文件（个人数据，不进 git）

注册表新键 `state.question_bank`（本地补充注册表登记，路径在 `data/personal/` 下；`contracts/workspace.md` §2.6 的个人数据规则）。
**每道题一个文件**（sol 264 M2：同一路径只写一次与"追加新题"不能并存）：`<state.question_bank>/<knowledge_point_id>/<题号>.yaml`。

```yaml
schema_version: 1
id: qb-math1.hs.ch02.requirements.item-03-01   # = "qb-" + 知识点 ID + "-" + 两位序号；与文件名一致；全库唯一
knowledge_point_id: math1.hs.ch02.requirements.item-03
difficulty: basic                               # 目前只有 basic
basis: past_questions                           # past_questions（依据真题改编）或 syllabus（该点无真题覆盖，只依据大纲条目，§4）
based_on: [math1-2025-01]                       # basis=past_questions 时非空、且都在提交所用输入包的候选里；basis=syllabus 时为空列表
stem: "…"                                       # 题干（改编后的新题，不得照抄真题原文）
choices: ["A. …", "B. …"]                       # 可省略（非选择题）
answer: "…"
explanation: "…"                                # 可省略
validation: guided                              # 固定
created_by: ai:claude-opus-5-5                  # 同 M19 actor 规则
created_on: 2026-10-05
```

`created_on` 可写 YAML 日期或 `YYYY-MM-DD` 字符串，入库统一存为 ISO 字符串（sol 268 F2）。完成事件里改编题的 `question_ref` 写 `qb:<id>`（如 `qb:qb-math1.hs.ch02.requirements.item-03-01`），由 `ky.question_bank.question_ref()` 生成、`question_id_from_ref()` 解析（sol 268 F1）。
未知键、重复键拒绝。每个文件**只写一次**（临时文件 + 重读校验 + `os.link`，目标已存在即原子失败，同 `ky/storage/route_store.py`）；
要加题就用下一个序号写新文件，旧题永不改写。序号两位 01–99（题号正则相应放宽）；一个知识点**未停用**的题最多 9 道，已停用的题不计入、序号继续递增（sol 269 M2：否则停用满后无法补题）。

## 4. 生成流程（AI 产物零特权，§4.1 硬不变量②）

0. 可以为**任一可学节点**生成（叶子或非叶子，跟踪节点除外；sol 264 M4：粗粒度复习项挂在非叶子上）。
1. `ky planner-input --kind adapted-questions --knowledge-point <ID>`：写 `staging/inputs/adapted--<ID>--<hash12>.json`，内容是该知识点（含 §6 的祖先回退）关联真题的
   **元数据与定位**（M24 候选：题号、年份、权重、定位；题型 / 分值 / 答案字母由装配层按候选的 `question_id` 从同一次读取的登记索引补上）、知识点标题与在树中的路径、
   该点（或其后代）在大纲里的条目原文（来自知识树 `title`）。**不含真题题干原文**（索引本来就不存）。
   候选为空（M24 `fallback: ai_generated_allowed`，即该点及祖先都没有真题覆盖）时包里写 `basis: syllabus`，这是修订前 B10 原本就允许的 AI 巩固题（sol 264 M5）。
2. AI 按 `prompts/adapted_questions.md` 打开本机真题 PDF 读题，写改编题到 `staging/question_bank/<名>.yaml`（同 §3 形状，外加 `input_hash`）。
3. `ky question-bank submit --from-staging FILE [--dry-run]`：校验形状、`input_hash` 新鲜度（同 M19）、`basis` 与包一致（包有候选 → `past_questions` 且 `based_on` 非空并都在候选里；
   包无候选 → `syllabus` 且 `based_on` 为空）、知识点在生效树里且是可学节点，
   然后按 §3 写入题库；`--dry-run` 只打印。改编题不得与真题题干逐字相同（与 `based_on` 无法比较时由 AI 指引约束，校验器只查形状）。

## 5. 当天出题 `ky review-questions [--date D] [--json]`（新命令，不改既有命令输出）

对当天 M9 选中的复习项（与 `preflight` 同一选择），逐项给出：

- 档位按 M30 §2 计算；
- `learned` → 从题库取一道改编题：先找复习项所挂知识点自己的题；没有就沿 `tree_parent` 向上找**最近**有题的可学祖先。在这组题里：
  先选**从未**被完成事件 `question_ref` 引用过的、序号最小的；全部都引用过 → 选"最近一次被引用的日期"最早的（同日按序号）（sol 264 M3）；
  题库没有该点的题 → 输出"缺改编题：先生成"（不报错），并给出生成命令；
- `progressing` 及以上 → M24 真题候选（§6 祖先回退），`exclude` = 该复习项已在完成事件中作为 `question_ref` 用过的真题；
  没有可用真题 → 退回改编题；也没有 → "缺题"。
- 输出：复习项、知识点标题、档位、题目层级（`adapted` / `past_question`）、题目引用（改编题全文 / 真题年份题号与 PDF 页码）、记录时应填的 `check` 与 `question_ref`。

## 6. M24 祖先回退（数学一拆细后需要）

现有公开端口 `ky.review.check_questions.candidate_check_questions(workspace, knowledge_point_id, *, exclude=(), limit=None)` 新增关键字参数
`ancestor_fallback: bool = False`（缺省时行为与输出逐字节不变；sol 264 M1）。为 `True` 且目标知识点**自身**没有映射真题时：

1. 沿 M4 `tree_parent` 逐级向上取祖先 `A`；
2. `A` 的候选 = 映射到 `A` **或 `A` 的任一后代**的真题，每题权重 = 它映射到这些节点的权重之和；排序与 `exclude` / `limit` 规则同原端口；
3. 第一个有候选的祖先即用其候选，结果加 `matched_ancestor: <A 的 ID>`；到根仍无 → 原 `fallback` 规则。

为什么要"并入后代"：数学一真题挂在 `…ch02.content` 小节上，而拆细后的叶子在 `…ch02.requirements.item-NN` 下，两者只在章节点 `…ch02.chapter` 汇合
（`tree_parent` 的语法规则把 `.content` / `.requirements` 挂到 `.chapter`）。只看祖先自身的映射找不到题。

## 6a. 标记坏题（用户 2026-10-01 选补缺口）

做题时发现改编题有问题（答案错、超纲、与该知识点无关、太难），可以停用它：

```
py -3.12 -m ky question-bank retire --question <题号> --reason "<原因>" --date D [--dry-run]
```

- 题目文件只写一次，所以停用另写一个只写一次的文件 `<state.question_bank>/<knowledge_point_id>/<题号>.retired.yaml`：
  `{schema_version: 1, id: <题号>, reason: <非空字符串>, retired_on: <ISO 日期>}`；已停用再停用 → 违约（"已停用"）。题号不存在 → 违约。
- 取题（§5）跳过已停用的题；一个知识点（含向上查找到的那组）的题**全部停用**时，按"缺改编题：先生成"处理，并在输出里注明"该点改编题已全部停用"。
- `ky review-questions` 的文本输出每道改编题后提示一行"有问题可停用：py -3.12 -m ky question-bank retire --question <题号> --reason "替换为原因" --date <当天>"
  （日期填 `--date` 的值，整行可直接复制运行；sol 272。原因占位符**必须带引号**，否则 PowerShell 把 `<原因>` 当重定向运算符、整行无法解析；sol 282 M2）。
- 停用的题仍保留（历史完成事件引用它时可查），不删除；生成新题用下一个序号。

## 7. 存储与登记

- `state.question_bank` 未登记 → `review-questions` 对 `learned` 项输出"未登记题库"，`question-bank submit` 违约退出 2。
- 新模块 `ky/question_bank/`（读写、校验、取题）；`docs/模块地图.md` 登记 **M31**。

## 8. 决议记录（用户 2026-10-01）

| 问题 | 选择 |
|---|---|
| B10 | 改：早期用改编题；只有真题答对才算已巩固（§2） |
| 切换时机 | 记忆稳定度 ≥ 7 天（"掌握中"）起用真题原题 |
| 改编题来源 | 每个知识点预先生成 2–3 道，存本地题库 |

## 9. 决策者自拟、待 sol 初检的细则

§3 每题一文件、只写一次；§4 任一可学节点可生成、无真题时 `basis: syllabus`；§5 取题顺序（先未用、再最久未用）与题库向上查找；§6 章级回退把后代映射的题并入章候选。
sol 264 留给最终大检查：祖先候选全被 `exclude` 后是否继续上溯、聚合权重双来源优先级、粗粒度真题答对对后代的继承口径。
