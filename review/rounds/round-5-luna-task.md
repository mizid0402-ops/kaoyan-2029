# 阶段 2 开工：复习队列存储分片 + 知识点结构化契约（Luna 5.6 执行）

## 你的身份与分工

你是 **Codex / gpt-5.6-luna（high effort）**，本轮担任**主实现者**。
本项目的审查由另一个模型（Claude Opus 5）**并行**进行，你们不共享会话。

**边界（重要）**：审查者此刻可能正在编辑 `ky/models.py`、`ky/schedule/*.py`、
`tests/test_contracts.py`（它在关闭阶段 1 的遗留项）。因此：

- **你必须新建文件，不要修改上述已有文件。**
- 如果你认为必须改动它们，**在报告里写明"需要修改 X 文件，理由与最小 diff"**，由编排器统一落。
- 允许你新建：`ky/storage/**`、`ky/knowledge/**`、`tests/**`（新建测试文件）。
- **禁止**：修改 `review/**`、`docs/**`、`README.md`、`tools/**`；禁止碰 `F:\workspace\study`；不要执行 git。

本机注意：`py` 启动器**不回显子进程输出**，所有 Python 命令**必须用 `py -3.12`**。

---

## 背景（你必须先读）

1. `F:\workspace\kaoyan-ai-system\docs\阶段1交付说明.md` —— 阶段 1 交付内容与算法语义
2. `F:\workspace\kaoyan-ai-system\docs\评审结论与实施契约.md` —— 已定的契约与三条硬不变量
3. `F:\workspace\kaoyan-ai-system\review\rounds\round-4-codex.md` 的
   "`load_review_items` 扩展性评估"一节 —— 上一轮实测数据与推荐方案
4. 代码：`ky/models.py`（尤其 `load_review_items` / `ReviewItem` / `validate_items_against_config`）、
   `ky/schedule/review_clip.py`、`ky/schedule/budget.py`
5. 现有测试与 fixture：`tests/test_contracts.py`、`tests/fixtures/reviews/*.yaml`

### 已实测的扩展性问题（上一轮数据，你需要自己复现关键点）

| 条目数 | YAML 大小 | `load_review_items` 耗时 | Working Set 峰值增量 |
|---:|---:|---:|---:|
| 1,000 | 0.46 MiB | ~1.08 s | ~27.7 MiB |
| 5,000 | 2.30 MiB | ~5.76 s | ~142 MiB |
| 20,000 | 9.21 MiB | ~23.7 s | ~568 MiB |

并且：
- **写放大**：更新一条要重写整个根文件；
- **审计哈希过粗**：改一条，全文件 SHA-256 变化，其他 999 条的来源哈希一起"过期"；
- **失败爆炸半径大**：一条非法条目导致整个队列加载失败（当前是 fail-closed）。

阶段 2 预计规模：408 四科约 800–1200 考点 + 数学一约 300–400 → **1200–1600 条**。

### 已定的三条硬不变量（不得违反）

1. **唯一真相源**：本地文件为权威状态；数据库只是可删除重建的投影。
2. **AI 产物零特权**：AI 输出先进 staging，经程序校验后 apply；AI 不得直接写能力图谱、
   出现频率、任务完成状态。
3. **自评零特权**：自评不能改到期日、不能跳过复习、不能提高质量分、不能驱动能力提级。

并且：正式调度必须保持**全量 fail-closed**（部分加载会静默漏掉应复习条目，比明确失败更危险）。

---

## 任务 1：复习队列分片存储（核心交付）

在 `ky/storage/` 下新建模块，实现"**确定性有界分片 + 清单索引**"。

### 必须满足

1. **分片**：把复习队列按**确定性规则**切成有界分片（建议先按 `subject_id`，再按稳定 ID 桶或
   固定条数上限，每片约 100–500 条）。分片规则必须**确定性**：同样的输入集合永远得到同样的
   分片划分，与文件写入顺序、字典遍历顺序无关。
2. **清单（manifest）**：记录 schema 版本、分片路径、每片 SHA-256、条目数、科目/桶范围。
   清单本身也必须有哈希或版本，用作**原子提交点**。
