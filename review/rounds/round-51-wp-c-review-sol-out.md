# Round 51 WP-C 复习推进端口独立评审

**结论：FAIL。** `88474d4` 的纯算法与 v2/v1 解析基本符合本轮规格；两个需在合并前处理的问题是：旧事件乱序重放会重复推进，以及 D3 允许的自评排序信号无法进入裁剪核。审查与测试均在 `F:\workspace\kaoyan-wt-wp-c` 的 `88474d4` 进行；主工作区除本报告外未改动。

## 1. D3、硬不变量③与推进规则

| 项目 | 判断 | 证据与意见 |
| --- | --- | --- |
| `check: none` 的四档自评 | **不改 / PASS（就排程而言）** | `contracts/review_progress.md:28-33`；`ky/schedule/completion.py:125-148` 在 `progress_quality is None` 时沿用原 `schedule`，到期日固定为 `completed_on + 当前 interval_days`，与自评值无关。契约测试 `tests/contract/test_review_progress_port.py:48-70` 遍历四档；本机单跑 3/3 通过。另用 `interval_days=7` 实测四档均得到 `2026-10-02`、原 schedule 不变。这里到期日因“完成”而重排，不因自评分而变化；这是 D3 `docs/阶段2.5-接缝收口.md:121-123` 对 README 硬不变量③的具体解释。 |
| 有核对的映射与阶梯 | **不改 / PASS** | `ky/schedule/completion.py:53-55,175-226` 将 correct/partial/incorrect 映为 4/3/1；失败重置 1 天、计 lapse，及 fixed-bootstrap、SM-2 Lite 路径与父提交原算法一致。用 `git show 88474d4^:ky/schedule/completion.py` 取得旧实现，在 5 个 fixed-bootstrap phase 和 3 组 SM-2 边界状态上对三个 outcome 共比对 24 个返回值，输出 `checked output equality: 24`。`tests/test_completion.py` 20/20 通过。 |
| v1 旧事件 | **不改 / PASS** | `ky/schedule/completion.py:312-321` 校验历史 `quality` 0..5 后生成 `check="none"`，不把它带入推进；`contracts/review_progress.md:16-18` 明确有意改变历史推进语义。`tests/contract/test_review_progress_port.py:91-109` 的 v1 quality=5 测试通过。 |
| D3 自评仅作裁剪排序末级信号 | **必须改 / FAIL，M2（MAJOR）** | 决议 `docs/阶段2.5-接缝收口.md:122` 要求自评可用于裁剪排序末级 tie-break；实际裁剪核只读 `ReviewItem.last_self_rating`（`ky/schedule/review_clip.py:197-213`），但推进器始终复制旧值（`ky/schedule/completion.py:148`），并且规格 `contracts/review_progress.md:32-33` 反而规定自评不得改写复习项。实测 `unknown/vague/basic/fluent` 四次推进返回的 `last_self_rating` 全为 `None`，因此刚记录的自评不会参与排序。**最小修法**：先修订端口规格，将 `last_self_rating` 列为允许更新的排序元数据；推进时有新自评就写入该字段，无新自评保留旧值。契约测试应只断言 schedule、due_date、last_quality 对四档相同，并另断言 tie-break 字段及裁剪排序，不能继续要求整个 `ReviewItem` 完全相同。此修改不赋予自评推进权。 |

**证据边界**：`question_ref` 在规格中明确是可选项（`contracts/review_progress.md:12-14`），实现允许无引用的 `check + outcome`（`ky/schedule/completion.py:332-358`；`tests/test_cli.py:511-515`）。因此当前系统只能确认调用者声明了核对方式和结果，不能独立证明实际核对材料；“有锚点”若指可追溯材料，需另行收紧规格或明确人工声明的信任边界。此处是设计语义待明确，未将其伪装成违反现有字段规格的代码缺陷。

## 2. 队列重放与幂等键

**必须改 / FAIL，M1（MAJOR）。** `ky/storage/day_plan_store.py:343-354` 仅以复习项当前保存的 `(last_reviewed_on, last_quality)` 与待处理的 `(completed_on, progress_quality)` 比较；它只能识别“最后一次事件的紧邻重放”，不能识别较早事件的重放。

