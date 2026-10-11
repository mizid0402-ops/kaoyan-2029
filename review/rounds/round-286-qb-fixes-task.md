# 第 286 轮任务书：题库读端与停用提示的四条必须改（gpt-6-luna，窗口 luna-fix-qb，新会话）

## 来源

最终大检查 B（`review/rounds/round-282-final-b-sol61.md`）的 M2 / M4 / M5 / M6，决策者已逐条复核代码位置。

**M2 `ky/__main__.py:1288`**：停用提示里的 `--reason <原因>` 在 PowerShell 里解析失败（`<` 是保留的重定向运算符）。
把占位文字加引号并说明要替换成原因；`--date` 部分已经是对的，保留。

**M4 `ky/question_bank/port.py:150-157`**：读端要求每个文件都是 `<id>.yaml` 或 `<id>.retired.yaml`，
否则报 `unexpected file in question bank`；而写入器 `:222-238` / `:293` 就在**题库目录内**建
`.<目标名>.<随机>.tmp`。一次强制终止（Ctrl+C、断电、进程被杀）留下这种残留，之后整个题库读不了、也提交不了。
复现：合法题库里留一个与写入器命名一致的 `.qb-<ID>-01.yaml.<...>.tmp`，`load_question_bank` 直接报契约错误。
要求：读端认出**写入器自己的**临时产物并跳过（或按写入器语义安全回收），
同时不许放宽成"忽略一切未知文件"——真正的手工污染仍须 fail-closed。命名规则照写入器现有命名，不要发明新格式。

**M5 `ky/question_bank/port.py:198` 与 `:210`**：同一份题库连续 `load_question_bank` 两次
（`AGENTS.md` 已知缺陷 #2）。保存一次解析结果，序号与容量都从这份结果推，不要读两遍。

**M6 `ky/question_bank/port.py:514`**：dry-run 提前返回，跳过 `append_question` 的序号/容量规则。
复现：已有合法 01 题，用新鲜输入包再次提案 01 —— `dry_run=True` 成功，正式提交却报
`expected next question id ...-02`。抽出共享的**只读入库预检**，让 dry-run 与正式路径走同一套判断，
dry-run 仍然一个字节都不写。

## 约束

- 每条修复带**该条**的回归测试，放 `tests/contract/test_question_bank_port.py`（照该文件已有夹具与命名），
  测试断言要能区分"修好了"和"把错误吞掉了"（例如 M4 要同时断言：自己的 tmp 被跳过、外来垃圾文件仍报错）。
- 不动 `ky/today/`、不动 `ky/web/`、不改编题选择算法、不动 M30。
- 不跑全量、不做顺手重构、不提交。
- 只改这四个缺陷；B 包的"建议改"（最近使用日期口径、全停用输出优先级 M3 属另一包）本轮**不做**。

## 验收（只跑这三条 + 每条缺陷一个探针）

```
py -3.12 -m unittest tests.contract.test_question_bank_port
py -3.12 -m unittest tests.test_cli
py -3.12 -m unittest tests.contract.test_check_questions_port
```

探针：M2 用 `[System.Management.Automation.Language.Parser]::ParseInput` 之类方式证明提示行现在能解析（或直接给一条可复制执行的命令）；
M4 留残留文件后 `load_question_bank` 成功且外来文件仍被拒；M5 数一次 `Path.open`/读取次数；
M6 对同一输入比较 dry-run 与正式路径的结论一致。

## 报告

写 `review/rounds/round-286-qb-fixes-luna.md`，≤ 80 行：逐条 M2/M4/M5/M6 的改法（`文件:行`）与修复前后实测输出；
三条验收命令的 `Ran ... OK` 原文；"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"；怀疑模块；未做/没把握的地方。

## 规则（照 `AGENTS.md`）

- 含中文的文件只用编辑工具写；写完查有没有连续 `???`。
- 行宽 ≤ 100；函数 ≤ 约 60 行；注释写"为什么"并引用 M31 / sol 282 的编号（M2/M4/M5/M6）。
- 模块头 docstring 保持 M 编号与规格引用（`contracts/question_bank.md`）。
- 临时输入放系统临时目录；设 `PYTHONDONTWRITEBYTECODE=1`；不读 `data/personal/`。
