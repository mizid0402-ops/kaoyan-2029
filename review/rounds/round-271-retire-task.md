# 第 271 轮任务书：M31 标记坏题 `ky question-bank retire`（gpt-6-luna，续 luna-a）

## 先读

`AGENTS.md`；规格 `contracts/question_bank.md` §6a（本包依据）与 §5；sol 第 269 轮初检 `review/rounds/round-269-intake-spec-review-sol61.md`（必须改已改进规格，以规格为准）。
你上一轮写的 `ky/question_bank/`、`ky/__main__.py` 的 `question_bank_main` 与 `review-questions`。

## 工作区与并行

主仓库 master 当前提交之上。luna-b 同时在 `ky/__main__.py` 新增 `learn` 子命令；你只改 `question-bank` 与 `review-questions` 相关处，不碰其他命令；
不改 README、`docs/模块地图.md`（决策者统一改）。

## 要做的

0. 规格 §3 已改（sol 269 M2）：序号放宽到 01–99（`_ID` 正则同步），限制改为"未停用的题最多 9 道"；补对应测试（停用 9 道后仍能写第 10 号）。
1. `ky/question_bank/`：停用文件读写（只写一次，同题目文件的发布方式）、`load_question_bank` 能区分已停用、取题跳过已停用、整组全停用的结果。
2. `ky question-bank retire --question <题号> --reason … --date D [--dry-run]`。
3. `ky review-questions`：整组全停用时的说明；文本输出每道改编题后加一行停用提示（JSON 不加）。

## 测试（只写这些，`tests/contract/test_question_bank_port.py`）

- 停用后不再被选；停用文件只写一次（再停用 → 退出 2）；题号不存在 → 退出 2；`--dry-run` 零写入。
- 整组全停用 → "缺改编题：先生成"并注明全部停用；向上查找时祖先组的停用同样生效。
- 文本输出含停用提示行；JSON 形状不变。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_question_bank_port tests.test_cli
```

报告 `review/rounds/round-271-retire-luna.md`：改动、做法、测试输出原文、"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"、歧义与选择。
不提交；中文字符串写字面量；含中文的文件只用 `apply_patch`；写完 `rg -n '\?\?\?'` 检查；保持 LF 换行。
