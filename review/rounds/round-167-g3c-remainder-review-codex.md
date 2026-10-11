# 第 167 轮评审：WP-G3c 余项拆分

## 结论：PASS

按 `AGENTS.md` 的日常单用户威胁模型，未发现必须改的输出、退出码或写入状态回归。评审对象是工作区尚未提交的 `ky/__main__.py` 与 `tests/test_cli_split_baseline.py`；实现报告只作线索。全量：未跑（按 AGENTS.md）。

## 必须改

无。

## 建议改

**S1：`_snapshot_build` 只有一次调用，且只原样转发参数。** `ky/__main__.py` 中该函数仅把 `config, items, today, target_exam_date, vocab_db, workspace` 传给 `build_snapshot`，没有自己的组装、校验或决策；`snapshot_main` 已只有 35 行。任务书把 `_snapshot_build` 列为拆分点，但本轮评审要求避免纯转发辅助函数。可在 `snapshot_main` 直接调用 `build_snapshot`，或让该辅助真正负责一项输入组装职责。复现：在临时归档对 `py -m ky snapshot --config <测试配置> --items <测试队列> --workspace <注册表> --date <当天> --json --vocab-db <词库副本>` 比较两版，均 exit 0、stdout 1094 字节、stderr 0，逐字节相同；因此它是可读性建议，不满足本轮“必须改”的日常故障门槛。

## 不改：已核对的要求

### 固定旧版基线

新增类 `CliG3cRemainderSplitBaselineTests` 明写 `baseline_commit = "24371ee"`，以 `git show 24371ee:ky/__main__.py` 读取旧源码，再用 AST 检查六个旧函数的长度下界。实测旧版/新版行数依次为：`ledger_main` 115/30，`snapshot_main` 90/35，`route_main` 83/9，`resume_main` 76/23，`month_close_main` 95/29，`review_queue_main` 74/22。六个旧值均达到测试断言的下界，取到的是拆分前实现。若提交后把基线改为 `HEAD`，`HEAD` 将指向短函数新版，类初始化时的旧长度断言会失败；在提交前 `HEAD` 恰好还是旧版不能证明这种写法将来可靠。当前固定哈希符合第 12a 条。

### 完整 diff、输出与状态

完整阅读两个待审文件的 diff。各主函数的参数解析、读取、计算、打印及错误捕获顺序与旧版对应；除 S1 外，新辅助函数有具体职责，`route` 和 `review-queue` 按子动作拆分。新增代码行宽检查没有超过 100 字符的行。`_resume_context` 在返回前检查 `latest_freeze > day`；随后才可能调用 `_resume_without_backlog` 或 `_resume_write_plan` 写恢复记录/队列，所以早于未解除冻结的日期仍在任何写入前拒绝。

测试类的 `resume-before-freeze` 场景分别在旧版、新版命令运行后调用 `_assert_no_resume_record`，读取 `DayPlanStore(...).freeze_events()` 并断言没有 `kind == "resume"`；它不只是比较 `(退出码, stdout, stderr)`。该场景预期 exit 2，测试通过。

用 `git archive 24371ee` 展开旧版，在系统临时目录复制工作区新实现和测试，给两份归档补入相同的 47 份登记原始资料（73,005,384 字节）及 `products` 空目录；以 `GIT_DIR` 读取旧提交。`PYTHONDONTWRITEBYTECODE=1` 下运行 `py -3.12 -m unittest tests.test_cli_split_baseline`：5 项 OK；补资料后只重跑新增类：2 项 OK。被测 CLI 和测试只在临时归档运行，未写主仓库状态。

另以同一临时场景路径先后运行 `24371ee` 旧 CLI 和工作区新 CLI，并在两次运行之间重建场景。以下输入均不在新增 12 个对照场景中，实测 `(退出码, stdout, stderr)` 原始字节相同：

| 输入 | 两版结果 | 状态 |
| --- | --- | --- |
| `ledger --workspace <登记注册表> --subject <配置中首科目> --json` | `(0, 11197 字节, 0)` | 只读 |
| `route submit --plan <有效路线 YAML> --store <临时目录>` | `(0, 174 字节, 0)` | 产物文件及 SHA-256 相同 |
| `snapshot --config <测试配置> --items <测试队列> --workspace <登记注册表> --date <当天> --json --vocab-db <词库副本>` | `(0, 1094 字节, 0)` | 只读 |
| `month-close --config <测试配置> --store <空临时计划目录> --year <今年> --month <本月> --json` | `(0, 771 字节, 0)` | 只读 |
| `review-queue migrate --subject <登记科目> --from <有效版本> --to <同一版本> --workspace <登记注册表> --store <空临时队列> --apply` | `(0, 187 字节, 0)` | 空映射链只校验、不写入；两版临时文件相同 |

这些实跑覆盖了新增类未测的筛选、提交成功、词库、JSON 月结和迁移 apply 分支；不据此声称穷尽所有输入。

## 安全登记

本轮未发现需要按恶意输入、手工篡改内部文件或精确竞态单列的新增安全问题。
