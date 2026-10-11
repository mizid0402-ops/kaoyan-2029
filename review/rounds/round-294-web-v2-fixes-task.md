# 第 294 轮任务书：前端第二版实现的 3 条必须改（gpt-6-luna，窗口 luna-web-v2-fix，新会话）

来源：`review/rounds/round-293-web-v2-review-sol61.md`（FAIL）。**只改这三条**，别碰其它行为与模块。

## R1 / MAJOR：队列页遗漏规格明写的展示行为

`ky/web/server.py:72`、`:110`、`:129`。sol 的复现：合成合法配置总分钟 5、各科最低分钟 0，入队一条预计 30 分钟、
`2026-10-01` 到期的 `queued` 项，查看 `2026-10-08` → 实测
`freeze=True; unschedulable=1; date_heading_before_freeze=True; split_hint_present=False; english_tier_present=True`。

要改：

1. **冻结提示放在日期 / 时间摘要之前**（规格 `contracts/web.md` §8.2 的顺序，sol 291 M2 明确并入）。
2. **`unschedulable` 的项要给出"单项太大，请拆分"的提示**（§8.2 第 3 项的列名含义）。
3. **档位用中文展示**（学过 / 掌握中 / 已巩固）——复用"今天"页已有的档位显示映射，不要再出英文 `learned` / `progressing` / `consolidated`。
4. 补上 §9 点名的断言：冻结顺序、五个桶的列名与字段、中文档位。

**不要改业务口径**（桶成员、分钟计算、`caps` 等一律不动），只改渲染与顺序。

## R2 / MAJOR：未知 POST 的路由判定晚于表单解析

`ky/web/server.py:736`。sol 的复现：无 `Content-Type` 的空体 `POST /unknown` → 实得 **400**；按 `contracts/web.md` §8.1
未知路由应返回 **404**（405 只用于"已知的只读路径 + 非 GET"）。

要改：**先判路由，再对已知写入路由解析表单**。保留三个首版表单的行为与只读路径的 405。改完补一条断言：
无 Content-Type / 空体的 `POST /unknown` → 404。

## R3 / MAJOR：§9 要求的可否证测试没落地

位置：`tests/contract/test_today_port.py:151`、`:217`；`tests/contract/test_web_port.py:81`、`:137`。
sol 的反例：运行期把 `_bucket_mapping` 的 minutes 恒置 0，三个新增 M33 测试**全部通过**——即测试不能否证"桶分钟算错"。

要补（都来自已并入的 `contracts/web.md` §9 与 `contracts/today.md` §8，不要扩大范围）：

**M33**

- 真实链路：M8 配额缩放 / 冻结 → M9，而不是只造空队列。
- 五个桶的**计数与分钟**用既有端口（M9 `ClipResult` / `ReviewItem.estimated_minutes`）推导的期望值断言；
  `caps` 的分钟与来源；`selected` / `backlog.details` 的**值与顺序**；`backlog.remaining_count`；`ahead` 的条数与日期。
- **每个来源的读取计数**（现在只有空队列时队列端口一次）；同名同输入的 `load_today` 与 `load_queue_view`
  的 `budget`、入选 ID、五桶计数 / 分钟一致。
- 期望值必须由合成输入与既有端口推导，**不得写死仓库数据量**（规则 7）。

**M16**

- 队列非空时的字段与冻结**置顶**；
- `/queue`、`/route` 的非法日期与重复查询字段 → 400；
- 请求期来源错误 → 400（与启动期退出 2 分开）；
- 登记但空路线、周期尚未开始两种分支；
- 图表文件名的编码、未登记 `products.charts` 的两种提示；
- 上述路径的"工作区文件树字节前后不变"；
- 方法覆盖要含 `plotly.min.js` 资源端点。

要求：补完之后，**R1 / R2 与"桶分钟置零"这类改动都必须让测试失败**（在报告里用一次变异探针证明）。

## 不要做

- 不改 `contracts/` 规格、不改 `ky/today` 的业务口径（除 R1 的渲染映射）、不动 `ky/charts` / `ky/pacing` / `ky/storage`。
- 不新增写入路径、不引入依赖、不写 JavaScript；只读路径继续不写任何文件。
- 不跑全量、不提交（提交由决策者做）。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_today_port
py -3.12 -m unittest tests.contract.test_web_port
py -3.12 -m unittest tests.test_cli
```

再加：(a) R1 的渲染探针（冻结顺序 / 拆分提示 / 中文档位）；(b) R2 的未知 POST → 404；
(c) **变异探针**：把桶分钟置零后相关测试必须失败（贴失败输出）。

## 报告

写 `review/rounds/round-294-web-v2-fixes-luna.md`，≤ 80 行：逐条 R1 / R2 / R3 的改法（`文件:行`）、
三条探针（含变异探针的失败输出）、三条验收命令的 `Ran ... OK` 原文、"全量：未跑"、怀疑模块、未做 / 没把握的地方。

## 规则（照 `AGENTS.md`）

- 行宽 ≤ 100；函数 ≤ 约 60 行；注释引用 sol 293 R1 / R2 / R3。
- 含中文的文件只用编辑工具写；写完查有没有连续 `???`。
- 临时输入放系统临时目录；不读 `data/personal/`；`PYTHONDONTWRITEBYTECODE=1`。
