# 第 252 轮任务书：WP-M28c 返工**初检**（gpt-6.1-sol，续 sol61-m28）

## 这一轮只做初检（用户 2026-10-01）

用户要求：交付后只做初检，**彻底的大检查等全部工作做完后统一做**。所以本轮：

- 只核对你第 250 轮的 C1–C5 是否落实；用你 250 轮报告里的可复现输入各跑一次即可（每项 1 个探针为限）。
- 不重新通读全部实现、不重审 250 轮已判"通过"的部分、不再找新的测试缺口。
- 顺手看到的**新**问题：会让日常使用算错 / 丢数据 / 崩溃的才写进"必须改"；其他一律写进"留给最终大检查"一节，一行一条，不展开、不判 FAIL。
- 报告控制在约 60 行以内。

## 范围

worktree `F:\workspace\kaoyan-wt-m28c`（分支 `wip/m28c`）未提交改动里第 251 轮返工的部分。
返工任务书 `F:\workspace\kaoyan-ai-system\review\rounds\round-251-m28c-fix-task.md`；实现者报告在该 worktree 的 `review/rounds/round-247-m28c-luna.md` 末尾"第 251 轮返工"一节。

luna 交付后决策者直接改了两处（不必复查）：`ky/pacing/port.py`、`submit.py` 里的 `\uXXXX` 中文转义还原为中文字面量并合并拆开的字符串；
新提交 `--dry-run` 先打印 `new submission (dry-run; no files written)` 标题，再打印摘要。

## 已知、不在本轮

- 复盘设置接 IO2 `base_resolver`、拆分 `apply_pacing`：决策者合并时做。
- 250 轮安全登记两条：已登记，不复查。

## 验证

只跑：

```
py -3.12 -m unittest tests.contract.test_pacing_port
```

外加 C1–C3 各一个合成探针（系统临时目录，`PYTHONDONTWRITEBYTECODE=1`）。不跑全量、不跑其他模块。

## 输出

`F:\workspace\kaoyan-ai-system\review\rounds\round-252-m28c-rereview-sol61.md`：PASS / FAIL；C1–C5 逐条"已落实 / 未落实（附输入）"；"必须改"（若有）；"留给最终大检查"。

## 禁止

不联网；只写这一份报告；不修改其他文件；不读仓库外文件；不写个人数据。
