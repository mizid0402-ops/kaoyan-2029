# WP-G3d 第 150 轮修复复审：PASS

## 范围与方法

对照 `review/rounds/round-150-review-sol-out.md` 的 G3d-M1/M2/M3，复核本工作树中
`tools/verify_408_index.py` 与
`tests/contract/test_index_tree_verifiers_split_baseline.py` 的未提交差异。固定旧版为
`ec832c7`；测试先确认旧函数仍是拆分前的长实现，再在同一份输入上比较新旧返回值、
异常、stdout 和 stderr。只运行相关单模块与临时换序探针，未改动实现和测试文件。

## 上轮必须改项

- **G3d-M1 已解决。** 原先无效的 `header`、`provenance-shape`、
  `coverage-shape`、`calibration` 输入已替换；新增 `notes`、空 `entries` 早退及卷面
  答案检查输入。每个单错和可并存双错先断言标称错误确实出现，再比较固定旧版的
  完整可观察结果。空列表与后续错误组合时，只期待早退之前的错误。将
  `_verify_totals` 与 `_verify_answer_coverage` 在临时索引校验器中换序后，该对照
  测试出现 6 个失败，证明双错能检出这一处顺序回归。
- **G3d-M2 已解决。** `evidence` 输入通过知识点契约，进入来源检查并产生
  `extracted node must not carry evidence`。它分别与重复 ID 和缺少必需 scope
  组合；测试确认各错误同时出现并比较完整输出。在系统临时目录分别交换
  “结构/来源”和“来源/必需 scope”两对调用，两份对应输入的输出都与原版不同。
- **G3d-M3 已解决。** `_verify_totals` 不再调用答案覆盖检查；`verify` 在合计检查
  后单独调用 `_verify_answer_coverage`。新函数先筛出字典题目，与拆分前传入的
  `object_entries` 一致，固定基线对照通过。

## 验证

- `py -3.12 -B -m unittest tests.contract.test_index_tree_verifiers_split_baseline`：
  2 项通过，约 34 秒。
- 临时源码换序：索引合计/答案覆盖对照变红（6 个失败）；知识树结构/来源、
  来源/必需 scope 的相应双错输出均改变。临时副本随探针结束删除，原工作树源码
  未改动。
- `git diff --check`：通过。
- 全量测试未跑，遵守 `AGENTS.md` 的最小验证范围。

## 结论

**PASS。** 上轮三项必须改均有直接证据闭环；在本次复审范围内没有发现新的
阻断问题。正式合入与提交仍由决策者处理。
