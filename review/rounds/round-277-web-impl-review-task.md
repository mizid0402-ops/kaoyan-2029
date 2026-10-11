# 第 277 轮任务书：⑥ 前端首版**实现初检**（gpt-6.1-sol，续 sol61-m16）

luna-a 第 275 / 276 轮按 `contracts/today.md`、`contracts/web.md` 实现了 M33 与 M16（未提交，看工作区 `git diff` 与未跟踪文件）。
决策者已审 diff，并自行把重复的冻结锁存合并为 `ky/today/record.py::latch_freeze_if_needed`（CLI `submit` / `record` 与 M33 共用），
做过一次变异探针确认 `60a4fd2` 对照矩阵会抓到 CLI 文本变化。luna 报告：`review/rounds/round-276-web-rework-luna.md`。

## 只做初检（用户 2026-10-01）

只核对下列点名项，每项 1 个探针为限；非阻断问题一行进"留给最终大检查"；报告约 60 行。可以跑**单个**测试或单条命令复现，不跑全量。

1. 你第 274 轮的 R1 / R2 在规格（`today.md` §4 阶段表、§4.1）与实现里是否都关闭：恢复命令带齐实际路径、`advance` 与 `record` 路径规则一致、
   `freeze_written` 只在真的写了冻结事件时出现。
2. 实现者改了规格：`today.md` §2 / §4 新增 `submitted_review_ids`。判断是否合理、是否引入日常问题。
3. `tests/contract/test_today_port.py` 的固定基线矩阵是否覆盖 `today.md` §6 点名的分支，基线身份断言是否有效（不是新版对新版）。
4. M16 网页日常使用：缺题项的"对照后"声明、跨午夜、回退重交、两种部分失败页、表单 C；HTML 转义。
5. `ky/today/` 与 `ky/web/` 的 D7 可读性（函数长度、职责、是否 import 别模块私有名）。

## 输出

`F:\workspace\kaoyan-ai-system\review\rounds\round-277-web-impl-review-sol61.md`：PASS / FAIL；必须改（附可复现输入）；留给最终大检查；安全登记。

## 禁止

不联网；只写这一份报告；不改其他文件；不读 `data/personal/` 与 gitignore 的学习状态；不启动连到真实工作区的 `ky web`。
