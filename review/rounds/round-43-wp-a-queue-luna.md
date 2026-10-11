# Round 43 — WP-A 队列读入统一（实现报告）

## 改动

- `ky/__main__.py`
  - `preflight` 与 `snapshot` 的 `--items` 统一调用 `ky.storage.review_shards.load_review_queue()`。
  - 两处 `--items` 帮助文本，以及模块和 `snapshot_main` 用法说明，列出扁平 YAML、分片目录和分片 `manifest.yaml` 三种入口。
  - 删除原先未再使用的 `load_review_items` 导入。
  - 没有改 loader、分片存储格式或 CLI 分派方式。
- `tests/test_cli.py`
  - 增加 preflight 和 snapshot 对扁平文件、分片目录、manifest 文件的 JSON UTF-8 字节一致性测试。
  - 两个命令都覆盖“目录存在但缺 manifest”时 exit 2、stderr 以 `contract violation:` 开头且无 traceback。
  - 扩展 `day-plan record --review-store` 闭环测试：推进后 preflight 与 snapshot 均成功，推进后的项目不再计入当天到期项。
- `review/rounds/round-43-wp-a-queue-luna.md`
  - 本轮实现和验收记录。

## 错误处理与导入检查

`load_review_queue` 和 `ReviewShardStore` 来自 `ky.storage.review_shards`；CLI 原本已从该模块导入 `ReviewShardStore`，本次只增加同模块函数导入。`review_shards` 依赖 `ky.models`，而 CLI 先导入 `ky.models`，未形成新的循环导入。`ky.storage.review_shards.StorageError` 继承 `ky.models.ContractError`；preflight 和 snapshot 的既有 `except ContractError` 会将 manifest、分片校验错误转换为 `contract violation: …` 和 exit 2。

## 验收结果

| 命令 | 实际结果 |
|---|---|
| `py -3.12 -m unittest tests.test_cli` | `Ran 26 tests in 11.462s`，`OK`。 |
| `py -3.12 -m unittest tests.test_cli tests.test_storage tests.test_review_queue_advance tests.test_state_snapshot` | `Ran 53 tests in 42.692s`，`OK`。 |
| `py -3.12 -m unittest discover -s tests -t .` | `Ran 440 tests in 91.222s`，`FAILED (failures=2)`；仅有下列两项已知失败，无 errors：<br>1. `tests.test_eng1_vocabulary.English1VocabularyRegressionTests.test_verifier_deterministic_check_and_mutations`：缺少 `%TEMP%\kaoyan-probe\claude2\dl\bv_e1_2024.pdf`。<br>2. `tests.test_round24_weighted_tree.WeightedTreeStructureTest.test_real_file_passes_validation`：缺少 `%TEMP%\kaoyan-probe\ghsurvey\downloads\408_syllabus_2022.pdf`。 |
| 原始队列目录复现：用 `write_review_queue(temp/rq, load_review_items(reviews-normal.yaml))` 后运行 `py -3.12 -m ky preflight --config tests/fixtures/config/config-minimal.yaml --items <temp>/rq --date 2026-09-25` | `repro_exit=0`；正常输出 `due items: 3`、`selected: 3`，stderr 为空。临时队列由 `tempfile.TemporaryDirectory()` 创建并清理。 |

## 自查风险

- `load_review_queue` 的输入判别仍沿用既有规则：目录按分片队列读取，名为 `manifest.yaml` 的文件按所属目录读取，其他文件走扁平 YAML 加载。本轮没有改变该规则。
- 全量测试的两项失败都指向本机缺失的外部临时 PDF；它们与本轮改动无关，定向四模块验收全绿。
- 未改 `data/` 下文件，也未提交 commit。

## 增量

### 新增验收

- `test_corrupt_or_missing_review_shard_is_contract_violation_in_both_clis`：基于合法分片队列分别改写一个分片字节（保持 YAML 可读、令内容哈希不匹配）和删除分片文件；两种情况下分别调用 preflight 与 snapshot，均断言 exit 2、stderr 以 `contract violation:` 开头且无 traceback。
- `test_unknown_subject_in_sharded_queue_matches_flat_yaml_rejection`：将 fixture 中一项改为配置外的 `ghost` 科目，使用同一项生成扁平 YAML 和分片队列，确认两种输入的 preflight stderr 完全相同且均 exit 2。分片存储的 schema 允许非空任意科目 ID，因此该状态可以通过正常 `write_review_queue()` 写入，无需直接伪造 manifest 或分片文件。

### 验收结果

| 命令 | 实际结果 |
|---|---|
| `py -3.12 -m unittest tests.test_cli.SnapshotCliTest.test_corrupt_or_missing_review_shard_is_contract_violation_in_both_clis tests.test_cli.SnapshotCliTest.test_unknown_subject_in_sharded_queue_matches_flat_yaml_rejection` | `Ran 2 tests in 1.456s`，`OK`。 |
| `py -3.12 -m unittest tests.test_cli tests.test_storage tests.test_review_queue_advance tests.test_state_snapshot` | `Ran 55 tests in 45.426s`，`OK`。 |

按本轮任务要求未重跑全量测试；前一节的全量结果保持原记录。
