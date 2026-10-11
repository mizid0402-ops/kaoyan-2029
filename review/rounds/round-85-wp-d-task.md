# 任务书：WP-D 词汇投放状态迁出参考库（M7 → M13，审查项 B2）

先读仓库根 `AGENTS.md`（尤其 11–13 条：输出逐字节不变、固定基线提交、删用户可见文字先报告），再读：
`docs/阶段2.5-接缝收口.md` 审查项 B2 与 WP-D 行、`docs/模块地图.md` M7 / M13 行、`contracts/vocabulary.md`、
`ky/schedule/vocab_channel.py`、`ky/schedule/completion.py`（`VocabProgress`：`delivered_words` / `practiced_words`）、
`ky/storage/day_plan_store.py`、`ky/schedule/state_snapshot.py`、`tools/daily_words.py`、`tests/test_eng1_vocabulary.py`。

## 为什么做

英语词汇参考库 `data/english_vocabulary/eng1_vocabulary.sqlite`（`reference.vocabulary_db`）是**冻结**的参考数据（哈希不应再变），
但里面混着学习状态表 `delivery_log`（当前 15 行，2026-09-13 投放）。`tools/daily_words.py` 仍往这张表写（每次投放 INSERT、`--reset` DELETE），
`vocab_channel` 与状态快照也从这张表读"已投放"。参考库因此无法整库替换。
阶段②已经给了新路径：完成事件（`CompletionEvent.vocab.delivered_words`，由 `ky day-plan record` 写入 `state.plans`）。本包把旧路径关掉。

## 决策者已定的设计（照做；有更好的写法先在报告里提，不要自行改设计）

1. **真相源**：已投放词 = `state.plans` 下所有完成事件的 `vocab.delivered_words` 之并集（按 `word_form`）。
   在 M13 给 `DayPlanStore` 加只读查询（例如 `delivered_words() -> frozenset[str]`），逐个读已写入的完成事件；不引入新的状态文件。
2. **一次性迁移**：新工具 `tools/migrate_vocab_delivery.py`：用只读的 `import_delivery_baseline(db)` 读出旧 `delivery_log` 的词（它已存在），
   按原 `delivered_on` 日期分组，每个日期写一条只含 `vocab.delivered_words`、`reviews: []` 的完成事件（经 `DayPlanStore.write_completion_event`，写一次）。
   该日期已有完成事件 → 拒绝并说明（不合并、不覆盖）。默认 dry-run 只打印，`--apply` 才写；路径从注册表 `state.plans` 取（`workspace.plans`，写入目标不走 `require`）。
   `import_delivery_baseline` 目前只返回词形不带日期——需要日期就在 M7 加一个同样只读的函数返回 `(delivered_on, word_form)`，旧函数若再无调用者就删掉（不留别名）。
   **本包不对仓库的真实 `state.plans` 执行 `--apply`**；决策者审完后自己执行。
3. **M7 读取端**（`ky/schedule/vocab_channel.py`）：删除 `_legacy_delivered_word_ids` 及一切对 `delivery_log` 的读取（迁移用的只读函数除外）。
   `remaining_pool(db, *, delivered=…)`、`preview_batch(count, *, db, delivered=…)`：`delivered` 由调用方传入（`word_form` 集合，缺省空集），取代 `exclude_delivered`。
   规格 `contracts/vocabulary.md` 改写相应段落（删掉"legacy bridge remains until WP-D"一类过时说法）。
4. **快照**（M12）：`vocab.delivered` 改为状态存储里的已投放词数；`remaining` 用同一集合调用 `remaining_pool`。先看 `contracts/state_snapshot.md` 怎么定义这两个数，按规格改；
   快照拿不到 `state.plans`（没有注册表、目录不存在）时的行为照现有规格对"无数据"的处理，写进报告。
5. **`tools/daily_words.py` 关闭写入**：
   - 删除 `INSERT INTO delivery_log`、`--reset`；以只读方式打开参考库（`mode=ro`）；库路径从注册表 `reference.vocabulary_db` 取（保留隐藏的 `--db` 覆盖）。
   - 已投放集合改为从状态存储读（第 1 条），按原逻辑排除同一词族（lemma 分组规则不变）。
   - **词表输出逐字节不变**：对同一"已投放词集合"，新工具的输出必须与旧工具一致。验收：用固定基线 `162a9e1` 的 `tools/daily_words.py`，在参考库的临时副本上（其 `delivery_log` 放入某个词集合）运行；新工具在同一副本上（状态存储里放入同一词集合、副本的 `delivery_log` 清空）运行；逐字节比较 stdout（含 `--show-evidence`、`--include-stopwords` 各一组）。测试里断言取到的确实是旧版。
   - 旧工具"同一天重跑返回同一批"的行为：新工具不写状态，所以未记录前重跑得到同一批，自然成立；在报告里确认。
   - 输出末尾追加一段可直接粘贴进完成事件的 `vocab.delivered_words` YAML（这是**新增**的用户可见文字，允许）。"已投递完，剩余 N 个"提示保留。
   - 删除的用户可见文字（`delivery_log reset` 提示等）先在报告里列出。

## 不做的

- 不改参考库文件（`eng1_vocabulary.sqlite` 字节不得变化：验收前后对比 SHA-256）。不删 `delivery_log` 表（留给以后整库替换）。
- 不改 `tools/build_eng1_vocabulary.py`、`tools/verify_eng1_vocabulary.py`（它们建库 / 校验库，属于参考数据生产线）；若发现它们依赖 `delivery_log` 写入，写进报告。
- 不改完成事件格式、不改复习推进。

## 测试（只写这些）

1. `tests/contract/test_vocabulary_port.py`：`delivered` 参数的正反例；读取端不再读 `delivery_log`（在临时库的 `delivery_log` 放词，未传 `delivered` 时不排除）。
2. M13：`delivered_words()` 并集、空存储。放 `tests/test_day_plan_store.py`。
3. 迁移工具：dry-run 不写；`--apply` 写出的事件经 `parse_completion_event` 可读且词与日期正确；目标日期已有事件时拒绝。放新文件 `tests/test_migrate_vocab_delivery.py`（临时工作区，参考库临时副本）。
4. `tools/daily_words.py`：上面第 5 条的固定基线逐字节对照；写入被移除（运行前后参考库副本 SHA-256 不变）。放 `tests/test_eng1_vocabulary.py`。
5. 快照：`tests/contract/test_state_snapshot_port.py` 里 `delivered` 取自状态存储。
不写数据量字面量（"15 行"只能来自读库）。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_vocabulary_port tests.test_day_plan_store tests.test_migrate_vocab_delivery tests.test_eng1_vocabulary tests.contract.test_state_snapshot_port tests.test_state_snapshot tests.test_monthly_close
```

（`tests.test_eng1_vocabulary` 里有一项因 `%TEMP%\kaoyan-probe` 缺 PDF 的既有失败，照旧记录，不要修。）
另：`docs/模块地图.md` 的 M7、M13 行更新；§4 缺口表如有 WP-D 行则改写。

## 报告

`review/rounds/round-85-wp-d-luna.md`：改了哪些文件、每条设计的落点、删除的用户可见文字清单、逐字节对照结果、参考库 SHA-256 前后值、迁移工具对**真实**仓库的 dry-run 输出（只 dry-run）、验收输出、建议。
写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。含中文的文件写完查 `???`。
