# 任务：把加权知识点映射写回索引（schema 扩展 B 方案）

## 背景

项目已用**三模型独立编码 + 置信度加权**算出每道题的知识点**权重分布**（不再强行单一归类）。
副产品：`data/review_weights/topic_weights.json`，其中 `per_question` 是每题的分布。
编码者原始产出：`data/review_weights/coder_outputs/`（66 份）。

现在要把这个分布**写回** `data/exam_questions/*.json`。

## 用户已拍板的选择：**方案 B（新增字段）**

不要只把占比重最大的节点塞进现有单值字段——那会丢掉跨考点信息，而**保留分布正是这次映射的意义**。
所以：

- 保留 `knowledge_point_id`（存 **argmax**，让既有消费方不破）
- **新增** `knowledge_point_weights`：`{节点id: 权重}`，权重之和 = 1.0
- `knowledge_point_status`：三方一致 → `assigned_reviewed`；权重分散/分歧 → `assigned_unreviewed`

## 我已经改过一半，**必须先接手核对我改的对不对**

我（DSH）已在 `tools/verify_408_index.py` 里做了两处修改：

1. `ENTRY_KEYS` 增加了 `"knowledge_point_weights"`（约在文件 48–58 行）
2. 在 `knowledge_point_id` 校验之后，新增了 `knowledge_point_weights` 的校验块
   （对象类型、非空、节点 id 合法、权重为正、**权重和 = 1.0（容差 1e-6）**、
   **`knowledge_point_id` 必须是 `knowledge_point_weights` 的 argmax**、
   有 weights 就不许 `knowledge_point_id` 为 null）

**请先读这两处，判断我写得对不对**（尤其是容差与 argmax 一致性这两条是否过严/过松），
**不要默认我是对的**。有异议就改，并在报告里说明理由。

## 你要做的

### 1. 核对并补全验证器

- 复核我改的两处
- 检查是否有**其他地方**需要同步（例如按年份参数化的形状校验、`ky/exam/paper_shape.py` 的交互）
- **写变异测试**证明新校验真的会红：
  至少覆盖「权重和 != 1.0」「argmax 与 knowledge_point_id 不符」
  「有 weights 但 knowledge_point_id 为 null」三类。
  给出变异前后文件哈希，证明已还原。

### 2. 写回脚本

新建 `tools/apply_knowledge_weights.py`：

- 输入：`data/review_weights/topic_weights.json` 的 `per_question`（键形如 `cs408-2024-43`）
- 逐个索引文件 `data/exam_questions/{subj}_index_{year}.json` 写入
- **要求**：
  - 只用 `topic_weights.json` 里已有的分布，**不得自己重算或补值**
  - 某题在 `per_question` 里缺失 → **不要动它**，保持 `null`/`not_assigned`，并在报告里列出
  - 权重和必须在 1.0（容差内）；不满足就**拒绝写入并报错**，不要悄悄归一化
  - 写入是**幂等**的：重复运行结果相同
  - 用 `--check` 支持干跑
- 写完后 `tools/verify_408_index.py` 必须对**全部 11 个索引**通过

### 3. 更新测试

- `tests/` 下增加或扩展对 `knowledge_point_weights` 的回归锁
- 现有 `188 tests` 不得变红；`py -3.12 -m unittest discover -s tests -q` 必须全绿

### 4. 交付报告

写入 `F:\workspace\kaoyan-ai-system\review\rounds\round-15-apply-weights-claude.md`：

1. 你对我那两处改动的复核结论（同意/不同意 + 理由）
2. `apply_knowledge_weights.py` 做了什么、幂等性如何验证的
3. 写回结果统计：每年每科写入了多少条、多少条是单一节点、多少条是分布、多少条缺失未动
4. 变异测试结果 + 还原哈希
5. 测试与验证器的实际输出
6. 「我实测到了」vs「我推断」
7. 没有把握的地方至少 3 条

## 纪律

- 允许修改：`tools/**`、`tests/**`、`data/exam_questions/**`、`ky/**`
- **禁止**修改：`data/review_weights/coder_outputs/**`（那是原始证据，不可改）、
  `data/structured_materials/**`（知识树）、`data/materials.yaml`
- 不要执行 git
- 本机 `py` 启动器不回显输出，**必须用 `py -3.12`**
- 终端吞中文：结果写 UTF-8 文件再用 read 工具读
- **索引只含元信息，绝不写入题干/选项/解析原文**

最后用一句话回复：验证器改动是否认可 + 写回条数 + unittest 结果 + verify 结果 + 报告路径。
