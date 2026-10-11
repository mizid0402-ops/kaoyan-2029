# 第 293 轮：Web v2 实现初检（sol61）

## 结论：FAIL

对象：`00a2368`；已读 AGENTS.md、两份规格、291/292 报告，审查 `2fa2b71..HEAD` 的相关差异。
只新增本报告；未改实现、测试、规格，未提交、未联网，未读被忽略的个人数据。
验证：`PYTHONDONTWRITEBYTECODE=1`，`py -3.12 -B -m unittest tests.contract.test_web_port tests.contract.test_today_port` → 29 项，32.571s，OK。
全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。未另跑 tests.test_cli；已有固定基线 CLI 对照随 today 模块通过。
以下代码位置是静态核对证据，不冒称新增运行探针；动态复现各项仅一条。

## 逐条核对

- A1 已核实：`ky/today/port.py:188` 返回固定十键；budget 与原装配相同，caps 五键取 ClipResult，冻结归零且配额 null，无配额也为 null。
- A2 已核实：`ky/today/port.py:171` 只映射 M9 五元组，计数/分钟由长度与 estimated_minutes 推导；没有补未来 queued 或加入停用项的支路。
- A3 已核实：`ky/today/port.py:181` 按 deferred+unschedulable+unreachable 拼接，截前 20 项、计算剩余数；保留 M9 加一后的对象，函数不写回。
- A4 已核实：`ky/today/port.py:184` 从原 items 筛 queued/scheduled、due_date>day，全部计数，ISO 日期升序去重截前三。
- A5 已核实：`test_missing_review_queue_registration_fails_startup` 实跑通过：缺 state.review_queue 返回 2；合法视图恒 true。
- A6 已核实（代码与既有对照）：`ky/today/port.py:79` 先校验再读来源，仅一次装配/计算，跳过题库；load_today 仅改为从保留的 ClipResult 取 selected，映射未改，固定基线 CLI 测试通过。各来源完整读取计数的验收缺口见 R3。
- B1 不成立：探针 `unknown_post()` 的无 Content-Type、空体 POST /unknown → 400，规格要求未知路由 404；其它只读方法在装配前拒绝、Allow: GET 及日期/查询护栏可见 `ky/web/server.py:670`。
- B2 不成立：探针 `queue_render()` 得到真实冻结、unschedulable=1；日期标题先于冻结，缺拆分提示，明细出现英文档位。五桶与字段渲染、空队列文字其余已有，见 R1。
- B3 已核实：`test_route_page_shows_current_phase_and_latest_report` 实跑通过，规划输入前 12 位、当前阶段、最大终日报告及 base/完成统计成立；空路线/未登记 pacing 与 cycle=null 分支核对 `ky/web/server.py:191`。
- B4 已核实（代码及资源测试）：`ky/web/server.py:356` 解码后白名单/分隔符检查，拒绝链接并要求目标直接位于目录；JS 精确名、完整 MIME/长度和原字节返回成立；未登记/缺目录/缺脚本提示均有且不生成文件。
- B5 已核实：`ky/web/server.py:42` 为三个成功入口共用外壳、导航和转义；离线 HTML/JS 走原字节响应，资源契约测试通过。
- B6 已核实：`test_readonly_pages_resources_methods_and_workspace_tree` 实跑通过：三入口与 HTML/JS GET，以及四种非 GET 拒绝前后，合成工作区逐路径文件字节相等。
- C1 不成立：探针 `coverage_mutation()` 将五桶分钟全部改为 0，三个新增 M33 测试仍通过（3 项、0 failures、0 errors）；§9 的其它明确缺口见 R3。
- C2 已核实：`tests/contract/test_today_port.py:217` 的 25/5 是合成项数，20/3 是规格展示上限；新增测试未钉住仓库数据量，也没有布局像素验收。

## 规格并入核对

