# 第 294 轮：Web v2 三条必须改

## R1：队列页渲染

- `ky/web/server.py:42`、`:77`、`:126`、`:138`：抽出今天页共用的中文档位映射；冻结节移至日期标题前；单项太大桶增加“单项太大，请拆分”提示。只改渲染。
- `tests/contract/test_web_port.py:66`：断言冻结顺序、五桶标签与计数/分钟、拆分提示及三种中文档位。
- 探针：`py -3.12 -m unittest tests.contract.test_web_port.WebPortContractTests.test_queue_render_freeze_order_bucket_fields_split_and_tiers`
  → `Ran 1 test in 0.000s`，`OK`。

## R2：未知 POST 路由

- `ky/web/server.py:736`：只读路径仍先返回 405；写路由白名单在 `_read_form` 前判定，保留三种已知表单处理。
- `tests/contract/test_web_port.py:361`、`:357`：资源端点纳入非 GET 405；原始 HTTP 空体、无 `Content-Type` 的 `POST /unknown` 断言 404。
- 探针输出：`POST /unknown, empty body, no Content-Type -> 404`。

## R3：M33 / M16 可否证断言

- `tests/contract/test_today_port.py:127`、`:181`、`:319`：合成路线配额经 M8 缩放后进入真实 M9 预检；从 `ClipResult` 推导五桶条数/分钟、caps、selected、backlog 明细值与顺序、科目汇总、剩余数、ahead；比较 today/queue 两视图；统计配置、队列、计划、路线、可用时间、课表、复盘设置与题目来源读取次数。另覆盖真实冻结路径。
- `tests/contract/test_web_port.py:190`、`:230`、`:264`、`:361`：覆盖登记但空路线、周期未开始、非空冻结队列、未登记图表提示；非法日期/重复查询与请求期来源错误 400；编码文件名、Plotly 资源方法 405；相关只读请求前后比较工作区文件树字节。
- 分钟置零变异：将运行期 `_bucket_mapping` 的 `minutes` 固定为 0，再运行 M33 真实链路测试。输出：
  `FAIL: ...test_load_queue_view_uses_five_m9_buckets_and_matches_today`；
  `AssertionError: ... bucket minutes 0 != ClipResult minutes 56 ... minutes 8 ...`；
  `Diff is 791 characters long.`；
  `Ran 1 test in 0.463s`，`FAILED (failures=1)`。

## 验收

- `py -3.12 -m unittest tests.contract.test_today_port`：`Ran 16 tests in 41.169s`，`OK`。
- `py -3.12 -m unittest tests.contract.test_web_port`：`Ran 17 tests in 5.759s`，`OK`。
- `py -3.12 -m unittest tests.test_cli`：`Ran 63 tests in 99.502s`，`OK`。
- 全量：未跑。
- 怀疑模块：无新增；真实链路覆盖 M8 `ky/schedule/budget` 与 M9 `ky/schedule/review_clip`，未改其实现。
- 未做 / 没把握：未做浏览器像素布局检查（不属 §9 验收）；未验证点名范围外模块。首轮 web 测试的图表夹具互相影响已修正并重跑通过。
