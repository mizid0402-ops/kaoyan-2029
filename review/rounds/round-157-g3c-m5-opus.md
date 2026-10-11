# Round 157：G3c-M5 修复（Opus 子代理）

对应第 150 轮 sol 评审"二、G3c 复审"的必须改项 G3c-M5。只改了 `ky/__main__.py` 与
`tests/test_cli_split_baseline.py`，未提交。

## 一、改动

`ky/__main__.py` 的 `_day_plan_record_query_candidates` 异常分支：

```python
    except ContractError as exc:
        # Keep groups found before the failing review; b867ae7 did (sol round 150, G3c-M5).
        return candidates, str(exc)
```

原先是 `return [], str(exc)`，会丢掉失败项之前已经 `append` 的候选组。`b867ae7` 的循环在
`ContractError` 时只设置 `question_skip_reason`，`check_question_candidates` 保留已累计的组；
现在与之一致。文本输出路径不变：有 skip 原因时旧版和新版都只打印跳过提示、不打印候选题，
`_day_plan_record_print_queue` 本来就与旧版相同。

## 二、新增对照场景（`tests/test_cli_split_baseline.py`）

- 辅助函数 `_write_done_reviews(root, reviews)`：写入多条复习的完成事件；原 `_write_done`
  改为委托它，单条场景生成的 `done.yaml` 内容不变。
- `_record_partial_skip_args`：按评审者复现构造两项队列：
  - `record-review`：复习夹具首项的科目与知识点，注册表为该科目登记试卷索引 → 找到候选；
  - `record-second`：配置中另一个活跃科目（从配置推导，不写死科目 ID，AGENTS.md 第 8 条），
    知识点 ID 用该科目前缀；注册表未登记它的 `exam_indexes` → 查询报 not registered → skip。
  - 两条完成记录均为 `check=none, self_rating=fluent`，配置 `self_rating_mode: lenient`。
- 新场景 `record-question-partial-skip`（`--json`）与 `record-question-partial-skip-text`
  加入 `test_day_plan_record_cli_bytes_match_fixed_baseline`，与 `b867ae7` 按
  (退出码, stdout, stderr) 原始字节比较，并断言事件已写入。
- 额外断言：JSON 的 `check_question_candidates` 恰有 1 组、`review_id` 为 `record-review`、
  组内候选非空，且含 `check_question_suggestions_skipped`；文本输出含"出题查询失败，已跳过"行。

说明：文本场景在修复前后输出相同（有 skip 时本就不打印候选），它锁住的是文本路径与基线一致，
抓回归的是 JSON 场景。

## 三、回退检查

在 `PYTHONDONTWRITEBYTECODE=1` 下把异常分支改回 `return [], str(exc)`，运行
`tests.test_cli_split_baseline...test_day_plan_record_cli_bytes_match_fixed_baseline`：

```
FAIL: ... (case='record-question-partial-skip')
AssertionError: Tuples differ: (0, b[33 chars]s": [],\r\n  "check_question_suggestions_skipp[545 chars] b'')
  != (0, b[33 chars]s": [\r\n    {\r\n      "candidates": [\r\n   [1046 chars] b'')
Ran 1 test in 17.337s
FAILED (failures=1)
```

只有 JSON 场景失败（文本场景如上所述不受影响）。随后从备份恢复，`ky/__main__.py`
sha256 恢复前后均为 `0f13f1f1a8203e8d0a2cce662f2815b85be393b6ae93791d500a919b9e58f434`，
`cmp` 一致。

## 四、测试

```
PYTHONDONTWRITEBYTECODE=1 py -3.12 -m unittest tests.test_cli tests.test_cli_split_baseline
Ran 50 tests in 67.975s
OK
```

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。

## 安全登记

无。
