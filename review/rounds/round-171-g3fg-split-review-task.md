# 评审任务：WP-G3f（`ky/schedule/`）与 WP-G3g（`ky/storage/`、`ky/ledger/`、`ky/freeze/`）拆分

工作区状态：`master` = `24371ee`。**待审的是工作区未提交的改动**（两个包同时在工作区里）：

| 包 | 文件 | 实现报告 |
|---|---|---|
| WP-G3f | `ky/schedule/*.py`（5 个）+ 新增 `tests/contract/test_schedule_split_baseline.py` | `review/rounds/round-168-wp-g3f-schedule-luna.md` |
| WP-G3g | `ky/storage/review_shards.py`、`ky/storage/day_plan_store.py`、`ky/ledger/material.py`、`ky/ledger/citations.py`、`ky/freeze/resume.py`、`ky/acquisition/ledger_restore.py` + 新增 `tests/contract/test_storage_ledger_split_baseline.py` | `review/rounds/round-169-wp-g3g-storage-ledger-luna.md` |

任务书：`review/rounds/round-168-wp-g3f-schedule-task.md`、`review/rounds/round-169-wp-g3g-storage-ledger-task.md`。
仓库根 `AGENTS.md` 是你的常驻规则，**先读"验证范围"与"迁移 / 重构不得改变输出"两节**。
两个实现者的自述**只当线索**。

**注意**：另有 `ky/__main__.py` 与 `tools/` 的未提交改动属于第三、第四个包（`luna-a`），
**不在本轮范围**，不要审它们，也不要因为它们的失败下结论。

## 只做这四件事

1. **对照基线是否真的取到旧版**：两个新增测试都用 `git show 24371ee:<文件>`。
   核对取到的确实是拆分前的长实现（各自断言了长度下界），且**不是**用 `HEAD`
   （`AGENTS.md` 第 12a 条）。
2. **拆出来的函数是否名副其实**：读完整 diff，核对六个主函数确实变短、新辅助各有具体职责
   （不是"只转发参数的辅助函数"）。**逐个文件亲自扫一遍行数**，报告里给出实际数字。
3. **用户可见输出与行为逐字节不变**：这是纯重构。你自己找几个**任务书没写进对照测试的**
   输入来验。至少覆盖：
   - `select_daily_reviews`：配额路径与非配额路径各一，含紧急项借用；
   - `close_month`：同一日期重复计划的违规计数；
   - `restore_materials`：`--check` 不建临时目录、畸形 URL 仍在单行内处理（sol 164 修的三项）；
   - `plan_resume`：D11"逾期天数 > 当前间隔"的边界；
   - `_publish_commit`：新增分片与移除分片两种提交的 manifest 与存储树字节。
4. **行为裂缝**：`WP-G3g` 的实现报告"留意事项"一节说
   `ReviewShardStore._publish_commit` 原本就用 `os.replace` 发布、**没有** `os.link` 身份复核，
   与 `AGENTS.md` 已知缺陷第 1 条及 `route_store._write_version` 的做法不一致。
   **独立核实这个说法**（`git show 24371ee:ky/storage/review_shards.py`），确认它是否属实、
   是否已被 `docs/安全风险登记.md` 登记（我看到 S19 已补登记）。若属实且未登记，写进你的
   "安全登记"一节；**不要**要求本轮回工修它（按 `AGENTS.md` 的威胁模型，属安全登记）。

## 怎么做

- 用 `git archive 24371ee` 展开旧版到系统临时目录，新实现从工作区复制，在同一组输入上对比。
- 做变异 / 调换时设 `PYTHONDONTWRITEBYTECODE=1` 并清 `__pycache__`。
- **只读**：不要改仓库源码、不要提交。
- **不跑全量测试**。要复现只跑最小命令，例如
  `py -3.12 -m unittest tests.contract.test_schedule_split_baseline`、
  `py -3.12 -m unittest tests.contract.test_storage_ledger_split_baseline`，
  以及你为复现缺陷需要的最小模块。

## 报告

写到 `review/rounds/round-171-g3fg-split-review-codex.md`：**分两节**（G3f / G3g），
各写结论（PASS / FAIL）、"必须改"（每条给可复现输入与实测输出）、"建议改"、"不改"（你验过没问题的路径）。
另加**安全登记一节**（含上面第 4 条核实结果）。
"必须改"只列日常正常使用会碰到的：数据算错 / 丢失 / 被错误改写、输出与基线不符、
流程卡死或无法恢复、traceback、违反用户决议或 `AGENTS.md`。
写清"全量：未跑（按 AGENTS.md）"。
