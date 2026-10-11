# WP-F-a：状态来源读取端口实施报告

## 新接口

- `DayPlanStore.read_state_sources(self) -> DayPlanStateSources` 返回不可变的
  `plans: tuple[DayPlanRecord, ...]`、`completions: tuple[CompletionEvent, ...]`、
  `freeze_events: tuple[FreezeEvent, ...]` 和只读 `sources: Mapping[str, str]`。
  `DayPlanRecord` 是当前 `DayPlan`、版本号、`actor` 与 `input_hash`；旧计划版本和月结不返回。
- `ReviewShardStore.read_state_sources(self) -> ReviewQueueStateSources` 返回与 `load()` 等值、
  同顺序的 `items: tuple[ReviewItem, ...]` 和只读 `sources`。
- `RoutePlanStore.read_state_sources(self) -> RoutePlanReadResult` 返回 `route: RoutePlan | None`
  和只读 `sources`。仅当前版本进入来源映射。
- `load_availability_with_source(path: str | Path) -> AvailabilitySource` 返回
  `availability: Availability` 与文件 `sha256: str`。

前三个结果类型均为 `frozen` dataclass。`sources` 用 `MappingProxyType` 包装。M13 来源键是
相对各自存储根的 POSIX 路径；availability 的结果针对传入的单个文件，不返回路径映射。
所有摘要均取自传给解析器的同一份原始字节。缺失的计划根返回空结果；缺失队列 manifest
返回空队列和空来源；缺失路线 manifest 返回 `route=None` 和空来源；availability 文件缺失报
`ContractError`。已存在但无效的 manifest、摘要不符、无效事件或错位完成事件均报错。

规格见 `contracts/state_sources.md`；模块地图只更新 M13、M26 两行。

## 撤实现验证

通过测试进程内将对应新读取方法临时替换为不可调用值来撤去端口，没有编辑或保留任何变异代码。
关联契约测试均转红：

| 临时撤去的接口 | 运行数 | 转红数 |
|---|---:|---:|
| `DayPlanStore.read_state_sources` | 5 | 5 |
| `ReviewShardStore.read_state_sources` | 2 | 2 |
| `RoutePlanStore.read_state_sources` | 1 | 1 |
| `load_availability_with_source` | 1 | 1 |

覆盖项包括：多月计划及同日多版本、完成与冻结/恢复事件、来源摘要、排除旧版本和月结、每月
manifest 只读一次、错位完成事件、日计划摘要不符、队列缺 manifest 和分片摘要不符、路线两版本、
availability 摘要与缺失文件。

## 验收

指定命令：

```text
py -3.12 -m unittest tests.contract.test_state_sources_port tests.test_day_plan_store tests.test_storage tests.contract.test_route_plan_port tests.contract.test_availability_port tests.contract.test_freeze_port
```

结果：`Ran 75 tests in 46.568s`，`OK`。之后冻结事件重复序号错误路径做了小幅修正，重跑受影响的新契约模块：
`Ran 9 tests in 0.210s`，`OK`。含中文文件的 UTF-8 编码和文本完整性已检查。

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。未提交。

## 留给 F-b

- 直接消费这些公开读取结果；不要自行解析 M13/M26 状态 YAML，也不要加载对象后重读源文件算摘要。
- 聚合 `sources` 时保留相对根路径命名空间，避免不同存储根下相同文件名冲突；摘要排序/序列化由投影端定义稳定规则。
- 计划结果只代表 manifest 当前版本；队列缺 manifest 是空队列；路线无 manifest 是空路线；availability 的已登记缺文件仍是错误。
- `DayPlanRecord` 来源字段兼容旧 manifest：缺省 `actor` 为 `unknown`，缺省 `input_hash` 为 `None`。

## 建议

F-b 可将合并来源路径和摘要按稳定顺序写入 `state_inputs`，并保留本接口的当前版本语义。约 800 天规模的
投影耗时尚未实测；建议在 F-b 有代表性的临时输入上记录构建时长后再判断是否需要进一步优化。
