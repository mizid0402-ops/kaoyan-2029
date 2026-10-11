# Round 288: pending 页面显示已存结果

## 改法

- `ky/web/server.py:1`：模块头标明 M16、`contracts/web.md` 与公开接口。
- `ky/web/server.py:201`：pending 仍显示未推进提示和补推进表单；记录分钟与各项结果移至两个 recorded 状态共用的只读渲染。
- `tests/contract/test_web_port.py:58`：临时工作区持久化 correct 完成事件和 0 分钟，构造未推进视图并断言 HTML 文本。
- 保留 `None` 显示“未填写”；外部记录 ID 与结果仍经 `_esc`。

## HTML 对照

修复前（pending）：`<h2>已记录，复习队列未推进</h2>...<button>补推进复习队列</button>`；没有结果区。

修复后（pending）：上述提示和按钮仍在，并显示 `<h2>记录结果</h2><p>学习分钟：0 分钟</p><p>rv_math1_limit_0001：对</p>`。

## 验收

- `PYTHONDONTWRITEBYTECODE=1 py -3.12 -m unittest tests.contract.test_web_port`
- 原文：`Ran 10 tests in 3.351s` / `OK`
- 探针：单测方法 `test_pending_record_renders_saved_results_and_zero_minutes`
- 原文：`Ran 1 test in 0.030s` / `OK`
- 全量：未跑（按 AGENTS.md，由决策者提交前统一跑）

## 未做 / 把握边界

- 未启动真实工作区服务、未做浏览器布局检查；探针以 `_render` 返回的 HTML 做文本断言。
- 初次尝试从 `load_today` 组装视图时，最小 fixture 缺少知识树登记而失败；回归改为从临时工作区已存事件构造 pending 视图，未改 M33。
