# 第 262 轮实现报告：FSRS 接管复习时间

## 改动

- 新增 `ky/schedule/fsrs_algorithm.py`：实现 M10 `ReviewAlgorithm`；使用 `py-fsrs` 默认参数、UTC 当日零点、空学习步、180 天上限和关闭 fuzzing。已核对的 correct/partial/incorrect 分别映射 Good/Hard/Again；未核对按 D9 更新间隔且不改变 FSRS 记忆状态。
- `ReviewSchedule` 增加 `stability`、`difficulty`、`fsrs_reviewed_on`；FSRS 模式要求 phase=5、稳定度有限且大于 0、难度在 1–10、记忆日期为 `YYYY-MM-DD`。其他模式出现任何 FSRS 字段均拒绝。FSRS 队列读写保留浮点精度；旧模式仍省略这些键。
- 增加 `review_policy.algorithm` 和 `create_review_algorithm()`；CLI 由工厂按配置选择算法。阶梯缺省行为不变。
- FSRS 晚到的已核对完成保留七个 FSRS 调度字段，仍记入完成 ID；推进报告新增 `fsrs_late_checks`，文本 CLI 输出提示，JSON 只在有晚到核对时添加该字段，以维持旧输入输出。
- 投影 `review_items` 增加三列并升至 schema 5；更新状态读取、规格、契约测试、依赖和 M10 模块地图。未改 M9、复习创建规则、个人配置或技术债清单。

## 做法与选择

- 首次从阶梯接管时，以 FSRS 新卡开始；FSRS 项恢复为 `State.Review`，`last_review` 只取 `fsrs_reviewed_on`。普通 `last_reviewed_on` 仍按完成记录推进。
- `completed_on < fsrs_reviewed_on` 时不调用 FSRS；完成记录和 `last_reviewed_on` 仍遵循原有推进规则。相等日期仍调用库。
- 切回 ladder 后，已核对 FSRS 项由既有 SM-2 Lite 公式接管并移除三字段；未核对只依 D9 改间隔，保持模式和 FSRS 状态。
- `fsrs_late_checks` 在 JSON 中仅有内容时输出，避免给缺省 ladder 输入增加 JSON 键。

## 测试输出原文

首轮执行任务书给出的 8 模块命令：

```text
Ran 233 tests in 109.845s

FAILED (failures=3, errors=1)
```

失败原因原文摘要：

```text
ERROR: test_single_error_variant_table (tests.test_contracts.ReviewItemContractTest.test_single_error_variant_table)
KeyError: 'difficulty'

FAIL: test_fsrs_memory_fields_are_rejected_for_ladder_mode (tests.test_contracts.ReviewItemContractTest.test_fsrs_memory_fields_are_rejected_for_ladder_mode)
AssertionError: '<item>.schedule.stability' != 'items[0].schedule.stability'

FAIL: test_fsrs_schedule_requires_valid_memory_state (tests.test_contracts.ReviewItemContractTest.test_fsrs_schedule_requires_valid_memory_state)
AssertionError: '<item>.schedule.stability' != 'items[0].schedule.stability'

FAIL: test_schema5_adds_only_the_three_fsrs_columns_to_pinned_schema4 (tests.contract.test_projection_port.ProjectionPaperSourceTest.test_schema5_adds_only_the_three_fsrs_columns_to_pinned_schema4)
AssertionError: 'paper_source' unexpectedly found in {'answer_confidence', 'subject_id', 'marks', 'question_id', 'knowledge_point_id', 'exam_year', 'paper_sha256', 'n_knowledge_points', 'locator_page', 'number', 'paper_source', 'question_type', 'knowledge_point_status', 'answer'}
```

修复后受影响模块复跑输出：

```text
py -3.12 -m unittest tests.contract.test_fsrs_algorithm_port
..........
----------------------------------------------------------------------
Ran 10 tests in 0.094s

OK
```

```text
py -3.12 -m unittest tests.test_contracts
......................................................................
----------------------------------------------------------------------
Ran 70 tests in 0.795s

OK
```

```text
py -3.12 -m unittest tests.test_review_queue_advance
..................
----------------------------------------------------------------------
Ran 18 tests in 0.664s

OK
```

```text
py -3.12 -m unittest tests.contract.test_projection_port
.................
----------------------------------------------------------------------
Ran 17 tests in 13.722s

OK
```

```text
py -3.12 -m unittest tests.contract.test_learning_state_projection
......
----------------------------------------------------------------------
Ran 6 tests in 5.258s

OK
```

```text
py -3.12 -m unittest tests.test_cli
Ran 62 tests in 8595.691s

OK
```

`tests.test_completion` 和 `tests.contract.test_config_port` 在首轮 8 模块命令中通过；该命令其余首次通过模块也未重跑。未再次运行整个 8 模块命令，按 `AGENTS.md` 只重跑改动影响的模块。

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）

## 检查与边界

- 本任务源码、测试、`contracts/projection.md` 和模块地图的定向 `git diff --check` 无输出；相关文件 `rg -n '\?\?\?'` 无命中。
- 全仓库 `git diff --check` 会报告其他未提交规格文件中的行尾空白（包括 charts、review_progress 等）；这些并行规格改动未在本轮改写。
- 规格文件 `contracts/charts.md`、`contracts/config.md`、`contracts/learning_state_projection.md`、`contracts/review_progress.md`、`contracts/workspace.md` 及对应任务/审查材料在开始时已是未提交状态，本轮保留。
- 怀疑受影响但未点名的模块：无。M15 投影状态读取器是 schema 直接消费者，本轮已同步更新并由投影测试覆盖。
- 未提交；未读 `data/personal/`，未运行 FSRS 优化器。
