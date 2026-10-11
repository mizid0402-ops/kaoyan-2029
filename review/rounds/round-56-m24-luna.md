# Round 56 M24 实现报告

## 结果

新增 M24 核对出题端口规格、只读实现与契约测试，并在模块地图登记 M24。实现使用工作区科目档案解析知识点 ID 的科目段，经 `require_all` 读取该科目登记的真题索引；索引逐题权重优先，直接知识点 ID 映射缺少逐题权重时读取 `reference.topic_weights.per_question`。候选按权重降序、年份降序、题号升序排列，输出不含题目原文。

没有关联真题时返回空候选及 `fallback=ai_generated_allowed`。若关联真题全部在 `exclude` 中，则空候选但不报告 AI 回退，因为索引仍有真题来源。端口不生成或记录 AI 题目。

## 验收

- 命令：`py -3.12 -m unittest tests.contract.test_check_questions_port`
- 结果：`Ran 7 tests ... OK`。首跑发现“无真题”夹具误关联目标点，修正夹具并重跑通过；新增逐题聚合权重回退用例通过。
- 全量：未跑（按 `AGENTS.md`，由决策者提交前统一跑）。
- 连续问号检查：通过，新增及修改文件未发现三个连续问号。

## 范围

除新增的规格、实现、契约测试和本报告外，只修改 `docs/模块地图.md` 增加 M24 一行，并新增允许的 `ky/review/__init__.py`。未提交。