对照 291 的六条替换案与 `c9acaa1`：语义均如实并入，无实质漏项；排版、措辞重排不构成另定规则。
- M1：today §8 恒 true/必需键、web §8.2 启动拒绝与空库处理均保留。
- M2：固定映射、ClipResult/caps、backlog/ahead、单次读取和冻结先于日期摘要均保留（today §8、web §8.2）。
- M3：公开读取链、stage1_input_hash、右开阶段、周期终日和报告真实统计均保留（web §8.3）。
- M4：Plotly 例外、原字节/MIME/长度、同一白名单、三种缺失提示与禁止补写均保留（web §8.1/§8.4）。
- M5：date/查询、全部非 GET 405、未知路由 404、启动与请求错误分离均保留（web §8.1）。
- M6：跨视图值/顺序、全来源读取计数、图表脚本/编码/缺失提示等验收均保留（web §9）；实现测试没有完整兑现。

## 必须改

### R1（MAJOR）：队列页遗漏明确的展示行为

位置：`ky/web/server.py:72`、`:110`、`:129`。合成合法配置总分钟 5、各科最低分钟 0，入队一条预计 30 分钟、2026-10-01 到期的 queued 项，查看 2026-10-08。
一条复现：临时探针 `queue_render()` 输出 `freeze=True; unschedulable=1; date_heading_before_freeze=True; split_hint_present=False; english_tier_present=True`。
预期：冻结提示在日期/时间摘要前；单项太大提示拆分；档位沿用中文展示。调整渲染并补 §9 点名的冻结顺序/字段断言，不修改业务口径。

### R2（MAJOR）：未知 POST 的路由判定晚于表单解析

位置：`ky/web/server.py:736`。一条复现：`unknown_post()` 在合成服务器发送无 Content-Type 的空体 `POST /unknown`，实得 400；应按 web §8.1 返回 404。
先判路由，再对已知写入路由解析表单；保留三个首版表单及只读 405 行为。此解析顺序首版已有，但本轮新规格明确要求未知路由 404，不能据此验收通过。

### R3（MAJOR）：§9 要求的可否证测试未完整落地

位置：`tests/contract/test_today_port.py:151`、`:217`；`tests/contract/test_web_port.py:81`、`:137`。
一条复现：`coverage_mutation()` 用运行期 patch 将 `_bucket_mapping` 的 minutes 恒置 0；三个新增 M33 测试全部通过，不能否证五桶分钟错误。
必须按 §9 补齐真实 M8 配额缩放/冻结→M9 的链路断言，五桶计数/分钟、明细/backlog 值与顺序的端口对照，以及每个来源的读取计数（现仅空队列计队列端口一次）。
M16 还缺队列非空字段/冻结置顶、queue/route 非法日期与重复查询、请求期来源错误 400、登记但空路线/周期未开始、编码文件名/未登记 charts 提示及对应文件树不变断言；路由方法覆盖也应包含 JS 资源。
这些均来自已并入的 §9，不要求增加其它模块测试或全量；补测须能拒绝本轮 R1/R2 和上述分钟置零实现。

## 建议改

- M16 模块头的“Business data crosses M33 and M26 ports”补列实际使用的 M11/M28/M8，方便后续替换模块。

## 安全登记

无新增；沿用 291 的离线 HTML/JS 同源脚本登记及既有并发登记，不另开安全返工。

## 最坏情况

已确认：冻结信息顺序/中文档位/拆分提示不符规格，未知 POST 状态码不符；错误桶分钟能逃过新增测试。未发现本轮新增写入或数据丢失路径。
合理推测：缺少真实计算链与数值对照，会让后续配额或积压展示回归漏检；不是已确认的当前算错。未验证个人数据、浏览器布局或点名范围外模块。
复现脚本仅在系统临时目录：`C:\Users\Lenovo\AppData\Local\Temp\round293_web_probe.py`，以 py -3.12 -B 和上述环境变量运行；每个函数对应一项发现。
