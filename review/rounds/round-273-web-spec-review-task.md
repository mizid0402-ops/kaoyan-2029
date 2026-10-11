# 第 273 轮任务书：⑥ 前端首版（M33 今日视图 + M16 本机网页）规格**初检**（gpt-6.1-sol，新窗口 sol61-m16）

## 背景

路线图 ⑤ 已完成。用户 2026-10-02 定 ⑥ 首版：本机小服务；"看 + 少量表单"（改某天可用分钟、记录做题结果）；首版只做"今天"页；
其余操作（学完入队、补题、复盘、路线）由 AI 在对话里运行命令。决策者据此写了两份规格，按 `AGENTS.md`"决策者细则先审再实现"先审细则。

## 只做初检（用户 2026-10-01）

只审规格本身，不写代码、不跑测试；每个"必须改"附可复现的反例或代码位置（每项 1 个探针为限）；非阻断问题各一行进"留给最终大检查"；报告约 60 行。范围：

1. `contracts/today.md`（新，M33）全文，重点：
   - 细则是否与用户原选项一致（§7 表格；"决策者拟定"一行逐条判断是否合理）；
   - §3 映射里每个字段能否由现有代码得到：`ky/__main__.py` 的 `_preflight_*`、`review_questions_main`、`ky/pacing/cli.py` 的 `pacing_status_main`，
     特别是"`preflight` / `reviews` 原样嵌入、两个 CLI 的 `--json` 以后从视图输出"是否会改变现有输出字节；
   - §3.2 `view_hash` 的组成是否足以发现"渲染后题目或入选项变了"，是否会在正常使用里误报（例如同一天 AI 刚补了改编题）；
   - §4 与 `ky day-plan record --review-store` 是否真能共用一条管线（`_day_plan_record_*`，冻结锁存、注册表一次读取 S15、完成事件只写一次）；缺题记 `recall_vs_notes` 是否合 D3；
   - §5 `set_day_minutes` 与 M26 规格（`contracts/availability.md`）是否冲突；
   - §6 对照基线 `60a4fd2` 的覆盖面是否够。
2. `contracts/web.md`（新，M16）全文，重点：日常使用会碰到的问题（例如跨午夜、浏览器回退重复提交、手机宽度）、与 M33 的分工、§6 测试要点能否落地。
   安全类只写进"安全登记"一节（`AGENTS.md` 威胁模型），不判 FAIL。

## 输出

`F:\workspace\kaoyan-ai-system\review\rounds\round-273-web-spec-review-sol61.md`：PASS / FAIL；必须改（附反例）；留给最终大检查；安全登记。

## 禁止

不联网；只写这一份报告；不改其他文件；不读 `data/personal/` 与 gitignore 的学习状态。
