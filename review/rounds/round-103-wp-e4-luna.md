# Round 103 — WP-E4 手填可用时间

## 改动与设计落点

- 新增 M26 `ky/availability/` 和 `contracts/availability.md`。`load_availability()` 使用
  `load_yaml_text()`，校验 `schema_version: 1`、顶层字段、日期键和非负整数分钟；datetime
  键及归一化后重复的日期键拒绝并报告字段路径。`resolve_daily_minutes()` 返回分钟数及
  `availability` / `config` 来源；`availability_for_workspace()` 对未登记返回 `None`，登记后
  要求文件存在并读取。
- 工作区根注册表登记 `data/availability.yaml`，并新增符合契约的空文件。工作区契约将该键
  说明为“登记即必须存在”，模块地图登记 M26 并删除 E4 缺口。
- `ky preflight` 显式加载或向上发现注册表后解析当日分钟；仅来源为 `availability` 时才传
  `daily_minutes_override`，配置回落时省略参数。没有发现注册表且未指定时使用配置值。JSON
  容量字段和人类可读的 daily budget 显示解析后的日容量。
- M19 日输入包在键未登记时仍写 `availability: null`；登记后写入解析分钟和来源。手填日期
  参与复习裁剪，配置回落仍不传 override。planner port 规格已说明新字段及回落行为。
- `DayPlanStore` 新增可选 `availability` 参数，在既有纵向不变量之后、写盘之前校验该日手填
  上限；重读临时文件时也复核。未改 `check_invariants`。CLI 的人工计划和 staging 提交均从
  注册表加载可用时间并注入存储器。

## 固定基线逐字节对照

- 测试通过 `git show 79623ee630c49c74944413f43dab0032516c88c0:<文件>` 获取旧版源码，并检查
  旧版 preflight 含原选择器调用且不含 M26 helper；旧版 planner port 保留 `availability: None`。
- preflight 在临时工作目录、登记文件为空日时分别执行旧脚本和当前 CLI，按原始 stdout / stderr
  bytes 比较。另验证未发现注册表时当前 preflight 与旧版输出一致。
- 未登记的 M19 输入包将旧版 `_build_input_data()` 与当前包映射序列化为规范 JSON bytes 比较，
  并断言当前 `availability` 为 `null`。这避免以当前 `HEAD` 误取新版作为基线。

## 验收输出

- 完整任务书命令已运行。第一次结果为 157 项：有 1 个已知错误（`test_workspace` 需要缺失的
  `data/raw_materials/`），另有 2 个新测试样例问题；已修正样例并重跑受影响模块。
- `py -3.12 -m unittest tests.contract.test_availability_port`：8 项，`OK`。
- `py -3.12 -m unittest tests.test_cli`：41 项，`OK`。
- 完整任务书命令中的其余模块在第一次运行通过；修复后按 `AGENTS.md` 只重跑了受影响的契约
  模块及 CLI 模块。全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。
- `git diff --check` 通过；本包新增及修改文件未发现连续问号。未提交。

## 建议

- 不建议月结重新读取当前 availability 文件。月结应汇总已提交日计划里的 `available_minutes`；
  后续修改手填文件不应追溯改写历史。如果将来需要审计当时的来源，可在独立任务中给日计划
  持久化来源或输入快照。
- 不建议 M12 snapshot 读取 availability。它汇总复习与词汇状态，不负责某个规划日的容量；
  M19 输入包已为规划器提供日期化容量字段，职责边界更清楚。
