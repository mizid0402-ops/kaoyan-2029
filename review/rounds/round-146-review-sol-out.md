# Round 146 评审：WP-G3c（`8c86fbf`）

## 方法与范围

将 `git archive 8c86fbf` 展开到系统临时目录，补入上一轮临时副本保存的 47 份原始资料（73,005,384 字节）及 `products` 空目录。旧入口只用指向主仓库对象库的 `GIT_DIR` 读取 `b867ae7:ky/__main__.py`。运行和改写均在临时归档；换序时设 `PYTHONDONTWRITEBYTECODE=1` 并清除相关 `.pyc`，每次恢复源码。评审输入未取自主仓库工作区；主仓库只写本报告。没有跑全量测试。

## 必须改

### M1：`record-needs-question` 实际没有测到出题建议成功路径

`tests/test_cli_split_baseline.py` 的 `_write_registry(question=...)` 用 `_write_yaml` 写入 `data/weights.json` 和 `indexes/questions.json`。`candidate_check_questions` 用 `json.loads` 读取，因而 `record-needs-question` 虽使 `needs_check_review_ids=['record-review']`，却得到 `check_question_candidates=[]`，并在 `check_question_suggestions_skipped` 报 `reference.topic_weights: cannot read registered JSON`。这组对照只测到了建议查询失败；文本模式下 `_day_plan_record_print_suggestion` 也没有被调用。任务书要求覆盖“需要核对出题”，现有标签与实际路径不符。

可复现：在归档用 `_record_case(root, 'record-needs-question')` 建场景，运行现版 CLI 并解析 stdout JSON，可见候选数 0 和上述 skip 原因。把两份 `.json` 临时文件按其已生成的数据改用 `json.dumps(..., ensure_ascii=False)` 写回后，旧版和新版都返回 0，候选集合数 1、其中候选题数 1、无 skip，`(退出码, stdout, stderr)` 逐字节相等；去掉 `--json` 后，文本建议也逐字节相等。请让测试夹具写真正的 JSON，并断言确实进入候选和文本建议路径。

### M2：record 写入后失败分支与写入前门禁的状态顺序未被对照锁住

现有 `record-queue-failure` 令完成事件引用队列中不存在的 ID：`preflight_review_queue` 先报 `reviews[0].review_id: unknown review_id`，退出 2，`day-plans/` 下没有完成事件。它不覆盖任务书所指的“事件已写，但队列未推进”。在有效的 `record-review-success` 场景中，临时把新旧模块的 `advance_review_queue` 同样替换为抛出 `ContractError('forced advance failure', 'queue')`：两版均退出 2，stderr 逐字节相同，完成事件文件均已写入。将新入口该分支的 `but the review queue was not advanced` 改为别的文字，现有 record 对照测试仍为绿色，证明该分支未被测到。

另外，在有效的 `record-review-success` 场景里，同样让 `_latch_freeze_if_needed` 抛出 `StorageError('forced freeze write error', 'freeze')`：旧版与未修改新版均退出 2，完成事件未写。临时调换 `_day_plan_record_freeze` 与 `_day_plan_record_write` 的顺序后，退出码、stdout、stderr **仍与旧版相同**，但完成事件已经写入。现有对照只比较三元组，无法发现这类正常写入失败后的状态错误。请给写入后失败分支加定向对照，并在失败场景断言完成事件是否存在；冻结检查必须先于事件写入。

### M3：多处同时出错时的首报顺序仍有多处测试盲点

在临时源码中逐对调换主流程可独立执行的相邻步骤，再运行对应的 `tests.test_cli_split_baseline.CliSplitBaselineTests` 单个测试方法，得到：

| 调换步骤 | 对照结果 |
| --- | --- |
| preflight 日期 / usage | 红：`preflight-order-probe` |
| preflight usage / 上下文加载 | **绿** |
| preflight 上下文加载 / 策略校验 | **绿** |
| preflight 冻结字段加入 JSON / JSON 输出 | **绿** |
| preflight 文本摘要 / 复习列表 | 红：正常文本等场景 |
| preflight 复习列表 / 新内容分配打印 | 红：正常文本等场景 |
| submit 工作区及存储路径 / 配置加载 | **绿** |
| record 工作区及存储路径 / 配置加载 | **绿** |
| record 配置加载 / 完成事件解析 | **绿** |
| record 完成事件解析 / review-store 构造 | **绿** |
| record 队列预检 / 冻结检查 | **绿** |
| record 冻结检查 / 事件写入 | **绿**，且有 M2 所示状态差异 |

