# M17 可视化（路线图 ⑤a：周课表图、学习进度图）

> 决议来源：用户 2026-10-01（见 §7）。状态：sol 253 初检 FAIL（M1 状态库空库语义）→ 已改 §5；sol 255 实现初检 PASS；
> **第二版**（用户看过实际页面后改版，§7 第二表）：新配色与卡片页面、每日分钟改列表、完成度改为可折叠目录树并按语法取层级（新 M4 端口 `tree_parent`）。
> 需求依据：`review/requirements.md` §8.1、§8.2。能力画像（§8.3）与目标差距（§8.4）是 ⑤b，**不在本规格**：
> 先要定义"掌握度"怎么算（自评零特权，`交接文档.md` §4.1），由决策者另拟规则、用户拍板后再写。

## 1. 职责与边界

- **只读**：读注册表登记的课表、路线、复盘设置、考试配置、复习队列、知识树、日计划与完成事件；**不写任何学习状态**。
- 两层，可分别替换：
  1. **图表数据**（纯函数，`ky/charts/data.py`）：输入已加载的对象，输出普通映射。映射是图表内容的**唯一形状来源**，契约测试只断言它。
  2. **渲染**（`ky/charts/render.py`）：把图表数据映射交给 plotly（`plotly.graph_objects`，不用 `plotly.express`、不依赖 pandas）生成 HTML 片段，拼成一页。
     换图表库只换这一层。
- **装配**（`ky/charts/cli.py`）：一次读取各来源（同一数据只读一次，`AGENTS.md` 已知缺陷 2），调纯函数，再渲染、写文件。
- 输出是**派生产物**：可删可重建，允许覆盖；用 `ky.storage.atomic.replace_bytes` 写，不写穿硬链接。

## 2. 输出位置与页面

- 输出目录 = 注册表 `products.charts`（`contracts/workspace.md` 的 `products` 映射，已有键形状，无 schema 变更）；
  仓库注册表登记 `products.charts: outputs/charts`，`.gitignore` 忽略 `outputs/`（图里有个人课表与学习记录）。
  `--out DIR` 显式覆盖；两者都没有 → 契约错误退出 2，提示登记或传 `--out`（不自选路径）。
- 每页一个 HTML 文件，引用同目录的 `plotly.min.js`（`plotly.offline.get_plotlyjs()` 的字节；目录里没有或字节不同才写）。
  **离线可用**，不引用 CDN。
- **确定性**：同一输入两次生成的 HTML **逐字节相同**（图表 `div_id` 由页面类型与序号确定，如 `chart-week-0`；不嵌入当前时间）。
- 写完打印文件的绝对路径与 `file:///` 链接；`--open` 时再用 `webbrowser.open` 打开（不加不开）。
- 页面标题、坐标轴、图例用中文；页首一行说明数据来源与口径（各图下面写明）。科目一律显示注册表 `subjects.<id>.name`，不显示 ID。
- **页面样式**（第二版）：浅底页面上的白色圆角卡片，每张图 / 列表一张卡片（标题 + 一行灰色口径说明 + 内容），内容最大宽度约 1180px，
  窄于 820px 时多列改单列。图表随卡片宽度自适应（plotly `responsive`，不写死宽度）。
- **配色**用 dataviz 参考调色板（已过色盲校验）。颜色定义成页面 `<style>` 里的 CSS 变量，浅色 / 深色两套（`prefers-color-scheme: dark`）：

  | 角色 | 浅色 | 深色 |
  |---|---|---|
  | 页面底 / 卡片底 | `#f6f5f2` / `#fcfcfb` | `#121211` / `#1a1a19` |
  | 主文字 / 次文字 / 弱文字 | `#0b0b0b` / `#52514e` / `#8a8984` | `#ffffff` / `#c3c2b7` / `#8f8e86` |
  | 网格线 / 未点亮 | `#e7e6e2` / `#dcdbd6` | `#2c2c2a` / `#3a3a37` |
  | 科目色（按配置在考科目顺序取槽 1、2、3…） | `#2a78d6`、`#eb6834`、`#1baf7a`、`#eda100` | `#3987e5`、`#d95926`、`#199e70`、`#c98500` |

  科目色**跟科目走、不跟排名走**：第 i 个在考科目（配置顺序）固定用槽 i。plotly 图按浅色生成，页面脚本在深色模式下用同一张表 `Plotly.relayout` 换底色、文字与网格色。
  图表风格：背景与卡片同色、网格浅、无外框；柱子之间 2px 卡片色间隔。

## 3. 周课表图 `ky chart week --week N [--semester L] [--out DIR] [--open]`

参数规则与 `ky timetable show --week` 相同（`contracts/timetable.md` §8）：只有一个学期时可省 `--semester`；
学期不存在、`N` 超出 1..weeks、未登记个人课表或零学期 → 用法错误退出 3，提示文字与 `timetable show` 相同。

