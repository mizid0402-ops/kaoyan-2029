# 第 279 轮任务书：⑥ 前端首版**实现复审初检**（gpt-6.1-sol，续 sol61-m16）

你第 277 轮的 C1–C5 已由 luna-a 第 278 轮返工（报告：`review/rounds/round-278-web-rework2-luna.md`）；同轮另改了决策者实看发现的网页显示
（配额科目中文名、"本周期到 <终日> 结束，<次日> 复盘"、0 分钟）并给固定基线矩阵加了"带复习项、会推进队列"的 `record` 分支。
规格 `contracts/today.md` §4.1 补了一句 `advance` 与 `record` 在 `--review-store` 缺省上的差别（采纳你 277 的最终检查项）。

只做初检：只核对 C1–C5 是否关闭、新分支是否真比较了推进后的文件树、以及返工有无引入新的日常问题；每项 1 个探针为限；
可跑单个测试或单条命令，不跑全量；非阻断问题一行进"留给最终大检查"；报告约 40 行。

输出：`F:\workspace\kaoyan-ai-system\review\rounds\round-279-web-impl-rereview-sol61.md`：PASS / FAIL；仍需改（附可复现输入）；留给最终大检查。

禁止：不联网；只写这一份报告；不改其他文件；不读 `data/personal/` 与 gitignore 的学习状态；不启动连到真实工作区的 `ky web`。
