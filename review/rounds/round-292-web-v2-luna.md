# 第 292 轮实现报告：Web v2 / M33 队列视图

## 改动

- **M33 视图**：[ky/today/port.py:79](../../ky/today/port.py#L79) 增加 `load_queue_view`；复用单次来源装配与保留的 M9 `ClipResult`，构造固定五桶、caps、入选明细、积压和 ahead 映射。延期期数取 M9 预检后的对象，不写回。映射 helper 在 [ky/today/port.py:166](../../ky/today/port.py#L166)；公开导出在 [ky/today/__init__.py:3](../../ky/today/__init__.py#L3)。`load_today` 的输出结构保持原样。
- **三个只读页**：[ky/web/server.py:71](../../ky/web/server.py#L71) 渲染 `/queue`；[ky/web/server.py:161](../../ky/web/server.py#L161) 从 M11/M28/M8 读取路线与复盘状态；[ky/web/server.py:267](../../ky/web/server.py#L267) 枚举图表与按白名单读文件。页面共享导航外壳；HTML/Plotly 按原字节、MIME 与长度返回；只读路径的非 GET 返回 405 / `Allow: GET`。原有三种写入路由未改。
- **测试**：[tests/contract/test_today_port.py:116](../../tests/contract/test_today_port.py#L116) 覆盖空视图、参数路径、五桶一致性、路线配额、冻结 caps 和 20/3 截断；[tests/contract/test_web_port.py:64](../../tests/contract/test_web_port.py#L64) 覆盖必需队列注册启动失败、路线报告、图表资源/白名单及读写拒绝。

## 文件树探针

- **(a) 三页及资源 GET**：queue/route/charts/HTML/JS 返回 200；图表目录空或脚本缺失时显示提示；越界/缺失文件 404，未知图表查询 400。GET 组前后临时工作区文件树逐路径字节相等。输出：`Ran 1 test in 0.603s` / `OK`。
- **(b) 非 GET**：POST `/queue`、PUT `/route`、DELETE `/charts`、PATCH 图表文件均返回 405 与 `Allow: GET`；拒绝组前后文件树逐路径字节相等。输出同上（与 (a) 在同一探针中分别断言）。

## 验收

```text
Ran 16 tests in 28.582s
OK

Ran 13 tests in 3.910s
OK

Ran 63 tests in 70.995s
OK
```

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。

## 边界与异议

- 怀疑受影响但未单独运行模块：M9 `review_clip`、M11 `route_store`、M28 pacing；其端口经本轮契约测试间接调用。
- 未做浏览器像素/颜色位置检查；契约明确不以布局作为验收。使用合成临时工作区，未读 `data/personal/`，未启动真实工作区服务。
- 对并入后的规格无异议；未更改 `contracts/` 或模块地图。
