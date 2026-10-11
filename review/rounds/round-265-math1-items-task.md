# 第 265 轮任务书：包 C 数学一"考试要求"拆到条目（gpt-6-luna，luna-b 新会话）

## 先读

`AGENTS.md`；`交接文档.md` §4.2（AI 不得凭自己知道的补节点，只能"大纲原文 → 节点"；允许修正明显排版断裂但**必须标注**）、§4.3、§6.3（知识点契约约束：节点没有 `notes` 字段、`extracted → reviewed` 只允许人）；
`contracts/knowledge_tree.md`；`data/structured_materials/math1/knowledge_tree.yaml` 文件头与 `knowledge_tree_report.md`；`ky/knowledge/tree_grammar.py`（`named_chapters`）；`tools/verify_tree.py`；
sol 第 264 轮初检 `review/rounds/round-264-abc-spec-review-sol61.md`（若有"必须改"，决策者已改进本任务书，以本任务书为准）；
sol 第 256 / 258 轮报告（`review/rounds/round-256-math1-syllabus-sol61.md`、`round-258-math1-syllabus-years-sol61.md`：哪些差异是转录错字）。

## 工作区与并行

主仓库 `F:\workspace\kaoyan-ai-system`，master 当前提交之上。另外两个窗口同时在做：luna-a（`ky/review/`、`ky/question_bank/`、`ky/__main__.py`、`ky/workspace.py`）、
luna-c（`ky/mastery/`、`ky/charts/`、`ky/schedule/planning.py`、`ky/pacing/`）。**只改下面列出的文件**；不改 README、`docs/模块地图.md`（决策者统一改）。

## 要做的

1. `data/structured_materials/math1/knowledge_tree.yaml`：22 章各自的 `…chNN.requirements` 下，按"考试要求"的**编号条目**逐条加节点：
   - ID `<章前缀>.requirements.item-NN`（两位序号，按原文顺序），`scope: item`，`status: extracted`，`source_kind` 同现有节点，`transition_history` 照现有 extracted 节点的写法；
   - `title` = 该条原文（空白归一；公式按转录文本原样，不自行改写）；
   - `sources` 列出能定位该条的转录（现有两份：eol 2022、newdu 2026），每源写自己的 `locator.quote_ref`（在该源中空白归一后可定位的原文），`sha256` = 本地文件哈希；
   - 两源措辞不同时分三类（sol 264 M6）：
     ① 第 256 / 258 轮报告**确认的转录错字**（如 2026 版"柑合性"、"伯努"缺字）→ `title` 用正确写法，report 逐条标注"修正：2026 转录 X → Y，依据 2022 转录与第 25x 轮报告"；
     ② 报告**确认的考试要求变更**（如 2025 起概率第 1 章第 3 条加"的方法"）→ `title` 保留新版（2026）写法；
     ③ 其他不能确认的差异 → `title` 保留 2026 版写法，report 记录，**不择一改写**；
     三类都是两源各写各的 `quote_ref`（各自在本源中可定位的原文）；
   - 一条在某源里找不到（转录缺漏）→ 该源不列入这条的 `sources`，report 记录；两源都找不到 → 不建这条，report 记录。
   - "考试内容"小节不拆；`requirements` 小节保留为父节点；不增删其他节点。
2. 树文件头的结构说明（`structure`、粒度段落）与 `knowledge_tree_report.md` 同步：新增节点数、每章条目数、修正与差异清单。
3. `ky/knowledge/tree_grammar.py` 的 `named_chapters` 接受 `…requirements.item-NN`（`scope: item`，父必须是存在的 `requirements` 小节）；
   `tools/verify_tree.py` 的结构统计与检查随之接受；不放宽其他语法的规则。
4. `tests/test_data_manifest.py` 里钉住的数学一节点数按 AGENTS 第 7 条更新（报告列旧值 → 新值）；`tests/test_verify_tree_shapes.py` 若有数学一形状断言同步。

## 不做的

不改真题索引、`data/review_weights/` 下任何文件、考频权重、`syllabus_versions`（同一版大纲的细化，不是换版；复习队列为空无需迁移）；不推进任何节点状态；不读 `data/personal/`；
报告与日志里只写短的定位串，不整段贴大纲原文以外的东西（大纲条目本身就是节点 title，可以出现在树文件里）。

## 测试（只写这些）

- `tests/contract/test_knowledge_tree_port.py`：`named_chapters` 接受 `requirements.item-NN`；拒绝父小节不存在的条目、拒绝挂在 `content` 下的条目。
- 用真实数学一树跑：`learnable_tree(points, "named_chapters")` 的叶子 = 22 个 `content` 小节 + 全部条目；每个 `requirements` 小节都有 ≥1 条目。

## 验收（只跑这些）

```
py -3.12 tools/verify_tree.py data/structured_materials/math1/knowledge_tree.yaml --workspace kaoyan.workspace.yaml
py -3.12 tools/aggregate_topic_weights.py --check
py -3.12 -m unittest tests.contract.test_knowledge_tree_port tests.test_data_manifest tests.test_verify_tree_shapes tests.test_tree_integrity tests.contract.test_topic_weights_port
```

报告 `review/rounds/round-265-math1-items-luna.md`：改动、每章条目数、修正与差异清单摘要、测试输出原文、"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。
不提交；树文件与 report 含中文，只用 `apply_patch` 编辑或写成 UTF-8 `.py` 生成；写完 `rg -n '\?\?\?'` 检查；**保持 LF 换行**。
