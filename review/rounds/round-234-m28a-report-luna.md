# 第 234 轮 WP-M28a 实施报告（luna-a）

## 改动

- `ky/workspace.py`、`contracts/workspace.md`：增加可选 F 键 `settings.pacing` 和 `Workspace.pacing`；主注册表与本地补充注册表均可登记。沿用严格未知键、重复键、`local.` 错误路径和 `local_sha256` 处理。
- `ky/schedule/completion.py`、`ky/storage/day_plan_store.py`、`contracts/review_progress.md`：完成事件可选记录 `study_minutes`。缺失仍按 v2 序列化；提供非负整数（含 0）时按 v3 序列化。v1/v2/v3 均可读，v1/v2 解析为 `None`。
- 新增 `ky/pacing/`：实现设置校验、半月/月周期（内部右开）、报告映射与哈希、报告校验和只写一次存储，以及 `ky pacing report` CLI。
- 新增 `tests/contract/test_pacing_port.py`；补充 `tests/test_completion.py`。未改路线、M8、输入包、护栏、资料或模块地图。

## 做法与边界

- 设置字段按 §2 拒绝未知项、重复 YAML 键、布尔整数、非法日期、无效 cadence 边界；周期覆盖 2026 示例、闰年与平年 2 月，并确认 `start` 前无周期。
- 报告从一次读取的日计划、完成事件、冻结事件和复习队列快照构建。复习按 `completed_on` 归期；同一 `completion_id` 取最早 `event.day`；队列找不到的复习不猜科目。积压使用生成日 M12 口径，冻结锁存只计算终日及之前的事件，`previous` 只读取紧邻周期报告。
- 此包的逐日 `base` 与 `reference_minutes` 暂用 `daily_base_minutes(config)`；两个来源说明字段标注“按生成时来源重算”。这是 M28b 替换基数解析前的任务书限定。
- 报告通过临时文件写入、重读校验和 `os.link` 不覆盖发布。重复运行读回原报告；当前来源变化时输出指定提示。
- `sources` 收录已读文件的工作区相对 POSIX 路径与原始字节 SHA-256，包括本地补充注册表和被读取的上一周期报告。
- CLI 的 `--config` 未给出时，使用注册的 `settings.exam_config`；未登记时回退到工作区根目录的 `kaoyan_config.yaml`。纯计算不读取系统日期，缺省 `--today` 仅在 CLI 装配时取一次。

## 验收

按任务书指定范围执行：

```text
py -3.12 -m unittest tests.contract.test_pacing_port tests.contract.test_workspace tests.test_completion tests.contract.test_day_plan_store_port tests.contract.test_state_sources_port tests.test_cli
```

测试输出原文：

```text
Ran 146 tests in 37.529s

OK (skipped=3)
```

固定提交 `dcbb5b6` 的旧版来源由 `tests/_baseline_harness.py` 读取并断言身份；主注册表合成夹具没有本地补充文件。无 `study_minutes` 的 day-plan record 文件、preflight 文本、preflight `--json` 和 `planner-input --kind day` 的进程输出与写入文件树均逐字节一致。

```text
全量：未跑（按 AGENTS.md，由决策者提交前统一跑）
```

`git diff --check` 通过；含中文文件已扫描连续问号占位串，无匹配。未提交。

## 歧义与选择

- §3 的“注明按生成时来源重算”没有固定映射键名；实现将说明放在 `base.source_note` 与 `reference_source_note`，不改变数字字段本身的类型。
- `sources` 明确按实际被读取的来源收集。上一周期报告存在时，其原始字节摘要也纳入本次 `sources`；缺失时不向更早周期回找。
- 报告只包含实际出现复习完成的科目行、以及有分钟记录的 `due_next` 科目行；未出现的科目不虚构观测值。任务书未要求补零行。

## 第 243 轮返工

- **A1**：将 `build_report` 拆为输入校验、周期日、复习/队列/冻结统计及映射构造辅助函数；将 `_validate_report` 拆为外形、周期、正文统计和完整性校验函数。报告契约测试将拆分前映射作为 fixture，仅替换本轮规定的 `base.source_note` 并重算 hash 后逐字段比较。`report_to_mapping` 文档注明浅拷贝语义。
- **A2**：未提供 `--config` 且未登记 `settings.exam_config` 时抛契约错误，要求显式传参或登记键；测试检查退出 2 且没有发布目标报告。
- **A3**：装配层各加载一次手填可用性、课表和已登记路线，传入纯报告函数；逐日用 `resolve_day_budget` 汇总 M8 总分钟，冻结日期照算。可用性来源摘要与课表、路线摘要一并进入 `sources`；已登记可用性文件缺失/无效由现有 loader fail-closed。报告基数说明按要求注明 M28c 后续接入。合成用例覆盖手填 0 得 1680，以及单日课表 120 降至 75 少计 45。
- **A4**：计划、队列和路线 store 返回的相对路径先拼接其登记目录，再转为工作区根相对 POSIX 路径；课表来源使用端口提供的路径。外部配置来源以 `external:<绝对 POSIX 路径>` 记名。摘要均复用各 loader 同次读取得到的摘要。CLI 用例覆盖 `data/plans/...`、`data/queue/manifest.yaml`、实际分片路径和工作区外配置。
- **规格与回归**：§3 明确 `base.source_note`、`reference_source_note` 固定文案，并注明 `reviews` / `due_next` 为稀疏映射，缺行不代表 0。用例还覆盖来源变更提示及拆分前后报告映射一致。

验收命令原文及输出：

```text
py -3.12 -m unittest tests.contract.test_pacing_port tests.contract.test_workspace tests.test_completion tests.test_cli
.......ss......s...............................................................................
............................
----------------------------------------------------------------------
Ran 122 tests in 48.362s

OK (skipped=3)
```

全量：未跑。
