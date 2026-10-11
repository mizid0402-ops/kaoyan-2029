# 第 266 轮任务书：M31 改编题库 + 按档位出题 + M24 章级回退（gpt-6-luna，续 luna-a）

## 先读

`AGENTS.md`；规格 `contracts/question_bank.md`（本包唯一依据）、`contracts/check_questions.md`（M24 现有端口）、`contracts/mastery.md` §2（档位，含真题门槛）、
`contracts/planner_port.md`（M19 输入包 / staging / 新鲜度 / actor 规则，题库提交照抄这套）、`contracts/workspace.md`（新键 `state.question_bank`）；
sol 第 264 轮初检 `review/rounds/round-264-abc-spec-review-sol61.md`（必须改已改进规格，以规格为准）。
现有实现：`ky/review/check_questions.py`、`ky/planner/port.py`（输入包与提交）、`ky/storage/`（只写一次：临时文件 + 重读校验 + `os.link`，见 `route_store.py`）、
`ky/mastery/port.py` 的 `item_level`（**只调用公开函数**，不改它；它的新签名由 luna-c 同时在改——用工作区里的版本，如签名尚未落地，按规格 `item_level(item, past_question_passed)` 写调用并在报告注明）。

## 工作区与并行

主仓库 master 当前提交之上。luna-b 在改数学一树与树语法，luna-c 在改 `ky/mastery/`、`ky/charts/`、路线与 `ky/pacing/`。**不碰**这些；不改 README、`docs/模块地图.md`（决策者统一改）。

## 要做的

1. `ky/workspace.py`：接受 `state.question_bank`（主注册表与本地补充文件都可登记，目录型写入目标）。
2. 新包 `ky/question_bank/`：题库读写与校验（规格 §3，只写一次、只增不改）、取题（§5 的顺序）；模块头写 M31、规格、对外接口。
3. M24 `candidate_check_questions(..., ancestor_fallback=False)`：规格 §6；缺省时输出逐字节不变。
4. `ky planner-input --kind adapted-questions --knowledge-point <ID>`（§4.1）与 `ky question-bank submit --from-staging FILE [--dry-run]`（§4.3）。
5. `ky review-questions [--date D] [--json]`（§5）：选择与 `preflight` 相同；"做过"看完成事件的 `question_ref`；档位用 M30 `item_level`，真题门槛所需集合由完成事件推出。
6. 新 AI 指引 `prompts/adapted_questions.md`：读输入包里的真题定位、打开本机 PDF、改编出**更简单**、考同一知识点的新题；不得照抄真题题干；写 2–3 道；答案与简要解析；`validation: guided`。
7. `交接文档.md` §3 的早期决定表里 B10 行改成"已修订（2026-10-01），见 `contracts/question_bank.md` §2"——**这一行由决策者改，你不改**。

## 不做的

不改 M9 选择与排序、不改 `preflight` / `day-plan` 既有输出、不改 M10 推进；不让改编题进入任何频率 / 覆盖统计；不读 `data/personal/`；测试一律用临时工作区合成数据（含合成 PDF 定位，不读真实 PDF）。

## 测试（只写这些）

- `tests/contract/test_question_bank_port.py`：题库文件形状（未知键、重复键、ID 与文件名一致、`basis` 与 `based_on` 的搭配）；每题一文件只写一次、追加新序号；取题顺序（三道题先 01 再 02 后必须轮到 03；全做过选最久未用）；题库沿祖先向上找；无真题覆盖的知识点 `basis: syllabus` 可提交；粗粒度（非叶子）知识点可生成；
  提交：新鲜度过期拒绝、`based_on` 不在候选里拒绝、知识点不是可学叶子拒绝、`--dry-run` 零写入；未登记 `state.question_bank` 时的输出与退出码。
- `tests/contract/test_check_questions_port.py`：`ancestor_fallback=False` 与原结果逐字节相同；`True` 时 `requirements.item-NN` 经章节点找到 `content` 小节上的题（权重求和）、`matched_ancestor`；到根仍无 → 原 `fallback`。
- `ky review-questions`：`learned` 项给改编题、`progressing` 项给真题（排除用过的）、真题用尽退回改编题、都没有 → "缺题"；`--json` 形状。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_question_bank_port tests.contract.test_check_questions_port tests.contract.test_workspace tests.contract.test_planner_port tests.test_cli
```

报告 `review/rounds/round-266-question-bank-luna.md`：改动、做法、测试输出原文、"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"、歧义与选择。
不提交；中文字符串写字面量，不要写成 `\uXXXX`；含中文的文件只用 `apply_patch`；写完 `rg -n '\?\?\?'` 检查；保持 LF 换行。
