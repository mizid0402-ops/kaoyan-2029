# 任务：把「三模型一致」的状态名改掉，避免字段名与含义不符

## 为什么改（用户已拍板）

你在 round 15 里做了一件对的事：发现验证器原有的「未校准前禁止知识点」闸门会 100% 拒绝写回，
把它改成只挡「无证据的裸 id」，并主动把这一步列为「最需要用户确认的一条」——**这个做法是对的**。

用户确认的结论是：**改法可以，但字段名要换。**

原因：`knowledge_point_status` 的取值 `assigned_reviewed` 里，`reviewed` 原本指**人工对照官方答案书复核过**。
现在按新规则，它表示**三个 AI 模型独立给出同一节点**。**两者含义不同，字段名在撒谎**：

| | 旧含义 | 新含义 |
|---|---|---|
| 谁核的 | 人 | 三个 AI |
| 依据 | 官方答案书 | 三模型独立一致 |

本项目一贯坚持「把证据等级说清楚、不含糊」（如 `trusted_reprint` vs `official`、
「推断」与「实测」分开标），字段名骗人是同类问题，所以要改。

## 你要做的

### 1. 新增状态值 `assigned_multi_model`

`knowledge_point_status` 的取值集合改为：

- `not_assigned` —— 未赋知识点
- `assigned_multi_model` —— **三模型独立给出同一节点**（单节点分布）
- `assigned_unreviewed` —— 权重分散/存在分歧（分布形式）
- `assigned_reviewed` —— **保留，但不再由本流程写入**。
  它的语义**只留给将来的人工复核**：即有人对照官方答案书或源转录逐条核过。
  **不要在文档里把它重新定义成"三模型一致"。**

### 2. 改代码

- `tools/verify_408_index.py` 的 `ENUMS`：`knowledge_point_status` 增加 `assigned_multi_model`
- `tools/apply_knowledge_weights.py`：单节点分布的题写 `assigned_multi_model`
  （原来写的是 `assigned_reviewed`）
- 检查是否还有其他地方引用 `assigned_reviewed`（用 Grep 搜遍 `ky/`、`tools/`、`tests/`、`docs/`），
  逐个判断该改成 `assigned_multi_model` 还是保持

### 3. 重写 11 个索引文件的状态字段

按新规则重新写回 `data/exam_questions/*.json`：
- 单节点分布 → `assigned_multi_model`
- 分布形式 → `assigned_unreviewed`

**只改状态字段与必要的字段名，不改权重数值**（权重已由 round 15 写好并验证过）。

### 4. 文档同步

- 更新 `docs/题-知识点映射-多模型交叉验证方法.md`：
  写明两个状态的确切含义，并**明确 `assigned_reviewed` 现在专指人工复核**（暂无人使用）
- 如果 `交接文档.md` 里有提到知识点状态，一并同步

### 5. 验证

- `py -3.12 tools/verify_408_index.py` —— 11 个索引全过
- `py -3.12 -m unittest discover -s tests -q` —— 全绿
- **变异测试**：把某题的 `assigned_multi_model` 改成 `assigned_reviewed`，
  验证器是否应该报错？请你判断并说明——
  **如果 `assigned_reviewed` 现在专指人工复核、而本流程无权产生它，那验证器就应该拒绝本流程写入它。**
  这是一条值得加的校验，请你判断后实现并给变异证据。
- 给出改名前后的文件哈希

## 报告

写入 `F:\workspace\kaoyan-ai-system\review\rounds\round-18-rename-status-claude.md`：

1. 你改动了哪些文件、每处改动的理由
2. 你如何判断「其他地方该不该跟着改」
3. 关于「验证器是否该拒绝本流程写入 assigned_reviewed」的判断与实现
4. 变异测试结果 + 还原哈希
5. `verify_408_index.py` 与 `unittest` 的实际输出
6. 「我实测到了」vs「我推断」
7. 没有把握的地方至少 3 条

## 纪律

- 可改：`tools/**`、`tests/**`、`data/exam_questions/**`、`docs/**`、`交接文档.md`
- **禁止**改：`data/review_weights/coder_outputs/**`（原始证据）、
  `data/structured_materials/**`（知识树）、`data/materials.yaml`、
  `data/english_vocabulary/**`（另一任务正在进行）
- 不要执行 git
- 本机 **没有 `rg`**，用 Grep 工具或 `Get-ChildItem -Recurse`
- 必须用 `py -3.12`；终端吞中文，结果写 UTF-8 文件再读
- 索引只含元信息，绝不写入题干/选项/解析原文

最后用一句话回复：改了哪些文件 + 11 个索引状态分布 + 验证器是否新增了拒绝规则 + unittest 结果 + 报告路径。
