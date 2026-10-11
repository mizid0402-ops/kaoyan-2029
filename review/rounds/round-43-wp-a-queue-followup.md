# Round 43 增量：WP-A 补两条验收（来自 gpt-6-sol 评审）

在你已有改动之上补测试（仍加在 `tests/test_cli.py`，仍用 `tempfile`，不提交）：

1. **分片被篡改 / 缺失**：先 `write_review_queue` 写出合法分片目录，然后分别
   (a) 改写某个分片文件的一个字节（使 sha256 与 manifest 不符）、(b) 删除某个分片文件。
   对每种情况，`preflight --items <dir>` 与 `snapshot --items <dir>` 都必须：exit 2、stderr 以 `contract violation:` 开头、stderr 不含 `Traceback`。
2. **分片队列里的未知科目仍被拒**：分片目录里放一个 `subject_id` 不在配置中的复习项，
   `preflight --items <dir>` 必须仍被 `validate_items_against_config` 拒绝（exit 2），与扁平 YAML 行为一致（参照现有 `test_unknown_subject_id_in_items_exits_2`）。
   如果分片存储在写入时就拒绝了该科目，就直接写 manifest/分片构造这个状态，或说明为什么这条在分片路径上不可达。

验收：`py -3.12 -m unittest tests.test_cli tests.test_storage tests.test_review_queue_advance tests.test_state_snapshot` 全绿。
这一轮**不必再跑全量**，全量集成由决策者在工作区稳定后统一跑。

把补充内容追加到 `review/rounds/round-43-wp-a-queue-luna.md` 末尾（新增一节"增量"），不要覆盖前面内容。
