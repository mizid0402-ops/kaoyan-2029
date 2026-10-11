# 第 147 轮：F-b 复审与 WP-F-c 评审

审查基线分别是独立临时目录中的 `git archive 74ec415`、`git archive ec832c7`；补入原始资料与空 `products` 目录。固定提交对照使用 `GIT_DIR=F:\workspace\kaoyan-ai-system\.git`。仅在归档中运行，变异测试均设置 `PYTHONDONTWRITEBYTECODE=1`。严重度按个人本机正常使用判断；本轮未跑全量。

## 一、F-b 复审：`74ec415`

### 必须改

无。第 142 轮 B1 已修复。

### 建议改

无。

### 不改：B1 的定点复核

`tests/contract/test_learning_state_projection.py` 现在在 `day-plan record --review-store` 和 `ky resume` 各自重建后，按 `review_id` **从投影**查询 `review_items`，将 `state`、`due_date`、`last_reviewed_on`、全部 `schedule_*`、延期与反馈字段同写后队列对象核对；同时确认写前、写后发生了应有变化。原始单条测试通过：`Ran 1 test ... OK`。

可复现变异：只在 `74ec415` 临时归档改 `ky/projection/learning_state.py` 的 `_review_rows` 输出，每次运行
`$env:PYTHONDONTWRITEBYTECODE='1'; py -3.12 -m unittest tests.contract.test_learning_state_projection.LearningStateProjectionTests.test_real_cli_writes_are_visible_after_rebuild`，随后撤销该次变异：

| 临时改值 | 实测结果 |
|---|---|
| 全部 `due_date` 改成 `1900-01-01` | 测试失败，`recorded-review` 的投影日期与写后队列日期不等。 |
| 全部 `state` 改成 `invalid-state` | 测试失败，投影状态与写后队列的 `queued` 不等。 |
| 全部 `interval_days` 改成 `-999` | 测试失败，投影间隔与写后队列的 `4` 不等。 |
| **只把 `resume-review` 的 `due_date` 改成 `1900-01-01`** | `record` 核对通过，测试在 `resume` 后的投影核对处失败；证明恢复分支也独立受守护。 |

四次变异均以测试退出码 1 告终；撤销后 `learning_state.py` 的 Git 哈希与 `74ec415` 对象一致，均为 `bdafffc047315076289538538ffd16317c8aa806`。这些探针检验了验收断言，不表示原提交有错误数据。

### 安全登记

未发现新增安全问题。

**F-b：PASS。** B1 的必需契约断言已能抓住记录与恢复后的投影队列错误；本次复审未扩大到其他实现范围。

## 二、WP-F-c 评审：`ec832c7`

### 必须改

无。以下结论只针对本轮规格和任务书列出的正常使用路径。

### 建议改

无。未把可选的防篡改校验或额外测试列为本轮返工。

### 不改：已确认的行为

1. **M12 口径与旧输出。** `count_review_items_by_subject` 只按传入的 `ReviewItem` 序列和日期计算：`queued/scheduled` 均计入队列，只有 `queued` 且到期日等于查询日计入今日到期，小于查询日计入积压。它按科目给计数；`build_snapshot` 仍按配置科目原顺序补零项行。契约测试用 `git show b867ae7:ky/schedule/state_snapshot.py` 固定旧实现并确认不是新版，在同一输入上比较快照 JSON 原始字节；含零项科目、`scheduled`、查询日前/当天/后到期项，测试通过。另以同一队列分别查询 D−1、D、D+1，M12 与 M15 每科四项计数三次均相等。这个“必然同数”以**同一已重建队列和有效配置**为前提；队列写后未重建时，两个端口读的不是同一份状态。
2. **对象还原与冻结。** `status.py` 将投影的全部 `review_items` 列映射回 `validate_review_item` 的公开输入形状，包括扁平 `schedule_*` 重新嵌套、`last_self_rating → self_rating` 与 ISO 日期。独立探针从测试投影读出四个对象，与 `ReviewShardStore.load()` 的对应对象逐项比较，结果 `equal=True`。冻结事件按序还原，调用 M27 的 `latch_active` 与 `assess_freeze`；JSON 总含 `frozen` 布尔，仅冻结时含 `resume`。测试还覆盖过去日期仍采用**当前投影事件锁存**，与“非历史回放”一致。
3. **按日期展示的事实。** 查询返回当天当前计划及科目分钟、完成事件存在性、手填分钟、半开区间 `start <= D < end_exclusive` 命中的路线阶段及各科分钟；缺项分别为 `null` 或 `false`。规格把 `as_of` 定义为“按 D 评估最近一次成功重建的投影事实”，明确不是历史回放，也不承诺反映刚才的写入。CLI 文本写“latest successful rebuild”；规格中“实时积压”只出现在否定旧计划字段被当作实时量的说明中。未发现学习建议、推荐、优先级或下一步任务字段；冻结时的 `resume` 是 M27 已有的恢复操作提示。
4. **只读、错误与旧命令。** SQLite 用 `mode=ro` 打开，先查 schema 版本及所需表/列；查询前后投影字节相等。缺文件抛带投影路径的 `ContractError`，独立探针确认没有创建空库；测试中的 schema 2 返回版本错误。另从有效 schema 3 测试投影复制一份、删除 `day_plans` 表，独立探针得到“`projection tables are missing (day_plans); rebuild it`”。队列科目不在本次配置中被模型公开校验器拒绝；CLI 既无显式 `--config` 又无注册表 `settings.exam_config` 时返回退出码 2 和设置方法，显式配置可用。旧重建命令的 JSON 输出与固定 `b867ae7` 基线逐字节相同；独立对照其非 JSON 文本输出与错误输出也逐字节相同。

可复现的最小验收命令（在 `ec832c7` 归档内设置 `GIT_DIR` 后运行）：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:GIT_DIR='F:\workspace\kaoyan-ai-system\.git'
py -3.12 -m unittest tests.contract.test_learning_state_projection tests.contract.test_projection_status tests.contract.test_state_snapshot_counts_baseline tests.test_projection_service tests.contract.test_state_snapshot_port
```

实测：`Ran 25 tests in 10.882s; OK`。这不是全量测试。上述对象相等、三日期计数、schema 3 缺表和旧命令文本输出另做了定点探针；实现者报告里的其他变异结果未当成我的独立测量。

### 安全登记

未发现本轮新增的恶意输入、链接或竞态类安全问题。手工篡改 SQLite 内部值后的全面防护不属于当前个人本机正常使用的阻断范围；本轮保留既有只读打开和契约校验，不要求扩展防护。

**F-c：PASS。** 指定功能、错误边界与旧重建入口已通过定点验证；前端写后重建与运行中 `serve --immutable` 的连接刷新仍按既定 W2 边界处理。
