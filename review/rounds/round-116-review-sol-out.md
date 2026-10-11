# Round 116 Codex 复审：`cdff892` 与 `2bbeaae`

范围限两次提交；探针及测试均在系统临时目录的 `git archive 2bbeaae` 中运行，按约定补入本机 `data/raw_materials/` 和空 `products/`。只跑相关单模块，不审 D11。

## A. 第 114 轮修复 `cdff892`

| 项目 | 判断 | 证据与复现 |
|---|---|---|
| A1 路线双读 | 不改 | `ky/planner/port.py:45,80,84`：同一个 `RoutePlan` 对象供预算和 `route_plan.phase`。重跑第 114 轮 `patch.object(RoutePlanStore, 'current', side_effect=[r1, r2])` 探针：`current.call_count == 1`，包内 `route_plan.revision == 1`、三科裁剪配额均为 r1 的 0；r2 未混入。`tests/contract/test_day_budget_port.py:303-320` 同时断言调用次数和两侧内容，撤回单次读取会变红。 |
| A2 非整数配额 | 不改 | 直接调用 `select_daily_reviews(config, (), 2026-09-15, subject_review_quotas={'math1': '2'})`，现报 `ContractError`，`path == 'subject_review_quotas.math1'`；`ky/schedule/review_clip.py:376-390` 先逐项校验再求和。回归测试在 `tests/contract/test_day_budget_port.py:322-328`。 |
| A3 文本标注 | 不改 | 登记阶段三科各 10 分钟后运行文本 `preflight`，退出 0，输出 `review soft / hard : 30 / 72 min (timeline quotas / 0.6)` 和 `timeline phase : 0 test-phase (cs408=10 eng1=10 math1=10)`；`ky/__main__.py:321-333` 不再把软值说成配置比率。建议以后给这行加直接文本断言；本轮手工探针已核实。 |
| A4 阶段首尾 | 不改 | 重跑两段 `[9/15,9/17)`、`[9/17,9/19)` 探针：日期偏移 `-1,0,1,2,3,4` 的 `phase_index` 分别为 `None,0,0,1,1,None`；`tests/contract/test_day_budget_port.py:330-360` 锁住首日、交界、考试日的右开语义。 |

**A：PASS。**

## B. D10 补充：紧急项只借剩余空闲 `2bbeaae`

| 项目 | 判断 | 证据与复现 |
|---|---|---|
| B1 配额保护与借用 | **必须改** | 对 M8 给出的、配额和不超过硬上限的正常输入，两遍法确实先给各科配额内项目让位：`ky/schedule/review_clip.py:283-305`。归档探针 `math1` 配额 0、紧急项 12 分钟，`eng1` 配额 20、普通项 20：两者均入选，紧急项只用了普通项之后的空位。但**“紧急项在本科内优先”不成立**：配置硬上限 72，配额 `math1=10, eng1=62`；同科普通项 `regular` 到期 `9/14`、成本 10、`defer_count=0`，紧急项 `urgent` 到期 `9/15`、成本 10、`defer_count=2`；另一科普通项 `other` 成本 62。于 `9/15` 调用 `select_daily_reviews`，结果 `selected=('regular','other')`、`deferred=('urgent',)`。`_sort_key` 在 `ky/schedule/review_clip.py:240-255` 先比逾期天数再比延期次数，第一遍在 `:283-295` 未把 `_is_urgent` 置于本科普通项前；与 `docs/阶段2.5-接缝收口.md:214-215`、`contracts/route_plan.md:72` 所写优先规则冲突。最小修法是在配额内先处理紧急项、再处理普通项，各组内保持原排序；第二遍仍只让未入选紧急项借全日剩余，最终列表仍按原排序输出。补一条上述同科反例的断言。另：直接调用公开端口传过量配额 `{math1:72, eng1:10}`，紧急 A 成本 72 可使本科配额内的普通 B 成本 10 延期；M8 会把这类配额缩到 72，故属端口前提未写清，**建议**在 M9 校验 `sum(quotas) <= hard_cap` 或写明仅接收 M8 解析后的配额。 |
| B2 无配额回退 | 不改 | `ky/schedule/review_clip.py:405-423` 的 `else` 保留旧单遍的 `unschedulable → hard cap → soft/urgent → selected` 顺序。将当前函数与固定前版 `cdff892:ky/schedule/review_clip.py` 在空队列、普通项、紧急项、过大项、scheduled 项及 `None/0/60/120` 日容量的 16 组输入上比较规范 JSON 字节，全部相同；第 114 轮固定基线的无路线／时间线外对照在本归档测试中也通过。 |
| B3 会计与统计 | 不改 | `ky/schedule/review_clip.py:283-309,397-452`：过大项在第一遍进 `unschedulable`，第二遍只遍历第一遍未选紧急项；最终 `review_minutes` 从 selected 求和，`subject_review_minutes` 在两次入选处累计。归档探针配额 `math1=0, eng1=20`，紧急 A=12、普通 B=20、过大 A=73：selected 为前两项，unschedulable 为过大项，实际分钟 `{math1:12, eng1:20}`，总 32，三个到期 ID 各在一个桶。两个输出列表按首轮 `rank` 排序；已存储队列拒绝重复 `review_id`（`ky/storage/review_shards.py:429,662`）。 |
| B4 新测试撤旧规则 | 不改 | `tests/contract/test_day_budget_port.py:187-217` 在归档中通过；临时把 `ky/schedule/review_clip.py` 换为 `git show cdff892:ky/schedule/review_clip.py` 后单跑该测试，退出 1：`calm-0` 不在 selected，旧规则只选 `urgent-0, urgent-1`；随后恢复归档文件。新测试有效锁住“别科普通项不被挤”，但它的 `urgent-0` 本就在本科配额内；真正的超配额借用另由同模块 `test_phase_quotas_gate_regular_items_and_allow_urgent_borrowing` 覆盖。 |

归档单跑 `py -3.12 -m unittest tests.contract.test_day_budget_port`：10/10；`tests.test_review_scheduler`：38/38。未跑全量。

**B：FAIL。** 保护别科配额和剩余空位借用已实现，但配额内的紧急优先承诺存在上述可复现反例。

可读性建议：`ky/schedule/review_clip.py:331-339` 的公开函数 docstring 仍只描述旧的全局软配额单遍规则；修 B1 时同步写明有配额时的两遍规则，避免端口使用者误解。

## 总结

**整体 FAIL**：A 的四项均关闭；B 需使同科紧急项在本科配额内先于普通项入选，并用反例测试锁住，同时保持当前的跨科配额保护。
