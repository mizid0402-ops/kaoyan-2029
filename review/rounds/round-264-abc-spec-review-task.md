# 第 264 轮任务书：A + B + C 与改编题库 规格**初检**（gpt-6.1-sol，续 sol61-m17）

## 背景

用户看了能力画像演示后指出：一个月就"已巩固 36%"、按两年线性算"应到 3.9%"很不合理。用户定了三项改动加一个新想法：

- **A**：已巩固须真题答对过；**B**：应到按路线阶段末目标插值；**C**：数学一树"考试要求"拆到每条编号条目；
- **新**：早期复习用 AI 依据真题改编的简单题，记忆稳定度 ≥ 7 天起用真题原题（修订决议 B10）。

## 只做初检（用户 2026-10-01）

只审规格本身，不写代码、不跑测试；必须改附反例；其他一行进"留给最终大检查"；报告约 60 行。范围：

1. `contracts/question_bank.md`（新，M31）全文，重点 §2 B10 修订是否守住其余限制、§5 取题规则、§6 M24 章级回退（"并入后代"）对数学一 / 408 / 英语一三棵树是否都成立。
2. `contracts/mastery.md` 第二版 §2（真题门槛）、§5（阶段目标插值）、§6 端口签名；`contracts/route_plan.md` 末节"阶段目标"（v4、不减约束、M28 切段归属）；
   `contracts/charts.md` §8 卡片 2；`contracts/workspace.md` 新键 `state.question_bank`。
3. 包 C 的规则（尚无单独规格，下面是决策者写给实现者的规则，请一并审）：
   - 数学一 22 章各自的 `…chNN.requirements` 小节下，按大纲原文"考试要求"的**编号条目**（1. 2. 3. …）逐条建节点：ID `<章前缀>.requirements.item-NN`（两位序号），`scope: item`，
     `status: extracted`，`title` = 该条原文（空白归一），`sources` 列出能定位该条的转录来源（现有两份：eol 2022、newdu 2026，`quote_ref` 为该条原文，`sha256` 为本地文件哈希）。
   - 两份转录措辞不同：title 跟 2026 版（树是 2026 版大纲）；2026 版有确认的转录错字（与 2022 版对照、且第 258 轮变化报告未提该处改动）时按 §4.2"修正明显排版断裂须标注"改正，
     并在 `knowledge_tree_report.md` 记录；不能确认的差异只记录、不择一（两源各写各的 `quote_ref`）。
   - "考试内容"小节不拆（原文是不编号的连续清单）；`requirements` 小节自身保留为父节点。
   - 树语法 `named_chapters` 与 `tools/verify_tree.py` 需接受这层 item；`tests/test_data_manifest.py` 里钉住的数学一节点数按 AGENTS 第 7 条只在数据清单测试更新。
   - 真题索引、考频权重、M6 编码产出**不改**（它们挂在 `…content` 小节，靠 M31 §6 章级回退找到）。

## 输出

`F:\workspace\kaoyan-ai-system\review\rounds\round-264-abc-spec-review-sol61.md`：PASS / FAIL；必须改；留给最终大检查。

## 禁止

不联网；只写这一份报告；不改其他文件；不读 `data/personal/` 与 gitignore 的学习状态（可以读 `data/raw_materials/transcripts/` 下数学一大纲转录以核对 C 的可行性）。