3. **加载**：
   - 支持从清单加载全部队列；
   - **保留旧单文件格式作为兼容输入**（现有 fixture 必须继续能读，不能破坏阶段 1 的测试）；
   - 加载后做**全局** `review_id` 去重与跨分片一致性校验；
   - **全量 fail-closed**：任一分片非法即整体失败，错误必须带**精确路径**
     （要能说出是哪个分片、哪一条、哪个字段）。
4. **写入**：新增/更新/删除单条时，只重写受影响的分片 + 清单；必须是
   **写临时文件 → 校验 → 原子替换**，且中途失败不得留下半成品状态。
5. **审计粒度**：能回答"本周只变更了哪几条"——即能给出受影响分片的哈希变化集合，
   而不是"整个队列变了"。
6. **诊断通道**：提供一个**只读**的诊断命令，枚举**每一个分片**的错误而不中断，
   供修复用；但正式加载仍要求全部通过。

### 必须给出的测试（新建 `tests/test_storage.py`）

至少覆盖：

- 确定性：同一集合用不同输入顺序分片，结果完全一致；
- 往返：分片 → 清单 → 加载，得到的 `ReviewItem` 集合与单文件加载完全等价；
- 兼容：现有 `tests/fixtures/reviews/*.yaml` 仍能加载；
- 原子性：模拟写入中途失败，原分片不被破坏；
- 失败定位：某一分片注入非法条目时，错误路径能精确指出分片与条目；
- 规模：1,000 / 5,000 条的分片加载耗时与内存，并与单文件加载对比（给实测数字）；
- 写放大：更新 1 条时，实际被重写的字节数/分片数与单文件方案对比。

### 验收标准

```powershell
cd F:\workspace\kaoyan-ai-system
py -3.12 -m unittest tests.test_storage
py -3.12 -m unittest tests.test_contracts tests.test_review_scheduler tests.test_cli
```

两条都必须通过；第二条是**回归**，证明你没有破坏阶段 1（注意：审查者可能同时在改这些文件，
如果第二条失败，先判断是不是你造成的）。

---

## 任务 2：知识点结构化契约（第二个交付）

阶段 2 还要落地"资料台账 + 知识点结构化"。请为 `knowledge_point` 设计并实现契约骨架。

要求（**不要做 AI 提取逻辑，只做契约与校验**）：

- `raw → extracted → reviewed → approved → superseded` 状态机，以及**每个迁移的发起者与前置条件**；
- 每个结论必须能**回链到来源**（`path` + `sha256` + 定位信息）；
- **`frequency.value` 只能由确定性脚本写入**；契约层必须能**拒绝** AI 直接写入该字段
  （这是阶段 1 已确立的原则，见 `docs/评审结论与实施契约.md`）；
- 明确 **AI 生成题**（`source_kind: ai_generated`）与真题的边界：前者永不进入频率统计、
  考纲覆盖率、基线测验、套卷预测或最终验收，且最多产生 `validation=guided` 证据；
- 未知键必须拒绝并带精确路径（沿用 `ky/models.py` 的 `_reject_unknown_keys` 风格）。

在 `ky/knowledge/` 下新建，并写 `tests/test_knowledge_contract.py`。

---

## 报告

- 写入 `F:\workspace\kaoyan-ai-system\review\rounds\round-5-luna.md`
- 用**中文**，`## 任务1` / `## 任务2` / `## 未解决` 作二级标题。
- 必须包含**真实完整输出**（含 exit code）：
  - `py -3.12 -m unittest tests.test_storage`
  - `py -3.12 -m unittest tests.test_contracts tests.test_review_scheduler tests.test_cli`
  - 规模与写放大的实测对比表
- **"未解决"一节必须诚实**：你没能做到的、你认为是设计取舍的、你认为该由审查者或用户决定的，
  都要写清楚。不要为了显得完整而隐藏问题。
- 不要写操作确认语。
- 最后用一句话回复我：交付了哪些文件 + 两条测试命令的结果 + 1,000/5,000 条实测耗时 +
  你认为最脆弱的一处。