数据：该学期第 `N` 周周一至周日 7 天，每天 `TimetableCalendar.day(d, base_for(d))`，`base_for` 用 M29 公开的
`ky.timetable_io.base_resolver(workspace, config)`（路线阶段 > 复盘设置 `initial` > 配置，已接 M28）。

`week_chart_data(semester_label, week, days) -> Mapping`：

```
{kind: "week", semester: L, week: N,
 days: [  # 7 项，周一到周日
   {date: ISO, weekday: 1..7, covered: bool,          # day() 为 None → covered false，其余字段为 null / 空
    no_class: bool, followed: ISO | null,
    classes: [{name, first_period, last_period, start: "HH:MM", end: "HH:MM", unconfirmed: bool}],
    free_segments: [["HH:MM", "HH:MM"], ...], free_minutes, blocks, base_minutes, minutes}],
 time_range: ["HH:MM", "HH:MM"]}   # 本周所有 start/end 与空闲段端点的最小值向下取整点、最大值向上取整点；本周无数据时 ["08:00", "22:00"]
```

`unconfirmed` = 该课程的节次与 `DaySchedule.unconfirmed_periods` 有交集。

渲染：横轴周一…周日（标签在顶部：`周X M/D` 换行 `可学 N 分`），纵轴时刻（上早下晚）。课程画成科目槽 1 色的色块，块内写课名（截前 8 字）与 `a–b 节`，
悬停显示全名、时刻、节次、是否待确认；待确认加虚线边。空闲时段画成浅绿半透明底块（比课程块略宽）。`covered: false` 的列标"课表不覆盖"。
课程块的 `start`–`end` **只作展示**（跨午休的课会把午休画进去）；真实可学时间以空闲时段为准，页首写明这一点。

文件名：`week--<学期 label 中非 [A-Za-z0-9_-] 的字符换成 _>--w<两位周次>.html`。

## 4. 学习进度图 `ky chart progress [--from D] [--to D] [--today T] [--out DIR] [--open]`

`T` 缺省为当天；`--to` 缺省为 `T − 1`（当天还没过完）；`--from` 缺省为 `--to` 往前 27 天（4 周）。
要求 `from <= to < T`，否则用法错误退出 3。一页四张卡片，依次：

### 4.1 每日学习分钟（实际 vs 参考）——**列表**（第二版，用户 2026-10-01 不要折线图）

- **实际**：区间内每天完成事件的 `study_minutes`（`contracts/review_progress.md`，v3 字段）；没有完成事件或该字段为 `null` → 该日写"未记录"，不当作 0。
- **参考**：同一天 M8 解析的当日总分钟（手填 > 课表 > 基数，`resolve_day_budget(...).total_minutes` 同口径，与 M28 报告 `reference_minutes` 一致）。
- 卡片顶部四个数字块：`有记录天数 / 区间天数`、`实际合计`、`同日参考合计`（只合计有记录的日子）、`达成率`（实际合计 ÷ 同日参考合计，整数百分比，ROUND_HALF_EVEN；参考合计为 0 或无记录时写 `—`）。
- 下面是纯 HTML 表格，**最近的日子在最上**：`日期（M/D）| 星期 | 实际 | 参考 | 达成`；"达成"是一根细进度条（实际 ÷ 参考，封顶 100%；参考为 0 时不画）。
  数字列右对齐、等宽数字。
- 卡片说明：参考分钟"按生成时来源重算"（同 M28 报告 `reference_source_note`），不是当时的历史预算。

### 4.2 四科计划分钟（按周）

- 按 ISO 周（周一起）汇总区间内**当前日计划**的 `subject_minutes`；只列配置在考科目，按配置顺序。堆叠柱，科目色见 §2，图例用科目名、横排在图上方。
- 区间内没有任何日计划 → 卡片只写"区间内没有日计划"；有日计划但分科分钟全为 0 → 照常画（全 0 柱），不报"没有数据"（sol 255）。
- 图标题与图例写明"**计划**分钟"（用户 2026-10-01：不逐科记实际用时）。区间首尾不满一周的照实汇总并在横轴标签注明日期范围。
- 图下说明：只含知识点通道的分科分钟，不含单词 / 短语通道。

### 4.3 完成度——**知识树点亮**（第二版：可折叠目录树）

**层级**：父子关系一律用 M4 新端口 `ky.knowledge.hierarchy.tree_parent(point_id, points_by_id, grammar)`（`contracts/knowledge_tree.md` "Grammar-aware tree parent"），
`grammar` 取该科注册表 `subjects.<id>.tree_grammar`。**不用 `parent_id`**：按 ID 前缀推层级对 `named_chapters`（数学一）与 `numbered_chapters`（408 各章）推不出父子
（数学一 69 个节点会全被当成互不相连的叶子；2026-10-01 决策者实测）。

