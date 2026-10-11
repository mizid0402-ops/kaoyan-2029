# 第 288 轮任务书：pending 页要显示已存结果（gpt-6-luna，窗口 luna-fix-web，新会话）

## 来源

最终大检查 C（`review/rounds/round-283-final-c-sol61.md`）必须改 M3。

位置：`ky/web/server.py:199` 的 pending 分支只输出提示与补推进按钮；每项已存结果与学习分钟都在 `else` 里，
所以"完成事件已写、队列推进失败"之后刷新页面，用户看不到自己刚保存的内容。

sol 的复现：已存一条 correct 结果、`study_minutes=0`，推进失败 → 刷新页面仍看不到这份已存结果。

## 要做

1. 两种 recorded 状态（正常与 pending）都**只读**列出已存结果与学习分钟（`study_minutes=0` 显示"0 分钟"，
   与 `None` 的"未填写"区分开——这个区分已经做好了，别退化）。
2. pending 状态**额外**再给出提示与补推进按钮。
3. 依据：`contracts/web.md` §3 第 5 项。
4. 回归测试放 `tests/contract/test_web_port.py`，照该文件已有的渲染断言风格（HTML 文本断言，不是布局结论）。

## 不要做

- 只改 `ky/web/server.py` 与 `tests/contract/test_web_port.py`；不改 M33（`ky/today/`）、不改 CLI、不改写入路径。
- 页面继续不用 JavaScript；所有外部文本继续走 `_esc`。
- 不跑全量、不提交；不动 `ky/charts/`、`ky/question_bank/`。

## 验收（只跑这一条 + 一条探针）

```
py -3.12 -m unittest tests.contract.test_web_port
```

探针：构造"事件已写、推进失败"的状态，取页面 HTML，断言其中同时出现已存结果字样与"0 分钟"，
并仍带有补推进提示；贴修复前后对照。

## 报告

写 `review/rounds/round-288-web-pending-luna.md`，≤ 50 行：改法（`文件:行`）；修复前后 HTML 关键片段对照；
验收命令的 `Ran ... OK` 原文；"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"；未做 / 没把握的地方。

## 规则（照 `AGENTS.md`）

- 模块头写 M 编号与规格（`contracts/web.md`）；行宽 ≤ 100；函数 ≤ 约 60 行；注释引用 sol 283 M3。
- 含中文的文件只用编辑工具写；写完查有没有连续 `???`。
- 临时输入放系统临时目录；不读 `data/personal/`；不启动真实工作区的 `ky web`；设 `PYTHONDONTWRITEBYTECODE=1`。
