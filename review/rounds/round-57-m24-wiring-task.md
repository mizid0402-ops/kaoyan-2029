# Round 57 任务书：把 M24 核对出题接进 day-plan record（D9 宽松档）+ 模块地图三行

你是实现者（主工作区）。先读仓库根 `AGENTS.md`。依据：`docs/阶段2.5-接缝收口.md` §七 D9、`contracts/check_questions.md`、`contracts/review_progress.md`。

## 要做的

1. `ky/__main__.py` 的 `day-plan record --review-store`：队列推进报告里有 `needs_check_review_ids`（宽松档下自评"基本会 / 熟练"的未核对完成）时，
   对每个这样的复习项取其 `knowledge_point_id`，调用 `ky.review.check_questions.candidate_check_questions(workspace, kp, limit=3)`，
   在输出里列出："<review_id> 需要核对：<question_id>（<年份> 第 <题号> 题，卷面第 <页> 页）"；无真题时输出"该知识点无真题，可用 AI 巩固题（仅 guided 证据）"。
   - 注册表按 `contracts/workspace.md` §3.1 发现；加 `--workspace`。**找不到注册表时不失败**：照常完成记录与推进，只打印一行"未找到工作区注册表，跳过出题"。
   - `--json` 模式下把候选题放进 JSON（字段名在规格里写明）。
   - 只读 M24，不写任何新文件；出题不影响推进结果。
2. 规格：`contracts/review_progress.md` 增加"宽松档的出题提示"一小节（触发条件、输出形状、找不到注册表时的行为）。
3. 测试（`tests/test_cli.py` 或新文件）：宽松档配置 + 自评 fluent 的未核对完成 → 输出列出候选题；严格档 → 不出题；找不到注册表 → exit 0 且有跳过提示。临时文件用 `tempfile`，期望值从索引推导，不写字面量。
4. `docs/模块地图.md`：更新 M8（配置含 `review_policy.self_rating_mode`）、M10（规格 `contracts/review_progress.md`，可替换性 A，D3/D8′/D9）、M13（manifest schema 2 记录 `calculated_completion_ids`）三行。只改这三行。

## 验收

`py -3.12 -m unittest tests.test_cli tests.contract.test_review_progress_port tests.contract.test_check_questions_port`。全量不跑。无 `???`。
报告 `review/rounds/round-57-m24-wiring-luna.md`（`apply_patch`）。不提交。
