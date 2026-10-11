# 第 291 轮：前端第二版规格评审与 290 复验（sol61）

## A：FAIL（规格尚不能直接交实现）

对象：`2fa2b71` 的 web.md §8–§9、today.md §2/§8、模块地图 M16/M33；B 对象为 `aacb42e`。仅写本报告，不提交。
以下替换案供决策者采纳；M1/M3 选择保留既有端口，删减无法由它们提供的展示要求，未代替用户作决定。

1. **范围**：只读、本机服务一致；§8.1 明令 GET、405 与不写文件，没有新写入面。内容/次序已有规定，但日期查询、冻结置顶与顺序冲突、来源及报告展示仍须明确（M2–M5）。
2. **来源**：队列可以经 M33；charts 的注册目录是明确允许的文件格式端口，不算绕过。route 指定端口不够：`current()` 没有 actor/input_hash，`load_settings` 接收已解析对象而非路径，当前基数还需配置和 M8（M3）。模块地图方向正确，但“必需 review_queue”与新规格相冲突（M1）。
3. **形状**：基本数据可从已加载配置、队列、完成事件与 M9 结果取得；§3 reviews 本身不含科目/日期/延期等字段，不能原样复用。caps、明细键、backlog 截断顺序、ahead 口径未固定；五桶不能覆盖所有未来 queued 项（M2）。
4. **只读/一致性**：两份规格的“一次请求/调用每个来源只读一次”足够硬；实现应传同一对象，而非连续调用两个装配器。但“同口径”须限定同日同输入，§9 未要求跨视图行为对照（M6）。
5. **charts**：../、子目录及其它扩展名已有 404；符号链接未定义，未登记时文字未定。HTML 原字节与 MIME 正确，但既有图表需要被规则禁止的 JS 资源，且与共同“无 JavaScript/每页导航”冲突（M4）。
6. **错误/状态**：GET 无写入是明确约束；空队列、空图表目录已有文字。必需队列未登记不能启动；请求内契约错误与“退出 2”、chart 子路径非 GET、未知路由和日期查询须区分（M1/M5）。
7. **§9**：主要是行为断言，已有 POST/GET 文件树不变、空队列及未登记来源；当前阶段标识与冻结优先提示也属于行为。漏 caps/桶分钟/跨视图同口径、实际图表脚本资源及报告字段（M6）；三份合成 HTML、20/3 展示上限不是写死仓库数据量。
8. **首版关系**：不读投影、已有 A/B/C 写入和 CLI 输出均保留。§5 的“不提供路线/复盘操作”允许只展示状态；真正冲突是图表资源与无 JS，以及新接口将必需队列说成可选（M1/M4）。

## 必须改（均 MAJOR；每项仅列一处最小证据）

### M1：未登记队列成功返回的分支不可达
证据：`ky/workspace.py:700` 在 load_workspace 时即要求 state.review_queue；不能得到可交给新端口的合法 Workspace。
将 today.md §8 的 queue_registered 行替换为：“`queue_registered: bool`，合法 Workspace 中恒为 true；state.review_queue 仍为必需键，未登记按 §2 抛 ContractError，不构造视图。目录/manifest 尚不存在按既有 M13 空库处理。”
将 web.md §8.2 最后一段替换为：“合法空队列返回 200，显示‘复习队列是空的（学完知识点后用 ky learn 入队）’；state.review_queue 未登记属于无效注册表，按 §2 在启动时退出 2。”同步 §9 队列条目的“未登记队列文字”为“缺必需键启动拒绝”；M33 必需键列表保留。
若必须保留未登记队列的 200 页面，先另审 Workspace 注册表可选化及 load_today/record 的边界，不能让实现者私自放宽解析器。

