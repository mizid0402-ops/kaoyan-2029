# WP-G3d 第 150 轮评审修复

## 范围

本工作树保留原有未提交改动，只修改 `tools/verify_408_index.py` 和
`tests/contract/test_index_tree_verifiers_split_baseline.py`。`verify_tree.py` 的阶段调用
本来与固定基线一致，本轮只补了能检验该顺序的输入。未提交、未合并。

## 修复

- G3d-M1：把无效的索引错误变体改成确实触发对应检查段的值；补充 `notes`、空
  `entries` 早退、卷面答案与来源不符等输入。每个变体先断言预期问题存在，再把
  `verify` 的返回值、异常和输出与固定提交 `ec832c7` 逐字节比较。不同字段的两项
  错误组合用于锁住问题顺序；空 `entries` 与后续检查组合时，只要求早退前的错误。
- G3d-M2：知识树变体加入契约合法但触发来源阶段失败的 `evidence`，并与重复 ID、
  缺少必需 scope 分别组合，以锁住结构、来源、scope 三阶段的报告顺序。另有状态
  提示、空树和契约退出变体。每项先断言退出码及关键报告，再对照旧 CLI 的退出码、
  stdout、stderr 原始字节。
- G3d-M3：`_verify_totals` 只计算编号、数量和分值；`verify` 在其后独立调用
  `_verify_answer_coverage`。答案覆盖仍位于原来的问题列表位置；后者自行筛出对象
  题目，与旧版传入对象题目的行为一致。

## 验证

- 固定基线对照模块：2 项通过。命令为
  `$env:PYTHONDONTWRITEBYTECODE='1'; py -3.12 -m unittest`，后接
  `tests.contract.test_index_tree_verifiers_split_baseline`。
- 任务书其余四个验收模块：33 项通过，分别为 `tests.contract.test_exam_index_port`、
  `tests.test_exam_index`、`tests.contract.test_knowledge_tree_port`、
  `tests.test_tools_catalog`，以同样环境变量运行。
- `git diff --check` 无错误；编辑文件未检出连续问号或超过 100 字符的行。
- 全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。

未发现本包范围内的未解决问题。实跑 CLI 与旧提交的对照结果仍见
`round-148-wp-g3d-luna.md`；本轮新增变体的固定基线对照在上述测试中执行。
