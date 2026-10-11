# Round 118 Codex 复审与评审

范围：`a79c06a` 与 R1 合并提交 `b7f6a7b`。所有运行均在系统临时目录的 `git archive b7f6a7b` 中，补入本机 `data/raw_materials/` 与空 `products/`；固定基线测试设置 `GIT_DIR`。只运行直接相关模块，不审 R2 的实现。

## A. `a79c06a`：第 116 轮 B1

| 项目 | 判断 | 证据、可复现输入 |
|---|---|---|
| 同科紧急优先 | 不改 | 重跑原探针：硬上限 72，配额 `math1=10, eng1=62`；`regular`（math1、9/14 到期、延期 0 次、成本 10）、`urgent`（math1、9/15 到期、延期 2 次、成本 10）、`other`（eng1、成本 62）。9/15 结果为 `selected=('urgent','other')`、`deferred=('regular',)`。`ky/schedule/review_clip.py:283-308` 先剔除不可安排项，再将紧急与普通分组，组内保留原排序；在有效队列的唯一 `review_id` 前提下，第一遍紧急项会先占本科配额，第二遍才借空位。 |
| 原始配额超额 | 不改 | `ky/schedule/review_clip.py:404-416` 在挑选前拒绝配额和大于当天硬上限。直接传入 `math1=72, eng1=10`、硬上限 72，得到 `ContractError.path == 'subject_review_quotas'`；M8 生成的配额仍先缩放，不受此防线误拒。 |
| 文档与撤修复 | 不改 | `select_daily_reviews` docstring（`ky/schedule/review_clip.py:346-351`）及 `contracts/route_plan.md:72` 已明确紧急组先于普通组、两组内按原优先级。归档单跑 `tests.contract.test_day_budget_port`：12/12。临时将裁剪实现撤为 `2bbeaae:ky/schedule/review_clip.py`，`test_urgent_item_precedes_longer_overdue_regular_in_its_own_quota` 与 `test_raw_quotas_above_hard_cap_are_refused` 分别变红；随后恢复归档文件。 |

**A：PASS。**

## B. WP-R1 积压冻结（M27）

| 项目 | 判断 | 证据、可复现输入 |
|---|---|---|
| B1 计数与阈值 | 不改 | `ky/freeze/port.py:39-63` 只计 `queued` 且 `due_date < day`；阈值为 `backlog_days × config.review_hard_cap_minutes()`，等号冻结，空队列即使阈值取整为 0 也不冻结。`tests/contract/test_freeze_port.py:113-145` 检查边界、scheduled 与当天到期排除、零容量空队列。已过期 `scheduled` 在 M9 是 `unreachable` 而非可裁剪积压；按 D11 现有口径不宜悄悄计入 queued 阈值，建议另设显式状态修复提示或停排规则，避免大量 unreachable 仍继续排新内容。 |
| B2 冻结效果与旧版字节 | 建议改 | `ky/__main__.py:313-346` 与 `ky/planner/port.py:48-68` 均在普通预算解析后调用 M27；冻结时传 `daily_minutes_override=0` 且不传阶段配额。归档探针：手填 60 分钟、已登记阶段三科各 20、9 个各 24 分钟的逾期 queued 项（合计 216，阈值 216），preflight 与 M19 的 `review_clip` 相同：selected 空、新内容 0、`subject_review_quotas` 不出现、`freeze` 出现；外层输入仍如实记录 availability 与路线。`tests/contract/test_freeze_port.py:147-223` 固定 `2bbeaae55e82725baed492143c494ffe22d1d6ec`、断言取到旧入口，比较未冻结 JSON／文本输出和规范输入包字节，测试通过。**展示仍有歧义**：冻结文本继续显示 `review soft / hard : 0 / 0 min (timeline quotas / 0.6)` 和阶段配额行，虽然阶段配额并未生效（`ky/__main__.py:358-373`）；建议标为“冻结期间不生效”或隐藏这两处。 |
| B3 两种 submit 与双读 | **必须改** | 静态提案内容经两次相同的严格 YAML／`parse_day_plan` 解析，未找到同一字节得到两个 `day` 的办法；但 `ky/__main__.py:143-148,846-859` 先读并检验，`ky/planner/port.py:282-312` 随后**重读可变文件**。归档探针在原 `_reject_submission_while_frozen` 返回后、M19 重读前，将提案从 `9/14` 改为冻结日 `9/15`：`--plan` 退出 0，实际写出 `2026-09-15--v1.yaml`。对 `--from-staging` 用相同换文件时机、预先生成冻结日的有效输入包及匹配 hash，也退出 0 并写出该冻结日计划。前提队列在 9/15 达阈值、9/14 尚未逾期；两种入口均绕过“冻结日 submit 拒绝且不写”。最小方向是让 M19 的**最终已解析计划对象**接受冻结检查，并在同一次解析所得对象上完成校验与提交，而不是 CLI 对路径另读一遍。另测：有效注册表向上发现时冻结拒绝退出 2；显式无效注册表退出 2；找不到注册表而显式给 `--store` 时按规格跳过检查、可写；已登记队列无 manifest 时视为空队列、可写。 |
| B4 `--freeze-backlog-days` | 不改 | `FreezePolicy` 在 `ky/freeze/port.py:17-25` 拒绝 bool、非整数与小于 1；CLI 在 `ky/__main__.py:206-211,305-310` 将策略值错误转成退出 3。归档实测 `0/-1 → 3`，`1 → 0`，同一队列调高天数可不冻结。`abc` 由 argparse 在策略构造前退出 2，与现有整数参数的 argparse 用法一致；规格只承诺低于 1 的值退出 3。 |
| B5 D11 细则 | **必须改** | **“冻结只由当前队列推导”与用户选择的“手动 `ky resume` 重启”不能同时成立。** 归档实际命令：27 个各 8 分钟的逾期项正好 216/216，`assess_freeze(...).frozen=True`；冻结期间执行允许的 `day-plan record --review-store`，带一条 `past_question/correct` 的完成记录，退出 0、队列推进 1 条；随后剩余逾期 208/216，`assess_freeze(...).frozen=False`，**没有执行 `ky resume` 就自动解冻**。`ky/freeze/port.py:47-63` 与 `contracts/freeze.md` 明确没有冻结锁存状态，R2 若仍只靠队列也无法区分这次自动解冻。需在决议上二选一：承认完成记录可自动解冻并修改“手动重启”，或保存可审计的冻结／恢复状态，使 record 不解除冻结。阈值采用配置容量而不随单日手填 0 波动是合理的。 |
| B6 测试撤回敏感性 | 建议改 | 归档单跑 `tests.contract.test_freeze_port`：6/6。临时把阈值 `>=` 撤成 `>`，边界测试失败；把 submit 冻结预检撤掉，`test_submit_is_rejected_while_record_remains_allowed` 因 human 入口由 2 变 0 而失败；恢复文件。冻结 payload 测试也断言 selected 空、新内容 0、M19 与 preflight 相同。现有测试只用不可变提案文件，未覆盖 B3 的两次读取窗口；record 用 `reviews: []`，未覆盖 B5 的实际自动解冻。两条应成为修复回归输入。 |

**B：FAIL。** B3 可向冻结日写计划，B5 会在未执行手动恢复时解除冻结，均违反本轮验收／D11 承诺。未跑全量测试。

## 总结

**整体 FAIL**：`a79c06a` 已关闭第 116 轮 B1；R1 的判定和静态冻结效果成立，但 submit 双读窗口与“手动恢复”语义冲突需先处理。
