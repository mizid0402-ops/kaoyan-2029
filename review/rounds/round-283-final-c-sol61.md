# 第 283 轮：最终大检查 C — M16 / M33（sol61）

## 1. 结论：FAIL

M1–M3 为 MAJOR；M4 为 AGENTS.md 明文要求的低风险必改项。四项一次列齐。
按任务书顺序读完规格、模块地图和 273/274/277/279 报告；不重审已修的 N1。
评审期间 HEAD 从 03d349a 变为 f51fea5（外部提交）；点名实现、规格、测试未变化。
本轮只新增本报告；未联网、未读忽略的个人数据、未启动真实工作区服务、未提交。
定向验证：10 个相关单测 OK；固定 CLI 基线矩阵及非空网页/CLI 记录对照 2 tests / 24.943s / OK。
另用系统临时目录合成工作区做来源计数、补题、冻结清理失败及 HTTP 探针；服务均 shutdown/join。
全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。

## 2. 逐条 A1–E1

- **A1 不成立**：配置、路线、可用时间、课表、复盘设置、题库对象在 sources 中读取并复用；
  但队列 load 内部每片读两次；有 recorded 时另读队列 manifest；出题计算读树、逐项读索引/权重。
  `_ancestor_map` / M24 算越界：即使树只读一次，也违反 today.md 的“计算层不暗读文件”。
  复盘报告不在 sources 快照中，`_pacing_mapping` 经 missing_report_cycles 现读报告；record 管线又读队列/冻结。
  同科两项探针：load_today 中 index/weights 各 2 次、manifest 2 次、每片 2 次；见 M1。
- **A2 已核实**：§3 顶层全部字段和 budget/timetable/route_phase/pacing/recorded 子字段一致；
  preflight/reviews 使用共享构造器；未登记可选来源、无阶段、无周期分别为 null；未启用配额不造零。
  recorded.study_minutes 保留 None/0 区别；空 reviews 的 advanced 为真；旧 ID 按 day#index 补齐。
  证据：`ky/today/port.py:128` 起各映射 helper；CLI 对照与映射定向用例通过。
- **A3 已核实**：真实 M31 append_question 补无关题，hash 不变；补当前缺题点，hash 改变，旧提交在 view_hash 拒绝且无事件。
  缺 check/null question_ref 与显式 recall_vs_notes/null 的哈希相等；不哈希整个题库。
- **A4 不成立**：`ky/today/port.py:1` 有 M33 与规格，但没有四个公开接口列表，见 M4。
- **B1 已核实（串行正常操作）**：重复 record 返回 400、不再写事件或推进；这里的幂等指副作用，而非重复返回成功。
  M13 完成事件仍为 exists + replace 的旧实现，非原子不覆盖；跨进程问题按既有安全登记处理，见“不改”。
- **B2 不成立**：一般 rejected/freeze_written/event_written 路径及 OSError 用例通过，网页按 stage 分支，不读错误消息子串；
  但冻结已硬链接发布、清理临时文件失败时仍报 rejected；实际已有冻结文件，见 M2。
- **B3 已核实（有条件）**：三个显式相对路径原样保留，workspace.source 固定为绝对路径。
  同一合成恢复输入在原 cwd 执行退出 0，换到空目录退出 2；当前提示必须保持原 cwd，不能声称跨目录可复制。
  证据：`ky/__main__.py:1597`；建议固定全部绝对路径或明示原 cwd。
- **B4 已核实**：预检在锁存之前；普通事件写失败和 M2 清理失败后，恢复磁盘并重交都成功，冻结只保留一条。
  记录已写但推进失败时改走 advance，不回滚事件；未发现本轮失败路径形成不可恢复状态。
- **C1 已核实**：真实事件已写/推进失败用例可补推进；第二次仅 replay，队列不再写入。
  `test_partial_event_failure_can_be_replayed_and_replay_is_idempotent` 通过。
- **C2 已核实，题设已过时**：M33 §4 不读系统时间；现行 M16 §4 表单 C 允许任意有事件的日期。
  采用 303 → already_advanced，而非拒绝过去日；过去日首次补推进和回退重交均实测，重交队列字节不变。
- **C3 已核实**：持 POST 锁排队时 provider 调用为 0；换到次日后释放锁，调用一次、旧日 record 返回 400，无事件。
- **C4 已核实**：today.md §4.1 已明确 record 省略 review-store 不推进，advance 省略则用登记队列；
  显式路径仍无需登记表，不能把“完全相同”理解为 record 也自动推进（`ky/__main__.py:1438`）。
- **D1 已核实，单线程前提不成立**：实际是 ThreadingHTTPServer；开不发请求的 TCP 连接后另发 GET，返回 200。
- **D2 已核实**：record 成功 303、重复 POST 400；advance 成功 303、重复 303/already_advanced。
  GET 与重定向后的 GET 没有写调用；合成 GET 前后文件不变，重复推进 manifest 不变。
- **D3 已核实，字段名需修正**：表单 A 是 minutes，study_minutes 属于 B；保存/清除为独立普通表单。
  HTMLParser 得到 A 的字段分别为 [date, minutes] 与 [date, clear]，清除不连带发送其他表单的字段，无需 JS。
