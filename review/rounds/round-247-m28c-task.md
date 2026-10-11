# 第 247 轮任务书：WP-M28c 输入包 / 提交 / 恢复 / 接线（gpt-6-luna，续 luna-a，worktree `F:\workspace\kaoyan-wt-m28c`，分支 `wip/m28c` 已含 M28a + M28b）

## 背景

规格 `contracts/pacing_review.md`（sol 第 233 轮 PASS；**以它为准**）。M28a（设置、周期、报告、完成事件 v3、`settings.pacing`）与 M28b（路线 v3、M8 三级基数）已合并。
本包做规格 §4（输入包与方案）、§5 的复盘设置接线、§6（提交：新提交分支 / 恢复分支 / `--dry-run`）、§6.1–6.2（提交意图）、§7（路线转换）、§9（preflight 提醒）、`ky pacing status`。
AI 指引 `prompts/pacing_review.md` 已由决策者写好，**不要改**。

## 要做的

1. **复盘设置接线**：`settings.pacing` 已登记时，preflight、M19 日输入包、`ky resume`、`ky timetable show`、报告（M28a 的 `base` / `reference_minutes`）、
   `ky/timetable_io.base_resolver` 把设置的 `start` / `initial` 作为 `PacingInitial` 传给 M8；M19 `availability` 对象在登记时带 `base_minutes`、`base_source`（M28b 已实现参数，本包接真实值）。
   报告 `base.source_note` 改为说明三级来源。未登记时一切输出逐字节不变（对 `8eca5be` 之后的合并提交做固定对照，断言取到旧版）。
2. **输入包**（§4）：`ky planner-input --kind pacing --cycle-end D [--today T]`；已保存报告不存在即违约；`input_hash` 用 M19 规范 JSON；`base_at` 取 `T`。
3. **路线存储公开读端口**（sol 233 细节 3）：在 `ky/storage/route_store.py` 增加一个公开方法，一次读取 manifest，同时给出当前修订号、指定目标修订的来源记录（actor、input_hash）
   与按现有规则核验过的目标路线；写端口持锁后重读 manifest 的检查保留不变。M28 不 import 存储私有方法。同步 `contracts/route_plan.md`。
4. **提交**（§6）：先读方案做形状校验、找到输入包得到 `D`，按意图文件是否存在**分流**；新提交分支七条护栏；`--dry-run` 覆盖所有分支；意图字段表与一致性校验
   （sol 233 细节 2：整数排除布尔、`target_revision = base_revision + 1`、外层 `actor` / `input_hash` 与 `proposal` 一致、`route.revision = target_revision`、
   `route.stage1_input_hash = input_hash`、两个摘要按规范映射计算——`route_sha256` 与 manifest 的原始字节摘要是两回事，细节 4）。
   恢复表三行与文案（细节 5：dry-run 用"将恢复提交"、第一 / 三行"不发布"，已有更高修订时说"历史应用"）。
5. **路线转换** `apply_pacing(route | None, proposal, settings, cycle_end)`（§7）：原地替换 / 切段 / 重编号 / 无路线新建，全部经 `validate_route_plan`。
6. **CLI**：`ky pacing submit --from-staging FILE [--dry-run] [--today T]`、`ky pacing status`（当前基数、下次复盘日期、未出报告的周期）。
   `staging/pacing/` 路径两步包含检查。退出码：用法 3、契约 2、成功 0；恢复表第三行 2。
7. **preflight 提醒**（§9）：`settings.pacing` 登记且 `T` 所在周期之前存在已结束、没有已保存报告的周期 → 多一行提醒；否则不变。
8. 模块头、规格同步：`contracts/pacing_review.md` 只在实现暴露出规格没写到的表示细节时补充，不改业务规则。

## 测试（只写这些，全部合成数据）

sol 第 233 轮报告 §二 的恢复三状态表（正式与 dry-run 各一例）与"无路线恢复不随设置延长"、"生效日已过仍发布并提示"两例；§6 七条护栏各一例拒绝；
§7 路线转换的五种情形（sol 220 R6 表）；复盘设置接线后 preflight / M19 / resume / timetable show / 报告取到 `pacing_initial` 基数；未登记设置时的固定对照；
preflight 提醒出现与不出现；`ky pacing status` 输出。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_pacing_port tests.contract.test_route_plan_port tests.contract.test_day_budget_port tests.contract.test_planner_port tests.contract.test_resume_port tests.contract.test_timetable_io_port tests.test_cli
```

报告 `review/rounds/round-247-m28c-luna.md`：改动、做法、测试输出原文、"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"、歧义与选择。不提交。报告与测试不含个人数据。
