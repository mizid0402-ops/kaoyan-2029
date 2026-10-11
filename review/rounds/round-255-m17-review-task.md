# 第 255 轮任务书：M17 可视化 ⑤a 实现**初检**（gpt-6.1-sol，续 sol61-m17）

## 这一轮只做初检（用户 2026-10-01）

- 只核对实现是否落实规格 `contracts/charts.md` 与你第 253 轮的 M1（状态库空库语义）；每项最多 1 个合成探针。
- 不通读全部代码、不找新的测试缺口、不评视觉效果。
- 日常使用会算错 / 崩溃 / 报错退出的写"必须改"（附输入）；其他一律一行写进"留给最终大检查"。报告约 50 行以内。

## 范围

主仓库 `F:\workspace\kaoyan-ai-system` 未提交改动：`ky/charts/`、`ky/__main__.py`（`chart` 子命令）、`tests/contract/test_charts_port.py`、
`kaoyan.workspace.yaml`（`products.charts`）、`.gitignore`、`pyproject.toml`、`docs/模块地图.md`、`README.md`。
任务书 `review/rounds/round-254-m17-task.md`；实现者报告 `review/rounds/round-254-m17-luna.md`。

luna 交付后决策者改过（不必复查）：科目改为 `config.active_subjects()`（规格"在考科目"）；页面标题改中文并做 HTML 转义；
`div_id` 只由页面类型与序号决定；周课表顶部标注分两行。

## 验证

只跑 `py -3.12 -m unittest tests.contract.test_charts_port`，外加探针（系统临时目录，`PYTHONDONTWRITEBYTECODE=1`）。不跑全量。

## 输出

`F:\workspace\kaoyan-ai-system\review\rounds\round-255-m17-review-sol61.md`：PASS / FAIL；"必须改"（若有）；"留给最终大检查"。

## 禁止

不联网；只写这一份报告；不修改其他文件；不读仓库外文件；不读 `data/personal/`、`outputs/` 与 gitignore 的学习状态。
