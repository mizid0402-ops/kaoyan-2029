# 评审：WP-E5b 时间线各科复习分钟生效到每日裁剪（决议 D10）

遵守 `AGENTS.md`（不跑全量）。范围：合并提交 `653e63b` 与实现提交 `1df327c`；`git diff 653e63b^1 653e63b`；运行用 `git archive 653e63b`（照前几轮补原始资料与 `products` 空目录）。
依据：`docs/阶段2.5-接缝收口.md` 的 D10（用户决定 + 决策者细则）；任务书 `review/rounds/round-113-wp-e5b-task.md`；实现者报告 `review/rounds/round-113-wp-e5b-luna.md`。
决策者审查时改了一处：把 `ky.models._scale_minutes` 直接改名为公开的 `scale_minutes`（删掉实现者加的转发包装，不留两个名字），调用方与 `tests/test_contracts.py` 同步。

请判断：
1. `resolve_day_budget`：阶段命中（右开区间、首尾日）；未知科目 / 缺在考科目 / 不在考科目 >0 的报错与路径；缩放到当天硬上限的精确性、确定性、同分规则；硬上限与 `select_daily_reviews` 是否同一公式（含手填 override 与 clamp）。
2. 分科裁剪：普通项受本科配额与全天硬上限双重约束；紧急项可超本科配额但不超硬上限；某科配额 0；配额外科目；`unschedulable` 规则未变；会计不变量（每个到期项恰落一桶）。**D10 细则本身是否合理**（可以反驳，例如紧急项借用是否会让某科长期挤占他科）。
3. 无路线 / 时间线外：preflight JSON 与文本、输入包字节与 `20f4391` 一致（对照测试是否真固定了旧版、是否两种场景都覆盖）。
4. 有配额时：JSON 新键只在有配额时出现；输入包 `review_clip` 等于 preflight `--json` 去 `config`；文本 `timeline phase` 行。
5. `scale_minutes` 改名是否有遗漏调用方；M8 ↔ M9 的 import 方向（`review_clip` import `budget`，`budget` import `availability` / `planning`）有无循环或越界。
6. 新测试撤实现是否变红。

产物：`review/rounds/round-114-review-sol-out.md`，每项"必须改 / 建议改 / 不改"附可复现输入，最后 PASS / FAIL。只写这一个文件。
