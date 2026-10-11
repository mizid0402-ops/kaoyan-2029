# 第 286 轮题库修复报告

## M2 停用提示

- 改法：[ky/__main__.py:1286](/F:/workspace/kaoyan-ai-system/ky/__main__.py:1286)
  给原因占位符加双引号，明确显示“替换为原因”；保留日期参数。
- 修复前：sol 282 B 报告记录 PowerShell 解析为 `RedirectionNotSupported`。
- 修复后：Language.Parser 探针输出 `parse_errors=0`。

## M4 题库残留文件

- 改法：[ky/question_bank/port.py:34](/F:/workspace/kaoyan-ai-system/ky/question_bank/port.py:34)、
  [ky/question_bank/port.py:193](/F:/workspace/kaoyan-ai-system/ky/question_bank/port.py:193)。
  只跳过有效题目 ID、同知识点目录、8 位小写字母/数字随机尾缀的 writer 临时名；
  题目与 `.retired.yaml` 两类目标均覆盖。其他文件仍 fail-closed。
- 修复前：合法题库加 `.qb-<ID>.yaml.<随机>.tmp` 后报 `unexpected file in question bank`。
- 修复后：回归探针同时放入题目临时文件和停用临时文件，题库读取成功；加入
  `manual-notes.txt` 后仍报 `unexpected file in question bank`。

## M5 单次读取

- 改法：[ky/question_bank/port.py:209](/F:/workspace/kaoyan-ai-system/ky/question_bank/port.py:209)、
  [ky/question_bank/port.py:242](/F:/workspace/kaoyan-ai-system/ky/question_bank/port.py:242)。
  `append_question` 用一次解析结果推导最大序号和活动题容量。
- 修复前：代码连续调用两次 `load_question_bank`。
- 修复后：`Path.open` 探针确认入库预检对已有题目 YAML 只读取一次。

## M6 dry-run 入库预检

- 改法：[ky/question_bank/port.py:242](/F:/workspace/kaoyan-ai-system/ky/question_bank/port.py:242)、
  [ky/question_bank/port.py:537](/F:/workspace/kaoyan-ai-system/ky/question_bank/port.py:537)。
  dry-run 与正式写入共用只读序号/容量预检；dry-run 不写题库。
- 修复前：同一新鲜提案的 dry-run 通过，正式提交报 `expected next question id ...-02`。
- 修复后：两条路径均报相同的 `expected next question id ...-02`，且未创建 02 文件。

## 验收

```text
py -3.12 -m unittest tests.contract.test_question_bank_port
Ran 23 tests in 1.003s
OK

py -3.12 -m unittest tests.test_cli
Ran 63 tests in 80.655s
OK

py -3.12 -m unittest tests.contract.test_check_questions_port
Ran 12 tests in 0.235s
OK
```

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。

## 范围与遗留

- 怀疑受影响模块：M31 `ky.question_bank` 的读写入口；M2 `ky.__main__` 的停用提示。
- 未做：M3 最近使用日期与全停用输出优先级；其他模块及个人数据未检查。
- 把握：M4 精确匹配依赖当前 Python `tempfile` 的 8 位小写字母/数字后缀格式；
  该格式与本机写入器实测命名一致。未做跨平台或故意伪造内部文件的安全测试。
- 工作区同时存在图表与 ICS 文件的其他改动，本报告未纳入这些改动。
