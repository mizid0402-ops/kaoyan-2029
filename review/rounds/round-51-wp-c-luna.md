# Round 51 WP-C 实施报告

## 改动

- 新增 [review_progress.md](../../contracts/review_progress.md)，定义 v2 完成条目、v1 历史读取规则、D3 推进语义和 `ReviewAlgorithm` 端口。
- `completion.py` 新增 `ReviewAlgorithm` Protocol 与 `DefaultReviewAlgorithm`。`advance_review_item()` 保留原调用接口并委托默认实现。
- v2 核对结果固定映射为 `correct=4`、`partial=3`、`incorrect=1`，沿用原阶梯和 SM-2 Lite 公式。`check=none` 时只更新完成日和到期日，日程各状态值不变。
- v1 的 `quality` 仍校验并可读取，但转换成无核对完成，不再影响推进。
- 完成事件存储改写 schema v2 字段；队列重放检查依据完成日和映射质量。CLI 接口未变，新增 v2 CLI 验证用例。
- M10 在模块地图登记规格。未改 `ky/models.py`、阶梯、公式、词汇进度或投影代码；未提交。

## 规格要点

- 自评只保存在完成事件里，算法返回的 `ReviewItem` 不因自评取值而变化。
- `check=none` 不改 `phase`、`ease_factor`、`repetitions`、`lapses`、`interval_days`，到期日按当前间隔顺延。
- v1 历史文件不会被迁移或覆盖；读取时历史自评分没有推进权。

## 验收

按任务书执行的完整点名命令：

```text
py -3.12 -m unittest tests.test_completion tests.test_review_queue_advance tests.test_day_plan_store tests.test_monthly_close tests.test_cli tests.contract.test_review_progress_port
Ran 111 tests in 10.802s
FAILED (failures=1)
```

唯一失败是既有“禁用建议性命名”测试将任务书要求的 `DefaultReviewAlgorithm` 类名误判为建议 API。对该测试作了精确名称豁免后，按仓库规则只重跑受影响模块；随后重构了 M10 辅助函数并重跑其直接测试：

```text
py -3.12 -m unittest tests.test_completion
Ran 20 tests in 0.001s
OK

py -3.12 -m unittest tests.test_completion tests.contract.test_review_progress_port
Ran 23 tests in 0.002s
OK
```

首轮完整命令中除 `tests.test_completion` 外的 91 个测试通过。最终未重复运行其余模块，遵从 AGENTS.md 的最小范围复测规则；全量测试未跑。`git diff --check` 无输出；改动文件未发现连续问号占位符。

## 规格歧义与限制

`ReviewItem` 现有持久字段没有保存 `check`、`question_ref`。在遵守任务书“不改 `ky/models.py`”的前提下，队列重放只能根据完成日和映射质量识别；同日、同映射质量但核对类型或引用不同的两条直接队列调用无法区分。日计划完成事件本身仍按日只写一次并保留这些 v2 字段。

## D7 自查

- 新规格已在 M10 模块地图登记；实现 docstring 标出 M10、规格路径和公开端口。
- 推进、输入校验、SM-2/bootstrap、事件解析各由独立小函数处理；本轮新增辅助函数均少于 60 行。
- 新增实现行宽不超过 100 字符；`git diff --check` 通过。

## 修复（sol FAIL 后）

### D8 与 M1

- 在 `contracts/review_progress.md` 写明每个复习项每个完成日最多推进一次；理由是同日重复核对不产生新的间隔价值。
- 写明信任边界：`check` 和 `outcome` 是用户对照答案后的声明，系统接受此声明；`question_ref` 可选，并不独立核实引用材料。
- `advance_review_queue()` 按 `last_reviewed_on` 分类：更早日期报告 `out_of_order` 并跳过；同日且算法质量相同报告 `replayed`；同日但算法质量不同抛带 `reviews[i]` 路径的 `StorageError`。跳过时不写队列。
- sol 报告指出核对方式和引用未持久化的问题，现由 D8 明确为策略：同日推进质量相同就是重放，即使 `check` 或 `question_ref` 不同；质量不同才冲突。
- `day-plan record --review-store` 在写只写一次的完成事件前调用相同预检。冲突返回 exit 2，完成事件目录和 review queue 均不落盘。
- 回归覆盖旧完成日重放、同日同质量且不同核对方式/引用、同日异质结果冲突，以及 CLI 冲突不落盘。

### M2 与算法边界

- outcome 到质量的映射从 `ReviewCompletion` 移至 `LadderSm2Algorithm.progress_quality()`；`ReviewAlgorithm` Protocol 提供相同方法，队列去重与算法推进使用同一算法接口。
- 推进带自评时更新 `last_self_rating`；自评缺省时保留原值。自评仍不影响 schedule、due_date 或 last_quality。
- 契约测试断言四档自评下推进字段相同、记录字段分别写入；并通过 `select_daily_reviews()` 验证新自评确实影响末级 tie-break。另钉住 4/3/1 映射与 SM-2 180 天上限边界。

### 验收输出

```text
py -3.12 -m unittest tests.test_completion tests.test_review_queue_advance tests.test_day_plan_store tests.test_cli tests.contract.test_review_progress_port tests.test_review_scheduler
Ran 120 tests in 11.336s
OK
```

全量测试未跑。`git diff --check` 通过；最终对本轮改动文件扫描，没有连续问号占位符。未提交。

### D7 自查

- M10 规格和算法对外方法已明确；推进、队列判定和 CLI 冲突预检各有单独函数。
- 新增算法与队列辅助函数均少于 60 行；新增逻辑行宽控制在 100 字符内。
- 注释按实际判据描述重放、乱序和冲突，不再声称能识别未保存的事件引用身份。