- **已复现重复推进**：临时目录中顺序应用 `2026-09-12 correct`、`2026-09-14 correct`、再次应用首条。三次报告都显示 `advanced_review_ids=('rv1',)`；phase 依次为 `1 → 2 → 3`，最后 `last_reviewed_on` 从 `2026-09-14` 倒退至 `2026-09-12`。预期第三次是无推进的重放。两条不同日期事件都符合完成记录格式，故这是实际可达的历史补放/重建顺序问题。
- **已复现漏推进的条件**：先以 `event.day=2026-09-12, completed_on=2026-09-12, check=past_question, outcome=correct, question_ref=q1` 推进，再以 `event.day=2026-09-13, completed_on=2026-09-12, check=exercise, outcome=correct, question_ref=q2` 推进，第二条返回 `skipped_review_ids=('rv1',)`，phase 留在 1。`parse_completion_event` 没有要求 `completed_on == event.day`（`ky/schedule/completion.py:294-321`），而 `DayPlanStore` 只限制每个 **event.day** 一个文件（`ky/storage/day_plan_store.py:508-515`），所以这两条可各自落盘。若业务允许同日同项多次核对，它是漏推进；若业务规定同日最多推进一次，就应在规格中写明，并在输入边界拒绝第二条，而不是称其为“同一事件重放”。
- **同日不同结果也会重复推进**：直接依次应用同日 correct、partial、再重放 correct，phase 为 `1 → 2 → 3`，因为质量 4/3/4 每次不同。当前公开的 `advance_review_queue` 接受这样的 `CompletionEvent`；写一次事件文件的常规 CLI 路径不会自然生成同日两个事件，但端口没有阻止。

**最小修法取决于同日语义**。若约定每项每完成日最多一次：在端口规格写明，较早 `completed_on` 一律跳过或拒绝，同日不同核对结果报冲突；同日同结果只有在“同一事件”可证实时才报告为重放，并约束 `event.day` 与 `completed_on` 的关系。此方案可复用现有 `last_reviewed_on`，不必新增 `ReviewItem` 字段。CLI 在写入不可覆盖的完成事件之前应做同样的冲突预检，否则冲突会留下“事件已落盘、队列未推进”的状态（`ky/__main__.py:621-635`）。

若业务必须允许同日同项多次核对：给每条完成记录稳定 ID，并在队列投影保存**已处理 ID 集或可重建的事件账本**。只加 `ReviewItem.last_completion_id` 仍挡不住“旧事件在新事件之后重放”。代价包括完成事件 schema、`ReviewItem` 模型与校验、`review_shards` 序列化/旧分片兼容、队列重建顺序和契约测试；不建议在未确定该业务语义前临时加字段。

## 3. D7 可读性与测试

| 项目 | 判断 | 证据与建议 |
| --- | --- | --- |
| “重放”注释过度承诺 | **建议改 / PASS（可读性）** | `ky/storage/day_plan_store.py:302-304,311-314,349-350` 把日期和质量相同称为“exact / identical completion”，但 `check`、`question_ref`、事件身份都没比较。先修 M1，再让注释只描述实际判据和被接受的同日策略。 |
| 映射责任跨越模块边界 | **建议改 / PASS（可读性）** | 规格 `contracts/review_progress.md:21-26` 说映射属于 `ReviewAlgorithm`，实现把映射放在 `ReviewCompletion.progress_quality`（`ky/schedule/completion.py:78-82`），队列存储还直接依赖该属性（`ky/storage/day_plan_store.py:347-348`）。当前默认算法正确，但将来替换算法时“质量映射”和“去重键”会散在两个模块。宜定义单一公开语义/端口，让算法与队列共用，避免替换时漏改。 |
| 契约测试的检查强度 | **建议改 / PASS（测试自身）** | `tests/contract/test_review_progress_port.py:72-89` 只断言 correct/partial 的 phase 大于原值，不能单独发现 4/3 映射互换、SM-2 ease 或边界公式变化。父提交对照的 24 组实测未见偏差；修 M1/M2 时补一组精确映射及边界断言即可，不需扩大到全量测试。 |

## 验证与修复交接

- `py -3.12 -m unittest tests.contract.test_review_progress_port` → 3/3 PASS。
- `py -3.12 -m unittest tests.test_completion` → 20/20 PASS。
- `py -3.12 -m unittest tests.test_review_queue_advance` → 9/9 PASS。
- `py -3.12 -m unittest tests.test_day_plan_store` → 16/16 PASS。
- `py -3.12 -m unittest tests.test_cli` → 28/28 PASS。
- 未跑全量测试；复现脚本未写入仓库，队列写入仅在系统临时目录。

**修复包**：M1 先明确同日推进次数与乱序策略，再增加“旧事件在新事件后重放”“同日同质不同引用”“同日异质冲突”的定向回归；M2 统一 D3、端口规格与 `last_self_rating` 更新规则，并验证裁剪核确实读取到新自评。两项修复前不建议合并。
