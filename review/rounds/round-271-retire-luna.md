# 第 271 轮：M31 标记坏题

## 改动与做法

- `ky/question_bank/port.py` 将题号校验放宽到 01–99。
  `load_question_bank` 读取对应的 `.retired.yaml`，验证字段、题号、日期和文件位置，
  并在加载结果中标出停用状态；选择器跳过停用题。
- 新增 `retire_question`：先校验目标题及原因，再按临时文件、重读校验、`os.link` 的只写一次流程发布停用记录。dry-run 不写文件。重复停用和题号不存在均为契约错误。
- 追加题目时以历史最大序号递增，容量只统计未停用题。因此 01–09 全部停用后可继续新增 10。
- `ky question-bank retire` 支持 `--question`、`--reason`、`--date` 和 `--dry-run`。保留既有 `submit` 的处理路径与无效子命令用法提示。
- `review-questions` 忽略停用题；最近的非空题组全部停用且没有可选题时，
  状态包含“该点改编题已全部停用”。文本模式在每道改编题后打印停用提示；
  JSON 字段形状不变。
- 契约测试覆盖停用文件只写一次、dry-run、错误输入、跳过停用题、祖先组停用、序号 10、review 文本提示及 JSON 形状。

## 验收

执行命令：

```text
py -3.12 -m unittest tests.contract.test_question_bank_port tests.test_cli
```

测试输出原文：

```text
.................................................................................
----------------------------------------------------------------------
Ran 81 tests in 94.267s

OK
```

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）

另在最终验收前针对新加测试执行 `py -3.12 -m unittest tests.contract.test_question_bank_port`，输出：

```text
...................
----------------------------------------------------------------------
Ran 19 tests in 0.879s

OK
```

`git diff --check` 无输出；本轮涉及的代码与测试文件执行 `rg -n '\?\?\?'` 无匹配。

## 歧义与选择

- 停用状态作为加载结果的派生字段 `retired` / `retirement` 提供，不写回原题 YAML；未停用题仍保持原来的映射形状。
- 全停用提示附在现有 `status` 值后面，不增加 JSON 键。`learned` 项保留
  “缺改编题：先生成”状态前缀；`progressing` 项在真题用尽后仍按既有回退流程
  给出缺题状态并附停用说明。
- 工作区同时出现 luna-b 的 `learn` 命令变更。本轮没有编辑其实现；
  `ky/__main__.py` 的本轮改动仅限题库导入、`question_bank_main`、
  `review-questions` 和题库帮助描述。