**可学节点**：去掉 `scope: subject` 且子树里（按 `tree_parent`）没有任何非 `subject` 节点的节点——即"考查目标 / 区块验收"类跟踪节点（408 有 16 个）。
它们不是可学内容，不进树、不进分母分子。其余节点（含作为分组根的 `subject` 节点，如 `cs408.ds.subject`）保留。

- 分母：可学节点中的**叶子**数（没有可学子节点的节点）。
- 分子：复习队列中该科（任意状态）引用到的叶子，加上被引用的**非叶子节点**下的全部叶子（按较粗粒度引入的复习项视为整棵子树已学过一遍）。
  引用了不在生效树里、或引用了被去掉的跟踪节点 → 不计入，列进 `unknown_refs` / `tracker_refs`（不报错）。
- 节点"点亮"：叶子被计入分子即点亮；非叶子显示 `点亮叶子数 / 叶子数`。

**展示**（用户 2026-10-01 选"方案 E"）：三科并排三列（窄屏单列），每列是一棵**可折叠的缩进目录树**（HTML `<details>`/`<summary>`，不用 plotly）：
- 列头：科目名 + `点亮 / 总数（百分比，一位小数，ROUND_HALF_EVEN）` + 一根进度条；
- 每个非叶子一行：标题、右侧细进度条（科目色）与 `a/b` 计数；点击展开 / 收起。**初始只展开到第一层**（科目下的直接子节点可见）；
- 每个叶子一行：实心圆点（科目色）= 已点亮；空心圆点 + 弱文字 = 未点亮；
- 同层节点按知识树文件中的出现顺序排列；节点标题用知识树 `title` 原文（HTML 转义）。
- 没有登记树的科目整列写"无知识树"。
- 卡片说明：按当前复习队列的引用折算"学过一遍"的覆盖，**不是掌握度**（掌握度是 ⑤b）。

### 4.4 阶段推进

- 当前路线（`state.routes` 已登记且有修订）各阶段画成横向时间条（甘特），悬停显示 label、基础分钟、各科复习分钟；`T` 处画竖线并标"今天"；
  另标注距路线 `target_exam_date` 的天数。没有路线 → 该图只写"尚无路线"。

### 4.5 数据映射

`progress_chart_data(...) -> Mapping`：

```
{kind: "progress", from: ISO, to: ISO, today: ISO,
 daily: [{date, actual: int | null, reference: int}],
 daily_totals: {recorded_days, actual_sum, reference_sum_on_recorded_days},
 weekly_plan: [{week_start: ISO, from: ISO, to: ISO, minutes: {<科目>: int}}],   # 科目按配置顺序、缺省 0
 coverage: [{subject_id, name, covered: int | null, total: int | null,
             unknown_refs: [id, ...], tracker_refs: [id, ...],
             tree: null | Node}],          # 无登记树时 covered/total/tree 为 null
   # Node = {id, title, lit: int, leaves: int, children: [Node, ...]}；根是虚拟科目节点 {id: <subject_id>, title: <科目名>}，
   #        其子节点 = tree_parent 为 None 的可学节点；叶子 children 为空、leaves 为 1、lit 为 0 或 1；同层按树文件顺序
 route: null | {route_id, revision, target_exam_date, days_to_exam,
                phases: [{index, start, end_exclusive, label, base_daily_minutes, review_minutes}]}}
```

纯函数的参数是已加载的对象（配置、科目名、逐日参考分钟映射、日计划与完成事件序列、队列项、各科已加载的知识点序列与树语法名、路线），不读文件。
第二版不再接受"树节点 ID 集合"——层级要靠 `scope` 与语法，必须传完整知识点序列。

## 5. CLI 与错误

- 命令：`ky chart week …`、`ky chart progress …`；`--workspace`、`--config` 取法与 `ky pacing report` 相同（缺省读登记的 `settings.exam_config`）。
- 退出码：成功 0；契约违约（登记了但无效的文件、缺 `products.charts` 且无 `--out` 等）2；用法错误 3。错误走 `contract violation: …`，不出 traceback。
- 未登记的可选来源（课表、路线、复盘设置、日计划、完成事件、复习队列）按"没有数据"画（空图加说明），不报错（注册表"找不到"与"找到但无效"区分，`AGENTS.md` 已知缺陷 4）。
- 登记了的**单文件来源**（个人课表、学校档案、复盘设置、考试配置、知识树）缺失或无效 → 退出 2。
- 登记了的**状态库**（`state.plans`、`state.review_queue`、`state.routes`）一律经现有读端口读取，**沿用其空库语义**：
  根目录或 manifest 尚不存在 = 空库（新工作区首次运行即如此，sol 253 M1；`contracts/state_sources.md`、`contracts/day_plan_store.md` §2），按"没有数据"画；
  已存在但无效的目录 / manifest、manifest 引用的文件缺失或摘要不符 → 读端口报错，退出 2。不对状态库另做存在性检查。