### M2：稳定映射与 M9 业务口径没有固定
证据：`contracts/review_clip.md:130` 明定未来 queued 不在五桶，deferred 对象的 defer_count 已加 1；新规格“整条队列五桶/字段与 §3 一致”不足以定实现。
将 today.md §8 的装配首段及字段表替换为下列文字（后面的参数校验、输出不变约束保留）：
“复用 §1 已加载上下文和同一个 M9 预检计算，保留 ClipResult；不另外读取队列或重新实现裁剪。返回键固定为 schema_version=1、date、budget、caps、freeze、queue_registered、buckets、selected、backlog、ahead；date/budget 与 §3 同日同输入时同值；freeze 为 preflight.get('freeze')，无冻结为 null；queue_registered 见上条。”
“caps={soft_target_minutes,hard_cap_minutes,soft_source,hard_source,subject_review_quotas}：两分钟值直接取 ClipResult；冻结时均为 0、来源均为 freeze、配额为 null；否则 soft_source 为 route_quota（有经 M8 缩放的配额）或 config_ratio，hard_source 为 config_ratio；配额取 ClipResult.subject_review_quotas，无配额为 null，硬上限不等于路线配额之和。”
“buckets 固定五键，各值={count,minutes}，按 ClipResult 对应元组长度和 estimated_minutes 求和；沿用 M9 的成员与顺序，不补未来 queued，不含 suspended/retired。selected 明细保持 M9 入选顺序，仅含 {review_id,knowledge_point_id,title,subject_id,subject_name,level,due_date,overdue_days,defer_count,lapses,estimated_minutes}；名称取配置 display_name，level 沿用 M31 的已加载完成事件判定，日期为 ISO，overdue_days 用 ReviewItem.overdue_days(day)，lapses 取 schedule.lapses，不加载题目作为展示前提。”
“backlog={count,minutes,by_subject,details,remaining_count}：成员为 deferred+unschedulable+unreachable，不等同 M9.backlog_minutes（后者仅 deferred）；by_subject 为科目 ID 键控的 {count,minutes} 稀疏映射；details 按三桶上述顺序拼接取前 20 项，使用 selected 同形明细；deferred 的 defer_count 为本次预检加 1 后值，标注‘本次预检延期后计数’，不写回；remaining_count=count-len(details)。”
“ahead={count,due_dates}：取原队列 state∈{queued,scheduled} 且 due_date>day 的全部项；count 为项数，due_dates 为升序去重 ISO 日期的前 3 个，不等同 scheduled_ahead 桶。空集合保持全部键，数字 0、列表空、by_subject 空；不读投影、不缓存，每个来源一次读取。”
将 web.md §8.2 的来源说明改为：“同日且来源内容相同，两页 budget、M9 入选 ID 顺序与各桶计数/分钟一致；两次请求之间 AI 改了数据则允许变化。”顺序改为：“冻结提示存在时放在日期/时间摘要前，其余保持原序”；§8.2 第 5/6 项采用上述 backlog/ahead 口径及延期计数说明。

### M3：路线来源与报告中的“分钟变化”没有指定端口可提供
证据：`contracts/pacing_review.md:64` 的完整报告字段只提供 base 统计、reviews 完成统计等，没有各科复习配额变化；路线来源另存 manifest，不在 RoutePlan 对象。
将 web.md §8.3 数据段替换为：“路线从 M11 RoutePlanStore.current() 读取一次；配置经公开 load_config(workspace.require('settings.exam_config'))，设置经 M28 settings_for_workspace(workspace) 各读一次；当前基数经 M8 daily_base_minutes(day,config,route,settings) 计算。复盘周期经 cycle_for_date，未报告周期及保存报告经 load_pacing_report_state(settings,day,workspace.write_target('state.plans')) 一次取得。无 settings 时不读取报告；不调用报告生成/提交端口。”
将第 1 项替换为：“route_id、revision、规划输入标识 stage1_input_hash 前 12 位、start_date、target_exam_date、剩余天数 max(0,(target_exam_date-day).days)；不将规划输入标识冒称提交来源。未登记路线或 current() 为 null 都显示原‘还没有路线’提示。”
将第 3 项替换为：“当前基数及来源由 M8 返回；周期显示 start 至 end 终日，next_review=cycle.end；cycle 为 null 时显示‘复盘尚未开始’，下个复盘日为空。未报告周期按终日升序显示；最近报告取返回报告映射的最大周期终日键，显示 cycle.end、base.min/max/mean 和 reviews 各科完成统计，不声称是配额变化；无报告保留原提示。”
第 2 项当前阶段明确为 start<=day<end_exclusive，无命中则无高亮。如决策者坚持 actor/input_hash，须先定义返回当前路线及来源的单次读取公开端口；current()+provenance() 会重读 manifest，不能作为本版方案。删除“来源/各科分钟变化”的展示要求已在此明列，供决策者裁定。

### M4：图表按现有产物提供时缺少必需资源
证据：`ky/charts/render.py:30` 的 HTML 引用同目录 plotly.min.js；只提供 *.html 会令浏览器请求 /charts/plotly.min.js 得到 404，三张图无法绘制。
将 web.md §8.4 的读取规则替换为：“入口仅枚举直接位于登记目录、符合三类 HTML 名字模式的普通文件；GET /charts/<文件名> 原字节返回这些 HTML，Content-Type 为 text/html; charset=utf-8。另仅允许精确名 plotly.min.js 的普通文件，原字节返回，Content-Type 为 application/javascript; charset=utf-8，不列入入口。两类响应均给正确 Content-Length；不得调用 ky chart 生成或补写资源。”
“文件名先按 URL 路径解码；拒绝路径分隔符、../、子目录、符号链接及其它名字/扩展名，404。登记目录按 Workspace 路径包含规则解析，目标解析后须直接位于其中；列表和下载采用同一筛选规则。命中文件丢失返回 404；读失败按请求错误规则处理。”
“products.charts 未登记时 GET /charts 返回 200，文字‘未登记图表目录，请让 AI 检查注册表’；未登记时所有文件 URL 返回 404。目录不存在或无匹配 HTML 保留原生成命令提示；路径存在但不是目录属于契约错误；匹配 HTML 存在但 plotly.min.js 缺失时入口提示重新生成图表，不在 GET 中修复。”
在 §8.1 外壳约束后追加：“共同外壳、无新增 JavaScript、导航与外部文本转义适用于三个入口页；原样提供的离线图表 HTML 及其既有 Plotly 脚本例外，不加导航、不改 HTML、不转义其文件字节。§1 的无 JS 约束据此作明确限定，M17 产物格式不变。”

