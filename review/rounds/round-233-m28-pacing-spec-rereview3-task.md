# 第 233 轮任务书：M28 周期复盘规格第四次复审（gpt-6.1-sol，新窗口 sol61-m28）

## 背景

`contracts/pacing_review.md` 是 M28 周期复盘与调整的规格（用户 2026-09-30：基础时长 180–240 在区间内由复盘调整，前两个月每半月、之后每月，
AI 方案进 staging、用户提交才生效）。它已经过 sol 第 220、221、230 轮审阅，处理记录在其 §12。第 230 轮的 R10、R11 已关闭，
本版按 R12–R15 修订：§6 先按提交意图分流；§6.1 意图保存已校验的完整候选路线与摘要；§6.2 恢复分支只发布意图里的路线、`--dry-run` 覆盖所有分支；
§8 `settings.pacing` 经本地补充注册表登记（`contracts/workspace.md` §2.6 的允许键在 M28 实现时加入）。

## 必读

`AGENTS.md`；`contracts/pacing_review.md`；上几轮报告 `review/rounds/round-220-*-sol61.md`、`round-221-*-sol61.md`、`round-230-*-sol61.md`；
`contracts/workspace.md` §2.6；`contracts/route_plan.md`；`contracts/timetable.md` §4、§6；代码 `ky/schedule/budget.py`、`ky/storage/route_store.py`、
`ky/availability/port.py`（M18 计算接口以固定提交 `4816a14` 为准；工作区里 luna 正在改的 M29 文件不在范围内）。

## 请判断

1. R12–R15 是否关闭；恢复分支在"已生效 / 第 2 步前中断 / 路线已被改"三种状态与 `--dry-run` 下是否都有唯一结果。
2. 修订有无新的矛盾或二义（意图字段、摘要核对、manifest 一次读、生效日已过的说明）。
3. 是否已足以直接写实现任务书；只剩可在任务书里钉住的细节时列出，不必判 FAIL。

## 输出

`review/rounds/round-233-m28-pacing-spec-rereview3-sol61.md`：PASS / FAIL；必须改（附具体输入、草案结果、应有结果）/ 建议改 / 不改；安全登记单列。

## 禁止

不联网；只写这一份报告；不跑测试；不读仓库外文件；不写个人数据；不评审或改动 luna 正在做的 M29 文件。
