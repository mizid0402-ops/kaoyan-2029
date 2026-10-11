# 断链复核：DSH 关条件改动的确认 + 一个扩展性问题（Codex 执行）

## 背景

你在 `round-3-final3-codex.md` 给出的裁决是**有条件通过**，条件是修正验收文本里那条被证伪的
全称断言（"对任意合法比例与预算，精确值与旧浮点值差异 ≤ 1"），并让测试按修正后的契约断言。
你同时明确：问题在验收要求、不在实现，**不应回退到旧 float 乘法**，并接受了 DSH 保留精确实现的决定。

DSH 已按你的替代方案关闭该条件，改动落在 4 个文件上。**这些改动之后没有再经审查方确认，
所以之前那份 PASS 上挂着一个断链。本轮就是补上它。**

## DSH 的改动清单（请逐项核实，不要只跑测试）

| 文件 | 改动 |
|---|---|
| `tests/test_contracts.py` | ① 把 `test_repeating_decimal_never_exceeds_the_true_product` 替换为 `test_exact_contract_holds_for_repeating_decimals`：断言基准从**旧 float 乘积**改为**精确有理乘积** `floor(total × Fraction(str(ratio)))`，并同时断言 `exact ≤ 真实乘积 < exact+1`、`0 ≤ exact ≤ total`。② 新增 `test_exact_contract_holds_across_a_cross_product`：15 个比例 × 12 个预算的交叉积，全部对照精确有理乘积断言。③ 收窄 `test_the_projects_own_ratios_are_unaffected` 的 docstring——它原先泛称"每个合理预算都一致"，现在明确只承诺 `0.45`/`0.60` 且 `total=1..20000`。 |
| `ky/models.py` | 改写 `_scale_minutes` 的 docstring。原文声称"日常预算下与 float 乘积逐位相同"，已被 `1/53` 反例推翻。新表述写明：① 这是契约 `floor(total × ratio)` 的冻结解读；② 大预算下 float 乘法会 `OverflowError`；③ 对不终止小数的比例两者**不等价**，并给出 `1/53` 的具体数字；④ 明确警告"不要改回 `int(total_minutes * ratio)`"。 |
| `ky/schedule/budget.py` | 把 `assert 0 <= leftover < len(weights)` 改为显式 `raise RuntimeError(...)`（你指出 assert 在 `python -O` 下会消失）。 |
| `tests/test_contracts.py` | `test_the_projects_own_ratios_are_unaffected` 保留原断言（`0.45`/`0.60`，`total=1..20000`）。 |

DSH 实测（改动后）：`Ran 88 tests ... OK`、`tools/verify_round3_findings.py 13/13`、
preflight 正常/满载/违规分别 exit 0 / 0 / 2。

---

## 你的任务

### 1. 核实条件是否真的关闭

- 读上述 4 处改动，确认它们**确实**实现了你提出的替代方案，而不是绕过。
- 特别核实：`test_the_projects_own_ratios_are_unaffected` 的 docstring 现在是否**与断言一致**
  （原来它声称的范围大于断言范围）。
- 确认**没有任何测试再把旧 float 乘积当权威**。
- 确认 `_scale_minutes` 的新 docstring **不含**已被证伪的表述。
- 跑规定检查并给出真实输出：
  ```powershell
  cd F:\workspace\kaoyan-ai-system
  py -3.12 -m unittest tests.test_contracts tests.test_review_scheduler tests.test_cli
  py -3.12 tools/verify_round3_findings.py
  ```
  （本机 `py` 启动器不回显输出，**必须用 `py -3.12`**。）

### 2. 变异测试（确认新测试不是空真）

- 把 `_scale_minutes` 改回 `int(total_minutes * ratio)`，确认**新测试会红**；
- 把 `_scale_minutes` 改成 `ceil` 而非 `floor`，确认**新测试会红**；
- 把你上一轮指出的 `leftover` 不变量检查删掉或放宽，确认是否有测试能杀死该变异
  （**如果没有，明说"该防御无测试保护"**）。
- 每次变异**必须还原**并给出回归后的 SHA-256。

### 3. 一个**新的**扩展性问题（本轮的重点，请给明确结论）

阶段 2 要落地"资料台账 + 知识点结构化 + 复习队列"，题目会从现在的 24 条手写 fixture
增长到**上千条量级**（408 四科约 800–1200 个考点 + 数学一约 300–400 个）。

请评估：**`ky/models.py::load_review_items` 要求整个复习队列放在一个根文件里的设计，
在真实规模下是否会成为瓶颈？**

需要覆盖（用你自己的判断和探针，不要只复述问题）：

- **写放大**：每次新增/更新一个 `ReviewItem` 是否都要重写整个文件？这对每周/每日的
  受控生成流程意味着什么？
- **解析与校验成本**：1000 / 5000 / 20000 条时，`load_review_items` 的耗时与内存量级。
  给出实测数字。
- **审计与哈希**：项目现有哲学是"每个结论回链到 `path + sha256`"。单文件大队列
  是否会让"冻结来源哈希"变得过粗（改一条就全文件哈希变化）？这对周证据闭环意味着什么？
- **失败模式**：一个文件里有一条非法条目时，是整个队列加载失败还是部分可用？
  这在实际使用中是好还是坏？
- **替代方案**：如果需要改，你会建议什么形态（按科目分文件 / 一条一文件 / 分片 +
  索引 / 保持单文件但加缓存）？各自代价是什么？

**结论请明确给出：可以保持现状 / 应该在阶段 2 之前改 / 应该在阶段 3 再改**，并说明依据。
如果认为可以保持现状，请说明在什么规模、什么条件下会失效。

### 4. 裁决

- 断链是否已补上：`是 / 否`。
- 扩展性问题的结论。
- 如发现问题，给出 `位置(文件:行)` / `触发条件` / `最小复现` / `实际输出` / `期望` / `修法`。

---

## 约束

- 用**中文**。输出到 `F:\workspace\kaoyan-ai-system\review\rounds\round-4-codex.md`
- 只写这一个文件：不得修改 `ky/**`、`tests/**`、`tools/**`、`docs/**`、`review/**` 里的其他文件。
  变异改坏的代码**必须还原**并给哈希。
- 不要执行 git。不要操作确认语。
- 最后用一句话回复：断链裁决 + 扩展性结论 + 文件路径 + 哈希。
