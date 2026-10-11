# Round 110 Codex 定向复审：N1

范围：`a7f2a43`（`git log -1 --format=%h -- ky/schedule/review_clip.py`）。在该提交的 `git archive` 临时归档运行；未跑全量测试。

| 项目 | 意见 | 证据与可复现输入 |
| --- | --- | --- |
| N1 较长手填日 | **不改** | `ky/schedule/review_clip.py:307-320` 以 `max(配置硬上限, 当日硬上限)` 判定需拆分，与 `contracts/availability.md:55-58` 一致。重跑第 109 轮原输入：把 `tests/fixtures/config/config-minimal.yaml` 的 `total_daily_minutes` 改为 30、各科保底改为 0；队列只留首项并把成本改为 20；`data/availability.yaml` 在 2026-09-15 登记 60。临时归档运行 `py -3.12 -m ky preflight --json --config <临时配置> --items <临时队列> --date 2026-09-15 --workspace kaoyan.workspace.yaml`，退出 0；配置硬上限 18、当日硬上限 36，结果首项在 `selected`，`deferred=[]`、`unschedulable=[]`。这个合法输入已关闭。 |
| 第 107 轮 C2 原输入 | **不改** | 用正常 fixture 在 2026-09-15 调 `select_daily_reviews(..., daily_minutes_override=0)`，三个到期项均在 `deferred`，`unschedulable=[]`；30 分钟时第三项也进入 `deferred`。较小手填日仍只导致延期。 |
| 无 override 兼容 | **不改** | 以 `git show a7f2a43^:ky/schedule/review_clip.py` 加载旧选择器，在 2026-09-15、2026-09-16、2027-01-01 用相同配置与队列比较完整结果的 `repr(asdict(...)).encode('utf-8')`，三次均逐字节相等。代码上无 override 时 `hard_cap == config.review_hard_cap_minutes()`，故 `max(...)` 仍是原上限；配置的 `hard_max_ratio` 不超过 1。 |
| 新回归测试 | **建议改** | `tests/contract/test_availability_port.py:274-287` 的长日测试单跑通过；在临时归档把 `max(...)` 退回只取配置上限后，同一测试失败，能检出本次回退。但它沿用默认 120 分钟配置，构造成本为配置硬上限加一，即 73 分钟，超过合法复习单项的 30 分钟上限。建议改为本报告 N1 行的**合法**配置 30／手填 60／单项 20，保持撤修复变红的同时覆盖真实输入；当前测试的不足不阻断已验证的实现。 |

**结论：PASS。** 第 109 轮 N1 已关闭，零容量原修复与无 override 输出保持。定向运行 `py -3.12 -m unittest tests.contract.test_availability_port`：12 项通过；未跑全量。
