# 第 171 轮评审：WP-G3f / WP-G3g 拆分

评审对象是 `master=24371ee` 上的指定未提交改动。两份实现报告只作定位线索；`ky/__main__.py`、`tools/` 及其他包的改动未纳入结论。用 `git archive 24371ee` 建立旧版临时树，将本轮 11 个实现文件和 2 个新增测试复制到新版临时树，两树各补相同的 47 份原始资料（73,005,384 字节）与 `products` 空目录。评审末再次比较工作区与临时新版这 13 个文件的 SHA-256，均相同。全量：未跑（按 AGENTS.md）。

## WP-G3f（`ky/schedule/`）：PASS

### 必须改

无。

### 建议改

无。

### 不改：固定基线、函数职责与行为

新增 `test_schedule_split_baseline.py` 明写 `BASELINE_COMMIT = "24371ee"`，以 `git show 24371ee:<文件>` 取得五份旧源码，对六个旧长函数逐一作 AST 长度下界断言；没有使用 `HEAD`。实际逐文件扫描结果如下（行数含空行、注释和 docstring；辅助函数列给出本轮新增函数的最大长度）：

| 文件 | 文件总行数旧→新 | 目标函数旧→新 | 新辅助最大行数 |
| --- | ---: | --- | ---: |
| `review_clip.py` | 495→507 | `select_daily_reviews` 173→48；`_select_with_subject_quotas` 62→34 | 31 |
| `monthly_close.py` | 219→234 | `close_month` 120→42 | 29 |
| `longitudinal.py` | 301→332 | `check_invariants` 104→44 | 17 |
| `state_snapshot.py` | 285→317 | `build_snapshot` 93→39 | 27 |
| `completion.py` | 416→430 | `parse_completion_event` 68→15 | 47 |

辅助函数分别负责配额校验/选择、月计划去重/累计、单条不变量、单科快照、完成记录分段解析等实际步骤，没有仅转发参数的新增函数。`select_daily_reviews` 在容量算术前验证配额，返回前仍执行 `expected - accounted` 检查；月结先按输入顺序留每日期第一份，再按日期排序；五条不变量、快照的两道前置校验与覆盖优先级、完成事件字段顺序均保留。对临时新版的 `ky/schedule/` 逐函数 AST 扫描，没有超过 60 行的函数。

最小对照命令 `py -3.12 -m unittest tests.contract.test_schedule_split_baseline`：5 项 OK。另用两棵完整归档分别运行同一独立输入，并以原始 UTF-8 字节比较包含完整数据类字段的输出：

- 配置与复习项从夹具读取，取两个活跃科目，日预算覆盖为 40 分钟。一个非紧急项先占 10 分钟，另一个 `defer_count=2` 的紧急项占 10 分钟。无科目配额时软目标 18、硬上限 24，两项均入选，紧急项借用了软目标之外的容量；科目配额分别为 10 和 5 时软目标 15、硬上限 24，两项也均入选，紧急项借用了自身配额之外的容量。旧/新所选 ID、分钟、全部结果字段字节相同。这两组不在新增基线测试的输入里。
- 同一日期给月结三份计划（可用分钟 21、42、63），另一天一份 12 分钟计划。旧/新均只累计第一份，`available_minutes=33`，并给该日期一条 `3 day-plan entries supplied ... only the first was counted` 违规；完整月结对象字节相同。这不同于新增基线测试的两份重复计划。

若提交后把固定哈希改成 `HEAD`，`HEAD` 会指向短函数新版，六个旧长度断言会失败；提交前 `HEAD` 恰为旧版不足以证明测试长期有效。当前写法满足 `AGENTS.md` 第 12a 条。

## WP-G3g（存储、台账、冻结与恢复）：PASS

### 必须改

无。

### 建议改

无。本轮不把 S19 的旧有并发发布问题转成纯拆分返工项，见安全登记。

### 不改：固定基线、函数职责与行为

