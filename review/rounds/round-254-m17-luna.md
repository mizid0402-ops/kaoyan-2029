# 第 254 轮：M17 可视化 ⑤a 实现报告

## 改动

- 新增 `ky/charts/`：`data.py` 负责周课表、每日分钟、ISO 周计划、叶子覆盖与路线映射；`render.py` 用 Plotly `graph_objects` 生成四图进度页与周课表页；`cli.py` 只读装配来源并写离线 HTML。
- 注册 `ky chart`；支持 `week`、`progress`、`--workspace`、`--config`、`--out` 与 `--open`。输出目录使用 `products.charts` 或显式 `--out`，HTML 与本地 `plotly.min.js` 通过 `replace_bytes` 写入。
- 注册 `products.charts: outputs/charts`，忽略 `outputs/`；`tests/` 的 products 搜索确认现有测试辅助按映射动态检查产品路径，缺少 gitignore 产品目录时已有跳过逻辑，无需同步样例。
- 加入 `plotly>=6,<7`；更新模块地图与 README；新增 `tests/contract/test_charts_port.py`。

## 做法与口径

- 复用 M18 `TimetableCalendar.day` 与 `base_resolver`；以基数 `initial` 覆盖默认配置值时，映射仍记录实际解析的 `base_minutes`。
- 进度参考分钟逐日通过 `resolve_day_budget(...).total_minutes` 生成；状态库通过 M13 `read_state_sources` 端口读取，新工作区缺少状态目录时保留空库语义。
- 完成度只按当前复习队列对生效知识树叶子的引用折算；树外引用保留在 `unknown_refs`，缺树科目显示空覆盖值。计划分钟按 `config.subjects` 的配置顺序输出，缺失科目分钟补 0。
- HTML 使用固定 Plotly `div_id`、本地 JS 文件和稳定文件名；同一工作区的周课表与进度页重复生成逐字节一致。

## 验收

命令：

```text
py -3.12 -m unittest tests.contract.test_charts_port tests.contract.test_workspace tests.test_cli
```

测试输出原文：

```text
----------------------------------------------------------------------
Ran 95 tests in 88.674s

OK (skipped=2)
```

另对新增契约模块单独复跑：

```text
...
----------------------------------------------------------------------
Ran 3 tests in 0.390s

OK
```

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）

## 歧义与选择

- §4.2 的“配置在考科目”按考试配置 `subjects` 序列解释，保留配置顺序；缺省计划值为 0。
- 周课表 `time_range` 以课程显示区间和空闲区间端点共同计算；空周使用规格给定的 `08:00`–`22:00` 默认范围。
- 未登记个人课表或零学期时，沿用 `timetable show` 的“没有可显示的学期”文案并以 3 退出。
- 未提交；任务书要求的其它当前工作区未跟踪文件保留原样。

## 第 257 轮：第二版

### 改动与做法

- M4 `ky.knowledge.hierarchy.tree_parent` 按 `contracts/knowledge_tree.md` 的四步顺序解析父节点，
  并从 `ky.knowledge` 导出。`parent_id` 与 `nearest_ancestor_with_scope` 实现未改。
- M17 数据层改为接收完整 `KnowledgePoint` 序列、语法名与注册表科目名；按 `tree_parent` 构建保序 Node 树，
  删除无非 `subject` 后代的跟踪节点，计算点亮叶子、未知引用和跟踪引用。`ReviewItem`、`DayPlan`、
  `CompletionEvent` 使用明确的领域对象属性读取。
- 渲染改为卡片页、浅/深两组 CSS 配色变量和响应式图表。每日数据使用最近日期优先的 HTML 表格与四个数字块；
  周计划按科目名称绘制，并区分无日计划与全零日计划；完成度使用三列可折叠目录树；路线阶段沿用科目配色。
  Plotly 图使用稳定 div ID，深色模式脚本通过 `Plotly.relayout` 调整背景、文字、网格与色板。
- CLI 将活动科目对应的注册表名称、完整知识树和 `tree_grammar` 传给数据层；原有离线写出与错误码路径保留。
- 契约测试覆盖 M4 三种语法、父级解析四步、M6 `parent_id` 结果、知识树结构/计数/引用分类、每日数字块与行序、
  无计划/全零计划、科目名展示及第 254 轮 CLI 确定性与错误码检查。

### 验收

命令：

```text
py -3.12 -m unittest tests.contract.test_charts_port tests.contract.test_knowledge_tree_port tests.contract.test_topic_weights_port
```

测试输出原文：

```text
.............................
----------------------------------------------------------------------
Ran 29 tests in 7.805s

OK
national.json: write=0 unchanged=0 missing=1 rejected=0 single_node=0 spread=0
   - missing from topic_weights.json: cs408-2023-01
school.json: write=1 unchanged=0 missing=0 rejected=0 single_node=1 spread=0

TOTAL write=1 unchanged=0 missing=1 rejected=0 single_node=1 spread=0
```

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）

### 歧义与选择

- “去掉跟踪节点”按知识树父子关系计算完整后代：只有自身 `scope` 为 `subject` 且所有后代仍为 `subject` 的节点才剔除；
  被剔除节点的队列引用单独列入 `tracker_refs`。
- 虚拟科目根只作为 Node 返回映射的根，其标题使用注册表科目名；树文件中的实际 `subject` 节点仍保留为子节点（若未被跟踪规则剔除）。
- 区间内只要存在一个日计划，即保留区间内全部 ISO 周桶并补零；完全没有计划时返回空周列表，由渲染层显示“区间内没有日计划”。
- 未登记知识树继续输出 `covered`、`total`、`tree` 均为 `null`；不因复习队列存在相应引用而推断知识树内容。
- 原型参考只检查了本地 HTML/CSS 源码；本轮没有浏览器内视觉预览，验收以指定契约测试为准。
