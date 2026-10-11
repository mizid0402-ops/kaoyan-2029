# 评审任务：WP-G3c S1 收尾 + WP-G3h（`tools/` 活跃工具拆分）

工作区状态：`master` = `24371ee`。**待审的是工作区未提交的改动**，本轮范围只有两部分：

| 部分 | 文件 | 报告 |
|---|---|---|
| G3c S1 收尾 | `ky/__main__.py`（去掉纯转发辅助 `_snapshot_build`）、`tests/test_cli_split_baseline.py` | `review/rounds/round-170-wp-g3h-tools-luna.md` 第一部分 |
| WP-G3h | `tools/` 下 8 个脚本 + 新增 `tests/test_tools_split_baseline.py` | 同报告第二部分 |

任务书：`review/rounds/round-170-wp-g3h-tools-task.md`。
仓库根 `AGENTS.md` 是你的常驻规则，**先读"验证范围"、"迁移 / 重构不得改变输出"（第 11–13 条）
与"评审严重度与威胁模型"三节**。实现者自述**只当线索**。

**不属于本轮范围**（别的包同时在改动，不要审、不要因它们的失败下结论）：
`ky/schedule/`、`ky/storage/`、`ky/ledger/`、`ky/freeze/`、`ky/acquisition/`。
（`ky/schedule/` 与存储侧的拆分包已由第 171 轮单独判 PASS。）

## 只做这四件事

1. **对照基线是否真的取到旧版**：`tests/test_tools_split_baseline.py` 与
   `CliG3cRemainderSplitBaselineTests` 都固定 `24371ee`。核对取到的确实是拆分前的长实现
   （各自断言了长度下界），且**不是**用 `HEAD`（`AGENTS.md` 第 12a 条）。
2. **拆出来的函数是否名副其实**：读完整 diff，核对 `ky/__main__.py` 里 `_snapshot_build`
   确实已删除且 `snapshot_main` 直接调用 `build_snapshot`；`tools/` 的新辅助各有具体职责
   （不是"只转发参数的辅助函数"）。亲自扫一遍行数，报告给实际数字。
3. **用户可见输出逐字节不变**（这是重点，第 49 轮在这里出过事故）：
   - `ky/__main__.py`：`snapshot` 的成功与失败路径。
   - `tools/render_weight_manual.py` 生成的**说明书正文**（章节、汇总段、表格文字）；
   - `tools/extract_408_questions_from_html.py` 的**产物文件字节与提取报告**；
   - `tools/netem_cross_validate.py` 的**报告每行内容**；
   - `tools/extract_exam_skeleton.py`、`probe_exam_pdf.py`、`verify_netem_source.py`、
     `verify_408_question_extraction.py` 的 stdout/stderr。
   你自己找**任务书没写进对照测试的**输入来验，至少覆盖：`render_weight_manual.py` 的
   **完整生成产物**与登记版本对照；`extract_408_questions_from_html.py` 的成功路径产物；
   `probe_exam_pdf.py` 的失败路径。
4. **`pinned_reproducer` / `migration` / `archived` / `retired` 脚本未被改动**（任务书写明不拆）。
   核对 `git status` 与 `tools/README.md` 的清单，确认这批确实没动。
   另外 `tools/round24_validate_weighted_tree.py::validate`（76 行）与
   `tools/round29_validate_agreement.py::validate`（78 行）**没有**被拆——这两个在
   `tools/README.md` 里标 `validation`，但文件名是 `round*` 历史脚本。说明你对这个取舍的判断
   （是否算"未完成任务"，还是与其余历史脚本同类、应留待另行决定）。

## 怎么做

- 用 `git archive 24371ee` 展开旧版到系统临时目录，新实现从工作区复制，在同一组输入上对比。
- 需要外部原始资料的用例：缺资源的按 `tests/_resources.require_path` 跳过并写明缺什么，
  不要把它当成通过。
- 做变异 / 调换时设 `PYTHONDONTWRITEBYTECODE=1` 并清 `__pycache__`。
- **只读**：不要改仓库源码、不要提交。
- **不跑全量测试**。要复现只跑最小命令，例如 `py -3.12 -m unittest tests.test_tools_split_baseline`、
  `py -3.12 -m unittest tests.test_cli_split_baseline`，以及你为复现缺陷需要的最小模块。

## 报告

写到 `review/rounds/round-172-g3h-tools-review-codex.md`：结论（PASS / FAIL）、
"必须改"（每条给可复现输入与实测输出）、"建议改"、"不改"（你验过没问题的路径）、
**安全登记一节**（按 `AGENTS.md` 威胁模型：恶意输入 / 手工篡改 / 精确竞态才算）。
"必须改"只列日常正常使用会碰到的：数据算错 / 丢失 / 被错误改写、输出与基线不符、
流程卡死或无法恢复、traceback、违反用户决议或 `AGENTS.md`。
写清"全量：未跑（按 AGENTS.md）"。