### M5：请求日期、错误和方法覆盖需要定死
证据：`contracts/web.md:108` 将请求章节中的注册表错误写为进程退出 2，却没有区分启动与请求错误。
将 §8.1 的路径/错误约束替换为：“/queue、/route 接受可选 date=YYYY-MM-DD（校验同 §3），只接受一个 date 查询字段；缺省每请求取一次系统日期，全部计算用同一 day。/charts 及文件 URL 不接受查询字段，未知/重复查询字段或非法日期返回 400。上述入口及 /charts/<文件名> 的所有非 GET 方法返回 405、Allow: GET，不进入数据装配或写入管线；未知路由为 404。”
“找不到/无效注册表在启动时按 §2 退出 2；运行中读取已登记来源失败或来源无效，返回转义契约错误的 400 页面；可选键未登记和合法空数据按各页规则返回 200；未预期异常返回 500 并只向 stderr 写详情，不终止服务、不向页面暴露 traceback。全部 GET/拒绝请求不创建目录、锁、缓存、报告或任何工作区文件。”

### M6：验收要能否定上述错误实现
证据：`contracts/web.md:155` 只验五桶条数/字段存在，没有分钟值、两视图一致性、真实图表资源或报告内容的断言。
在 §9 追加：“M33：合成冻结、路线配额缩放、未来 queued/scheduled、当日不可选 scheduled 及超过展示上限的输入，按 M9 输出断言 buckets/caps、明细及 backlog/ahead 值与顺序；同日同输入比较 load_today 和 load_queue_view 的 budget、入选 ID、五桶条数/分钟，并以读取计数确认每来源一次。期望值由合成输入与既有端口推导，不钉住仓库数据量。”
“M16：断言日期/查询 400、启动缺注册表/必需键退出 2、请求已登记来源错误 400、未知路由/缺文件 404、所有只读入口及资源非 GET 405；测试登记但空路线、周期尚未开始、最近报告选择与报告字段。图表合成 HTML 须引用 plotly.min.js，断言脚本 GET 原字节/MIME、HTML MIME、文件链接编码及未登记/缺目录/缺脚本提示；GET/拒绝请求均复用文件树不变断言。布局像素、颜色位置不作为验收。”

## 建议改

- 图表同修改时间时按文件名排序，避免列表顺序漂移；模块地图页首更新时间可同步为 2026-10-08。

## 不改（说明）

- 保留首版记录/可用分钟/补推进、127.0.0.1、标准库服务、不读投影；不因“第二版只读”删除首版写入。不要求在线图表生成、额外分页或布局截图测试。

## B：两条均 PASS / RESOLVED（各一条探针）

- **(a)** 原 `round289_probe.source_counts()` 单条命令实跑：load_today 与次日 record_day 的 config、旧 manifest、两个旧分片、旧完成事件、树、权重、索引各 1 次；输出 .tmp 重读校验不计旧来源。传递链 `day_plan_store.py:534` → `review_shards.py:686` 已用 source_state。复现：设 PYTHONDONTWRITEBYTECODE=1 后，`py -3.12 -B -c "import sys; sys.path.insert(0,r'C:\Users\Lenovo\AppData\Local\Temp'); import round289_probe as p; p.source_counts()"`。
- **(b)** 单条命令直调 `_assert_only_retire_hint_differs`：old 为 `--reason <原因> --date 2026-10-01`（CRLF），仅改为 `--reason "替换为原因"` 被接受；再把日期换成 `2099-01-01` 被 AssertionError 拒绝。最小复验位置 `tests/contract/test_today_port.py:630`，整行等于唯一占位符替换，不再抹掉其它差异。
- Python 探针均用 py -3.12 -B、PYTHONDONTWRITEBYTECODE=1；合成输入仅系统临时目录。A 未跑实现测试；全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。

## 安全登记

- 新入口的恶意符号链接可能令图表下载读到目录外文件（需手工布置链接；影响为本机文件泄露；修法是解析后包含检查/排除链接，M4 已建议明确规则，不单独开安全返工）。篡改离线 HTML/JS 后同源脚本向首版写入口 POST 的风险沿用 S20，开源前可隔离图表来源或加令牌；不把恶意输入当本轮日常缺陷。

## 最坏情况

已确认：照原文无法同时满足队列未登记成功页与现有注册表、路线来源与单次读取；图表依赖被禁止，报告配额变化没有数据。合理推测：实现者补猜会漏未来 queued、误报硬上限/积压或伪造历史变化。B 两修复通过不代表第二版实现通过；本轮未验证个人数据、浏览器布局或新页面实现。
