# 第 253 轮：M17 可视化规格初检 — FAIL

范围：只审 `contracts/charts.md` 的四条自拟细则、§7 决议一致性与引用接口。
验证：静态阅读；未联网、未读个人学习状态、不写实现、不跑测试。

## 已核对

- §7 四项选择与正文一致：plotly、离线静态 HTML、分科计划分钟、仅做⑤a。
- §4 默认区间：截至昨天、向前 27 天，闭区间恰为 28 天；`to < T` 自洽。
- §2 逐字节确定性：固定 div ID、不嵌当前时间，与离线输出及只读边界无冲突。
- §3 课程块只作展示：与 M18 `DaySchedule.classes` 的首末时刻语义一致；跨午休提示必要。
- §4.3 叶子按真实父子关系取，避免依赖各科 scope；粗粒度子树覆盖是自拟折算规则，不能据此确认实际已学完。
- 引用接口真实存在：`TimetableCalendar.day`、`DaySchedule`、公开导出的 `ky.timetable_io.base_resolver`、
  `resolve_day_budget(...).total_minutes`、`ky.knowledge.hierarchy.parent_id`、`replace_bytes`。
- `products` 支持任意合规名称；`charts` 无需改 schema；完成事件 v3 的 `study_minutes` 与缺省/零值口径吻合。

## 必须改

### M1（MAJOR）：§5 将合法空状态库误判为登记来源缺失

- 位置：`contracts/charts.md:105`；该句覆盖日计划、完成事件、复习队列和路线。
- 反例：新工作区已登记 `state.plans`、`state.review_queue`、`state.routes`，但尚未执行任何写入，库目录未创建。
  按 §5“登记了却缺失 → 退出 2”实现，首次 `chart progress` 会失败，不能按 §4.4 显示“尚无路线”等空数据说明。
- 依据：`contracts/state_sources.md:24` 规定缺计划库返回空；`:36` 规定无队列 manifest 返回空；
  `:46` 规定无路线 manifest 返回 None；`contracts/day_plan_store.md` §2 明定不存在的根目录是空库。
  实现也如此：`day_plan_store.py:700`、`review_shards.py:556`、`route_store.py:185`。
- 最小修改：§5 区分单文件来源与状态库；状态库按现有读端口的空库语义处理。
  已存在但无效的目录/manifest、manifest 引用文件缺失或摘要不符仍退出 2；不能统一对状态库先做存在性拒绝。

## 留给最终大检查

- §4.3 页首需明确“按当前队列引用折算覆盖”；粗粒度引用与队列整理可能使它偏离实际学习完成度，不等于掌握度。
- §4.2 `subject_minutes` 仅含知识点通道，词汇/短语不在其中；最终核对标题与口径说明是否避免冒充全部分科学习计划时长。
- §4.1 参考分钟按生成时来源重算；最终核对页面是否沿用 M28“按生成时来源重算”说明，避免被理解为历史预算。
- 最终再检查 HTML/JS 离线嵌入、特殊学期名的文件名碰撞、渲染确定性与图表视觉效果。

结论：FAIL 仅由 M1 引起；其余条目不阻断本轮初检。
执行偏差：起始时误读仓库外评审技能文件，已向用户说明；报告依据为上述仓库内资料。
