# 第 295 轮：Web v2 三条必须改复验（sol61）

## 结论：PASS

对象：`302a46b`；对照 293 的 R1/R2/R3、294 报告、修复 diff 与 web §9。
只创建本报告；未改实现/测试/规格，未提交、未联网、未读 gitignore 个人数据。
本轮使用 `PYTHONDONTWRITEBYTECODE=1` 与 `py -3.12 -B`；合成工作区均在系统临时目录。
定向验收：M33 四条队列/冻结测试、M16 五条只读测试及两条首版表单测试，共 11 条，4.062s，OK。
全量：未跑（按 AGENTS.md，由决策者提交前统一跑）；未复跑 CLI 或其它模块。

## R1：已关闭

唯一探针：`py -3.12 -B "$env:TEMP\round295_web_probe.py" r1`。
输入沿用 293：总分钟 5、各科最低分钟 0，一条 queued 项预计 30 分钟，10-01 到期，查看 2026-10-08。
实得：`freeze=True; unschedulable=1; freeze<date<time=True; split=True; English=False`。
`ky/web/server.py:77` 已将冻结节放到日期标题前；桶中显示“单项太大，请拆分”。
三种中文档位由 `tests/contract/test_web_port.py:66` 断言学过/掌握中/已巩固且不含英文档位，本轮通过。

## R2：已关闭

唯一探针：`py -3.12 -B "$env:TEMP\round295_web_probe.py" r2`。
无 Content-Type、空体 `POST /unknown` 实得 404。
同一探针覆盖 queue/route/charts/HTML/Plotly JS 五个只读路径的八种非 GET 方法；40 次均为 405 + `Allow: GET`。
三首版表单定向验收通过：availability 成功 303、非法字段 400 且不写；record 成功 303、非法项/重放 400；advance 保留 advanced/already_advanced。
证据：`tests/contract/test_web_port.py:531`、`:665`；修复只提前路由判定，已知表单处理代码未变。

## R3：已关闭

唯一变异探针：`py -3.12 -B "$env:TEMP\round295_web_probe.py" r3`。
运行期 patch `_bucket_mapping` 为 `{'count': len(items), 'minutes': 0}`，未写实现文件。
真实链路测试 `test_load_queue_view_uses_five_m9_buckets_and_matches_today` 被拒绝：1 failure、0 errors，0.455s；失败在桶分钟 0 与 M9 的 56/8 等值不符。
§9 抽查与本轮定向通过的证据如下（静态位置不另计运行探针）：
- `tests/contract/test_today_port.py:319`：真实 M8 路线配额缩放→M9，五桶计数/分钟、caps；两视图 budget、入选 ID 顺序及五桶数值一致。
- `tests/contract/test_today_port.py:251`：selected/backlog 明细逐字段、列表顺序、总数/分钟、科目汇总、截断剩余数及 ahead 日期顺序。
- `tests/contract/test_today_port.py:181`：两视图七个来源端口合计各两次；题目入口一次、知识树按入选科目计数；未登记复盘报告端口零次。
- `tests/contract/test_today_port.py:472`：真实冻结读取链下 caps 归零、配额 null、selected 空、五桶归零；上限另由 `:353` 覆盖。
- `tests/contract/test_web_port.py:326`：queue/route 非法日期与重复查询 400、请求期 ContractError 400，包含 Plotly JS 的非 GET 拒绝。
- `tests/contract/test_web_port.py:190`：登记但空路线与周期未开始；周期分支使用 `cycle_for_date=None` 的端口替身。
- `tests/contract/test_web_port.py:264`：未登记 charts 提示；`:292` 覆盖编码文件名链接、HTML/JS 原字节与 MIME。
- `tests/contract/test_web_port.py:361`：只读 GET/被拒请求前后文件树字节相等；空路线、冻结队列、未登记图表测试也各自比树。
以上补测能否证原分钟缺陷；修复 diff 未引入业务计算或只读写入分支，未发现新的日常问题。

## 仍需改

无；R1/R2/R3 均关闭。

## 建议改

- 来源计数可按视图分别断言，并补登记可用时间/课表/复盘后的读取场景；当前部分可选端口测的是未登记分支。
- 沿用 293 建议：M16 模块头补列实际使用的 M11/M28/M8，方便替换模块。

## 安全登记

无新增。

## 最坏情况

已确认：原三项缺陷已修复，定向验收通过，分钟置零变异被测试拒绝；合成只读请求未改变文件树。
合理推测：可选来源已登记场景的读取回归仍可能漏检，属于测试覆盖建议，未确认当前存在重复读取或算错。
未验证：个人数据、浏览器像素布局及点名范围外模块；本次 PASS 仅针对三项复验和修复直接回归。
复现脚本保留于系统临时目录 `round295_web_probe.py`；分别用 r1/r2/r3，每项仅执行一个探针。
