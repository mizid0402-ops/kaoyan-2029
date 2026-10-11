# 评审任务：WP-G3c 余项拆分（`ky/__main__.py` 六个大函数）

工作区状态：`master` = `24371ee`（已提交的上一批）。**待审的是工作区未提交的改动**：
`ky/__main__.py`（+712/-296 左右）与 `tests/test_cli_split_baseline.py`（+174）。
实现报告 `review/rounds/round-166-wp-g3c-remainder-luna.md`（实现者自述，**只当线索**）。
任务书 `review/rounds/round-166-wp-g3c-remainder-task.md`（验收标准在"验收"一节）。
仓库根 `AGENTS.md` 是你的常驻规则，**先读它的"验证范围"与"评审严重度与威胁模型"两节**。

## 只做这三件事

1. **对照基线是否真的取到旧版**：新增测试类 `CliG3cRemainderSplitBaselineTests` 用
   `git show 24371ee:ky/__main__.py`。核对它取到的确实是拆分前的长实现（六个函数各自达到
   断言的长度下界），且**不是**用 `HEAD`（`AGENTS.md` 第 12a 条要求固定提交哈希）。
   反例检查：把基线改成 `HEAD` 后该测试应当失败或不再有意义——说明理由即可，不必真改。
2. **拆出来的函数是否名副其实**：读 `ky/__main__.py` 的完整 diff，核对
   - 六个主函数确实变短、每个新辅助函数做一件事（不是"只转发参数的辅助函数"）；
   - **用户可见输出逐字节不变**：错误消息、打印字段、字段顺序、退出码。你自己找几个
     **任务书没写进对照测试的**输入来验（例如 `ledger --subject`、`route submit` 成功路径、
     `snapshot --vocab-db`、`month-close --json`、`review-queue migrate --apply`），
     用 `git stash` 或 `git show 24371ee:ky/__main__.py` 取旧版，比较两版 `(退出码, stdout, stderr)`。
   - `resume` 的"日期早于未解除冻结"拒绝仍发生在**任何写入之前**（sol 125 那条）。
3. **失败场景是否断言了状态而不只是三元组**：任务书要求 `resume-before-freeze` 场景断言
   **没有恢复记录**。核对它真的断言了（不是只比退出码）。

## 怎么做

- 用 `git archive 24371ee` 展开到系统临时目录，新实现从工作区复制，在同一组输入上对比。
- 做变异 / 调换时设 `PYTHONDONTWRITEBYTECODE=1` 并清 `__pycache__`。
- **只读**：不要改仓库源码、不要提交。
- **不跑全量测试**（`AGENTS.md` 验证范围）。要复现只跑：
  `py -3.12 -m unittest tests.test_cli_split_baseline` 及你为复现缺陷需要的最小命令。

## 报告

写到 `review/rounds/round-167-g3c-remainder-review-codex.md`：
结论（PASS / FAIL）、"必须改"（每条给可复现输入与实测输出）、"建议改"、"不改"（你验过没问题的路径），
以及**安全登记一节**（按 `AGENTS.md` 的威胁模型：恶意输入 / 手工篡改 / 精确竞态才算，日常用手写错不算）。
"必须改"只列日常正常使用会碰到的：数据算错 / 丢失 / 被错误改写、输出与基线不符、
流程卡死或无法恢复、traceback、违反用户决议或 `AGENTS.md`。
写清"全量：未跑（按 AGENTS.md）"。
