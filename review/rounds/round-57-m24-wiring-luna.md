# Round 57 实现报告：M24 接入 day-plan record

## 完成内容

- `day-plan record --review-store` 在推进报告含 `needs_check_review_ids` 时，读取对应队列项的
  `knowledge_point_id`，通过工作区注册表调用 M24，最多列出 3 道关联真题。
- 文本输出列出题目 ID、年份、题号和卷面页；无关联真题时提示 AI 巩固题仅产生 `guided` 证据。
- 增加 `--workspace` 和 `--json`。JSON 候选字段为 `check_question_candidates`，规格同步记录其结构。
- 找不到注册表时保留完成记录与队列推进，输出指定跳过提示。M24 查询错误也只跳过提示，不回滚推进。
- 更新模块地图 M8、M10、M13 三行；添加候选题、严格档和注册表缺失 CLI 覆盖。

## 验收

- `py -3.12 -m unittest tests.test_cli tests.contract.test_review_progress_port tests.contract.test_check_questions_port`
  → 46 tests，OK。
- 全量：未跑（按 `AGENTS.md`，由决策者提交前统一跑）。
- 对改动文件及本报告执行 `rg -n '\?\?\?'`：无命中。

## 限制

- `locator.page` 按 M24 原始定位对象读取并用于文本输出；索引若缺少该页字段，输出会显示其原始缺失值。
