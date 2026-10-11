# 第 293 轮：前端第二版实现初检（gpt-6.1-sol，窗口 sol61-web-v2-r2，新会话）

你是独立评审者。规格在上一轮被你判 FAIL、6 条必须改已由决策者**逐条并入**
（`contracts/web.md` §8–§9、`contracts/today.md` §8，见提交 `c9acaa1`）；这一轮 luna 按并入后的规格实现了它。

本轮**只核对实现是否按规格落地、有没有引入日常会出错的回归**，每项最多 1 个探针。

## 先读

1. `AGENTS.md`（验证范围、严重度与威胁模型、**证据最小充分**、已知缺陷清单）。
2. `contracts/web.md` §8–§9（尤其是 M1–M6 并入后的文字）与 `contracts/today.md` §8。
3. 实现报告 `review/rounds/round-292-web-v2-luna.md`；改动看 `git diff 2fa2b71..HEAD`（或 `git show`）。
4. 你上一轮的报告 `review/rounds/round-291-web-v2-spec-review-sol61.md`——**核对决策者是否把你的六条替换文字
   如实并入了规格**（只核对你写过的文字有没有被改动或漏掉，不重新设计）。

## 必须逐条核对的实现点

**A. `load_queue_view`（`contracts/today.md` §8）**

- A1 返回键固定；`budget` 与同日同输入的 `load_today` **同值**；`caps` 五键与来源取值（含冻结时归零、配额 `null`）。
- A2 `buckets` 只来自 M9 `ClipResult` 五个桶、**不补未来 `queued`**、不含 `suspended` / `retired`；分钟数按 `estimated_minutes` 求和。
- A3 `backlog` 成员是 `deferred + unschedulable + unreachable`（**不是** M9 的 `backlog_minutes`）、
  `details` 前 20 项、`remaining_count`、`deferred` 的 `defer_count` 是预检 +1 值且不写回。
- A4 `ahead` 取原队列 `queued` / `scheduled` 且 `due_date > day`；条数与升序去重前 3 个日期。
- A5 `queue_registered` 恒 `true`；未登记 `state.review_queue` 是无效注册表（启动退出 2），不是 200 页面。
- A6 参数护栏；**一次调用每个来源只读一次**；`load_today` 与 CLI 输出**没有变化**。

**B. 三个只读页面（`contracts/web.md` §8）**

- B1 非 GET → 405 且带 `Allow: GET`，**不写任何文件**；未知路由 404；`/queue` / `/route` 的 `date` 校验 400；
  `/charts` 拒绝查询字段。
- B2 `GET /queue`：五桶条数与分钟、入选项字段、冻结置顶、空队列文字。
- B3 `GET /route`：`stage1_input_hash` 前 12 位（**不冒称** `actor` / 提交流）、阶段表与当前阶段、
  复盘周期与最近报告的 `base.min/max/mean` 与各科完成统计；未登记路线 / 未登记 pacing 的文字。
- B4 `GET /charts`：HTML 白名单 + **`plotly.min.js`**（`application/javascript; charset=utf-8`、正确 `Content-Length`、
  不列入入口）；文件名解码后校验；`../`、子目录、符号链接、其它扩展名 → 404；
  未登记目录 / 缺目录 / 缺脚本三种提示；**不生成、不补写**文件。
- B5 共同外壳适用于自渲染页面；离线图表 HTML 与其脚本**原样**返回（不加导航、不转义字节）。
- B6 三页 GET 与被拒请求前后**工作区文件树字节不变**。

**C. 测试是否真能否证上述**

- C1 契约测试是否覆盖了 §9 列出的行为（含跨视图一致性、图表脚本、405/404/400、字节树不变）。
- C2 有没有写死仓库数据量（规则 7）或把布局像素当验收。

## 输出

写 `review/rounds/round-293-web-v2-review-sol61.md`，≤ 90 行：

1. 结论 **PASS / FAIL**。
2. A1–A6、B1–B6、C1–C2 逐条：已核实（附一条探针结果）/ 不成立（附可复现输入）/ 无法核实（说明缺什么）。
3. 规格并入核对：你上一轮的六条替换文字是否如实落地（有出入就写明哪一段）。
4. **必须改**（附复现，每项 1 个探针）。
5. **建议改**（一行一条）。
6. **安全登记**（新现象；沿用既有登记写"无新增"）。
7. **最坏情况**。

## 纪律

- 只创建你这一份报告；不改实现 / 测试 / 规格 / 文档，不提交，不联网。
- **不跑全量**；复现只跑点名模块（`tests.contract.test_today_port`、`tests.contract.test_web_port`、必要时 `tests.test_cli`）或单条命令。
- **证据最小充分**：一条结论一个能跑的输入或 `文件:行`。
- 不读 gitignore 的个人数据；合成输入放系统临时目录；`PYTHONDONTWRITEBYTECODE=1`。
