# 评审：WP-F-a 状态来源读取端口（`b97f3ac`）

遵守 `AGENTS.md`（不跑全量；严重度按威胁模型，安全类单列"安全登记"）。你在本窗口第 132 轮审过 WP-F 细则（`review/rounds/round-132-wp-f-rules-sol-out.md`），决策者全盘采纳；F-a 实现你"建议的最终规则"第 2、5 条。
用 `git archive b97f3ac`（补原始资料与 `products` 空目录），只在你自己的临时目录运行。

依据：任务书 `round-133-wp-fa-task.md` 与返工任务书 `round-134-wp-fa-rework-task.md`；实现者报告 `round-133-wp-fa-luna.md`、`round-134-wp-fa-rework-luna.md`；规格 `contracts/state_sources.md`。

请查：
1. 四个新接口（`DayPlanStore.read_state_sources`、`ReviewShardStore.read_state_sources`、`RoutePlanStore.read_state_sources`、`load_availability_with_source`）返回的对象是否与现有读取方法一致；空 / 缺失 / 无效三种情况是否符合你第 132 轮 F5 的结论。
2. "哈希来自解析所用的同一份字节"是否在每条路径上成立；每个来源文件是否只读一次（测试计数了 `read_bytes` / `read_text`，有没有别的读取途径漏计）。
3. 日计划只收 `<root>/<YYYY-MM>/day_plans_manifest.yaml`、放错位置报错：对正常使用会不会误报（例如月结、旧版本文件、`freeze/` 目录）。
4. 返工后共用的私有解析函数：现有 `freeze_events()`、`load_day_plan`、`current()`、`load_revision()`、`load()` 的行为与错误消息是否不变。
5. `sources` 的路径约定对 F-b 合并多个存储是否够用（相对各自存储根，是否会撞名）。

产物：`review/rounds/round-136-review-sol-out.md`，"必须改 / 建议改 / 不改"附可复现输入，"安全登记"一节，最后 PASS / FAIL。只写这一个文件。
