# 第五轮：跨模型审查（Opus 5 执行）——阶段 1 收敛 + 断链闭合

## 你的身份

你是 **Claude Opus 5（high effort）**，本轮担任**独立高级审查者**。
这台机器上此前的审查由另一个模型（Codex / gpt-5.6-sol）完成，你与它没有共享会话。
你的任务不是复述它的结论，而是**独立判断它是否正确**，并把它做对的部分和它可能做错的部分都指出来。

## 背景

项目：`F:\workspace\kaoyan-ai-system` —— 计算机考研（2029 届，数学一 + 英语一 + 408）的
本地学习系统。当前处于**阶段 1**，已交付"考试配置合同 + 复习容量裁剪核"，在 `ky/` 下，
约 55 KB Python，测试在 `tests/`。

阶段 1 的验收门槛是三条：**合同自洽、算法确定、不超预算**。

## 你必须先读的材料（按顺序）

1. `F:\workspace\kaoyan-ai-system\review\rounds\round-4-codex.md` —— 上一轮（另一个模型）的断链复核，
   裁决 **FAIL**，给出 3 条"最小修法"。
2. `F:\workspace\kaoyan-ai-system\docs\阶段1交付说明.md`
3. `F:\workspace\kaoyan-ai-system\review\rounds\round-3-final3-codex.md` —— 更早一轮的语义裁定
4. 代码：`ky/models.py`、`ky/schedule/budget.py`、`ky/schedule/review_clip.py`、`ky/__main__.py`
5. 测试：`tests/test_contracts.py`、`tests/test_review_scheduler.py`、`tests/test_cli.py`
6. `tools/verify_round3_findings.py`（**审查方工具，不得修改**）

**本机注意**：`py` 启动器**不回显子进程输出**，所有 Python 命令**必须用 `py -3.12`**。

---

## 任务 A：独立复核上一轮的三条"最小修法"

上一轮报告要求：

1. 删除 `test_matches_the_float_product_across_the_everyday_range` 与
   `test_matches_the_float_product_at_realistic_daily_budgets`，或把它们改为精确有理契约测试，
   因为**不能再让 float 差异本身导致失败**；它声称获准的旧行为兼容范围只有
   `ratio ∈ {0.45, 0.60}` 且 `total = 1..20000`。
2. `test_the_projects_own_ratios_are_unaffected` 的 docstring 必须明写范围。
3. `_scale_minutes` 的 docstring 里"项目比例与 float 一致"的表述必须限定到已验证范围或删除；
   它给出的反例是 `total = 9007199254740993`（即 `2**53 + 1`）。

**你要做的是判断这三条是否成立、是否完整、是否过度。**

- 逐条核实它的技术主张（自己去跑、去算，不要采信）。
- **特别核实它给的反例**：`total = 2**53 + 1`、`ratio ∈ {0.45, 0.60}` 时，
  精确实现与 `int(total * ratio)` 是否真的不同？给出你实测的数字。
- 判断：把"与旧 float 一致"的测试范围**收窄**是正确做法，还是应该**彻底删掉**这类测试？
  给出你的理由。注意契约本身写的是 `floor(total × ratio)`，而 `float` 乘法不是这个契约的定义。
- 如果它漏了什么，补上；如果它说错了，明确反驳并给依据。

## 任务 B：执行修复（你有编辑权）

按你复核后的结论**直接修改**（不要只写建议）：

- 允许修改：`F:\workspace\kaoyan-ai-system\ky\**`、`F:\workspace\kaoyan-ai-system\tests\**`
- **禁止修改**：`review/**`、`docs/**`、`README.md`、`tools/verify_round3_findings.py`，
  以及 `F:\workspace\study` 下的任何文件。不要执行 git。

修复后必须给出**真实完整输出**：

```powershell
cd F:\workspace\kaoyan-ai-system
py -3.12 -m unittest tests.test_contracts tests.test_review_scheduler tests.test_cli
py -3.12 tools/verify_round3_findings.py
```

## 任务 C：你独立判断阶段 1 是否达到验收门槛

**不要因为上一轮判了 FAIL 就跟着判 FAIL，也不要因为它之前的 PASS 就跟着判 PASS。**

给出一份你自己的缺陷清单。要求：

- 逐条给 `位置(文件:行)` / `触发条件` / `最小复现` / `实际输出` / `期望` / `修法`。
- 明确分级：`BLOCKER` / `MAJOR` / `MINOR` / `不阻塞的已知限制`。
- **必须做变异测试**：至少对下列实现故意改坏，确认对应测试会不会变红（改完必须还原并给哈希）：
  1. `review_clip.py` 的 `_is_urgent` 恒返回 `False`；
  2. `review_clip.py` 的 `_deficit_ratio` 恒返回 `0.0`；
  3. `models.py` 的 `_scale_minutes` 改成 `ceil`；
  4. `budget.py` 删掉 `leftover` 不变量的 `RuntimeError`。
  对**不会变红**的，明说"该行为无测试保护"。
- 最后给出裁决：`通过 / 有条件通过（条件：…） / 不通过`，并单独列出**仍存在但不应阻塞**的限制。

## 任务 D：回答一个设计问题（阶段 2 的接口）

阶段 2 要把复习队列从现在的 24 条 fixture 扩展到**上千条**。
`load_review_items` 目前要求整个队列在一个根文件里。

上一轮给出的结论是"**应在阶段 2 之前改为确定性有界分片 + 清单索引**"，理由是写放大、
审计哈希粒度过粗（改一条导致全文件哈希变化）、单条坏数据阻断全队列。

**请独立判断这个结论**：

- 你同意还是不同意？给出理由。
- 如果同意，你认为最小可行的分片设计是什么（分片键、清单字段、加载与校验顺序、
  与"全量 fail-closed"的关系）？
- 如果不同意，说明单文件在什么规模/什么条件下仍然成立。
- 给出你对 1,000 / 5,000 / 20,000 条时 `load_review_items` 的**实测**耗时与内存量级
  （自己跑，不要采信上一轮的数字）。

---

## 输出

- 写入 `F:\workspace\kaoyan-ai-system\review\rounds\round-5-opus.md`
- 用**中文**。用 `## A` `## B` `## C` `## D` 作二级标题。
- 允许并鼓励直接反驳上一轮报告；反驳必须给依据（代码事实、算术、实测输出）。
- 不要写操作确认语。
- 最后用一句话回复我：裁决 + 报告路径 + 你改了哪些文件 + unittest 结果 + 设计问题结论。
