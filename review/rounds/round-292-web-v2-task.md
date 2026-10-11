# 第 292 轮任务书：实现前端第二版（只读三页）+ M33 队列视图（gpt-6-luna，窗口 luna-web-v2，新会话）

规格已由 sol 审过（`review/rounds/round-291-web-v2-spec-review-sol61.md`，FAIL 6 条），决策者已把它的
**M1–M6 替换文字逐条并入** `contracts/web.md` §8/§9 与 `contracts/today.md` §8。**按并入后的规格实现**。

## 规格里最容易做错的几点（逐条对照，别凭印象）

1. `state.review_queue` 是**必需键**：合法 `Workspace` 里 `queue_registered` 恒为 `true`；
   未登记属于无效注册表 → 启动退出 2。**不要**为"未登记队列"写 200 页面。
2. `buckets` **只**来自 M9 `ClipResult` 的五个桶，**不补未来 `queued`**；`backlog` 是
   `deferred + unschedulable + unreachable`（≠ M9 的 `backlog_minutes`，后者只含 `deferred`）；
   `deferred` 的 `defer_count` 是**本次预检 +1 后**的值（不写回）；`ahead` 取原队列里 `state ∈ {queued, scheduled}`
   且 `due_date > day` 的项（≠ `scheduled_ahead` 桶）。
3. `caps` 的五个键与来源取值照 §8 表格；冻结时分钟为 0、来源 `freeze`、配额 `null`。
4. `/charts` **必须额外提供 `plotly.min.js`**（离线图表 HTML 引用同目录的它），`Content-Type: application/javascript; charset=utf-8`，
   **不列入入口列表**；HTML 与脚本都给正确的 `Content-Length`；文件名先按 URL 路径解码再白名单校验。
5. 三个入口与 `/charts/<文件名>` 的非 GET → **405 + `Allow: GET`**；未知路由 404；
   `/queue` 与 `/route` 只接受一个 `date` 查询字段、`/charts` 不接受查询字段；
   启动期注册表错误退出 2 与请求期来源错误 400 是两回事。
6. 共同外壳（无 JS、导航、转义）**不适用于**原样提供的离线图表 HTML 与其 Plotly 脚本。

## 要读的规格

- `contracts/web.md` §8（三个只读页面：`/queue`、`/route`、`/charts`）与 §9（契约测试要点）。
- `contracts/today.md` §8（`load_queue_view`）与 §2（公开接口列表）。
- `docs/模块地图.md` 的 M16 / M33 两行。
- 现有实现：`ky/today/port.py`（`load_today` 的装配与映射 helper）、`ky/web/server.py`（现有路由与渲染写法）、
  `ky/web/cli.py`、`tests/contract/test_web_port.py`、`tests/contract/test_today_port.py`。

## 要做（按这个顺序，每步都照规格）

1. **M33 `load_queue_view(workspace, day)`**（`contracts/today.md` §8）：
   复用 `load_today` 的那套**一次读取**装配（同一个来源快照对象），返回规格表里的稳定映射。
   - 参数先校验再运算（非 `Workspace` / 非 `date` → `ContractError` 带参数名路径）。
   - **不改** `load_today` 的输出；`ky/today/__init__.py` 导出新名字；模块头补上它。
   - 桶名与 M9 的五个输出桶一致；`budget` 与 §3 同形状同值。
2. **M16 三个只读页面**（`contracts/web.md` §8）：
   - `GET /queue`：用 `load_queue_view`；按 §8.2 的顺序渲染；空队列 / 未登记队列两种文字。
   - `GET /route`：用 M11 `RoutePlanStore.current()` 与 M28 只读端口；当前阶段高亮；未登记路线 / 未登记 pacing 的文字。
   - `GET /charts` 与 `GET /charts/<文件名>`：按 §8.4 的白名单列出与按字节返回（`Content-Type: text/html; charset=utf-8`）；
     名字不匹配 / 子目录 / `../` → 404；目录不存在或没有匹配文件 → 给生成命令的提示。
   - 三页共用 §3 的外壳与风格（服务端渲染、无 JavaScript、浅色 / 深色、手机宽度、全部文本 `_esc` 转义、
     顶部导航）；**不读投影、不缓存**。
   - 对这三个路径的 `POST`（及其它方法）→ **405** 简短页面，**不写任何文件**。
   - §4 的三类写入（`/availability`、`/record`、`/advance`）**原样不动**。
3. **测试**（照 §9，行为断言，不写布局断言、不写死数据量）：
   - `tests/contract/test_today_port.py`：`load_queue_view` 的五个桶、空队列、未登记队列、参数护栏、
     以及"与 `load_today` 同口径"（同一输入下两页的分钟数与桶分类一致）。
   - `tests/contract/test_web_port.py`：三页各自的关键行为；`POST` → 405 且工作区文件树字节前后不变；
     三页 `GET` 前后工作区文件树字节不变；`/charts` 的 404 与白名单。
   - 测试用临时工作区（照现有夹具），`--port 0` 在线程里起服务。

## 不要做

- 不新增任何写入路径、不改 §4 表单与 POST 语义、不动 `ky/charts` / `ky/pacing` / `ky/storage` / `ky/question_bank` 的实现。
- 不引入新依赖（只用标准库 + 既有依赖）；不写 JavaScript。
- 不跑全量、不提交（提交由决策者做）。
- 不改 `contracts/` 里已审批的规格文字；实现中若发现规格确实写不通，**停下来写进报告**，不要自己改规格。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_today_port
py -3.12 -m unittest tests.contract.test_web_port
py -3.12 -m unittest tests.test_cli
```

另加两条探针：(a) 三页 `GET` 前后工作区文件树字节不变（只读验收）；(b) 三页 `POST` → 405 且不写文件。

## 报告

写 `review/rounds/round-292-web-v2-luna.md`，≤ 80 行：逐块（M33 视图 / 三页 / 测试）的改法（`文件:行`）、
两条探针输出、三条验收命令的 `Ran ... OK` 原文、"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"、
怀疑受影响但没跑的模块、未做 / 没把握的地方、以及你对规格的任何异议。

## 规则（照 `AGENTS.md`）

- 模块头写 M 编号与规格；行宽 ≤ 100；函数 ≤ 约 60 行（D7）；注释写"为什么"并引用 sol 291 的条目号。
- 含中文的文件只用编辑工具写；写完查有没有连续 `???`。
- 临时输入放系统临时目录；不读 `data/personal/`；不启动真实工作区的 `ky web`；`PYTHONDONTWRITEBYTECODE=1`。
