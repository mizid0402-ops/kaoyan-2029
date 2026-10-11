# 定向复审：sol 第 109 轮 N1（较长手填日误判"需拆分"）

遵守 `AGENTS.md`（不跑全量）。范围只限本轮修复提交（`git log -1 --format=%h -- ky/schedule/review_clip.py`），运行用 `git archive <该提交>`。

决策者承认第 108 轮任务书里定的 C2 规则错了（只看配置硬上限）。修正为：`unschedulable_cap = max(配置硬上限, 当日硬上限)`——两个都装不下才提示拆分；
当日上限较小只延期，较大可入选；无 override 时两者相等、结果不变。`select_daily_reviews` docstring 与 `contracts/availability.md` 同步修订。
新测试 `test_long_availability_day_schedules_item_above_configured_cap`（当日容量为配置两倍，成本 = 配置硬上限 + 1 → 入选、无 unschedulable）；撤回为只看配置上限时变红。

请用你第 109 轮的原探针（配置 30 分钟、保底 0、单项 20 分钟、手填 60）重跑，并确认第 107 轮 C2 原输入（手填 0 全部延期）仍关闭、无 override 时逐字节不变。

产物：`review/rounds/round-110-review-sol-out.md`，每项"必须改 / 建议改 / 不改"，最后 PASS / FAIL。只写这一个文件。