- **D4 已核实**：进入 HTML 的题面、选项、答案、标题、阶段名、ID、错误文本统一走 _esc；学期名没有显示。
  `<`、`&`、script 文本转义用例通过（`ky/web/server.py:26` 及各 render helper）。
- **D5 不成立**：pending 只展示未推进提示与按钮，已存 reviews/outcome/study_minutes 全被跳过，见 M3。
- **D6 已核实（B2 阶段误报另计）**：注入 GET/POST RuntimeError，均返回 500；页面无异常详情或 traceback，详情进入 stderr。
  两种部分失败返回 400；未把异常转换为成功 303。
- **D7 已核实**：`ky/web/server.py:377` 的同一锁覆盖解析、重新 load_today、校验、写入及响应；不覆盖外部 CLI。
- **E1 部分已核实 / 部分无法核实**：Chrome 实际渲染的浅色页面，校准 innerWidth=390，scrollWidth=376；
  看到了时间/复习区、换行后的结果单选、学习分钟、记录及保存/清除按钮，无横向溢出或重叠。
  深色未验证：当前浏览器为浅色，现有控制接口没有主题仿真能力；不以 HTML/CSS 字符串代替视觉结论。
  浏览器临时尺寸已复原、临时标签已关闭；以上视觉结论仅覆盖该合成页面。

## 3. 必须改

### M1 / MAJOR：来源快照没有贯穿今日计算与记录

位置：`ky/today/port.py:85`、`:173`、`:183`；`ky/today/questions.py:38`、`:54`；`ky/today/record.py:127`。
唯一探针输入：合成队列放两个同科 progressing 项、登记该科树/真题索引/权重、当天已有完成事件；计数 Path.open 的读模式后调用 load_today。
结果：索引/权重各读 2 次、manifest 2 次、每个队列分片 2 次；树由出题计算现读，非已加载参数。
要求：装配一次读取并传递队列含已计算 ID、树/祖先关系、索引、冻结/报告等上下文；M24/记录计算使用公开的已加载端口。
复盘 helper 不再拿路径现读；预检/锁存/推进复用同一份来源；临时输出重读校验不属于禁止的输入重复读取。
按 today.md §2/§3 和 AGENTS.md #2 判必改；不因“暂未碰到文件被替换”豁免。建议影响模块：M13/M24/M28。

### M2 / MAJOR：冻结发布后的清理错误丢失持久化阶段

位置：`ky/storage/day_plan_store.py:220`；`ky/today/record.py:51`、`:53`。
唯一探针：正常合成积压触发冻结，仅在 freeze 目录临时文件的 Path.unlink 注入 PermissionError；调用 record_day({}, study_minutes=5)。
结果：stage=rejected，真实冻结事件 1 条、完成事件不存在；解除故障重交后冻结仍 1 条、完成事件成功写成。
原因：os.link 已发布，但 finally 清理抛出，latch 尚未返回，调用方 freeze_written 仍为 False。
要求：发布后的清理失败必须保留 freeze_written 阶段（或把已发布后的残留清理作为可恢复清理处理）；不靠消息文字猜阶段。

### M3 / MAJOR：pending 页面隐藏已存结果

唯一代码证据：`ky/web/server.py:199` 的 pending 分支仅输出提示/按钮；学习分钟及每项结果全部在 `else` 中。
正常输入：已存一条 correct 结果、study_minutes=0，推进失败；刷新页面仍看不到这份已存结果。
要求：两种 recorded 状态都只读列出已存结果与分钟；pending 再附提示和补推进按钮，符合 web.md §3 第 5 项。

### M4 / 规则必改：模块头缺公开接口列表

唯一证据：`ky/today/port.py:1`；AGENTS.md 的模块头要求明确包括公开接口。
要求：列出 load_today、today_view_hash、record_day、advance_recorded_day；无需改行为。

## 4. 建议改

- 恢复命令把 store/review-store/config 一并绝对化，或输出原 cwd 提醒；目前只保证原 cwd 可执行。
- 补齐深色视觉检查；本轮浅色窄屏截图不能证明深色可读性。

## 5. 不改（说明）

- C2 使用已推进重放响应，现行规格与实现一致；不新增过去日门槛，也不要求重交成功写一份事件。
- 完成事件旧 exists + replace 的跨进程覆盖风险沿用 M13 §10 D1/S19；本机网页串行已防重复，不按并发攻击开返工。
- M26 仅新写入限制 0–1440；旧读取仍接受其他日的大值，删除不存在报错，替换走 replace_bytes，不要求保留注释。
- CLI 对照只保留 today.md §6 明定的字节不变与失败提示例外；不另加摘要绑定或矩阵证据门槛。

## 6. 安全登记

CSRF/认证、跨进程并发与恶意链接沿用第 273 轮登记；本轮转义检查没有新增注入现象。
M2 是正常文件清理失败导致的阶段错误，不归入安全登记以回避修复；不扩展当前安全修复范围。

## 7. 最坏情况

已确认：冻结已经锁存却报普通 rejected；随后 pending 状态又隐藏已存结果，用户无法从页面核对保存内容。
合理推测：来源在重复读取之间变化会形成混合视图；本轮未用并发改文件来宣称实际数据损坏。
已有事件及 completion ID 保留、上述故障可恢复；本轮未发现正常串行回退重交造成二次推进。深色可读性仍无法确认。
