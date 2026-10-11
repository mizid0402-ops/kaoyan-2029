# Round 56 任务书：M24 核对出题（新模块，决议 D9 / B10）

你是实现者，在独立 worktree（分支 `stage25/m24`，基于 master `aa78883`）。先读仓库根 `AGENTS.md`（D7：新组件 = 新模块 = 规格 + 实现 + 契约测试 + 模块地图一行）
与 `docs/阶段2.5-接缝收口.md` §七 D9。**只新建文件**，唯一例外是 `docs/模块地图.md` 加一行 M24、`ky/review/__init__.py`。

## 职责

回答："要核对知识点 X 掌握没有，拿哪道题来考？"——宽松档下用户自评"会"时，由上层调用它出题（接入由另一个工作包做，本轮不接）。

## 要做的

1. **规格 `contracts/check_questions.md`**：
   - 输入：工作区注册表（`reference.exam_indexes.*` 与 `reference.topic_weights`）、知识点 ID、可选的"已做过的题"集合、可选数量上限。
   - 输出：候选题列表，每项 `question_id`、`subject_id`、`exam_year`、`number`、`weight`（该题映射到此知识点的权重）、`locator`（卷面页等，照索引原样）、`source: past_question`。
   - 选题规则（确定性）：只取映射到该知识点（`knowledge_point_weights` 含它，或 `knowledge_point_id` 等于它）的真题；排序 = 权重降序 → 年份降序 → 题号升序；排除"已做过的题"。
   - **没有真题时**：返回空列表并给出 `fallback: ai_generated_allowed`，说明按决策 B10：AI 生成的巩固题允许用于这种情况，但只能产生 `validation=guided` 级证据、永不进频率统计。本模块**不生成题目**。
   - 只读，不写任何文件；不含题目原文（只给定位，引用规范见 `QUOTATION_POLICY.md` 的约束精神）。
2. **实现 `ky/review/check_questions.py`**：纯读函数 `candidate_check_questions(workspace, knowledge_point_id, *, exclude=(), limit=None)`（**不要**用 `suggest_` / `recommend_` / `default_` 前缀，项目有测试禁止这类名字）。
   经 `workspace.require_all("reference.exam_indexes.<科目>")` 读索引；知识点 ID 的科目按科目档案判断（ID 第一段）。模块头按 D7 写明 M24 与规格。
3. **契约测试 `tests/contract/test_check_questions_port.py`**：临时工作区 + 最小索引：排序规则、排除已做、limit、无真题 → 空 + fallback、索引缺失 → `ContractError`；
   再用仓库注册表对一个在索引里出现过的知识点（从索引里**推导**出来，不写字面量）断言非空且排序正确。
4. `docs/模块地图.md`：加 M24 一行（职责、规格、实现、读哪些注册表键、可替换性 A、验收命令）。

## 验收

在本 worktree：`py -3.12 -m unittest tests.contract.test_check_questions_port`。全量不跑。无 `???`。报告 `review/rounds/round-56-m24-luna.md`（`apply_patch`）。不提交。