## 6. 不变的部分

- 不改任何既有命令的输出；不改 M18 / M8 / M13 / M28 的接口；只新增 `ky chart` 子命令、`products.charts` 登记行、`outputs/` 忽略规则、`plotly` 依赖。
- 第二版给 M4 **新增**公开函数 `tree_parent`；既有 `parent_id`、`nearest_ancestor_with_scope` 行为不变（M6 考频权重依赖它们，输出必须逐字节不变）。
- `docs/模块地图.md` 把 "M16–M17 前端 / 可视化（未开始）" 拆出 **M17 可视化**一行；README 模块速查同步。

## 7. 决议记录（用户 2026-10-01）

| 问题 | 选择 |
|---|---|
| 图表库 | plotly（2026-09-15 轮子调研；本机已装 6.9.0，`pyproject.toml` 声明 `plotly>=6,<7`） |
| 输出形式 | 静态 HTML 文件（命令生成，浏览器打开、离线可用）；⑥ 前端以后直接嵌入 |
| 四科学习时间分布 | 用日计划的分科**计划**分钟；实际只画每日总分钟 |
| 范围 | 先做课表图 + 进度图（⑤a）；能力画像 / 目标差距（⑤b）另定掌握度规则后再做 |

第二版（用户 2026-10-01 看过实际页面后）：

| 问题 | 选择 |
|---|---|
| 配色 | 原 plotly 默认配色"很难看"→ 换 dataviz 参考调色板、卡片式页面（§2） |
| 每日学习分钟 | 不要折线图，改**列表**（§4.1） |
| 知识树覆盖 | 不要条形图（408 节点多、观感差）；比较过径向树、旭日图、冰柱图、自上而下树、同粒度树后，选**可折叠目录树**（方案 E，§4.3）；径向树原型保留备用 |

第一版决策者自拟、经 sol 253 初检的细则：§4.3 完成度口径（叶子覆盖、粗粒度引用覆盖整棵子树）、§4 默认区间（最近 4 周、截至昨天）、
§2 输出逐字节确定、§3 课程块只作展示的说明。

## 8. 能力画像页 `ky chart ability [--today T] [--out DIR] [--open]`（⑤b，第三版）

数据全部来自 M30 `contracts/mastery.md`（档位、薄弱、科目能力、目标差距），本模块只装配与渲染。`T` 缺省为当天。
页面样式、配色、确定性、离线、错误码同 §2 / §5；文件名 `ability--<T>.html`。四张卡片，依次：

1. **四科能力**：每科一根横向堆叠条（未学 / 学过 / 掌握中 / 已巩固 的**权重占比**，用同一科目色的四级深浅，未学用"未点亮"灰），
   条右写 `能力 xx.x%`（= 已巩固占比）。408 下面一行小字说明"按近年真题考频加权；N 个知识点近年未考（权重 0）"。三科不画雷达（只有三个轴）。
2. **目标差距**（第二版，M30 §5）：每科两行——`覆盖 当前 xx.x% / 应到 yy.y%` 与 `巩固 当前 xx.x% / 应到 yy.y%`，各一根进度条，条上标"应到"刻度线；
   差距为负时数字用状态色 critical 加"落后"字样（不只靠颜色）。`missing_route` / `no_targets` 时整卡写原因与做法（"建立路线并在阶段上写 targets"）。
3. **各模块掌握度**：与 §4.3 同一棵可折叠目录树，但叶子圆点改为四级：空心 = 未学，浅 / 中 / 满色 = 学过 / 掌握中 / 已巩固；
   薄弱叶子在名字后加"⚠ 遗忘 ≥2"标记；每个非叶子行右侧是四档迷你堆叠条与 `已巩固/叶子数`。
4. **薄弱点清单**：所有薄弱叶子的表格（科目、所在章、知识点、遗忘次数、当前档位），按科目配置顺序、再按树文件顺序；没有则写"暂无薄弱点（遗忘 ≥ 2 次的知识点）"。

卡片说明统一写明：档位由 FSRS 记忆稳定度（尚未用 FSRS 核对过的项用阶梯间隔）决定，只随有锚点的核对变化，自评不参与（硬不变量③）。
薄弱清单的"遗忘次数"直接取 M30 叶子映射的 `lapses`。

`ability_chart_data(...)`：把 M30 的 `subject_mastery` / `mastery_gap` 结果加上科目名、树结构（Node，同 §4.5，叶子另带 `level` 与 `weak`）组成一个映射，
是页面内容的唯一形状来源；契约测试只断言它与 HTML 中的关键文字。