新增 `test_storage_ledger_split_baseline.py` 固定 `BASELINE_COMMIT = "24371ee"`，逐文件用 `git show 24371ee:<文件>` 读取旧实现，并对下表全部七个目标函数（`material.py` 两个）作 AST 长度下界断言；没有使用 `HEAD`。实际逐文件扫描：

| 文件 | 文件总行数旧→新 | 目标函数旧→新 | 新辅助最大行数 |
| --- | ---: | --- | ---: |
| `review_shards.py` | 794→872 | `_commit` 114→23 | `_publish_commit` 52 |
| `day_plan_store.py` | 1009→1020 | `write_day_plan` 63→11 | `_commit_day_plan` 50 |
| `material.py` | 808→864 | `validate_material` 131→55；`_load_rights` 72→31 | 56 |
| `citations.py` | 238→215 | `check_knowledge_point_citations` 102→37 | 40 |
| `resume.py` | 197→210 | `plan_resume` 62→38 | 35 |
| `ledger_restore.py` | 185→185 | `restore_materials` 66→19 | 45 |

新增辅助分别负责读取旧分片、准备清单、发布、写前护栏、字段/权限校验、单条引用拒绝、逾期分配和单行恢复；均执行具体工作，没有只转发参数。另对临时新版 `ky/schedule/`、`ky/storage/`、`ky/ledger/`、`ky/freeze/`、`ky/projection/` 及该恢复文件共 27 个 `.py` 文件逐函数扫描，超过 60 行的函数为零。`write_day_plan` 的不变量、可用时间、冻结护栏先后顺序未变；材料与引用错误路径/理由的先后顺序未变。

最小对照命令 `py -3.12 -m unittest tests.contract.test_storage_ledger_split_baseline`：6 项 OK。独立旧/新进程探针还验证了新增测试之外的这些输入：

- `plan_resume` 放入同一夹具项的两份副本：逾期恰等于当前间隔者为 `recent_overdue`，大一天者为 `possible_forgetting`；分配日期、更新项及完整计划对象字节相同。
- `restore_materials(check_only=True)` 对两条缺失的本地材料逐行处理：`https://[bad` 得 `invalid_url`，合法 URL 得 `needs_download`；没有调用下载函数，临时根仅有预先创建的 `raw` 目录，没有新建下载临时目录。旧/新结果字节相同。
- `ReviewShardStore(shard_size=1)` 先写一项，再增至三项，再移除首项但保留两项。三次提交的 `manifest`、`changed_shards`、`bytes_written`、哈希报告，以及每步存储树的每个文件路径和**原始文件字节**均旧/新相同；第二步报告新增两个分片，第三步报告移除首项所在分片。

上述独立探针把这些结果和存储树文件的十六进制原始字节序列化后，在两棵完整归档中各自执行，均 exit 0、stderr 0、stdout 20,140 字节且逐字节相同。它不取代未运行的全量测试，也不证明未选输入的行为。若把测试基线改成提交后的 `HEAD`，上表旧函数的下界断言会失败；固定提交满足第 12a 条。

## 安全登记

**S19 已登记，事实独立确认。** `git show 24371ee:ky/storage/review_shards.py` 的原 `_commit` 在临时分片验证后用 `os.replace(temp_path, final_path)` 发布分片，再替换 manifest；失败时遍历 `final_paths` 删除，没有 `os.link` 原子不覆盖发布，也没有已发布文件的身份复核。新版 `_publish_commit` 保持该流程。`ky/storage/route_store.py::_write_version` 则使用 `os.link` 和临时文件 inode 身份。`docs/安全风险登记.md` 已有 S19，准确写明此项为基线旧问题。触发需要另一个写者在发布窗口提交同名分片，或清理时删除其文件；可能覆盖/删除另一写者的数据。可能的修法是参考路线存储的硬链接发布及只清理本次发布文件。按个人本机单用户威胁模型，它属精确并发条件的安全登记，不要求 G3g 纯重构返工。