这些是可直接换序的步骤；解析器产生 `args`、队列推进依赖 `report`、输出依赖 `queue_state` 等边不能直接互换。双错误输入可复现未锁住的首报次序：从 `_preflight_case(..., 'preflight-usage-json')` 再将 `config.yaml` 换为 `config-weights-not-closed.yaml`，旧版先报 usage JSON 错误；从 `_submit_case(..., 'submit-plan-success')` 再将注册表写成 `schema_version: [\n` 且配置换成同一无效配置，旧版先报注册表；从 `_record_case(..., 'record-no-registry')` 将配置换成无效配置并删除 `done.yaml`，旧版先报配置。上述换序测试仍绿，因为 28 组没有相应双错误。冻结 JSON 也未覆盖：两个冻结场景都是文本，唯一 JSON preflight 场景未冻结，故先输出 JSON、再加入 `freeze` 字段的变异仍绿。请补有意义的双错误组合及冻结 JSON 场景，固定首报与字段输出。

### M4：`_day_plan_record_advance` 混合了两项职责

`ky/__main__.py` 的 `_day_plan_record_advance` 先推进 review queue（`ContractError` 使命令退出 2），又重新加载队列并查询出题候选（`ContractError` 被转换为 `skip_reason`，命令继续成功）。二者有不同的失败语义和独立的复现输入：`record-review-success` 只推进；修正 M1 的两份 JSON 后，`record-needs-question` 才实际查询候选。任务书把“队列推进、出题建议”列为不同步骤，`AGENTS.md` 要求一个函数做一件事；现名称也掩盖了第二项。请拆成推进和候选查询两个命名步骤，同时保持原错误顺序与输出。

## 建议改

**S1：让步骤函数的返回形状显式表达成功或退出。** `_day_plan_record_workspace` 返回四元组或整数 `2`，`_day_plan_record_event` 返回事件或整数 `2/3`，`_day_plan_record_write` 返回报告或整数 `2`，`_day_plan_record_advance` 返回三元组或整数 `2`；调用方反复用 `isinstance(value, int)` 区分。当前没有观察到误判，但类型签名缺失，今后新增分支容易漏处理。可用具名结果类型或显式错误结果，使成功值和退出码各有固定形状。可复现输入：阅读 `_day_plan_record` 中四处 `isinstance(..., int)` 分派及各 helper 的返回语句；不要求本包改变现有 CLI 行为。

## 不改：已确认一致的行为

- 基线钉在 `b867ae7`，测试还断言旧 `day_plan_main` 超过 200 行；每个场景重建临时输入与写入存储，并逐字节比较 `(returncode, stdout, stderr)`。现有 12 组 preflight、6 组 submit、10 组 record 均通过，但 M1–M3 所列路径未覆盖。
- `py -3.12 -B -m unittest tests.test_cli_split_baseline`：3 项 OK；`py -3.12 -B -m unittest tests.test_cli`：47 项 OK。另逐字节比较了 `preflight -h`、`day-plan submit -h`、`day-plan record -h` 和缺少 day-plan 动作的用法输出，均一致。未跑全量。
- 28 组中，满载场景实际输出 `over capacity: YES`，违规配置退出 2，冻结两例实际输出 `FROZEN`；submit 的手填上限错误实际包含 single-item bound；record 有/无 `--store`、有/无 `--review-store`、注册表找不到/无效/有效和 JSON/文本均进入相应分支。M1 的出题候选是例外。
- 对照源码阅读未发现已修改实现与 `b867ae7` 的确定性输出差异。所有新增私有函数均小于 60 行；除 M4 外，函数职责与名称基本相符。变异完成后，临时 `ky/__main__.py` 与 `git show 8c86fbf:ky/__main__.py` 原始字节相同，SHA-256 均为 `7bc82538617b6c01538b781006a0f52911cc0171389b73f0417242ced22df9a4`。

## 安全登记

本轮未发现需按恶意输入、手工篡改内部文件或精确竞态单列的新增安全问题。M2 的模拟写入失败用于检验日常故障恢复顺序，属于本包验证范围。

## 结论

**WP-G3c FAIL。** 已覆盖的调用未见新旧输出差异；对照测试未覆盖正常出题、写入后失败及多处错误的多段首报，且无法发现冻结失败后误写事件的顺序回归；`_day_plan_record_advance` 仍合并了任务书要求分开的职责。
