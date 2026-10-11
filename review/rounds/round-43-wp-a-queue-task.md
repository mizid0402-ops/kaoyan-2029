# Round 43 任务书：WP-A 队列读入统一（阶段 2.5 第 1 个工作包）

你是本轮的**实现者**。Claude（决策者）与 gpt-6-sol（独立评审）会审查你的 diff。
背景文件：`docs/阶段2.5-接缝收口.md`（§四 WP-A）、`docs/模块拆分与架构审查.md`（A4）。

## 问题（已在本机复现）

`ky day-plan record --review-store <dir>` 把推进后的复习项写进 `ReviewShardStore` 分片目录；
但 `ky preflight --items` 与 `ky snapshot --items` 只认扁平 YAML：

```
write_review_queue(<tmp>/rq, load_review_items('tests/fixtures/reviews/reviews-normal.yaml'))
py -3.12 -m ky preflight --config tests/fixtures/config/config-minimal.yaml --items <tmp>/rq --date 2026-09-25
→ contract violation: file does not exist: <tmp>\rq   (exit 2)
```

根因：`ky/__main__.py:169`（preflight）与 `:426`（snapshot）调用 `ky.models.load_review_items`，
而 `ky.storage.review_shards.load_review_queue` 已经两种格式都认。

## 要做的（只动 M13/M14 这一条接缝）

1. `preflight` 与 `snapshot` 的 `--items` 改走 `load_review_queue()`。
   `--items` 的 help 文本改为说明两种格式都接受（扁平 YAML 文件 / 分片目录 / 分片 `manifest.yaml`）。
   模块 docstring 与 `snapshot_main` docstring 里的用法同步。
2. 注意循环导入：`ky.storage` 依赖 `ky.models`，`ky/__main__.py` 已经从 `ky.storage.review_shards` 导入，确认没有新问题。
3. 失败语义不变：目录存在但没有 `manifest.yaml`、分片哈希不符、重复 review_id 等，必须仍是 `contract violation: …` + **exit 2**，不得出现 traceback。
   `StorageError` 是 `ContractError` 子类，确认被现有 `except ContractError` 捕获。
4. 测试（加到 `tests/test_cli.py`，沿用该文件现有的子进程/调用风格）：
   - **等价性**：同一批复习项分别以扁平 YAML 和分片目录喂给 `preflight --json` 与 `snapshot --json`，输出逐字节相同。
   - **闭环**：`day-plan record --review-store <dir>` 推进后，`preflight --items <dir>` 与 `snapshot --items <dir>` exit 0，且被推进项的新 `due_date` 反映在输出里（例如到期计数变化）。
   - **失败**：空目录（无 manifest）→ exit 2 且 stderr 以 `contract violation:` 开头；传 `manifest.yaml` 文件路径也能读。
   - 所有临时文件用 `tempfile`，不得写进仓库。

## 不做的

- 不改 `load_review_items` / `load_review_queue` 本身的语义，不改存储格式。
- 不做工作区配置（那是 WP-B），不动任何写死路径，不动 `data/` 下任何文件。
- 不重构 CLI 分派方式（`ky -h` 问题留给后面）。

## 验收

1. `py -3.12 -m unittest tests.test_cli tests.test_storage tests.test_review_queue_advance tests.test_state_snapshot` 全绿。
2. 全量 `py -3.12 -m unittest discover -s tests -t .`：只允许出现基线已知的 2 项失败
   （`test_eng1_vocabulary…test_verifier_deterministic_check_and_mutations`、`test_round24_weighted_tree…test_real_file_passes_validation`，均因 `%TEMP%\kaoyan-probe` 缺文件），不得新增失败。
3. 上面的复现命令 exit 0。

## 产物

不要提交（commit 由决策者做）。写报告到 `review/rounds/round-43-wp-a-queue-luna.md`：改了哪些文件、为什么、每条验收命令的实际输出摘要（含 Ran N / 失败名单）、你自己发现的风险。
